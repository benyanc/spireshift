from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.core.manifest import manifest_identifier
from spireshift.core.types import DecisionType, LegalAction, Observation, Transition
from spireshift.full_run_experience import (
    PublicProgress,
    collect_episode,
    load_episode,
    save_episode,
    verify_episode_trace,
)
from spireshift.full_run_features import PHASE_NAMES, full_run_input
from spireshift.full_run_policy import (
    FullRunModel,
    FullRunPolicy,
    initial_full_run_model,
    score_features,
    score_gradient,
)
from spireshift.neural_combat_features import CARD_FLAGS
from spireshift.training_objective import TrainingScope, load_training_score_spec

RULESET = MockSpireEnvironment.ruleset
CATALOG = {
    str(i): {
        "Cost": 1,
        "BaseDamage": damage,
        "BaseBlock": block,
        "UpgradeDamage": 2,
        "UpgradeBlock": 2,
        "UpgradeCost": 0,
        "Type": "Attack" if damage else "Skill",
        "Target": "AnyEnemy" if damage else "Self",
        **{k: False for k in CARD_FLAGS},
    }
    for i, damage, block in ((17, 6, 0), (45, 0, 5))
}


def observation(phase: str, **updates: Any) -> Observation:
    state: dict[str, Any] = {
        "phase": phase,
        "floor": 1,
        "act": "overgrowth",
        "gold": 100,
        "player_hp": 60,
        "player_max_hp": 80,
        "deck_size": 2,
        "deck": [{"card_id": 17, "upgraded": False}, {"card_id": 45, "upgraded": False}],
        "potions": [47, 0, 0, 0, 0, 0],
        "relic_slots": [],
        "deck_selection": [0, 0, 0],
        "card_rewards": [17, 45, 17],
        "card_reward_upgraded": [False] * 3,
        "shop_cards": [17, 45],
        "shop_costs": [40, 50] + [0] * 12,
        "shop_relics": [5, 29, 89],
        "shop_potions": [47, 48, 49],
        "neow_options": [5, 29, 89],
        "enemy_def_ids": [11, 0, 0, 0, 0, 0],
        "pending_rewards": [20, 47, 5, 0],
        "bundle_offer": [17, 17, 17, 45, 45, 45],
        "offer_cards": [],
        "event_id": 8,
        "terminal": False,
        "victory": False,
        "observation_vector": [0] * 682,
        "map_choices": [{"node_type": 1, "x": 1, "y": 1}, {"node_type": 3, "x": 2, "y": 1}],
    }
    vector = state["observation_vector"]
    vector[276] = next(i for i, name in PHASE_NAMES.items() if name == phase)
    vector[:8] = [60, 80, 0, 3, 3, 5, 0, 0]
    vector[8:16] = [17, 0, 0, 0, 45, 0, 0, 0]
    vector[80:85] = [8, 8, 0, 0, 10]
    vector[288:290] = [1, 3]
    state.update(updates)
    kind = {
        "combat": DecisionType.COMBAT,
        "map": DecisionType.PATH,
        "rest_site": DecisionType.REST_SITE,
        "shop": DecisionType.SHOP,
        "card_selection": DecisionType.CARD_SELECTION,
        "card_reward": DecisionType.REWARD,
    }.get(phase, DecisionType.EVENT)
    return Observation(
        "observation-v1",
        RULESET.patch_id,
        kind,
        state,
        hashlib.sha256(
            json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    )


def actions(phase: str, *indices: int) -> tuple[LegalAction, ...]:
    return tuple(
        LegalAction(f"handle:{i}", f"evangambit_{phase}", {"phase": phase, "action_index": i})
        for i in indices
    )


def model() -> FullRunModel:
    return initial_full_run_model(RULESET, CATALOG, "a" * 64, dimension=128, hidden_units=4)


@pytest.mark.parametrize(
    ("phase", "indices"),
    [
        ("combat", (0, 1, 2, 3)),
        ("card_reward", (0, 1, 3)),
        ("map", (0, 1)),
        ("rest_site", (0, 1)),
        ("shop", (0, 1, 7, 10, 13, 14)),
        ("ancient", (0, 1)),
        ("card_selection", (0, 1)),
        ("bundle_selection", (0, 1, 2)),
        ("relic_reward", (0, 1, 2, 3)),
        ("event", (0, 1)),
        ("crystal_sphere", (0, 121)),
        ("treasure", (3,)),
        ("phase-13", (0, 6)),
    ],
)
def test_each_family_binds_distinct_visible_candidates(
    phase: str, indices: tuple[int, ...]
) -> None:
    inputs = full_run_input(RULESET, observation(phase), actions(phase, *indices), CATALOG, 128)
    assert len({manifest_identifier(row) for row in inputs.bindings}) == len(indices)
    assert len({manifest_identifier(row) for row in inputs.vectors}) == len(indices)
    choice = FullRunPolicy(RULESET, model()).predict(observation(phase), actions(phase, *indices))
    assert choice.selected_action in actions(phase, *indices)
    assert sum(choice.probabilities) == pytest.approx(1)


def test_bound_object_scores_follow_hand_permutation_and_not_handles() -> None:
    first = observation("combat")
    second = copy.deepcopy(first.public_state)
    second["observation_vector"][8:16] = [45, 0, 0, 0, 17, 0, 0, 0]
    later = observation("combat", **{k: v for k, v in second.items() if k != "phase"})
    policy = FullRunPolicy(RULESET, model())
    a = policy.predict(first, actions("combat", 0, 1, 2))
    renamed = tuple(
        replace(v, action_id=f"arbitrary:{i}") for i, v in enumerate(actions("combat", 0, 1, 2))
    )
    b = policy.predict(later, renamed)
    assert a.logits == pytest.approx((b.logits[1], b.logits[0], b.logits[2]))


def test_card_selection_binds_offer_instead_of_deck_and_combat_selection_is_not_play() -> None:
    offered = observation("card_selection", offer_cards=[45, 17])
    inputs = full_run_input(RULESET, offered, actions("card_selection", 0, 1, 2), CATALOG, 128)
    assert inputs.bindings[0]["card"]["card_id"] == 45
    assert inputs.bindings[2]["kind"] == "confirm"
    combat = observation("combat")
    v = copy.deepcopy(combat.public_state["observation_vector"])
    v[183:189] = [15, 1, 45, 0, 0, 0]
    choice = full_run_input(
        RULESET, observation("combat", observation_vector=v), actions("combat", 0), CATALOG, 128
    )
    assert choice.bindings[0]["kind"] == "select_card"
    assert choice.bindings[0]["card"]["card_id"] == 45


def test_public_boundary_and_patch_reject_hidden_or_misaligned_inputs() -> None:
    with pytest.raises(ValueError, match="Privileged"):
        FullRunPolicy(RULESET, model()).predict(
            observation("ancient", rng_state=3), actions("ancient", 0)
        )
    with pytest.raises(ValueError, match="patch"):
        FullRunPolicy(RULESET, model()).predict(
            replace(observation("ancient"), patch_id="other"), actions("ancient", 0)
        )
    with pytest.raises(ValueError, match="phase"):
        FullRunPolicy(RULESET, model()).predict(observation("ancient"), actions("shop", 0))


def test_admitted_numeric_phase_is_normalized_without_changing_observation() -> None:
    obs = observation("ancient", phase_id=8)
    public = copy.deepcopy(obs.public_state)
    public["phase"] = 8
    numeric = replace(
        obs,
        public_state=public,
        state_hash=hashlib.sha256(
            json.dumps(public, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    )
    policy = FullRunPolicy(RULESET, model())
    assert (
        policy.predict(numeric, actions("ancient", 0, 1)).logits
        == policy.predict(obs, actions("ancient", 0, 1)).logits
    )
    assert numeric.public_state["phase"] == 8
    v = list(public["observation_vector"])
    v[276] = 4
    wrong = observation("ancient", observation_vector=v)
    with pytest.raises(ValueError, match="phase differs"):
        policy.predict(wrong, actions("ancient", 0, 1))


def test_genome_roundtrip_and_all_layer_gradients() -> None:
    original = model()
    assert original.parameter_count == 648
    restored = FullRunModel.from_mapping(original.as_dict())
    assert restored.genome == original.genome
    assert restored.model_id == original.model_id
    assert (
        FullRunModel.from_mapping(json.loads(json.dumps(original.as_dict()))).model_id
        == original.model_id
    )
    rows = ({0: 1.0, 2: 0.5, 60: 0.2}, {0: 1.0, 31: -0.4, 60: 0.1})
    gradient = np.array(score_gradient(original, rows, (0.3, -0.3)))
    for index in (2, 128, 512, 516, 520, 551):
        genes = list(original.genome)
        genes[index] += 1e-6
        up = score_features(original.with_genome(genes), rows)
        genes[index] -= 2e-6
        down = score_features(original.with_genome(genes), rows)
        derivative = (0.3 * (up[0] - down[0]) - 0.3 * (up[1] - down[1])) / 2e-6
        assert gradient[index] == pytest.approx(derivative, abs=1e-8)
    d = original.as_dict()
    d["genome"][0] += 1
    with pytest.raises(ValueError, match="identity"):
        FullRunModel.from_mapping(d)
    with pytest.raises(ValueError, match="finite"):
        original.with_genome([float("nan")] * original.parameter_count)


def test_progress_uses_observed_transitions_not_floor_or_first_act_identity() -> None:
    progress = PublicProgress()
    progress.observe(observation("map", act="underdocks", floor=1), 0)
    progress.observe(observation("map", act="underdocks", floor=17), 2)
    assert progress.completed_acts(False) == 0
    progress.observe(observation("ancient", act="hive", floor=18), 3)
    assert progress.completed_acts(False) == 1
    progress.observe(observation("ancient", act="glory", floor=35), 4)
    assert progress.completed_acts(True) == 3
    with pytest.raises(ValueError, match="transition"):
        progress.observe(observation("map", act="overgrowth", floor=40), 5)


def test_complete_episode_trace_and_interruption_preserve_failures(tmp_path: Path) -> None:
    spec = load_training_score_spec(
        Path("configs/training-objective/sts2-v0.107.1-full-run-bootstrap-v1.json")
    )
    spec = replace(spec, scope=TrainingScope(RULESET.manifest_id, "ironclad", 0))

    class TinyEnvironment:
        ruleset = RULESET

        def reset(self, seed: int) -> Observation:
            return observation("ancient")

        def legal_actions(self) -> tuple[LegalAction, ...]:
            return actions("ancient", 0, 1)

        def step(self, action: LegalAction) -> Transition:
            return Transition(
                observation("ancient"),
                action,
                observation("ancient", terminal=True),
                0,
                True,
                False,
            )

        def close(self) -> None:
            pass

    case, trace = collect_episode(
        TinyEnvironment,  # type: ignore[arg-type]
        RULESET,
        FullRunPolicy(RULESET, model()),
        spec,
        seed=1,
        partition="train",
        split_id="synthetic",
    )
    assert case["outcome"]["status"] == "terminal_loss"
    assert case["score"]["training_return"] > 0
    assert trace[0]["behavior_probability"] == 1
    path = tmp_path / "case.json"
    save_episode(path, case, trace)
    assert load_episode(path, case["binding"])["case_id"] == case["case_id"]
    verified = verify_episode_trace(
        path, RULESET, FullRunPolicy(RULESET, model()), spec, case["binding"]
    )
    assert verified["valid"] is True and verified["games_replayed"] == 0
    with pytest.raises(FileExistsError):
        save_episode(path, case, trace)

    class StalledEnvironment(TinyEnvironment):
        def step(self, action: LegalAction) -> Transition:
            return Transition(
                observation("ancient"), action, observation("ancient"), 0, False, False
            )

    failed, _ = collect_episode(
        StalledEnvironment,  # type: ignore[arg-type]
        RULESET,
        FullRunPolicy(RULESET, model()),
        spec,
        seed=1,
        partition="train",
        split_id="synthetic",
    )
    assert failed["outcome"]["status"] == "liveness_failure"
    assert failed["outcome"]["decisions"] == 3
    assert failed["score"]["training_return"] == 0
