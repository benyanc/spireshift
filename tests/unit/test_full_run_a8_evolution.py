from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from test_full_run_ppo import ImmediateExecutor, small_config
from test_full_run_public_policy import CATALOG

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_a8_evolution import (
    CONFIG_SCHEMA,
    A8EvolutionConfig,
    population,
    run_locked,
    show,
    source_assessment,
)
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_ppo import frozen_json
from spireshift.splits import SplitName


@pytest.fixture
def recipe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    import spireshift.full_run_a8_evolution as evolution
    import spireshift.full_run_ppo as ppo

    monkeypatch.setattr(ImmediateExecutor, "requests", [])
    monkeypatch.setattr(ImmediateExecutor, "fail_next", False)
    monkeypatch.setattr(ppo, "ThreadPoolExecutor", ImmediateExecutor)
    monkeypatch.setattr(evolution, "ThreadPoolExecutor", ImmediateExecutor)
    monkeypatch.setattr(ppo, "load_printed_card_catalog", lambda *args: CATALOG)
    collector = small_config()
    collector_path = tmp_path / "collector.json"
    atomic_json(collector_path, collector.document)
    source_root = tmp_path / "ppo-source"
    source_root.mkdir()
    report = ppo.run_locked(collector, collector_path, source_root, ppo.ppo_protocol(collector))
    assessment = source_assessment(collector, source_root)
    used = set(assessment["source_used_seeds"])
    train = [s for s in collector.splits.seeds(SplitName.TRAIN) if s not in used]
    dev = [s for s in collector.splits.seeds(SplitName.VALIDATION) if s not in used]
    cost = frozen_json(
        tmp_path / "source-resources.json",
        {
            "schema_version": "experiment-resources-v1",
            "experiment_kind": "training",
            "artifacts": {"roots": [str(source_root.resolve())]},
            "usage": {
                "wall_seconds": 1.0,
                "cpu_seconds": 2.0,
                "trajectories": report["experience_cases"],
            },
        },
        "report_id",
    )
    body = {
        "schema_version": CONFIG_SCHEMA,
        "inputs": {
            "collector_config": {"path": str(collector_path), "id": collector.config_id},
            "ppo_output": str(source_root),
            "ppo_report_id": report["report_id"],
            "additional_inspected_development_seeds": [],
            "source_resource_reports": [
                {"path": str(tmp_path / "source-resources.json"), "id": cost["report_id"]}
            ],
        },
        "evolution": {
            "population_size": 4,
            "elite_count": 2,
            "maximum_generations": 2,
            "minimum_generations": 2,
            "confirmation_every": 1,
            "plateau_confirmations": 2,
            "generation_train_seeds": [train[:2], train[2:4]],
            "confirmation_train_seeds": train[4:6],
            "development_seeds": dev[:2],
            "mutation_probability": 1.0,
            "mutation_scales": [0.01, 0.03, 0.1],
            "rng_seed": 7,
        },
        "resource_limits": {
            "wall_seconds": 120,
            "cpu_seconds": 240,
            "storage_bytes": 1000000000,
            "memory_bytes": 4000000000,
        },
    }
    path = tmp_path / "evolution.json"
    frozen_json(path, body, "config_id")
    return path


def rewrite(path: Path, document: dict[str, Any]) -> None:
    document["config_id"] = manifest_identifier(
        {k: v for k, v in document.items() if k != "config_id"}
    )
    path.write_text(json.dumps(document))


def test_source_assessment_is_outcome_only_and_counts_prior_launches(recipe: Path) -> None:
    config = A8EvolutionConfig.load(recipe)
    assert config.source["games_replayed"] == 0
    assert config.source["optimizer_steps"] == 0
    assert config.source["compressed_traces_reaudited"] is False
    assert config.source["prior_PPO_resources"]["cpu_seconds"] == 2
    assert config.source["paired_development"]["planned_pairs"] == 2


@pytest.mark.parametrize(
    "wrong", ["final_test", "source_train", "source_dev", "duplicate", "inspected"]
)
def test_reserved_and_inspected_seeds_are_rejected(recipe: Path, wrong: str) -> None:
    config = A8EvolutionConfig.load(recipe)
    d = copy.deepcopy(config.document)
    e = d["evolution"]
    if wrong == "final_test":
        e["development_seeds"][0] = config.collector.splits.seeds(SplitName.TEST)[0]
    elif wrong == "source_train":
        e["generation_train_seeds"][0][0] = config.collector.document["learning"][
            "rollout_seed_panels"
        ][0][0]
    elif wrong == "source_dev":
        e["development_seeds"][0] = config.collector.document["learning"]["development_seeds"][0]
    elif wrong == "duplicate":
        e["generation_train_seeds"][1][0] = e["generation_train_seeds"][0][0]
    else:
        d["inputs"]["additional_inspected_development_seeds"] = [e["development_seeds"][0]]
    rewrite(recipe, d)
    with pytest.raises(ValueError, match="overlap|partitions"):
        A8EvolutionConfig.load(recipe)


def test_missing_prior_cost_cannot_be_treated_as_free_training(recipe: Path) -> None:
    d = json.loads(recipe.read_text())
    d["inputs"]["source_resource_reports"] = []
    rewrite(recipe, d)
    with pytest.raises(ValueError, match="prior PPO launch costs"):
        A8EvolutionConfig.load(recipe)


def test_mutations_change_every_actor_layer_but_keep_the_critic(recipe: Path) -> None:
    config = A8EvolutionConfig.load(recipe)
    a, lineage = population(config, config.ppo, [config.ppo], 0)
    b, second = population(config, config.ppo, [config.ppo], 0)
    assert [m.as_dict() for m in a] == [m.as_dict() for m in b]
    assert lineage == second
    assert len({m.model_id for m in a}) == 4
    mutated = [m for m, entry in zip(a, lineage, strict=True) if entry["parent_model_id"]]
    assert mutated
    assert all(m.value_weights == config.ppo.value_weights for m in mutated)
    assert all(
        old != new
        for old, new in zip(config.ppo.actor.genome, mutated[0].actor.genome, strict=True)
    )


def test_source_cannot_substitute_a_different_players_development_cases(recipe: Path) -> None:
    d = json.loads(recipe.read_text())
    source_root = Path(d["inputs"]["ppo_output"])
    report_path = source_root / "ppo-report.json"
    report = json.loads(report_path.read_text())
    report["development"][report["initial_model_id"]]["model_id"] = "sha256:" + "f" * 64
    report["report_id"] = manifest_identifier({k: v for k, v in report.items() if k != "report_id"})
    report_path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="frozen seed/model"):
        A8EvolutionConfig.load(recipe)


def test_interrupted_generation_resumes_without_replaying_finished_games(
    recipe: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import spireshift.full_run_a8_evolution as evolution

    config = A8EvolutionConfig.load(recipe)
    root = tmp_path / "interrupted-result"
    root.mkdir()
    original = frozen_json

    def interrupt(path: Path, body: dict[str, Any], key: str) -> dict[str, Any]:
        if path.name == "generation-001.json":
            raise OSError("simulated interruption before generation checkpoint")
        return original(path, body, key)

    monkeypatch.setattr(evolution, "frozen_json", interrupt)
    ImmediateExecutor.requests = []
    with pytest.raises(OSError, match="simulated interruption"):
        run_locked(config, root)
    completed_requests = list(ImmediateExecutor.requests)
    monkeypatch.setattr(evolution, "frozen_json", original)
    result = run_locked(config, root)
    # Only the not-yet-started development panel may be collected after resume.
    new_requests = ImmediateExecutor.requests[len(completed_requests) :]
    assert all(request["partition"] == "development" for request in new_requests)
    assert result["generations_completed"] == 2
    assert show(config, root) == result


def test_finite_pipeline_uses_common_panels_freezes_and_resumes_without_games(
    recipe: Path,
    tmp_path: Path,
) -> None:
    config = A8EvolutionConfig.load(recipe)
    root = tmp_path / "evolution-result"
    root.mkdir()
    ImmediateExecutor.requests = []
    result = run_locked(config, root)
    assert result["generations_completed"] == 2
    assert result["optimizer_steps"] == 0
    assert result["final_test_opened"] is False
    assert result["checkpoint_promoted"] is False
    assert result["protocol"]["comparison_scope"].startswith("additional_hybrid_stage")
    for i, seeds in enumerate(config.document["evolution"]["generation_train_seeds"]):
        stage = json.loads((root / f"generation-{i:03d}.json").read_text())
        assert len(stage["panels"]) == 4
        assert all(p["seeds"] == seeds for p in stage["panels"])
    assert (root / "train-selection.json").stat().st_mtime_ns <= (
        root / "evolution-report.json"
    ).stat().st_mtime_ns
    before = len(ImmediateExecutor.requests)
    assert run_locked(config, root) == result
    assert show(config, root) == result
    assert len(ImmediateExecutor.requests) == before
    # Neither cached reading nor explicit resume starts a backend or optimizer.
    changed = json.loads((root / "generation-000.json").read_text())
    changed["champion_model_id"] = "sha256:" + "f" * 64
    (root / "generation-000.json").write_text(json.dumps(changed))
    with pytest.raises(ValueError):
        run_locked(config, root)


def test_failed_candidate_stays_in_its_original_denominator(recipe: Path, tmp_path: Path) -> None:
    config = A8EvolutionConfig.load(recipe)
    ImmediateExecutor.fail_next = True
    root = tmp_path / "failed-result"
    root.mkdir()
    result = run_locked(config, root)
    assert result["interrupted_or_worker_failed_attempts"] == 1
    assert result["all_episode_costs_known"] is False
    cases = [json.loads((root / ref["path"]).read_text()) for ref in result["cases"]]
    failures = [case for case in cases if case["outcome"]["status"] == "runtime_error"]
    assert len(failures) == 1
    assert failures[0]["outcome"]["maximum_floor"] == 0
