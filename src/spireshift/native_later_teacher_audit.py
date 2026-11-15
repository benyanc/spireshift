"""Reconstruct saved teacher choices/labels one episode at a time; never start a host."""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode, score_episode
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_combat_teacher import tasks
from spireshift.native_combat_teacher_data import (
    CONTRACT,
    INFORMATION,
    ReplayChooser,
    lesson,
    sampling_seed,
    trace_id,
)
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import ChunkJournal, load_state
from spireshift.native_context_reuse import check_sources
from spireshift.native_later_teacher import load
from spireshift.training_objective import TrainingScoreSpec, load_training_score_spec


def reconstruct(
    case: dict[str, Any],
    root: dict[str, Any],
    action: int,
    repeat: int,
    model: CachedContextModel,
    score: TrainingScoreSpec,
    temperature: float,
) -> int:
    if (
        case.get("status") != "terminal"
        or case.get("seed") != root["native_seed"]
        or case.get("recovered") is not False
        or case.get("privileged_fixture") is not False
        or case.get("native_ending_evidence_agrees") is not True
        or case.get("policy_contract") != CONTRACT
        or case.get("privileged_fixed_world_teacher") is not True
        or case.get("ordinary_PPO_eligible") is not False
    ):
        raise ValueError(
            "Only complete explicitly marked fixed-world teacher episodes can be audited"
        )
    chooser = ReplayChooser(root, action, repeat, model, score, temperature)
    for row in case["decisions"]:
        expected = chooser(row["public_input"])
        actual = row["choice"]
        for key, value in expected.items():
            other = actual.get(key)
            if type(value) is float:
                matches = type(other) in (int, float) and math.isclose(
                    other, value, rel_tol=0, abs_tol=1e-10
                )
            else:
                matches = type(other) is type(value) and other == value
            if not matches:
                raise ValueError(f"Saved teacher choice does not reconstruct: {key}")
    if not chooser.root_reached:
        raise ValueError("Saved teacher episode never reached its declared forced choice")
    return len(case["decisions"])


def audit(root: Path, path: Path, *, deadline: float) -> dict[str, Any]:
    cfg, corpus, roots, sources = load(root, path)
    store = ChunkJournal(root, cfg)
    report_path = store.workspace / "report.json"
    report = identified(report_path)
    plan = tasks(roots, cfg["repeats"], cfg["stage"] == "short_control")
    if (
        report["status"] != "native_later_combat_teacher_complete"
        or report["config_id"] != store.config_id
        or report["planned_branches"] != len(plan)
        or report["completed_units"] != len(plan)
        or report["failed_branches"]
        or report["skipped_branches"]
    ):
        raise ValueError("Saved teacher audit requires the complete original branch denominator")
    check_sources(root, report["sources"])
    score = load_training_score_spec(root / corpus["training_spec"]["path"])
    models = {}
    for ref in corpus["models"]:
        model, optimizer, state_id = load_state(root / ref["state_path"])
        if state_id != ref["state_id"] or optimizer.steps != ref["optimizer_steps"]:
            raise ValueError("Saved continuation player or full Adam state differs")
        models[ref["numerical_seed"]] = model
    by_id = {r["root_id"]: r for r in roots}
    grouped: dict[str, list[dict[str, Any]]] = {key: [] for key in by_id}
    traces: dict[tuple[str, int, int], str] = {}
    decisions = 0
    for task in plan:
        if time.monotonic() >= deadline:
            raise TimeoutError("Saved teacher audit reached its finite cap; no game is started")
        receipt = store.completed(task["key"], {**task, "scope": INFORMATION})
        if receipt is None:
            raise ValueError("Saved teacher lost a planned branch")
        result = receipt["result"]
        if (
            any(result[k] != task[k] for k in ("action", "repeat", "duplicate_control"))
            or result["root_reached"] is not True
            or result["native_audit_valid"] is not True
        ):
            raise ValueError("Saved branch result differs from its declared intervention")
        r = by_id[task["root_id"]]
        header_path = root / result["episode_path"]
        binding = json.loads(header_path.read_text())["binding"]
        expected_binding = {
            "config_id": store.config_id,
            "environment_id": models[r["numerical_seed"]].actor.environment_id,
            "root_id": r["root_id"],
            "forced_root_action": task["action"],
            "native_seed": r["native_seed"],
            "seed_id": r["source_seed_id"],
            "partition": "train",
            "panel_purpose": "teacher_comparison_not_PPO",
            "policy_contract": CONTRACT,
            "model_id": models[r["numerical_seed"]].model_id,
            "training_spec_id": score.spec_id,
            "information_scope": INFORMATION,
            "continuation_sampling_seed": sampling_seed(r["root_id"], task["repeat"]),
        }
        if any(binding.get(k) != v for k, v in expected_binding.items()):
            raise ValueError("Saved teacher branch belongs to another intervention or player")
        case = read_native_episode(header_path, binding)
        decisions += reconstruct(
            case,
            r,
            task["action"],
            task["repeat"],
            models[r["numerical_seed"]],
            score,
            cfg["temperature"],
        )
        scored = score_episode(case, r["source_seed_id"], score)
        digest = trace_id(case)
        if (
            not scored["completed"]
            or scored["training_return"] != result["training_return"]
            or digest != result["trace_id"]
            or any(
                case[k] != result[k]
                for k in ("status", "victory", "maximum_floor", "completed_acts")
            )
        ):
            raise ValueError("Saved teacher return, public trace or ending differs")
        del case
        key = r["root_id"], task["action"], task["repeat"]
        if task["duplicate_control"]:
            if traces.get(key) != digest:
                raise ValueError("Repeated teacher branch public traces differ")
        else:
            traces[key] = digest
        grouped[r["root_id"]].append(result)
    tables = [lesson(r, grouped[r["root_id"]], cfg["repeats"]) for r in roots]
    if tables != report["cases"]:
        raise ValueError("Saved teacher action tables or uncertainty/preference gates differ")
    check_sources(root, sources)
    alternatives = [p for table in tables for p in table["preferences"]]
    body = {
        "schema_version": "native-later-combat-teacher-audit-v2",
        "source_report_id": report["report_id"],
        "recipe_path": str(path.relative_to(root)),
        "auditor_sha256": _sha_file(Path(__file__)),
        "branch_receipts_verified": len(plan),
        "public_decisions_reconstructed": decisions,
        "source_hidden_worlds": len(roots),
        "action_tables_exactly_reconstructed": True,
        "prefix_forced_actions_and_continuation_probabilities_reconstructed": True,
        "native_journal_bytes_verified": True,
        "native_delivery_semantically_reaudited": False,
        "paired_alternative_counts": {
            key: sum(p[key] for p in alternatives)
            for key in ("positive_pairs", "negative_pairs", "tied_pairs")
        },
        "admitted_preferences": sum(p["admitted_exploratory_preference"] for p in alternatives),
        "original_players_and_full_Adam_unchanged": True,
        "information_scope": INFORMATION,
        "ordinary_PPO_eligible": False,
        "new_games": 0,
        "optimizer_steps": 0,
        "checkpoint_promoted": False,
    }
    return {**body, "report_id": manifest_identifier(body)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = Path.cwd()
    try:
        result = audit(root, root / args.recipe, deadline=time.monotonic() + 210)
        atomic_json(args.output, result)
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TimeoutError) as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
