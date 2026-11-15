"""Rebuild the completed finite comparison from sealed units; no games or fitting."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_journal import ChunkJournal, load_state
from spireshift.native_context_reuse import check_sources
from spireshift.native_policy_trial_inputs import load
from spireshift.native_policy_trial_plan import plan, request, summary


def conclusion(result: dict[str, Any]) -> dict[str, Any]:
    """Describe this fixed comparison; do not invent an automatic promotion rule."""
    players = result["summary"]["players"]
    clean = result["failed_games"] == 0 and all(
        arm["recorded"] == arm["denominator"]
        and arm["failed_games"] == arm["not_attempted_games"] == 0
        for player in players
        for arm in player["arms"].values()
    )
    return {
        "complete_clean_comparison": clean,
        "updated_players_have_positive_floor_point_estimates": all(
            p["ppo_minus_original"]["maximum_floor"]["mean"] > 0 for p in players
        ),
        "pooled_floor_interval95": result["summary"]["pooled_ppo_minus_original"]["maximum_floor"][
            "interval95"
        ],
        "victories_observed": sum(a["wins"] for p in players for a in p["arms"].values()),
        "no_observed_wins_is_not_proof_of_zero_win_probability": True,
        "small_comparison_cannot_identify_the_cause_of_stalled_learning": True,
        "automatic_scale_up_allowed": False,
        "next_step": "small_native_A8_decision_learning_controls_before_representation_changes",
        "checkpoint_promoted": False,
        "base_readiness_passed": False,
        "adaptive_controller_allowed": False,
    }


def assess(root: Path, recipe: Path, output: Path, *, wall_seconds: float = 180) -> dict[str, Any]:
    started = time.monotonic()
    context = load(root, recipe)
    cfg, seeds = context["config"], context["seeds"]
    store = ChunkJournal(root, cfg)
    path = store.workspace / "report.json"
    result = identified(path)
    if (
        result["status"] != "native_policy_update_comparison_complete"
        or result["config_id"] != store.config_id
        or result["completed_units"] != result["planned_units"]
    ):
        raise ValueError("Finish the unchanged prepared comparison before selecting follow-ups")
    if output.exists():
        saved = identified(output)
        if saved["source_report_id"] != result["report_id"]:
            raise ValueError("Preserve the assessment under its original completed report")
        check_sources(root, saved["sources"])
        return saved
    done: dict[str, dict[str, Any]] = {}
    fits = []
    for task in plan(cfg, seeds):
        if time.monotonic() - started >= wall_seconds:
            raise TimeoutError("Saved comparison audit reached its finite cap")
        receipt = store.completed(task["key"], request(task, done))
        if receipt is None:
            raise ValueError("A claimed completed comparison has an unsealed or missing unit")
        row = receipt["result"]
        done[task["key"]] = row
        if row["kind"] == "fit":
            directory = store.path(task["key"])
            credit = json.loads((directory / "credit.json").read_text())
            work = json.loads((directory / "work.json").read_text())
            fits.append(
                {
                    "unit": task["key"],
                    "clean_games": credit["clean_complete_training_games"],
                    "decisions": credit["decisions"],
                    "choice_decisions": credit["choice_decisions"],
                    "prediction_quality": credit["prediction_quality"],
                    "optimizer_steps": work["optimizer_steps"],
                    "final_behavior_kl": work["final_behavior_kl"],
                    "stop_reason": work["stop_reason"],
                }
            )
    rebuilt = summary(cfg, seeds, done)
    if rebuilt != result["summary"] or sum(r["games_recorded"] for r in done.values()) != 256:
        raise ValueError("Saved full-game summary or original attempt denominator does not rebuild")
    for parent in cfg["players"]:
        _, optimizer, sid = load_state(root / parent["path"])
        if sid != parent["state_id"] or optimizer.steps != parent["optimizer_steps"]:
            raise ValueError("An original player's weights or complete Adam state changed")
    check_sources(root, result["sources"])
    sources = {**result["sources"], str(path.relative_to(root)): _sha_file(path)}
    body = {
        "schema_version": "native-policy-update-assessment-v1",
        "source_report_id": result["report_id"],
        "config_id": store.config_id,
        "verified_units": len(done),
        "verified_source_files": len(sources),
        "summary_reconstructed_from_sealed_units": True,
        "native_delivery_and_probability_audits_reused_from_sealed_collection": True,
        "native_games_or_policy_fitting_replayed": False,
        "summary": rebuilt,
        "fitting_diagnostics": fits,
        "decision": conclusion(result),
        "original_full_states_and_Adam_unchanged": True,
        "games_launched": 0,
        "optimizer_steps": 0,
        "game_apps_created": 0,
        "sources": sources,
        "wall_seconds": time.monotonic() - started,
    }
    report = {**body, "report_id": manifest_identifier(body)}
    atomic_json(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    result = assess(root, root / args.recipe, root / args.output)
    print(json.dumps({k: v for k, v in result.items() if k != "sources"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
