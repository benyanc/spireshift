"""Screen, replay and index complete normal-start A8 demonstrations."""

from __future__ import annotations

import argparse
import gzip
import json
import re
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_replay_probe as replay
from spireshift import native_a8_replay_source as replay_source
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path, _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_mix_session import Study, admit, unchanged
from spireshift.native_a8_replay_source import BUILD, Intent, Journal
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_compatibility_contract import local, verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_flow_inputs_v12 import canonical_seed
from spireshift.native_flow_verification_v12 import records
from spireshift.native_win4_game import write
from spireshift.native_win_teacher import validate_student_input

AREA = "artifacts/native-a8-archive-batch"
RECIPE = "configs/native-curriculum/sts2-v0.111.0-a8-archive-pilot-v1.json"
SCHEMA = "native-a8-archive-batch-v1"
WIN = "verified_native_victory"
FAMILIES = {
    "combat_turn",
    "map_navigation",
    "event_option",
    "card_reward_selection",
    "reward_claim",
    "shop_inventory",
    "rest_site",
}
REPLAY_FILES = ("native_a8_replay_probe.py", "native_a8_replay_source.py")
FAILURES = (ValueError, LookupError, OSError, TimeoutError, TypeError, StopIteration)
SELECTOR_EFFECTS = {"deck_select_transform": "transform", "deck_select_enchant": "enchant"}
compile_archive_intents = replay_source.compile_intents


def validate_plan(cfg: dict[str, Any]) -> None:
    cases = cfg["cases"]
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["game_build"] != BUILD
        or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,60}", cfg["batch"])
        or cfg["batch"] == "execution"
        or not 1 <= len(cases) <= 40
        or not 75 <= cfg["case_wall_seconds"] <= replay.FULL_SECONDS
        or not cfg["case_wall_seconds"] <= cfg["wall_seconds"] <= 5400
    ):
        raise ValueError("Require a bounded exact-build archive batch")
    ids = [case["run_id"] for case in cases]
    sources = [case["source"]["sha256"] for case in cases]
    seeds = [case["seed"] for case in cases] + cfg["development_seeds"] + cfg["final_test_seeds"]
    if (
        any(not re.fullmatch(r"[a-f0-9]{16}", run_id) for run_id in ids)
        or len(set(ids)) != len(ids)
        or len(set(sources)) != len(sources)
        or not cfg["development_seeds"]
        or not cfg["final_test_seeds"]
        or len(set(seeds)) != len(seeds)
        or any(canonical_seed(seed) != seed for seed in seeds)
    ):
        raise ValueError("Archive training worlds and reserved seeds must be distinct")
    for case in cases:
        if set(case) - {"run_id", "seed", "source", "saved"}:
            raise ValueError("Unsupported archive case field")
        if Path(case["source"]["path"]).parts[:1] != ("artifacts",) or not re.fullmatch(
            r"[a-f0-9]{64}", case["source"]["sha256"]
        ):
            raise ValueError("Store archive journals under private artifacts")


def known_seeds(base: Study) -> set[str]:
    root, ctx = base.root, base.ctx
    parent = json.loads(verified(root, ctx["config"]["parent_recipe"]).read_text())
    history = json.loads(verified(root, parent["seed_history"]).read_text())
    used = set(history["canonical_prior_seeds"])
    used.update(parent["plan"]["reserved_evaluation_seeds"])
    used.update(ctx["paired_panel"]["worlds"])
    used.update(base.cfg["development"] + [base.cfg["prefix_seed"], base.cfg["ending_seed"]])
    for scope in ("study", "control"):
        data = base.source.recipe[scope]
        used.update(task["seed"] for task in data["training"])
        used.update(data["development"] + data["reload"])
    used.update(entry["seed"] for entry in base.bank["entries"].values())
    for cases in ctx["practice_cases"].values():
        used.update(seed for case in cases for seed in case["seed_pool"])
    return used


def source_facts(journal: Journal) -> dict[str, Any]:
    def event(intent: Intent, event_id: str) -> bool:
        return intent.kind == "event" and (intent.offer or {}).get("event_id") == event_id

    (opening,) = (
        intent
        for intent in journal.intents
        if event(intent, "NEOW")
        and intent.record["act"] == 1
        and intent.record["floor"] == 1
        and intent.record["option_id"].startswith("NEOW.")
    )
    final = journal.intents[-1]
    last_fight = next(i.record for i in reversed(journal.intents) if i.kind == "combat_end")
    boss = last_fight["combat_id"].split(":", 1)[1]
    if (
        not event(final, "THE_ARCHITECT")
        or final.record.get("option_id") != "PROCEED"
        or last_fight["act"] != 3
        or last_fight["floor"] != final.record["floor"]
        or boss not in {"AEONGLASS_BOSS", "QUEEN_BOSS", "TEST_SUBJECT_BOSS"}
    ):
        raise ValueError("Require a recorded final boss and Architect Proceed")
    # Version 7 can omit an entire grid. The recorded event choice alone cannot
    # identify the selections or the decline, even if a later reward is present.
    selected_rooms = {
        (i.record["act"], i.record["floor"]) for i in journal.intents if i.kind == "pick"
    }
    if any(
        event(i, "CRYSTAL_SPHERE")
        and i.record.get("option_id") == "CRYSTAL_SPHERE.pages.INITIAL.options.PAYMENT_PLAN"
        and (i.record["act"], i.record["floor"]) not in selected_rooms
        for i in journal.intents
    ):
        raise ValueError("Crystal Sphere Payment Plan has no recorded grid answer")
    return {
        "seed": journal.seed,
        "opening": opening.record["option_id"],
        "act1_boss": journal.boss,
        "final_boss": boss,
        "source_intents": len(journal.intents),
    }


def recorded_selectors(rows: list[dict[str, Any]]) -> tuple[Intent, ...]:
    """Keep the actual pick when a deck selector also reports a matching outcome."""
    linked: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        if "decision_id" in row:
            linked.setdefault(row["decision_id"], []).append(row)
    normalized = list(rows)
    for row in rows:
        effect_kind = SELECTOR_EFFECTS.get(row.get("decision_type", ""))
        if row["t"] != "outcome" or effect_kind is None:
            continue
        group = linked[row["decision_id"]]
        offers = [entry for entry in group if entry["t"] == "decision"]
        picks = [entry for entry in group if entry["t"] == "pick"]
        effects = [entry for entry in group if entry["t"] == effect_kind]
        if len(offers) != 1 or len(picks) != 1 or sum(e["t"] == "outcome" for e in group) != 1:
            raise ValueError(f"Deck selector at record {row['s']} lacks one offer and exact pick")
        (offer,), (pick,) = offers, picks
        cards = pick["cards"]
        indices = [c["option_index"] for c in cards]
        eligible = {
            o["option_index"]: (o["instance_id"], o["option_id"], o["up"])
            for o in offer["options"]
            if o["presented"] and o["selectable"]
        }
        effect_cards = {
            e["option_index"]: (e["from_c"], e["from_id"])
            if effect_kind == "transform"
            else (e["c"], e["id"])
            for e in effects
        }
        if (
            not cards
            or row["outcome"] != "select"
            or pick["selector"] != "human"
            or any(e.get("decision_type") != row["decision_type"] for e in (offer, pick))
            or any(
                (e["act"], e["floor"]) != (row["act"], row["floor"])
                for e in (offer, pick, *effects)
            )
            or not offer["s"] < pick["s"] < row["s"]
            or any(not pick["s"] < e["s"] < row["s"] for e in effects)
            or not offer["min_select"] <= len(cards) <= offer["max_select"]
            or len(cards) != len(set(indices))
            or len(cards) != len(effects)
            or len(cards) != row["n_selected"]
            or len(cards) != pick["n_picked"]
            or indices != row["selected_option_indices"]
            or any(
                eligible.get(c["option_index"]) != (c["c"], c["id"], c["up"])
                or effect_cards.get(c["option_index"]) != (c["c"], c["id"])
                for c in cards
            )
        ):
            raise ValueError(f"Deck selector records disagree at outcome {row['s']}")
        normalized[row["s"]] = {**row, "t": "corroborated_selector_outcome"}
    return compile_archive_intents(normalized)


def screen(root: Path, case: dict[str, Any]) -> tuple[Journal | None, dict[str, Any]]:
    source = verified(root, case["source"])
    try:
        with patch.object(replay_source, "compile_intents", recorded_selectors):
            journal = replay_source.read(source)
        facts = source_facts(journal)
    except (ValueError, LookupError, TypeError, StopIteration) as exc:
        return None, {"status": "source_rejected", "error": str(exc)}
    if journal.seed != case["seed"]:
        raise ValueError("Declared source seed differs from the journal")
    return journal, {"status": "source_ready", **facts}


def check_private_run(out: Path, journal: Journal, report: dict[str, Any], decisions: int) -> None:
    allowed = {
        "runtime_identity",
        "run_identity",
        "process_metrics",
        "get_map",
        "action",
        "start_run",
        "quit",
    }
    starts: list[dict[str, Any]] = []
    quits: list[dict[str, Any]] = []
    identities: list[dict[str, Any]] = []
    action_count = 0
    last = None
    for row in records(out / "worker/private-transcript.jsonl.gz"):
        request, response = row["request"], row["response"]
        command = request["cmd"]
        if command not in allowed or quits:
            raise ValueError("Archive replay used a command outside the fresh-run contract")
        if command == "start_run":
            starts.append(request)
        elif command == "run_identity" and starts:
            identities.append(response)
        elif command == "action":
            if len(starts) != 1:
                raise ValueError("Native action outside the single fresh run")
            action_count += 1
        elif command == "quit":
            quits.append(response)
        last = command
    (start,) = starts
    (quit_result,) = quits
    identity = report["native_ending"]["private_final_identity"]
    closed = json.loads((out / "worker/closed.json").read_text())
    normal_start = {
        "cmd": "start_run",
        "seed": journal.seed,
        "character": "Ironclad",
        "ascension": 8,
        "lang": "en",
        "content_policy": "native_benchmark_full_v1",
    }
    if (
        start != normal_start
        or not identities
        or identities[-1] != identity
        or identities[0]["started_with_neow"] is not True
        or any(item["seed"] != journal.seed or item["native_abandoned"] for item in identities)
        or action_count != decisions
        or last != "quit"
        or quit_result["success"] is not True
        or quit_result["save"] is not None
        or closed["episodes"] != 1
        or closed["clean_exit"] is not True
        or closed["runtime_errors"]
    ):
        raise ValueError("Archive run startup, ending or clean shutdown did not verify")


def labels(out: Path, path: Path, deliveries: int) -> dict[str, Any]:
    """Export only current public menus and answers, grouping local selector factors."""
    raw = iter(records(out / "worker/public-observations.jsonl.gz"))
    current = next(raw)
    factors: list[dict[str, Any]] = []
    group_owner = None
    by_act: dict[int, Counter[str]] = {}
    decisions = count = 0
    with gzip.open(path, "xt", encoding="utf-8") as stream:
        for row in records(out / replay.TRACE):
            snapshot = current["snapshot"]
            menu = snapshot["bound_actions"]
            frame, choice, receipt = row["frame"], row["choice"], row["receipt"]
            public, actions = frame["public_input"], frame["actions"]
            index = choice["action_index"]
            current = next(raw)
            if (
                menu["status"] != "complete"
                or menu["total_count"] != len(menu["actions"])
                or len(public["candidates"]) != len(actions)
                or sorted(a["raw_index"] for a in actions) != list(range(len(menu["actions"])))
                or any(
                    a["bound_action_id"] != menu["actions"][a["raw_index"]]["bound_action_id"]
                    for a in actions
                )
                or type(index) is not int
                or not 0 <= index < len(actions)
                or choice["binding_id"] != frame["binding_id"]
                or receipt["bound_action_id"] != actions[index]["bound_action_id"]
                or receipt["delivery"] != "delivered"
                or receipt["before_snapshot_id"] != snapshot["snapshot_id"]
                or receipt["successor_snapshot_id"] != current["snapshot"]["snapshot_id"]
                or frame["terminal"]
            ):
                raise ValueError("Demonstration requires the complete delivered public menu")
            validate_student_input(public)
            run = public["context"]["persistent"]["run"]
            act = run["act"]
            family = public["context"]["interaction"]["kind"]
            domain = receipt["delivery_domain"]
            verb = public["candidates"][index]["verb"]
            owner = (act, run["floor"], family)
            if factors and owner != group_owner:
                raise ValueError("Local factors must finish at the same public owner")
            group_owner = owner
            factors.append({"public_input": public, "action_index": index})
            count += 1
            if domain == "local_answer_factor" and verb == "select":
                continue
            if domain != "native" or (len(factors) > 1 and verb not in {"confirm", "cancel"}):
                raise ValueError("Require a native receipt for each complete answer")
            by_act.setdefault(act, Counter())[family] += 1
            decisions += 1
            stream.write(json.dumps({"act": act, "family": family, "factors": factors}) + "\n")
            factors = []
        if factors or not decisions or count != deliveries or next(raw, None) is not None:
            raise ValueError("Archive trace has an incomplete answer or delivery count")
        if set(by_act) != {1, 2, 3}:
            raise ValueError("Demonstration labels must cover all three acts")
    return {"decisions": decisions, "deliveries": count, "by_act": by_act}


def audit(
    base: Study,
    case: dict[str, Any],
    journal: Journal,
    out: Path,
    target: Path,
    report: dict[str, Any],
    before: dict[str, bool],
    deadline: float,
    *,
    saved: bool,
) -> dict[str, Any]:
    config = identified(out / "config.json", "config_id")
    frame = identified(out / "last-frame.json")
    frame.pop("report_id")
    if (
        config["config_id"] != report["config_id"]
        or config["objective"] != base.cfg["objective"]
        or config["seed"] != journal.seed
        or config["source"] != f"https://spire-codex.com/runs/{case['run_id']}/replay"
        or config["source_sha256"] != case["source"]["sha256"]
        or report["source_sha256"] != case["source"]["sha256"]
        or config["environment_id"] != base.ctx["environment_id"]
        or report["environment_id"] != config["environment_id"]
        or report["status"] != "native_archive_victory_verified"
        or report["genuine_native_victory"] is not True
        or report["stop"] is not None
        or report["clean_shutdown"] is not True
        or report["optimizer_updates"] != 0
        or report["frozen_checks"] != before
        or not all(before.values())
        or config["source_prefix_intents"] != len(journal.intents)
        or report["source_intents"] != len(journal.intents)
        or report["source_intents_consumed"] != len(journal.intents)
    ):
        raise ValueError("Require a complete verified replay on the frozen environment")
    check_sources(
        base.root,
        {f"src/spireshift/{name}": config["implementation"][name] for name in REPLAY_FILES},
    )
    replay.victory(frame, journal, report["native_ending"])
    deliveries = report["verified_native_deliveries"]
    if saved:
        locale = base.ctx["native"]["localization"] / "localization_eng"
        names = {
            (kind, key.removesuffix(".title")): value
            for kind in ("potion", "relic", "card")
            for key, value in json.loads((locale / f"{kind}s.json").read_text()).items()
            if key.endswith(".title")
        }
        if (
            replay.verify(
                base.ctx,
                out,
                replace(journal, reward_names=names),
                len(journal.intents),
                deadline,
                frame,
                log=target / "verify.log",
            )
            != deliveries
        ):
            raise ValueError("Saved replay does not reconstruct the declared deliveries")
    label_path = target / "public-answers.jsonl.gz"
    counts = labels(out, label_path, deliveries)
    check_private_run(out, journal, report, counts["decisions"])
    return {
        **source_facts(journal),
        "status": WIN,
        "replay_report_id": report["report_id"],
        "labels": {"path": str(label_path.relative_to(base.root)), "sha256": _sha_file(label_path)},
        **counts,
    }


def summarize(cfg: dict[str, Any], rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    winners = {key: row for key, row in rows.items() if row["status"] == WIN}
    by_act: dict[int, Counter[str]] = {}
    for row in winners.values():
        for act, counts in row["by_act"].items():
            by_act.setdefault(int(act), Counter()).update(counts)
    openings = sorted({row["opening"] for row in winners.values()})
    first = sorted({row["act1_boss"] for row in winners.values()})
    final = sorted({row["final_boss"] for row in winners.values()})
    outcomes = Counter(row["status"] for row in rows.values())
    all_resolved = all(
        row["status"] in {WIN, "source_rejected", "diverged"} for row in rows.values()
    )
    checks = {
        "all_cases_resolved": all_resolved and len(rows) == len(cfg["cases"]),
        "three_distinct_winning_worlds": len({row["seed"] for row in winners.values()}) >= 3,
        "two_distinct_openings": len(openings) >= 2,
        "two_distinct_act1_bosses": len(first) >= 2,
        "two_distinct_final_bosses": len(final) >= 2,
        "all_acts_and_decision_families": set(by_act) == {1, 2, 3}
        and set().union(*by_act.values()) >= FAMILIES,
    }
    return {
        "planned_worlds": len(cfg["cases"]),
        "outcomes": dict(outcomes),
        "verified_worlds": len(winners),
        "native_delivery_count": sum(row["deliveries"] for row in winners.values()),
        "public_answers_by_act_and_owner": by_act,
        "openings": openings,
        "act1_bosses": first,
        "final_bosses": final,
        "checks": checks,
        "candidate_for_separate_fitting_admission": all(checks.values()),
        "bank": {key: {"seed": row["seed"], **row["labels"]} for key, row in winners.items()},
    }


def execute(
    root: Path,
    recipe: Path,
    cfg: dict[str, Any],
    screened: dict[str, tuple[Journal | None, dict[str, Any]]],
) -> dict[str, Any]:
    deadline = time.monotonic() + cfg["wall_seconds"]
    base = admit(root)
    before = frozen(root, base.ctx)
    if (
        cfg["environment_id"] != base.ctx["environment_id"]
        or cfg["objective"] != base.cfg["objective"]
        or cfg["game_limits"] != base.cfg["game_limits"]
        or not all(before.values())
    ):
        raise ValueError("Archive batch requires the frozen native execution and objective")
    if known_seeds(base).intersection(
        [case["seed"] for case in cfg["cases"]] + cfg["development_seeds"] + cfg["final_test_seeds"]
    ):
        raise ValueError("An archive or reserved world overlaps the existing native study worlds")
    scope = ChunkJournal(root, {"workspace": f"{AREA}/execution", "schema_version": SCHEMA})
    implementation = {
        str(p.relative_to(root)): _sha_file(p)
        for p in (Path(__file__), *(Path(__file__).with_name(name) for name in REPLAY_FILES))
    }
    store = ChunkJournal(
        root, {**cfg, "workspace": f"{AREA}/{cfg['batch']}", "implementation": implementation}
    )
    profile = _shared_snapshot(Path.home() / SHARED_PROFILE)
    rows = {
        case["run_id"]: {"status": "unattempted", "seed": case["seed"]} for case in cfg["cases"]
    }
    seals = {}
    stop = None
    with scope.lock(), store.lock():
        result_path = store.workspace / "result.json"
        if result_path.exists():
            result = identified(result_path)
            if result["config_id"] != store.config_id or result["frozen_checks"] != before:
                raise ValueError("Saved archive batch identity or frozen state differs")
            for case in cfg["cases"]:
                key = case["run_id"]
                if key in result["seals"]:
                    seal = store.completed(key, case)
                    if (
                        seal is None
                        or seal["report_id"] != result["seals"][key]
                        or seal["result"] != result["worlds"][key]
                    ):
                        raise ValueError("Saved archive batch seal differs")
            return result
        for case in cfg["cases"]:
            key = case["run_id"]
            journal, screening = screened[key]
            source = verified(root, case["source"])
            hashes = {str(source.relative_to(root)): case["source"]["sha256"]}
            try:
                old = store.completed(key, case)
                if old is not None:
                    rows[key], seals[key] = old["result"], old["report_id"]
                    if rows[key]["status"] == "uncertain":
                        stop = {"run_id": key, "error": rows[key]["error"]}
                        break
                    continue
                if journal is not None and not case.get("saved") and _running_games():
                    raise ValueError("Close STS2 and wait for any other native worker")
                if time.monotonic() >= deadline - 15:
                    raise TimeoutError("Archive batch wall guard reached")
                target = store.begin(key, case)
                if journal is None:
                    row = screening
                elif case.get("saved"):
                    evidence = verified(root, case["saved"])
                    historical = identified(evidence)
                    out = _private_path(
                        root,
                        historical.get(
                            "local_evidence_directory", str(evidence.parent.relative_to(root))
                        ),
                    )
                    report = identified(out / "report.json")
                    if evidence != out / "report.json" and (
                        historical["native_report_id"] != report["report_id"]
                        or historical["final_frame_id"]
                        != identified(out / "last-frame.json")["report_id"]
                        or historical["worker_observations_sha256"]
                        != _sha_file(out / "worker/public-observations.jsonl.gz")
                        or historical["worker_receipts_sha256"]
                        != _sha_file(out / "worker/public-receipts.jsonl.gz")
                    ):
                        raise ValueError("Saved Queen evidence differs from its published summary")
                    row = audit(
                        base, case, journal, out, target, report, before, deadline, saved=True
                    )
                    for path in (
                        evidence,
                        out / "config.json",
                        out / "report.json",
                        out / "last-frame.json",
                        out / replay.TRACE,
                        *(
                            out / "worker" / name
                            for name in (
                                "public-observations.jsonl.gz",
                                "public-receipts.jsonl.gz",
                                "answer-plan-deliveries.jsonl.gz",
                                "private-transcript.jsonl.gz",
                                "closed.json",
                            )
                        ),
                    ):
                        name = str(path.relative_to(root))
                        hashes[name] = _sha_file(local(root, name))
                else:
                    seconds = min(cfg["case_wall_seconds"], deadline - time.monotonic() - 15)
                    if seconds < 75:
                        raise TimeoutError("Insufficient time to start another complete replay")
                    prior = root / replay.AREA / key
                    if any(prior.glob("archive-qualification-v*")):
                        raise ValueError("Preserve the prior native run and use saved evidence")
                    scope.begin(f"seed-{journal.seed.lower()}", {"batch": store.config_id, **case})
                    with patch.multiple(
                        replay,
                        AREA=str(target.relative_to(root)),
                        SAMPLE=key,
                        SOURCE_SHA=case["source"]["sha256"],
                        FULL_SECONDS=seconds,
                    ):
                        report = replay.probe(root, journal, source, control=False, attempt=1)
                    if report["stop"] is None:
                        row = audit(
                            base,
                            case,
                            journal,
                            target / key / "archive-qualification-v1",
                            target,
                            report,
                            before,
                            deadline,
                            saved=False,
                        )
                    else:
                        uncertain = (
                            report["stop"]["delivery_uncertain"] or not report["clean_shutdown"]
                        )
                        error = report["stop"].get("error", "Native shutdown uncertain")
                        status = (
                            "uncertain"
                            if uncertain
                            else (
                                "capped" if "guard" in error or "deadline" in error else "diverged"
                            )
                        )
                        row = {
                            "status": status,
                            "error": error,
                            "stop": report["stop"],
                            "replay_report_id": report["report_id"],
                        }
                rows[key] = {"seed": case["seed"], **row}
                seals[key] = store.commit(key, case, rows[key], hashes)["report_id"]
                if row["status"] == "uncertain":
                    stop = {"run_id": key, "error": row["error"]}
                    break
            except FAILURES as exc:
                if not store.path(key).exists():
                    raise
                rows[key] = {"status": "failed", "seed": case["seed"], "error": str(exc)}
                stop = {"run_id": key, "error": str(exc)}
                break
        unchanged(base, before, float("inf"))
        check_sources(root, implementation)
        if (
            json.loads(recipe.read_text()) != cfg
            or _shared_snapshot(Path.home() / SHARED_PROFILE) != profile
        ):
            raise ValueError("Archive recipe or shared profile changed")
        summary = summarize(cfg, rows)
        status = (
            "stopped_preserving_evidence"
            if stop
            else (
                "archive_bank_candidate"
                if summary["candidate_for_separate_fitting_admission"]
                else "archive_batch_gate_blocked"
            )
        )
        return write(
            result_path,
            {
                "schema_version": f"{SCHEMA}-result",
                "status": status,
                "config_id": store.config_id,
                "environment_id": cfg["environment_id"],
                "worlds": rows,
                "seals": seals,
                "coverage": summary,
                "stop": stop,
                "seed_ownership": {
                    "development": cfg["development_seeds"],
                    "final_test": cfg["final_test_seeds"],
                },
                "frozen_checks": before,
                "shared_profile_unchanged": True,
                "optimizer_updates": 0,
                "training_admission_granted": False,
                "promotion_allowed": False,
                "official_live_qualification_granted": False,
                "automatic_follow_up": False,
                "final_test_worlds_used": False,
                "full_game_playing_strength_evaluated": False,
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", nargs="?", default=RECIPE)
    parser.add_argument("--run", action="store_true", help="Audit saved wins and run ready sources")
    args = parser.parse_args()
    root = Path.cwd()
    try:
        recipe = local(root, args.recipe)
        cfg = json.loads(recipe.read_text())
        validate_plan(cfg)
        check_sources(root, cfg["replay_implementation"])
        screened = {case["run_id"]: screen(root, case) for case in cfg["cases"]}
        if args.run:
            result = execute(root, recipe, cfg, screened)
        else:
            result = {
                "status": "archive_sources_screened",
                "sources": {key: row for key, (_, row) in screened.items()},
                "optimizer_updates": 0,
            }
    except FAILURES as exc:
        result = {
            "status": "stopped_preserving_evidence",
            "error": str(exc),
            "optimizer_updates": 0,
            "training_admission_granted": False,
        }
    print(json.dumps(result))
    return 2 if result["status"] == "stopped_preserving_evidence" else 0


if __name__ == "__main__":
    raise SystemExit(main())
