"""A finite saved-only situation bank; no worker, learner, action targets or live-run reads."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode, score_episode
from spireshift.engine_learning import identified
from spireshift.engine_neural import validate_public_input
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_context_reuse import check_sources
from spireshift.native_inventory_credit_data import verify_binding
from spireshift.native_shop_policy import ShopNavigation
from spireshift.native_situation_features import CONTRACT, describe
from spireshift.native_situation_selection import select, split_worlds, thin
from spireshift.native_situation_sources import prepare
from spireshift.native_structured_policy import CONTRACT as POLICY


def prefix_start() -> str:
    return hashlib.sha256(CONTRACT.encode()).hexdigest()


def prefix_next(prefix: str, public_id: str, action: int) -> str:
    return hashlib.sha256(f"{prefix}|{public_id}|{action}".encode()).hexdigest()


def extract_case(
    case: dict[str, Any], game: dict[str, Any], case_id: str, deadline: float
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if (
        case.get("status") != "terminal"
        or case.get("ordinary_PPO_eligible") is not True
        or case.get("recovered") is not False
        or case.get("privileged_fixture") is not False
        or case.get("privileged_fixed_world_teacher") is not False
        or case.get("native_ending_evidence_agrees") is not True
        or case.get("policy_contract") != POLICY
        or case.get("seed") != game["world"]
    ):
        raise ValueError("Reject partial, recovered, evaluation or privileged bank sources")
    navigation, prefix = ShopNavigation(), prefix_start()
    rows = []
    counts = Counter(
        {"decisions": 0, "forced_navigation": 0, "single_choice": 0, "genuine_choices": 0}
    )
    for index, decision in enumerate(case["decisions"]):
        if time.monotonic() >= deadline:
            raise TimeoutError("Saved situation extraction reached its finite cap")
        public, saved = decision["public_input"], decision["choice"]
        validate_public_input(public)
        public_id = manifest_identifier(public)
        effective, indices, forced = navigation.view(public)
        action = saved["action_index"]
        if (
            type(action) is not int
            or action not in indices
            or saved.get("public_input_id") != public_id
            or saved.get("effective_input_id") != manifest_identifier(effective)
            or saved.get("effective_action_index") != indices.index(action)
            or saved.get("navigation_only") is not forced
            or saved.get("model_id") != game["model_id"]
            or saved.get("training") is not True
            or saved.get("policy_contract") != POLICY
            or saved.get("behavior")
            != ("deterministic_navigation" if forced else "sampled_softmax")
            or saved.get("temperature") != 0.8
            or type(saved.get("log_probability")) is not float
            or not math.isfinite(saved["log_probability"])
            or saved["log_probability"] > 1e-12
        ):
            raise ValueError("Saved public menu or source policy provenance differs")
        counts["decisions"] += 1
        if forced:
            counts["forced_navigation"] += 1
        elif len(indices) == 1:
            counts["single_choice"] += 1
        else:
            counts["genuine_choices"] += 1
            rows.append(
                {
                    **{
                        k: game[k]
                        for k in (
                            "cohort",
                            "source_ref",
                            "world",
                            "seed_id",
                            "model_id",
                            "player",
                            "arm",
                            "round",
                        )
                    },
                    "case_id": case_id,
                    "decision_index": index,
                    "public_input_id": public_id,
                    "effective_input_id": saved["effective_input_id"],
                    "effective_candidate_indices": indices,
                    "replay_prefix_sha256": prefix,
                    "description": describe(effective),
                }
            )
        # Prefix actions are replay metadata only; the root's action is never a label.
        prefix = prefix_next(prefix, public_id, action)
        navigation.advance(public, action)
    return thin(rows), dict(counts)


def coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def counts(name: str) -> dict[str, int]:
        return dict(sorted(Counter(str(r["description"][name]) for r in rows).items()))

    return {
        "situations": len(rows),
        "worlds": len({r["world"] for r in rows}),
        "families": counts("family"),
        "floor_bands": counts("floor_band"),
        "hp_bands": counts("hp_band"),
        "encounter_types": counts("encounter_type"),
        "tags": dict(sorted(Counter(t for r in rows for t in r["description"]["tags"]).items())),
        "distinct_deck_signatures": len({r["description"]["deck_signature"] for r in rows}),
        "distinct_relic_signatures": len({r["description"]["relic_signature"] for r in rows}),
        "distinct_card_definitions": len(
            {d for r in rows for d in r["description"]["deck_definitions"]}
        ),
        "distinct_relic_definitions": len(
            {d for r in rows for d in r["description"]["relic_definitions"]}
        ),
        "combat_roots_without_public_relic_counter_view": sum(
            r["description"]["family"] == "combat_turn"
            and not r["description"]["relic_counters_available"]
            for r in rows
        ),
    }


def build(
    root: Path, context: dict[str, Any], store: ChunkJournal, results: list[dict[str, Any]]
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for result in results:
        candidates.extend(json.loads((root / result["rows_path"]).read_text()))
        counts.update(result["counts"])
    worlds = sorted({g["world"] for g in context["games"]})
    splits = split_worlds(worlds)
    chosen, sampling = select(candidates, splits)
    if not chosen:
        raise ValueError("No genuine public choices available; do not invent a bank")
    if (store.workspace / "bank.json").exists():
        raise FileExistsError("Preserve an uncommitted bank; inspect it before resuming")
    bank = {
        "schema_version": "native-training-situation-bank-v1",
        "config_id": store.config_id,
        "contract": CONTRACT,
        "source_environment": context["source"]["environment_manifest"],
        "source_config_id": manifest_identifier(context["source"]),
        "source_seed_manifest": context["source"]["seed_manifest"],
        "training_spec": context["source"]["training_spec"],
        "world_splits": splits,
        "situations": [dict(r, situation_id=manifest_identifier(r)) for r in chosen],
        "student_input_contract": "resolve_public_input_only_keep_provenance_separate",
        "action_quality_labels_available": False,
        "ordinary_PPO_eligible": False,
        "native_replay_qualified": False,
        "source_native_probability_audits_reused": True,
        "native_policy_inference_recomputed": False,
        "selection_uses_saved_actions_or_final_outcomes": False,
        "validation_is_unseen_to_parent_player": False,
    }
    bank["bank_id"] = manifest_identifier(bank)
    atomic_json(store.workspace / "bank.json", bank)
    return {
        "source_attempts": len(results),
        "source_native_worlds": len(worlds),
        "counts": dict(counts),
        "sampling": sampling,
        "available_after_episode_thinning": coverage(candidates),
        "selected": coverage(chosen),
        "selected_by_split": {
            s: coverage([r for r in chosen if r["split"] == s]) for s in ("fit", "validation")
        },
        "bank_id": bank["bank_id"],
        "whole_native_world_split_counts": dict(Counter(splits.values())),
    }


def run(root: Path, path: Path, max_new_games: int | None = None) -> dict[str, Any]:
    started = time.monotonic()
    if max_new_games is not None and (
        type(max_new_games) is not int or not 1 <= max_new_games <= 384
    ):
        raise ValueError("Use a finite positive saved-game chunk limit")
    context = prepare(root, path)
    cfg, sources = context["config"], dict(context["sources"])
    store = ChunkJournal(root, cfg)
    deadline, new = started + cfg["session_limits"]["wall_seconds"] - 15, 0
    with store.lock():
        if (store.workspace / "report.json").exists():
            report = identified(store.workspace / "report.json")
            if report["config_id"] != store.config_id:
                raise ValueError("Saved bank belongs to another recipe")
            check_sources(root, report["sources"])
            return report
        results = []
        for game in context["games"]:
            req = {"game": game, "contract": CONTRACT}
            cached = store.completed(game["key"], req)
            if cached is None:
                if time.monotonic() >= deadline - 5 or (
                    max_new_games is not None and new >= max_new_games
                ):
                    break
                directory = store.begin(game["key"], req)
                episode_path = root / game["source_ref"]
                header = json.loads(episode_path.read_text())
                binding = header["binding"]
                verify_binding(
                    binding, context["source"], game["model_id"], {game["seed_id"]: game["world"]}
                )
                case = read_native_episode(episode_path, binding)
                if not score_episode(case, game["seed_id"], context["score"])["completed"]:
                    raise ValueError("An incomplete or over-budget game cannot supply bank roots")
                rows, counts = extract_case(case, game, header["case_id"], deadline)
                del case
                atomic_json(directory / "rows.json", rows)
                result = {
                    "rows_path": str((directory / "rows.json").relative_to(root)),
                    "counts": counts,
                }
                refs = (
                    game["source_ref"],
                    str(episode_path.with_suffix(".jsonl.gz").relative_to(root)),
                )
                cached = store.commit(game["key"], req, result, {n: sources[n] for n in refs})
                new += 1
            results.append(cached["result"])
            sources.update(cached["sources"])
            if len(results) % 32 == 0:
                print(
                    f"Situation bank: {len(results)}/{len(context['games'])} saved TRAIN games "
                    "indexed; no game attempts or updates.",
                    flush=True,
                )
        complete = len(results) == len(context["games"])
        summary = build(root, context, store, results) if complete else None
        if complete:
            sources[str((store.workspace / "bank.json").relative_to(root))] = _sha_file(
                store.workspace / "bank.json"
            )
        check_sources(root, sources)
        body = {
            "schema_version": "native-training-situation-bank-report-v1",
            "config_id": store.config_id,
            "recipe_path": str(path.relative_to(root)),
            "status": "native_situation_bank_complete"
            if complete
            else "native_situation_bank_clean_pause",
            "indexed_source_games": len(results),
            "planned_source_games": len(context["games"]),
            "new_games_indexed_this_session": new,
            "summary": summary,
            "sources": sources,
            "protected_files_unchanged": True,
            "original_full_states_and_Adam_unchanged": True,
            "maximum_raw_episode_histories_retained": 1,
            "evaluation_episodes_decoded": 0,
            "running_experiment_units_read": 0,
            "games_launched": 0,
            "optimizer_updates": 0,
            "checkpoint_promoted": False,
            "adaptive_controller_allowed": False,
            "automatic_followup": False,
            "wall_seconds": time.monotonic() - started,
        }
        report = {**body, "report_id": manifest_identifier(body)}
        sessions = store.workspace / "sessions"
        sessions.mkdir(exist_ok=True)
        number = len(list(sessions.glob("session-*.json"))) + 1
        atomic_json(sessions / f"session-{number:03d}.json", report)
        if complete:
            atomic_json(store.workspace / "report.json", report)
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe")
    parser.add_argument("--max-new-games", type=int)
    args = parser.parse_args()
    try:
        report = run(Path.cwd(), Path.cwd() / args.recipe, args.max_new_games)
        print(json.dumps({k: v for k, v in report.items() if k != "sources"}, indent=2))
        return 0
    except (ValueError, FileExistsError, KeyError, TimeoutError) as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
