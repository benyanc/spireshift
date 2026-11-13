"""Assess saved synthetic pilots only; no game, worker, optimizer or native DLL is invoked."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from test_engine_neural import public

import spireshift.native_pilot_assessment as assessment
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_neural import initial_actor, initialize_native_critic
from spireshift.engine_qualification import _sha_file
from spireshift.training_objective import load_training_score_spec


def write(path: Path, doc: dict[str, Any], key: str | None = None) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if key:
        doc = {k: v for k, v in doc.items() if k != key}
        doc = {**doc, key: manifest_identifier(doc)}
    path.write_text(json.dumps(doc))
    return doc


def reseal_case(path: Path, doc: dict[str, Any]) -> None:
    doc["case_id"] = manifest_identifier(
        {k: v for k, v in doc.items() if k not in {"case_id", "trace_file_sha256"}}
    )
    write(path, doc)


@pytest.fixture
def pilot(tmp_path: Path) -> tuple[Path, Path]:
    """A one-round synthetic pilot with deliberately misleading failed-game progress."""
    base = tmp_path / "artifacts/pilot"
    environment = write(
        tmp_path / "environment.json",
        {"version": "v0.111.0", "character": "Ironclad", "ascension": 8},
        "manifest_id",
    )
    env_id = environment["manifest_id"]
    seeds = write(
        tmp_path / "seeds.json",
        {
            "environment_id": env_id,
            "seeds": [
                {"id": i, "seed": f"SYNTHETIC{i}", "partition": part}
                for i, part in (
                    (1, "train"),
                    (2, "confirmation"),
                    (3, "development"),
                    (4, "development"),
                )
            ],
        },
        "manifest_id",
    )
    score_doc = json.loads(
        Path(
            "configs/training-objective/sts2-v0.111.0-ironclad-a8-native-bootstrap-v7.json"
        ).read_text()
    )
    score_doc["scope"]["ruleset_manifest_id"] = env_id
    write(tmp_path / "score.json", score_doc)
    score = load_training_score_spec(tmp_path / "score.json")
    cfg = {
        "stage": "bounded_policy_only_pilot",
        "workspace": "artifacts/pilot",
        "environment_manifest": {"path": "environment.json", "id": env_id},
        "seed_manifest": {"path": "seeds.json", "id": seeds["manifest_id"]},
        "training_spec": {"path": "score.json", "id": score.spec_id},
        "implementation_sha256": {"historical.py": hashlib.sha256(b"old learner").hexdigest()},
        "helpers_sha256": {"historical.mjs": hashlib.sha256(b"old worker").hexdigest()},
        "learning": {
            "rollout_panels": [[1]],
            "confirmation_seeds": [2],
            "development_seeds": [3, 4],
            "confirmation_every": 1,
            "sampling_seed": 7,
            "ppo": {"temperature": 0.8},
        },
        "evaluation_policy": {
            "behavior": "sampled_softmax",
            "sampling_seed": 8,
            "temperature": 0.8,
            "coupling": "same_run_seed_across_checkpoints",
        },
    }
    config_path = tmp_path / "config.json"
    write(config_path, cfg)
    write(base / "config.json", cfg)
    (base / "source-at-launch").mkdir()
    (base / "source-at-launch/historical.py").write_bytes(b"old learner")
    initial = initialize_native_critic(initial_actor(env_id, 128, 4))
    updated = initial.with_weights([initial.weights()[0] + 0.1, *initial.weights()[1:]])
    write(base / "initial-checkpoint.json", initial.as_dict())
    write(base / "round-001-checkpoint.json", updated.as_dict())
    write(base / "selected-checkpoint.json", updated.as_dict())
    write(
        base / "selection-freeze.json",
        {
            "model_id": updated.model_id,
            "selection_partition": "confirmation",
            "development_opened": False,
        },
    )
    update = {
        "round": 1,
        "behavior_model_id": initial.model_id,
        "updated_model_id": updated.model_id,
        "completed_training_games": 1,
        "excluded_failed_training_games": 0,
        "actor_l2_change": 0.1,
        "critic_l2_change": 0.0,
        "diagnostics": {"optimizer_steps": 1, "sampled_decisions": 1},
    }
    write(base / "round-001-update.json", update)
    seed_map = {s["id"]: s for s in seeds["seeds"]}
    models = {
        0: initial.model_id,
        1: updated.model_id,
        "initial": initial.model_id,
        "selected": updated.model_id,
    }
    summaries = []
    for panel in assessment.panel_plan(cfg):
        folder = base / panel["name"]
        model_id = models[panel["round"]]
        terminal = 0
        floors = 0
        for seed_id in panel["ids"]:
            failed = panel["name"] == "development-selected" and seed_id == 4
            floor = (
                (100 if failed else 14)
                if panel["name"] == "development-selected"
                else (10 if panel["partition"] == "development" else panel["round"] + 1)
            )
            terminal += not failed
            floors += floor
            seed = seed_map[seed_id]
            rng_source = (
                f"7|{panel['name']}|{seed_id}"
                if panel["partition"] == "train"
                else f"8|frozen-policy-evaluation|{seed_id}"
            )
            public_input = public()
            trace = folder / f"case-{seed_id}.jsonl.gz"
            trace.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(trace, "wt") as stream:
                stream.write(
                    json.dumps(
                        {
                            "public_input": public_input,
                            "public_key": "synthetic-public-state",
                            "choice": {
                                "action_index": 1,
                                "model_id": model_id,
                                "public_input_id": manifest_identifier(public_input),
                                "behavior": "sampled_softmax",
                                "temperature": 0.8,
                            },
                        }
                    )
                    + "\n"
                )
            doc = {
                "schema_version": "actual-engine-on-policy-experience-v1",
                "binding": {
                    "environment_id": env_id,
                    "config_id": manifest_identifier(cfg),
                    "seed_manifest_id": seeds["manifest_id"],
                    "seed_id": seed_id,
                    "native_seed": seed["seed"],
                    "partition": panel["partition"],
                    "panel": panel["name"],
                    "model_id": model_id,
                    "training_spec_id": score.spec_id,
                    "sampling_seed": int.from_bytes(
                        hashlib.sha256(rng_source.encode()).digest()[:8], "big"
                    ),
                    "behavior": "sampled_softmax",
                    "panel_purpose": (
                        "training" if panel["partition"] == "train" else "frozen_policy_evaluation"
                    ),
                },
                "episode": {
                    "status": "failed" if failed else "terminal",
                    "seed": seed["seed"],
                    "privileged_fixture": False,
                    "recovered": False,
                    "victory": False,
                    "native_ending_evidence_agrees": not failed,
                    "private_final_identity": {
                        "native_game_over": True,
                        "native_player_dead": True,
                        "native_victory_room": False,
                    },
                    "cpu_seconds": 1.0,
                    "maximum_floor": floor,
                    "completed_acts": 0,
                    "worker_workspace": f"{panel['name']}/worker-0",
                    "error": "synthetic unsupported state" if failed else None,
                },
                "decision_count": 1,
                "trace_file_sha256": _sha_file(trace),
            }
            reseal_case(trace.with_suffix("").with_suffix(".json"), doc)
        summary = {
            "panel": panel["name"],
            "model_id": model_id,
            "planned_games": len(panel["ids"]),
            "completed_games": terminal,
            "failed_games": len(panel["ids"]) - terminal,
            "not_attempted_games": 0,
            "wins": 0,
            "mean_floor": floors / len(panel["ids"]),
            "decisions": len(panel["ids"]),
        }
        write(folder / "summary.json", summary)
        summaries.append(summary)
        worker = folder / "worker-0"
        (worker / "source-at-launch").mkdir(parents=True)
        (worker / "source-at-launch/historical.mjs").write_bytes(b"old worker")
        (worker / "closed.json").write_text("synthetic closure")
        write(
            worker / "experience-audit.json",
            {
                "valid": True,
                "games": terminal,
                "excluded_failed_games": len(panel["ids"]) - terminal,
                "decisions": terminal,
                "source_sha256": {"closed.json": _sha_file(worker / "closed.json")},
            },
            "report_id",
        )
    write(
        base / "summary.json",
        {
            "schema_version": "actual-engine-neural-experiment-report-v1",
            "status": "bounded_pilot_complete_with_failures",
            "config_id": manifest_identifier(cfg),
            "environment_id": env_id,
            "training_spec_id": score.spec_id,
            "seed_manifest_id": seeds["manifest_id"],
            "implementation_sha256": cfg["implementation_sha256"],
            "evaluation_policy": cfg["evaluation_policy"],
            "initial_model_id": initial.model_id,
            "selected_model_id": updated.model_id,
            "checks": dict.fromkeys(
                (
                    "account_profile_unchanged",
                    "candidate_unchanged",
                    "frozen_archive_unchanged",
                    "runtime_unchanged",
                    "sdk_unchanged",
                ),
                True,
            ),
            "error": None,
            "worker_failures": 0,
            "planned_games": 7,
            "recorded_games": 7,
            "completed_games": 6,
            "failed_games": 1,
            "not_attempted_games": 0,
            "optimizer_steps": 1,
            "sampled_decisions_verified": 1,
            "rounds": [update],
            "panels": summaries,
        },
        "report_id",
    )
    return tmp_path, config_path


def test_failed_game_cannot_make_progress_look_good(pilot: tuple[Path, Path]) -> None:
    root, config = pilot
    report = assessment.assess_completed_pilot(root, config)
    assert report["accounting"]["planned_games"] == 7
    assert report["accounting"]["failed_games"] == 1
    dev = report["panels"][-1]
    assert dev["mean_floor_reached_diagnostic"] == 57
    assert dev["mean_floor_completed_only_diagnostic"] == 14
    assert dev["mean_floor_failures_zero"] == 7
    assert report["comparison"]["mean_floor_difference_failures_zero"] == -3
    assert report["verdict"] == "no_clear_improvement"
    assert report["checkpoint_promoted"] is report["base_readiness_passed"] is False
    assert report["games_launched"] == report["optimizer_steps"] == 0
    assert report["terminal_action_verbs"] == {"skip": 6}
    assert len(report["failures"]) == 1
    assert "historical.py" in str(report["source_files"])


@pytest.mark.parametrize(
    "fault",
    [
        "wrong_rng",
        "seed_leakage",
        "win_flag",
        "cpu",
        "trace_hash",
        "choice",
        "public_identity",
        "missing_ending",
    ],
)
def test_rejects_corrupted_or_misbound_saved_cases(
    pilot: tuple[Path, Path],
    fault: str,
) -> None:
    root, config = pilot
    path = root / "artifacts/pilot/development-selected/case-3.json"
    doc = json.loads(path.read_text())
    if fault == "wrong_rng":
        doc["binding"]["sampling_seed"] += 1
    elif fault == "seed_leakage":
        doc["binding"]["partition"] = "train"
    elif fault == "win_flag":
        doc["episode"]["victory"] = True
    elif fault == "missing_ending":
        del doc["episode"]["private_final_identity"]["native_player_dead"]
    elif fault == "cpu":
        doc["episode"]["cpu_seconds"] = 129
    elif fault == "trace_hash":
        doc["trace_file_sha256"] = "bad"
    else:
        trace = path.with_suffix(".jsonl.gz")
        with gzip.open(trace, "rt") as stream:
            row = json.loads(stream.read())
        row["choice"]["action_index" if fault == "choice" else "public_input_id"] = 999
        with gzip.open(trace, "wt") as stream:
            stream.write(json.dumps(row) + "\n")
        doc["trace_file_sha256"] = _sha_file(trace)
    reseal_case(path, doc)
    with pytest.raises(ValueError):
        assessment.assess_completed_pilot(root, config)


@pytest.mark.parametrize(
    "fault",
    [
        "missing_case",
        "changed_audit_source",
        "selection_freeze",
        "changed_launch_source",
        "denominator",
        "summary_seal",
    ],
)
def test_rejects_missing_evidence_and_changed_selection(
    pilot: tuple[Path, Path],
    fault: str,
) -> None:
    root, config = pilot
    base = root / "artifacts/pilot"
    if fault == "missing_case":
        (base / "development-selected/case-3.json").unlink()
    elif fault == "changed_audit_source":
        (base / "development-selected/worker-0/closed.json").write_text("changed")
    elif fault == "selection_freeze":
        freeze = json.loads((base / "selection-freeze.json").read_text())
        freeze["development_opened"] = True
        write(base / "selection-freeze.json", freeze)
    elif fault == "changed_launch_source":
        (base / "source-at-launch/historical.py").write_text("new learner")
    else:
        summary = json.loads((base / "summary.json").read_text())
        summary["planned_games"] = 6
        write(base / "summary.json", summary, "report_id" if fault == "denominator" else None)
    with pytest.raises(ValueError):
        assessment.assess_completed_pilot(root, config)


def recipe(root: Path, config: Path) -> Path:
    return_path = root / "assessment.json"
    write(
        return_path,
        {
            "schema_version": "native-pilot-assessment-config-v1",
            "assessment_policy": assessment.POLICY,
            "implementation_sha256": _sha_file(Path(assessment.__file__)),
            "experiment_config": str(config.relative_to(root)),
            "experiment_config_id": manifest_identifier(json.loads(config.read_text())),
            "workspace": "artifacts/assessment",
            "bootstrap_replicates": 2000,
            "bootstrap_seed": 11,
            "resource_limits": {"wall_seconds": 180},
        },
    )
    return return_path


def test_waits_without_reading_live_episodes_or_creating_output(pilot: tuple[Path, Path]) -> None:
    root, config = pilot
    (root / "artifacts/pilot/summary.json").unlink()
    # Deliberately unreadable partial JSON would fail if touched.
    (root / "artifacts/pilot/development-selected/case-3.json").write_text("unfinished")
    result = assessment.run_assessment(root, recipe(root, config))
    assert result["status"] == "awaiting_completed_pilot"
    assert not (root / "artifacts/assessment").exists()


def test_stopped_pilot_has_no_quality_verdict(pilot: tuple[Path, Path]) -> None:
    root, config = pilot
    path = root / "artifacts/pilot/summary.json"
    summary = json.loads(path.read_text())
    summary.update(
        status="stopped_incomplete",
        error="synthetic stopped worker",
        completed_games=3,
        failed_games=0,
        recorded_games=3,
        not_attempted_games=4,
        panels=summary["panels"][:3],
    )
    write(path, summary, "report_id")
    (root / "artifacts/pilot/development-selected/case-3.json").write_text("unfinished")
    result = assessment.run_assessment(root, recipe(root, config))
    assert result["status"] == "pilot_stopped_before_complete_assessment"
    saved = json.loads((root / "artifacts/assessment/report.json").read_text())
    assert saved["comparison"] is None
    assert "verdict" not in saved
    assert saved["not_attempted_games"] == 4


def test_cached_assessment_verifies_sources_without_reselection(pilot: tuple[Path, Path]) -> None:
    root, config = pilot
    path = recipe(root, config)
    result = assessment.run_assessment(root, path)
    saved = assessment.run_assessment(root, path)
    assert saved["status"] == "saved_assessment_verified"
    assert saved["report_id"] == result["report_id"]
    assert "failures zero" in (root / "artifacts/assessment/report.md").read_text()
    (root / "artifacts/pilot/development-selected/case-3.json").write_text("changed")
    with pytest.raises(ValueError, match="sources changed"):
        assessment.run_assessment(root, path)


def test_exact_win_uncertainty_does_not_vanish_with_zero_wins() -> None:
    low, high = assessment.binomial_interval(0, 16)
    assert low == 0
    assert high == pytest.approx(1 - 0.025 ** (1 / 16))
    assert assessment.binomial_interval(16, 16) == pytest.approx([1 - high, 1])
    assert assessment.binomial_interval(5, 10) == pytest.approx([0.1870860284, 0.8129139716])
    rows = [{"seed_id": i, "win": False, "floor_zero": 10} for i in range(16)]
    result = assessment.paired_comparison(rows, rows, replicates=2000, salt=0)
    assert result["victory_difference_95_interval"][0] < 0
    assert result["victory_difference_95_interval"][1] > 0
    assert result["victory_improvement_supported"] is False


def test_seed_pair_bootstrap_and_win_first_interpretation() -> None:
    initial = [{"seed_id": i, "win": False, "floor_zero": 10} for i in range(16)]
    selected = [{"seed_id": i, "win": True, "floor_zero": 11} for i in range(16)]
    result = assessment.paired_comparison(initial, selected, replicates=1000, salt=7)
    assert result["victory_improvement_supported"] is True
    assert result["floor_difference_95_interval"] == [1, 1]
    selected = [
        {**r, "win": False, "floor_zero": 9 if i % 2 else 11} for i, r in enumerate(initial)
    ]
    result = assessment.paired_comparison(initial, selected, replicates=1000, salt=7)
    assert result == assessment.paired_comparison(initial, selected, replicates=1000, salt=7)
    assert result["mean_floor_difference_failures_zero"] == 0
    assert result["floor_difference_95_interval"][0] < 0 < result["floor_difference_95_interval"][1]
    with pytest.raises(ValueError, match="not paired"):
        assessment.paired_comparison(initial, selected[::-1], replicates=1000, salt=7)
    with pytest.raises(ValueError, match="independent"):
        assessment.paired_comparison(initial[:1] * 16, initial[:1] * 16, replicates=1000, salt=7)


def test_missing_attempts_stay_in_original_denominator() -> None:
    metrics = assessment.panel_metrics(
        [
            {
                "terminal": True,
                "win": False,
                "floor_zero": 10,
                "floor_reached": 10,
                "completed_acts": 0,
                "decisions": 3,
                "cpu_seconds": 1,
                "auxiliary_progress_return": 0.01,
            }
        ],
        2,
    )
    assert metrics["not_attempted_games"] == 1
    assert metrics["mean_floor_failures_zero"] == 5
    assert metrics["mean_floor_completed_only_diagnostic"] == 10


@pytest.mark.parametrize("fault", ["cap", "replicates", "output", "source_hash"])
def test_assessment_recipe_cannot_remove_caps_or_overwrite_the_pilot(
    pilot: tuple[Path, Path],
    fault: str,
) -> None:
    root, config = pilot
    path = recipe(root, config)
    doc = json.loads(path.read_text())
    if fault == "cap":
        doc["resource_limits"]["wall_seconds"] = float("inf")
    elif fault == "replicates":
        doc["bootstrap_replicates"] = 0
    elif fault == "output":
        doc["workspace"] = "artifacts/pilot/subfolder"
    else:
        doc["implementation_sha256"] = "changed"
    write(path, doc)
    with pytest.raises(ValueError):
        assessment.run_assessment(root, path)
    assert not (root / "artifacts/assessment").exists()


def test_current_learner_changes_do_not_invalidate_historical_source_bytes(
    pilot: tuple[Path, Path],
) -> None:
    root, config = pilot
    (root / "src/spireshift").mkdir(parents=True)
    (root / "src/spireshift/historical.py").write_text("a later, different implementation")
    result = assessment.assess_completed_pilot(root, config)
    assert result["status"] == "completed_saved_assessment"
    # Source-at-launch bytes, rather than current code, were checked above.
    (root / "artifacts/pilot/source-at-launch/historical.py").write_text("changed launch bytes")
    with pytest.raises(ValueError, match="learner source"):
        assessment.assess_completed_pilot(root, config)


def test_confirmation_selection_uses_the_actual_act_and_floor_score(
    pilot: tuple[Path, Path],
) -> None:
    root, config = pilot
    base = root / "artifacts/pilot"
    summary = json.loads((base / "summary.json").read_text())
    for label, floor, acts in (("initial-confirmation", 20, 1), ("round-001-confirmation", 30, 0)):
        path = base / label / "case-2.json"
        case = json.loads(path.read_text())
        case["episode"].update(maximum_floor=floor, completed_acts=acts)
        reseal_case(path, case)
        panel = next(p for p in summary["panels"] if p["panel"] == label)
        panel["mean_floor"] = floor
        write(base / label / "summary.json", panel)
    write(base / "summary.json", summary, "report_id")
    # Raw floor would incorrectly accept the updated checkpoint. Native selection
    # prioritizes the completed act via the bounded auxiliary return instead.
    with pytest.raises(ValueError, match="confirmation-only rule"):
        assessment.assess_completed_pilot(root, config)


def test_stopped_worker_error_files_are_hashed_and_shown(pilot: tuple[Path, Path]) -> None:
    root, config = pilot
    base = root / "artifacts/pilot"
    summary = json.loads((base / "summary.json").read_text())
    summary.update(status="stopped_incomplete", error="synthetic missing worker", worker_failures=1)
    write(base / "summary.json", summary, "report_id")
    worker_error = base / "round-001-sampled/worker-9-failure.json"
    write(
        worker_error,
        {"error": "spawnSync git ETIMEDOUT", "recorded_games": 0, "replacement_started": False},
    )
    result = assessment.run_assessment(root, recipe(root, config))
    assert result["verdict"] is None
    markdown = (root / "artifacts/assessment/report.md").read_text()
    assert "spawnSync git ETIMEDOUT" in markdown
    assert "1 training rounds" in markdown
    worker_error.write_text("changed error")
    with pytest.raises(ValueError, match="sources changed"):
        assessment.run_assessment(root, root / "assessment.json")
