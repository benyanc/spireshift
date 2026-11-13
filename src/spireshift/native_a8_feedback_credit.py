"""Add native room outcomes to the actor credit on the same on-policy games."""

from __future__ import annotations

import statistics
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.native_a8_own_experience import groups, samples
from spireshift.native_a8_own_ppo import Decision, update
from spireshift.native_a8_own_training import State, restored, save_checkpoint
from spireshift.native_a8_rescue_game import TRACE, decisions
from spireshift.native_compatibility_contract import verified
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_value_credit import ValueRun, cross_fitted_predictions

ROOM_WEIGHT = 0.5
ARMS = ("original", "floor", "room")
Room = tuple[int, int]
Outcome = tuple[str, bool]


@dataclass
class RoomEvidence:
    decisions: list[Room | None]
    outcomes: dict[Room, Outcome]


def classify_rooms(inputs: Iterable[dict[str, Any]], ending: dict[str, Any]) -> RoomEvidence:
    """Use actual combat reward transitions and native combat deaths on the same floor."""
    locations = []
    encounters: dict[Room, str] = {}
    outcomes: dict[Room, Outcome] = {}
    ambiguous: set[Room] = set()
    active: Room | None = None
    last_combat = None
    for public in inputs:
        persistent, interaction = public["context"]["persistent"], public["context"]["interaction"]
        run = persistent["run"]
        location = (run["act"], run["floor"])
        kind = interaction["kind"]
        content = interaction["content"]["context"]
        if active is not None and active != location:
            active = None
        combat = kind == "combat_turn"
        if combat:
            encounter = content["encounter_type"]
            if location in outcomes or encounters.setdefault(location, encounter) != encounter:
                ambiguous.add(location)
            active = location
        elif (
            kind == "reward_claim"
            and active == location
            and content["reward_kind"] == "room_rewards"
            and persistent["player"]["hp"] > 0
        ):
            outcomes[location] = (encounters[location], True)
            active = None
        last_combat = location if combat else None
        locations.append(location if combat and len(public["candidates"]) > 1 else None)

    terminal = ending["public_input"]["context"]["persistent"]
    last = (terminal["run"]["act"], terminal["run"]["floor"])
    if (
        ending["terminal"]
        and ending["ending"]["victory"] is False
        and terminal["player"]["hp"] == 0
        and last_combat == last
        and last not in outcomes
    ):
        outcomes[last] = (encounters[last], False)
    return RoomEvidence(
        locations, {loc: result for loc, result in outcomes.items() if loc not in ambiguous}
    )


def room_advantages(
    evidence: Sequence[RoomEvidence],
) -> tuple[list[float | None], dict[str, dict[str, int]]]:
    """Leave the current world out of the room-success baseline."""
    counts = [Counter(item.outcomes.values()) for item in evidence]
    pooled = sum(counts, Counter())
    types = sorted({kind for kind, _ in pooled if pooled[kind, False] and pooled[kind, True]})
    auxiliary: list[float | None] = []
    for item, own in zip(evidence, counts, strict=True):
        other = pooled - own
        for loc in item.decisions:
            outcome = item.outcomes.get(loc) if loc is not None else None
            if outcome is None or outcome[0] not in types:
                auxiliary.append(None)
                continue
            kind, won = outcome
            total = other[kind, True] + other[kind, False]
            if total == 0:
                raise ValueError("Room feedback requires independent training worlds")
            auxiliary.append(won - other[kind, True] / total)
    return auxiliary, {
        kind: {"reward_reached": pooled[kind, True], "terminal_loss": pooled[kind, False]}
        for kind in types
    }


def with_room_credit(decisions: list[Decision], auxiliary: list[float | None]) -> list[Decision]:
    observed = [a for a in auxiliary if a is not None]
    if len(observed) < 2:
        raise ValueError("Require enough verified room outcomes for actor feedback")
    center, spread = statistics.fmean(observed), statistics.pstdev(observed)
    floor_std = statistics.pstdev(d.advantage for d in decisions)
    if min(spread, floor_std) <= 1e-8:
        raise ValueError("Matched feedback comparison requires varied credit")
    scale = ROOM_WEIGHT * floor_std / spread
    return [
        d if room is None else replace(d, advantage=d.advantage + scale * (room - center))
        for d, room in zip(decisions, auxiliary, strict=True)
    ]


def fit(
    source: ChunkJournal,
    report: dict[str, Any],
    ctx: dict[str, Any],
    player: int,
    target: Path,
) -> dict[str, Any]:
    def sealed(key: str, request: dict[str, Any]) -> dict[str, Any]:
        seal = source.completed(key, request)
        if seal is None or seal["report_id"] != report["seals"][key]:
            raise ValueError(f"Require exact first-round source seal for {key}")
        return seal

    key = f"initial-p{player}"
    original: State = restored(
        source, key, sealed(key, {"frozen_original": ctx["states"][f"p{player}-original"]})
    )
    model, adam, state_id = original
    recipe = source.recipe
    runs: list[ValueRun] = []
    rows: list[list[Decision]] = []
    rooms: list[RoomEvidence] = []
    source_games = []
    for task in recipe["study"]["training"]:
        if (task["partition"], task["player"], task["round"]) != ("train", player, 1):
            continue
        key = task["key"]
        seal = sealed(
            key, {"task": task, "behavior_state_id": state_id, "model_id": model.model_id}
        )
        source_games.append(seal["report_id"])
        game = seal["result"]
        directory = source.path(key)
        episode = identified(directory / "report.json")
        native = episode["native_ending"]
        identity = native["private_final_identity"]
        if (
            game != report["games"][key]
            or episode["report_id"] != game["episode_report_id"]
            or game["outcome"] != "loss"
            or episode["native_terminal"] is not True
            or native["native_ending_evidence_agrees"] is not True
            or identity["seed"] != task["seed"]
            or identity["native_game_over"] is not True
            or identity["native_victory_room"] is not False
            or identity["native_player_dead"] is not True
        ):
            raise ValueError("Training inputs must be the exact completed native training losses")
        batch, run, _ = samples(directory, game, model, ctx["score"], "train", 1)
        (ending,) = (
            frame for _, frame, delivery in decisions(directory / TRACE) if delivery is None
        )
        room = classify_rooms(
            (group[0][0]["public_input"] for group in groups(directory, model.model_id)), ending
        )
        rows.append(batch)
        runs.append(run)
        rooms.append(room)
    if len(runs) != 12 or len({run.seed for run in runs}) != len(runs):
        raise ValueError("Require all 12 original first-round training worlds for each initializer")

    key = f"fit-p{player}-r1"
    settings = recipe["settings"]
    seal = sealed(
        key,
        {"predecessor_state_id": state_id, "training_games": source_games, "settings": settings},
    )
    floor = restored(source, key, seal)
    credit = recipe["credit"]
    predictions, folds = cross_fitted_predictions(
        runs, credit["baseline"], credit["regularization"], credit["folds"], credit["fold_salt"]
    )
    if (
        folds != seal["result"]["cross_fit"]
        or seal["result"]["training_returns_by_seed_id"] != {str(r.seed): r.target for r in runs}
        or any(len(batch) != len(room.decisions) for batch, room in zip(rows, rooms, strict=True))
    ):
        raise ValueError("First-round cross-fit, targets or decision count changed")
    base = [
        replace(d, advantage=d.target - baseline)
        for run, batch in zip(runs, rows, strict=True)
        for d, baseline in zip(batch, predictions[run.seed], strict=True)
    ]
    raw_room, counts = room_advantages(rooms)
    augmented = with_room_credit(base, raw_room)
    shuffle = 80000 + 100 * player + 1
    base_model, base_adam, base_work = update(model, adam, base, settings, shuffle)
    if (
        base_model.as_dict() != floor[0].as_dict()
        or base_adam.as_dict() != floor[1].as_dict()
        or base_work != seal["result"]["work"]
    ):
        raise ValueError("The floor-only replay must reproduce the saved model and all Adam state")
    room_model, room_adam, work = update(model, adam, augmented, settings, shuffle)
    if (
        work["optimizer_steps"] != base_work["optimizer_steps"]
        or work["epochs_completed"] != base_work["epochs_completed"]
        or work["stop_reason"] != "epoch_limit"
        or room_model.model_id in {model.model_id, base_model.model_id}
    ):
        raise ValueError("The feedback arm must finish the same PPO work and change the actor")
    states = {"original": original, "floor": floor, "room": (room_model, room_adam, state_id)}
    checkpoints = {}
    for arm in ARMS:
        path = target / arm
        path.mkdir()
        checkpoints[arm] = save_checkpoint(path, states[arm])
    if (
        checkpoints["original"]["state_id"] != state_id
        or checkpoints["floor"]["state_id"] != floor[2]
    ):
        raise ValueError("Copied reference checkpoints changed")
    return {
        "player": player,
        "source_training_seals": source_games,
        "source_floor_fit_seal": seal["report_id"],
        "games": len(runs),
        "decisions": len(base),
        "room_credit_decisions": sum(value is not None for value in raw_room),
        "room_outcomes_used": counts,
        "actor_room_weight": ROOM_WEIGHT,
        "training_returns_unchanged": True,
        "floor_model_and_Adam_reproduced": True,
        "checkpoints": checkpoints,
        "floor_work": base_work,
        "room_work": work,
        "matched_optimizer_updates_per_fitted_arm": work["optimizer_steps"],
    }


def audited_source(
    root: Path, original_recipe: dict[str, Any], evidence: dict[str, Any], study_ref: dict[str, Any]
) -> tuple[ChunkJournal, dict[str, Any]]:
    source = ChunkJournal(root, original_recipe)
    audit = identified(verified(root, evidence["audit"]))
    path = verified(root, study_ref)
    report = identified(path)
    if (
        path.parent != source.workspace
        or audit["study_report_id"] != report["report_id"]
        or audit["study_report_sha256"] != study_ref["sha256"]
        or audit["native_deliveries"] != 10937
        or not all(audit["frozen_checks"].values())
        or report["config_id"] != source.config_id
        or report["status"] != "a8_model_only_training_complete"
        or report["final_test_worlds_used"]
        or report["stop"] is not None
    ):
        raise ValueError("Require the audited completed model-only training source")
    return source, report
