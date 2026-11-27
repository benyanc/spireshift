"""Separate admission for full-run model-only PPO on the frozen native host."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.core.objective import ObjectiveSpec
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.engine_startup import _script_closure
from spireshift.native_a8_boss_worker import SCRIPT
from spireshift.native_a8_crash_resume import RECIPE as CRASH_RECIPE
from spireshift.native_a8_crash_resume import relocated_context
from spireshift.native_a8_ordinary_session import require_short, saved_check
from spireshift.native_a8_own_policy import CONTRACT
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_rescue_inputs import CONVERTER, GAME_LIMITS, ORDERED_PROOF
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_flow_inputs_v12 import canonical_seed
from spireshift.native_policy_updates import SETTINGS
from spireshift.native_win5_inputs import completed

RECIPE = "configs/native-learning/sts2-v0.111.0-a8-own-training-v1.json"
MODULE = "spireshift.native_a8_own_training"
WRAPPER = "scripts/train-a8-own-policy-v1.sh"
AREA = "artifacts/native-a8-own-training"
SCHEMA = "native-a8-model-only-full-run-ppo-v1"
ROUNDS = 2
TRAIN_PER_ROUND = 12
MINIMUM_COMPLETE = 8
DEVELOPMENT = [f"SP1RESH1FTA8ML1D{i:03d}" for i in range(1, 7)]
CONTROL_PREFIX_CHOICES = 6
LIMITS = {
    "wall_seconds": 5400,
    "cpu_seconds": 14400,
    "resident_memory_bytes": 4_000_000_000,
    "storage_bytes": 4_000_000_000,
}
CONTROL_LIMITS = {**LIMITS, "wall_seconds": 280, "cpu_seconds": 480}
CREDIT = {
    "baseline": "public_residual_ridge",
    "folds": 4,
    "regularization": 0.001,
    "fold_salt": "a8-full-menu-ppo-credit-v1",
}


def schedule(control: bool = False) -> dict[str, Any]:
    training = []
    width = 2 if control else TRAIN_PER_ROUND
    code = "C" if control else "T"
    for player in PLAYERS:
        for index in range(1, (1 if control else ROUNDS) + 1):
            for game in range(1, width + 1):
                slot = player * 1000 + index * 100 + game
                training.append(
                    {
                        "key": f"{code.lower()}-p{player}-r{index}-{game:02d}",
                        "seed": canonical_seed(f"SP1RESH1FTA8ML1{code}{slot}"),
                        "seed_id": slot,
                        "player": player,
                        "round": index,
                        "partition": "control" if control else "train",
                    }
                )
    return {
        "training": training,
        "reload": [f"SP1RESH1FTA8ML1R{p}" for p in PLAYERS] if control else [],
        "development": [] if control else DEVELOPMENT,
        "minimum_complete_games_per_batch": 2 if control else MINIMUM_COMPLETE,
    }


def implementation(root: Path) -> dict[str, str]:
    src = root / "src"
    pending = list((src / "spireshift").glob("native_a8_own_*.py"))
    paths = {WRAPPER, "pyproject.toml", "uv.lock", "src/spireshift/__init__.py"}
    paths.update(
        "scripts/" + name
        for name in _script_closure(root / "scripts", {SCRIPT, CONVERTER, ORDERED_PROOF})
    )
    while pending:
        path = pending.pop()
        name = path.relative_to(root).as_posix()
        if name in paths:
            continue
        paths.add(name)
        for node in ast.walk(ast.parse(path.read_text())):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                modules = [node.module, *(node.module + "." + alias.name for alias in node.names)]
            for module in modules:
                if module.startswith("spireshift."):
                    base = src.joinpath(*module.split("."))
                    for dependency in (base.with_suffix(".py"), base / "__init__.py"):
                        if dependency.is_file():
                            pending.append(dependency)
    return {name: _sha_file(root / name) for name in sorted(paths)}


def declaration(root: Path) -> dict[str, Any]:
    cfg = json.loads((root / RECIPE).read_text())
    expected = {
        "schema_version": SCHEMA,
        "workspace": f"{AREA}/study-v1",
        "control_workspace": f"{AREA}/control-v1",
        "resource_prefix": "artifacts/resources/a8-own-training-v1",
        "control_resource": "artifacts/resources/a8-own-training-control-v1.json",
        "policy_contract": CONTRACT,
        "game_limits": GAME_LIMITS,
        "session_limits": LIMITS,
        "control_limits": CONTROL_LIMITS,
        "study": schedule(),
        "control": schedule(control=True),
        "control_prefix_choices": CONTROL_PREFIX_CHOICES,
        "settings": SETTINGS,
        "credit": CREDIT,
        "implementation": implementation(root),
    }
    if any(cfg.get(key) != value for key, value in expected.items()):
        raise ValueError("Use the exact declared model-only recipe and execution sources")
    return dict(cfg)


def admitted_context(root: Path, cfg: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if cfg["crash_recipe"]["path"] != CRASH_RECIPE:
        raise ValueError("Require the verified local runtime relocation")
    crash = json.loads(verified(root, cfg["crash_recipe"]).read_text())
    check_sources(root, crash["implementation"])
    continuation = json.loads(verified(root, crash["continuation_recipe"]).read_text())
    ordinary = json.loads(verified(root, continuation["previous_recipe"]).read_text())
    ctx, runtime = relocated_context(root, ordinary, crash["node"])
    require_short(root, ctx, saved_check(root, ctx))

    own = identified(verified(root, cfg["model_only_control"]))
    workspace = (root / cfg["model_only_control"]["path"]).parent
    store = ChunkJournal(root, json.loads((workspace / "config-at-launch.json").read_text()))
    if (
        own["status"] != "own_policy_short_verified"
        or own["policy_contract"] != CONTRACT
        or own["optimizer_updates"] != 0
        or own["config_id"] != store.config_id
        or not all(own["frozen_checks"].values())
        or own["shared_profile_unchanged"] is not True
    ):
        raise ValueError("Require the exact passing full-menu native control")
    check_sources(root, store.recipe["implementation"])
    for case in store.recipe["cases"]:
        seal = store.completed(case["key"], case)
        if seal is None or seal["report_id"] != own["new_games"][case["key"]]["seal_id"]:
            raise ValueError("Missing model-only native control evidence")

    endpoint = identified(verified(root, cfg["architect"]["report"]))
    completed(root, cfg["architect"]["resource"])
    objective = ObjectiveSpec.from_mapping(ctx["native"]["objective"])
    if (
        objective != ctx["score"].evaluation_objective
        or cfg["objective"] != objective.as_dict()
        or cfg["training_score_id"] != ctx["score"].spec_id
        or objective.whole_run_budget != cfg["game_limits"]["episode_cpu_seconds"]
        or cfg["environment_id"] != ctx["environment_id"]
        or endpoint["status"] != "architect_persistence_verified"
        or endpoint["environment_id"] != ctx["environment_id"]
        or endpoint["objective"] != cfg["objective"]
        or not endpoint["checks"]
        or not all(endpoint["checks"].values())
        or endpoint["normal_start_evaluation_wins"] != 0
    ):
        raise ValueError("Require the frozen A8 objective, score and verified Architect endpoint")
    check_sources(root, endpoint["sources"])
    check_sources(root, endpoint["evidence"])

    curriculum = json.loads(verified(root, ctx["config"]["parent_recipe"]).read_text())
    history = json.loads(verified(root, curriculum["seed_history"]).read_text())
    used = set(history["canonical_prior_seeds"]) | set(ctx["paired_panel"]["worlds"])
    used.update(curriculum["plan"]["reserved_evaluation_seeds"])
    used.update(c["seed"] for c in store.recipe["cases"])
    used.add(endpoint["seed"])
    seeds = [
        *(task["seed"] for task in cfg["study"]["training"] + cfg["control"]["training"]),
        *cfg["study"]["development"],
        *cfg["control"]["reload"],
    ]
    if len(set(seeds)) != len(seeds) or used.intersection(seeds):
        raise ValueError("Training, control and development worlds must be fresh and disjoint")
    return {**ctx, "learning_config_id": manifest_identifier(cfg)}, runtime
