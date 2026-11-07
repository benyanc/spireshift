from __future__ import annotations

import copy
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from test_native_action_context import model, score
from test_native_natural_curriculum import public
from test_native_turn_teacher_policy import next_round

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_cache import cached_model
from spireshift.native_coordinated_branch import branch
from spireshift.native_coordinated_data import candidates, cell, extensions, later_root, proposal
from spireshift.native_coordinated_roots import choose, eligible
from spireshift.native_coordinated_teacher import collect, summarize
from spireshift.native_natural_data import resources


def trace() -> dict[str, Any]:
    p = public()
    p["context"]["interaction"]["content"]["context"].update(round=1, is_play_phase=True)
    steps = []
    for _ in range(3):
        for _ in range(4):
            steps.append(
                {
                    "public_input": copy.deepcopy(p),
                    "public_input_id": manifest_identifier(p),
                    "action_index": 0,
                    "log_probabilities": [-0.1, -2, -3],
                }
            )
        p = next_round(p)
    return {
        "fight_id": "reference",
        "candidate": 0,
        "status": "complete",
        "outcome": "loss",
        "resources": {**resources(public()), "hp": 0},
        "steps": steps,
        "edits": [],
        "public_rounds": 3,
        "choice_decisions": 12,
        "cpu_seconds": 1,
    }


def root_entry(name: str = "root", player: int = 2) -> dict[str, Any]:
    p = trace()["steps"][0]["public_input"]
    return {
        "root_id": name,
        "player": player,
        "world": name,
        "pool": "control",
        "partition": "control",
        "entry": "early",
        "prefix": [],
        "public_input": p,
        "public_input_id": manifest_identifier(p),
        "descriptor": {"enemy_definitions": [name]},
    }


def path_from(plan: dict[str, Any], reference: dict[str, Any], candidate: int) -> dict[str, Any]:
    result = copy.deepcopy(reference)
    for i, step in enumerate(plan["forced"]):
        result["steps"][i]["action_index"] = step["action_index"]
    result.update(
        candidate=candidate,
        edits=plan["edits"],
        fight_id=f"fight-{candidate}",
        executed_edits=len(plan["edits"]),
    )
    return result


def test_joint_proposal_replays_actual_observed_prefix_and_keeps_all_prior_edits() -> None:
    ref = trace()
    a = proposal(ref, {"decision": 0, "action": 1})
    first = path_from(a, ref, 1)
    b = proposal(first, {"decision": 4, "action": 2})
    assert b["forced"][0]["action_index"] == 1 and b["forced"][4]["action_index"] == 2
    assert len(b["edits"]) == 2 and len(b["forced"]) == 5
    assert b["parent_fight_id"] == first["fight_id"]
    assert b["plan_id"] == manifest_identifier({k: v for k, v in b.items() if k != "plan_id"})
    assert ref["edits"] == [] and ref["steps"][0]["action_index"] == 0


@pytest.mark.parametrize(
    "edit",
    [{"decision": 0, "action": 0}, {"decision": 0, "action": 50}, {"decision": -1, "action": 1}],
)
def test_proposals_never_invent_or_repeat_an_action(edit: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        proposal(trace(), edit)


def test_extensions_change_later_choices_and_include_a_later_round() -> None:
    ref = trace()
    first = path_from(proposal(ref, {"decision": 0, "action": 1}), ref, 1)
    a, b = extensions(first, 2)
    assert a["edits"][-1]["decision"] == 1 and b["edits"][-1]["decision"] == 4
    with pytest.raises(ValueError):
        proposal(first, {"decision": 0, "action": 2})
    first["edits"][-1]["decision"] = len(first["steps"]) - 1
    assert extensions(first, 2) == []


def test_three_change_search_keeps_losing_intermediates_and_lineages_with_fixed_budget() -> None:
    ref = trace()
    rows: list[dict[str, Any]] = []
    for i in range(16):
        plan = candidates("coordinated", i, 4, ref, rows)
        assert plan is not None
        child = path_from(plan, ref, i + 1)
        # A deliberately delayed synthetic synergy; there is no one-change improvement.
        child["outcome"] = "win" if len(child["edits"]) >= 2 else "loss"
        child["resources"]["hp"] = 20 if child["outcome"] == "win" else 0
        rows.append(child)
    assert [len(r["edits"]) for r in rows] == [1] * 4 + [2] * 8 + [3] * 4
    assert all(r["outcome"] == "loss" for r in rows[:4])
    assert {r["edits"][0]["decision"] for r in rows[-4:]} == {0, 4}
    with pytest.raises(ValueError):
        candidates("coordinated", 16, 4, ref, rows)


def test_single_arm_remains_single_change_and_ignores_candidate_endings() -> None:
    ref = trace()
    before = [candidates("single_change", i, 4, ref, []) for i in range(16)]
    ref["resources"]["hp"], ref["outcome"] = 99, "win"
    assert before == [candidates("single_change", i, 4, ref, []) for i in range(16)]
    assert all(p is not None and len(p["edits"]) == 1 for p in before)


def test_exhausted_or_failed_lineages_are_not_replaced_with_new_worlds_or_retried() -> None:
    ref = trace()
    ref["steps"] = ref["steps"][:1]
    first = path_from(proposal(ref, {"decision": 0, "action": 1}), ref, 1)
    assert candidates("coordinated", 1, 1, ref, [first]) is None
    first["status"] = "failed"
    assert candidates("coordinated", 2, 1, ref, [first]) is None


def test_valid_short_better_plan_is_counted_without_the_old_four_choice_filter() -> None:
    reference = trace()
    reference.update(outcome="win", choice_decisions=3, public_rounds=2)
    reference["resources"]["hp"] = 28
    better = path_from(proposal(reference, {"decision": 0, "action": 1}), reference, 1)
    better["resources"]["hp"] = 35
    result = cell(reference, [better], True)
    assert result["strict_local_improvement"] and result["selected_choices"] == 3
    assert result["selected_hp"] - result["reference_hp"] == 7


def test_changed_plan_is_rejected_before_any_worker_starts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import spireshift.native_coordinated_branch as module

    def must_not_start(*args: Any, **kwargs: Any) -> None:
        pytest.fail("A changed proposal must not start a worker")

    monkeypatch.setattr(module, "RelicWorker", must_not_start)
    plan = proposal(trace(), {"decision": 0, "action": 1})
    plan["forced"][0]["action_index"] = 2
    with pytest.raises(ValueError, match="exact observed"):
        branch(
            cast(Any, None),
            {},
            {},
            root_entry(),
            {"plan": plan},
            cached_model(model()),
            score(),
            tmp_path,
            time.monotonic() + 180,
        )


def test_late_root_fixes_only_the_exact_original_greedy_opening_and_does_not_use_outcomes() -> None:
    early, ref = root_entry(), trace()
    late = later_root(early, ref)
    assert late is not None and late["reference_offset"] == 4
    assert len(late["prefix"]) == 4 and late["entry"] == "later"
    ref["resources"]["hp"], ref["outcome"] = 99, "win"
    assert later_root(early, ref) == late
    ref["steps"] = ref["steps"][:4]
    assert later_root(early, ref) is None


def test_public_first_turn_selection_is_not_a_menu_mask() -> None:
    p = root_entry()["public_input"]
    assert eligible(p) is not None
    assert eligible(next_round(p)) is None
    p["context"]["interaction"]["content"]["context"]["player"].pop("relics")
    with pytest.raises(ValueError):
        eligible(p)


def test_whole_world_sampling_excludes_all_old_teacher_worlds_and_ignores_final_results() -> None:
    pool = []
    for p in (2, 3):
        for i in range(24):
            pool.append(
                {
                    "key": [p, i],
                    "world": f"w{p}-{i}",
                    "player": p,
                    "descriptor": {
                        "hp_fraction": 0.9 - i * 0.01,
                        "enemy_definitions": [str(i), "other"],
                        "encounter_type": "normal",
                        "hp_band": "high",
                        "floor_band": "05-08",
                        "deck_signature": str(i),
                        "relic_signature": str(i),
                    },
                }
            )
    selected = choose(pool, {"w2-0", "w3-0"})
    assert len(selected) == len({r["world"] for r in selected}) == 10
    assert sum(r["partition"] == "fit" for r in selected) == 4
    for row in pool:
        row["final_victory"] = True
    assert [r["world"] for r in choose(pool, {"w2-0", "w3-0"})] == [r["world"] for r in selected]


def test_native_branch_executes_three_observed_changes_across_rounds_on_unchanged_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import spireshift.native_coordinated_branch as module

    p = root_entry()["public_input"]
    end = copy.deepcopy(p)
    end["context"]["interaction"] = {
        "kind": "reward_claim",
        "content": {"context": {"kind": "reward_flow", "reward_kind": "room_rewards"}},
    }
    observations = [p, next_round(p), next_round(next_round(p)), end]

    class FakeWorker:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.workspace, self.i = tmp_path / "worker", 0

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
            pass

        def stop(self) -> None:
            pass

        def retire(self, reason: str) -> None:
            pass

    monkeypatch.setattr(module, "RelicWorker", FakeWorker)
    monkeypatch.setattr(module, "audit", lambda *args: {"valid": True})
    m, r = cached_model(model()), root_entry()
    before = m.as_dict()
    result = branch(
        cast(Any, SimpleNamespace(root=tmp_path)),
        {},
        {"node": "node", "helpers_sha256": {}},
        r,
        {},
        m,
        score(),
        tmp_path / "reference",
        time.monotonic() + 180,
    )
    for i in range(3):
        action = (result["steps"][i]["action_index"] + 1) % len(p["candidates"])
        plan = proposal(result, {"decision": i, "action": action})
        result = branch(
            cast(Any, None),
            {},
            {"node": "node", "helpers_sha256": {}},
            r,
            {"candidate": i + 1, "arm": "coordinated", "plan": plan},
            m,
            score(),
            tmp_path / f"candidate-{i}",
            time.monotonic() + 180,
        )
    assert result["executed_edits"] == 3 and result["edited_rounds"] == [1, 2, 3]
    assert result["outcome"] == "win" and not result["ordinary_PPO_eligible"]
    assert m.as_dict() == before


@pytest.mark.parametrize("phase", ["prefix", "fight"])
def test_global_request_deadline_and_prefix_caps_retire_without_retry_or_success_label(
    phase: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import spireshift.native_coordinated_branch as module

    r = root_entry()
    if phase == "prefix":
        r["prefix"] = [{"public_input_id": r["public_input_id"], "action_index": 0}]
    calls: list[tuple[str, float]] = []
    retired: list[str] = []

    class TimedWorker:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.workspace = tmp_path / "worker"

        def request(self, command: str, *, timeout: float, **kwargs: Any) -> dict[str, Any]:
            calls.append((command, timeout))
            if command == "step":
                raise TimeoutError("Bounded action; never resend")
            return {
                "model_input": r["public_input"],
                "snapshot": {"snapshot_id": "s"},
                "facts": {"terminal": False},
            }

        def cpu_seconds(self) -> float:
            return 1.0

        def retire(self, reason: str) -> None:
            retired.append(reason)

        def stop(self) -> None:
            pass

    monkeypatch.setattr(module, "RelicWorker", TimedWorker)
    result = branch(
        cast(Any, None),
        {},
        {"node": "node", "helpers_sha256": {}},
        r,
        {},
        cached_model(model()),
        score(),
        tmp_path,
        time.monotonic() + 25,
    )
    assert result["status"] == "capped" and result["outcome"] is None
    assert result["native_audit"] is None and not result["ordinary_PPO_eligible"]
    assert [name for name, _ in calls] == ["mount", "step"] and len(retired) == 1
    assert all(0 < limit <= 5 for _, limit in calls)


def install_fake(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fail: bool = False
) -> tuple[dict[str, Any], list[str]]:
    import spireshift.native_coordinated_teacher as module

    calls = []

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
        replay: Any,
    ) -> dict[str, Any]:
        calls.append(r["world"])
        value = trace()
        value["steps"] = value["steps"][r.get("reference_offset", 0) :]
        value["resources"]["hp"], value["outcome"] = 20, "win"
        if replay:
            value.update(steps=replay["steps"], edits=replay["edits"])
        elif task.get("plan"):
            value = path_from(task["plan"], value, task["candidate"])
        value.update(
            root_id=r["root_id"],
            candidate=task.get("candidate", 0),
            status="failed" if fail and r["world"] == "first" else "complete",
            executed_edits=len(value["edits"]),
            edited_rounds=[1, 2] if len(value["edits"]) >= 2 else [1],
        )
        value.pop("fight_id")
        value["fight_id"] = manifest_identifier(value)
        atomic_json(target / "fight.json", value)
        return value

    monkeypatch.setattr(module, "branch", fake_branch)
    monkeypatch.setattr(module, "_running_games", lambda: [])
    monkeypatch.setattr(module, "_shared_snapshot", lambda _: {})
    monkeypatch.setattr(module, "immutable_checks", lambda *args: {"unchanged": True})
    monkeypatch.setattr(module, "snapshot", lambda *args: {})
    cfg = {
        "stage": "qualification_control",
        "workspace": "artifacts/test",
        "lineages": 1,
        "session_limits": {"wall_seconds": 240},
    }
    context = {
        "config": cfg,
        "sources": {},
        "roots": [root_entry("first"), root_entry("second", 3)],
        "models": {2: cached_model(model()), 3: cached_model(model())},
        "score": score(),
    }
    return context, calls


def test_full_2x2_comparison_resumes_sealed_units_without_new_fits_or_replaying_completed_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, calls = install_fake(monkeypatch, tmp_path)
    saved = collect(tmp_path, context, (None, None), max_units=5)
    assert saved["status"] == "coordinated_teacher_clean_pause" and len(calls) == 5
    result = collect(tmp_path, context, (None, None))
    assert result["status"] == "coordinated_teacher_complete"
    assert result["completed_units"] == result["native_attempts"] == len(calls) == 48
    assert result["control_checks_passed"] and result["optimizer_steps"] == 0
    assert len(result["cells"]) == 8 and len(result["comparison"]["paired_worlds"]) == 2
    assert collect(tmp_path, context, (None, None)) == result and len(calls) == 48


def test_failed_root_is_not_retried_or_replaced_and_other_world_still_finishes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, calls = install_fake(monkeypatch, tmp_path, True)
    result = collect(tmp_path, context, (None, None))
    assert calls.count("first") == 1 and calls.count("second") == 24
    assert result["failed_branches"] == 1 and result["planned_worlds"] == 2
    assert not result["control_checks_passed"]
    for p in result["comparison"]["panels"].values():
        assert p["world_denominator"] == 2


def test_open_game_refusal_leaves_no_poisoned_active_collection_unit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, calls = install_fake(monkeypatch, tmp_path)
    monkeypatch.setattr("spireshift.native_coordinated_teacher._running_games", lambda: [1])
    with pytest.raises(ValueError, match="Close STS2"):
        collect(tmp_path, context, (None, None))
    assert not list(tmp_path.rglob("active.json")) and not calls


def test_missing_late_positions_keep_the_original_world_denominator() -> None:
    result = summarize({"stage": "bounded_comparison"}, [{"partition": "fit"}] * 4, [])
    assert not result["paired_worlds"]
    assert all(
        p["world_denominator"] == 4 for k, p in result["panels"].items() if k.startswith("fit/")
    )
