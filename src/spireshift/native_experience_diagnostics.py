"""Inspect sealed updates on old public inputs; no policy/optimizer/baseline fitting."""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_context_reuse import check_sources
from spireshift.native_experience_diagnostic_data import prepare as data
from spireshift.native_experience_diagnostic_sources import COHORTS, prepare
from spireshift.native_experience_feedback import matched_feedback
from spireshift.native_structured_state import load
from spireshift.native_training_diagnostics import measure, summary_text


def analyze(root: Path, context: dict[str, Any], key: str, deadline: float) -> dict[str, Any]:
    task, done = context["tasks"][key], context["done"]
    parent, child = done[task["state"]], done[key]
    before, adam_before, sid = load(root / parent["state_path"])
    after, adam_after, aid = load(root / child["state_path"])
    if (
        sid != parent["state_id"]
        or aid != child["state_id"]
        or before.model_id != parent["model_id"]
        or after.model_id != child["model_id"]
        or adam_before.steps != parent["optimizer_steps"]
        or adam_after.steps != child["optimizer_steps"]
        or adam_after.steps - adam_before.steps != child["new_optimizer_steps"]
        or before.mode != after.mode
        or before.feature_spec_id != after.feature_spec_id
        or before.actor.dimension != after.actor.dimension
        or before.actor.environment_id != after.actor.environment_id
    ):
        raise ValueError("Require the exact saved before/after full model/Adam lineage")
    paths = [p for name in task["collections"] for p in done[name]["paths"]]
    directory = root / context["source"]["workspace"] / "chunks" / key
    credit = json.loads((directory / "credit.json").read_text())
    work = json.loads((directory / "work.json").read_text())
    samples, metadata, details = data(
        root, context["source"], task, paths, before, context["score"], credit, deadline
    )
    result = measure(before, after, samples, metadata, context["source"]["learning"], deadline)
    moments = result["normalization_and_game_weighting"]
    if any(
        not math.isclose(moments[k], work[k], abs_tol=1e-12, rel_tol=0)
        for k in ("raw_advantage_mean", "raw_advantage_std")
    ):
        raise ValueError("Source update normalization no longer reconstructs")
    for family in result["families"]:
        family["choice_decisions_per_planned_game"] = family["choices"] / details["planned_games"]
        family["fraction_of_clean_games_with_family"] = family["complete_runs"] / details["games"]
    losses = Counter(r["last_public_family"] for r in details["outcomes"] if not r["victory"])
    return {
        "cohort": key,
        "player": task["player"],
        "arm": task["arm"],
        "round": task["round"],
        "before_model_id": before.model_id,
        "after_model_id": after.model_id,
        "source_before_Adam_steps": adam_before.steps,
        "source_after_Adam_steps": adam_after.steps,
        "source_saved_update_steps": child["new_optimizer_steps"],
        "decisions": len(samples),
        "losses_preceded_by_public_family": dict(losses),
        **details,
        **result,
        "baseline_refits": 0,
        "optimizer_updates": 0,
        "games_launched": 0,
        "claim_scope": "source_training_fit_diagnostic_not_fresh_game_performance",
    }


def run(root: Path, path: Path, max_new_cohorts: int = 1) -> dict[str, Any]:
    started = time.monotonic()
    if type(max_new_cohorts) is not int or not 1 <= max_new_cohorts <= 4:
        raise ValueError("Use one to four finite already sealed cohorts")
    context = prepare(root, path)
    store = ChunkJournal(root, context["config"])
    sources = dict(context["sources"])
    results, new = [], 0
    deadline = started + 225
    with store.lock():
        report_path = store.workspace / "report.json"
        if report_path.exists():
            report = identified(report_path)
            if report["config_id"] != store.config_id:
                raise ValueError("A completed diagnostic belongs to another recipe")
            check_sources(root, report["sources"])
            return report
        for key in COHORTS:
            task = context["tasks"][key]
            req = {
                "task": task,
                "source_config_id": manifest_identifier(context["source"]),
                "source_fit_state_id": context["done"][key]["state_id"],
            }
            receipt = store.completed(key, req)
            if receipt is None:
                if new >= max_new_cohorts or time.monotonic() >= deadline - 45:
                    break
                directory = store.begin(key, req)
                result = analyze(root, context, key, deadline)
                atomic_json(directory / "result.json", result)
                receipt = store.commit(key, req, result)
                new += 1
            results.append(receipt["result"])
            sources.update(receipt["sources"])
        if len(results) == 4:
            text = summary_text(results).replace(
                "Only completed historical TRAIN games", "Only sealed first-round TRAIN games"
            )
            readable = store.workspace / "summary.md"
            if readable.exists():
                raise FileExistsError("Preserve an uncommitted readable diagnostic report")
            readable.write_text(text)
            sources[str(readable.relative_to(root))] = _sha_file(readable)
        check_sources(root, sources)
        body = {
            "schema_version": "native-experience-training-diagnostic-v1",
            "config_id": store.config_id,
            "recipe_path": str(path.relative_to(root)),
            "status": "native_experience_diagnostic_complete"
            if len(results) == 4
            else "native_experience_diagnostic_clean_pause",
            "completed_cohorts": len(results),
            "planned_cohorts": 4,
            "new_cohorts_this_session": new,
            "planned_source_attempts": sum(len(t["seeds"]) for t in context["tasks"].values()),
            "results": results,
            "shared_train_feedback": matched_feedback(results),
            "sources": sources,
            "source_game_data_scope": "only_already_sealed_first_round_TRAIN_units",
            "later_or_active_source_units_read": 0,
            "evaluation_episodes_decoded": 0,
            "all_original_and_source_full_states_and_Adam_unchanged": True,
            "games_launched": 0,
            "optimizer_updates": 0,
            "baseline_refits": 0,
            "checkpoint_promoted": False,
            "automatic_training_follows": False,
            "wall_seconds": time.monotonic() - started,
        }
        report = {**body, "report_id": manifest_identifier(body)}
        sessions = store.workspace / "sessions"
        sessions.mkdir(exist_ok=True)
        number = len(list(sessions.glob("session-*.json"))) + 1
        atomic_json(sessions / f"session-{number:03d}.json", report)
        if len(results) == 4:
            atomic_json(report_path, report)
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe")
    parser.add_argument("--max-new-cohorts", type=int, default=1)
    args = parser.parse_args()
    try:
        report = run(Path.cwd(), Path.cwd() / args.recipe, args.max_new_cohorts)
        print(
            json.dumps(
                {k: v for k, v in report.items() if k not in {"sources", "results"}}, indent=2
            )
        )
        return 0
    except (ValueError, KeyError, FileExistsError, TimeoutError) as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
