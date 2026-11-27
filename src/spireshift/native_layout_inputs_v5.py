"""Separately pinned public-layout and exact-world compatibility plans; never training."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_connector import _verify_toolchain, load_connector_qualification_config
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.engine_startup import _script_closure
from spireshift.engine_worker import worker_helpers
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_interface_controls_inputs import dependencies as previous_dependencies
from spireshift.native_interface_controls_inputs import load as previous
from spireshift.native_live_inputs import prepare

__all__ = ["load", "prepare"]
NEW = (
    "native_layout_inputs",
    "native_layout_inputs_v2",
    "native_layout_inputs_v3",
    "native_layout_inputs_v4",
    "native_layout_inputs_v5",
    "native_layout_audit_v5",
    "native_official_session_v8",
    "native_live_checkpoint_v8",
    "engine_belt_worker",
    "native_layout_audit_v4",
    "native_official_session_v7",
    "native_live_checkpoint_v7",
    "native_layout_audit_v3",
    "native_official_session_v6",
    "native_live_checkpoint_v6",
    "engine_layout_worker",
    "native_layout_audit_v2",
    "native_layout_audit",
    "native_live_checkpoint_v4",
    "native_official_session_v4",
    "native_official_session_v5",
    "native_live_checkpoint_v5",
)
ENTRIES = {
    "engine-shared-input-v7.mjs",
    "engine-live-checkpoint-v8.mjs",
    "audit-input-layout-v4.mjs",
}
WRAPPERS = ("check-input-layout-v5.sh", "compare-input-layout-v5.sh")
PIN_FIELDS = (
    "artifact_sha256",
    "artifact_mvid",
    "godot_stub_sha256",
    "runtime_sts2_sha256",
    "reference_pack_id",
    "source_diff_id",
    "runtime_dependencies_id",
)


def canonical_seed(seed: Any) -> str:
    if not isinstance(seed, str) or re.fullmatch(r"[A-HJ-NP-Z0-9]{1,64}", seed) is None:
        raise ValueError("Comparison seeds must already be canonical, with no I or O")
    return seed


def dependencies(root: Path) -> set[str]:
    return previous_dependencies(root) | {f"src/spireshift/{name}.py" for name in NEW}


def export_build(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    build_cfg = json.loads(verified(root, cfg["build_config"]).read_text())
    report = identified(verified(root, cfg["build_report"]))
    if (
        build_cfg.get("schema_version") != "native-layout-export-config-v1"
        or build_cfg.get("games_allowed") is not False
        or report.get("config_id") != manifest_identifier(build_cfg)
    ):
        raise ValueError("Public-layout export build settings changed")
    check_sources(root, build_cfg["sources"])
    check_sources(root, report["sources"])
    built = report["build"]
    if built["status"] != "local_candidate_built_unqualified":
        raise ValueError("Public-layout export did not build")
    for name in ("baseline", "repaired"):
        runs = built[name]
        expected = build_cfg[f"expected_{name}"]
        if len(runs) != 2 or any(
            any(run.get(k) != expected[k] for k in PIN_FIELDS) for run in runs
        ):
            raise ValueError("Fresh export reproductions do not match their pins")
        for run in runs:
            if _sha_file(Path(run["artifact"])) != run["artifact_sha256"]:
                raise ValueError("Public-layout assembly bytes changed")
    return built["repaired"][0]  # type: ignore[no-any-return]


def load(root: Path, path: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    stage = cfg.get("stage")
    offline, control = stage == "saved_only_checks", stage == "short_control"
    if (
        cfg.get("schema_version") != "native-input-layout-config-v1"
        or stage not in {"saved_only_checks", "short_control", "bounded_live_checkpoint_canary"}
        or cfg.get("training_allowed") is not False
    ):
        raise ValueError("Use the finite versioned public-layout plan")
    if (
        cfg.get("contract") != "official_cli_shared_public_graph_v1"
        or cfg.get("input_layout") != "typed_official_public_layout_v4"
        or cfg.get("maximum_decisions") != (0 if offline else 4 if control else 128)
        or cfg.get("maximum_case_wall_seconds") != (0 if offline else 180 if control else 360)
    ):
        raise ValueError("Public-layout case limits changed")
    if cfg.get("session_limits") != {
        "wall_seconds": 240 if offline or control else 900,
        "cpu_seconds": 480 if offline or control else 1800,
        "resident_memory_bytes": 4000000000,
        "storage_bytes": 1000000000,
    } or not (root / cfg["workspace"]).resolve().is_relative_to(root / "artifacts/native-layout"):
        raise ValueError("Keep the isolated finite layout workspace and resource limits")
    if (
        len(cfg["cases"]) != (0 if offline else 1 if control else 4)
        or len({c["key"] for c in cfg["cases"]}) != len(cfg["cases"])
        or len({(c["player"], c["seed"]) for c in cfg["cases"]}) != len(cfg["cases"])
    ):
        raise ValueError("Keep the declared bounded cases")
    check_sources(root, cfg["sources"])
    expected = {name: _sha_file(root / name) for name in sorted(dependencies(root))}
    helpers = {
        f"scripts/{name}": _sha_file(root / "scripts" / name)
        for name in sorted(_script_closure(root / "scripts", ENTRIES))
    }
    helpers.update(
        {f"scripts/{k}": v for k, v in worker_helpers(root, "engine-native-worker-v13.mjs").items()}
    )
    entries = {f"scripts/{name}": _sha_file(root / "scripts" / name) for name in WRAPPERS}
    if (
        cfg["implementation_sha256"] != expected
        or cfg["helpers_sha256"] != helpers
        or cfg["entry_sha256"] != entries
        or any(cfg["sources"].get(k) != v for k, v in {**expected, **helpers, **entries}.items())
    ):
        raise ValueError("Public-layout execution source membership changed")
    ctx = previous(root, root / cfg["parent_controls_recipe"])
    if (
        cfg["node"] != ctx["config"]["node"]
        or cfg["players"] != ctx["config"]["players"]
        or cfg["protected_originals"] != ctx["config"]["protected_originals"]
    ):
        raise ValueError("Preserve both exact original players and all Adam")
    candidate = export_build(root, cfg)
    official = load_connector_qualification_config(
        verified(root, cfg["official_connector"]), ctx["qualification"]
    )
    _verify_toolchain(official)
    native_helpers = worker_helpers(root, "engine-native-worker-v13.mjs")
    native = copy.deepcopy(ctx["native"])
    native.update(candidate=Path(candidate["candidate_directory"]), build=candidate)
    native["projection"] = {**native["projection"], **cfg["projection_repair"]}
    if _sha_file(Path(native["projection"]["patch"])) != native["projection"]["patch_sha256"]:
        raise ValueError("Layout projection supplement changed")
    native["recipe"]["input_config_id"] = manifest_identifier(
        {
            "parent": ctx["native"]["recipe"]["input_config_id"],
            "export_build": cfg["build_report"]["sha256"],
            "projection": native["projection"],
            "input_layout": cfg["input_layout"],
            "native_helpers": native_helpers,
        }
    )
    env = identified(verified(root, cfg["environment"]), "manifest_id")
    shared = {
        f"scripts/{name}": _sha_file(root / "scripts" / name)
        for name in sorted(_script_closure(root / "scripts", {"engine-shared-input-v7.mjs"}))
    }
    if (
        env["parent_environment_id"] != ctx["environment"]["parent_environment_id"]
        or env["predecessor_interface_environment_id"] != ctx["environment"]["manifest_id"]
        or env["input_config_id"] != native["recipe"]["input_config_id"]
        or env["shared_input_helpers_sha256"] != shared
        or env["game_assembly_sha256"] != ctx["environment"]["game_assembly_sha256"]
        or env["helpers_sha256"] != native_helpers
        or env["official_connector_config_id"] != official.config_id
        or env["input_layout"] != cfg["input_layout"]
    ):
        raise ValueError("Public-layout environment does not bind the exact new observations")
    for case in cfg["cases"]:
        canonical_seed(case["seed"])
        if case["player"] not in (2, 3):
            raise ValueError("Use both frozen original initializers")
    used: set[str] = set()
    for ref in cfg["history_reports"]:
        historical = identified(verified(root, ref))
        used.update(
            seed.upper().replace("O", "0").replace("I", "1").strip() for seed in historical["seeds"]
        )
        check_sources(root, historical["sources"])
        check_sources(root, historical["evidence"])
    if any(c["seed"] in used for c in cfg["cases"]):
        raise ValueError("Never retry a prior world, including an O/I seed alias")
    if not offline:
        key = "offline_receipt" if control else "control_receipt"
        receipt = identified(verified(root, cfg[key]))
        if (
            receipt["status"]
            != ("saved_input_layout_pass" if control else "live_checkpoint_delivery_control_pass")
            or receipt["environment_id"] != env["manifest_id"]
            or receipt["implementation_id"] != manifest_identifier(expected)
            or receipt["helpers_id"] != manifest_identifier(helpers)
        ):
            raise ValueError("Qualify the exact layout tuple before live continuation")
        check_sources(root, receipt["sources"])
        check_sources(root, receipt["evidence"])
        if not control and {c["seed"] for c in cfg["cases"]} & set(receipt["seeds"]):
            raise ValueError("Do not reuse a short-control world")
        if not control and not receipt["full_prefix_input_equivalence"]:
            raise ValueError(
                "Resolve the short control's complete public inputs before broader validation"
            )
    sources = {**ctx["sources"], **cfg["sources"], str(path.relative_to(root)): _sha_file(path)}
    for key in ("build_config", "build_report", "environment", "official_connector"):
        sources[cfg[key]["path"]] = cfg[key]["sha256"]
    ctx.update(
        config=cfg,
        sources=sources,
        native=native,
        native_helpers=native_helpers,
        environment=env,
        connector=official,
    )
    return ctx
