"""Native-only large ordered-answer admission; all earlier scopes remain immutable."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_win3_inputs import RECIPE as PARENT_RECIPE
from spireshift.native_win3_inputs import frozen_checks as frozen_checks
from spireshift.native_win3_inputs import load as parent_load
from spireshift.native_win4_recovery import continuation_plan

RECIPE = "configs/native-curriculum/sts2-v0.111.0-a8-win-curriculum-v4.json"


def binding(cfg: dict[str, Any]) -> str:
    return manifest_identifier({k: v for k, v in cfg.items() if k != "plan_control"})


def implementation(root: Path) -> dict[str, str]:
    # Reuse the recursive source walker without changing the earlier entry point.
    import ast

    from spireshift.engine_startup import _script_closure

    names = {str(p.relative_to(root)) for p in (root / "src/spireshift").glob("native_win4_*.py")}
    names.update(
        "scripts/" + n
        for n in _script_closure(root / "scripts", {"engine-win-curriculum-worker-v4.mjs"})
    )
    names.update(
        {
            "scripts/continue-win-curriculum-v4.sh",
            "scripts/win-curriculum-session-v4.py",
            "tests/unit/test_native_win4_plan.py",
            "scripts/engine-ordered-plan-v1.test.mjs",
            "scripts/engine-ordered-plan-regression-v1.mjs",
            "scripts/engine-ordered-plan-verify-v1.mjs",
        }
    )
    pending = list(names)
    while pending:
        p = root / pending.pop()
        if p.suffix != ".py":
            continue
        for item in ast.walk(ast.parse(p.read_text())):
            if (
                isinstance(item, ast.ImportFrom)
                and item.module
                and item.module.startswith("spireshift")
            ):
                child = root / "src" / Path(*item.module.split("."))
                child = (
                    child.with_suffix(".py")
                    if child.with_suffix(".py").is_file()
                    else child / "__init__.py"
                )
                name = str(child.relative_to(root))
                if child.is_file() and name not in names:
                    names.add(name)
                    pending.append(name)
    return {n: _sha_file(root / n) for n in sorted(names)}


def validate(cfg: dict[str, Any], parent: dict[str, Any]) -> None:
    changed = {
        "schema_version",
        "workspace",
        "continuation_parent",
        "implementation",
        "plan",
        "historical_incomplete_cases",
        "reused_original_cases",
    }
    for key, value in parent.items():
        if key not in changed and cfg.get(key) != value:
            raise ValueError("Parent curriculum criteria, runtime or original evidence changed")
    if (
        cfg.get("schema_version") != "native-win-curriculum-config-v4"
        or cfg.get("workspace") != "artifacts/native-win-curriculum/study-v4"
        or cfg.get("plan") != continuation_plan(parent)
        or cfg.get("historical_incomplete_cases") != 3
        or cfg.get("reused_original_cases") != 31
        or cfg.get("ordered_answer_contract") != "factorized_ordered_card_answer_v1"
        or type(cfg.get("plan_control_generation")) is not int
        or not 1 <= cfg["plan_control_generation"] <= 8
    ):
        raise ValueError("Use only the separate no-replay compact-answer continuation")
    prior = {
        s
        for group in ["fit", "heldout"]
        for case in parent["plan"][group]
        for s in case["seed_pool"]
    }
    replacement = set(cfg["plan"]["fit"][31]["seed_pool"])
    if replacement & prior or len(replacement) != 8:
        raise ValueError("Failed worlds cannot be replacement worlds")


def load(root: Path, path: Path, *, require_control: bool = True) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    parent = verified(root, cfg["continuation_parent"])
    if str(parent.relative_to(root)) != PARENT_RECIPE:
        raise ValueError("Unexpected continuation parent")
    ctx = parent_load(root, parent)
    validate(cfg, ctx["config"])
    if implementation(root) != cfg["implementation"]:
        raise ValueError("Compact-answer sources changed")
    audit = identified(verified(root, cfg["plan_audit"]))
    resource = identified(verified(root, cfg["plan_audit_resource"]))
    if (
        audit["status"] != "complete_cases_preserved_large_selection_excluded"
        or audit["parent_config_id"] != ctx["config_id"]
        or audit["completed_cases"] != 31
        or len(audit["imports"]) != 173
        or len(audit["historical_failures"]) != 3
        or any(f["labels_allowed"] for f in audit["historical_failures"])
        or resource["status"] != "completed"
        or resource["exit_code"] != 0
        or resource["cap"] is not None
    ):
        raise ValueError("Saved continuation audit incomplete")
    check_sources(root, audit["sources"])
    check_sources(root, audit["evidence"])
    check_sources(root, json.loads(verified(root, cfg["plan_protection"]).read_text()))
    execution = {
        "schema_version": "native-curriculum-ordered-plan-execution-v1",
        "parent_environment_id": ctx["environment"]["manifest_id"],
        "ordered_answer_contract": cfg["ordered_answer_contract"],
        "official_qualification": False,
    }
    environment = {**execution, "manifest_id": manifest_identifier(execution)}
    native = copy.deepcopy(ctx["native"])
    native["recipe"]["input_config_id"] = environment["manifest_id"]
    if require_control:
        proof = identified(verified(root, cfg["plan_control"]["report"]))
        guard = identified(verified(root, cfg["plan_control"]["resource"]))
        if (
            proof["status"] != "compact_answer_and_continuation_verified"
            or proof["implementation_id"] != manifest_identifier(cfg["implementation"])
            or proof["launch_binding_id"] != binding(cfg)
            or not all(proof["checks"].values())
            or guard["status"] != "completed"
            or guard["exit_code"] != 0
            or guard["cap"] is not None
        ):
            raise ValueError("Compact-answer native control failed or stale")
        check_sources(root, proof["sources"])
        check_sources(root, proof["evidence"])
    sources = {
        **ctx["sources"],
        **cfg["implementation"],
        str(path.relative_to(root)): _sha_file(path),
        **{
            cfg[k]["path"]: cfg[k]["sha256"]
            for k in ["continuation_parent", "plan_audit", "plan_audit_resource", "plan_protection"]
        },
    }
    return {
        **ctx,
        "parent_config": ctx["config"],
        "config": cfg,
        "config_id": manifest_identifier(cfg),
        "recipe": path,
        "native": native,
        "environment": environment,
        "imports": audit["imports"],
        "historical_failures": audit["historical_failures"],
        "sources": sources,
    }
