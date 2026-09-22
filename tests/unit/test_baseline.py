from spireshift.agents.baseline import SearchRolloutPolicy, TerminalVictoryPolicy
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
