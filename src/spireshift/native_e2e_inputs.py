"""Pinned reconciliation and natural-ending plans; existing source tuples stay immutable."""

from __future__ import annotations

import json
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.engine_startup import _script_closure
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_inputs_v12 import canonical_seed
from spireshift.native_systematic_inputs_v1 import load as current_load


def runtime_pins(node: Path) -> dict[str, str]:
    python = Path(sys.executable).resolve()
    uv = shutil.which("uv")
    if uv is None:
        raise ValueError("The pinned local uv launcher is missing")
    uv_path = Path(uv).resolve()
    return {
        "node_path": str(node.resolve()),
        "node_sha256": _sha_file(node),
        "python_path": str(python),
        "python_sha256": _sha_file(python),
        "python_version": platform.python_version(),
        "uv_path": str(uv_path),
        "uv_sha256": _sha_file(uv_path),
        "host_system": platform.system(),
        "host_release": platform.release(),
        "host_machine": platform.machine(),
    }


def implementation(root: Path) -> dict[str, str]:
    names = {str(p.relative_to(root)) for p in (root / "src/spireshift").glob("native_e2e_*.py")}
    names.update(
        str(p.relative_to(root)) for p in (root / "tests/unit").glob("test_native_e2e*.py")
    )
    names.update(
        str(p.relative_to(root)) for p in (root / "scripts").glob("*e2e*v1*") if p.is_file()
    )
    names.update(
        f"scripts/{name}"
        for name in _script_closure(
            root / "scripts", {"engine-e2e-checkpoint-v1.mjs", "engine-shared-input-v15.mjs"}
        )
    )
    return {name: _sha_file(root / name) for name in sorted(names)}


def source_delta(root: Path, old_host: Path, new_host: Path) -> dict[str, Any]:
    def files(folder: Path) -> dict[str, str]:
        return {
            str(p.relative_to(folder)): _sha_file(p)
            for p in folder.rglob("*.cs")
            if not any(
                part in {"bin", "obj", "out", "tools", "tests", "canonical-out"}
                for part in p.relative_to(folder).parts
            )
        }

    old, new = files(old_host), files(new_host)
    changed = sorted(name for name in old.keys() | new.keys() if old.get(name) != new.get(name))
    if changed != [
        "NativeUi/NativeRelicCounterTransition.cs",
        "PlayerEnvironment/Observation/SnapshotBuilder.cs",
    ]:
        raise ValueError("Unexpected production Connector change; do not inherit old coverage")
    baseline = (
        (root / "scripts/engine-input-layout-v11.mjs")
        .read_text()
        .replace("typed_official_public_layout_v11", "typed_official_public_layout_v12")
    )
    layout = (root / "scripts/engine-input-layout-v12.mjs").read_text()
    start = layout.index('  if(surface.kind === "rest_site") {')
    end = layout.index('  if(current?.kind==="event"', start)
    if layout[:start] + layout[end:] != baseline:
        raise ValueError("Layout changed outside the declared rest mapping")
    old_converter = (root / "scripts/engine-shared-input-v14.mjs").read_text()
    if (root / "scripts/engine-shared-input-v15.mjs").read_text() != old_converter.replace(
        "./engine-input-layout-v11.mjs", "./engine-input-layout-v12.mjs"
    ):
        raise ValueError("Shared converter changed outside its versioned layout import")
    return {
        "changed_production_files": changed,
        "unchanged_production_files": sum(old.get(n) == h for n, h in new.items()),
        "old_production_sha256": old,
        "new_production_sha256": new,
        "layout_changes_outside_rest": False,
        "converter_changes_outside_layout_import": False,
        "historical_live_effects_relabelled_as_current": False,
    }


def load(root: Path, recipe: Path) -> dict[str, Any]:
    cfg = json.loads(recipe.read_text())
    if (
        cfg.get("schema_version") != "native-e2e-qualification-config-v1"
        or cfg.get("stage") not in {"saved_reconciliation", "natural_ending_panel"}
        or cfg.get("training_allowed") is not False
        or cfg.get("maximum_decisions") != 384
        or cfg.get("whole_run_cpu_seconds") != 128
        or cfg.get("maximum_pair_wall_seconds") != 600
        or cfg.get("implementation") != implementation(root)
    ):
        raise ValueError("Use the finite source-pinned natural-ending qualification plan")
    expected_limits = {
        "wall_seconds": 240 if cfg["stage"] == "saved_reconciliation" else 2400,
        "cpu_seconds": 480 if cfg["stage"] == "saved_reconciliation" else 7200,
        "resident_memory_bytes": 4000000000,
        "storage_bytes": 1000000000 if cfg["stage"] == "saved_reconciliation" else 4000000000,
    }
    if cfg.get("resource_limits") != expected_limits:
        raise ValueError("Keep the explicit saved/live resource limits")
    workspace = (root / cfg["workspace"]).resolve()
    if not workspace.is_relative_to(root / "artifacts/native-e2e-qualification"):
        raise ValueError("Keep the separate immutable end-to-end workspace")
    check_sources(root, cfg["sources"])
    if runtime_pins(Path(cfg["node"])) != cfg["runtime_pins"]:
        raise ValueError("Pinned runtime/host changed; do not silently migrate this workflow")
    ctx = current_load(root, verified(root, cfg["systematic_recipe"]))
    if cfg["players"] != ctx["config"]["players"] or cfg["node"] != ctx["config"]["node"]:
        raise ValueError("Keep both original players and their entire Adam states")
    if len(cfg["historical_units"]) != 4 or {u["kind"] for u in cfg["historical_units"]} != {
        "reward_glyphs",
        "status_titles",
        "modified_deck",
        "selector_belt",
    }:
        raise ValueError("Keep the four declared passing historical controls")
    report = identified(verified(root, cfg["systematic_result"]))
    if (
        report["status"] != "saved_owner_panel_verified"
        or report["environment_id"] != ctx["environment"]["manifest_id"]
    ):
        raise ValueError("Require the completed scoped systematic comparison")
    check_sources(root, report["sources"])
    check_sources(root, report["evidence"])
    delta = source_delta(root, root / cfg["old_host_source"], root / cfg["current_host_source"])
    if delta != cfg["expected_source_delta"]:
        raise ValueError("Connector source-equivalence evidence changed")
    prior = set(
        json.loads(verified(root, cfg["seed_history"]).read_text())["canonical_prior_seeds"]
    )
    cases = cfg["cases"]
    if cfg["stage"] == "natural_ending_panel":
        if len(cases) != 2 or {c["player"] for c in cases} != {2, 3}:
            raise ValueError("Require one natural pair per original player")
        if len({c["key"] for c in cases}) != 2 or len({c["seed"] for c in cases}) != 2:
            raise ValueError("Distinct prospectively declared cases are required")
        for case in cases:
            if canonical_seed(case["seed"]) in prior:
                raise ValueError("No completed or uncertain historical seed may be replayed")
    elif cases:
        raise ValueError("Saved reconciliation cannot start cases")
    ctx.update(
        config=cfg,
        sources={
            **ctx["sources"],
            **cfg["sources"],
            str(recipe.relative_to(root)): _sha_file(recipe),
        },
    )
    return ctx
