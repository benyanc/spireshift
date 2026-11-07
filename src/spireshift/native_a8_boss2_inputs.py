"""Version the reward-lifecycle repair without changing the capped v1 study."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.engine_worker import LIVENESS_POLICY
from spireshift.native_a8_boss2_policy import CONTRACT
from spireshift.native_a8_boss_inputs import AREA, GATE
from spireshift.native_a8_boss_inputs import RECIPE as PRIOR_RECIPE
from spireshift.native_a8_boss_inputs import declaration as prior_declaration
from spireshift.native_a8_boss_inputs import freeze as prior_freeze
from spireshift.native_a8_boss_inputs import load as prior_load
from spireshift.native_a8_boss_inputs import short_check as prior_short_check
from spireshift.native_a8_boss_worker import PROJECTION
from spireshift.native_a8_rescue_inputs import CONTROL_LIMITS, GAME_LIMITS, SESSION_LIMITS
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources

RECIPE = "configs/native-curriculum/sts2-v0.111.0-a8-act1-boss-qualification-v2.json"
WRAPPER = "scripts/qualify-act1-boss-teacher-v2.sh"
MODULE = "spireshift.native_a8_boss2_session"
CONTROL_RESOURCE = "artifacts/resources/a8-act1-boss-control-v2.json"
FAILED_ATTEMPT = f"{AREA}/study-v1/attempt-1794067461556879000.json"
FAILED_RESOURCE = "artifacts/resources/a8-act1-boss-v1-1794067461556879000.json"
CONTROL_WORLDS = [
    {"key": f"decline-probe-{i}", "player": i + 1, "seed": f"SP1RESH1FTA8BC20{i}"} for i in (1, 2)
]
CONTROL_DELIVERIES = 72


def worlds() -> list[dict[str, Any]]:
    return [
        {"key": f"boss-v2-{i:03d}", "player": 2 + (i + 1) % 2, "seed": f"SP1RESH1FTA8BR{i:03d}"}
        for i in range(1, 9)
    ]


def implementation(root: Path) -> dict[str, str]:
    paths = [
        root / WRAPPER,
        *(root / "src/spireshift").glob("native_a8_boss2_*.py"),
    ]
    return {path.relative_to(root).as_posix(): _sha_file(path) for path in sorted(paths)}


def declaration(root: Path) -> dict[str, Any]:
    cfg = json.loads((root / RECIPE).read_text())
    expected = {
        "schema_version": "native-a8-act1-boss-qualification-v2",
        "workspace": f"{AREA}/study-v2",
        "control_workspace": f"{AREA}/control-v2",
        "control_resource": CONTROL_RESOURCE,
        "game_limits": GAME_LIMITS,
        "session_limits": SESSION_LIMITS,
        "control_limits": CONTROL_LIMITS,
        "liveness_policy": LIVENESS_POLICY,
        "teacher": CONTRACT,
        "projection": PROJECTION,
        "control_worlds": CONTROL_WORLDS,
        "control_deliveries": CONTROL_DELIVERIES,
        "gate": GATE,
        "worlds": worlds(),
        "implementation": implementation(root),
    }
    if any(cfg.get(key) != value for key, value in expected.items()) or any(
        cfg[key]["path"] != path
        for key, path in (
            ("previous_recipe", PRIOR_RECIPE),
            ("previous_attempt", FAILED_ATTEMPT),
            ("previous_resource", FAILED_RESOURCE),
        )
    ):
        raise ValueError("Require the exact reward-safe qualification and execution sources")
    return dict(cfg)


def load(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    verified(root, cfg["previous_recipe"])
    previous = prior_declaration(root)
    ctx = prior_load(root, previous)
    ctx["boss_short_receipts"] = prior_short_check(root, ctx)
    attempt = identified(verified(root, cfg["previous_attempt"]))
    resource = identified(verified(root, cfg["previous_resource"]))
    old_boss = attempt["qualification"]["outcomes_by_arm"]["boss"]
    if (
        not ctx["boss_short_receipts"]
        or cfg["objective"] != previous["objective"]
        or cfg["gate"] != previous["gate"]
        or attempt["config_id"] != ctx["boss_config_id"]
        or attempt["execution_id"] != ctx["execution_id"]
        or attempt["status"] != "act1_boss_teacher_qualification_blocked"
        or old_boss != {"act1_clear": 0, "act1_loss": 1, "capped": 7}
        or attempt["lessons_admitted"] != 0
        or attempt["optimizer_updates"] != 0
        or resource["exit_code"] != 2
        or resource["cap"] is not None
    ):
        raise ValueError("The historical capped qualification or its receipts differ")
    original = ctx["config"]
    parent = json.loads(verified(root, original["parent_recipe"]).read_text())
    history = json.loads(verified(root, parent["seed_history"]).read_text())
    used = set(history["canonical_prior_seeds"]) | set(ctx["paired_panel"]["worlds"])
    used.update(parent["plan"]["reserved_evaluation_seeds"])
    used.update(
        seed for p in ("fit", "heldout") for c in parent["plan"][p] for seed in c["seed_pool"]
    )
    used.update(case["seed"] for phase in original["worlds"].values() for case in phase)
    used.update(case["seed"] for case in previous["worlds"])
    used.update((original["control"]["seed"], previous["control"]["seed"]))
    seeds = [case["seed"] for case in [*cfg["worlds"], *CONTROL_WORLDS]]
    if len(set(seeds)) != len(seeds) or used.intersection(seeds):
        raise ValueError("Use fresh disjoint qualification and diagnostic seeds")
    config_id = manifest_identifier(cfg)
    return {
        **ctx,
        "reward_config": cfg,
        "reward_config_id": config_id,
        "failed_boss_attempt": attempt,
        "execution_id": manifest_identifier(
            {
                "previous_execution_id": ctx["execution_id"],
                "reward_config_id": config_id,
                "teacher": CONTRACT,
            }
        ),
    }


def short_check(root: Path, ctx: dict[str, Any]) -> dict[str, str] | None:
    cfg = ctx["reward_config"]
    workspace, resource = root / cfg["control_workspace"], root / cfg["control_resource"]
    if not workspace.exists() and not resource.exists():
        return None
    path = workspace / "report.json"
    if not path.is_file() or not resource.is_file():
        raise ValueError("Preserve the incomplete reward lifecycle short check")
    proof, receipt = identified(path), identified(resource)
    if (
        proof["status"] != "act1_boss_reward_lifecycle_short_check_verified"
        or proof["config_id"] != ctx["reward_config_id"]
        or proof["execution_id"] != ctx["execution_id"]
        or proof["controls"] != CONTROL_WORLDS
        or proof["verified_decline_exits"] != len(CONTROL_WORLDS)
        or proof["saved"]["capped_reward_loops"] != 7
        or proof["qualification_games"] != 0
        or proof["optimizer_updates"] != 0
        or receipt["status"] != "completed"
        or receipt["exit_code"] != 0
        or receipt["cap"] is not None
        or receipt["limits"] != cfg["control_limits"]
        or receipt["command"] != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--control"]
        or receipt["artifacts"]["roots"] != [str(workspace)]
    ):
        raise ValueError("The exact reward lifecycle short check is required")
    check_sources(root, proof["evidence"])
    return {str(file.relative_to(root)): _sha_file(file) for file in (path, resource)}


def freeze(root: Path, ctx: dict[str, Any]) -> dict[str, bool]:
    cfg = ctx["reward_config"]
    if json.loads((root / RECIPE).read_text()) != cfg:
        raise ValueError("The reward-safe qualification recipe changed")
    check_sources(root, cfg["implementation"])
    for key in ("previous_recipe", "previous_attempt", "previous_resource"):
        verified(root, cfg[key])
    check_sources(root, ctx.get("reward_short_receipts", {}))
    return prior_freeze(root, ctx)
