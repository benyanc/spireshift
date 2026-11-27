"""Carry native coverage forward only across the reviewed, effect-checked host delta."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import EngineQualificationConfig
from spireshift.engine_runtime_gaps import repair_inputs
from spireshift.native_context_reuse import check_sources
from spireshift.native_context_trial import launch_inputs as old_launch_inputs


def require_effects(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    recipe = json.loads((root / cfg["runtime_repair"]["path"]).read_text())
    report = identified(root / cfg["runtime_effects"]["path"])
    if (
        manifest_identifier(recipe) != cfg["runtime_repair"]["id"]
        or report["report_id"] != cfg["runtime_effects"]["id"]
        or report["config_id"] != manifest_identifier(recipe)
        or report["status"] != "scoped_native_runtime_effects_pass"
        or len(report["cases"]) != 6
        or not all(report["checks"].values())
        or report["privileged_fixture"] is not True
        or report["training_allowed"] is not False
        or [c.get("payment_option") for c in report["cases"][:4]] != [0, 0, 1, 1]
        or not all(c["native_event_finished"] for c in report["cases"][:4])
        or not all(c["native_damage_and_growth"] for c in report["cases"][4:])
    ):
        raise ValueError("Qualify both native payments/tools and repeated growing Boulder damage")
    check_sources(root, report["sources"])
    return dict(recipe)


def launch_inputs(
    q: EngineQualificationConfig, cfg: dict[str, Any], parent: dict[str, Any]
) -> dict[str, Any]:
    recipe = require_effects(q.root, cfg)
    # Keep the historical mechanics gate attached to the original host. Do not
    # relabel the old sweep as if it had run on this new candidate.
    old = old_launch_inputs(q, parent)
    if manifest_identifier(old["recipe"]) != recipe["old_run"]["id"]:
        raise ValueError("Inherited admission binds a different original host")
    new = repair_inputs(q, recipe)
    effects = identified(q.root / cfg["runtime_effects"]["path"])
    if effects["build_report_id"] != new["inputs"]["build_report_id"]:
        raise ValueError("Effects belong to another runtime repair")
    return new
