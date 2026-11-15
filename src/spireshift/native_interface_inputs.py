"""Exact, separately labelled interface-repair context; never alters a frozen host."""

from __future__ import annotations

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
from spireshift.native_interface_build import verify_build
from spireshift.native_live_inputs import dependencies as previous_dependencies
from spireshift.native_live_inputs import load as previous
from spireshift.native_live_inputs import prepare

__all__ = ["load", "prepare"]
NEW_SOURCES = (
    "native_interface_inputs.py",
    "native_interface_build.py",
    "native_live_checkpoint_v2.py",
    "native_official_session_v2.py",
)


def dependencies(root: Path) -> set[str]:
    return previous_dependencies(root) | {f"src/spireshift/{name}" for name in NEW_SOURCES}


def load(root: Path, path: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    control = cfg.get("stage") == "short_control"
    if (
        cfg.get("schema_version") != "native-interface-live-config-v1"
        or cfg.get("contract") != "official_cli_shared_public_graph_v1"
        or cfg.get("stage") not in {"short_control", "bounded_live_checkpoint_canary"}
        or cfg.get("training_allowed") is not False
        or cfg.get("maximum_decisions") != (4 if control else 128)
        or cfg.get("maximum_case_wall_seconds") != (180 if control else 360)
        or cfg.get("session_limits")
        != {
            "wall_seconds": 240 if control else 900,
            "cpu_seconds": 480 if control else 1800,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 1000000000,
        }
        or not (root / cfg["workspace"])
        .resolve()
        .is_relative_to(root / "artifacts/native-live-adapter")
        or len(cfg.get("cases", [])) != (1 if control else 4)
        or len({(c["player"], c["seed"]) for c in cfg["cases"]}) != len(cfg["cases"])
        or len({c["key"] for c in cfg["cases"]}) != len(cfg["cases"])
        or any(
            c["player"] not in (2, 3) or not c["seed"].isalnum() or not c["seed"].isupper()
            for c in cfg["cases"]
        )
    ):
        raise ValueError("Use the finite, separately pinned consolidated interface recipe")
    check_sources(root, cfg["sources"])
    expected = {name: _sha_file(root / name) for name in sorted(dependencies(root))}
    helper_names = _script_closure(
        root / "scripts", {"engine-shared-input-v2.mjs", "engine-live-checkpoint-v2.mjs"}
    )
    helpers = {
        f"scripts/{name}": _sha_file(root / "scripts" / name) for name in sorted(helper_names)
    }
    if cfg["implementation_sha256"] != expected or cfg["helpers_sha256"] != helpers:
        raise ValueError("Consolidated interface implementation/helper membership changed")
    check_sources(root, cfg["entry_sha256"])
    if any(
        cfg["sources"].get(name) != value
        for name, value in {**expected, **helpers, **cfg["entry_sha256"]}.items()
    ):
        raise ValueError("Full live source inventory omitted an execution dependency")
    ctx = previous(root, root / cfg["parent_live_recipe"])
    if (
        cfg["players"] != ctx["config"]["players"]
        or cfg["protected_originals"] != ctx["config"]["protected_originals"]
    ):
        raise ValueError("Keep both original complete players/Adam; no result-based replacement")
    build_config = json.loads(verified(root, cfg["build_config"]).read_text())
    report = identified(verified(root, cfg["build_report"]))
    candidate = verify_build(root, build_config, report)
    projection = {**ctx["native"]["projection"], **cfg["projection_repair"]}
    if projection["patch_sha256"] != _sha_file(Path(projection["patch"])):
        raise ValueError("Interface projection supplement changed")
    native = copy.deepcopy(ctx["native"])
    native.update(
        candidate=Path(candidate["candidate_directory"]), build=candidate, projection=projection
    )
    native["recipe"]["input_config_id"] = manifest_identifier(
        {
            "parent": ctx["native"]["recipe"]["input_config_id"],
            "export_build": report["report_id"],
            "projection": projection,
            "scope": "consolidated_interface_diagnostic_only",
        }
    )
    env = identified(verified(root, cfg["environment"]), "manifest_id")
    if (
        env["parent_environment_id"] != ctx["environment"]["parent_environment_id"]
        or env["build_report_id"] != report["report_id"]
        or env["input_config_id"] != native["recipe"]["input_config_id"]
        or env["game_assembly_sha256"] != ctx["environment"]["game_assembly_sha256"]
        or env["helpers_sha256"] != ctx["native_helpers"]
        or env["shared_input_helpers_sha256"] != cfg["shared_input_helpers_sha256"]
    ):
        raise ValueError("Interface metadata does not bind the exact frozen game and new exports")
    if not control:
        receipt = identified(verified(root, cfg["control_receipt"]))
        if (
            receipt["status"] != "live_checkpoint_delivery_control_pass"
            or receipt["environment_id"] != env["manifest_id"]
            or receipt["implementation_id"] != manifest_identifier(cfg["implementation_sha256"])
            or receipt["helpers_id"] != manifest_identifier(cfg["helpers_sha256"])
        ):
            raise ValueError("Qualify the exact new interface tuple on a short fresh control first")
        check_sources(root, receipt["sources"])
        if {c["seed"] for c in cfg["cases"]} & set(receipt["seeds"]):
            raise ValueError("Main diagnostic worlds must differ from short controls")
    sources = {**ctx["sources"], **cfg["sources"], str(path.relative_to(root)): _sha_file(path)}
    for key in ("build_config", "build_report", "environment"):
        sources[cfg[key]["path"]] = cfg[key]["sha256"]
    ctx.update(config=cfg, native=native, environment=env, sources=sources)
    return ctx
