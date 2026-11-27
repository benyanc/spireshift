from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from spireshift import native_a8_head_policy, native_a8_own_experience
from spireshift import native_a8_head_study as study
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_neural import initial_actor, initialize_native_critic
from spireshift.full_run_ppo_math import Adam
from spireshift.native_a8_head_policy import (
    ARMS,
    HeadChooser,
    HeadState,
    OwnedDecision,
    initialize,
    load,
    owned_decisions,
    save,
)
from spireshift.native_a8_head_training import gradient, matched_update, step
from spireshift.native_a8_own_ppo import Decision, Factor, loss_gradient
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_action_context import CROSSED
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_input_normalization import QUARTER
from spireshift.training_objective import TrainingScoreSpec

SETTINGS = {
    "actor_learning_rate": 0.001,
    "clip": 0.2,
    "entropy_coefficient": 0.015,
    "epochs": 2,
    "gradient_clip": 1.0,
    "minibatch_decisions": 2,
    "target_kl": 0.03,
    "temperature": 0.8,
    "value_coefficient": 0.5,
    "value_learning_rate": 0.003,
}


@pytest.fixture
def frozen() -> tuple[CachedContextModel, Adam]:
    actor = initial_actor("sha256:" + "1" * 64, 128, 4, 7, input_normalization=QUARTER)
    model = CachedContextModel(initialize_native_critic(actor), CROSSED, "sha256:" + "2" * 64)
    return model, Adam(12, (0.001,) * model.parameter_count, (0.0001,) * model.parameter_count)


def example(combat: bool, advantage: float = 1.0) -> OwnedDecision:
    factor = Factor(({1: 0.7, 5: 0.3}, {1: -0.2, 4: 0.1}), 0)
    decision = Decision((factor,), (0.1,) * 129, -math.log(2), 0.55, advantage)
    return OwnedDecision(combat, decision)


def test_both_heads_copy_the_same_actor_and_full_warm_adam(
    tmp_path: Path, frozen: tuple[CachedContextModel, Adam]
) -> None:
    model, adam = frozen
    shared = initialize(model, adam, "shared")
    split = initialize(model, adam, "split")
    assert shared.model.model_id == model.model_id
    assert split.model.model_id != shared.model.model_id
    assert split.model.actor == split.model.combat_actor == model.actor
    assert split.model.value_weights == model.value_weights
    assert split.actor_adam == split.combat_adam == shared.actor_adam
    assert (*split.actor_adam.first, *split.value_adam.first) == adam.first
    assert (*split.actor_adam.second, *split.value_adam.second) == adam.second
    assert split.value_adam.steps == adam.steps
    for arm, state in (("shared", shared), ("split", split)):
        path = tmp_path / f"{arm}.json"
        receipt = save(path, state)
        assert load(path) == (state, receipt)


def test_shared_gradient_and_optimizer_match_the_existing_learner(
    frozen: tuple[CachedContextModel, Adam],
) -> None:
    model, adam = frozen
    shared = initialize(model, adam, "shared")
    batch = [example(True), example(False, -0.4)]
    _, reference, _ = loss_gradient(model, [sample.decision for sample in batch], SETTINGS)
    grads = gradient(shared, batch, SETTINGS)
    assert grads.actor is not None
    assert (*grads.actor, *grads.value) == reference
    assert grads.combat is None
    expected, expected_adam, _ = adam.update(
        cast(Any, model),
        reference,
        actor_rate=SETTINGS["actor_learning_rate"],
        value_rate=SETTINGS["value_learning_rate"],
        maximum_norm=SETTINGS["gradient_clip"],
    )
    current = step(shared, grads, SETTINGS)
    assert current.model.weights() == pytest.approx(expected.weights(), abs=1e-13)
    assert (*current.actor_adam.first, *current.value_adam.first) == expected_adam.first
    assert (*current.actor_adam.second, *current.value_adam.second) == expected_adam.second


@pytest.mark.parametrize("combat", [True, False])
def test_split_only_updates_the_owning_head_even_with_warm_momentum(
    frozen: tuple[CachedContextModel, Adam], combat: bool
) -> None:
    split = initialize(*frozen, "split")
    updated = step(split, gradient(split, [example(combat)], SETTINGS), SETTINGS)
    assert (updated.model.actor != split.model.actor) is not combat
    assert (updated.actor_adam != split.actor_adam) is not combat
    assert (updated.model.combat_actor != split.model.combat_actor) is combat
    assert (updated.combat_adam != split.combat_adam) is combat
    assert updated.value_adam.steps == split.value_adam.steps + 1


def test_matched_optimizer_work_with_different_experience_lengths(
    frozen: tuple[CachedContextModel, Adam],
) -> None:
    states = {arm: initialize(*frozen, arm) for arm in ARMS}
    data = {
        "shared": [example(True), example(False, -1), example(True, 0.3)],
        "split": [example(True), example(False, -1)],
    }
    current, report = matched_update(states, data, SETTINGS, 9)
    assert report["selected_decisions_per_arm"] == 2
    assert report["optimizer_steps_per_arm"] > 0
    assert all(
        current[arm].value_adam.steps
        == states[arm].value_adam.steps + report["optimizer_steps_per_arm"]
        for arm in ARMS
    )


def test_combat_owned_selector_uses_combat_and_rewards_use_strategy(
    frozen: tuple[CachedContextModel, Adam],
) -> None:
    model = initialize(*frozen, "split").model
    chooser = HeadChooser(model, cast(TrainingScoreSpec, object()), "SP1RESH1FT")

    def public(kind: str, owner: str) -> dict[str, Any]:
        return {
            "context": {
                "persistent": {"run": {"act": 1, "floor": 5, "act_definition_id": "OVERGROWTH"}},
                "interaction": {
                    "kind": kind,
                    "content": {"context": {"kind": owner, "round": 1}},
                },
            },
        }

    assert chooser.combat(public("combat_turn", "combat"))
    assert chooser.combat(public("card_selection", "combat"))
    assert chooser.combat(public("card_selection", "selection"))
    assert not chooser.combat(public("reward_claim", "reward_flow"))
    assert not chooser.combat(public("card_selection", "shop"))
    assert not chooser.combat(public("map_navigation", "map"))


def test_compound_answer_rejects_a_change_of_scoring_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, frozen: tuple[CachedContextModel, Adam]
) -> None:
    model = initialize(*frozen, "split").model
    first = {"combat_owned": True, "scoring_head": "combat"}
    second = first.copy()
    monkeypatch.setattr(
        native_a8_own_experience, "groups", lambda *args: iter([[({}, first), ({}, second)]])
    )
    row = example(True)
    assert list(owned_decisions(tmp_path, model, [row.decision])) == [row]
    second.update(combat_owned=False, scoring_head="strategy")
    with pytest.raises(ValueError, match="crossed scoring heads"):
        list(owned_decisions(tmp_path, model, [row.decision]))


def test_complete_depth_plan_and_missing_games_in_denominator() -> None:
    plan = study.declaration()
    worlds = study.world_schedule()
    all_worlds = [world for partition in worlds.values() for world in partition]
    assert len(all_worlds) == len(set(all_worlds))
    assert len(worlds["train"]) == 1024
    assert len(worlds["holdout"]) == 128
    assert plan["world_schedule_id"] == manifest_identifier(worlds)
    world = worlds["holdout"][0]
    outcome = study.evaluate([world], {(world, 2, "split"): {"outcome": "failed"}})
    assert outcome["comparison"] == "inconclusive"
    assert outcome["pooled_split_minus_shared_win_rate_bounds"] == [-1.0, 1.0]
    assert outcome["by_initializer"]["2"]["arms"]["split"]["failed"] == 1
    rows = {
        (world, p, arm): {"outcome": "loss", "completed_acts": 0, "maximum_floor": 6}
        for p in PLAYERS
        for arm in ARMS
    }
    assert study.evaluate([world], rows)["comparison"] == "inconclusive"


def test_session_reuses_verified_units_and_pauses_before_a_new_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    journal = ChunkJournal(tmp_path, {"workspace": "artifacts/control"})
    fake = SimpleNamespace(
        store=lambda _: journal,
        source=SimpleNamespace(study=SimpleNamespace(base=SimpleNamespace(ctx={}))),
    )
    monkeypatch.setattr(study, "_shared_snapshot", lambda _: {})
    session = study.Session(cast(study.Study, fake), control=False, deadline=math.inf)
    with journal.lock():
        seal = session.unit("sealed", {"input": 1}, 1, lambda _: {"outcome": "verified"})
        session.deadline = -math.inf
        assert session.unit("sealed", {"input": 1}, 1, lambda _: pytest.fail("replayed")) == seal
        with pytest.raises(study.CleanPause):
            session.unit("pending", {}, 1, lambda _: pytest.fail("started"))
        assert not journal.path("pending").exists()


def test_study_resumes_rounds_and_uses_a_separate_final_panel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, frozen: tuple[CachedContextModel, Adam]
) -> None:
    journal = ChunkJournal(tmp_path, {"workspace": "artifacts/study"})
    fake = SimpleNamespace(
        root=tmp_path,
        store=lambda _: journal,
        unchanged=lambda _: None,
        source=SimpleNamespace(
            cfg={"implementation": {}},
            states={(p, "fitted"): (*frozen, f"frozen-p{p}") for p in PLAYERS},
            study=SimpleNamespace(
                base=SimpleNamespace(ctx={"score": object()}), frozen_checks={"exact": True}
            ),
        ),
        cfg={
            "game_limits": {"episode_wall_seconds": 90},
            "plan": {"minimum_paired_terminal_worlds": 2},
            "credit": {},
            "settings": SETTINGS,
            "selector_control_id": "adapter",
            "starting_states": {str(p): f"frozen-p{p}" for p in PLAYERS},
        },
    )
    attempted: dict[str, dict[str, Any]] = {}

    def play(
        ctx: dict[str, Any],
        task: dict[str, Any],
        directory: Path,
        state: HeadState,
        deadline: float,
    ) -> dict[str, Any]:
        key = task["key"]
        assert key not in attempted
        attempted[key] = task
        return {
            "task": task,
            "model_id": state.model.model_id,
            "outcome": "loss",
            "initial_public_input_id": task["seed"],
            "completed_acts": 0,
            "maximum_floor": 6,
        }

    def examples(*args: Any) -> tuple[list[OwnedDecision], dict[str, Any]]:
        return [example(True), example(False, -1)], {}

    monkeypatch.setattr(native_a8_head_policy, "play", play)
    monkeypatch.setattr(study, "training_examples", examples)
    monkeypatch.setattr(study, "_running_games", lambda: [])
    monkeypatch.setattr(study, "_shared_snapshot", lambda _: {})
    monkeypatch.setattr(study, "ROUNDS", 2)
    monkeypatch.setattr(study, "WORLDS_PER_ROUND", 2)
    monkeypatch.setattr(study, "PROGRESS_ROUNDS", (0, 1, 2))
    monkeypatch.setattr(study, "PROGRESS_WORLDS", 1)
    monkeypatch.setattr(study, "HOLDOUT_WORLDS", 2)

    first = study.Session(cast(study.Study, fake), control=False, deadline=math.inf)
    paused = first.execute(1, 1, "control")
    assert paused["status"] == "paused"
    assert paused["holdout"] is None
    assert len(attempted) == 16
    second = study.Session(cast(study.Study, fake), control=False, deadline=math.inf)
    complete = second.execute(2, 2, "control")
    assert complete["status"] == study.COMPLETE
    assert complete["verified_games"] == len(attempted) == 36
    assert set(complete["progress"]) == {"0", "1", "2"}
    assert complete["holdout"]["comparison"] == "inconclusive"
    assert all(depth["training_rounds_with_updates"] == 2 for depth in complete["depth"].values())
    worlds = study.world_schedule()
    for task in attempted.values():
        assert (task["seed"] in worlds["train"]) is (task["partition"] == "train")
        assert (task["seed"] in worlds["holdout"]) is task["key"].startswith("holdout-")
