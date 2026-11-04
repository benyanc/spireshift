"""Pinned native card display contexts and visible-text qualification."""

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
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_inputs_v12 import canonical_seed
from spireshift.native_shop_inputs import load as parent_load

MODULES = ("native_render_inputs", "native_render_endings")
ENTRIES = {"engine-shop-checkpoint-v1.mjs", "engine-shop-task-verify-v1.mjs"}
CHANGED = [
    "ConnectorMod.Helpers.cs",
    "LiveHost/CardRewardSurfaceReader.cs",
    "LiveHost/CombatHandCardSelectionSurfaceReader.cs",
    "LiveHost/DeckEnchantSurfaceReader.cs",
    "LiveHost/EventOptionSurfaceReader.cs",
    "LiveHost/LiveContextReader.cs",
    "LiveHost/VisibleText.cs",
    "NativeUi/NativeCombatPileSelection.cs",
    "NativeUi/NativeDeckCardSelection.cs",
    "NativeUi/NativeDeckTransformSelection.cs",
    "NativeUi/NativeDeckUpgradeSelection.cs",
    "NativeUi/NativeGeneratedCardChoice.cs",
    "NativeUi/NativeRestSite.cs",
    "NativeUi/NativeSimpleCardSelection.cs",
]


def implementation(root: Path) -> dict[str, str]:
    names = {f"src/spireshift/{n}.py" for n in MODULES}
    names.update(f"scripts/{n}" for n in _script_closure(root / "scripts", ENTRIES))
    names.update(
        {
            "src/spireshift/native_shop_ending_session.py",
            "src/spireshift/native_shop_verification.py",
            "tests/unit/test_native_rendering.py",
            "scripts/compare-render-endings-v1.sh",
            "backend-patches/card-rendering-v1/Probe.cs",
            "backend-patches/card-rendering-v1/Probe.csproj",
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
        raise ValueError(
            "Changes exceed explicit card renderer contexts and visible-text LF handling"
        )
    return {
        "connector_changed_production_files": changed,
        "connector_old_sources": before,
        "connector_new_sources": after,
        "connector_unchanged_production_files": sum(before.get(n) == h for n, h in after.items()),
        "CLI56_worker24_converter16_layout12_unchanged": True,
        "original_game_and_rules_unchanged": True,
        "potion_shop_task_and_other_readiness_repairs_unchanged": True,
        "all_card_exports_require_explicit_native_display_context": True,
        "line_break_helper_preserves_all_other_codepoints": True,
    }


def verify_plan(cfg: dict[str, Any], expected_implementation: dict[str, str]) -> None:
    natural = cfg.get("stage") == "natural_ending_panel"
    if (
        cfg.get("schema_version") != "native-render-context-config-v1"
        or cfg.get("stage") not in {"source_saved_checks", "natural_ending_panel"}
        or cfg.get("training_allowed") is not False
        or cfg.get("automatic_follow_up") is not False
        or cfg.get("whole_run_cpu_seconds") != 128
        or cfg.get("maximum_decisions") != 384
        or cfg.get("maximum_pair_wall_seconds") != 600
        or cfg.get("implementation") != expected_implementation
        or cfg.get("resource_limits")
        != {
            "wall_seconds": 2400 if natural else 290,
            "cpu_seconds": 7200 if natural else 900,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 4000000000,
        }
    ):
        raise ValueError(
            "Require the frozen renderer repair, original gameplay budget and explicit limits"
        )


def load(root: Path, recipe: Path) -> dict[str, Any]:
    cfg = json.loads(recipe.read_text())
    verify_plan(cfg, implementation(root))
    if (
        not (root / cfg["workspace"])
        .resolve()
        .is_relative_to(root / "artifacts/native-card-rendering")
    ):
        raise ValueError("Use the separate immutable rendering qualification workspace")
    check_sources(root, cfg["sources"])
    check_sources(root, json.loads(verified(root, cfg["protection"]).read_text()))
    ctx = copy.deepcopy(parent_load(root, verified(root, cfg["parent_recipe"])))
    if cfg["players"] != ctx["config"]["players"] or cfg["node"] != ctx["config"]["node"]:
        raise ValueError("Keep both full original players/Adam and pinned node runtime")
    connector = load_connector_qualification_config(
        verified(root, cfg["connector"]), ctx["qualification"]
    )
    _verify_toolchain(connector)
    build = _hashed(root / connector.document["local_build"]["build_report"])
    if source_delta(root, ctx, Path(build["artifact"]).parent.parent) != cfg["source_delta"]:
        raise ValueError("Renderer source delta changed")
    env = identified(verified(root, cfg["environment"]), "manifest_id")
    expected = copy.deepcopy(ctx["environment"])
    expected.pop("manifest_id")
    expected.update(
        compatibility_parent_environment_id=ctx["environment"]["manifest_id"],
        official_connector_config_id=connector.config_id,
        card_render_context_contract="explicit_native_widget_display_pile_no_shared_Hand_default_v1",
        visible_text_contract="native_LF_to_space_all_other_codepoints_preserved_v1",
    )
    if {k: v for k, v in env.items() if k != "manifest_id"} != expected:
        raise ValueError("Only the declared rendering identity may change")
    history = set(
        json.loads(verified(root, cfg["seed_history"]).read_text())["canonical_prior_seeds"]
    )
    if (
        len(cfg["cases"]) != 2
        or len({c["seed"] for c in cfg["cases"]}) != 2
        or any(canonical_seed(c["seed"]) in history for c in cfg["cases"])
    ):
        raise ValueError("Require two fresh declared worlds; no historical seed/action retry")
    if cfg["stage"] == "natural_ending_panel":
        report = identified(verified(root, cfg["source_qualification"]))
        if (
            report["status"] != "render_context_and_text_source_saved_qualified"
            or report["environment_id"] != env["manifest_id"]
        ):
            raise ValueError("Require exact source/saved rendering qualification first")
        check_sources(root, report["sources"])
        check_sources(root, report["evidence"])
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
