"""Pinned scoped-view/control repairs on the preserved v36 host; no implicit resume."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.engine_startup import _script_closure
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_interface_inputs import dependencies as previous_dependencies
from spireshift.native_interface_inputs import load as previous
from spireshift.native_live_inputs import prepare

__all__ = ["load", "prepare"]
ROOTS = (
    "native_interface_controls_inputs",
    "native_live_checkpoint_v3",
    "native_official_session_v3",
    "native_interface_controls_audit",
)
ENTRIES = {
    "engine-shared-input-v3.mjs",
    "engine-live-checkpoint-v3.mjs",
    "audit-interface-controls-v1.mjs",
}
WRAPPERS = ("check-interface-controls-v1.sh", "compare-interface-controls-v1.sh")


def dependencies(root: Path) -> set[str]:
    pending = [f"spireshift.{name}" for name in ROOTS]
    seen: set[str] = set()
    files = previous_dependencies(root)
    while pending:
        name = pending.pop()
        if name in seen or not name.startswith("spireshift"):
            continue
        seen.add(name)
        path = root / "src" / Path(*name.split("."))
        path = path.with_suffix(".py") if path.with_suffix(".py").exists() else path / "__init__.py"
        if not path.is_file():
            raise ValueError(f"Missing controls execution dependency: {name}")
        files.add(str(path.relative_to(root)))
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and node.module:
                pending.append(node.module)
            elif isinstance(node, ast.Import):
                pending.extend(alias.name for alias in node.names)
    return files


def load(root: Path, path: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    stage = cfg.get("stage")
    offline, control = stage == "saved_only_checks", stage == "short_control"
    expected_decisions = 0 if offline else 4 if control else 128
    if (
        cfg.get("schema_version") != "native-interface-controls-config-v1"
        or stage not in {"saved_only_checks", "short_control", "bounded_live_checkpoint_canary"}
        or cfg.get("contract") != "official_cli_shared_public_graph_v1"
        or cfg.get("training_allowed") is not False
        or cfg.get("maximum_decisions") != expected_decisions
        or cfg.get("maximum_case_wall_seconds") != (0 if offline else 180 if control else 360)
        or len(cfg.get("cases", [])) != (0 if offline else 1 if control else 4)
        or cfg.get("session_limits")
        != {
            "wall_seconds": 240 if offline or control else 900,
            "cpu_seconds": 480 if offline or control else 1800,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 1000000000,
        }
        or not (root / cfg["workspace"])
        .resolve()
        .is_relative_to(
            root / "artifacts" / ("native-interface-controls" if offline else "native-live-adapter")
        )
        or len({(c["player"], c["seed"]) for c in cfg["cases"]}) != len(cfg["cases"])
        or len({c["key"] for c in cfg["cases"]}) != len(cfg["cases"])
    ):
        raise ValueError("Use the finite, separately pinned interface-controls plan")
    check_sources(root, cfg["sources"])
    expected = {name: _sha_file(root / name) for name in sorted(dependencies(root))}
    helpers = {
        f"scripts/{name}": _sha_file(root / "scripts" / name)
        for name in sorted(_script_closure(root / "scripts", ENTRIES))
    }
    entries = {f"scripts/{name}": _sha_file(root / "scripts" / name) for name in WRAPPERS}
    if (
        cfg["implementation_sha256"] != expected
        or cfg["helpers_sha256"] != helpers
        or cfg["entry_sha256"] != entries
        or any(
            cfg["sources"].get(name) != value
            for name, value in {**expected, **helpers, **entries}.items()
        )
    ):
        raise ValueError("Controls implementation/helper membership changed")
    ctx = previous(root, root / cfg["parent_interface_recipe"])
    if cfg["node"] != ctx["config"]["node"]:
        raise ValueError("Keep the pinned Node runtime")
    if (
        cfg["players"] != ctx["config"]["players"]
        or cfg["protected_originals"] != ctx["config"]["protected_originals"]
    ):
        raise ValueError("Keep both original full players and all Adam state")
    env = identified(verified(root, cfg["environment"]), "manifest_id")
    shared = {
        f"scripts/{name}": _sha_file(root / "scripts" / name)
        for name in sorted(_script_closure(root / "scripts", {"engine-shared-input-v3.mjs"}))
    }
    for key in (
        "parent_environment_id",
        "game_assembly_sha256",
        "build_report_id",
        "input_config_id",
        "official_connector_config_id",
        "profile",
        "character",
        "ascension",
        "helpers_sha256",
    ):
        if env[key] != ctx["environment"][key]:
            raise ValueError(f"Unrelated frozen execution identity changed: {key}")
    if (
        env["predecessor_interface_environment_id"] != ctx["environment"]["manifest_id"]
        or env["shared_input_helpers_sha256"] != shared
        or env["adapter_controls_contract"]
        != "scoped_card_views_explicit_shop_and_read_only_refresh_v1"
    ):
        raise ValueError("Controls environment does not bind the new adapter")
    used = {c["seed"] for c in ctx["config"]["cases"]}
    for case in cfg["cases"]:
        if (
            case["player"] not in (2, 3)
            or not case["seed"].isalnum()
            or not case["seed"].isupper()
            or case["seed"] in used
        ):
            raise ValueError("Use fresh declared worlds; preserve every previous attempt")
    if not offline:
        key = "offline_receipt" if control else "control_receipt"
        receipt = identified(verified(root, cfg[key]))
        expected_status = (
            "saved_interface_controls_pass" if control else "live_checkpoint_delivery_control_pass"
        )
        if (
            receipt["status"] != expected_status
            or receipt["environment_id"] != env["manifest_id"]
            or receipt["implementation_id"] != manifest_identifier(expected)
            or receipt["helpers_id"] != manifest_identifier(helpers)
        ):
            raise ValueError("Qualify the exact controls tuple before the next stage")
        check_sources(root, receipt["sources"])
        check_sources(root, receipt["evidence"])
        if not control and {c["seed"] for c in cfg["cases"]} & set(receipt["seeds"]):
            raise ValueError("Never reuse a control world in the owner canary")
    sources = {**ctx["sources"], **cfg["sources"], str(path.relative_to(root)): _sha_file(path)}
    sources[cfg["environment"]["path"]] = cfg["environment"]["sha256"]
    ctx.update(config=cfg, sources=sources, environment=env)
    return ctx
