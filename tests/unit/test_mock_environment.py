from spireshift.adapters.mock import MockSpireEnvironment


def test_nonterminal_progress_has_no_reward() -> None:
    environment = MockSpireEnvironment()
    environment.reset(seed=1)
    safe = next(action for action in environment.legal_actions() if action.action_id == "safe_path")
    transition = environment.step(safe)
    assert transition.terminal is False
    assert transition.reward == 0.0


def test_same_seed_and_actions_reproduce_state() -> None:
    hashes: list[str] = []
    for _ in range(2):
        environment = MockSpireEnvironment()
        observation = environment.reset(seed=13)
        elite = next(
            action for action in environment.legal_actions() if action.action_id == "elite_path"
        )
        transition = environment.step(elite)
        hashes.append(observation.state_hash + transition.next_observation.state_hash)
    assert hashes[0] == hashes[1]
