from __future__ import annotations

import json
from pathlib import Path

import pytest

from spireshift.cli import main
from spireshift.fixed_search import (
    FixedSearchConfig,
    FixedSearchTier,
    capture_combat_state,
    run_fixed_search_suite,
    verify_fixed_search_report,
)
from spireshift.rollouts import sha256_file
from spireshift.search_workers import (
    SearchBackendSpec,
    SearchWorkerEvidence,
    SearchWorkerRequest,
    SearchWorkerStatus,
)

FIXTURE = Path("tests/fixtures/fixed-search/tactical-mock-v2/fixed-search-report.json")


def _config() -> FixedSearchConfig:
    return FixedSearchConfig(
        tiers=(
            FixedSearchTier("shallow", 3),
            FixedSearchTier("medium", 4),
            FixedSearchTier("expensive", 5),
        ),
        maximum_rollout_steps=8,
        workers=5,
        worker_timeout_seconds=30.0,
    )


def test_capture_finds_public_combat_checkpoint_without_hidden_state() -> None:
    captured = capture_combat_state(
        backend=SearchBackendSpec.tactical_mock(),
        run_seed=7,
    )

    assert captured.observation.decision_type.value == "combat"
    assert captured.checkpoint.action_prefix == ()
    assert captured.checkpoint.state_hash == captured.observation.state_hash
    assert [action.action_id for action in captured.legal_actions] == [
        "preserve_hp",
        "take_damage_for_power",
        "spend_potion_for_relic",
    ]


def test_checked_fixed_search_runs_three_nested_budgets_from_one_state() -> None:
    report = json.loads(FIXTURE.read_text(encoding="utf-8"))
    verification = verify_fixed_search_report(FIXTURE)

    assert verification.valid, verification.errors
    assert verification.tiers == 3
    assert verification.simulations == 12
    assert verification.verified_worker_batches == 3
    assert report["objective_id"] == "terminal-victory-v1"
    assert (
        report["checkpoint"]["state_hash"]
        == report["tiers"][0]["simulations"][0]["output"]["source_state_hash"]
    )
    assert [tier["simulation_budget"] for tier in report["tiers"]] == [3, 4, 5]
    prefixes: list[list[tuple[str, int]]] = [
        [
            (simulation["source_action_id"], simulation["simulation_seed"])
            for simulation in tier["simulations"]
        ]
        for tier in report["tiers"]
    ]
    assert prefixes[1][:3] == prefixes[0]
    assert prefixes[2][:4] == prefixes[1]
    for tier in report["tiers"]:
        summary = tier["summary"]
        assert summary["attempted_simulations"] == tier["simulation_budget"]
        assert summary["sampled_worlds"] == tier["simulation_budget"]
        assert summary["unique_simulation_seeds"] == tier["simulation_budget"]
        assert summary["worker_cpu_seconds"] >= 0.0
        assert summary["wall_seconds"] > 0.0
        assert summary["p95_worker_wall_seconds"] >= 0.0
        assert sum(candidate["visit_probability"] for candidate in tier["candidates"]) == 1.0


def test_failed_workers_remain_in_budget_and_make_suite_unsuccessful(tmp_path: Path) -> None:
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

    result = run_fixed_search_suite(
        backend=SearchBackendSpec.tactical_mock(),
        run_seed=7,
        output_directory=tmp_path / "failed-suite",
        config=_config(),
        task_runner=crash,
    )

    assert not result.successful
    assert result.report["summary"]["attempted_simulations"] == 12
    assert result.report["summary"]["failed_or_truncated_simulations"] == 12
    assert result.report["summary"]["all_tiers_complete"] is False
    for tier in result.report["tiers"]:
        assert (
            sum(candidate["failed_simulations"] for candidate in tier["candidates"])
            == tier["simulation_budget"]
        )
        assert all(candidate["terminal_value"] == 0.0 for candidate in tier["candidates"])


def test_explicit_noncombat_checkpoint_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="requires a combat state"):
        run_fixed_search_suite(
            backend=SearchBackendSpec.mock(),
            run_seed=7,
            action_prefix=(),
            output_directory=tmp_path / "noncombat",
            config=_config(),
        )


def test_cli_runs_and_verifies_short_fixed_search(tmp_path: Path) -> None:
    output = tmp_path / "suite"
    verification = tmp_path / "verification.json"

    generated = main(
        [
            "search",
            "fixed-suite",
            str(output),
            "--backend",
            "tactical_mock",
            "--run-seed",
            "7",
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
            "--worker-timeout",
            "30",
        ]
    )
    verified = main(
        [
            "search",
            "verify-fixed",
            str(output / "fixed-search-report.json"),
            "--output",
            str(verification),
        ]
    )

    assert generated == 0
    assert verified == 0
    document = json.loads(verification.read_text(encoding="utf-8"))
    assert document["valid"] is True
    assert document["simulations"] == 12
