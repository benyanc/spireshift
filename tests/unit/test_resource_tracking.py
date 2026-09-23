from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import psutil
from pytest import MonkeyPatch

from spireshift.cli import main
from spireshift.resource_tracking import (
    CostRates,
    ExperimentKind,
    ExperimentStatus,
    ResourceLimits,
    _ProcessSample,
    _ProcessTreeAccounting,
    _sample_process_tree,
    capture_hardware,
    load_cost_rates,
    load_resource_report,
    run_tracked_command,
    verify_resource_report,
)


class _FakeProcess:
    def __init__(self, pid: int, created: float, cpu: float, rss: int = 1) -> None:
        self.pid = pid
        self._created = created
        self._cpu = cpu
        self._rss = rss
        self.descendants: list[_FakeProcess] = []

    def children(self, *, recursive: bool) -> list[_FakeProcess]:
        assert recursive is True
        return self.descendants

    def create_time(self) -> float:
        return self._created

    def cpu_times(self) -> SimpleNamespace:
        return SimpleNamespace(user=self._cpu, system=0.0)

    def memory_info(self) -> SimpleNamespace:
        return SimpleNamespace(rss=self._rss)


def test_tracked_command_captures_hardware_throughput_storage_and_cost(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    metrics = tmp_path / "metrics.json"
    report = tmp_path / "resources.json"
    code = """
import json
import pathlib
import sys
artifact_root = pathlib.Path(sys.argv[1])
artifact_root.mkdir(parents=True)
(artifact_root / 'model.bin').write_bytes(b'x' * 1000)
pathlib.Path(sys.argv[2]).write_text(json.dumps({
    'trajectories': 4,
    'simulations': 8,
    'transitions': 16,
    'gpu_seconds': 0.0,
    'energy_kwh': 0.0,
}))
"""

    result = run_tracked_command(
        command=(sys.executable, "-c", code, str(artifacts), str(metrics)),
        experiment_kind=ExperimentKind.TRAINING,
        report_path=report,
        artifact_roots=(artifacts,),
        metrics_path=metrics,
        workers=2,
        rates=CostRates(
            cpu_per_hour=0.25,
            gpu_per_hour=1.0,
            storage_per_gb_month=0.10,
            electricity_per_kwh=0.20,
        ),
        poll_interval_seconds=0.01,
        experiment_id="00000000-0000-4000-8000-000000000048",
    )

    assert result.status is ExperimentStatus.COMPLETED
    assert result.exit_code == 0
    assert report.is_file()
    assert verify_resource_report(result.report) == ()
    assert result.report["workers"] == 2
    hardware = _mapping(result.report["hardware"])
    cpu = _mapping(hardware["cpu"])
    memory = _mapping(hardware["memory"])
    assert cpu["logical_cores"] is not None
    assert memory["total_bytes"] > 0
    usage = _mapping(result.report["usage"])
    assert usage["trajectories"] == 4
    assert usage["simulations"] == 8
    assert usage["transitions"] == 16
    assert usage["cpu_seconds"] >= 0.0
    assert usage["cpu_hours"] == usage["cpu_seconds"] / 3600.0
    assert usage["gpu_hours"] == 0.0
    assert usage["wall_seconds"] > 0.0
    assert usage["final_storage_bytes"] == 1000
    assert usage["peak_storage_bytes"] >= 1000
    throughput = _mapping(result.report["throughput"])
    assert throughput["simulations_per_second"] > 0.0
    estimated = _mapping(result.report["estimated_cost"])
    assert estimated["complete"] is True
    assert estimated["missing"] == []
    assert estimated["known_subtotal"] >= 0.0


def test_missing_measurements_and_rates_remain_null_and_explicit(tmp_path: Path) -> None:
    result = run_tracked_command(
        command=(sys.executable, "-c", "pass"),
        experiment_kind=ExperimentKind.BENCHMARK,
        report_path=tmp_path / "resources.json",
        poll_interval_seconds=0.01,
    )

    usage = _mapping(result.report["usage"])
    assert usage["trajectories"] is None
    assert usage["simulations"] is None
    assert usage["gpu_seconds"] is None
    assert usage["energy_kwh"] is None
    throughput = _mapping(result.report["throughput"])
    assert throughput["trajectories_per_second"] is None
    estimated = _mapping(result.report["estimated_cost"])
    assert estimated["complete"] is False
    assert set(estimated["missing"]) == {
        "cpu_rate",
        "gpu_usage",
        "storage_rate",
        "energy_usage",
    }


def test_process_tree_cpu_accounting_retains_completed_descendants() -> None:
    root = _FakeProcess(1, 10.0, 0.1)
    first_child = _FakeProcess(2, 20.0, 1.25)
    second_child = _FakeProcess(3, 30.0, 2.5)
    accounting = _ProcessTreeAccounting({})
    fallback = _ProcessSample(0.0, 0, 1)

    root.descendants = [first_child]
    first = _sample_process_tree(root, fallback, accounting)  # type: ignore[arg-type]
    root._cpu = 0.2
    root.descendants = [second_child]
    second = _sample_process_tree(root, first, accounting)  # type: ignore[arg-type]

    assert first.cpu_seconds == 1.35
    assert second.cpu_seconds == 3.95


def test_wall_cap_stops_process_and_preserves_partial_artifact(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    report = tmp_path / "resources.json"
    code = """
import pathlib
import sys
import time
root = pathlib.Path(sys.argv[1])
root.mkdir(parents=True)
(root / 'partial.bin').write_bytes(b'partial')
time.sleep(5)
"""

    result = run_tracked_command(
        command=(sys.executable, "-c", code, str(artifacts)),
        experiment_kind=ExperimentKind.TEACHER_GENERATION,
        report_path=report,
        artifact_roots=(artifacts,),
        limits=ResourceLimits(wall_seconds=0.1),
        poll_interval_seconds=0.01,
    )

    assert result.status is ExperimentStatus.CAPPED
    cap = _mapping(result.report["cap"])
    artifacts_document = _mapping(result.report["artifacts"])
    usage = _mapping(result.report["usage"])
    assert cap["resource"] == "wall_seconds"
    assert artifacts_document["partial_artifacts_preserved"] is True
    assert (artifacts / "partial.bin").read_bytes() == b"partial"
    assert usage["wall_seconds"] < 3.0


def test_resource_report_identity_detects_tampering(tmp_path: Path) -> None:
    result = run_tracked_command(
        command=(sys.executable, "-c", "pass"),
        experiment_kind=ExperimentKind.OTHER,
        report_path=tmp_path / "resources.json",
        poll_interval_seconds=0.01,
    )
    changed = copy.deepcopy(result.report)
    changed["workers"] = 99

    errors = verify_resource_report(changed)

    assert errors == ("resource report identity mismatch",)


def test_hardware_capture_uses_null_for_unavailable_values() -> None:
    hardware = capture_hardware()

    assert set(hardware) == {"platform", "cpu", "memory", "gpus"}
    cpu = _mapping(hardware["cpu"])
    assert cpu["model"] is None or isinstance(cpu["model"], str)
    json.dumps(hardware)


def test_hardware_capture_allows_missing_cpu_frequency_api(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delattr(psutil, "cpu_freq", raising=False)

    hardware = capture_hardware()

    cpu = _mapping(hardware["cpu"])
    assert cpu["frequency_mhz"] is None


def test_resource_cli_runs_and_verifies_command(tmp_path: Path) -> None:
    report = tmp_path / "resources.json"
    metrics = tmp_path / "metrics.json"
    benchmark = tmp_path / "benchmark.json"

    exit_code = main(
        [
            "resources",
            "run",
            "--kind",
            "benchmark",
            "--report",
            str(report),
            "--metrics",
            str(metrics),
            "--artifact-root",
            str(tmp_path),
            "--poll-interval",
            "0.01",
            "--",
            sys.executable,
            "-m",
            "spireshift",
            "tactical-handoff",
            "benchmark-mock",
            str(benchmark),
            "--seeds",
            "7",
        ]
    )
    verify_exit_code = main(["resources", "verify", str(report)])

    assert exit_code == 0
    assert verify_exit_code == 0
    document = load_resource_report(report)
    usage = _mapping(document["usage"])
    assert usage["simulations"] > 0
    assert usage["transitions"] > 0


def test_checked_resource_fixture_has_valid_content_identity() -> None:
    report = load_resource_report(Path("tests/fixtures/experiment-resources-v1.json"))

    assert report["report_id"] == (
        "sha256:5a3f2449608c597d782e62790c81bb202b73548bce33b89224aaf66e9945291a"
    )


def test_example_cost_profiles_are_explicit_and_loadable() -> None:
    path = Path("configs/cost-rates.example.toml")

    local = load_cost_rates(path, "local")
    hosted = load_cost_rates(path, "hosted")

    assert local.cpu_per_hour == 0.05
    assert local.electricity_per_kwh == 0.15
    assert hosted.gpu_per_hour == 1.0
    assert hosted.storage_per_gb_month == 0.10


def _mapping(value: object) -> dict[str, Any]:
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)
