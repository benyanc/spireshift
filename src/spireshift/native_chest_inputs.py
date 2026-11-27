"""Source-pinned chest repair on the original game and exact original players."""

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
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_e2e_inputs import load as parent_load
from spireshift.native_flow_inputs_v12 import canonical_seed, export_build

GAME = "9cb4f1ad8c9f284aa8fec3122ffd6d780bbf543d875c817abdd12ff63fbf12b4"
SCRIPT = "engine-native-worker-v24.mjs"
ENTRIES = {
    SCRIPT,
    "engine-chest-checkpoint-v1.mjs",
    "engine-chest-official-v1.mjs",
    "engine-chest-fixture-worker-v1.mjs",
    "engine-chest-verify-ending-v1.mjs",
    "engine-chest-surface-v1.test.mjs",
    "engine-chest-ending-v1.test.mjs",
    "engine-shared-input-v16.mjs",
}
MODULES = (
    "engine_chest_worker",
    "native_chest_inputs",
    "native_chest_live",
    "native_chest_worker",
    "native_chest_fixture_session",
    "native_chest_verification",
    "native_chest_endings",
    "native_chest_ending_session",
    "native_chest_ending_verification",
)


def implementation(root: Path) -> dict[str, str]:
    names = {f"scripts/{name}" for name in _script_closure(root / "scripts", ENTRIES)}
    names.update(f"src/spireshift/{name}.py" for name in MODULES)
    names.update(
        {
            "tests/unit/test_native_chest_lifecycle.py",
            "scripts/compare-chest-endings-v1.sh",
        }
    )
    return {name: _sha_file(root / name) for name in sorted(names)}


def source_delta(
    root: Path, ctx: dict[str, Any], candidate: dict[str, Any], host: Path
) -> dict[str, Any]:
    old = ctx["native"]["candidate"] / "src/Sts2Headless/RunSimulator.cs"
    new = Path(candidate["candidate_directory"]) / "src/Sts2Headless/RunSimulator.cs"
    left, right = old.read_text(), new.read_text()
    start = "    private Dictionary<string, object?> TreasureState(TreasureRoom treasureRoom)"
    end = "    private Dictionary<string, object?> GameOverState(bool isVictory)"
    if (
        left[: left.index(start)] != right[: right.index(start)]
        or left[left.index(end) :] != right[right.index(end) :]
    ):
        raise ValueError("Native changes exceed the declared chest public export")

    def native_sources(folder: Path) -> dict[str, str]:
        return {
            str(p.relative_to(folder)): _sha_file(p)
            for p in (folder / "src").rglob("*")
            if p.is_file()
            and p.suffix in {".cs", ".csproj"}
            and not set(p.relative_to(folder).parts) & {"bin", "obj"}
        }

    native_before = native_sources(ctx["native"]["candidate"])
    native_after = native_sources(Path(candidate["candidate_directory"]))
    native_changed = sorted(
        n
        for n in native_before.keys() | native_after.keys()
        if native_before.get(n) != native_after.get(n)
    )
    if native_changed != ["src/Sts2Headless/RunSimulator.cs"]:
        raise ValueError("Other native production sources changed")

    def production(folder: Path) -> dict[str, str]:
        return {
            str(p.relative_to(folder)): _sha_file(p)
            for p in folder.rglob("*.cs")
            if not set(p.relative_to(folder).parts) & {"bin", "obj", "out", "tests", "tools"}
        }

    old_host = Path(ctx["connector"].document["local_build"]["build_report"])
    old_report = _hashed(root / old_host)
    before = production(Path(old_report["artifact"]).parent.parent)
    after = production(host)
    changed = sorted(
        name for name in before.keys() | after.keys() if before.get(name) != after.get(name)
    )
    if changed != [
        "LiveHost/TreasureRoomSurfaceReader.cs",
        "NativeUi/NativeTreasureTransition.cs",
        "PlayerEnvironment/Observation/SnapshotBuilder.cs",
    ]:
        raise ValueError("Unexpected production Connector change")
    converter = (root / "scripts/engine-shared-input-v15.mjs").read_text()
    expected = (
        'import { requireChestMenu } from "./engine-chest-contract-v1.mjs";\n'
        + converter.replace(
            "export function sharedDecision(snapshot, reads, navigation = null) {",
            "export function sharedDecision(snapshot, reads, navigation = null) {\n"
            "  requireChestMenu(snapshot);",
        )
    )
    if (root / "scripts/engine-shared-input-v16.mjs").read_text() != expected:
        raise ValueError("Shared conversion changed outside the chest pre-sampling guard")
    return {
        "native_changes_outside_TreasureState": False,
        "native_old_sha256": _sha_file(old),
        "native_new_sha256": _sha_file(new),
        "native_changed_production_files": native_changed,
        "native_unchanged_production_files": sum(
            native_before.get(n) == h for n, h in native_after.items()
        ),
        "connector_changed_production_files": changed,
        "connector_unchanged_production_files": sum(before.get(n) == h for n, h in after.items()),
        "connector_old_sources": before,
        "connector_new_sources": after,
        "shared_converter_changes_outside_chest_guard": False,
        "shared_layout_unchanged": True,
    }


def input_identity(ctx: dict[str, Any], cfg: dict[str, Any], helpers: dict[str, str]) -> str:
    return manifest_identifier(
        {
            "parent": ctx["native"]["recipe"]["input_config_id"],
            "native_build": cfg["build_report"],
            "native_helpers": helpers,
            "projection": ctx["native"]["projection"],
            "treasure_contract": "stable_native_single_player_chest_lifecycle_and_hover_v1",
        }
    )


def load(root: Path, recipe: Path) -> dict[str, Any]:
    cfg = json.loads(recipe.read_text())
    stage = cfg.get("stage")
    if (
        cfg.get("schema_version") != "native-chest-lifecycle-config-v1"
        or stage not in {"short_controls", "natural_ending_panel"}
        or cfg.get("training_allowed") is not False
        or cfg.get("whole_run_cpu_seconds") != 128
        or cfg.get("maximum_pair_wall_seconds") != (120 if stage == "short_controls" else 600)
        or cfg.get("maximum_decisions") != (3 if stage == "short_controls" else 384)
        or cfg.get("implementation") != implementation(root)
    ):
        raise ValueError(
            "Require the finite, pinned chest repair plan and unchanged compute budget"
        )
    if cfg.get("resource_limits") != {
        "wall_seconds": 270 if stage == "short_controls" else 2400,
        "cpu_seconds": 900 if stage == "short_controls" else 7200,
        "resident_memory_bytes": 4000000000,
        "storage_bytes": 4000000000,
    }:
        raise ValueError("Keep the explicit short/owner resource caps")
    if (
        not (root / cfg["workspace"])
        .resolve()
        .is_relative_to(root / "artifacts/native-chest-repair")
    ):
        raise ValueError("Require a separate immutable chest workspace")
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
        or env.get("CLI_export_revision") != "v55"
        or env.get("input_layout") != "typed_official_public_layout_v12"
        or env.get("shared_input_helpers_sha256") != shared
    ):
        raise ValueError("Environment must bind exact chest execution and unchanged shared inputs")
    history = set(
        json.loads(verified(root, cfg["seed_history"]).read_text())["canonical_prior_seeds"]
    )
    cases = cfg["cases"]
    if (
        len(cases) != 2
        or len({c["key"] for c in cases}) != 2
        or len({c["seed"] for c in cases}) != 2
    ):
        raise ValueError("Require exactly two distinct prospectively declared cases")
    for case in cases:
        if canonical_seed(case["seed"]) in history:
            raise ValueError("Never replay a completed or uncertain world")
    if stage == "short_controls":
        if [c["instructions"] for c in cases] != [
            ["open_chest", "take_relic", "proceed"],
            ["open_chest", "skip_relic"],
        ] or any(c["family"] != "treasure_room" or c["room"] != "treasure" for c in cases):
            raise ValueError("Keep only the declared Take and Skip fixtures")
    elif {c["player"] for c in cases} != {2, 3}:
        raise ValueError("Require one genuine-ending pair per original player")
    if stage == "natural_ending_panel":
        witness = identified(verified(root, cfg["short_qualification"]))
        if (
            witness["status"] != "chest_short_controls_qualified"
            or witness["environment_id"] != env["manifest_id"]
        ):
            raise ValueError("Require matched short chest effects before the owner panel")
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
