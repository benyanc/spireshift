from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, cast

import pytest

from spireshift import native_a8_later_training_plan as plan
from spireshift.engine_neural import initial_actor, initialize_native_critic
from spireshift.full_run_ppo_math import Adam
from spireshift.native_a8_head_policy import OwnedDecision, initialize
from spireshift.native_a8_later_start import complete_history, progress
from spireshift.native_a8_later_training import evaluation_task
from spireshift.native_a8_own_ppo import Decision
from spireshift.native_action_context import CROSSED
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_flow_live_v12 import append
from spireshift.native_input_normalization import QUARTER
from spireshift.training_objective import TrainingScoreSpec


def test_preboss_history_keeps_native_map_and_player_bytes() -> None:
    ancient = {"coord": {"col": 0, "row": 0}, "type": "ancient", "children": [{"col": 0, "row": 1}]}
    rest = {"coord": {"col": 0, "row": 1}, "type": "rest_site", "children": []}
    boss = {"coord": {"col": 0, "row": 2}, "type": "boss"}
    save: dict[str, Any] = {
        "acts": [
            {},
            {
                "id": "ACT.HIVE",
                "rooms": {"ancient_id": "EVENT.OROBAS"},
                "saved_map": {"start": ancient, "points": [rest], "boss": boss},
            },
        ],
        "players": [{"character_id": "CHARACTER.IRONCLAD", "net_id": 1, "deck": ["example"]}],
        "rng": {"seed": "TEST123"},
        "current_act_index": 1,
        "ascension": 8,
        "pre_finished_room": None,
        "visited_map_coords": [ancient["coord"], rest["coord"]],
        "map_point_history": [
            [],
            [{"map_point_type": "ancient", "rooms": [], "player_stats": [{"player_id": 1}]}],
        ],
    }
    before = copy.deepcopy(save)
    assert (
        complete_history(save, {"act": 2, "act_definition": "HIVE", "entry": "preboss"}, "TEST123")
        == 1
    )
    assert save["map_point_history"][1][0]["rooms"] == [
        {"room_type": "event", "model_id": "EVENT.OROBAS", "turns_taken": 0}
    ]
    assert {k: v for k, v in save.items() if k != "map_point_history"} == {
        k: v for k, v in before.items() if k != "map_point_history"
    }


def test_prepared_credit_starts_at_the_loaded_floor(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl.gz"
    for act, floor in ((2, 14), (2, 16), (3, 0), (3, 4)):
        append(
            path,
            {
                "kind": "policy_input",
                "frame": {
                    "public_input": {
                        "context": {"persistent": {"run": {"act": act, "floor": floor}}}
                    }
                },
            },
        )
    assert progress(path, 2, 14, False) == {
        "completed_acts": 1,
        "maximum_floor": 6,
        "maximum_act": 3,
    }
    assert progress(path, 2, 14, True)["completed_acts"] == 2
    with pytest.raises(ValueError, match="fresh normal-start evaluation"):
        evaluation_task({"act": 2, "archived": "m-023-p2"}, 2, "fitted", "development")


def test_shared_fit_uses_verified_strata_and_keeps_full_adam(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    actor = initial_actor("sha256:" + "1" * 64, 128, 4, 7, input_normalization=QUARTER)
    model = CachedContextModel(initialize_native_critic(actor), CROSSED, "sha256:" + "2" * 64)
    start = initialize(
        model, Adam(12, (0.1,) * model.parameter_count, (0.01,) * model.parameter_count), "shared"
    )
    original = start.document()
    games = [
        (
            tmp_path,
            {
                "task": {"start_act": act, "player": 2},
                "outcome": "loss",
                "setup_id": f"setup-{act}" if act > 1 else None,
                "prepared_suffix_victory": False,
            },
        )
        for act, count in ((1, 4), (2, 3), (3, 8))
        for _ in range(count)
    ]
    origins = []

    def collect(rows: list[tuple[Path, dict[str, Any]]], *_: Any) -> Any:
        origins.append({row["task"]["start_act"] for _, row in rows})
        return [OwnedDecision(False, cast(Decision, object())) for _ in rows], {}

    def update(
        current: CachedContextModel, adam: Adam, batch: list[Decision], *_: Any
    ) -> tuple[CachedContextModel, Adam, dict[str, int]]:
        assert current == start.model and len(batch) == 8
        assert adam.first == start.actor_adam.first + start.value_adam.first
        assert adam.second == start.actor_adam.second + start.value_adam.second
        weights = current.weights()
        return (
            cast(CachedContextModel, current.with_weights((weights[0] + 0.01, *weights[1:]))),
            Adam(adam.steps + 1, adam.first, adam.second),
            {"optimizer_steps": 1},
        )

    monkeypatch.setattr(plan, "training_examples", collect)
    monkeypatch.setattr(plan, "update", update)
    fitted, work = plan.fit(
        start, games, cast(TrainingScoreSpec, None), {"credit": {}, "settings": {}}, 2, 1
    )
    assert origins == [{1}, {2}, {3}]
    assert [work["by_start_act"][str(act)]["selected_decisions"] for act in (1, 2, 3)] == [4, 2, 2]
    assert fitted.model.arm == "shared" and fitted.model != start.model
    assert fitted.actor_adam.steps == fitted.value_adam.steps == 13
    assert start.document() == original
