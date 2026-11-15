from __future__ import annotations

import copy
import json
from concurrent.futures import Future
from pathlib import Path
from typing import Any

import pytest
from test_full_run_public_policy import CATALOG, MenuRun, environment

from spireshift.adapters.evangambit_public_choices import PublicChoiceEnvironment
from spireshift.cli import main
from spireshift.core.manifest import load_patch_manifest, manifest_identifier
from spireshift.full_run_a8_experience import collect_a8_episode
from spireshift.full_run_experience import atomic_json, save_episode
from spireshift.full_run_ppo import (
    ExperienceStore,
    PPOConfig,
    inspect_ppo,
    load_actor_critic,
    load_ppo_config,
    ppo_protocol,
    run_locked,
    summarize_ppo,
)
from spireshift.full_run_ppo_math import initialize_critic
from spireshift.full_run_public_policy import initial_public_full_run_model
from spireshift.splits import SplitName

CONFIG = Path("configs/full-run-ppo/sts2-v0.107.1-public-a8-pilot-v1.json")


def small_config() -> PPOConfig:
    d = copy.deepcopy(load_ppo_config(CONFIG).document)
    d["network"].update(dimension=128, hidden_units=4)
    d["workers"] = 1
    p = d["learning"]
    p.update(
        maximum_rounds=2,
        minimum_rounds=2,
        confirmation_every=1,
        plateau_confirmations=2,
        epochs=1,
        minibatch_decisions=8,
    )
    p["rollout_seed_panels"] = [seeds[:2] for seeds in p["rollout_seed_panels"][:2]]
    p["confirmation_train_seeds"] = p["confirmation_train_seeds"][:2]
    p["development_seeds"] = p["development_seeds"][:2]
    d["config_id"] = manifest_identifier({k: v for k, v in d.items() if k != "config_id"})
    return PPOConfig.from_mapping(d)


class ImmediateExecutor:
    """Synthetic public menus, no native games and no separate processes."""

    requests: list[dict[str, Any]] = []
    fail_next = False

    def __init__(self, **kwargs: Any) -> None:
        pass

    def __enter__(self) -> ImmediateExecutor:
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def submit(self, function: Any, request: dict[str, Any]) -> Future[dict[str, Any]]:
        self.requests.append(request)
        result: Future[dict[str, Any]] = Future()
        if self.fail_next:
            self.fail_next = False
            result.set_exception(RuntimeError("Synthetic worker interruption"))
            return result
        c = load_ppo_config(Path(request["config_path"]))
        m = load_actor_critic(Path(request["model_path"]))
        layout = environment(MenuRun())._layout
        env = PublicChoiceEnvironment(
            lambda: MenuRun(),
            load_patch_manifest(Path(c.document["inputs"]["ruleset_manifest"]["path"])),
            layout,
            backend=MenuRun(),
        )
        case, trace = collect_a8_episode(
            lambda: env,
            c.ruleset,
            m,
            c.score,
            c.splits,
            seed=request["seed"],
            partition=request["partition"],
            behavior=request["behavior"],
            temperature=request["temperature"],
            sampling_seed=request["sampling_seed"],
            maximum_decisions=4096,
        )
        save_episode(Path(request["case_path"]), case, trace)
        result.set_result(case)
        return result


def test_reserved_or_repeated_seeds_and_wrong_a0_label_are_rejected() -> None:
    for name in ("final_test", "duplicate", "scope"):
        d = copy.deepcopy(small_config().document)
        if name == "final_test":
            d["learning"]["rollout_seed_panels"][0][0] = small_config().splits.seeds(
                SplitName.TEST
            )[0]
        elif name == "duplicate":
            d["learning"]["rollout_seed_panels"][1][0] = d["learning"]["rollout_seed_panels"][0][0]
        else:
            d["inputs"]["training_spec"] = {
                "path": "configs/training-objective/sts2-v0.107.1-full-run-bootstrap-v1.json",
                "id": "sha256:" + "1" * 64,
            }
        d["config_id"] = manifest_identifier({k: v for k, v in d.items() if k != "config_id"})
        with pytest.raises(ValueError):
            PPOConfig.from_mapping(d)


def test_finite_training_freezes_before_development_and_resumes_without_games(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = small_config()
    path = tmp_path / "config.json"
    atomic_json(path, config.document)
    import spireshift.full_run_ppo as module

    monkeypatch.setattr(module, "ThreadPoolExecutor", ImmediateExecutor)
    monkeypatch.setattr(module, "load_printed_card_catalog", lambda *args: CATALOG)
    ImmediateExecutor.requests = []
    output = tmp_path / "pilot"
    output.mkdir()
    protocol = ppo_protocol(config)
    report = run_locked(config, path, output, protocol)
    assert report["rounds_completed"] == 2
    assert sum(r["optimization"]["optimizer_steps"] for r in report["updates"]) > 0
    assert report["experience_cases"] == len(ImmediateExecutor.requests)
    assert report["all_episode_costs_known"]
    assert report["foundation_readiness_established"] is False
    requests = ImmediateExecutor.requests
    first_dev = next(i for i, r in enumerate(requests) if r["partition"] == "development")
    assert all(r["partition"] == "train" for r in requests[:first_dev])
    assert all(r["partition"] == "development" for r in requests[first_dev:])
    selection = json.loads((output / "train-selection.json").read_text())
    assert selection["selection_uses_development"] is False
    assert inspect_ppo(path, output)["report_id"] == report["report_id"]
    before = len(requests)
    (output / "ppo-report.json").unlink()
    resumed = run_locked(config, path, output, protocol)
    assert resumed["report_id"] == report["report_id"]
    assert len(requests) == before


def test_worker_failure_is_not_dropped_or_retried_on_resume(tmp_path: Path) -> None:
    config = small_config()
    path = tmp_path / "config.json"
    atomic_json(path, config.document)
    model = initialize_critic(
        initial_public_full_run_model(
            config.ruleset, CATALOG, "a" * 64, dimension=128, hidden_units=4
        )
    )
    executor = ImmediateExecutor()
    executor.fail_next = True
    store = ExperienceStore(config, path, tmp_path / "pilot", executor)  # type: ignore[arg-type]
    seeds = config.document["learning"]["rollout_seed_panels"][0]
    first, _ = store.panel(model, seeds, "train", round_index=0, label="Synthetic test")
    assert first["summary"]["benchmark_denominator"] == 2
    assert first["summary"]["failed_runs"] == 1
    assert any(c.get("cpu_seconds_known") is False for c in store.cases.values())
    before = len(executor.requests)
    resumed = ExperienceStore(config, path, tmp_path / "pilot", executor)  # type: ignore[arg-type]
    again, _ = resumed.panel(model, seeds, "train", round_index=0, label="Synthetic resume")
    assert again == first and len(executor.requests) == before


def test_owner_command_is_finite_and_unwrapped_training_is_blocked(capsys: Any) -> None:
    config = load_ppo_config(CONFIG)
    script = Path("scripts/train-full-run-ppo-a8-v1.sh").read_text()
    for flag, key in (
        ("max-wall-seconds", "wall_seconds"),
        ("max-cpu-seconds", "cpu_seconds"),
        ("max-storage-bytes", "storage_bytes"),
        ("max-memory-bytes", "memory_bytes"),
    ):
        assert f"--{flag} {config.document['resource_limits'][key]}" in script
    assert main(["full-run", "inspect-ppo-config", str(CONFIG)]) == 0
    assert json.loads(capsys.readouterr().out)["maximum_planned_game_attempts"] == 2112
    assert main(["full-run", "train-ppo", str(CONFIG), "artifacts/never-started-test"]) == 1
    assert "resource caps" in capsys.readouterr().out


def test_terminal_only_reference_uses_zero_loss_return_and_no_bootstrap_graduation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    d = copy.deepcopy(small_config().document)
    score = small_config().score.as_dict()
    score.update(training_objective_id="full-run-terminal-training-v1", stage="terminal_only")
    score["progress"]["loss_progress_weight"] = 0
    score_path = tmp_path / "terminal-score.json"
    atomic_json(score_path, score)
    from spireshift.training_objective import TrainingScoreSpec

    spec = TrainingScoreSpec.from_mapping(score)
    d["inputs"]["training_spec"] = {"path": str(score_path), "id": spec.spec_id}
    d["learning"].update(maximum_rounds=1, minimum_rounds=1)
    d["learning"]["rollout_seed_panels"] = d["learning"]["rollout_seed_panels"][:1]
    d["config_id"] = manifest_identifier({k: v for k, v in d.items() if k != "config_id"})
    config = PPOConfig.from_mapping(d)
    path = tmp_path / "config.json"
    atomic_json(path, d)
    import spireshift.full_run_ppo as module

    monkeypatch.setattr(module, "ThreadPoolExecutor", ImmediateExecutor)
    monkeypatch.setattr(module, "load_printed_card_catalog", lambda *args: CATALOG)
    output = tmp_path / "terminal"
    output.mkdir()
    report = run_locked(config, path, output, ppo_protocol(config))
    assert report["graduation"] is None
    assert report["updates"][0]["sampled_training_panel"]["summary"]["mean_training_return"] == 0
    assert report["foundation_readiness_established"] is False


def test_interrupted_trace_is_retained_with_unknown_cost_and_never_replayed(tmp_path: Path) -> None:
    config = small_config()
    path = tmp_path / "config.json"
    atomic_json(path, config.document)
    model = initialize_critic(
        initial_public_full_run_model(
            config.ruleset,
            CATALOG,
            "a" * 64,
            dimension=128,
            hidden_units=4,
        )
    )
    executor = ImmediateExecutor()
    output = tmp_path / "pilot"
    store = ExperienceStore(config, path, output, executor)  # type: ignore[arg-type]
    seeds = config.document["learning"]["rollout_seed_panels"][0]
    _, keys = store.panel(model, seeds, "train", round_index=0, label="Synthetic source")
    completed = store.paths[keys[0]]
    # Simulate interruption after starting/writing the trace, before publishing its case.
    completed.unlink()
    assert completed.with_suffix(".jsonl.gz").exists()
    before = len(executor.requests)
    resumed = ExperienceStore(config, path, output, executor)  # type: ignore[arg-type]
    panel, _ = resumed.panel(model, seeds, "train", round_index=0, label="Synthetic resume")
    assert len(executor.requests) == before
    assert panel["summary"]["benchmark_denominator"] == 2
    assert panel["summary"]["failed_runs"] == 1
    failure = resumed.cases[keys[0]]
    assert failure["cpu_seconds_known"] is False
    assert failure["outcome"]["status"] == "runtime_error"


def test_same_checkpoint_is_not_reported_as_an_independent_model_gain() -> None:
    from spireshift.full_run_ppo import REPORT_SCHEMA

    report = {
        "schema_version": REPORT_SCHEMA,
        "report_id": "synthetic",
        "rounds_completed": 0,
        "stop_reason": "synthetic",
        "initial_model_id": "same",
        "champion_model_id": "same",
        "development": {"same": {"summary": {"failed_runs": 1}}},
        "paired_development": {
            "planned_pairs": 2,
            "both_completed": 1,
            "champion_only_victories": 0,
            "initial_only_victories": 0,
        },
        "updates": [],
        "experience_cases": 2,
        "public_decisions": 0,
        "champion_checkpoint": "model.json",
        "interrupted_or_worker_failed_attempts": 1,
        "all_episode_costs_known": False,
        "graduation": {},
    }
    # Explicit fake summaries validate reporting, never learning evidence.
    summary = summarize_ppo(report, Path("unused"))
    assert summary["development_status"] == "incomplete_with_failed_attempts"
    assert summary["paired_development"]["comparison_valid"] is False
    assert summary["paired_development"]["distinct_players"] is False


def test_native_teardown_failure_retains_a_completed_file_only_as_debug(tmp_path: Path) -> None:
    config = small_config()
    directory = tmp_path / "case"
    directory.mkdir()
    completed = directory / "case.json"
    completed.write_text('{"debug": "result written before native teardown"}')
    store = ExperienceStore(config, tmp_path / "config.json", tmp_path, ImmediateExecutor())  # type: ignore[arg-type]
    case = store.failure({"seed": 1}, directory / "failure.json", "Native teardown failed")
    assert not completed.exists()
    assert (directory / "post-crash-case.json").exists()
    assert "post-crash-case.json" in case["execution_evidence"]
    assert case["outcome"]["status"] == "runtime_error"
    assert case["cpu_seconds_known"] is False


def test_incomplete_development_marks_the_training_command_failed(
    monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    import spireshift.full_run_cli as module
    from spireshift.resource_tracking import EXPERIMENT_METRICS_ENV

    monkeypatch.setenv(EXPERIMENT_METRICS_ENV, "synthetic-not-used")
    monkeypatch.setattr(module, "run_ppo", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        module,
        "summarize_ppo",
        lambda *args: {"development_status": "incomplete_with_failed_attempts"},
    )
    assert main(["full-run", "train-ppo", str(CONFIG), "unused"]) == 1
    assert json.loads(capsys.readouterr().out)["development_status"].startswith("incomplete")


def test_repaired_owner_recipe_has_a_separate_scope_and_later_plateau_stop() -> None:
    newer = load_ppo_config(Path("configs/full-run-ppo/sts2-v0.107.1-public-a8-pilot-v2.json"))
    older = load_ppo_config(CONFIG)
    assert newer.ruleset.manifest_id != older.ruleset.manifest_id
    assert newer.splits.manifest_id != older.splits.manifest_id
    assert newer.document["learning"]["minimum_rounds"] == 24
    assert newer.document["learning"]["plateau_confirmations"] == 6
    script = Path("scripts/train-full-run-ppo-a8-v2.sh").read_text()
    for flag, key in (
        ("max-wall-seconds", "wall_seconds"),
        ("max-cpu-seconds", "cpu_seconds"),
        ("max-storage-bytes", "storage_bytes"),
        ("max-memory-bytes", "memory_bytes"),
    ):
        assert f"--{flag} {newer.document['resource_limits'][key]}" in script
