"""New support-build admission and immutable imports from thirty clean cases."""

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
from spireshift.native_win2_inputs import RECIPE as PARENT_RECIPE
from spireshift.native_win2_inputs import frozen_checks as frozen_checks
from spireshift.native_win2_inputs import load as parent_load
from spireshift.native_win3_recovery import continuation_plan

RECIPE = "configs/native-curriculum/sts2-v0.111.0-a8-win-curriculum-v3.json"
AUDIT_SOURCE = "src/spireshift/native_win3_recovery.py"


def binding(cfg: dict[str, Any]) -> str:
    return manifest_identifier({k: v for k, v in cfg.items() if k != "support_control"})


def implementation(root: Path) -> dict[str, str]:
    # Reuse the recursive source walker without changing the earlier entry point.
    import ast

    from spireshift.engine_startup import _script_closure

    names = {str(p.relative_to(root)) for p in (root / "src/spireshift").glob("native_win3_*.py")}
    names.update(
        "scripts/" + n
        for n in _script_closure(root / "scripts", {"engine-win-curriculum-worker-v3.mjs"})
    )
    names.update(
        {
            "scripts/continue-win-curriculum-v3.sh",
            "scripts/win-curriculum-session-v3.py",
            "tests/unit/test_native_win3_support.py",
            "scripts/engine-native-runtime-errors-v1.test.mjs",
            "backend-patches/godot-node-index-v1/Probe.csproj",
            "backend-patches/godot-node-index-v1/Program.cs",
            "backend-patches/godot-node-index-v1/node-index.patch",
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
    if (
        cfg.get("schema_version") != "native-win-curriculum-config-v3"
        or cfg.get("workspace") != "artifacts/native-win-curriculum/study-v3"
        or cfg.get("plan") != continuation_plan(parent)
        or type(cfg.get("support_control_generation")) is not int
        or not 1 <= cfg["support_control_generation"] <= 8
        or cfg.get("historical_incomplete_cases") != 2
        or cfg.get("reused_original_cases") != 30
        or cfg.get("main_optimizer_updates") != 0
        or cfg.get("ordinary_PPO_allowed") is not False
        or cfg.get("promotion_allowed") is not False
        or cfg.get("automatic_follow_up") is not False
        or cfg.get("official_live_qualification_inherited") is not False
        or cfg.get("native_development_only") is not True
        or cfg.get("session_limits") != parent["session_limits"]
        or cfg.get("execution_runtime") != parent["execution_runtime"]
        or cfg.get("node") != parent["node"]
        or cfg.get("operation") != parent["operation"]
        or cfg.get("contract") != parent["contract"]
    ):
        raise ValueError(
            "Use the declared support-build-only continuation with both failures retained"
        )


def verify_audit_sources(root: Path, report: dict[str, Any], archive: dict[str, Any]) -> None:
    # The saved audit ran before a formatting-only edit. Its exact executable
    # source is explicitly archived; every other original source still matches.
    source = verified(root, archive)
    if report["sources"].get(AUDIT_SOURCE) != _sha_file(source):
        raise ValueError("Saved-audit implementation archive differs")
    check_sources(root, {k: v for k, v in report["sources"].items() if k != AUDIT_SOURCE})
    check_sources(root, report["evidence"])


def load(root: Path, path: Path, *, require_control: bool = True) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    p = verified(root, cfg["continuation_parent"])
    if str(p.relative_to(root)) != PARENT_RECIPE:
        raise ValueError("Unexpected continuation parent")
    ctx = parent_load(root, p)
    parent = ctx["config"]
    validate(cfg, parent)
    if cfg["implementation"] != implementation(root):
        raise ValueError("Support continuation sources changed")
    imports: dict[str, Any] = {}
    reports = []
    for first, last, ref, resource_ref in cfg["saved_audits"]:
        r = identified(verified(root, ref))
        resource = identified(verified(root, resource_ref))
        if (
            r["status"] != "saved_cases_verified_runtime_error_excluded"
            or r["parent_config_id"] != ctx["config_id"]
            or (r["first_case"], r["last_case"]) != (first, last)
            or resource["status"] != "completed"
            or resource["exit_code"] != 0
            or resource["cap"] is not None
        ):
            raise ValueError("A saved case audit is incomplete")
        verify_audit_sources(root, r, cfg["saved_audit_source"])
        if set(imports) & r["imports"].keys():
            raise ValueError("Repeated imported case units")
        imports.update(r["imports"])
        reports.append(r)
    if len(imports) != 168 or sum(r["completed_cases"] for r in reports) != 30:
        raise ValueError("All thirty complete cases must be conserved")
    failures = reports[-1]["historical_failures"]
    if len(failures) != 2 or any(r["labels_allowed"] for r in failures):
        raise ValueError("Failed episodes cannot provide labels")
    support = identified(verified(root, cfg["support_build"]))
    resource = identified(verified(root, cfg["support_build_resource"]))
    if (
        support["status"] != "support_build_and_jit_verified"
        or resource["status"] != "completed"
        or resource["exit_code"] != 0
        or resource["cap"] is not None
        or support["changed_production_source_files"] != ["GodotStubs/Core.cs"]
    ):
        raise ValueError("Pinned support build is unqualified")
    archived = verified(root, cfg["support_build_source"])
    if support["sources"].get("src/spireshift/native_win3_build.py") != _sha_file(archived):
        raise ValueError("Support build source archive changed")
    check_sources(
        root,
        {k: v for k, v in support["sources"].items() if k != "src/spireshift/native_win3_build.py"},
    )
    check_sources(root, support["evidence"])
    built = support["builds"][0]
    native = copy.deepcopy(ctx["native"])
    if built["runtime_sts2_sha256"] != native["build"]["runtime_sts2_sha256"]:
        raise ValueError("Game assembly changed")
    native.update(
        candidate=root / built["candidate"], candidate_before=support["candidate_inventory"]
    )
    native["build"] = {
        **native["build"],
        **{
            k: built[k]
            for k in [
                "artifact_sha256",
                "artifact_mvid",
                "godot_stub_sha256",
                "runtime_sts2_sha256",
            ]
        },
    }
    execution = {
        "schema_version": "native-curriculum-support-execution-v57",
        "parent_environment_id": ctx["environment"]["manifest_id"],
        "input_contract_environment_id": ctx["environment"]["manifest_id"],
        "support_build_id": support["report_id"],
        "official_qualification": False,
    }
    environment = {**execution, "manifest_id": manifest_identifier(execution)}
    native["recipe"]["input_config_id"] = environment["manifest_id"]
    check_sources(root, json.loads(verified(root, cfg["protection"]).read_text()))
    if require_control:
        r = identified(verified(root, cfg["support_control"]["report"]))
        guard = identified(verified(root, cfg["support_control"]["resource"]))
        if (
            r["status"] != "reattach_support_and_continuation_verified"
            or r["implementation_id"] != manifest_identifier(cfg["implementation"])
            or r["launch_binding_id"] != binding(cfg)
            or not r["checks"]
            or not all(r["checks"].values())
            or guard["status"] != "completed"
            or guard["exit_code"] != 0
            or guard["cap"] is not None
        ):
            raise ValueError("Support control failed or is stale")
        check_sources(root, r["sources"])
        check_sources(root, r["evidence"])
    refs = [
        cfg["continuation_parent"],
        cfg["support_build"],
        cfg["protection"],
        cfg["saved_audit_source"],
        cfg["support_build_source"],
    ] + [x[2] for x in cfg["saved_audits"]]
    sources = {
        **ctx["sources"],
        **cfg["implementation"],
        str(path.relative_to(root)): _sha_file(path),
        **{r["path"]: r["sha256"] for r in refs},
    }
    return {
        **ctx,
        "parent_config": copy.deepcopy(parent),
        "config": cfg,
        "config_id": manifest_identifier(cfg),
        "recipe": path,
        "native": native,
        "environment": environment,
        "imports": imports,
        "historical_failures": failures,
        "sources": sources,
    }
