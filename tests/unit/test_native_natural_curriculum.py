from __future__ import annotations

import copy
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from test_native_action_context import model, score
from test_native_turn_teacher_policy import next_round, selection
from test_native_turn_teacher_policy import public as old_public

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_ppo_math import Adam
from spireshift.native_conditional_control import teaching_gradient
from spireshift.native_context_cache import cached_model
from spireshift.native_natural_branch import branch
from spireshift.native_natural_curriculum import schedule, summary
from spireshift.native_natural_data import (
    LEARNING,
    admit,
    ending,
    improves,
    mutations,
    resources,
    select,
)
from spireshift.native_natural_learning import epoch, examples, lessons
from spireshift.native_natural_roots import choose, eligible
from spireshift.native_structured_state import load, save


def public() -> dict[str, Any]:
    p = old_public()
    p["context"]["reads"][0]["content"]["cards"] = []
    p["context"]["persistent"]["run"]["ascension"] = 8
    p["context"]["persistent"]["player"]["character_definition_id"] = "IRONCLAD"
    p["context"]["interaction"]["content"]["context"]["player"]["relics"] = []
    p["context"]["interaction"]["content"]["context"]["enemies"][0]["definition_id"] = "BEETLE"
    return p


def plan(candidate: int = 0, hp: float = 20) -> dict[str, Any]:
    p = public()
    steps = []
    for _ in range(3):
        for _ in range(3):
            steps.append(
                {
                    "public_input": copy.deepcopy(p),
                    "public_input_id": manifest_identifier(p),
                    "action_index": 0,
                    "log_probabilities": [-0.1, -1, -2],
                }
            )
        p = next_round(p)
    return {
        "candidate": candidate,
        "status": "complete",
        "outcome": "win",
        "steps": steps,
        "resources": {**resources(public()), "hp": hp},
        "fight_id": f"fight-{candidate}",
    }


def test_natural_fight_continues_through_enemy_turns_and_nested_menus() -> None:
    p = public()
    assert ending(p, next_round(p)) is None
    assert ending(p, selection(p)) is None
    after = copy.deepcopy(p)
    after["context"]["interaction"] = {
        "kind": "reward_claim",
        "content": {"context": {"kind": "reward_flow", "reward_kind": "room_rewards"}},
    }
    assert ending(p, after) == "win"
    after["context"]["persistent"]["player"]["hp"] = 0
    assert ending(p, after) == "loss"


def test_escape_and_non_room_rewards_are_not_labelled_combat_victories() -> None:
    p = public()
    after = copy.deepcopy(p)
    for context in ({"kind": "map"}, {"kind": "reward_flow", "reward_kind": "potion"}):
        after["context"]["interaction"] = {
            "kind": "map_navigation",
            "content": {"context": context},
        }
        assert ending(p, after) == "alive_exit"


@pytest.mark.parametrize("fault", ["room", "unknown"])
def test_ambiguous_encounter_exits_are_not_invented_wins(fault: str) -> None:
    p, q = public(), public()
    if fault == "room":
        q["context"]["persistent"]["run"]["floor"] += 1
    else:
        q["context"]["interaction"] = {"kind": "unknown_modal", "content": {}}
    with pytest.raises(ValueError):
        ending(p, q)


@pytest.mark.parametrize(
    "fault", ["potion_identity", "potion_count", "deck", "relic", "gold", "max_hp", "capped"]
)
def test_hp_does_not_override_observed_persistent_or_consumable_costs(fault: str) -> None:
    ref, better = plan(), plan(1, 30)
    assert improves(better, ref)
    if fault == "potion_identity":
        ref["resources"]["potions"], better["resources"]["potions"] = ["FAIRY"], ["FIRE"]
    elif fault == "potion_count":
        ref["resources"]["potions"] = ["FIRE", "FIRE"]
        better["resources"]["potions"] = ["FIRE"]
    elif fault in {"deck", "relic"}:
        better["resources"]["deck" if fault == "deck" else "relics"] = "changed"
    elif fault in {"gold", "max_hp"}:
        better["resources"][fault] = ref["resources"][fault] - 1
    else:
        better["status"] = "capped"
    assert not improves(better, ref)


def test_native_win_can_rescue_reference_death_but_is_not_full_run_utility() -> None:
    ref, better = plan(), plan(1)
    ref["outcome"] = "loss"
    assert improves(better, ref) and select([ref, better]) == 1
    better["outcome"] = "loss"
    assert not improves(better, ref) and select([ref, better]) == 0


def test_mutations_visit_later_turns_and_ignore_future_outcome_fields() -> None:
    p = plan()
    before = copy.deepcopy(p)
    a = mutations(p, 16)
    p["outcome"], p["resources"]["hp"] = "loss", -999
    assert mutations(p, 16) == a
    assert (
        len(
            {
                p["steps"][m["decision"]]["public_input"]["context"]["interaction"]["content"][
                    "context"
                ]["round"]
                for m in a
            }
        )
        == 3
    )
    assert all(m["action"] != before["steps"][m["decision"]]["action_index"] for m in a)
    assert p["steps"] == before["steps"]


def test_fitting_quality_is_whole_world_and_does_not_use_heldout_successes() -> None:
    roots, rows = [], []
    for i in range(5):
        roots.append(
            {
                "root_id": str(i),
                "partition": "fit" if i < 4 else "heldout",
                "world": str(i),
                "descriptor": {"enemy_definitions": [str(i % 2)], "deck_signature": str(i)},
            }
        )
        rows.append(
            {
                "root_id": str(i),
                "verified": True,
                "selected_outcome": "win",
                "choice_decisions": 6,
                "public_rounds": 3,
                "strict_local_improvement": True,
            }
        )
    assert admit(roots, rows)["passed"]
    rows[4]["selected_outcome"] = "loss"
    assert admit(roots, rows)["passed"]
    roots[1]["world"] = "0"
    assert not admit(roots, rows)["passed"]
    with pytest.raises(ValueError, match="Repeated"):
        admit(roots, [*rows, rows[0]])


def test_natural_root_requires_actual_repaired_public_inventory() -> None:
    p = public()
    assert eligible(p) is not None
    del p["context"]["interaction"]["content"]["context"]["player"]["relics"]
    with pytest.raises(ValueError, match="missing-counter"):
        eligible(p)


def test_world_selection_is_outcome_blind_and_keeps_control_out_of_both_splits() -> None:
    pool = []
    d = eligible(public())
    assert d is not None
    for p in (2, 3):
        for i in range(50):
            pool.append(
                {
                    "key": [p, i],
                    "world": f"WORLD{i}",
                    "player": p,
                    "descriptor": {
                        **d,
                        "hp_fraction": i / 50,
                        "deck_signature": str(i),
                        "enemy_definitions": [str(i % 3)],
                        "encounter_type": "normal",
                    },
                }
            )
    a = choose(pool)
    for x in pool:
        x["future_victory"], x["future_floor"] = True, 999
    assert [x["key"] for x in choose(pool)] == [x["key"] for x in a]
    assert len(a) == len({x["world"] for x in a}) == 14
    assert Counter(x["partition"] for x in a) == {
        "control_fit": 1,
        "control_heldout": 1,
        "fit": 8,
        "heldout": 4,
    }


def fitting() -> list[dict[str, Any]]:
    return [{"root_id": str(i), "world": str(i), "steps": plan()["steps"][: i + 1]} for i in (1, 2)]


def test_imitation_gradient_is_categorical_and_matches_nonzero_finite_differences() -> None:
    m, s = cached_model(model()), score()
    samples, labels = examples(m, fitting(), s, 8, "fixed-draws")
    settings = {"temperature": 0.8, "clip": 0.2, "value_coefficient": 0, "entropy_coefficient": 0}
    _, g, _ = teaching_gradient(cast(Any, m), samples, labels, settings)
    coordinates = sorted(range(m.actor.parameter_count), key=lambda i: abs(g[i]), reverse=True)[:3]
    assert all(abs(g[i]) > 1e-4 for i in coordinates)
    assert all(v == 0 for v in g[m.actor.parameter_count :])
    for i in coordinates:
        plus, minus = list(m.weights()), list(m.weights())
        plus[i] += 1e-5
        minus[i] -= 1e-5
        numeric = (
            teaching_gradient(cast(Any, m.with_weights(plus)), samples, labels, settings)[0]
            - teaching_gradient(cast(Any, m.with_weights(minus)), samples, labels, settings)[0]
        ) / 2e-5
        assert g[i] == pytest.approx(numeric, abs=1e-7)


def test_saved_full_adam_and_weights_resume_bit_exactly_and_original_stays_intact(
    tmp_path: Path,
) -> None:
    m, s = cached_model(model()), score()
    a = Adam.zero(m.parameter_count)
    original = m.as_dict(), a.as_dict()
    m1, a1, _ = epoch(m, a, fitting(), s, LEARNING, 1, 2, tmp_path / "one")
    save(tmp_path / "state.json", m1, a1)
    restored, restored_a, _ = load(tmp_path / "state.json")
    m2, a2, _ = epoch(m1, a1, fitting(), s, LEARNING, 2, 2, tmp_path / "two")
    resumed, resumed_a, _ = epoch(
        restored, restored_a, fitting(), s, LEARNING, 2, 2, tmp_path / "resumed"
    )
    assert resumed.weights() == m2.weights() and resumed_a.as_dict() == a2.as_dict()
    assert m2.value_weights == m.value_weights and a2.steps == 8
    assert (m.as_dict(), a.as_dict()) == original


def test_heldout_root_cannot_be_fitted_even_if_a_forged_gate_admits_it(tmp_path: Path) -> None:
    context = {
        "config": {"stage": "natural_multiturn_test"},
        "roots": [{"root_id": "held", "partition": "heldout"}],
    }
    teacher = {"gate": {"usable_fitting_roots": ["held"]}, "summaries": [{"root_id": "held"}]}
    with pytest.raises(ValueError, match="Held-out"):
        lessons(tmp_path, context, teacher)


def test_all_final_states_precede_heldout_and_fresh_evaluation() -> None:
    cfg = {"learning": LEARNING, "evaluation_seeds": [{"id": 1}]}
    tasks = schedule(cfg, [{"root_id": "held", "partition": "heldout"}])
    first = next(i for i, t in enumerate(tasks) if t["kind"] in {"held", "fresh"})
    assert all(t["kind"] in {"import", "fit"} for t in tasks[:first])
    assert all(t["kind"] in {"held", "fresh"} for t in tasks[first:])
    assert Counter(t["arm"] for t in tasks if t["kind"] == "fit") == {
        "reference_clone": 32,
        "teacher_clone": 32,
    }


def test_failed_full_games_stay_in_original_denominator_with_zero_value() -> None:
    cfg = {"stage": "short_control", "evaluation_seeds": [{"id": 1}]}
    done = {}
    for p in (2, 3):
        for arm in ("initial", "reference_clone", "teacher_clone"):
            done[f"{p}-{arm}"] = {
                "kind": "fresh",
                "player": p,
                "arm": arm,
                "seed_id": 1,
                "status": "failed" if arm == "teacher_clone" and p == 2 else "terminal",
                "victory": False,
                "completed_acts": 0,
                "maximum_floor": 10,
                "training_return": 0.01,
            }
    report = summary(cfg, done)
    assert report["arms"]["teacher_clone"]["denominator"] == 2
    assert report["arms"]["teacher_clone"]["mean_floor"] == 5
    assert report["paired"]["teacher_clone_minus_initial"]["maximum_floor"]["mean"] == -5


def test_native_branch_crosses_a_turn_and_closes_without_claiming_full_game_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import spireshift.native_natural_branch as module

    p = public()
    end = public()
    end["context"]["interaction"] = {
        "kind": "reward_claim",
        "content": {"context": {"kind": "reward_flow", "reward_kind": "room_rewards"}},
    }
    observations = [p, selection(p), next_round(p), end]
    workers = []

    class FakeWorker:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.workspace = tmp_path / "worker"
            self.i, self.closed, self.retired = 0, False, False
            workers.append(self)

        def request(self, command: str, **kwargs: Any) -> dict[str, Any]:
            if command == "step":
                self.i += 1
            return {
                "model_input": observations[self.i],
                "snapshot": {"snapshot_id": str(self.i)},
                "facts": {"terminal": False},
            }

        def cpu_seconds(self) -> float:
            return 1.0

        def close(self) -> None:
            self.closed = True

        def stop(self) -> None:
            pass

        def retire(self, reason: str) -> None:
            self.retired = True

    monkeypatch.setattr(module, "RelicWorker", FakeWorker)
    monkeypatch.setattr(module, "audit", lambda *args: {"valid": True})
    r = {"world": "NATURAL", "root_id": "root", "partition": "fit", "prefix": [], "public_input": p}
    result = branch(
        cast(Any, SimpleNamespace(root=tmp_path)),
        {},
        {"node": "node", "helpers_sha256": {}},
        r,
        {},
        cached_model(model()),
        score(),
        tmp_path,
        time.monotonic() + 180,
    )
    assert result["outcome"] == "win" and result["public_rounds"] == 2
    assert len(result["steps"]) == 3 and result["ordinary_PPO_eligible"] is False
    assert workers[0].closed and not workers[0].retired


def test_failed_reference_is_not_retried_and_does_not_erase_other_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import spireshift.native_natural_teacher as module

    calls: list[tuple[str, str]] = []

    def fake_branch(
        q: Any,
        inputs: Any,
        cfg: Any,
        r: Any,
        task: Any,
        m: Any,
        s: Any,
        target: Path,
        deadline: float,
        reference: Any,
    ) -> dict[str, Any]:
        calls.append((r["root_id"], task["phase"]))
        body = {
            **plan(task["candidate"]),
            "root_id": r["root_id"],
            "status": "failed" if r["root_id"] == "failed" else "complete",
            "public_rounds": 3,
            "choice_decisions": 9,
        }
        body.pop("fight_id")
        value = {**body, "fight_id": manifest_identifier(body)}
        atomic_json(target / "fight.json", value)
        return value

    monkeypatch.setattr(module, "branch", fake_branch)
    monkeypatch.setattr(module, "_running_games", lambda: [])
    monkeypatch.setattr(module, "_shared_snapshot", lambda _: {})
    monkeypatch.setattr(module, "immutable_checks", lambda *args: {"unchanged": True})
    monkeypatch.setattr(module, "snapshot", lambda *args: {})
    cfg = {
        "workspace": "artifacts/test",
        "maximum_mutations": 4,
        "session_limits": {"wall_seconds": 240},
    }
    roots = [
        {
            "root_id": name,
            "player": 2,
            "world": name,
            "partition": partition,
            "descriptor": {"enemy_definitions": ["TEST"], "deck_signature": name},
        }
        for name, partition in [("failed", "fit"), ("other", "heldout")]
    ]
    context = {
        "config": cfg,
        "roots": roots,
        "sources": {},
        "models": {2: cached_model(model())},
        "score": score(),
    }
    result = module.collect(tmp_path, context, (None, None))
    assert result["status"] == "natural_teacher_complete"
    assert result["root_gaps"] == 1 and result["planned_root_denominator"] == 2
    assert [phase for name, phase in calls if name == "failed"] == ["reference"]
    assert any(name == "other" and phase == "confirm_selected" for name, phase in calls)
    count = len(calls)
    assert module.collect(tmp_path, context, (None, None)) == result
    assert len(calls) == count
