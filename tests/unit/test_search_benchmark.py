from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pytest

from spireshift.cli import main
from spireshift.fixed_search import FixedSearchConfig, FixedSearchTier, capture_combat_state
from spireshift.rollouts import sha256_file
from spireshift.search_benchmark import (
    SearchBenchmarkConfig,
    freeze_search_benchmark_state_set,
    load_search_benchmark_state_set,
    load_search_benchmark_state_set_document,
    run_search_compute_quality_benchmark,
    verify_search_compute_quality_report,
)
from spireshift.search_workers import (
    SearchBackendSpec,
    SearchWorkerEvidence,
    SearchWorkerRequest,
    SearchWorkerStatus,
)
from spireshift.splits import SplitName, load_split_manifest

PRODUCTION_SPLIT = Path("manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json")
PRODUCTION_STATE_SET = Path("manifests/benchmarks/sts2-v0.107.1-evangambit-validation-v1.json")
PRODUCTION_STATE_SPECIFICATION = Path(
    "configs/search-benchmark/sts2-v0.107.1-evangambit-validation-v1.json"
)


def _state_set_document() -> dict[str, object]:
    captured = capture_combat_state(
        backend=SearchBackendSpec.tactical_mock(),
        run_seed=7,
    )
    return freeze_search_benchmark_state_set(
        {
            "split_manifest_id": (
                "sha256:7010c687c42c5ecc47239da7ccd13ebd40d7af9be012b6774be63bb0a160dfe1"
            ),
            "ruleset_manifest_id": captured.checkpoint.ruleset_manifest_id,
            "objective_id": "terminal-victory-v1",
            "capture_policy_id": "terminal-victory-search-rollout-v1",
            "partition": "validation",
            "selection_policy": "predeclared-distinct-run-seeds-v1",
            "cases": [
                {
                    "state_id": "validation-seed-7-combat-0",
                    "run_seed": 7,
                    "combat_state_index": 0,
                    "expected_state_hash": captured.checkpoint.state_hash,
                    "expected_legal_actions": len(captured.legal_actions),
                }
            ],
        }
    )


def _configuration() -> SearchBenchmarkConfig:
    return SearchBenchmarkConfig(
        search=FixedSearchConfig(
            tiers=(
                FixedSearchTier("shallow", 3),
                FixedSearchTier("medium", 4),
                FixedSearchTier("expensive", 5),
            ),
            maximum_rollout_steps=8,
            workers=5,
            worker_timeout_seconds=30.0,
        ),
        evaluation_samples_per_candidate=2,
        evaluation_workers=6,
        evaluation_worker_timeout_seconds=30.0,
        calibration_bins=4,
    )


def test_state_set_is_content_addressed_and_rejects_tampering(tmp_path: Path) -> None:
    document = _state_set_document()
    path = tmp_path / "states.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    loaded = load_search_benchmark_state_set(path)

    assert loaded.state_set_id == document["state_set_id"]
    assert loaded.partition == "validation"
    tampered = dict(document)
    tampered["partition"] = "test"
    with pytest.raises(ValueError, match="identity mismatch"):
        load_search_benchmark_state_set_document(tampered)


def test_production_state_set_is_frozen_to_complete_validation_runs() -> None:
    split = load_split_manifest(PRODUCTION_SPLIT)
    state_set = load_search_benchmark_state_set(PRODUCTION_STATE_SET)
    specification = json.loads(PRODUCTION_STATE_SPECIFICATION.read_text(encoding="utf-8"))

    assert state_set.state_set_id == (
        "sha256:0d1acac2c99daad3b87f236e370c809bcc5a6b51c4dac1a0a1e7f3f395779076"
    )
    assert state_set.split_manifest_id == split.manifest_id
    assert len(state_set.cases) == 32
    assert (
        tuple(case.run_seed for case in state_set.cases) == split.seeds(SplitName.VALIDATION)[:32]
    )
    assert all(case.combat_state_index == 0 for case in state_set.cases)
    assert all(case.expected_legal_actions > 0 for case in state_set.cases)
    assert (
        freeze_search_benchmark_state_set(
            specification,
            split_manifest=split,
        )
        == state_set.as_dict()
    )


def test_compute_quality_benchmark_uses_paired_independent_seeds_and_verifies(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "states.json"
    state_path.write_text(json.dumps(_state_set_document()), encoding="utf-8")
    result = run_search_compute_quality_benchmark(
        backend=SearchBackendSpec.tactical_mock(),
        state_set=load_search_benchmark_state_set(state_path),
        config=_configuration(),
        output_directory=tmp_path / "benchmark",
    )

    assert result.successful
    case = result.report["cases"][0]
    assert case["status"] == "completed"
    assert [tier["simulation_budget"] for tier in case["tiers"]] == [3, 4, 5]
    for tier in case["tiers"]:
        assert 0.0 <= tier["terminal_value_regret"] <= 1.0
        assert 0.0 <= tier["death_risk_brier"] <= 1.0
        assert tier["compute"]["wall_seconds"] > 0.0
    summary = result.report["summary"]
    assert summary["benchmark_denominator"] == 1
    assert summary["completed_cases"] == 1
    assert summary["search_simulations"] == 12
    assert summary["independent_evaluation_simulations"] == 6
    assert summary["simulations"] == 18
    assert summary["transitions"] > 0
    assert set(summary["tiers"]) == {"shallow", "medium", "expensive"}

    case_root = result.report_path.parent / "cases" / "validation-seed-7-combat-0"
    search_seeds = {
        request["simulation_seed"]
        for path in (case_root / "search").glob("tiers/*/wave-*/tasks/*/request.json")
        for request in [json.loads(path.read_text(encoding="utf-8"))]
    }
    evaluation_seeds: dict[str, set[int]] = defaultdict(set)
    for path in (case_root / "evaluation" / "tasks").glob("*/request.json"):
        request = json.loads(path.read_text(encoding="utf-8"))
        evaluation_seeds[request["action_id"]].add(request["simulation_seed"])
    assert len(evaluation_seeds) == 3
    assert all(len(seeds) == 2 for seeds in evaluation_seeds.values())
    assert len({tuple(sorted(seeds)) for seeds in evaluation_seeds.values()}) == 1
    assert search_seeds.isdisjoint(next(iter(evaluation_seeds.values())))

    verification = verify_search_compute_quality_report(result.report_path)
    assert verification.valid, verification.errors
    assert verification.cases == 1
    assert verification.verified_cases == 1


def test_report_identity_detects_changed_metrics(tmp_path: Path) -> None:
    state_path = tmp_path / "states.json"
    state_path.write_text(json.dumps(_state_set_document()), encoding="utf-8")
    result = run_search_compute_quality_benchmark(
        backend=SearchBackendSpec.tactical_mock(),
        state_set=load_search_benchmark_state_set(state_path),
        config=_configuration(),
        output_directory=tmp_path / "benchmark",
    )
    document = json.loads(result.report_path.read_text(encoding="utf-8"))
    document["summary"]["completion_rate"] = 0.0
    result.report_path.write_text(json.dumps(document), encoding="utf-8")

    verification = verify_search_compute_quality_report(result.report_path)

    assert not verification.valid
    assert "search benchmark report identity mismatch" in verification.errors
    assert "benchmark summary differs from case evidence" in verification.errors


def test_failed_simulations_remain_in_denominator_and_resource_totals(tmp_path: Path) -> None:
    def crash(request: SearchWorkerRequest) -> SearchWorkerEvidence:
        return SearchWorkerEvidence(
            task_id=request.task.task_id,
            status=SearchWorkerStatus.CRASHED,
            exit_code=137,
            worker_pid=None,
            message="injected crash",
            request_path=str(request.request_path.relative_to(request.batch_directory)),
            result_path=str(request.result_path.relative_to(request.batch_directory)),
            request_sha256=sha256_file(request.request_path),
            result_sha256=None,
            cpu_seconds=None,
            wall_seconds=None,
            output=None,
        )

    state_path = tmp_path / "states.json"
    state_path.write_text(json.dumps(_state_set_document()), encoding="utf-8")
    result = run_search_compute_quality_benchmark(
        backend=SearchBackendSpec.tactical_mock(),
        state_set=load_search_benchmark_state_set(state_path),
        config=_configuration(),
        output_directory=tmp_path / "benchmark",
        task_runner=crash,
    )

    assert not result.successful
    assert result.report["cases"][0]["status"] == "failed"
    assert result.report["summary"]["benchmark_denominator"] == 1
    assert result.report["summary"]["completed_cases"] == 0
    assert result.report["summary"]["simulations"] == 18
    verification = verify_search_compute_quality_report(result.report_path)
    assert verification.valid, verification.errors
    assert verification.verified_cases == 1


def test_cli_freezes_runs_and_verifies_short_benchmark(tmp_path: Path) -> None:
    specification = _state_set_document()
    specification.pop("schema_version")
    specification.pop("state_set_id")
    specification_path = tmp_path / "specification.json"
    state_set_path = tmp_path / "states.json"
    output_directory = tmp_path / "benchmark"
    verification_path = tmp_path / "verification.json"
    specification_path.write_text(json.dumps(specification), encoding="utf-8")

    frozen = main(
        [
            "search",
            "freeze-benchmark-states",
            str(specification_path),
            str(state_set_path),
        ]
    )
    generated = main(
        [
            "search",
            "benchmark-fixed",
            str(output_directory),
            "--states",
            str(state_set_path),
            "--backend",
            "tactical_mock",
            "--shallow-simulations",
            "3",
            "--medium-simulations",
            "4",
            "--expensive-simulations",
            "5",
            "--maximum-rollout-steps",
            "8",
            "--workers",
            "5",
            "--evaluation-samples",
            "2",
            "--evaluation-workers",
            "6",
            "--calibration-bins",
            "4",
        ]
    )
    verified = main(
        [
            "search",
            "verify-benchmark",
            str(output_directory / "search-compute-quality-report.json"),
            "--output",
            str(verification_path),
        ]
    )

    assert frozen == 0
    assert generated == 0
    assert verified == 0
    assert json.loads(verification_path.read_text(encoding="utf-8"))["valid"] is True
