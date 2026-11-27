"""Versioned reward-belt repair and no-replay curriculum continuation admission."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.engine_startup import _script_closure
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_win2_recovery import continuation_plan
from spireshift.native_win_inputs import RECIPE as BASE_RECIPE
from spireshift.native_win_inputs import frozen_checks as frozen_checks
from spireshift.native_win_inputs import load as base_load

RECIPE = "configs/native-curriculum/sts2-v0.111.0-a8-win-curriculum-v2.json"


def binding(cfg: dict[str, Any]) -> str:
    return manifest_identifier({k: v for k, v in cfg.items() if k != "repair_control"})


def implementation(root: Path) -> dict[str, str]:
    names = {str(p.relative_to(root)) for p in (root / "src/spireshift").glob("native_win2_*.py")}
    names.update(
        "scripts/" + s
        for s in _script_closure(
            root / "scripts",
            {"engine-win-curriculum-worker-v2.mjs", "engine-reward-belt-surface-v1.mjs"},
        )
    )
    names.update(
        {
            "scripts/continue-win-curriculum-v2.sh",
            "scripts/win-curriculum-session-v2.py",
            "scripts/engine-reward-belt-surface-v1.test.mjs",
            "scripts/engine-reward-belt-regression-v1.mjs",
            "tests/unit/test_native_win2_recovery.py",
        }
    )
    pending = list(names)
    while pending:
        p = root / pending.pop()
        if p.suffix != ".py":
            continue
        for node in ast.walk(ast.parse(p.read_text())):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith("spireshift")
            ):
                child = root / "src" / Path(*node.module.split("."))
                child = (
                    child.with_suffix(".py")
                    if child.with_suffix(".py").is_file()
                    else child / "__init__.py"
                )
                name = str(child.relative_to(root))
                if child.is_file() and name not in names:
                    names.add(name)
                    pending.append(name)
    return {name: _sha_file(root / name) for name in sorted(names)}


def validate(cfg: dict[str, Any], parent: dict[str, Any]) -> None:
    if (
        cfg.get("schema_version") != "native-win-curriculum-config-v2"
        or cfg.get("workspace") != "artifacts/native-win-curriculum/study-v2"
        or cfg.get("plan") != continuation_plan(parent)
        or type(cfg.get("repair_generation")) is not int
        or not 1 <= cfg["repair_generation"] <= 8
        or cfg.get("historical_incomplete_cases") != 1
        or cfg.get("reused_original_cases") != 6
        or cfg.get("ordinary_PPO_allowed") is not False
        or cfg.get("main_optimizer_updates") != 0
        or cfg.get("automatic_follow_up") is not False
        or cfg.get("promotion_allowed") is not False
        or cfg.get("native_development_only") is not True
        or cfg.get("official_live_qualification_inherited") is not False
        or cfg.get("session_limits") != parent["session_limits"]
        or cfg.get("execution_runtime") != parent["execution_runtime"]
        or cfg.get("node") != parent["node"]
        or cfg.get("operation") != parent["operation"]
        or cfg.get("contract") != parent["contract"]
    ):
        raise ValueError("Use only the declared no-replay reward-belt continuation")
    original = {
        s
        for group in ("fit", "heldout")
        for case in parent["plan"][group]
        for s in case["seed_pool"]
    }
    replacement = set(cfg["plan"]["fit"][6]["seed_pool"])
    if original & replacement or len(replacement) != 8:
        raise ValueError("Interrupted worlds cannot be replacement worlds")


def load(root: Path, path: Path, *, require_control: bool = True) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    base = verified(root, cfg["base_recipe"])
    if str(base.relative_to(root)) != BASE_RECIPE:
        raise ValueError("Unexpected parent curriculum")
    context = base_load(root, base)
    parent = context["config"]
    validate(cfg, parent)
    if cfg["implementation"] != implementation(root):
        raise ValueError("Reward-belt continuation implementation changed")
    report = identified(verified(root, cfg["recovery_audit"]))
    resource = identified(verified(root, cfg["recovery_resource"]))
    if (
        report["status"] != "sealed_cases_verified_interrupted_world_excluded"
        or report["parent_config_id"] != context["config_id"]
        or len(report["imports"]) != 35
        or resource["status"] != "completed"
        or resource["exit_code"] != 0
        or resource["cap"] is not None
        or report["historical_failure"]["labels_allowed"] is not False
    ):
        raise ValueError("The saved recovery audit is incomplete")
    check_sources(root, report["sources"])
    check_sources(root, report["evidence"])
    check_sources(root, json.loads(verified(root, cfg["protection"]).read_text()))
    if require_control:
        r = identified(verified(root, cfg["repair_control"]["report"]))
        guard = identified(verified(root, cfg["repair_control"]["resource"]))
        if (
            r["status"] != "reward_belt_continuation_control_verified"
            or r["implementation_id"] != manifest_identifier(cfg["implementation"])
            or r["launch_binding_id"] != binding(cfg)
            or not r["checks"]
            or not all(r["checks"].values())
            or guard["status"] != "completed"
            or guard["exit_code"] != 0
            or guard["cap"] is not None
        ):
            raise ValueError("Exact-source reward-belt repair control is missing or stale")
        check_sources(root, r["sources"])
        check_sources(root, r["evidence"])
    return {
        **context,
        "config": cfg,
        "parent_config": copy.deepcopy(parent),
        "config_id": manifest_identifier(cfg),
        "recipe": path,
        "imports": report["imports"],
        "historical_failure": report["historical_failure"],
        "sources": {
            **context["sources"],
            **cfg["implementation"],
            str(path.relative_to(root)): _sha_file(path),
            cfg["recovery_audit"]["path"]: cfg["recovery_audit"]["sha256"],
            cfg["protection"]["path"]: cfg["protection"]["sha256"],
        },
    }
