"""Finite, restartable native full-run action comparisons; no optimizer calls."""

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
from spireshift.engine_selection_worker import SCRIPT
from spireshift.engine_worker import worker_helpers
from spireshift.engine_worker_qualification import immutable_checks
from spireshift.full_run_experience import atomic_json
from spireshift.native_combat_teacher_branch import branch
from spireshift.native_combat_teacher_data import INFORMATION, lesson
from spireshift.native_context_journal import ChunkJournal, load_state
from spireshift.native_context_reuse import check_sources
from spireshift.native_feedback_audit import SOURCES as AUDIT_SOURCES
from spireshift.training_objective import load_training_score_spec

SOURCES = tuple(
    sorted(
        set(
            (
                *AUDIT_SOURCES,
                "native_combat_teacher.py",
                "native_combat_teacher_data.py",
                "native_combat_teacher_prepare.py",
                "native_combat_teacher_branch.py",
            )
        )
    )
)


def tasks(roots: list[dict[str, Any]], repeats: int, control: bool) -> list[dict[str, Any]]:
    result = []
    for index, root in enumerate(roots):
        for repeat in range(repeats):
            for action in range(len(root["public_input"]["candidates"])):
                result.append(
                    {
                        "key": f"root-{index:03d}-r-{repeat:02d}-a-{action:02d}",
                        "root_id": root["root_id"],
                        "action": action,
                        "repeat": repeat,
                        "duplicate_control": False,
                    }
                )
        if control:
            result.append(
                {
                    "key": f"root-{index:03d}-duplicate-reference",
                    "root_id": root["root_id"],
                    "action": root["reference_action"],
                    "repeat": 0,
                    "duplicate_control": True,
                }
            )
    return result


def load(
    root: Path, path: Path
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, str]]:
    cfg = json.loads(path.read_text())
    control = cfg.get("stage") == "short_control"
    if (
        cfg.get("schema_version") != "native-combat-comparison-teacher-config-v1"
        or cfg.get("stage") not in {"short_control", "finite_teacher_pilot"}
        or cfg.get("information_scope") != INFORMATION
        or cfg.get("ordinary_PPO_eligible") is not False
        or cfg.get("repeats") != (2 if control else 8)
        or cfg.get("implementation_sha256")
        != {n: _sha_file(root / "src/spireshift" / n) for n in SOURCES}
        or cfg.get("helpers_sha256") != worker_helpers(root, SCRIPT)
        or cfg.get("entry_sha256")
        != {
            n: _sha_file(root / "scripts" / n)
            for n in (
                "native-combat-teacher-v1.py",
                "collect-native-combat-teacher-v1.sh",
                "verify-selection-cursor-v1.mjs",
            )
        }
        or cfg.get("session_limits")
        != {
            "wall_seconds": 240 if control else 900,
            "cpu_seconds": 480 if control else 1800,
            "resident_memory_bytes": 2000000000,
            "storage_bytes": 1000000000 if control else 4000000000,
        }
    ):
        raise ValueError("Freeze native teacher sources, fixed-world scope and finite caps")
    source = identified(root / cfg["roots_report"]["path"])
    if source["report_id"] != cfg["roots_report"]["id"] or source["new_games"] != 0:
        raise ValueError("Native roots differ from the frozen TRAIN-only selection")
    check_sources(root, source["sources"])
    refs = source["roots"]
    if control:
        refs = [
            min(
                (r for r in refs if r["numerical_seed"] == n),
                key=lambda r: (r["actions"], r["prefix_decisions"], r["id"]),
            )
            for n in (2, 3)
        ]
    roots = [identified(root / r["path"], "root_id") for r in refs]
    if any(r["id"] != value["root_id"] for r, value in zip(refs, roots, strict=True)):
        raise ValueError("Native root identity differs from the prepared corpus")
    if len(roots) != (2 if control else 8) or len({r["native_seed"] for r in roots}) != len(roots):
        raise ValueError("Keep distinct original TRAIN worlds and both numerical players")
    if cfg["temperature"] != source["temperature"]:
        raise ValueError("Do not tune continuation sampling after observing comparisons")
    if not control:
        passed = identified(root / cfg["control_report"]["path"])
        old = json.loads((root / passed["recipe_path"]).read_text())
        if (
            passed["report_id"] != cfg["control_report"]["id"]
            or passed["status"] != "native_combat_teacher_complete"
            or passed["failed_branches"]
            or passed["skipped_branches"]
            or not passed["duplicate_public_traces_identical"]
            or not all(c["comparison_complete"] for c in passed["cases"])
            or any(
                old[k] != cfg[k]
                for k in (
                    "implementation_sha256",
                    "roots_report",
                    "helpers_sha256",
                    "native_inputs",
                    "temperature",
                    "qualification",
                    "qualification_id",
                    "node",
                    "entry_sha256",
                    "information_scope",
                )
            )
        ):
            raise ValueError("Exact-prefix/all-action/repeated-trace native control must pass")
        check_sources(root, passed["sources"])
    sources = {
        **source["sources"],
        str(path.relative_to(root)): _sha_file(path),
        cfg["roots_report"]["path"]: _sha_file(root / cfg["roots_report"]["path"]),
        **{f"src/spireshift/{n}": sha for n, sha in cfg["implementation_sha256"].items()},
        **{f"scripts/{n}": sha for n, sha in cfg["entry_sha256"].items()},
        **{f"scripts/{n}": sha for n, sha in cfg["helpers_sha256"].items()},
    }
    if not control:
        sources[cfg["control_report"]["path"]] = _sha_file(root / cfg["control_report"]["path"])
    return cfg, source, roots, sources


def run(root: Path, path: Path, node: Path, *, status_only: bool = False) -> dict[str, Any]:
    cfg, corpus, roots, sources = load(root, path)
    store = ChunkJournal(root, cfg)
    final = store.workspace / "report.json"
    if final.exists():
        saved = identified(final)
        check_sources(root, saved["sources"])
        return saved
    plan = tasks(roots, cfg["repeats"], cfg["stage"] == "short_control")
    if status_only:
        return {
            "status": "native_teacher_plan_only",
            "roots": len(roots),
            "planned_branches": len(plan),
            "new_games": 0,
            "optimizer_steps": 0,
            "information_scope": INFORMATION,
        }
    if node != Path(cfg["node"]):
        raise ValueError("Use the exact Node runtime frozen in the teacher recipe")
    if _running_games() or not node.is_file():
        raise ValueError("Close STS2 before the isolated native teacher collection")
    q = load_engine_qualification_config(root / cfg["qualification"])
    if cfg["qualification_id"] != q.config_id:
        raise ValueError("Frozen native qualification changed")
    inputs = _run_inputs(q, root / cfg["native_inputs"]["path"])
    if manifest_identifier(inputs["recipe"]) != cfg["native_inputs"]["id"]:
        raise ValueError("The qualified actual-engine host changed")
    score = load_training_score_spec(root / corpus["training_spec"]["path"])
    if inputs["objective"] != score.evaluation_objective.as_dict():
        raise ValueError("Native teacher cannot silently change the terminal objective or budget")
    models = {}
    for ref in corpus["models"]:
        model, optimizer, state_id = load_state(root / ref["state_path"])
        if state_id != ref["state_id"] or optimizer.steps != ref["optimizer_steps"]:
            raise ValueError("Preserve exact continuation weights and every Adam moment")
        if (
            model.actor.environment_id != corpus["environment_manifest"]["id"]
            or model.feature_spec_id != score.spec_id
        ):
            raise ValueError("Continuation model belongs to another engine or training score")
        models[ref["numerical_seed"]] = model
    if any(models[r["numerical_seed"]].model_id != r["continuation_model_id"] for r in roots):
        raise ValueError("Native root cannot silently change its frozen continuation player")
    by_id = {r["root_id"]: r for r in roots}
    profile = Path.home() / "Library/Application Support/SlayTheSpire2"
    snapshot = _shared_snapshot(profile)
    started = time.monotonic()
    deadline = started + cfg["session_limits"]["wall_seconds"] - 10
    completed: dict[str, dict[str, Any]] = {}
    blocked: set[str] = set()
    grouped: dict[str, list[dict[str, Any]]] = {r["root_id"]: [] for r in roots}
    with store.lock():
        for task in plan:
            req = {**task, "scope": INFORMATION}
            receipt = store.completed(task["key"], req)
            if receipt is None:
                if deadline - time.monotonic() < (90 if cfg["stage"] == "short_control" else 130):
                    break
                target = store.begin(task["key"], req)
                r = by_id[task["root_id"]]
                result = (
                    {
                        "status": "not_attempted_root_blocked",
                        "root_id": r["root_id"],
                        "action": task["action"],
                        "repeat": task["repeat"],
                        "duplicate_control": task["duplicate_control"],
                    }
                    if r["root_id"] in blocked
                    else branch(
                        q,
                        cfg,
                        inputs,
                        target,
                        node,
                        r,
                        task["action"],
                        task["repeat"],
                        models[r["numerical_seed"]],
                        score,
                        deadline,
                        duplicate=task["duplicate_control"],
                    )
                )
                receipt = store.commit(task["key"], req, result)
                print(
                    f"Native teacher: {len(completed) + 1}/{len(plan)} branches saved; "
                    f"{result['status']}; optimizer updates 0.",
                    flush=True,
                )
            result = receipt["result"]
            completed[task["key"]] = result
            grouped[task["root_id"]].append(result)
            if result["status"] == "terminal" and (
                not result["root_reached"] or not result["native_audit_valid"]
            ):
                raise ValueError("Native branch ended without its exact audited intervention")
            if result["status"] == "failed":
                blocked.add(task["root_id"])
                if not result["root_reached"]:
                    raise ValueError(
                        "Exact native root replay failed; preserve this attempt for inspection"
                    )
            p = store.path(task["key"]) / "done.json"
            sources[str(p.relative_to(root))] = _sha_file(p)
            sources.update(receipt["sources"])
        checks = immutable_checks(q, inputs)
        checks["account_profile_unchanged"] = _shared_snapshot(profile) == snapshot
        check_sources(root, sources)
        if not all(checks.values()):
            raise ValueError("Native teacher changed shared runtime, game, SDK or account inputs")
        complete = len(completed) == len(plan)
        duplicates = []
        for task in plan:
            if task["key"] not in completed or not task["duplicate_control"]:
                continue
            original = next(
                t
                for t in plan
                if t["root_id"] == task["root_id"]
                and t["action"] == task["action"]
                and t["repeat"] == 0
                and not t["duplicate_control"]
            )
            a, b = completed[original["key"]], completed[task["key"]]
            duplicates.append(
                a.get("trace_id") is not None and a.get("trace_id") == b.get("trace_id")
            )
        if duplicates and not all(duplicates):
            raise ValueError(
                "Identical native prefix/action/policy stream did not reproduce its public trace"
            )
        cases = (
            [lesson(r, grouped[r["root_id"]], cfg["repeats"]) for r in roots] if complete else []
        )
        body = {
            "schema_version": "native-combat-comparison-teacher-v1",
            "recipe_path": str(path.relative_to(root)),
            "config_id": manifest_identifier(cfg),
            "status": "native_combat_teacher_complete"
            if complete
            else "paused_between_native_branches",
            "completed_units": len(completed),
            "planned_branches": len(plan),
            "native_attempts": sum(
                v["status"] != "not_attempted_root_blocked" for v in completed.values()
            ),
            "failed_branches": sum(v["status"] == "failed" for v in completed.values()),
            "skipped_branches": sum(
                v["status"] == "not_attempted_root_blocked" for v in completed.values()
            ),
            "duplicate_public_traces_identical": all(duplicates) if duplicates else None,
            "distinct_source_hidden_worlds": len(roots),
            "policy_streams_per_action": cfg["repeats"],
            "independent_hidden_worlds_per_root": 1,
            "information_scope": INFORMATION,
            "privileged_fixed_world_teacher": True,
            "ordinary_PPO_eligible": False,
            "public_belief_search_eligible": False,
            "student_inputs_public_only": True,
            "full_run_wins": sum(v.get("victory", False) for v in completed.values()),
            "production_optimizer_steps": 0,
            "original_full_states_unchanged": True,
            "game_apps_created": 0,
            "checks": checks,
            "cases": cases,
            "admitted_exploratory_preferences": sum(
                p["admitted_exploratory_preference"] for c in cases for p in c["preferences"]
            ),
            "sources": sources,
            "checkpoint_promoted": False,
            "adaptive_controller_allowed": False,
            "automatic_training_follows": False,
            "wall_seconds": time.monotonic() - started,
        }
        report = {**body, "report_id": manifest_identifier(body)}
        if complete:
            atomic_json(final, report)
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    try:
        report = run(root, root / args.recipe, args.node, status_only=args.status)
        print(
            json.dumps({k: v for k, v in report.items() if k not in {"cases", "sources"}}, indent=2)
        )
        return 0
    except (ValueError, KeyError, OSError, TimeoutError) as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
