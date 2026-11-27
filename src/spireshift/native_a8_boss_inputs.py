"""Execution manifest and frozen inputs for the separate boss qualification."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.engine_startup import _script_closure
from spireshift.native_a8_boss_policy import CONTRACT
from spireshift.native_a8_boss_worker import PROJECTION, SCRIPT
from spireshift.native_a8_rescue_inputs import (
    CONTROL_LIMITS,
    GAME_LIMITS,
    SESSION_LIMITS,
)
from spireshift.native_a8_rescue_inputs import (
    RECIPE as PRIOR_RECIPE,
)
from spireshift.native_a8_rescue_inputs import (
    declaration as prior_declaration,
)
from spireshift.native_a8_rescue_inputs import (
    freeze as prior_freeze,
)
from spireshift.native_a8_rescue_inputs import (
    load as prior_load,
)
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources

AREA = "artifacts/native-a8-act1-boss"
RECIPE = "configs/native-curriculum/sts2-v0.111.0-a8-act1-boss-qualification-v1.json"
PRIOR_RESULT = "docs/evidence/native-a8-act1-rescue-result-v1.json"
WRAPPER = "scripts/qualify-act1-boss-teacher-v1.sh"
MODULE = "spireshift.native_a8_boss_session"
REGRESSION = "engine-generated-choice-belt-regression-v1.mjs"
CONTROL_RESOURCE = "artifacts/resources/a8-act1-boss-control-v1.json"
CONTROL = {"key": "boss-control-001", "player": 2, "seed": "SP1RESH1FTA8BC001"}
CONTROL_DELIVERIES = 32
CONTROL_ARMS = ("survival", "boss")
GATE = {"minimum_confirmed_clears": 3, "strict_rescue_initializers": [2, 3]}


def worlds() -> list[dict[str, Any]]:
    return [
        {"key": f"boss-{i:03d}", "player": 2 + (i + 1) % 2, "seed": f"SP1RESH1FTA8BQ{i:03d}"}
        for i in range(1, 9)
    ]


def implementation(root: Path) -> dict[str, str]:
    names = {WRAPPER}
    names.update(
        p.relative_to(root).as_posix()
        for p in (root / "src/spireshift").glob("native_a8_boss_*.py")
    )
    names.update(
        f"scripts/{name}" for name in _script_closure(root / "scripts", {SCRIPT, REGRESSION})
    )
    return {name: _sha_file(root / name) for name in sorted(names)}


def declaration(root: Path) -> dict[str, Any]:
    cfg = json.loads((root / RECIPE).read_text())
    expected = {
        "schema_version": "native-a8-act1-boss-qualification-v1",
        "workspace": f"{AREA}/study-v1",
        "control_workspace": f"{AREA}/control-v1",
        "control_resource": CONTROL_RESOURCE,
        "game_limits": GAME_LIMITS,
        "session_limits": SESSION_LIMITS,
        "control_limits": CONTROL_LIMITS,
        "teacher": CONTRACT,
        "projection": PROJECTION,
        "control": CONTROL,
        "control_deliveries": CONTROL_DELIVERIES,
        "gate": GATE,
        "worlds": worlds(),
        "implementation": implementation(root),
    }
    if (
        any(cfg.get(name) != value for name, value in expected.items())
        or cfg["previous_recipe"]["path"] != PRIOR_RECIPE
        or cfg["previous_result"]["path"] != PRIOR_RESULT
    ):
        raise ValueError("Use the exact boss qualification recipe and execution sources")
    return dict(cfg)


def short_check(root: Path, ctx: dict[str, Any]) -> dict[str, str] | None:
    cfg = ctx["boss_config"]
    workspace, resource = root / cfg["control_workspace"], root / cfg["control_resource"]
    if not workspace.exists() and not resource.exists():
        return None
    path = workspace / "report.json"
    if not path.is_file() or not resource.is_file():
        raise ValueError("Preserve the incomplete boss short check for inspection")
    proof, receipt = identified(path), identified(resource)
    if (
        proof["status"] != "act1_boss_short_check_verified"
        or proof["config_id"] != ctx["boss_config_id"]
        or proof["execution_id"] != ctx["execution_id"]
        or proof["control_world"] != CONTROL["seed"]
        or proof["verified_deliveries"] != len(CONTROL_ARMS) * CONTROL_DELIVERIES
        or proof["optimizer_updates"] != 0
        or proof["qualification_games"] != 0
        or receipt["status"] != "completed"
        or receipt["exit_code"] != 0
        or receipt["cap"] is not None
        or receipt["limits"] != cfg["control_limits"]
        or receipt["command"] != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--control"]
        or receipt["artifacts"]["roots"] != [str(workspace)]
    ):
        raise ValueError("Require the exact passing boss short check")
    check_sources(root, proof["evidence"])
    return {str(file.relative_to(root)): _sha_file(file) for file in (path, resource)}


def load(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    verified(root, cfg["previous_recipe"])
    previous = prior_declaration(root)
    ctx = prior_load(root, previous, control=False)
    result = identified(verified(root, cfg["previous_result"]))
    audit = identified(verified(root, result["saved_audit"]))
    if (
        cfg["objective"] != previous["objective"]
        or result["config_id"] != ctx["config_id"]
        or result["environment_id"] != ctx["environment_id"]
        or not result["qualification"]["passed"]
        or result["collection"]["eligible_rescues"]
        or result["bank_id"] is not None
        or result["adapter_repair_scope"] != "saved_regression_only_separately_versioned_adapter"
        or audit["status"] != "stopped_act1_rescue_study_verified"
        or audit["owner_attempt_id"] != result["owner_attempt"]["report_id"]
    ):
        raise ValueError("Require the exact frozen Act 1 study and saved adapter repair")
    check_sources(root, result["sources"])
    check_sources(root, audit["failure"]["source_sha256"])
    parent = json.loads(verified(root, previous["parent_recipe"]).read_text())
    history = json.loads(verified(root, parent["seed_history"]).read_text())
    used = set(history["canonical_prior_seeds"]) | set(ctx["paired_panel"]["worlds"])
    used.update(parent["plan"]["reserved_evaluation_seeds"])
    used.update(
        seed for p in ("fit", "heldout") for c in parent["plan"][p] for seed in c["seed_pool"]
    )
    used.update(c["seed"] for phase in previous["worlds"].values() for c in phase)
    used.add(previous["control"]["seed"])
    seeds = [c["seed"] for c in [*cfg["worlds"], CONTROL]]
    if len(set(seeds)) != len(seeds) or used.intersection(seeds):
        raise ValueError("Use disjoint fresh qualification and short-control seeds")
    config_id = manifest_identifier(cfg)
    return {
        **ctx,
        "boss_config": cfg,
        "boss_config_id": config_id,
        "execution_id": manifest_identifier(
            {
                "frozen_build_environment_id": ctx["environment_id"],
                "boss_config_id": config_id,
                "projection": PROJECTION,
            }
        ),
        "prior_audit": audit,
    }


def freeze(root: Path, ctx: dict[str, Any]) -> dict[str, bool]:
    cfg = ctx["boss_config"]
    if json.loads((root / RECIPE).read_text()) != cfg:
        raise ValueError("The boss qualification declaration changed")
    check_sources(root, cfg["implementation"])
    verified(root, cfg["previous_recipe"])
    verified(root, cfg["previous_result"])
    check_sources(root, ctx["prior_audit"]["failure"]["source_sha256"])
    check_sources(root, ctx.get("boss_short_receipts", {}))
    return prior_freeze(root, ctx)
