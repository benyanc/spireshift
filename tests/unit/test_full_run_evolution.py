from __future__ import annotations

import copy
import json
import random
from concurrent.futures import Future
from pathlib import Path
from typing import Any

import pytest
from test_full_run_policy import CATALOG, model

from spireshift.cli import main
from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_evolution import (
    EpisodeStore,
    EvolutionConfig,
    _run_locked,
    evolution_protocol,
    inspect_evolution,
    load_evolution_config,
    mutate_genome,
    population_models,
)
from spireshift.full_run_experience import atomic_json, case_binding, save_episode
from spireshift.full_run_policy import FullRunPolicy, load_full_run_model
from spireshift.training_objective import TrainingOutcome, score_training_outcome

CONFIG = Path("configs/full-run-evolution/sts2-v0.107.1-unified-pilot-v1.json")


def small_config() -> EvolutionConfig:
    d = copy.deepcopy(load_evolution_config(CONFIG).document)
    d["workers"] = 1
    d["network"].update(dimension=128, hidden_units=4)
    e = d["evolution"]
    e.update(population_size=4, maximum_generations=2, elite_count=2, plateau_generations=2)
    e["generation_train_seeds"] = [p[:2] for p in e["generation_train_seeds"][:2]]
    e["confirmation_train_seeds"] = [p[:2] for p in e["confirmation_train_seeds"][:2]]
    e["development_seeds"] = e["development_seeds"][:2]
    d["config_id"] = manifest_identifier({k: v for k, v in d.items() if k != "config_id"})
    return EvolutionConfig.from_mapping(d)


def test_seed_panels_reject_leakage_and_duplicate_generation_seeds() -> None:
    for mutation in ("test", "duplicate", "objective"):
        d = copy.deepcopy(small_config().document)
        if mutation == "test":
            d["evolution"]["development_seeds"][0] = 100001  # replace below with a real test seed
            from spireshift.splits import SplitName

            d["evolution"]["development_seeds"][0] = small_config().splits.seeds(SplitName.TEST)[0]
        elif mutation == "duplicate":
            d["evolution"]["generation_train_seeds"][1][0] = d["evolution"][
                "generation_train_seeds"
            ][0][0]
        else:
            d["inputs"]["training_spec"]["id"] = "sha256:" + "f" * 64
        d["config_id"] = manifest_identifier({k: v for k, v in d.items() if k != "config_id"})
        with pytest.raises(ValueError):
            EvolutionConfig.from_mapping(d)


def test_whole_genome_evolution_is_deterministic_and_can_change_every_layer() -> None:
    source = model()
    a = mutate_genome(source, random.Random(12), 0.2, 1.0)
    b = mutate_genome(source, random.Random(12), 0.2, 1.0)
    assert a.genome == b.genome
    assert all(before != after for before, after in zip(source.genome, a.genome, strict=True))
    config = small_config()
    first, lineage = population_models(config, source, source, [source], 0)
    second, other_lineage = population_models(config, source, source, [source], 0)
    assert [m.model_id for m in first] == [m.model_id for m in second]
    assert lineage == other_lineage
    assert len({m.model_id for m in first}) == 4
    assert first[0].model_id == source.model_id


class ImmediateExecutor:
    """Synthetic outcomes only: no native game, process or long experiment is started."""

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
        future: Future[dict[str, Any]] = Future()
        if self.fail_next:
            self.fail_next = False
            future.set_exception(RuntimeError("synthetic worker failure"))
            return future
        config = load_evolution_config(Path(request["config_path"]))
        m = load_full_run_model(Path(request["model_path"]))
        binding = case_binding(
            config.ruleset,
            FullRunPolicy(config.ruleset, m),
            config.score,
            request["seed"],
            request["partition"],
            config.splits.manifest_id,
            config.document["maximum_decisions"],
        )
        # A reproducible toy score tests selection/control flow, not gameplay strength.
        outcome = TrainingOutcome.from_mapping(
            {
                "seed": request["seed"],
                "status": "terminal_loss",
                "completed_acts": 0,
                "maximum_floor": 10 + int(abs(m.genome[0]) * 100),
                "decisions": 0,
                "cpu_seconds": 0.001,
            }
        )
        body = {
            "schema_version": "unified-full-run-experience-v1",
            "binding": binding,
            "outcome": {
                "seed": outcome.seed,
                "status": outcome.status.value,
                "completed_acts": outcome.completed_acts,
                "maximum_floor": outcome.maximum_floor,
                "decisions": outcome.decisions,
                "cpu_seconds": outcome.cpu_seconds,
            },
            "trace_digest": manifest_identifier([]),
            "score": score_training_outcome(config.score, outcome),
        }
        case = {**body, "case_id": manifest_identifier(body)}
        save_episode(Path(request["case_path"]), case, [])
        future.set_result(case)
        return future


def test_finite_pipeline_resumes_exact_population_and_freezes_before_development(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = small_config()
    config_path = tmp_path / "config.json"
    atomic_json(config_path, config.document)
    import spireshift.full_run_evolution as module

    monkeypatch.setattr(module, "ProcessPoolExecutor", ImmediateExecutor)
    monkeypatch.setattr(module, "load_printed_card_catalog", lambda *args: CATALOG)
    ImmediateExecutor.requests = []
    root = tmp_path / "pilot"
    root.mkdir()
    report = _run_locked(config, config_path, root, evolution_protocol(config))
    assert report["generations_completed"] <= 2
    assert report["checkpoint_promoted"] is False
    assert report["all_episode_costs_known"] is True
    assert report["experience_cases"] == len(ImmediateExecutor.requests)
    first_dev = next(
        i for i, r in enumerate(ImmediateExecutor.requests) if r["partition"] == "development"
    )
    assert all(r["partition"] == "train" for r in ImmediateExecutor.requests[:first_dev])
    assert all(r["partition"] == "development" for r in ImmediateExecutor.requests[first_dev:])
    before = len(ImmediateExecutor.requests)
    assert inspect_evolution(config_path, root)["report_id"] == report["report_id"]
    # Simulate losing only the final report before resumption; source cases/populations
    # stay immutable and no already completed attempt is rerun.
    (root / "evolution-report.json").unlink()
    resumed = _run_locked(config, config_path, root, evolution_protocol(config))
    assert len(ImmediateExecutor.requests) == before
    assert resumed["champion_model_id"] == report["champion_model_id"]
    assert resumed["current_launch_games"] == 0
    assert (
        json.loads((root / "train-selection.json").read_text())["champion_id"]
        == report["champion_model_id"]
    )


def test_worker_failure_is_retained_and_not_retried_as_free_data(
    tmp_path: Path,
) -> None:
    config = small_config()
    path = tmp_path / "config.json"
    atomic_json(path, config.document)
    from spireshift.full_run_policy import initial_full_run_model

    initial = initial_full_run_model(
        config.ruleset, CATALOG, "a" * 64, dimension=128, hidden_units=4
    )
    executor = ImmediateExecutor()
    executor.fail_next = True
    store = EpisodeStore(config, tmp_path / "pilot", path, executor)  # type: ignore[arg-type]
    seeds = config.document["evolution"]["generation_train_seeds"][0]
    results = store.evaluate([initial], seeds, "train", "synthetic")
    assert results[initial.model_id]["summary"]["benchmark_denominator"] == 2
    assert results[initial.model_id]["summary"]["failed_runs"] == 1
    requested = len(ImmediateExecutor.requests)
    resumed = EpisodeStore(config, tmp_path / "pilot", path, executor)  # type: ignore[arg-type]
    again = resumed.evaluate([initial], seeds, "train", "synthetic resume")
    assert again == results
    assert len(ImmediateExecutor.requests) == requested


def test_owner_command_caps_match_frozen_config_and_cli_does_not_start_unwrapped_job(
    capsys: Any,
) -> None:
    config = load_evolution_config(CONFIG)
    script = Path("scripts/evolve-full-run-policy-v1.sh").read_text()
    for flag, key in (
        ("max-wall-seconds", "wall_seconds"),
        ("max-cpu-seconds", "cpu_seconds"),
        ("max-storage-bytes", "storage_bytes"),
        ("max-memory-bytes", "memory_bytes"),
    ):
        assert f"--{flag} {config.document['resource_limits'][key]}" in script
    assert main(["full-run", "inspect-config", str(CONFIG)]) == 0
    assert json.loads(capsys.readouterr().out)["maximum_planned_game_attempts"] == 832
    assert main(["full-run", "evolve", str(CONFIG), "artifacts/never-started-test"]) == 1
    assert "resource caps" in capsys.readouterr().out
