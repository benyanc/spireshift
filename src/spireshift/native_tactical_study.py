"""Restartable native tactical collection followed by fixed diagnostic learning.

No ordinary game training, reward change, player promotion or next experiment.
Only the short control may be run by Codex; the finite larger stage is owner-run.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file, load_engine_qualification_config
from spireshift.engine_run import _run_inputs
from spireshift.engine_worker_qualification import immutable_checks
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_context_reuse import check_sources
from spireshift.native_tactical_cases import collect_case, load, tasks
from spireshift.native_tactical_learning import fit, lessons


def coverage(cases: list[dict[str, Any]]) -> dict[str, Any]:
    fitting = {c["public_input_id"] for c in cases if c["task"]["seed"]["partition"] == "fit"}
    held = {c["public_input_id"] for c in cases if c["task"]["seed"]["partition"] == "heldout"}
    return {
        "distinct_fitting_public_inputs": len(fitting),
        "distinct_heldout_public_inputs": len(held),
        "public_inputs_in_both_partitions": len(fitting & held),
        "heldout_public_inputs_absent_from_fitting": len(held - fitting),
        "heldout_seeds_do_not_necessarily_mean_unseen_public_states": True,
    }


def run(root: Path, recipe: Path, *, max_units: int | None = None) -> dict[str, Any]:
    started = time.monotonic()
    context = load(root, recipe)
    cfg, prior = context["config"], context["comparison"]
    store = ChunkJournal(root, cfg)
    final = store.workspace / "report.json"
    if final.exists():
        cached = identified(final)
        if cached["config_id"] != store.config_id:
            raise ValueError("Preserve the saved tactical experiment under its original recipe")
        check_sources(root, cached["sources"])
        return cached
    if max_units is not None and max_units < 1:
        raise ValueError("Use a positive finite number of new diagnostic units")
    deadline = started + cfg["session_wall_seconds"] - 15
    schedule = tasks(cfg) + [{"key": f"fit-p{p}", "player": p} for p in (2, 3)]
    sources = {str(recipe.relative_to(root)): _sha_file(recipe)}
    sources.update({f"src/spireshift/{n}": v for n, v in cfg["implementation_sha256"].items()})
    sources.update({f"scripts/{n}": v for n, v in cfg["helpers_sha256"].items()})
    ref = cfg["comparison_assessment"]
    sources[ref["path"]] = _sha_file(root / ref["path"])
    for parent in prior["config"]["players"]:
        sources[parent["path"]] = parent["sha256"]
    done: dict[str, dict[str, Any]] = {}
    native = None
    new = 0
    with store.lock():
        for task in schedule:
            request = {
                "task": task,
                "contract": "native_short_horizon_known_answer_diagnostic_v1",
                "case_ids": [
                    r["public_input_id"] for r in done.values() if r["kind"] == "tactical_case"
                ]
                if "player" in task
                else [],
            }
            saved = store.completed(task["key"], request)
            if saved is None:
                reserve = (
                    (120 if cfg["stage"] == "short_control" else 240) if "player" in task else 100
                )
                if deadline - time.monotonic() < reserve or (
                    max_units is not None and new >= max_units
                ):
                    break
                if "player" not in task:
                    if _running_games():
                        raise ValueError(
                            "Close STS2 before starting another isolated tactical case"
                        )
                    if native is None:
                        q = load_engine_qualification_config(
                            root / prior["config"]["qualification"]
                        )
                        inputs = _run_inputs(q, root / prior["config"]["native_inputs"]["path"])
                        native = q, inputs
                    q, inputs = native
                    account = Path.home() / "Library/Application Support/SlayTheSpire2"
                    before = _shared_snapshot(account)
                    target = store.begin(task["key"], request)
                    result = collect_case(q, inputs, cfg, task, target)
                    checks = immutable_checks(q, inputs)
                    checks["account_profile_unchanged"] = before == _shared_snapshot(account)
                    if not all(checks.values()):
                        raise ValueError(
                            "A frozen input or account profile changed during diagnostics"
                        )
                    result["checks"] = checks
                else:
                    target = store.begin(task["key"], request)
                    player = task["player"]
                    result = fit(
                        cfg,
                        prior["models"][player],
                        prior["adams"][player],
                        prior["score"],
                        lessons(root, done),
                        player,
                        target,
                    )
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        "Diagnostic unit exceeded its finite session; preserve unfinished evidence"
                    )
                extra = result.pop("sources", {})
                store.commit(task["key"], request, result, extra)
                saved = store.completed(task["key"], request)
                assert saved is not None
                new += 1
                print(
                    f"Tactical diagnostic: {task['key']} sealed; {new} new units; "
                    "no full-run training.",
                    flush=True,
                )
            done[task["key"]] = saved["result"]
            sources.update(saved["sources"])
            receipt = store.path(task["key"]) / "done.json"
            sources[str(receipt.relative_to(root))] = _sha_file(receipt)
        check_sources(root, sources)
        complete = len(done) == len(schedule)
        cases = lessons(root, done)
        body = {
            "schema_version": "native-tactical-learning-study-v1",
            "config_id": store.config_id,
            "status": "tactical_control_complete"
            if complete and cfg["stage"] == "short_control"
            else "tactical_diagnostic_complete"
            if complete
            else "paused_between_tactical_units",
            "completed_units": len(done),
            "planned_units": len(schedule),
            "new_units_this_session": new,
            "native_branches": sum(c["native_branches"] for c in cases),
            "native_root_cases": len(cases),
            "coverage": coverage(cases),
            "learning": [v for v in done.values() if v["kind"] == "tactical_fit"],
            "diagnostic_subtasks_are_not_full_run_victories": True,
            "ordinary_PPO_eligible": False,
            "student_inputs_public_only": True,
            "privileged_fixture": True,
            "original_full_states_and_Adam_unchanged": True,
            "full_run_attempts": 0,
            "game_apps_created": 0,
            "checkpoint_promoted": False,
            "base_readiness_passed": False,
            "adaptive_controller_allowed": False,
            "automatic_training_follows": False,
            "sources": sources,
            "session_wall_seconds": time.monotonic() - started,
        }
        result = {**body, "report_id": manifest_identifier(body)}
        index = len(list((store.workspace / "sessions").glob("session-*.json"))) + 1
        atomic_json(store.workspace / f"sessions/session-{index:03d}.json", result)
        if complete:
            atomic_json(final, result)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--max-units", type=int)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    try:
        result = run(root, root / args.recipe, max_units=args.max_units)
        print(json.dumps({k: v for k, v in result.items() if k != "sources"}, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TimeoutError) as error:
        print(json.dumps({"status": "stopped_preserving_tactical_evidence", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
