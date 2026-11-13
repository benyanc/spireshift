"""Fit two matched A8 copies with the same whole-run anchor and different room data."""

from __future__ import annotations

import math
import random
import time
from collections.abc import Iterator, Sequence
from dataclasses import replace
from pathlib import Path
from statistics import fmean, pstdev
from typing import Any, cast

from spireshift.native_a8_mix_data import RoomPool, normal_runs, prepared_runs, room_pool
from spireshift.native_a8_own_ppo import Decision, loss_gradient
from spireshift.native_a8_own_training import State, save_checkpoint
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import ChunkJournal

ARMS = ("original", "normal", "mixed")
FITTED = ARMS[1:]
AUXILIARY_WEIGHT = 0.5
AUXILIARY_BATCH = 32
PRACTICE_PER_BATCH = AUXILIARY_BATCH // 2


def batches(rows: Sequence[Decision], size: int) -> Iterator[Sequence[Decision]]:
    return (rows[i : i + size] for i in range(0, len(rows), size))


def balanced_draws(pool: RoomPool, count: int, seed: int) -> list[Decision]:
    rng = random.Random(seed)
    worlds = list(pool.worlds.values())
    if not worlds or count < 1:
        raise ValueError("Require at least one eligible world and draw")
    result: list[Decision] = []
    # Cycle complete shuffled worlds and then choose a room and a decision.
    while len(result) < count:
        rng.shuffle(worlds)
        for rooms in worlds[: count - len(result)]:
            result.append(rng.choice(rng.choice(rooms)))
    return result


def behavior_kl(
    model: CachedContextModel, rows: Sequence[Decision], settings: dict[str, Any]
) -> float:
    return math.fsum(
        len(block) * loss_gradient(model, block, settings)[2]["approximate_joint_kl"]
        for block in batches(rows, settings["minibatch_decisions"])
    ) / len(rows)


def step(
    state: State,
    anchor: Sequence[Decision],
    auxiliary: list[Decision],
    settings: dict[str, Any],
    aux_settings: dict[str, Any],
) -> tuple[State, float]:
    model, adam, predecessor = state
    _, full_gradient, _ = loss_gradient(model, anchor, settings)
    _, room_gradient, _ = loss_gradient(model, auxiliary, aux_settings)
    updated, continued, norm = adam.update(
        cast(Any, model),
        [a + AUXILIARY_WEIGHT * b for a, b in zip(full_gradient, room_gradient, strict=True)],
        actor_rate=settings["actor_learning_rate"],
        value_rate=settings["value_learning_rate"],
        maximum_norm=settings["gradient_clip"],
    )
    if not isinstance(updated, CachedContextModel):
        raise ValueError("Mixed fitting must retain the full public actor and critic")
    return (updated, continued, predecessor), norm


def fit(
    root: Path,
    source: ChunkJournal,
    report: dict[str, Any],
    bank: dict[str, Any],
    ctx: dict[str, Any],
    player: int,
    original: State,
    target: Path,
    deadline: float,
    epochs: int,
) -> dict[str, Any]:
    normal, normal_data, proof = normal_runs(source, report, ctx["score"], player, original)
    practice_data = prepared_runs(root, bank, original[0], ctx["score"], player)
    normal_pool, practice_pool = room_pool(normal_data), room_pool(practice_data)
    if set(normal_pool.act_counts) != {1} or set(practice_pool.act_counts) != {1, 2, 3}:
        raise ValueError("The prepared room feedback must add verified later-act decisions")
    center, scale = fmean(d.advantage for d in normal), pstdev(d.advantage for d in normal)
    if scale <= 1e-8:
        raise ValueError("The common full-run actor credit needs variation")
    anchor = [replace(d, advantage=(d.advantage - center) / scale) for d in normal]
    settings = source.recipe["settings"]
    aux = {**settings, "entropy_coefficient": 0.0, "value_coefficient": 0.0}
    pool_rows = {
        name: [d for rooms in pool.worlds.values() for rows in rooms for d in rows]
        for name, pool in (("normal", normal_pool), ("prepared", practice_pool))
    }
    behavior = {
        name: behavior_kl(original[0], rows, aux)
        for name, rows in {"anchor": anchor, **pool_rows}.items()
    }
    if any(value > 1e-12 for value in behavior.values()):
        raise ValueError("An admitted sample does not match the original behavior policy")
    anchor_size = settings["minibatch_decisions"]
    per_epoch = math.ceil(len(anchor) / anchor_size)
    seed = 94000 + 100 * player
    rng = random.Random(seed)
    fitted = dict.fromkeys(FITTED, original)
    diagnostics = []
    largest_norm = dict.fromkeys(FITTED, 0.0)
    for epoch in range(epochs):
        rng.shuffle(anchor)
        base = balanced_draws(normal_pool, per_epoch * AUXILIARY_BATCH, seed + 2 * epoch + 1)
        practice = balanced_draws(
            practice_pool, per_epoch * PRACTICE_PER_BATCH, seed + 2 * epoch + 2
        )
        for common, left, right in zip(
            batches(anchor, anchor_size),
            batches(base, AUXILIARY_BATCH),
            batches(practice, PRACTICE_PER_BATCH),
            strict=True,
        ):
            if time.monotonic() >= deadline:
                raise TimeoutError("Fitting reached its short-check deadline")
            for name, batch in (
                ("normal", list(left)),
                ("mixed", [*left[:PRACTICE_PER_BATCH], *right]),
            ):
                fitted[name], norm = step(fitted[name], common, batch, settings, aux)
                largest_norm[name] = max(largest_norm[name], norm)
        epoch_kl = {
            arm: {
                name: behavior_kl(fitted[arm][0], rows, aux)
                for name, rows in {
                    "anchor": anchor,
                    "normal_room": pool_rows["normal"],
                    **({"prepared_room": pool_rows["prepared"]} if arm == "mixed" else {}),
                }.items()
            }
            for arm in FITTED
        }
        if any(
            value > settings["target_kl"] for arm in epoch_kl.values() for value in arm.values()
        ):
            raise ValueError(
                f"Matched fitting exceeded its policy-change guard at epoch {epoch + 1}: {epoch_kl}"
            )
        diagnostics.append(epoch_kl)

    updates = per_epoch * epochs
    if (
        any(state[1].steps - original[1].steps != updates for state in fitted.values())
        or any(state[0].actor.genome == original[0].actor.genome for state in fitted.values())
        or fitted["normal"][0].actor.genome == fitted["mixed"][0].actor.genome
    ):
        raise ValueError("Require two distinct actor fits with exact matched optimizer steps")
    checkpoints = {}
    for arm, state in {"original": original, **fitted}.items():
        path = target / arm
        path.mkdir()
        checkpoints[arm] = save_checkpoint(path, state)
    if checkpoints["original"]["state_id"] != original[2]:
        raise ValueError("The original reference copy changed")
    return {
        **proof,
        "player": player,
        "predecessor_state_id": original[2],
        "prepared_bank_id": bank["report_id"],
        "prepared_native_decisions": sum(len(run.rows) for run in practice_data),
        "eligible_room_decisions": {name: len(rows) for name, rows in pool_rows.items()},
        "normal_room_outcomes": normal_pool.counts,
        "prepared_room_outcomes": practice_pool.counts,
        "prepared_feedback_rooms_by_act": {str(k): v for k, v in practice_pool.act_counts.items()},
        "auxiliary_weight": AUXILIARY_WEIGHT,
        "auxiliary_batch": AUXILIARY_BATCH,
        "epochs": epochs,
        "matched_optimizer_updates_per_arm": updates,
        "prepared_draws_in_mixed_arm": updates * PRACTICE_PER_BATCH,
        "prepared_draws_in_normal_arm": 0,
        "prepared_critic_targets": 0,
        "normal_critic_targets_per_arm": len(anchor) * epochs,
        "critics_exactly_matched": fitted["normal"][0].value_weights
        == fitted["mixed"][0].value_weights,
        "checkpoints": checkpoints,
        "behavior_policy_reconstruction_kl": behavior,
        "post_epoch_kl": diagnostics,
        "maximum_gradient_norm": largest_norm,
    }
