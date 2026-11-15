from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from test_native_greedy_turn_policy import plan, root, seed

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_greedy_turn_data import (
    budget_task,
    first_actions,
    freeze_plans,
    freeze_roots,
    lessons,
    matched_draws,
    proposal_tasks,
    scored_tasks,
    source_tasks,
)


def test_main_proposes_every_current_legal_first_move_and_a_greedy_reference() -> None:
    r = root()
    assert first_actions(r, False) == [None, 0, 1, 2]
    assert len(first_actions(r, True)) == 2
    assert first_actions(r, True)[1] != r["reference_action"]
    tasks = proposal_tasks([r], False)
    assert [t["first_action"] for t in tasks] == [None, 0, 1, 2]
    assert all(t["seed"]["id"] == r["source_seed_id"] for t in tasks)


def frozen(
    tmp_path: Path, control: bool = False
) -> tuple[
    ChunkJournal, dict[str, Any], list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, str]
]:
    store = ChunkJournal(tmp_path, {"workspace": "artifacts/teacher"})
    r, completed, sources = root(), {}, {}
    tasks = proposal_tasks([r], control)
    for task in tasks:
        p = plan(r, task["first_action"])
        path = tmp_path / f"{task['key']}.json"
        atomic_json(path, p)
        completed[task["key"]] = {
            "stage": "proposal",
            "root_id": r["root_id"],
            "status": "terminal",
            "execution_cpu_seconds": 1.0,
            "plan_path": path.name,
            "plan_id": p["plan_id"],
            "root_reached": True,
            "turn_complete": True,
            "native_audit_valid": True,
            "inference_audit_valid": True,
            "training_return": 0.01,
            "victory": False,
        }
        sources[str((store.path(task["key"]) / "done.json").relative_to(tmp_path))] = "receipt"
    return store, r, tasks, completed, sources


def test_freeze_is_ordered_outcome_blind_and_exact_trace_deduplicated(tmp_path: Path) -> None:
    store, r, tasks, completed, sources = frozen(tmp_path)
    a = freeze_plans(store, [r], tasks, completed, sources, False)
    candidates = a["roots"][0]["candidates"]
    assert candidates[0]["reference"] and len(candidates) == 3
    assert sum(len(c["proposal_keys"]) for c in candidates) == 4
    for v in completed.values():
        v.update(training_return=1.0, victory=True, maximum_floor=999)
    assert freeze_plans(store, [r], tasks, completed, sources, False) == a
    with pytest.raises(ValueError, match="first-move"):
        freeze_plans(store, [r], tasks[:-1], completed, sources, False)


def test_comparisons_have_a_cheap_reference_and_charge_all_proposal_CPU(tmp_path: Path) -> None:
    store, r, tasks, completed, sources = frozen(tmp_path)
    f = freeze_plans(store, [r], tasks, completed, sources, False)
    scheduled = scored_tasks([r], f, 8, False)
    assert len(scheduled) == 24
    for t in scheduled:
        assert t["planning_cpu_seconds"] == (0.0 if t["reference"] else 4.0)
        assert budget_task(t, completed)["cpu_allowance"] == (128.0 if t["reference"] else 124.0)
    assert not any(t["duplicate_control"] for t in scheduled)


def test_short_control_has_exact_repeats_and_cannot_admit_preferences(tmp_path: Path) -> None:
    store, r, tasks, completed, sources = frozen(tmp_path, True)
    f = freeze_plans(store, [r], tasks, completed, sources, True)
    scheduled = scored_tasks([r], f, 2, True)
    assert len(scheduled) == 5 and sum(t["duplicate_control"] for t in scheduled) == 1
    for t in scheduled:
        completed[t["key"]] = {
            **t,
            "status": "terminal",
            "training_return": 0.01 if t["reference"] else 0.1,
            "root_reached": True,
            "turn_complete": True,
            "native_audit_valid": True,
            "victory": False,
            "maximum_floor": 8,
        }
    result = lessons([r], f, completed, 2)[0]
    assert result["comparison_complete"]
    assert not any(p["admitted_exploratory_preference"] for p in result["preferences"])
    assert not result["ordinary_PPO_eligible"] and not result["public_belief_search_eligible"]


@pytest.mark.parametrize("fault", ["failed", "incomplete", "cost"])
def test_bad_proposals_never_supply_partial_or_outcome_selected_candidates(
    fault: str, tmp_path: Path
) -> None:
    store, r, tasks, completed, sources = frozen(tmp_path)
    v = completed[tasks[-1]["key"]]
    if fault == "failed":
        v["status"] = "failed"
    elif fault == "cost":
        v["execution_cpu_seconds"] = 65.0
    else:
        v["turn_complete"] = False
    if fault == "incomplete":
        with pytest.raises(ValueError, match="audits"):
            freeze_plans(store, [r], tasks, completed, sources, False)
    else:
        f = freeze_plans(store, [r], tasks, completed, sources, False)
        assert f["roots"][0]["blocked"] and f["roots"][0]["candidates"] == []


def test_proposal_budget_is_finite_cumulative_and_never_restarts_at_each_candidate() -> None:
    t = proposal_tasks([root()], False)[0]
    done = {"prior": {"stage": "proposal", "root_id": t["root_id"], "execution_cpu_seconds": 40.0}}
    assert budget_task(t, done)["cpu_allowance"] == 24.0
    done["prior"]["execution_cpu_seconds"] = 64.0
    assert budget_task(t, done)["cpu_allowance"] == 0.0
    done["prior"]["execution_cpu_seconds"] = float("nan")
    with pytest.raises(ValueError, match="accounting"):
        budget_task(t, done)
    assert budget_task(source_tasks([seed()])[0], {})["cpu_allowance"] == 128.0


def test_missing_source_roots_remain_in_the_original_world_denominator(tmp_path: Path) -> None:
    store = ChunkJournal(tmp_path, {"workspace": "artifacts/teacher"})
    tasks = source_tasks([seed(2), seed(3)])
    r = root()
    path = tmp_path / "root.json"
    atomic_json(path, r)
    completed = {
        tasks[0]["key"]: {
            "status": "terminal",
            "root_path": "root.json",
            "root_id": r["root_id"],
            "inference_audit_valid": True,
        },
        tasks[1]["key"]: {"status": "terminal", "root_path": None},
    }
    sources = {
        str((store.path(t["key"]) / "done.json").relative_to(tmp_path)): "receipt" for t in tasks
    }
    f, available = freeze_roots(store, tasks, completed, sources)
    assert available == [r] and len(f["sources"]) == 2
    assert f["sources"][1]["reason"] == "no_eligible_public_root"
    assert f["no_missing_source_replacement"]
    with pytest.raises(ValueError, match="every"):
        freeze_roots(store, tasks, {tasks[0]["key"]: completed[tasks[0]["key"]]}, sources)


def test_draw_matching_rejects_shifted_draws_or_changed_identical_input_choices(
    tmp_path: Path,
) -> None:
    completed = {}
    original: dict[str, Any] = {
        "draw_key": "shared",
        "draw": 0.5,
        "effective_input_id": "same",
        "action_index": 0,
        "policy_log_probability": -0.1,
    }
    for ref in (True, False):
        body = {"noncombat": [copy.deepcopy(original)]}
        rng = {**body, "report_id": manifest_identifier(body)}
        name = f"{ref}.json"
        atomic_json(tmp_path / name, rng)
        completed[name] = {
            "stage": "comparison",
            "status": "terminal",
            "root_id": "root",
            "repeat": 0,
            "duplicate_control": False,
            "reference": ref,
            "rng_receipt_path": name,
            "rng_receipt_id": rng["report_id"],
        }
    assert matched_draws(tmp_path, completed)["identical_public_inputs_with_identical_choices"] == 1
    for fault in ("draw", "action_index"):
        row = {**original, fault: 0.75 if fault == "draw" else 1}
        body = {"noncombat": [row]}
        rng = {**body, "report_id": manifest_identifier(body)}
        (tmp_path / "False.json").write_text(json.dumps(rng))
        completed["False.json"]["rng_receipt_id"] = rng["report_id"]
        with pytest.raises(ValueError, match="matching"):
            matched_draws(tmp_path, completed)
