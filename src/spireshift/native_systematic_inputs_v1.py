"""Exact frozen-game context for separately versioned comparison diagnostics."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from spireshift.engine_connector import _verify_toolchain, load_connector_qualification_config
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.engine_startup import _script_closure
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_inputs_v12 import load as parent_load

GAME = "9cb4f1ad8c9f284aa8fec3122ffd6d780bbf543d875c817abdd12ff63fbf12b4"
ENTRIES = {
    "engine-systematic-comparison-v1.mjs",
    "engine-systematic-official-v1.mjs",
    "engine-systematic-fixture-worker-v1.mjs",
}


def sources(root: Path) -> dict[str, str]:
    paths = {f"scripts/{name}" for name in _script_closure(root / "scripts", ENTRIES)}
    paths.update(
        str(path.relative_to(root))
        for path in (root / "src/spireshift").glob("native_systematic*_v1.py")
    )
    paths.update(
        str(path.relative_to(root))
        for path in (root / "tests/unit").glob("test_native_systematic*.py")
    )
    paths.update(
        str(path.relative_to(root))
        for path in (root / "scripts").glob("*systematic*v1*")
        if path.is_file()
    )
    return {name: _sha_file(root / name) for name in sorted(paths)}


def load(root: Path, recipe: Path) -> dict[str, Any]:
    cfg = json.loads(recipe.read_text())
    if (
        cfg.get("schema_version") != "native-systematic-comparison-config-v1"
        or cfg.get("training_allowed") is not False
        or cfg.get("game_assembly_sha256") != GAME
        or cfg.get("stage") not in {"short_checks", "owner_transition_panel"}
        or cfg.get("implementation") != sources(root)
        or cfg.get("resource_limits")
        != {
            "wall_seconds": 240 if cfg.get("stage") == "short_checks" else 1800,
            "cpu_seconds": 480 if cfg.get("stage") == "short_checks" else 3600,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 4000000000,
        }
    ):
        raise ValueError("Use the pinned systematic diagnostic and finite limits")
    workspace = (root / cfg["workspace"]).resolve()
    if not workspace.is_relative_to(root / "artifacts/native-systematic-comparison"):
        raise ValueError("Use the separate systematic evidence workspace")
    check_sources(root, cfg["sources"])
    ctx = copy.deepcopy(parent_load(root, verified(root, cfg["parent_recipe"])))
    if cfg["players"] != ctx["config"]["players"]:
        raise ValueError("Preserve both original complete players and Adam states")
    connector = load_connector_qualification_config(
        verified(root, cfg["connector"]), ctx["qualification"]
    )
    _verify_toolchain(connector)
    env = identified(verified(root, cfg["environment"]), "manifest_id")
    shared = {
        f"scripts/{name}": _sha_file(root / "scripts" / name)
        for name in _script_closure(root / "scripts", {"engine-shared-input-v15.mjs"})
    }
    if (
        env.get("compatibility_parent_environment_id") != ctx["environment"]["manifest_id"]
        or env.get("game_assembly_sha256") != GAME
        or env.get("input_config_id") != ctx["native"]["recipe"]["input_config_id"]
        or env.get("helpers_sha256") != ctx["environment"]["helpers_sha256"]
        or env.get("shared_input_helpers_sha256") != shared
        or env.get("official_connector_config_id") != connector.config_id
        or env.get("input_layout") != "typed_official_public_layout_v12"
        or env.get("CLI_export_revision") != "v54"
    ):
        raise ValueError("Keep the original game/CLI/worker and bind the repaired adapter")
    if ctx["native"]["build"]["original_sts2_sha256"] != GAME:
        raise ValueError("Frozen headless game assembly changed")
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
