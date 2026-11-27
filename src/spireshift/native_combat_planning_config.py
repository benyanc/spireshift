"""Pinned native combat-planning recipes and streaming reuse of old baseline episodes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode, score_episode
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.engine_selection_worker import SCRIPT
from spireshift.engine_worker import worker_helpers
from spireshift.native_combat_planning_data import SAMPLES, SEARCH_CALL_CPU_CAP, SEARCH_CPU_CAP
from spireshift.native_combat_planning_policy import (
    CONTRACT,
    MAX_BYTES,
    MAX_STEPS,
    RANKING,
    combat_exit,
)
from spireshift.native_combat_teacher_data import INFORMATION
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_context_reuse import check_sources
from spireshift.native_turn_teacher import receipt
from spireshift.native_turn_teacher_config import SOURCES as TURN_SOURCES
from spireshift.native_turn_teacher_config import load as load_turn
from spireshift.native_turn_teacher_data import comparison_tasks
from spireshift.native_turn_teacher_policy import validate_plan
from spireshift.training_objective import load_training_score_spec

SOURCES = tuple(
    sorted(
        set(
            (
                *TURN_SOURCES,
                "native_combat_planning_policy.py",
                "native_combat_planning_data.py",
                "native_combat_planning_branch.py",
                "native_combat_planning_config.py",
                "native_combat_planning.py",
                "native_combat_planning_audit.py",
            )
        )
    )
)
ENTRIES = (
    "native-combat-planning-v1.py",
    "compare-native-combat-planning-v1.sh",
    "verify-selection-cursor-v1.mjs",
)


def items_for(
    root: Path, roots: list[dict[str, Any]], frozen: dict[str, Any], control: bool
) -> list[dict[str, Any]]:
    if [g["root_id"] for g in frozen["roots"]] != [r["root_id"] for r in roots]:
        raise ValueError("Preserve the original frozen root order")
    chosen = (
        {
            min(
                (r for r in roots if r["numerical_seed"] == n),
                key=lambda r: (
                    len(r["public_input"]["candidates"]),
                    len(r["prefix"]),
                    r["root_id"],
                ),
            )["root_id"]
            for n in (2, 3)
        }
        if control
        else {r["root_id"] for r in roots}
    )
    items = []
    for ri, (r, g) in enumerate(zip(roots, frozen["roots"], strict=True)):
        if g["blocked"] or not g["candidates"]:
            raise ValueError("A missing original turn group cannot disappear from the comparison")
        if r["root_id"] not in chosen:
            continue
        found_end = False
        for pi, candidate in enumerate(g["candidates"]):
            turn = identified(root / candidate["path"], "plan_id")
            validate_plan(turn, r)
            if turn["plan_id"] != candidate["plan_id"] or candidate["reference"] != (pi == 0):
                raise ValueError("Original reference or candidate identity differs")
            first = turn["steps"][0]
            is_end = (
                first["public_input"]["candidates"][first["action_index"]]["verb"] == "end_turn"
            )
            if control and not candidate["reference"] and (not is_end or found_end):
                continue
            found_end |= is_end and not candidate["reference"]
            items.append(
                {
                    "key": f"r{ri:03d}-p{pi:03d}",
                    "root_index": ri,
                    "candidate_index": pi,
                    "root_id": r["root_id"],
                    "turn_plan_id": turn["plan_id"],
                    "turn_plan_path": candidate["path"],
                    "reference": candidate["reference"],
                }
            )
        if control and not found_end:
            raise ValueError("The fixed short control requires the offered end-turn alternative")
    return items


def terminal_exit(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "native_terminal",
        "terminal_public_key": case["terminal_public_key"],
        "combat_survived": case["victory"],
        "exit_hp": None,
        "exit_max_hp": None,
    }


def old_baselines(
    root: Path,
    parent: dict[str, Any],
    corpus: dict[str, Any],
    roots: list[dict[str, Any]],
    frozen: dict[str, Any],
    items: list[dict[str, Any]],
    repeats: int,
    sources: dict[str, str],
) -> dict[str, dict[str, Any]]:
    old = ChunkJournal(root, parent)
    tasks = {t["key"]: t for t in comparison_tasks(roots, frozen["roots"], 8, False)}
    by_id = {r["root_id"]: r for r in roots}
    score = load_training_score_spec(root / corpus["training_spec"]["path"])
    values = {}
    for item in items:
        r = by_id[item["root_id"]]
        turn = identified(root / item["turn_plan_path"], "plan_id")
        for rep in range(repeats):
            key = f"compare-{item['root_index']:03d}-r-{rep:02d}-p-{item['candidate_index']:02d}"
            value = receipt(old, tasks[key], sources)
            if (
                value is None
                or value["status"] != "terminal"
                or not all(
                    value[k] for k in ("root_reached", "turn_complete", "native_audit_valid")
                )
            ):
                raise ValueError("Only the complete clean original baseline may be reused")
            path = root / value["episode_path"]
            header = json.loads(path.read_text())
            case = read_native_episode(path, header["binding"])
            if (
                score_episode(case, r["source_seed_id"], score)["training_return"]
                != value["training_return"]
            ):
                raise ValueError("Old baseline outcome or compute limit does not reproduce")
            end = next(
                (
                    end
                    for row in case["decisions"][len(r["prefix"]) + len(turn["steps"]) :]
                    if (end := combat_exit(r["public_input"], row["public_input"])) is not None
                ),
                None,
            )
            values[f"{item['key']}-r{rep:02d}"] = {
                **value,
                "combat_exit": end or terminal_exit(case),
            }
            del case
    return values


def load(
    root: Path, path: Path
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, str],
]:
    cfg = json.loads(path.read_text())
    control = cfg.get("stage") == "short_control"
    if (
        cfg.get("schema_version") != "native-bounded-combat-planning-config-v1"
        or cfg.get("stage") not in {"short_control", "finite_comparison"}
        or cfg.get("policy_contract") != CONTRACT
        or cfg.get("information_scope") != INFORMATION
        or cfg.get("ordinary_PPO_eligible") is not False
        or cfg.get("samples_per_initial_turn") != SAMPLES
        or cfg.get("ranking") != RANKING
        or cfg.get("repeats") != (2 if control else 8)
        or cfg.get("maximum_combat_decisions") != MAX_STEPS
        or cfg.get("maximum_plan_bytes") != MAX_BYTES
        or cfg.get("search_cpu_cap") != SEARCH_CPU_CAP
        or cfg.get("search_call_cpu_cap") != SEARCH_CALL_CPU_CAP
        or cfg.get("proposal_temperature") != 1.2
        or cfg.get("temperature") != 0.8
        or cfg.get("implementation_sha256")
        != {n: _sha_file(root / "src/spireshift" / n) for n in SOURCES}
        or cfg.get("entry_sha256") != {n: _sha_file(root / "scripts" / n) for n in ENTRIES}
        or cfg.get("helpers_sha256") != worker_helpers(root, SCRIPT)
        or cfg.get("session_limits")
        != {
            "wall_seconds": 240 if control else 900,
            "cpu_seconds": 480 if control else 1800,
            "resident_memory_bytes": 2000000000,
            "storage_bytes": 2000000000 if control else 4000000000,
        }
    ):
        raise ValueError(
            "Freeze combat generation, tactical ranking, implementation and finite compute"
        )
    parent_path = root / cfg["source_recipe"]["path"]
    parent, corpus, roots, sources = load_turn(root, parent_path)
    if (
        manifest_identifier(parent) != cfg["source_recipe"]["id"]
        or parent["stage"] != "finite_teacher_pilot"
        or any(
            cfg[k] != parent[k]
            for k in (
                "qualification",
                "qualification_id",
                "node",
                "native_inputs",
                "helpers_sha256",
                "temperature",
            )
        )
    ):
        raise ValueError(
            "Keep the original native A8 environment, full players and initial-turn curriculum"
        )
    prior = identified(root / cfg["baseline_report"]["path"])
    if (
        prior["report_id"] != cfg["baseline_report"]["id"]
        or prior["config_id"] != manifest_identifier(parent)
        or prior["status"] != "native_complete_turn_teacher_complete"
        or prior["failed_branches"]
        or prior["skipped_branches"]
        or not prior["all_candidates_frozen_before_scored_branches"]
    ):
        raise ValueError("The complete-turn baseline must be complete, clean and outcome-blind")
    check_sources(root, prior["sources"])
    sources.update(prior["sources"])
    sources[cfg["baseline_report"]["path"]] = _sha_file(root / cfg["baseline_report"]["path"])
    frozen_path = root / parent["workspace"] / "candidate-set.json"
    frozen = identified(frozen_path)
    if (
        frozen["config_id"] != manifest_identifier(parent)
        or len(prior["cases"]) != len(roots)
        or [c["candidate_plans"] for c in prior["cases"]]
        != [g["candidates"] for g in frozen["roots"]]
        or any(not c["comparison_complete"] for c in prior["cases"])
    ):
        raise ValueError("Keep every original frozen turn and source world")
    items = items_for(root, roots, frozen, control)
    baseline = old_baselines(root, parent, corpus, roots, frozen, items, cfg["repeats"], sources)
    selected_roots = [r for r in roots if any(i["root_id"] == r["root_id"] for i in items)]
    if not control:
        passed = identified(root / cfg["control_report"]["path"])
        old = json.loads((root / passed["recipe_path"]).read_text())
        audit = identified(root / cfg["control_audit"]["path"])
        same = (
            "source_recipe",
            "baseline_report",
            "implementation_sha256",
            "entry_sha256",
            "helpers_sha256",
            "ranking",
            "samples_per_initial_turn",
            "maximum_combat_decisions",
            "maximum_plan_bytes",
            "search_cpu_cap",
            "search_call_cpu_cap",
            "temperature",
            "proposal_temperature",
        )
        control_items = items_for(root, roots, frozen, True)
        control_attempts = len(control_items) * (SAMPLES + 2) + 4
        if (
            passed["report_id"] != cfg["control_report"]["id"]
            or passed["config_id"] != manifest_identifier(old)
            or passed["completed_units"] != control_attempts
            or passed["status"] != "native_bounded_combat_comparison_complete"
            or passed["failed_branches"]
            or passed["skipped_branches"]
            or passed["blocked_initial_turns"]
            or not passed["baseline_control_traces_match"]
            or not passed["duplicate_selected_traces_match"]
            or old["stage"] != "short_control"
            or any(old[k] != cfg[k] for k in same)
            or audit["report_id"] != cfg["control_audit"]["id"]
            or audit["source_report_id"] != passed["report_id"]
            or audit["auditor_sha256"]
            != cfg["implementation_sha256"]["native_combat_planning_audit.py"]
            or audit["branch_receipts_verified"] != passed["completed_units"]
            or any(
                audit[k] is not True
                for k in (
                    "all_choices_reconstructed",
                    "combat_plans_and_selection_reconstructed",
                    "planning_cost_charged_without_amortization",
                    "full_states_unchanged",
                )
            )
        ):
            raise ValueError("Matching native and saved combat-planning controls must pass")
        check_sources(root, passed["sources"])
        for key in ("control_report", "control_audit"):
            sources[cfg[key]["path"]] = _sha_file(root / cfg[key]["path"])
    sources.update(
        {
            str(path.relative_to(root)): _sha_file(path),
            **{f"src/spireshift/{n}": sha for n, sha in cfg["implementation_sha256"].items()},
            **{f"scripts/{n}": sha for n, sha in cfg["entry_sha256"].items()},
        }
    )
    return cfg, corpus, selected_roots, items, baseline, sources
