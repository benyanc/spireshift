"""Separate native-development admission; old official gates remain unchanged."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.engine_worker_qualification import immutable_checks
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_curriculum_config import THREADS, execution_runtime
from spireshift.native_structured_state import load as load_state
from spireshift.native_win_plan import ACTS, CONTRACT, cases, plan, profile, start_cases
from spireshift.training_objective import TrainingScoreSpec

RECIPE = "configs/native-curriculum/sts2-v0.111.0-a8-win-curriculum-v1.json"


def binding(config: dict[str, Any]) -> str:
    return manifest_identifier({k: v for k, v in config.items() if k != "short_control"})


def implementation(root: Path) -> dict[str, str]:
    from spireshift.engine_startup import _script_closure

    names = {str(p.relative_to(root)) for p in (root / "src/spireshift").glob("native_win_*.py")}
    names.update(
        f"scripts/{s}"
        for s in _script_closure(
            root / "scripts",
            {
                "engine-win-curriculum-worker-v1.mjs",
                "engine-win-curriculum-save-v1.mjs",
                "engine-shared-input-v16.mjs",
            },
        )
    )
    names.update(
        {
            "scripts/prepare-win-curriculum-v1.sh",
            "scripts/win-curriculum-session-v1.py",
            "tests/unit/test_native_win_curriculum.py",
            "scripts/engine-win-curriculum-save-v1.test.mjs",
        }
    )
    # Include every imported Python implementation, without modifying old closures.
    pending = list(names)
    while pending:
        path = root / pending.pop()
        if path.suffix != ".py":
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith("spireshift")
            ):
                p = root / "src" / Path(*node.module.split("."))
                p = p.with_suffix(".py") if p.with_suffix(".py").is_file() else p / "__init__.py"
                if p.is_file() and str(p.relative_to(root)) not in names:
                    names.add(str(p.relative_to(root)))
                    pending.append(str(p.relative_to(root)))
    return {n: _sha_file(root / n) for n in sorted(names)}


def restore_paths(root: Path, value: Any) -> Any:
    if isinstance(value, dict):
        if set(value) == {"__path__"}:
            p = Path(value["__path__"])
            return p if p.is_absolute() else root / p
        return {k: restore_paths(root, v) for k, v in value.items()}
    if isinstance(value, list):
        return [restore_paths(root, v) for v in value]
    return value


def validate(config: dict[str, Any]) -> None:
    if (
        config.get("schema_version") != "native-win-curriculum-config-v1"
        or config.get("contract") != CONTRACT
        or config.get("plan") != plan()
        or config.get("workspace") != "artifacts/native-win-curriculum/study-v1"
        or config.get("ordinary_PPO_allowed") is not False
        or config.get("native_development_only") is not True
        or config.get("main_optimizer_updates") != 0
        or config.get("official_live_qualification_inherited") is not False
        or config.get("promotion_allowed") is not False
        or config.get("automatic_follow_up") is not False
        or config.get("operation") != "collect_training_only_curriculum_then_stop"
        or config.get("session_limits")
        != {
            "wall_seconds": 5400,
            "cpu_seconds": 14400,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 4000000000,
        }
    ):
        raise ValueError("Use the separately versioned all-act training-only scope")
    seeds = [
        s for phase in ("fit", "heldout") for c in config["plan"][phase] for s in c["seed_pool"]
    ]
    seeds += config["plan"]["reserved_evaluation_seeds"]
    if (
        type(config.get("control_generation")) is not int
        or not 1 <= config["control_generation"] <= 8
    ):
        raise ValueError("Use a declared fresh control generation")
    controls = [
        s
        for phase in ("control_fit", "control_heldout")
        for c in cases(phase, control=True, generation=config["control_generation"])
        for s in c["seed_pool"]
    ]
    controls += [s for c in start_cases(config["control_generation"]) for s in c["seed_pool"]]
    if len(set(seeds + controls)) != len(seeds + controls):
        raise ValueError("World partitions and preparation pools must be disjoint")


def load(root: Path, path: Path, *, require_control: bool = True) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    validate(cfg)
    if cfg["implementation"] != implementation(root):
        raise ValueError("Curriculum source/helpers/tests changed")
    if any(os.environ.get(n) != "1" for n in THREADS) or cfg[
        "execution_runtime"
    ] != execution_runtime(cfg["node"]):
        raise ValueError("Use the pinned runtime and single numerical threads")
    baseline = identified(verified(root, cfg["baseline"]))
    check_sources(root, baseline["sources"])
    check_sources(root, baseline["evidence"])
    native = restore_paths(root, baseline["native"])
    catalog = identified(verified(root, cfg["native_model_catalog"]))
    if catalog["assembly_sha256"] != native["build"]["runtime_sts2_sha256"]:
        raise ValueError("Curriculum models must come from this exact frozen game assembly")
    models_present = {row["id"] for row in catalog["models"] if not row["is_mock"]}
    for act in (1, 2, 3):
        for archetype in ("strength", "block", "exhaust"):
            p = profile(archetype, act)
            needed = {
                f"{family}.{name}"
                for family, group in [
                    ("CARD", p["deck"]),
                    ("RELIC", p["relics"]),
                    ("POTION", p["potions"]),
                ]
                for name in group
            }
            if not needed <= models_present:
                raise ValueError("A curriculum profile contains an unknown/mock native model")
    if not {"ENCOUNTER." + b for _, bs in ACTS.values() for b in bs} <= models_present:
        raise ValueError("A declared boss is absent from the frozen game")
    qualification = EngineQualificationConfig(baseline["qualification_document"], root)
    score = TrainingScoreSpec.from_mapping(baseline["training_score"])
    models, adams = {}, {}
    for p, ref in baseline["originals"].items():
        if _sha_file(root / ref["imported_path"]) != ref["imported_sha256"]:
            raise ValueError("Original full checkpoint changed")
        model, adam, sid = load_state(root / ref["imported_path"])
        if (
            sid != ref["imported_state_id"]
            or model.model_id != ref["imported_model_id"]
            or manifest_identifier(adam.as_dict()) != ref["optimizer_id"]
            or adam.steps != ref["optimizer_steps"]
        ):
            raise ValueError("Exact original weights/full Adam are required")
        models[int(p)], adams[int(p)] = model, adam
    history = json.loads(verified(root, cfg["seed_history"]).read_text())
    used = set(history["canonical_prior_seeds"])
    if any(
        s in used
        for partition in ("fit", "heldout")
        for c in cfg["plan"][partition]
        for s in c["seed_pool"]
    ):
        raise ValueError("A curriculum world overlaps historical/evaluation evidence")
    if require_control:
        if not cfg.get("short_control"):
            raise ValueError("Exact-source collect/learn/reload/held-world control is required")
        report = identified(verified(root, cfg["short_control"]["report"]))
        resource = identified(verified(root, cfg["short_control"]["resource"]))
        if (
            report.get("status") != "all_act_curriculum_control_verified"
            or report.get("implementation_id") != manifest_identifier(cfg["implementation"])
            or report.get("launch_binding_id") != binding(cfg)
            or not all(report.get("checks", {}).values())
            or not report.get("checks")
            or resource["status"] != "completed"
            or resource["exit_code"] != 0
            or resource["cap"] is not None
        ):
            raise ValueError("The new native-development control failed or is stale")
        check_sources(root, report["sources"])
        check_sources(root, report["evidence"])
    return {
        "qualification": qualification,
        "native": native,
        "config": cfg,
        "config_id": manifest_identifier(cfg),
        "recipe": path,
        "models": models,
        "adams": adams,
        "score": score,
        "environment": baseline["environment"],
        "node": cfg["node"],
        "originals": baseline["originals"],
        "baseline": baseline,
        "sources": {
            **cfg["implementation"],
            str(path.relative_to(root)): _sha_file(path),
            cfg["baseline"]["path"]: cfg["baseline"]["sha256"],
        },
    }


def frozen_checks(context: dict[str, Any]) -> dict[str, bool]:
    root, cfg = context["qualification"].root, context["config"]
    check_sources(root, json.loads(verified(root, cfg["protection"]).read_text()))
    checks = immutable_checks(context["qualification"], context["native"])
    if not all(checks.values()):
        raise ValueError("The frozen game/runtime/CLI/SDK changed")
    return {**checks, "original_and_prior_final_weights_full_Adam_exact": True}
