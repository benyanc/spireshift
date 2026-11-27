"""Frozen tutorial-entry and visible-text repairs; source/saved checks, then two worlds."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_connector import _verify_toolchain, load_connector_qualification_config
from spireshift.engine_journey_verification import _hashed
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.engine_startup import _script_closure
from spireshift.engine_worker import worker_helpers
from spireshift.native_chest_inputs import GAME, SCRIPT
from spireshift.native_chest_inputs import load as parent_load
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_inputs_v12 import canonical_seed, export_build


def implementation(root: Path) -> dict[str, str]:
    names = {
        "src/spireshift/native_entry_text_inputs.py",
        "src/spireshift/native_entry_text_audit.py",
        "src/spireshift/native_entry_text_endings.py",
        "tests/unit/test_native_entry_text.py",
        "scripts/compare-entry-text-endings-v1.sh",
        "backend-patches/tutorial-entry-text-v1/Probe.csproj",
        "backend-patches/tutorial-entry-text-v1/Program.cs",
    }
    return {name: _sha_file(root / name) for name in sorted(names)}


def source_delta(
    root: Path, ctx: dict[str, Any], candidate: dict[str, Any], host: Path
) -> dict[str, Any]:
    old = ctx["native"]["candidate"] / "src/Sts2Headless/RunSimulator.cs"
    new = Path(candidate["candidate_directory"]) / "src/Sts2Headless/RunSimulator.cs"
    left, right = old.read_text(), new.read_text()
    start = "    private static string? StripVisibleText(string? value)"
    end = "    /// <summary>Common context added to every decision point.</summary>"
    if (
        left[: left.index(start)] != right[: right.index(start)]
        or left[left.index(end) :] != right[right.index(end) :]
    ):
        raise ValueError("Native changes exceed the declared visible-text formatter")

    def sources(folder: Path, native: bool = False) -> dict[str, str]:
        return {
            str(p.relative_to(folder)): _sha_file(p)
            for p in folder.rglob("*")
            if p.is_file()
            and p.suffix in ({".cs", ".csproj"} if native else {".cs"})
            and not set(p.relative_to(folder).parts) & {"bin", "obj", "out", "tests", "tools"}
        }

    native_before = sources(ctx["native"]["candidate"] / "src", True)
    native_after = sources(Path(candidate["candidate_directory"]) / "src", True)
    native_changed = sorted(
        n
        for n in native_before.keys() | native_after.keys()
        if native_before.get(n) != native_after.get(n)
    )
    if native_changed != ["Sts2Headless/RunSimulator.cs"]:
        raise ValueError("Other native production sources changed")
    old_report = _hashed(root / ctx["connector"].document["local_build"]["build_report"])
    before = sources(Path(old_report["artifact"]).parent.parent)
    after = sources(host)
    changed = sorted(n for n in before.keys() | after.keys() if before.get(n) != after.get(n))
    if changed != [
        "LiveHost/TutorialModalSurfaceReader.cs",
        "NativeUi/NativeTutorialEntryTransition.cs",
        "PlayerEnvironment/Observation/SnapshotBuilder.cs",
    ]:
        raise ValueError("Unexpected production Connector change")
    return {
        "native_changes_outside_StripVisibleText": False,
        "native_changed_production_files": native_changed,
        "native_old_sha256": _sha_file(old),
        "native_new_sha256": _sha_file(new),
        "native_unchanged_production_files": sum(
            native_before.get(n) == h for n, h in native_after.items()
        ),
        "connector_changed_production_files": changed,
        "connector_old_sources": before,
        "connector_new_sources": after,
        "connector_unchanged_production_files": sum(before.get(n) == h for n, h in after.items()),
        "worker_unchanged": True,
        "shared_converter_unchanged": True,
        "shared_layout_unchanged": True,
        "counter_rules_unchanged": True,
        "chest_and_summary_repairs_unchanged": True,
    }


def input_identity(ctx: dict[str, Any], cfg: dict[str, Any], helpers: dict[str, str]) -> str:
    return manifest_identifier(
        {
            "parent": ctx["native"]["recipe"]["input_config_id"],
            "native_build": cfg["build_report"],
            "native_helpers": helpers,
            "projection": ctx["native"]["projection"],
            "tutorial_entry_contract": "map_ftue_native_room_entry_readiness_v1",
            "text_contract": "frozen_numeric_rainbow_parameters_preserve_glyphs_v1",
        }
    )


def load(root: Path, recipe: Path) -> dict[str, Any]:
    cfg = json.loads(recipe.read_text())
    stage = cfg.get("stage")
    saved = stage == "saved_source_checks"
    if (
        cfg.get("schema_version") != "native-entry-text-config-v1"
        or stage not in {"saved_source_checks", "natural_ending_panel"}
        or cfg.get("training_allowed") is not False
        or cfg.get("automatic_follow_up") is not False
        or cfg.get("whole_run_cpu_seconds") != 128
        or cfg.get("maximum_pair_wall_seconds") != 600
        or cfg.get("maximum_decisions") != 384
        or cfg.get("implementation") != implementation(root)
    ):
        raise ValueError("Require the finite pinned tutorial/text repair and unchanged budget")
    if cfg.get("resource_limits") != {
        "wall_seconds": 270 if saved else 2400,
        "cpu_seconds": 900 if saved else 7200,
        "resident_memory_bytes": 4000000000,
        "storage_bytes": 1000000000 if saved else 4000000000,
    }:
        raise ValueError("Keep explicit saved/owner resource caps")
    if (
        not (root / cfg["workspace"])
        .resolve()
        .is_relative_to(root / "artifacts/native-entry-text-repair")
    ):
        raise ValueError("Require a separate immutable tutorial/text workspace")
    check_sources(root, cfg["sources"])
    check_sources(root, json.loads(verified(root, cfg["protection"]).read_text()))
    ctx = copy.deepcopy(parent_load(root, verified(root, cfg["parent_recipe"])))
    if cfg["players"] != ctx["config"]["players"] or cfg["node"] != ctx["config"]["node"]:
        raise ValueError("Keep both original players, full Adam and pinned runtime")
    candidate = export_build(root, cfg)
    if candidate["runtime_sts2_sha256"] != GAME:
        raise ValueError("The original game assembly changed")
    connector = load_connector_qualification_config(
        verified(root, cfg["connector"]), ctx["qualification"]
    )
    _verify_toolchain(connector)
    host_report = _hashed(root / connector.document["local_build"]["build_report"])
    delta = source_delta(root, ctx, candidate, Path(host_report["artifact"]).parent.parent)
    if delta != cfg["source_delta"]:
        raise ValueError("Declared source delta changed; do not inherit prior coverage")
    helpers = worker_helpers(root, SCRIPT)
    input_id = input_identity(ctx, cfg, helpers)
    env = identified(verified(root, cfg["environment"]), "manifest_id")
    shared = {
        f"scripts/{name}": _sha_file(root / "scripts" / name)
        for name in _script_closure(root / "scripts", {"engine-shared-input-v16.mjs"})
    }
    if (
        env.get("compatibility_parent_environment_id") != ctx["environment"]["manifest_id"]
        or env.get("input_config_id") != input_id
        or env.get("game_assembly_sha256") != GAME
        or env.get("worker_script") != SCRIPT
        or env.get("helpers_sha256") != helpers
        or env.get("official_connector_config_id") != connector.config_id
        or env.get("CLI_export_revision") != "v56"
        or env.get("input_layout") != "typed_official_public_layout_v12"
        or env.get("shared_input_helpers_sha256") != shared
    ):
        raise ValueError("Environment must bind the exact tutorial/text implementation")
    history = set(
        json.loads(verified(root, cfg["seed_history"]).read_text())["canonical_prior_seeds"]
    )
    cases = cfg["cases"]
    if (
        len(cases) != 2
        or len({c["key"] for c in cases}) != 2
        or len({c["seed"] for c in cases}) != 2
        or {c["player"] for c in cases} != {2, 3}
        or any(canonical_seed(c["seed"]) in history for c in cases)
    ):
        raise ValueError("Require two fresh declared worlds; never replay historical failures")
    if not saved:
        witness = identified(verified(root, cfg["short_qualification"]))
        if (
            witness["status"] != "entry_text_source_saved_qualified"
            or witness["environment_id"] != env["manifest_id"]
            or witness["new_games"] != 0
        ):
            raise ValueError("Qualify source/saved regressions before the owner panel")
        check_sources(root, witness["sources"])
        check_sources(root, witness["evidence"])
    native = copy.deepcopy(ctx["native"])
    native.update(candidate=Path(candidate["candidate_directory"]), build=candidate)
    native["recipe"]["input_config_id"] = input_id
    native["inputs"]["build_report_id"] = identified(verified(root, cfg["build_report"]))[
        "report_id"
    ]
    ctx.update(
        config=cfg,
        connector=connector,
        native=native,
        native_helpers=helpers,
        environment=env,
        sources={
            **ctx["sources"],
            **cfg["sources"],
            str(recipe.relative_to(root)): _sha_file(recipe),
        },
    )
    return ctx
