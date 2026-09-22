from __future__ import annotations

import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
import tomllib
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import psutil

from spireshift.core.manifest import manifest_identifier
from spireshift.rollouts import write_exclusive_json

RESOURCE_REPORT_SCHEMA_VERSION = "experiment-resources-v1"
EXPERIMENT_METRICS_ENV = "SPIRESHIFT_EXPERIMENT_METRICS_PATH"
SECONDS_PER_HOUR = 3600.0
SECONDS_PER_BILLING_MONTH = 30.0 * 24.0 * SECONDS_PER_HOUR
BYTES_PER_GB = 1_000_000_000.0


class ExperimentKind(StrEnum):
    TRAINING = "training"
    TEACHER_GENERATION = "teacher_generation"
    ADAPTATION = "adaptation"
    BENCHMARK = "benchmark"
    SEARCH = "search"
    ROLLOUT = "rollout"
    OTHER = "other"


class ExperimentStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    CAPPED = "capped"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True, slots=True)
class ResourceLimits:
    wall_seconds: float | None = None
    cpu_seconds: float | None = None
    storage_bytes: int | None = None
    resident_memory_bytes: int | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("wall_seconds", self.wall_seconds),
            ("cpu_seconds", self.cpu_seconds),
        ):
            if value is not None and (not math.isfinite(value) or value <= 0.0):
                raise ValueError(f"{name} must be finite and positive")
        for name, value in (
            ("storage_bytes", self.storage_bytes),
            ("resident_memory_bytes", self.resident_memory_bytes),
        ):
            if value is not None and (isinstance(value, bool) or value <= 0):
                raise ValueError(f"{name} must be positive")

    def as_dict(self) -> dict[str, object]:
        return {
            "wall_seconds": self.wall_seconds,
            "cpu_seconds": self.cpu_seconds,
            "storage_bytes": self.storage_bytes,
            "resident_memory_bytes": self.resident_memory_bytes,
        }


@dataclass(frozen=True, slots=True)
class CostRates:
    currency: str = "USD"
    cpu_per_hour: float | None = None
    gpu_per_hour: float | None = None
    storage_per_gb_month: float | None = None
    electricity_per_kwh: float | None = None

    def __post_init__(self) -> None:
        if not self.currency:
            raise ValueError("currency must be non-empty")
        for name, value in (
            ("cpu_per_hour", self.cpu_per_hour),
            ("gpu_per_hour", self.gpu_per_hour),
            ("storage_per_gb_month", self.storage_per_gb_month),
            ("electricity_per_kwh", self.electricity_per_kwh),
        ):
            if value is not None and (not math.isfinite(value) or value < 0.0):
                raise ValueError(f"{name} must be finite and non-negative")

    def as_dict(self) -> dict[str, object]:
        return {
            "currency": self.currency,
            "cpu_per_hour": self.cpu_per_hour,
            "gpu_per_hour": self.gpu_per_hour,
            "storage_per_gb_month": self.storage_per_gb_month,
            "electricity_per_kwh": self.electricity_per_kwh,
        }


@dataclass(frozen=True, slots=True)
class ExperimentMetrics:
    trajectories: int | None = None
    simulations: int | None = None
    transitions: int | None = None
    gpu_seconds: float | None = None
    energy_kwh: float | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("trajectories", self.trajectories),
            ("simulations", self.simulations),
            ("transitions", self.transitions),
        ):
            if value is not None and (isinstance(value, bool) or value < 0):
                raise ValueError(f"{name} must be non-negative")
        measurements: tuple[tuple[str, float | None], ...] = (
            ("gpu_seconds", self.gpu_seconds),
            ("energy_kwh", self.energy_kwh),
        )
        for name, measurement in measurements:
            if measurement is not None and (not math.isfinite(measurement) or measurement < 0.0):
                raise ValueError(f"{name} must be finite and non-negative")

    @classmethod
    def from_path(cls, path: Path | None) -> ExperimentMetrics:
        if path is None or not path.is_file():
            return cls()
        value: object = json.loads(path.read_text(encoding="utf-8"))
        document = _mapping(value, "experiment metrics")
        expected = {
            "trajectories",
            "simulations",
            "transitions",
            "gpu_seconds",
            "energy_kwh",
        }
        if set(document) != expected:
            raise ValueError("Experiment metrics fields differ from experiment-metrics-v1")
        return cls(
            trajectories=_optional_integer(document.get("trajectories")),
            simulations=_optional_integer(document.get("simulations")),
            transitions=_optional_integer(document.get("transitions")),
            gpu_seconds=_optional_number(document.get("gpu_seconds")),
            energy_kwh=_optional_number(document.get("energy_kwh")),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "trajectories": self.trajectories,
            "simulations": self.simulations,
            "transitions": self.transitions,
            "gpu_seconds": self.gpu_seconds,
            "energy_kwh": self.energy_kwh,
        }


@dataclass(frozen=True, slots=True)
class TrackedCommandResult:
    status: ExperimentStatus
    exit_code: int | None
    report_path: Path
    report: dict[str, object]


@dataclass(frozen=True, slots=True)
class _ProcessSample:
    cpu_seconds: float
    resident_memory_bytes: int
    process_count: int


def run_tracked_command(
    *,
    command: Sequence[str],
    experiment_kind: ExperimentKind,
    report_path: Path,
    artifact_roots: Sequence[Path] = (),
    metrics_path: Path | None = None,
    workers: int = 1,
    limits: ResourceLimits | None = None,
    rates: CostRates | None = None,
    working_directory: Path | None = None,
    poll_interval_seconds: float = 0.25,
    experiment_id: str | None = None,
) -> TrackedCommandResult:
    arguments = tuple(command)
    if not arguments:
        raise ValueError("Tracked command must not be empty")
    if workers <= 0:
        raise ValueError("workers must be positive")
    if not math.isfinite(poll_interval_seconds) or poll_interval_seconds <= 0.0:
        raise ValueError("poll_interval_seconds must be finite and positive")
    limits = limits or ResourceLimits()
    rates = rates or CostRates()
    canonical_experiment_id = str(uuid4()) if experiment_id is None else str(UUID(experiment_id))
    report_path = report_path.expanduser().resolve()
    if report_path.exists():
        raise FileExistsError(report_path)
    roots = tuple(path.expanduser().resolve() for path in artifact_roots)
    cwd = (working_directory or Path.cwd()).expanduser().resolve()
    hardware = capture_hardware()
    started_at = _utc_now()
    started = time.perf_counter()
    environment = os.environ.copy()
    if metrics_path is not None:
        environment[EXPERIMENT_METRICS_ENV] = str(metrics_path.expanduser().resolve())
    process = subprocess.Popen(  # noqa: S603 - exact argv is an explicit user command.
        arguments,
        cwd=cwd,
        env=environment,
        start_new_session=sys.platform != "win32",
        creationflags=(
            int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
            if sys.platform == "win32"
            else 0
        ),
    )
    tracked_process = psutil.Process(process.pid)
    peak_rss = 0
    peak_storage = _storage_bytes(roots)
    last_sample = _ProcessSample(0.0, 0, 1)
    cap: dict[str, object] | None = None
    interrupted = False
    try:
        while True:
            wall_seconds = time.perf_counter() - started
            last_sample = _sample_process_tree(tracked_process, last_sample)
            peak_rss = max(peak_rss, last_sample.resident_memory_bytes)
            storage_bytes = _storage_bytes(roots)
            peak_storage = max(peak_storage, storage_bytes)
            cap = _triggered_cap(
                limits,
                wall_seconds=wall_seconds,
                cpu_seconds=last_sample.cpu_seconds,
                storage_bytes=storage_bytes,
                resident_memory_bytes=last_sample.resident_memory_bytes,
            )
            if cap is not None:
                _terminate_process_tree(tracked_process)
                break
            if process.poll() is not None:
                break
            with suppress(subprocess.TimeoutExpired):
                process.wait(timeout=poll_interval_seconds)
    except KeyboardInterrupt:
        interrupted = True
        _terminate_process_tree(tracked_process)
    exit_code = process.poll()
    if exit_code is None:
        try:
            exit_code = process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            _kill_process_tree(tracked_process)
            exit_code = process.wait(timeout=5.0)
    completed_at = _utc_now()
    wall_seconds = time.perf_counter() - started
    final_storage = _storage_bytes(roots)
    peak_storage = max(peak_storage, final_storage)
    metrics = ExperimentMetrics.from_path(metrics_path)
    if interrupted:
        status = ExperimentStatus.INTERRUPTED
    elif cap is not None:
        status = ExperimentStatus.CAPPED
    elif exit_code == 0:
        status = ExperimentStatus.COMPLETED
    else:
        status = ExperimentStatus.FAILED
    cpu_hardware = _mapping(hardware["cpu"], "captured CPU hardware")
    logical_cores = cpu_hardware.get("logical_cores")
    usage = {
        **metrics.as_dict(),
        "cpu_seconds": last_sample.cpu_seconds,
        "cpu_hours": last_sample.cpu_seconds / SECONDS_PER_HOUR,
        "gpu_hours": (
            None if metrics.gpu_seconds is None else metrics.gpu_seconds / SECONDS_PER_HOUR
        ),
        "wall_seconds": wall_seconds,
        "average_cpu_utilization": _cpu_utilization(
            last_sample.cpu_seconds,
            wall_seconds,
            (
                logical_cores
                if isinstance(logical_cores, int) and not isinstance(logical_cores, bool)
                else None
            ),
        ),
        "peak_resident_memory_bytes": peak_rss,
        "final_storage_bytes": final_storage,
        "peak_storage_bytes": peak_storage,
        "peak_process_count": last_sample.process_count,
    }
    report_body: dict[str, object] = {
        "schema_version": RESOURCE_REPORT_SCHEMA_VERSION,
        "experiment_id": canonical_experiment_id,
        "experiment_kind": experiment_kind.value,
        "status": status.value,
        "started_at": started_at,
        "completed_at": completed_at,
        "command": list(arguments),
        "working_directory": str(cwd),
        "exit_code": exit_code,
        "workers": workers,
        "hardware": hardware,
        "usage": usage,
        "throughput": _throughput(metrics, wall_seconds),
        "limits": limits.as_dict(),
        "cap": cap,
        "cost_rates": rates.as_dict(),
        "estimated_cost": _estimated_cost(usage, rates),
        "artifacts": {
            "roots": [str(path) for path in roots],
            "partial_artifacts_preserved": status
            in {ExperimentStatus.CAPPED, ExperimentStatus.INTERRUPTED},
            "metrics_path": None if metrics_path is None else str(metrics_path.resolve()),
        },
    }
    report = {**report_body, "report_id": manifest_identifier(report_body)}
    write_exclusive_json(report_path, report)
    return TrackedCommandResult(status, exit_code, report_path, report)


def capture_hardware() -> dict[str, object]:
    frequency = psutil.cpu_freq()
    frequency_mhz: float | None = None if frequency is None else frequency.current
    if sys.platform == "darwin" and frequency_mhz is not None and frequency_mhz < 100.0:
        frequency_mhz = None
    return {
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "cpu": {
            "model": _cpu_model(),
            "logical_cores": psutil.cpu_count(logical=True),
            "physical_cores": psutil.cpu_count(logical=False),
            "frequency_mhz": frequency_mhz,
        },
        "memory": {"total_bytes": psutil.virtual_memory().total},
        "gpus": _gpus(),
    }


def load_cost_rates(path: Path, profile: str) -> CostRates:
    if not profile:
        raise ValueError("Cost-rate profile must be non-empty")
    with path.open("rb") as handle:
        document = tomllib.load(handle)
    raw_profile = document.get(profile)
    if not isinstance(raw_profile, dict):
        raise ValueError(f"Cost-rate profile {profile!r} is missing")
    expected = {
        "currency",
        "cpu_per_hour",
        "gpu_per_hour",
        "storage_per_gb_month",
        "electricity_per_kwh",
    }
    unexpected = set(raw_profile) - expected
    if unexpected:
        raise ValueError(f"Unexpected cost-rate fields: {sorted(unexpected)}")
    return CostRates(
        currency=str(raw_profile.get("currency", "USD")),
        cpu_per_hour=_optional_number(raw_profile.get("cpu_per_hour")),
        gpu_per_hour=_optional_number(raw_profile.get("gpu_per_hour")),
        storage_per_gb_month=_optional_number(raw_profile.get("storage_per_gb_month")),
        electricity_per_kwh=_optional_number(raw_profile.get("electricity_per_kwh")),
    )


def write_experiment_metrics(metrics: ExperimentMetrics) -> Path | None:
    configured = os.environ.get(EXPERIMENT_METRICS_ENV)
    if configured is None:
        return None
    path = Path(configured).expanduser().resolve()
    write_exclusive_json(path, metrics.as_dict())
    return path


def verify_resource_report(value: object) -> tuple[str, ...]:
    errors: list[str] = []
    document = _mapping(value, "resource report")
    if document.get("schema_version") != RESOURCE_REPORT_SCHEMA_VERSION:
        errors.append("unsupported resource report schema")
        return tuple(errors)
    report_id = document.get("report_id")
    body = {key: item for key, item in document.items() if key != "report_id"}
    if report_id != manifest_identifier(body):
        errors.append("resource report identity mismatch")
    usage = document.get("usage")
    if not isinstance(usage, dict):
        errors.append("resource report usage must be an object")
    else:
        wall = usage.get("wall_seconds")
        cpu = usage.get("cpu_seconds")
        if not _is_nonnegative_number(wall) or float(cast(float, wall)) <= 0.0:
            errors.append("wall_seconds must be positive")
        if not _is_nonnegative_number(cpu):
            errors.append("cpu_seconds must be non-negative")
        elif usage.get("cpu_hours") != float(cast(float, cpu)) / SECONDS_PER_HOUR:
            errors.append("cpu_hours differs from cpu_seconds")
        gpu_seconds = usage.get("gpu_seconds")
        if gpu_seconds is None:
            expected_gpu_hours = None
        elif _is_nonnegative_number(gpu_seconds):
            expected_gpu_hours = float(cast(float, gpu_seconds)) / SECONDS_PER_HOUR
        else:
            expected_gpu_hours = None
            errors.append("gpu_seconds must be non-negative or null")
        if usage.get("gpu_hours") != expected_gpu_hours:
            errors.append("gpu_hours differs from gpu_seconds")
    status = document.get("status")
    cap = document.get("cap")
    if (status == ExperimentStatus.CAPPED.value) != (cap is not None):
        errors.append("capped status and cap evidence differ")
    return tuple(errors)


def load_resource_report(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    document = _mapping(value, "resource report")
    errors = verify_resource_report(document)
    if errors:
        raise ValueError("; ".join(errors))
    return document


def _sample_process_tree(
    process: psutil.Process,
    fallback: _ProcessSample,
) -> _ProcessSample:
    try:
        processes = (process, *process.children(recursive=True))
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return fallback
    cpu_seconds = 0.0
    resident_memory = 0
    sampled = 0
    for child in processes:
        try:
            times = child.cpu_times()
            cpu_seconds += times.user + times.system
            resident_memory += child.memory_info().rss
            sampled += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if sampled == 0:
        return fallback
    return _ProcessSample(
        max(cpu_seconds, fallback.cpu_seconds),
        resident_memory,
        max(sampled, fallback.process_count),
    )


def _triggered_cap(
    limits: ResourceLimits,
    *,
    wall_seconds: float,
    cpu_seconds: float,
    storage_bytes: int,
    resident_memory_bytes: int,
) -> dict[str, object] | None:
    values: tuple[tuple[str, float | int, float | int | None], ...] = (
        ("wall_seconds", wall_seconds, limits.wall_seconds),
        ("cpu_seconds", cpu_seconds, limits.cpu_seconds),
        ("storage_bytes", storage_bytes, limits.storage_bytes),
        (
            "resident_memory_bytes",
            resident_memory_bytes,
            limits.resident_memory_bytes,
        ),
    )
    for name, observed, limit in values:
        if limit is not None and observed >= limit:
            return {"resource": name, "limit": limit, "observed": observed}
    return None


def _terminate_process_tree(process: psutil.Process) -> None:
    try:
        children = process.children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        children = []
    for child in reversed(children):
        with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            child.terminate()
    with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
        process.terminate()
    _, alive = psutil.wait_procs([*children, process], timeout=3.0)
    for remaining in alive:
        with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            remaining.kill()


def _kill_process_tree(process: psutil.Process) -> None:
    try:
        processes = (*process.children(recursive=True), process)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        processes = (process,)
    for child in reversed(processes):
        with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            child.kill()


def _storage_bytes(roots: Sequence[Path]) -> int:
    total = 0
    for root in roots:
        if root.is_file():
            with suppress(OSError):
                total += root.stat().st_size
            continue
        if not root.is_dir():
            continue
        for directory, _, files in os.walk(root, followlinks=False):
            base = Path(directory)
            for name in files:
                try:
                    path = base / name
                    if not path.is_symlink():
                        total += path.stat().st_size
                except OSError:
                    continue
    return total


def _throughput(metrics: ExperimentMetrics, wall_seconds: float) -> dict[str, object]:
    return {
        "trajectories_per_second": _rate(metrics.trajectories, wall_seconds),
        "simulations_per_second": _rate(metrics.simulations, wall_seconds),
        "transitions_per_second": _rate(metrics.transitions, wall_seconds),
    }


def _rate(count: int | None, wall_seconds: float) -> float | None:
    return None if count is None else count / wall_seconds


def _cpu_utilization(
    cpu_seconds: float,
    wall_seconds: float,
    logical_cores: int | None,
) -> float | None:
    if logical_cores is None or logical_cores <= 0 or wall_seconds <= 0.0:
        return None
    return cpu_seconds / (wall_seconds * logical_cores)


def _estimated_cost(usage: Mapping[str, object], rates: CostRates) -> dict[str, object]:
    cpu_seconds = float(cast(float, usage["cpu_seconds"]))
    wall_seconds = float(cast(float, usage["wall_seconds"]))
    peak_storage = int(cast(int, usage["peak_storage_bytes"]))
    gpu_seconds = _optional_number(usage.get("gpu_seconds"))
    energy_kwh = _optional_number(usage.get("energy_kwh"))
    cpu = (
        None if rates.cpu_per_hour is None else cpu_seconds / SECONDS_PER_HOUR * rates.cpu_per_hour
    )
    gpu = (
        None
        if gpu_seconds is None or rates.gpu_per_hour is None
        else gpu_seconds / SECONDS_PER_HOUR * rates.gpu_per_hour
    )
    storage = (
        None
        if rates.storage_per_gb_month is None
        else peak_storage
        / BYTES_PER_GB
        * (wall_seconds / SECONDS_PER_BILLING_MONTH)
        * rates.storage_per_gb_month
    )
    energy = (
        None
        if energy_kwh is None or rates.electricity_per_kwh is None
        else energy_kwh * rates.electricity_per_kwh
    )
    missing: list[str] = []
    if rates.cpu_per_hour is None:
        missing.append("cpu_rate")
    if gpu_seconds is None:
        missing.append("gpu_usage")
    elif rates.gpu_per_hour is None:
        missing.append("gpu_rate")
    if rates.storage_per_gb_month is None:
        missing.append("storage_rate")
    if energy_kwh is None:
        missing.append("energy_usage")
    elif rates.electricity_per_kwh is None:
        missing.append("electricity_rate")
    components = {"cpu": cpu, "gpu": gpu, "storage": storage, "energy": energy}
    return {
        "currency": rates.currency,
        "components": components,
        "known_subtotal": sum(value for value in components.values() if value is not None),
        "complete": not missing,
        "missing": missing,
    }


def _nvidia_gpus() -> list[dict[str, object]]:
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return []
    try:
        result = subprocess.run(  # noqa: S603 - resolved trusted local executable.
            [
                executable,
                "--query-gpu=name,uuid,memory.total",
                "--format=csv,noheader,nounits",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=3.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    gpus: list[dict[str, object]] = []
    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 3:
            continue
        try:
            memory_bytes = int(float(parts[2]) * 1024 * 1024)
        except ValueError:
            memory_bytes = None
        gpus.append({"model": parts[0], "uuid": parts[1], "memory_bytes": memory_bytes})
    return gpus


def _gpus() -> list[dict[str, object]]:
    gpus = _nvidia_gpus()
    if sys.platform != "darwin":
        return gpus
    try:
        result = subprocess.run(  # noqa: S603 - fixed system introspection command.
            ["/usr/sbin/system_profiler", "SPDisplaysDataType", "-json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        document: object = json.loads(result.stdout) if result.returncode == 0 else {}
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return gpus
    if not isinstance(document, dict):
        return gpus
    displays = document.get("SPDisplaysDataType")
    if not isinstance(displays, list):
        return gpus
    known_models = {str(gpu["model"]) for gpu in gpus}
    for raw_gpu in displays:
        if not isinstance(raw_gpu, dict):
            continue
        model_value = raw_gpu.get("sppci_model", raw_gpu.get("_name"))
        if not isinstance(model_value, str) or not model_value or model_value in known_models:
            continue
        gpus.append({"model": model_value, "uuid": None, "memory_bytes": None})
        known_models.add(model_value)
    return gpus


def _cpu_model() -> str | None:
    model = platform.processor().strip()
    if model and model.casefold() not in {"arm", "i386", "x86_64", "amd64"}:
        return model
    if sys.platform == "darwin":
        for key in ("machdep.cpu.brand_string", "hw.model"):
            try:
                result = subprocess.run(  # noqa: S603 - fixed system introspection command.
                    ["/usr/sbin/sysctl", "-n", key],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=2.0,
                )
            except (OSError, subprocess.TimeoutExpired):
                continue
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
    if sys.platform.startswith("linux"):
        with suppress(OSError):
            for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
                key, separator, value = line.partition(":")
                if separator and key.strip() in {"model name", "Hardware"} and value.strip():
                    return value.strip()
    windows_model = os.environ.get("PROCESSOR_IDENTIFIER", "").strip()
    return windows_model or model or None


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _optional_integer(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("Optional counter must be a non-negative integer or null")
    return value


def _optional_number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Optional measurement must be a number or null")
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError("Optional measurement must be finite and non-negative")
    return result


def _is_nonnegative_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and float(value) >= 0.0
    )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
