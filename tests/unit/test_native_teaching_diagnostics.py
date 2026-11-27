from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Any

import pytest
from test_native_action_context import model, score
from test_native_coordinated_teacher import trace
from test_native_teaching import config, context, fixture_bank, install_fakes

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_cache import cached_model
from spireshift.native_teaching_diagnostic_history import select
from spireshift.native_teaching_diagnostic_inputs import complete_report, local, receipts
from spireshift.native_teaching_diagnostic_metrics import (
    changed_reach,
    departure,
    distribution,
    interference,
    lesson_details,
    movement,
    world_mean,
)
from spireshift.native_teaching_diagnostic_report import run
from spireshift.native_teaching_execute import execute


def identified_report(path: Path, body: dict[str, Any]) -> None:
    atomic_json(path, {**body, "report_id": manifest_identifier(body)})


@pytest.mark.parametrize("partial_report", [False, True])
def test_active_source_refused_without_opening_partial_states_or_taking_its_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, partial_report: bool
) -> None:
    cfg = config()
    source = tmp_path / cfg["workspace"]
    (source / "chunks/live").mkdir(parents=True)
    marker = source / "chunks/live/active.json"
    marker.write_text("Uncommitted work must not be opened or cleared.")
    if partial_report:
        identified_report(source / "report.json", {"status": "native_teaching_clean_pause"})

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("The diagnostic must stop before opening partial chunks or acquiring a lock")

    monkeypatch.setattr("spireshift.native_context_journal.ChunkJournal.lock", forbidden)
    monkeypatch.setattr("spireshift.native_context_journal.ChunkJournal.completed", forbidden)
    with pytest.raises(ValueError, match="complete"):
        complete_report(tmp_path, cfg)
    assert marker.read_text() == "Uncommitted work must not be opened or cleared."


def test_completed_receipts_reconstruct_exact_schedule_and_never_lock_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_fakes(monkeypatch)
    ctx = context()
    report = execute(tmp_path, ctx, (None, None))

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("A read-only diagnostic cannot lock or fit a source")

    monkeypatch.setattr("spireshift.native_context_journal.ChunkJournal.lock", forbidden)
    monkeypatch.setattr("spireshift.native_natural_learning.epoch", forbidden)
    accepted, _ = complete_report(tmp_path, ctx["config"])
    done = receipts(tmp_path, ctx["config"], ctx["bank"], accepted)
    assert len(done) == report["planned_units"] == 16
    assert done["frozen-finals"] == report["frozen_finals"]
    state = tmp_path / done["initial-p2"]["state_path"]
    state.write_text(state.read_text() + "\n")
    with pytest.raises(ValueError, match="evidence changed"):
        receipts(tmp_path, ctx["config"], ctx["bank"], accepted)


def test_receipts_reject_relabelled_player_or_missing_evaluation_denominator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_fakes(monkeypatch)
    ctx = context()
    report = execute(tmp_path, ctx, (None, None))
    altered = copy.deepcopy(report)
    altered["planned_units"] -= 1
    with pytest.raises(ValueError, match="denominators"):
        receipts(tmp_path, ctx["config"], ctx["bank"], altered)
    altered = copy.deepcopy(report)
    altered["natural_fights"][0]["player"] = 3
    with pytest.raises(ValueError, match="denominators"):
        receipts(tmp_path, ctx["config"], ctx["bank"], altered)


def test_first_action_departure_stops_alignment_before_different_followup_states() -> None:
    expected = trace()["steps"][:3]
    actual = copy.deepcopy(expected)
    actual[1]["action_index"] = 1
    actual[2]["public_input"]["context"]["persistent"]["player"]["hp"] -= 2
    actual[2]["public_input_id"] = manifest_identifier(actual[2]["public_input"])
    result = departure(expected, actual)
    assert result["exact_common_prefix_actions"] == 1
    assert result["first_departure"]["position"] == 1
    assert result["first_departure"]["kind"] == "different_action_on_identical_public_state"
    assert result["first_departure"]["expected_action"] == 0
    assert result["first_departure"]["actual_action"] == 1
    assert result["departure_is_proven_mistake"] is False
    assert result["post_departure_states_compared_by_position"] is False


def test_state_difference_or_early_ending_is_not_compared_as_an_action_mistake() -> None:
    expected = trace()["steps"][:2]
    actual = copy.deepcopy(expected)
    actual[0]["public_input"]["context"]["persistent"]["player"]["hp"] -= 1
    actual[0]["public_input_id"] = manifest_identifier(actual[0]["public_input"])
    result = departure(expected, actual)
    assert result["first_departure"]["kind"] == "public_state_difference"
    assert result["first_departure"]["action_comparison_available"] is False
    assert departure(expected, expected[:1])["first_departure"]["kind"] == "executed_trace_ended"
    assert departure(expected[:1], expected)["first_departure"]["kind"] == "plan_trace_ended"
    assert departure(expected, expected)["same_complete_trace"]


def test_changed_choice_not_reached_stays_missing_instead_of_becoming_wrong() -> None:
    step = trace()["steps"][0]
    other = copy.deepcopy(step)
    other["public_input"]["context"]["persistent"]["player"]["hp"] -= 1
    other["public_input_id"] = manifest_identifier(other["public_input"])
    missing = changed_reach([step], [other])[0]
    assert not missing["exact_state_reached"] and missing["target_taken_on_every_visit"] is None
    repeated = changed_reach([step], [step, {**step, "action_index": 1}])[0]
    assert repeated["exact_state_reached"] and repeated["target_taken_on_every_visit"] is False
    assert len(repeated["observed_positions_and_actions"]) == 2


def probe(world: str, family: str, decision: int) -> dict[str, Any]:
    public = copy.deepcopy(trace()["steps"][0]["public_input"])
    public["context"]["persistent"]["player"]["gold"] += decision
    return {
        "world": world,
        "decision": decision,
        "public_input_id": manifest_identifier(public),
        "public_input": public,
        "description": {"family": family},
        "source": {"episode": world, "decision": decision},
    }


def test_probe_sampling_balances_families_caps_worlds_and_ignores_outcomes_and_actions() -> None:
    rows = [probe(f"w{i // 10}", "combat", i) for i in range(100)] + [probe("rare", "rest", 101)]
    selected = select(rows, 12, 2)
    altered = [
        {**r, "victory": True, "maximum_floor": 99, "action_index": 1} for r in reversed(rows)
    ]
    again = select(altered, 12, 2)
    assert [r["public_input_id"] for r in selected] == [r["public_input_id"] for r in again]
    assert len(selected) == 12 and any(r["description"]["family"] == "rest" for r in selected)
    assert all(sum(r["world"] == w for r in selected) <= 2 for w in {r["world"] for r in selected})
    duplicate = {**rows[0], "world": "alias-world"}
    unique = select([*rows, duplicate], 128, 2)
    assert len({r["public_input_id"] for r in unique}) == len(unique)


def test_world_means_do_not_let_long_fights_supply_extra_independent_weight() -> None:
    rows = [{"world": "long", "x": 1.0}] * 100 + [{"world": "short", "x": 0.0}]
    assert world_mean(rows, "x") == 0.5
    before = tuple(math.log(p) for p in (0.9, 0.1))
    after = tuple(math.log(p) for p in (0.1, 0.9))
    result = movement(before, after)
    assert result["greedy_action_changed"] and result["total_variation"] == pytest.approx(0.8)
    assert movement(before, before)["KL_initial_to_copy"] == 0


def test_inference_diagnostics_never_mutate_models_or_adam_and_exclude_hidden_labels() -> None:
    ctx = context()
    m = cached_model(model(seed=2))
    models = {"initial": m, "reference_clone": m, "teacher_clone": m}
    originals = copy.deepcopy((m.as_dict(), ctx["adams"][2].as_dict()))
    details = lesson_details(models, fixture_bank(), score(), math.inf)
    p = probe("old-world", "combat_turn", 3)
    p.update(DEBUG_future={"victory": 999}, action_index=999)
    result = interference(models, [p], score(), math.inf)
    assert (m.as_dict(), ctx["adams"][2].as_dict()) == originals
    assert details["better_target_probabilities_establish_stronger_play"] is False
    assert result["source_actions_used_as_optimal_labels"] is False
    assert all(a["by_family"][0]["total_variation"] == 0 for a in result["arms"].values())
    with pytest.raises(TimeoutError, match="wall cap"):
        interference(models, [p], score(), 0)
    public = copy.deepcopy(p["public_input"])
    public["DEBUG_future"] = 1
    with pytest.raises(ValueError):
        distribution(m, public, score())


def test_paths_reject_aliases_and_cannot_write_through_to_a_checkpoint(tmp_path: Path) -> None:
    original = tmp_path / "weights.json"
    original.write_text("Keep weights and Adam unchanged")
    (tmp_path / "alias.json").symlink_to(original)
    for name in ("alias.json", "../weights.json", str(original)):
        with pytest.raises(ValueError, match="aliases"):
            local(tmp_path, name)
    assert original.read_text() == "Keep weights and Adam unchanged"


def test_cached_report_is_verified_without_repeating_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import spireshift.native_teaching_diagnostic_report as module
    from spireshift.engine_qualification import _sha_file

    cfg: dict[str, Any] = {
        "workspace": "artifacts/diagnostic",
        "session_limits": {"wall_seconds": 240},
    }
    output = tmp_path / cfg["workspace"]
    output.mkdir(parents=True)
    (output / "summary.md").write_text("Complete saved diagnostic")
    body = {
        "config_id": manifest_identifier(cfg),
        "source_report_id": "completed",
        "summary_sha256": _sha_file(output / "summary.md"),
        "sources": {},
    }
    identified_report(output / "report.json", body)
    monkeypatch.setattr(
        module, "prepare", lambda *args: {"config": cfg, "report": {"report_id": "completed"}}
    )

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("Cached reports cannot start another analysis or optimizer")

    monkeypatch.setattr(module, "historical_probes", forbidden)
    assert run(tmp_path, tmp_path / "recipe.json")["source_report_id"] == "completed"
    (output / "summary.md").write_text("Changed summary")
    with pytest.raises(ValueError, match="existing diagnostic"):
        run(tmp_path, tmp_path / "recipe.json")
