"""Frozen event/counter facts and exact native shop task completion qualification."""

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
from spireshift.native_action_lifecycle_inputs import load as parent_load
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_inputs_v12 import canonical_seed

MODULES = (
    "native_shop_inputs",
    "native_shop_endings",
    "native_shop_ending_session",
    "native_shop_verification",
    "native_shop_live",
    "native_shop_session",
    "native_shop_control_verification",
    "engine_shop_fixture_worker",
)
ENTRIES = {
    "engine-shop-checkpoint-v1.mjs",
    "engine-shop-official-v1.mjs",
    "engine-shop-fixture-worker-v1.mjs",
    "engine-shop-task-verify-v1.mjs",
    "engine-shop-task-proof-v1.test.mjs",
}
CHANGED = [
    "HostControl/ConnectorMod.HostControl.cs",
    "LiveHost/EventOptionSurfaceReader.cs",
    "LiveHost/PersistentVisibleStateReader.cs",
    "LiveHost/ShopSurfaceReaders.cs",
    "LiveHost/VisibleEntityFacts.cs",
    "NativeUi/NativeShopTaskTransition.cs",
    "PlayerEnvironment/Observation/SnapshotBuilder.cs",
]


def implementation(root: Path) -> dict[str, str]:
    names = {f"src/spireshift/{n}.py" for n in MODULES}
    names.update(f"scripts/{n}" for n in _script_closure(root / "scripts", ENTRIES))
    names.update(
        {
            "tests/unit/test_native_shop_readiness.py",
            "scripts/compare-shop-endings-v1.sh",
            "backend-patches/shop-readiness-v1/Probe.cs",
            "backend-patches/shop-readiness-v1/Probe.csproj",
        }
    )
    return {n: _sha_file(root / n) for n in sorted(names)}


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
    if changed != CHANGED:
        raise ValueError("Changes exceed the declared event/counter/shop-task repair")
    return {
        "connector_changed_production_files": changed,
        "connector_old_sources": before,
        "connector_new_sources": after,
        "connector_unchanged_production_files": sum(before.get(n) == h for n, h in after.items()),
        "CLI56_worker24_converter16_layout12_unchanged": True,
        "original_game_and_rules_unchanged": True,
        "potion_repair_source_unchanged": True,
        "native_wrapper_tasks_retained_without_replacement": True,
        "task_owned_overlay_identity_is_diagnostic_only": True,
    }


def load(root: Path, recipe: Path) -> dict[str, Any]:
    cfg = json.loads(recipe.read_text())
    short = cfg.get("stage") != "natural_ending_panel"
    if (
        cfg.get("schema_version") != "native-shop-readiness-config-v1"
        or cfg.get("stage") not in {"source_saved_checks", "short_controls", "natural_ending_panel"}
        or cfg.get("training_allowed") is not False
        or cfg.get("automatic_follow_up") is not False
        or cfg.get("whole_run_cpu_seconds") != 128
        or cfg.get("maximum_decisions") != (4 if short else 384)
        or cfg.get("maximum_pair_wall_seconds") != (150 if short else 600)
        or cfg.get("implementation") != implementation(root)
    ):
        raise ValueError("Require the exact frozen shop repair and finite diagnostic plan")
    if cfg.get("resource_limits") != {
        "wall_seconds": 290 if short else 2400,
        "cpu_seconds": 900 if short else 7200,
        "resident_memory_bytes": 4000000000,
        "storage_bytes": 4000000000,
    }:
        raise ValueError("Keep fixed gameplay budgets and explicit short/owner resource limits")
    if (
        not (root / cfg["workspace"])
        .resolve()
        .is_relative_to(root / "artifacts/native-shop-readiness")
    ):
        raise ValueError("Use a separate immutable shop-repair workspace")
    check_sources(root, cfg["sources"])
    check_sources(root, json.loads(verified(root, cfg["protection"]).read_text()))
    ctx = copy.deepcopy(parent_load(root, verified(root, cfg["parent_recipe"])))
    if cfg["players"] != ctx["config"]["players"] or cfg["node"] != ctx["config"]["node"]:
        raise ValueError("Preserve both original players, complete Adam and pinned runtime")
    connector = load_connector_qualification_config(
        verified(root, cfg["connector"]), ctx["qualification"]
    )
    _verify_toolchain(connector)
    build = _hashed(root / connector.document["local_build"]["build_report"])
    if source_delta(root, ctx, Path(build["artifact"]).parent.parent) != cfg["source_delta"]:
        raise ValueError("Connector source delta changed")
    env = identified(verified(root, cfg["environment"]), "manifest_id")
    expected = copy.deepcopy(ctx["environment"])
    expected.pop("manifest_id")
    expected.update(
        compatibility_parent_environment_id=ctx["environment"]["manifest_id"],
        official_connector_config_id=connector.config_id,
        event_option_enablement_contract="native_button_enabled_and_unlocked_v1",
        relic_counter_visibility_contract="actual_inventory_renderer_not_merchant_icon_v1",
        shop_completion_contract="retained_native_wrapper_task_with_causal_overlay_ownership_v1",
    )
    if {k: v for k, v in env.items() if k != "manifest_id"} != expected:
        raise ValueError("Only the declared Connector facts and shop completion may change")
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
            witness["status"] != "shop_readiness_short_controls_qualified"
            or witness["environment_id"] != env["manifest_id"]
        ):
            raise ValueError("Require saved/source and fresh focused shop-task qualification first")
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
