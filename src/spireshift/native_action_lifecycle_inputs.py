"""Frozen action-lifecycle audit and potion completion qualification."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from spireshift.engine_connector import _verify_toolchain, load_connector_qualification_config
from spireshift.engine_journey_verification import _hashed
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.engine_startup import _script_closure
from spireshift.engine_worker import worker_helpers
from spireshift.native_chest_inputs import SCRIPT
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_entry_text_inputs import load as parent_load
from spireshift.native_flow_inputs_v12 import canonical_seed

MODULES = (
    "native_action_lifecycle_inputs",
    "native_action_lifecycle_audit",
    "native_action_lifecycle_live",
    "native_action_lifecycle_session",
    "native_action_lifecycle_verification",
    "native_action_lifecycle_verification_v2",
    "native_action_lifecycle_endings",
    "native_action_lifecycle_ending_session",
    "engine_lifecycle_fixture_worker",
)
ENTRIES = {
    "engine-lifecycle-fixture-worker-v1.mjs",
    "engine-lifecycle-official-v1.mjs",
    "engine-lifecycle-checkpoint-v1.mjs",
    "engine-potion-lifecycle-proof-v1.test.mjs",
}


def implementation(root: Path) -> dict[str, str]:
    names = {f"src/spireshift/{name}.py" for name in MODULES}
    names.update(f"scripts/{name}" for name in _script_closure(root / "scripts", ENTRIES))
    names.update(
        {
            "backend-patches/action-lifecycle-v1/Inventory.csproj",
            "backend-patches/action-lifecycle-v1/Inventory.cs",
            "tests/unit/test_native_action_lifecycles.py",
            "scripts/compare-action-lifecycle-endings-v1.sh",
        }
    )
    return {name: _sha_file(root / name) for name in sorted(names)}


def source_delta(root: Path, ctx: dict[str, Any], host: Path) -> dict[str, Any]:
    def production(folder: Path) -> dict[str, str]:
        return {
            str(p.relative_to(folder)): _sha_file(p)
            for p in folder.rglob("*.cs")
            if not set(p.relative_to(folder).parts) & {"bin", "obj", "out", "tests", "tools"}
        }

    old = _hashed(root / ctx["connector"].document["local_build"]["build_report"])
    before, after = production(Path(old["artifact"]).parent.parent), production(host)
    changed = sorted(n for n in before.keys() | after.keys() if before.get(n) != after.get(n))
    if changed != [
        "HostControl/ConnectorMod.HostControl.cs",
        "NativeUi/NativeNonCombatPotions.cs",
        "NativeUi/NativePotionUseTransition.cs",
        "PlayerEnvironment/Observation/SnapshotBuilder.cs",
    ]:
        raise ValueError("Changes exceed declared potion lifecycle and diagnostic proof scope")
    return {
        "connector_changed_production_files": changed,
        "connector_old_sources": before,
        "connector_new_sources": after,
        "connector_unchanged_production_files": sum(before.get(n) == h for n, h in after.items()),
        "CLI56_unchanged": True,
        "worker24_unchanged": True,
        "converter16_and_layout12_unchanged": True,
        "game_rules_unchanged": True,
        "earlier_repairs_unchanged": True,
        "new_provenance_is_diagnostic_only": True,
    }


def load(root: Path, recipe: Path) -> dict[str, Any]:
    cfg = json.loads(recipe.read_text())
    stage = cfg.get("stage")
    short = stage != "natural_ending_panel"
    if (
        cfg.get("schema_version") != "native-action-lifecycle-config-v1"
        or stage not in {"source_saved_checks", "short_controls", "natural_ending_panel"}
        or cfg.get("training_allowed") is not False
        or cfg.get("automatic_follow_up") is not False
        or cfg.get("whole_run_cpu_seconds") != 128
        or cfg.get("maximum_decisions") != (8 if short else 384)
        or cfg.get("maximum_pair_wall_seconds") != (150 if short else 600)
        or cfg.get("implementation") != implementation(root)
    ):
        raise ValueError("Require pinned source/saved lifecycle or finite fresh-pair plan")
    if cfg.get("resource_limits") != {
        "wall_seconds": 290 if short else 2400,
        "cpu_seconds": 900 if short else 7200,
        "resident_memory_bytes": 4000000000,
        "storage_bytes": 4000000000,
    }:
        raise ValueError("Keep explicit short/owner limits and fixed original gameplay budget")
    if (
        not (root / cfg["workspace"])
        .resolve()
        .is_relative_to(root / "artifacts/native-action-lifecycles")
    ):
        raise ValueError("Use a separate immutable lifecycle workspace")
    check_sources(root, cfg["sources"])
    check_sources(root, json.loads(verified(root, cfg["protection"]).read_text()))
    ctx = copy.deepcopy(parent_load(root, verified(root, cfg["parent_recipe"])))
    if cfg["players"] != ctx["config"]["players"] or cfg["node"] != ctx["config"]["node"]:
        raise ValueError("Keep original players, complete Adam and pinned runtime")
    connector = load_connector_qualification_config(
        verified(root, cfg["connector"]), ctx["qualification"]
    )
    _verify_toolchain(connector)
    report = _hashed(root / connector.document["local_build"]["build_report"])
    if source_delta(root, ctx, Path(report["artifact"]).parent.parent) != cfg["source_delta"]:
        raise ValueError("Source delta changed; inherited coverage is invalid")
    env = identified(verified(root, cfg["environment"]), "manifest_id")
    expected = copy.deepcopy(ctx["environment"])
    expected.pop("manifest_id")
    expected.update(
        compatibility_parent_environment_id=ctx["environment"]["manifest_id"],
        official_connector_config_id=connector.config_id,
        potion_completion_contract="exact_native_action_and_terminal_task_with_owned_choice_v1",
    )
    if {k: v for k, v in env.items() if k != "manifest_id"} != expected:
        raise ValueError("Only official potion lifecycle identity may change in environment46")
    helpers = worker_helpers(root, SCRIPT)
    if helpers != ctx["native_helpers"]:
        raise ValueError("Ordinary native execution changed")
    history = set(
        json.loads(verified(root, cfg["seed_history"]).read_text())["canonical_prior_seeds"]
    )
    if (
        len(cfg["cases"]) != 2
        or len({c["seed"] for c in cfg["cases"]}) != 2
        or any(canonical_seed(c["seed"]) in history for c in cfg["cases"])
    ):
        raise ValueError("Require two fresh declared worlds; no historical action retry")
    if not short:
        witness = identified(verified(root, cfg["short_qualification"]))
        if (
            witness["status"] != "potion_lifecycle_short_controls_qualified"
            or witness["environment_id"] != env["manifest_id"]
        ):
            raise ValueError("Require the saved and fresh focused qualification before owner runs")
        check_sources(root, witness["sources"])
        check_sources(root, witness["evidence"])
    ctx.update(
        config=cfg,
        connector=connector,
        environment=env,
        sources={
            **ctx["sources"],
            **cfg["sources"],
            str(recipe.relative_to(root)): _sha_file(recipe),
        },
    )
    return ctx
