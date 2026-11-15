"""Collect matched model-sampled action outcomes on new A8 training worlds."""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from contextlib import closing
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_own_experience
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_action_credit_policy import ARMS, CONTRACT, STRATA, eligible, policy
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_feedback_session import LIMITS
from spireshift.native_a8_mix_audit import STATUS as AUDITED
from spireshift.native_a8_mix_session import Study, admit, game, unchanged
from spireshift.native_a8_own_training import FAILURES, SCOPE
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_rescue_game import TRACE, decisions
from spireshift.native_a8_tactical_session import boundary, frozen
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS, execution_runtime
from spireshift.native_flow_inputs_v12 import canonical_seed
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command
from spireshift.training_objective import RunStatus, TrainingOutcome, score_training_outcome

MODULE = "spireshift.native_a8_action_credit_session"
AREA = "artifacts/native-a8-action-credit"
RECIPE = "configs/native-learning/sts2-v0.111.0-a8-action-credit-v1.json"
WRAPPER = "scripts/collect-a8-action-credit-v1.sh"
EVIDENCE = "docs/evidence/native-a8-matched-practice-result-v2.json"
SCHEMA = "native-a8-action-credit-collection-v1"
CONTROL_OK = "paired_action_credit_controls_verified"
SHORT_LIMITS = {**LIMITS, "wall_seconds": 260, "cpu_seconds": 480}
GATE = {"minimum_pairs": 12, "minimum_per_stratum": 2, "minimum_per_initializer": 3}
TERMINAL = {"win", "loss"}


def plan(control: bool) -> list[dict[str, Any]]:
    result = []
    phase, prefix = ("control", "C") if control else ("train", "T")
    floors = (2,) if control else (2, 4, 6, 2, 4, 6)
    for group, stratum in enumerate(STRATA):
        for index, floor in enumerate(floors, 1):
            world = group * len(floors) + index
            for player in (PLAYERS[group % len(PLAYERS)],) if control else PLAYERS:
                result.append(
                    {
                        "key": f"{phase}-{world:02d}-p{player}",
                        "partition": f"credit_{phase}",
                        "player": player,
                        "seed": f"SP1RESH1FTA8AC1{prefix}{world:03d}",
                        "seed_id": 97000 + player * 100 + world + (20 if control else 0),
                        "stratum": stratum,
                        "minimum_floor": floor,
                    }
                )
    return result


def implementation(root: Path) -> dict[str, str]:
    paths = [
        WRAPPER,
        "src/spireshift/native_a8_mix_audit.py",
        "src/spireshift/native_a8_action_credit_policy.py",
        "src/spireshift/native_a8_action_credit_session.py",
    ]
    return {name: _sha_file(root / name) for name in paths}


def inputs(root: Path) -> tuple[Study, dict[str, Any]]:
    base = admit(root)
    cfg = json.loads((root / RECIPE).read_text())
    assessment = identified(verified(root, cfg["assessment"]))
    owner = identified(verified(root, assessment["owner_report"]))
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["contract"] != CONTRACT
        or cfg["environment_id"] != base.cfg["environment_id"]
        or cfg["objective"] != base.cfg["objective"]
        or cfg["score_spec_id"] != base.ctx["score"].spec_id
        or cfg["assessment"]["path"] != EVIDENCE
        or cfg["implementation"] != implementation(root)
        or cfg["study"] != plan(False)
        or cfg["control"] != plan(True)
        or cfg["gate"] != GATE
        or assessment["status"] != AUDITED
        or assessment["sealed_terminal_games"] != len(base.cfg["development"]) * 6
        or any(a["wins"] or a["act1_clears"] for a in assessment["arms"].values())
        or assessment["environment_id"] != cfg["environment_id"]
        or assessment["frozen_checks"] != frozen(root, base.ctx)
        or owner["planned_worlds"] != base.cfg["development"]
    ):
        raise ValueError("Require the exact frozen action-credit recipe and saved A8 assessment")
    history = json.loads(verified(root, base.ctx["config"]["parent_recipe"]).read_text())
    used = set(
        json.loads(verified(root, history["seed_history"]).read_text())["canonical_prior_seeds"]
    )
    used.update(history["plan"]["reserved_evaluation_seeds"])
    used.update(base.ctx["paired_panel"]["worlds"])
    used.update([*base.cfg["development"], base.cfg["prefix_seed"], base.cfg["ending_seed"]])
    used.update(entry["seed"] for entry in base.bank["entries"].values())
    for stage in ("control", "study"):
        own = base.source.recipe[stage]
        used.update([*own["development"], *own["reload"], *(t["seed"] for t in own["training"])])
    study_seeds = {case["seed"] for case in cfg["study"]}
    control_seeds = {case["seed"] for case in cfg["control"]}
    if (
        len(study_seeds) * len(PLAYERS) != len(cfg["study"])
        or study_seeds & control_seeds
        or used & (study_seeds | control_seeds)
        or any(seed != canonical_seed(seed) for seed in study_seeds | control_seeds)
    ):
        raise ValueError("Action-credit controls and training must use fresh, separate seeds")
    return base, cfg


def matched_root(left: Path, right: Path, case: dict[str, Any]) -> dict[str, Any] | None:
    with (
        closing(decisions(left / TRACE)) as reference,
        closing(decisions(right / TRACE)) as alternate,
    ):
        for (_, a, old), (_, b, new) in zip(reference, alternate, strict=True):
            public = a["public_input"]
            if public != b["public_input"] or (old is None) != (new is None):
                raise ValueError("Native histories diverged before the declared alternative")
            if old is None or new is None:
                return None
            c, d = old["choice"], new["choice"]
            root = c.get("credit_root")
            if root is None and d.get("credit_root") is None:
                if c["action_index"] != d["action_index"] or eligible(public, case):
                    raise ValueError("Both arms must mark their first eligible public root")
                continue
            i, j = c["action_index"], d["action_index"]
            if (
                not eligible(public, case)
                or i == j
                or public["candidates"][i]["label"] == public["candidates"][j]["label"]
                or root
                != {
                    "contract": CONTRACT,
                    "stratum": case["stratum"],
                    "reference_action_index": i,
                    "alternate": False,
                    "reference_draw_key": c["draw_key"],
                }
                or d.get("credit_root") != {**root, "alternate": True}
                or any(x["receipt"]["delivery_domain"] != "native" for x in (old, new))
            ):
                raise ValueError("The paired root lacks two different native deliveries")
            successors = []
            for branch, record in ((reference, old), (alternate, new)):
                _, frame, _ = next(branch)
                if (
                    frame["observation"]["snapshot_id"]
                    != record["receipt"]["successor_snapshot_id"]
                ):
                    raise ValueError("The paired action successor differs from its receipt")
                successors.append(manifest_identifier(frame["public_input"]))
            return {
                "input_id": manifest_identifier(public),
                "stratum": case["stratum"],
                "family": a["source_family"],
                "floor": public["context"]["persistent"]["run"]["floor"],
                "reference_action": i,
                "alternate_action": j,
                "different_display_label": public["candidates"][i]["label"]
                != public["candidates"][j]["label"],
                "different_public_successor": successors[0] != successors[1],
            }
    raise ValueError("Missing native final observation")


def pair(
    base: Study, store: ChunkJournal, case: dict[str, Any], results: dict[str, Any]
) -> dict[str, Any]:
    old, new = (results[arm] for arm in ARMS)
    if old["initial_public_input_id"] != new["initial_public_input_id"]:
        raise ValueError("Paired action-credit starts have different public menus")
    if any(row["outcome"] not in TERMINAL for row in results.values()):
        return {"status": "incomplete", "root": None, "returns": None, "preferred_arm": None}
    root = matched_root(store.path(old["task"]["key"]), store.path(new["task"]["key"]), case)
    returns = {}
    for arm, row in results.items():
        outcome = TrainingOutcome(
            case["seed_id"],
            RunStatus.VICTORY if row["outcome"] == "win" else RunStatus.LOSS,
            row["completed_acts"],
            row["maximum_floor"],
            row["native_decisions"],
            row["native_cpu_seconds"],
        )
        returns[arm] = score_training_outcome(base.ctx["score"], outcome)["training_return"]
    preferred = None
    if root and root["different_public_successor"] and returns["reference"] != returns["alternate"]:
        preferred = max(ARMS, key=returns.__getitem__)
    return {"status": "complete", "root": root, "returns": returns, "preferred_arm": preferred}


def execute(
    base: Study, cfg: dict[str, Any], attempt: int, deadline: float, *, control: bool
) -> dict[str, Any]:
    store = journal(base.root, cfg, control)
    before, profile = frozen(base.root, base.ctx), _shared_snapshot(Path.home() / SHARED_PROFILE)
    cases = cfg["control" if control else "study"]
    pairs: dict[str, Any] = {}
    games: dict[str, Any] = {}
    stop = None
    key = "preflight"

    def check() -> None:
        unchanged(base, before, deadline)
        if json.loads((base.root / RECIPE).read_text()) != cfg:
            raise ValueError("Action-credit recipe changed after launch")
        check_sources(base.root, cfg["implementation"])
        boundary(base.root, base.ctx, before, profile)

    with store.lock():
        try:
            check()
            for case in cases:
                results = {}
                state = base.originals[case["player"]]
                for arm in ARMS:
                    key = f"{case['key']}-{arm}"
                    task = {**case, "key": key, "arm": arm}
                    request = {"task": task, "state_id": state[2]}
                    seal = store.completed(key, request)
                    if seal is None:
                        check()
                        store.begin(key, request)
                        with patch.object(native_a8_own_experience, "policy", policy):
                            row = game(base, store, task, state, deadline)
                        check()
                        seal = store.commit(key, request, row)
                    row = seal["result"]
                    if row["task"] != task or row["model_id"] != state[0].model_id:
                        raise ValueError("A paired choice changed the frozen behavior checkpoint")
                    games[key] = {"outcome": row["outcome"], "seal_id": seal["report_id"]}
                    results[arm] = row
                key = case["key"]
                result = pair(base, store, case, results)
                pairs[key] = result
                print(
                    f"{key} {case['stratum']} {result['status']} "
                    f"preferred={result['preferred_arm']}",
                    flush=True,
                )
            key = "final_verification"
            check()
            if execution_runtime(base.ctx["node"]) != base.runtime:
                raise ValueError("Numerical runtime changed")
        except FAILURES as exc:
            stop = {"unit": key, "error": f"{type(exc).__name__}: {exc}"}
        informative = [case for case in cases if pairs.get(case["key"], {}).get("preferred_arm")]
        strata = Counter(case["stratum"] for case in informative)
        players = Counter(case["player"] for case in informative)
        complete = (
            stop is None
            and len(pairs) == len(cases)
            and all(result["status"] == "complete" for result in pairs.values())
        )
        usable = (
            complete
            and len(informative) >= GATE["minimum_pairs"]
            and all(strata[name] >= GATE["minimum_per_stratum"] for name in STRATA)
            and all(players[p] >= GATE["minimum_per_initializer"] for p in PLAYERS)
        )
        control_ok = complete and all(result["root"] is not None for result in pairs.values())
        status = (
            CONTROL_OK
            if control and control_ok
            else "action_credit_candidate_ready"
            if not control and usable
            else "action_credit_collection_incomplete"
            if not complete
            else "action_credit_gate_blocked"
        )
        return write(
            store.workspace / f"attempt-{attempt}.json",
            {
                "schema_version": SCHEMA,
                "status": status,
                "config_id": store.config_id,
                "planned_pairs": len(cases),
                "planned_games": len(cases) * len(ARMS),
                "outcomes": dict(Counter(row["outcome"] for row in games.values())),
                "games": games,
                "pairs": pairs,
                "informative_pairs": len(informative),
                "informative_by_stratum": dict(strata),
                "informative_by_initializer": {str(p): count for p, count in players.items()},
                "stop": stop,
                "frozen_checks": before if stop is None else None,
                "native_training_only": True,
                "ordinary_PPO_eligible": False,
                "training_admission_granted": False,
                "optimizer_updates": 0,
                **SCOPE,
            },
        )


def journal(root: Path, cfg: dict[str, Any], control: bool) -> ChunkJournal:
    return ChunkJournal(root, {**cfg, "workspace": cfg["control_workspace"]} if control else cfg)


def require_control(base: Study, cfg: dict[str, Any]) -> None:
    store = journal(base.root, cfg, True)
    resource = identified(_private_path(base.root, cfg["control_resource"]))
    attempt = resource["command"][-1]
    report = identified(store.workspace / f"attempt-{int(attempt)}.json")
    if (
        resource["status"] != "completed"
        or resource["exit_code"] != 0
        or resource["cap"] is not None
        or resource["command"][:-1] != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--check"]
        or resource["limits"] != SHORT_LIMITS
        or resource["artifacts"]["roots"] != [str(store.workspace)]
        or report["config_id"] != store.config_id
        or report["status"] != CONTROL_OK
        or report["planned_games"] != len(cfg["control"]) * len(ARMS)
        or report["frozen_checks"] != frozen(base.root, base.ctx)
    ):
        raise ValueError("Require the exact successful native action-credit controls")
    for case in cfg["control"]:
        for arm in ARMS:
            key = f"{case['key']}-{arm}"
            task = {**case, "key": key, "arm": arm}
            seal = store.completed(
                key, {"task": task, "state_id": base.originals[case["player"]][2]}
            )
            if seal is None or seal["report_id"] != report["games"][key]["seal_id"]:
                raise ValueError("Native action-credit control evidence changed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--control", action="store_true")
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--check", type=int)
    modes.add_argument("--collect", type=int)
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the launcher with its fixed numerical settings")
        base, cfg = inputs(root)
        if args.check is not None or args.collect is not None:
            control = args.check is not None
            if not control:
                require_control(base, cfg)
            result = execute(
                base,
                cfg,
                args.check or args.collect,
                started + (SHORT_LIMITS if control else LIMITS)["wall_seconds"] - 20,
                control=control,
            )
            print(json.dumps({k: v for k, v in result.items() if k not in {"pairs", "games"}}))
            return 0 if result["status"] in {CONTROL_OK, "action_credit_candidate_ready"} else 2
        if not args.control:
            require_control(base, cfg)
        if args.preflight:
            print(json.dumps({"status": CONTROL_OK, "planned_pairs": len(cfg["study"])}))
            return 0
        attempt = time.time_ns()
        workspace = journal(root, cfg, args.control).workspace
        resource = (
            _private_path(root, cfg["control_resource"])
            if args.control
            else workspace.with_name(f"{workspace.name}-{attempt}-resources.json")
        )
        if resource.exists():
            raise FileExistsError("Preserve the existing resource receipt")
        mode, limits = ("--check", SHORT_LIMITS) if args.control else ("--collect", LIMITS)
        if not args.control:
            print(
                "Close STS2. Allow 20–35 minutes for 36 paired training cases. Zero updates.",
                flush=True,
            )
        tracked = run_tracked_command(
            command=["uv", "run", "--no-sync", "python", "-m", MODULE, mode, str(attempt)],
            experiment_kind=ExperimentKind.OTHER,
            report_path=resource,
            artifact_roots=[workspace],
            working_directory=root,
            limits=ResourceLimits(**limits),
        )
        print(json.dumps(tracked.report, indent=2))
        return 0 if tracked.exit_code == 0 and tracked.status == "completed" else 2
    except FAILURES as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
