from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from spireshift import native_consequence_evaluation as module
from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_journal import ChunkJournal


def seeds(control: bool = False) -> list[dict[str, Any]]:
    return [
        {"id": i, "seed": f"WORLD{i}", **({"numerical_seed": i + 2} if control else {})}
        for i in range(2 if control else 32)
    ]


def test_fresh_game_schedule_covers_every_parent_and_variant_without_replacement() -> None:
    tasks = module.tasks(seeds(), False)
    assert len(tasks) == 192 and len({t["key"] for t in tasks}) == 192
    assert all(
        t["arm"] == "greedy" and t["stage"] == "game" and t["duplicate_of"] is None for t in tasks
    )
    for seed in seeds():
        own = [t for t in tasks if t["seed"] == seed]
        assert {(t["numerical_seed"], t["variant"]) for t in own} == {
            (p, a) for p in (2, 3) for a in ("original", "return_only", "consequence")
        }


def test_native_control_uses_two_other_worlds_and_exact_repeat_for_each_fork() -> None:
    tasks = module.tasks(seeds(True), True)
    assert len(tasks) == 8 and len([t for t in tasks if t["duplicate_of"]]) == 2
    assert all(t["numerical_seed"] == t["seed"]["numerical_seed"] for t in tasks)
    assert {t["variant"] for t in tasks if t["duplicate_of"]} == {"consequence"}


@pytest.mark.parametrize("control", [True, False])
def test_every_game_key_is_valid_for_the_actual_restart_journal(
    control: bool, tmp_path: Path
) -> None:
    store = ChunkJournal(tmp_path, {"workspace": "artifacts/study"})
    for task in module.tasks(seeds(control), control):
        assert store.path(task["key"]).name == task["key"]


def test_failed_and_missing_games_stay_in_original_denominator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "intervals", lambda _: [[0, 0]] * 4)
    completed = {}
    for t in module.tasks(seeds(), False):
        completed[t["key"]] = {
            **t,
            "seed_id": t["seed"]["id"],
            "status": "terminal",
            "maximum_floor": 10 if t["variant"] == "original" else 12,
            "completed_acts": 0,
            "victory": False,
            "training_return": 0.02,
            "cpu_seconds": 1,
        }
    failed = next(k for k, v in completed.items() if v["variant"] == "consequence")
    completed[failed]["status"] = "failed"
    missing = next(k for k, v in completed.items() if v["variant"] == "return_only")
    del completed[missing]
    summary = module.summarize(seeds(), completed, False)
    assert (
        summary["planned_games"] == 192
        and summary["failed_games"] == summary["not_attempted_games"] == 1
    )
    assert summary["completed_games"] == 190
    player = completed[failed]["numerical_seed"]
    result = next(v for v in summary["players"] if v["numerical_seed"] == player)
    assert result["arms"]["consequence"]["denominator"] == 32
    assert result["arms"]["consequence"]["mean_floor"] == 31 * 12 / 32
    assert (
        summary["pooled_paired_comparisons"]["consequence_minus_return_only"]["victory"][
            "interval95"
        ]
        is None
    )
    assert not summary["base_readiness_passed"] and not summary["checkpoint_promoted"]


def test_different_learned_policies_share_uniform_draws_without_forcing_same_choice(
    tmp_path: Path,
) -> None:
    completed = {}
    for variant, action in (("original", 0), ("return_only", 0), ("consequence", 1)):
        body = {
            "noncombat": [
                {
                    "draw_key": "slot",
                    "draw": 0.25,
                    "effective_input_id": "public",
                    "action_index": action,
                    "policy_log_probability": -0.5 - action,
                }
            ]
        }
        receipt = {**body, "report_id": manifest_identifier(body)}
        atomic_json(tmp_path / f"{variant}.json", receipt)
        completed[variant] = {
            "stage": "game",
            "status": "terminal",
            "numerical_seed": 2,
            "seed_id": 1,
            "variant": variant,
            "duplicate_of": None,
            "rng_receipt_path": f"{variant}.json",
            "rng_receipt_id": receipt["report_id"],
        }
    summary = module.matched_draws(tmp_path, completed)
    assert summary["shared_noncombat_draw_keys"] == 2
    assert summary["identical_inputs_with_changed_learned_choice"] == 2
    body = {
        "noncombat": [
            {"draw_key": "slot", "draw": 0.75, "effective_input_id": "public", "action_index": 1}
        ]
    }
    changed = {**body, "report_id": manifest_identifier(body)}
    (tmp_path / "consequence.json").write_text(json.dumps(changed))
    completed["consequence"]["rng_receipt_id"] = changed["report_id"]
    with pytest.raises(ValueError, match="shifted"):
        module.matched_draws(tmp_path, completed)


def test_duplicate_requires_exact_trace_not_just_equal_floor() -> None:
    planned = module.tasks(seeds(True), True)
    t = next(t for t in planned if t["duplicate_of"])
    completed = {
        t["key"]: {"status": "terminal", "trace_id": "a"},
        t["duplicate_of"]: {"status": "terminal", "trace_id": "a"},
    }
    assert module.duplicates(planned, completed)
    completed[t["key"]]["trace_id"] = "b"
    with pytest.raises(ValueError, match="repeat"):
        module.duplicates(planned, completed)
