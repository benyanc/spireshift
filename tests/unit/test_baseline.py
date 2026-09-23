from spireshift.agents.baseline import (
    ProgressBootstrapPolicy,
    SearchRolloutPolicy,
    TerminalVictoryPolicy,
)
from spireshift.core.types import DecisionType, LegalAction, Observation


def test_search_rollout_policy_completes_card_selection_without_changing_base_policy() -> None:
    observation = Observation(
        schema_version="observation-v1",
        patch_id="test",
        decision_type=DecisionType.CARD_SELECTION,
        public_state={},
        state_hash="0" * 64,
    )
    actions = (
        LegalAction("select-0", "select_card", {"index": 0}),
        LegalAction("confirm", "confirm", {}),
    )

    assert TerminalVictoryPolicy().choose_action(observation, actions).action_id == "select-0"
    assert SearchRolloutPolicy().choose_action(observation, actions).action_id == "confirm"
    assert SearchRolloutPolicy.policy_id == "terminal-victory-search-rollout-v1"


def test_progress_bootstrap_policy_uses_public_combat_and_map_information() -> None:
    vector = [0] * 28
    vector[8] = 131
    vector[10] = 472
    combat = Observation(
        schema_version="observation-v1",
        patch_id="test",
        decision_type=DecisionType.COMBAT,
        public_state={"observation_vector": vector},
        state_hash="1" * 64,
    )
    combat_actions = (
        LegalAction("defend", "card", {"action_index": 0}),
        LegalAction("strike", "card", {"action_index": 1}),
        LegalAction("end", "end_turn", {"action_index": 5}),
    )
    path = Observation(
        schema_version="observation-v1",
        patch_id="test",
        decision_type=DecisionType.PATH,
        public_state={
            "player_hp": 60,
            "player_max_hp": 80,
            "map_choices": [{"node_type": 1}, {"node_type": 2}],
        },
        state_hash="2" * 64,
    )
    path_actions = (
        LegalAction("normal", "map", {"action_index": 0}),
        LegalAction("elite", "map", {"action_index": 1}),
    )
    policy = ProgressBootstrapPolicy()

    assert policy.choose_action(combat, combat_actions).action_id == "strike"
    assert policy.choose_action(path, path_actions).action_id == "elite"
    assert policy.policy_id == "public-progress-bootstrap-v1"


def test_progress_bootstrap_policy_heals_only_when_low() -> None:
    actions = (
        LegalAction("heal", "rest", {"action_index": 0}),
        LegalAction("upgrade", "rest", {"action_index": 1}),
    )
    policy = ProgressBootstrapPolicy()

    def observation(hp: int) -> Observation:
        return Observation(
            schema_version="observation-v1",
            patch_id="test",
            decision_type=DecisionType.REST_SITE,
            public_state={"player_hp": hp, "player_max_hp": 80},
            state_hash=str(hp).zfill(64),
        )

    assert policy.choose_action(observation(20), actions).action_id == "heal"
    assert policy.choose_action(observation(60), actions).action_id == "upgrade"
