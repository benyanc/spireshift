"""Freeze a mixed-origin schedule and continue the exact shared-head optimizer."""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift import native_a8_head_grid_resume as grid_resume
from spireshift import native_a8_head_policy as heads
from spireshift import native_a8_head_study as head
from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_ppo_math import Adam
from spireshift.native_a8_archive_batch import known_seeds
from spireshift.native_a8_head_training import training_examples
from spireshift.native_a8_own_ppo import Decision, update
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_practice_session import RECIPE as PRACTICE_RECIPE
from spireshift.native_a8_practice_session import TEMPLATES
from spireshift.native_compatibility_contract import verified
from spireshift.native_flow_inputs_v12 import canonical_seed
from spireshift.training_objective import TrainingScoreSpec

ROUNDS = 8
NORMAL_PER_ROUND = 8
EVALUATION_WORLDS = 32
DEFINITIONS = {2: "HIVE", 3: "GLORY"}
TERMINAL = {"win", "loss"}


def schedule(recovery: grid_resume.Recovery, control_revision: int) -> dict[str, Any]:
    base = recovery.original.source.study.base
    prior_practice = json.loads((base.root / PRACTICE_RECIPE).read_text())
    template = json.loads(verified(base.root, prior_practice["template_source"]).read_text())[
        "plan"
    ]
    profiles = {case["key"]: case for case in template["fit"]}
    bank = base.bank["entries"]
    old = {
        act: sorted(key for key, row in bank.items() if row["act"] == act and row["player"] == 2)
        for act in DEFINITIONS
    }
    if any(len(keys) != ROUNDS for keys in old.values()):
        raise ValueError("Require eight verified prepared starts in each later act")
    fresh: list[str] = []
    serial = 0

    def seed(tag: str) -> str:
        result = canonical_seed(f"SP1RESH1FTA8LS1{tag}")
        fresh.append(result)
        return result

    def world(tag: str, act: int, *, archived: str | None = None, tier: int = 0) -> dict[str, Any]:
        nonlocal serial
        serial += 1
        result: dict[str, Any] = {
            "key": tag.lower(),
            "seed_id": serial,
            "act": act,
            "archived": archived,
        }
        if archived is not None:
            result["seed"] = bank[archived]["seed"]
        elif act == 1:
            result["seed"] = seed(tag)
        else:
            definition = DEFINITIONS[act]
            source = TEMPLATES[definition][tier]
            result["case"] = {
                **profiles[source],
                "key": tag.lower(),
                "boss": None,
                "template": source,
                "partition": "later_act_setup",
                "tier": ("healthy", "lean", "preboss")[tier],
                "seed_pool": [seed(f"{tag}P{i:02d}") for i in range(1, 17)],
            }
        return result

    training = []
    for index in range(1, ROUNDS + 1):
        tag = f"T{index:02d}"
        row = [world(f"{tag}N{i:02d}", 1) for i in range(1, NORMAL_PER_ROUND + 1)]
        for act in DEFINITIONS:
            row.append(world(f"{tag}A{act}S", act, archived=old[act][index - 1]))
            row.extend(world(f"{tag}A{act}V{tier}", act, tier=tier) for tier in range(3))
        training.append(row)
    development = [world(f"E{i:03d}", 1) for i in range(1, EVALUATION_WORLDS + 1)]
    tag = f"C{control_revision:02d}"
    controls = [world(f"{tag}N{i}", 1) for i in (1, 2)]
    for act in DEFINITIONS:
        controls.extend(world(f"{tag}A{act}V{tier}", act, tier=tier) for tier in (0, 2))
    reload = world(f"{tag}R", 1)
    used = known_seeds(base) | {seed for seeds in head.world_schedule().values() for seed in seeds}
    used.update(grid_resume.CONTROL_SEEDS)
    used.update((grid_resume.PREFIX_SEED, grid_resume.REPLACEMENT))
    used.update(row["seed"] for row in base.bank["entries"].values())
    if len(set(fresh)) != len(fresh) or set(fresh) & used:
        raise ValueError("Later-act training, short controls and fresh evaluation must be disjoint")
    return {
        "training": training,
        "development": development,
        "controls": controls,
        "reload": reload,
    }


def training_task(
    world: dict[str, Any], player: int, round_index: int, seed: str, control: bool
) -> dict[str, Any]:
    return {
        "key": f"{world['key']}-p{player}",
        "seed": seed,
        "seed_id": world["seed_id"],
        "start_act": world["act"],
        "arm": "shared",
        "player": player,
        "round": round_index,
        "partition": "control" if control else "train",
    }


def fit(
    state: heads.HeadState,
    games: list[tuple[Path, dict[str, Any]]],
    score: TrainingScoreSpec,
    parent: dict[str, Any],
    player: int,
    round_index: int,
) -> tuple[heads.HeadState, dict[str, Any]]:
    if state.model.arm != "shared" or state.actor_adam.steps != state.value_adam.steps:
        raise ValueError("Require one shared actor with its exact actor and critic Adam clocks")
    if player not in PLAYERS:
        raise ValueError("Require the declared shared-head initializer")
    seed = 101_000 + player * 1000 + round_index
    batch: list[Decision] = []
    strata = {}
    normal_count = 0
    for act in (1, 2, 3):
        origin = [(path, row) for path, row in games if row["task"]["start_act"] == act]
        if any(row["task"]["player"] != player for _, row in origin):
            raise ValueError("A training game cannot cross initializers")
        counts = Counter(row["outcome"] for _, row in origin)
        eligible = [(path, row) for path, row in origin if row["outcome"] in TERMINAL]
        if len(eligible) < 2:
            raise ValueError(f"Act {act} needs at least two verified worlds for cross-fitting")
        for _, row in eligible:
            if (act != 1) != bool(row.get("setup_id")) or (
                act != 1 and row["prepared_suffix_victory"] != (row["outcome"] == "win")
            ):
                raise ValueError("A prepared outcome must keep its training-only provenance")
        samples, evidence = training_examples(eligible, state, score, parent["credit"], round_index)
        decisions = [sample.decision for sample in samples]
        # Estimate credit from all verified decisions. Limit the contribution
        # from each later act before processing the next stratum.
        if act == 1:
            normal_count = len(decisions)
        count = len(decisions) if act == 1 else min(len(decisions), normal_count // 2)
        if count < 1:
            raise ValueError("Require verified model decisions from each starting act")
        if count < len(decisions):
            decisions = random.Random(seed + act).sample(decisions, count)
        batch.extend(decisions)
        strata[str(act)] = {"outcomes": dict(counts), "selected_decisions": count, **evidence}
        del samples, decisions
    actor, value = state.actor_adam, state.value_adam
    combined = Adam(actor.steps, actor.first + value.first, actor.second + value.second)
    updated, adam, work = update(state.model, combined, batch, parent["settings"], seed)
    if not isinstance(updated, heads.HeadModel) or updated.arm != "shared":
        raise ValueError("A shared-head update must preserve the model architecture")
    size = updated.actor.parameter_count
    final = heads.HeadState(
        updated,
        Adam(adam.steps, adam.first[:size], adam.second[:size]),
        None,
        Adam(adam.steps, adam.first[size:], adam.second[size:]),
    )
    return final, {"by_start_act": strata, "training_decisions": len(batch), **work}


def schedule_id(recovery: grid_resume.Recovery, control_revision: int) -> str:
    return manifest_identifier(schedule(recovery, control_revision))
