"""Restartable native delayed-decision baseline comparison; no full-run promotion."""

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
from spireshift.native_delayed_collect import collect
from spireshift.native_delayed_data import ARMS, CONTRACT
from spireshift.native_delayed_execute import execute
from spireshift.native_delayed_inputs import load, plan


def run(root: Path, recipe: Path, *, max_units: int | None = None) -> dict[str, Any]:
    started = time.monotonic()
    context = load(root, recipe)
    cfg = context["config"]
    if max_units is not None and (type(max_units) is not int or max_units < 1):
        raise ValueError("Use a positive finite unit bound")
    journal = ChunkJournal(root, cfg)
    final = journal.workspace / "report.json"
    if final.exists():
        saved = identified(final)
        if saved["config_id"] != journal.config_id:
            raise ValueError("The completed diagnostic belongs to a different frozen recipe")
        check_sources(root, saved["sources"])
        return saved
    deadline = started + cfg["session_limits"]["wall_seconds"] - 15
    sources = dict(context["sources"])
    done: dict[str, dict[str, Any]] = {}
    new, native = 0, None
    tasks = plan(cfg)
    with journal.lock():
        for task in tasks:
            req = {
                "contract": CONTRACT,
                "task": task,
                "tree_ids": [r["tree_id"] for r in done.values() if r["kind"] == "delayed_tree"],
            }
            if "state" in task:
                req["predecessor_state_id"] = done[task["state"]]["state_id"]
            receipt = journal.completed(task["key"], req)
            if receipt is None:
                reserve = 65 if task["kind"] == "collect" else 45
                if deadline - time.monotonic() < reserve or (
                    max_units is not None and new >= max_units
                ):
                    break
                if task["kind"] == "collect":
                    if _running_games():
                        raise ValueError("Close STS2 before the next isolated delayed fixture")
                    if native is None:
                        q = load_engine_qualification_config(
                            root / context["source"]["qualification"]
                        )
                        inputs = _run_inputs(q, root / context["source"]["native_inputs"]["path"])
                        if (
                            q.config_id != context["source"]["qualification_id"]
                            or manifest_identifier(inputs["recipe"])
                            != context["source"]["native_inputs"]["id"]
                        ):
                            raise ValueError("Preserve the production frozen native engine inputs")
                        native = q, inputs
                    q, inputs = native
                    account = Path.home() / "Library/Application Support/SlayTheSpire2"
                    before = _shared_snapshot(account)
                    target = journal.begin(task["key"], req)
                    result = collect(q, inputs, cfg, task, target, deadline)
                    checks = immutable_checks(q, inputs)
                    checks["account_profile_unchanged"] = _shared_snapshot(account) == before
                    if not all(checks.values()):
                        raise ValueError("A frozen input or real account profile changed")
                    result["checks"] = checks
                else:
                    target = journal.begin(task["key"], req)
                    result = execute(root, context, task, done, target, deadline)
                if time.monotonic() >= deadline:
                    raise TimeoutError("Preserve the incomplete delayed unit at its finite cap")
                journal.commit(task["key"], req, result)
                receipt = journal.completed(task["key"], req)
                assert receipt is not None
                new += 1
                print(f"Delayed diagnostic: {task['key']} sealed.", flush=True)
            done[task["key"]] = receipt["result"]
            sources.update(receipt["sources"])
            sources[str((journal.path(task["key"]) / "done.json").relative_to(root))] = _sha_file(
                journal.path(task["key"]) / "done.json"
            )
        check_sources(root, sources)
        complete = len(done) == len(tasks)
        first = {
            p: [
                r
                for r in done.values()
                if r["kind"] == "fit" and r["player"] == p and r["start_round"] == 1
            ]
            for p in (2, 3)
        }
        matched = all(
            len(v) == 2 and v[0]["first_batch_trace_id"] == v[1]["first_batch_trace_id"]
            for v in first.values()
        )
        evaluations = [r for r in done.values() if r["kind"] == "evaluate"]
        control_pass = (
            complete
            and matched
            and all(done[f"initial-p{p}"]["optimizer_checks_passed"] for p in (2, 3))
        )
        if complete and not control_pass:
            raise ValueError("Starting own-policy traces or imported optimizer checks differ")
        body = {
            "schema_version": "native-delayed-baseline-comparison-v1",
            "config_id": journal.config_id,
            "recipe_path": str(recipe.relative_to(root)),
            "status": "delayed_control_complete"
            if complete and cfg["stage"] == "short_control"
            else "delayed_comparison_complete"
            if complete
            else "delayed_clean_pause",
            "completed_units": len(done),
            "planned_units": len(tasks),
            "new_units_this_session": new,
            "sources": sources,
            "pipeline_control_passed": control_pass,
            "first_own_policy_batches_identical_across_baselines": matched,
            "native_branches": sum(r.get("native_branches", 0) for r in done.values()),
            "sampled_diagnostic_episodes": sum(r.get("sampled_episodes", 0) for r in done.values()),
            "optimizer_steps_on_experimental_copies": sum(
                r.get("new_optimizer_steps", 0) for r in done.values()
            ),
            "final_evaluations": evaluations,
            "arms": list(ARMS),
            "fitting_passes_by_arm": {
                arm: sum(r["fitting_criterion_passed"] for r in evaluations if r["arm"] == arm)
                for arm in ARMS
            },
            "all_final_players_frozen_before_heldout_evaluation": complete,
            "production_PPO_sampler_encoder_loss_settings_and_full_Adam_used": True,
            "sole_treatment": (
                "production_learned_public_baseline_vs_exact_current_policy_native_tree_baseline"
            ),
            "diagnostic_goal": (
                "terminal_only_native_encounter_win_or_survive_advertised_enemy_turn"
            ),
            "full_run_objective": context["score"].evaluation_objective.as_dict(),
            "training_spec_id": context["score"].spec_id,
            "ordinary_PPO_eligible": False,
            "privileged_fixture": True,
            "exact_baseline_privileged_not_a_public_gameplay_baseline": True,
            "original_full_weights_and_all_Adam_unchanged": True,
            "full_run_attempts": 0,
            "game_apps_created": 0,
            "checkpoint_promoted": False,
            "base_readiness_passed": False,
            "adaptive_controller_allowed": False,
            "automatic_training_follows": False,
            "wall_seconds": time.monotonic() - started,
        }
        report = {**body, "report_id": manifest_identifier(body)}
        sessions = journal.workspace / "sessions"
        index = len(list(sessions.glob("session-*.json"))) + 1
        atomic_json(sessions / f"session-{index:03d}.json", report)
        if complete:
            atomic_json(final, report)
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--max-units", type=int)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    try:
        report = run(root, root / args.recipe, max_units=args.max_units)
        print(
            json.dumps(
                {k: v for k, v in report.items() if k not in {"sources", "final_evaluations"}},
                indent=2,
            )
        )
        return 0
    except (ValueError, OSError, KeyError, TimeoutError) as error:
        print(json.dumps({"status": "stopped_preserving_delayed_evidence", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
