"""Admit exact model-owned A8 trajectories and derive scoped room outcomes."""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from statistics import fmean
from typing import Any, cast

from spireshift import native_a8_practice_recovery as recovery
from spireshift import native_a8_practice_session as practice
from spireshift.engine_learning import identified
from spireshift.native_a8_feedback_credit import RoomEvidence, classify_rooms, room_advantages
from spireshift.native_a8_own_experience import groups, samples
from spireshift.native_a8_own_ppo import Decision, Factor
from spireshift.native_a8_own_training import State
from spireshift.native_a8_practice_goal import KIND, PracticeGoal
from spireshift.native_a8_rescue_game import TRACE, decisions
from spireshift.native_compact_training import PackedRow
from spireshift.native_compatibility_contract import verified
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_structured_model import encode
from spireshift.native_value_credit import ValueRun, cross_fitted_predictions
from spireshift.training_objective import TrainingScoreSpec


@dataclass
class RoomRun:
    seed: str
    rows: list[Decision]
    rooms: RoomEvidence


@dataclass
class RoomPool:
    worlds: dict[str, list[list[Decision]]]
    counts: dict[str, dict[str, int]]
    act_counts: dict[int, int]


def room_view(public: dict[str, Any]) -> dict[str, Any]:
    """Identify a combat-owned selector for credit only, without changing its model input."""
    context = public["context"]
    interaction = context["interaction"]
    if (
        interaction["kind"] in {"card_selection", "native_generated_card_choice"}
        and interaction["content"]["context"].get("kind") == "combat"
    ):
        return {
            **public,
            "context": {**context, "interaction": {**interaction, "kind": "combat_turn"}},
        }
    return public


def room_evidence(
    inputs: Iterable[dict[str, Any]], ending: dict[str, Any], size: int
) -> RoomEvidence:
    def views() -> Iterator[dict[str, Any]]:
        yield from map(room_view, inputs)
        if not ending["terminal"]:
            # A prepared goal stops on its final observed combat reward owner.
            yield ending["public_input"]

    evidence = classify_rooms(views(), ending)
    if not ending["terminal"] and evidence.decisions.pop() is not None:
        raise ValueError("A prepared endpoint must be a read-only goal observation")
    if len(evidence.decisions) != size:
        raise ValueError("Room evidence must align with delivered native decisions")
    return evidence


def normal_runs(
    source: ChunkJournal,
    report: dict[str, Any],
    score: TrainingScoreSpec,
    player: int,
    original: State,
) -> tuple[list[Decision], list[RoomRun], dict[str, Any]]:
    model, _, state_id = original
    runs: list[ValueRun] = []
    episodes = []
    seals = []
    for task in source.recipe["study"]["training"]:
        if (task["partition"], task["player"], task["round"]) != ("train", player, 1):
            continue
        key = task["key"]
        seal = source.completed(
            key, {"task": task, "behavior_state_id": state_id, "model_id": model.model_id}
        )
        if seal is None or seal["report_id"] != report["seals"][key]:
            raise ValueError("The normal source must be the original first-round behavior batch")
        game, path = seal["result"], source.path(key)
        episode = identified(path / "report.json")
        identity = episode["native_ending"]["private_final_identity"]
        if (
            game != report["games"][key]
            or episode["report_id"] != game["episode_report_id"]
            or episode["status"] != "complete"
            or episode["native_terminal"] is not True
            or episode["native_ending"]["native_ending_evidence_agrees"] is not True
            or identity["seed"] != task["seed"]
            or identity["native_game_over"] is not True
            or identity["native_victory_room"] is not False
            or game["outcome"] != "loss"
        ):
            raise ValueError("Invalid sealed normal-start training game")
        batch, run, _ = samples(path, game, model, score, "train", 1)
        (ending,) = (frame for _, frame, choice in decisions(path / TRACE) if choice is None)
        evidence = room_evidence(
            (group[0][0]["public_input"] for group in groups(path, model.model_id)),
            ending,
            len(batch),
        )
        runs.append(run)
        episodes.append(RoomRun(task["seed"], batch, evidence))
        seals.append(seal["report_id"])
    if len(runs) != 12 or len({run.seed for run in runs}) != 12:
        raise ValueError("Both fits require all twelve original first-round training games")
    credit = source.recipe["credit"]
    predictions, folds = cross_fitted_predictions(
        runs, credit["baseline"], credit["regularization"], credit["folds"], credit["fold_salt"]
    )
    saved = report["rounds"][f"fit-p{player}-r1"]
    targets = {str(run.seed): run.target for run in runs}
    if folds != saved["cross_fit"] or targets != saved["training_returns_by_seed_id"]:
        raise ValueError("The normal full-run return or cross-fitted baseline changed")
    anchor = [
        replace(row, advantage=row.target - baseline)
        for run, episode in zip(runs, episodes, strict=True)
        for row, baseline in zip(episode.rows, predictions[run.seed], strict=True)
    ]
    return (
        anchor,
        episodes,
        {
            "normal_seals": seals,
            "whole_run_training_returns": targets,
            "cross_fit_reproduced": True,
            "normal_native_decisions": len(anchor),
        },
    )


def practice_index(
    root: Path,
    old: dict[str, Any],
    ctx: dict[str, Any],
    states: dict[int, State],
    prep_id: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    bank = identified(verified(root, evidence["matched_bank_candidate"]))
    continuation = identified(verified(root, evidence["continuation"]))
    resource = identified(verified(root, evidence["continuation_resources"]))
    cfg = json.loads(verified(root, evidence["recipe"]).read_text())
    if cfg["implementation"] != recovery.implementation(root):
        raise ValueError("Practice continuation source changed")
    recovery.verify_control(root, cfg)
    original = ctx["practice_cases"]["collection"]
    previous = recovery.original_rows(root, old, cfg, original, states, prep_id)
    store = ChunkJournal(root, cfg)
    if (
        bank["status"] != "verified_candidate_for_separate_admission"
        or bank["continuation"] != evidence["continuation"]
        or bank["prepared_training_only"] is not True
        or bank["normal_start_evaluation_eligible"] is not False
        or bank["training_admission_granted"] is not False
        or bank["optimizer_updates"] != 0
        or continuation["status"] != "matched_practice_candidate_complete"
        or continuation["stop"] is not None
        or continuation["matched_candidate"]["ready_for_separate_admission"] is not True
        or resource["status"] != "completed"
        or resource["cap"] is not None
        or resource["artifacts"]["roots"] != [str(store.workspace)]
    ):
        raise ValueError("Require the independently verified paired practice candidate")
    resumed = {}
    for case in recovery.plan(original):
        key = case["key"]
        setup = store.completed(f"{key}-start", {"case": case})
        if setup is None:
            raise ValueError("Missing practice start seal")
        for player, state in states.items():
            unit = f"{key}-p{player}"
            seal = store.completed(
                unit,
                {
                    "start_seal": setup["report_id"],
                    "state_id": state[2],
                    "player": player,
                    "preparation_id": prep_id,
                },
            )
            if seal is None:
                raise ValueError("Missing practice continuation segment seal")
            resumed[unit] = {**seal["result"], "seal_id": seal["report_id"]}
    if resumed != continuation["new_segments"]:
        raise ValueError("The continuation source differs")
    retained = {key: row for key, row in previous.items() if not key.startswith("m-030-")}
    matched = {**retained, **resumed}
    if len(matched) != 64 or set(bank["entries"]) != set(matched):
        raise ValueError("The source must contain all 64 completed matched segments")
    prior = practice.journal(root, old, False)
    for key, row in matched.items():
        entry = bank["entries"][key]
        path = (prior if key in retained else store).path(key)
        if entry["source_chunk"] != path.relative_to(root).as_posix() or any(
            row[name] != value for name, value in entry.items() if name != "source_chunk"
        ):
            raise ValueError("A practice segment is outside its exact sealed training partition")
    if (
        Counter(row["outcome"] for row in matched.values()) != {"goal": 51, "loss": 13}
        or sum(row["native_decisions"] for row in matched.values()) != 3496
        or len({row["seed"] for row in matched.values()}) != 32
    ):
        raise ValueError("Verified practice bank counts changed")
    return bank


def prepared_run(
    root: Path, entry: dict[str, Any], model: CachedContextModel, score: TrainingScoreSpec
) -> RoomRun:
    path = root / entry["source_chunk"]
    episode, start = (identified(path / name) for name in ("report.json", "start.json"))
    loss = entry["outcome"] == "loss"
    if (
        episode["report_id"] != entry["episode_report_id"]
        or episode["status"] != "complete"
        or episode["optimizer_updates"] != 0
        or episode["full_run_win"] is not False
        or episode["model_id"] != model.model_id
        or episode["seed"] != entry["seed"]
        or episode["native_terminal"] is not loss
        or (loss and episode["native_ending"]["native_ending_evidence_agrees"] is not True)
        or not episode["shutdown"]["clean_exit"]
        or start["kind"] != KIND
        or start["evaluation_eligible"] is not False
        or start["scenario"]["partition"] != "practice_train"
        or start["scenario"]["goal"] != entry["goal"]
    ):
        raise ValueError("Prepared experience needs a clean model-owned training segment")
    (ending,) = (frame for _, frame, choice in decisions(path / TRACE) if choice is None)
    goal = PracticeGoal(entry["goal"], entry["act"])
    rows: list[Decision] = []

    def views() -> Iterator[dict[str, Any]]:
        for group in groups(path, model.model_id):
            factors, values = [], []
            for frame, choice in group:
                inputs, value = encode(frame["public_input"], model, score)
                packed = tuple(cast(dict[int, float], PackedRow(row)) for row in inputs)
                factors.append(Factor(packed, choice["action_index"]))
                values.append(value)
                if goal(frame, start) != (False, False):
                    raise ValueError("A practice decision crossed its declared goal boundary")
            rows.append(
                Decision(
                    tuple(factors),
                    values[0],
                    math.fsum(c["log_probability"] for _, c in group),
                    0.0,
                    0.0,
                )
            )
            yield group[0][0]["public_input"]

    evidence = room_evidence(views(), ending, entry["native_decisions"])
    if len(rows) != episode["actual_deliveries_independently_verified"] or goal(ending, start) != (
        True,
        not loss,
    ):
        raise ValueError("Prepared outcome or native delivery count differs")
    return RoomRun(entry["seed"], rows, evidence)


def prepared_runs(
    root: Path,
    bank: dict[str, Any],
    model: CachedContextModel,
    score: TrainingScoreSpec,
    player: int,
) -> list[RoomRun]:
    result = [
        prepared_run(root, entry, model, score)
        for entry in bank["entries"].values()
        if entry["player"] == player
    ]
    if len(result) != 32 or len({run.seed for run in result}) != 32:
        raise ValueError("Require the 32 matched prepared worlds for each behavior checkpoint")
    return result


def room_pool(runs: Sequence[RoomRun]) -> RoomPool:
    labels, counts = room_advantages([run.rooms for run in runs])
    offset = 0
    worlds: dict[str, dict[tuple[int, int], list[Decision]]] = {}
    act_counts: Counter[int] = Counter()
    for run in runs:
        rooms: dict[tuple[int, int], list[Decision]] = defaultdict(list)
        for row, loc, label in zip(
            run.rows, run.rooms.decisions, labels[offset : offset + len(run.rows)], strict=True
        ):
            if loc is not None and label is not None:
                rooms[loc].append(replace(row, target=0.0, advantage=label))
        offset += len(run.rows)
        if rooms:
            worlds[run.seed] = rooms
            act_counts.update(loc[0] for loc in rooms)
    if not worlds:
        raise ValueError("Require varied verified room outcomes")
    # The sampler gives every eligible world equal mass, then every room within it.
    center = fmean(fmean(rows[0].advantage for rows in rooms.values()) for rooms in worlds.values())
    scale = math.sqrt(
        fmean(
            fmean((rows[0].advantage - center) ** 2 for rows in rooms.values())
            for rooms in worlds.values()
        )
    )
    if scale <= 1e-8:
        raise ValueError("Room credit has no variation")
    return RoomPool(
        {
            seed: [
                [replace(row, advantage=(row.advantage - center) / scale) for row in rows]
                for rows in rooms.values()
            ]
            for seed, rooms in worlds.items()
        },
        counts,
        dict(act_counts),
    )
