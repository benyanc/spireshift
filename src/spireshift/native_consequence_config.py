"""Pinned supervised-loss ablation, fresh development worlds and short native controls."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_consequence_data import CONTRACT, TARGETS
from spireshift.native_consequence_math import ARMS, HEAD_SEEDS, SETTINGS
from spireshift.native_context_journal import load_state
from spireshift.native_context_reuse import check_sources

SOURCES = (
    "native_consequence_data.py",
    "native_consequence_math.py",
    "native_consequence_sources.py",
    "native_consequence_config.py",
    "native_consequence_evaluation.py",
    "native_consequence_study.py",
)
ENTRIES = ("native-combat-consequences-v1.py", "test-native-combat-consequences-v1.sh")
EVAL_ARMS = ("original", "return_only", "consequence")
SHARED = (
    "teacher_recipe",
    "teacher_report",
    "teacher_assessment",
    "consequence_contract",
    "targets",
    "learning",
    "arms",
    "deployment_head_seed",
    "implementation_sha256",
    "entry_sha256",
    "source_world_split",
    "information_scope",
    "ordinary_PPO_eligible",
    "freshness_exclusions",
    "maximum_decisions",
    "episode_wall_seconds",
    "qualification",
    "qualification_id",
    "native_inputs",
    "helpers_sha256",
    "node",
)


def load_config(root: Path, path: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    control = cfg.get("stage") == "short_control"
    if (
        cfg.get("schema_version") != "native-combat-consequence-config-v1"
        or cfg.get("stage") not in {"short_control", "bounded_learning_comparison"}
        or cfg.get("consequence_contract") != CONTRACT
        or cfg.get("targets") != list(TARGETS)
        or cfg.get("learning") != SETTINGS
        or cfg.get("arms") != list(ARMS)
        or cfg.get("deployment_head_seed") != HEAD_SEEDS[0]
        or cfg.get("cv_head_seeds") != list(HEAD_SEEDS[:1] if control else HEAD_SEEDS)
        or cfg.get("source_world_split")
        != "leave_one_entire_source_world_out_separately_per_parent_v1"
        or cfg.get("information_scope")
        != "public_student_inputs_privileged_fixed_world_supervised_labels"
        or cfg.get("ordinary_PPO_eligible") is not False
        or cfg.get("maximum_decisions") != 4096
        or cfg.get("episode_wall_seconds") != 120
        or cfg.get("implementation_sha256")
        != {n: _sha_file(root / "src/spireshift" / n) for n in SOURCES}
        or cfg.get("entry_sha256") != {n: _sha_file(root / "scripts" / n) for n in ENTRIES}
        or cfg.get("session_limits")
        != {
            "wall_seconds": 240 if control else 900,
            "cpu_seconds": 480 if control else 1800,
            "resident_memory_bytes": 2000000000,
            "storage_bytes": 1000000000 if control else 4000000000,
        }
    ):
        raise ValueError(
            "Freeze the finite consequence ablation, target/input boundaries and budgets"
        )
    return cast(dict[str, Any], cfg)


def evaluation_seeds(
    root: Path,
    cfg: dict[str, Any],
    teacher: dict[str, Any],
    environment_id: str,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    control = cfg["stage"] == "short_control"
    path = root / cfg["seed_manifest"]["path"]
    m = identified(path, "manifest_id")
    seeds = m["seeds"]
    required = {"id", "seed", "numerical_seed"} if control else {"id", "seed"}
    if (
        m["manifest_id"] != cfg["seed_manifest"]["id"]
        or m["schema_version"] != "native-combat-consequence-seeds-v1"
        or m["environment_id"] != environment_id
        or m["partition"] != ("control" if control else "development")
        or len(seeds) != (2 if control else 32)
        or any(
            set(s) != required
            or type(s["id"]) is not int
            or not isinstance(s["seed"], str)
            or not s["seed"]
            for s in seeds
        )
        or (
            control
            and (
                [s["numerical_seed"] for s in seeds] != [2, 3]
                or any(type(s["numerical_seed"]) is not int for s in seeds)
            )
        )
        or len({s["id"] for s in seeds}) != len(seeds)
        or len({s["seed"].upper() for s in seeds}) != len(seeds)
    ):
        raise ValueError("Freeze fresh complete-game development worlds, shared by all model arms")
    old = [
        *teacher["freshness_exclusions"],
        *teacher["excluded_seed_manifests"],
        teacher["seed_manifest"],
    ]
    expected = list({r["path"]: r for r in old}.values())
    if cfg["freshness_exclusions"] != expected:
        raise ValueError(
            "Retain every historical TRAIN, development, confirmation and control seed exclusion"
        )
    extra = cfg["excluded_seed_manifests"]
    if control and extra:
        raise ValueError("Do not change the predeclared control seed exclusions")
    if not control:
        control_cfg = json.loads((root / cfg["control_recipe"]["path"]).read_text())
        if extra != [control_cfg["seed_manifest"]]:
            raise ValueError(
                "Main games must also exclude both separate consequence control worlds"
            )
    sources = {str(path.relative_to(root)): _sha_file(path)}
    for ref in [*expected, *extra]:
        other = identified(root / ref["path"], "manifest_id")
        if other["manifest_id"] != ref["id"]:
            raise ValueError("An excluded seed manifest changed")
        if {s["id"] for s in seeds} & {s["id"] for s in other["seeds"]} or {
            s["seed"].upper() for s in seeds
        } & {s["seed"].upper() for s in other["seeds"]}:
            raise ValueError("Reused native world in a fresh consequence comparison")
        sources[ref["path"]] = _sha_file(root / ref["path"])
    return seeds, sources


def qualified_control(root: Path, cfg: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    recipe = root / cfg["control_recipe"]["path"]
    old = load_config(root, recipe)
    report = identified(root / cfg["control_report"]["path"])
    if (
        _sha_file(recipe) != cfg["control_recipe"]["sha256"]
        or old["stage"] != "short_control"
        or any(old[k] != cfg[k] for k in SHARED)
        or report["report_id"] != cfg["control_report"]["id"]
        or report["config_id"] != manifest_identifier(old)
        or report["status"] != "native_consequence_control_complete"
        or report["completed_games"] != 8
        or report["failed_games"]
        or not report["duplicate_traces_match"]
        or not report["mathematical_controls"]["passed"]
        or not report["original_full_states_unchanged"]
        or not all(report["checks"].values())
        or [p["numerical_seed"] for p in report["parents"]] != [2, 3]
        or {(p["numerical_seed"], p["arm"]) for p in report["final_forks"]}
        != {(p, arm) for p in (2, 3) for arm in ("return_only", "consequence")}
        or len(report["final_forks"]) != 4
    ):
        raise ValueError(
            "Require matching saved mathematical, state-preservation and native controls"
        )
    check_sources(root, report["sources"])
    for p in report["parents"]:
        model, adam, state_id = load_state(root / p["path"])
        if (
            model.model_id != p["model_id"]
            or state_id != p["state_id"]
            or adam.steps != p["optimizer_steps"]
        ):
            raise ValueError("Original player/Adam state differs from the qualified control")
        for fork in report["final_forks"]:
            if fork["numerical_seed"] == p["numerical_seed"] and (
                fork["initial_optimizer_steps"] != adam.steps
                or fork["optimizer_steps"] != adam.steps + SETTINGS["epochs"]
            ):
                raise ValueError("Supervised forks must continue the original full Adam counters")
    for fork in report["final_forks"]:
        model, adam, _ = load_state(root / fork["state_path"])
        if model.model_id != fork["model_id"] or adam.steps != fork["optimizer_steps"]:
            raise ValueError("Qualified supervised fork bytes or complete optimizer state changed")
    sources = dict(report["sources"])
    sources[cfg["control_recipe"]["path"]] = _sha_file(recipe)
    sources[cfg["control_report"]["path"]] = _sha_file(root / cfg["control_report"]["path"])
    return report, sources
