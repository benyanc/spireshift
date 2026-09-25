from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from spireshift.adapters.evangambit import (
    EvanGambitBackendError,
    load_evangambit_backend,
)
from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.adapters.sts2mcp import (
    DEFAULT_STS2MCP_URL,
    LiveStateError,
    Sts2McpHttpActionTransport,
    Sts2McpHttpTransport,
    Sts2McpLiveStateAdapter,
    Sts2McpStateProjector,
)
from spireshift.agents.baseline import PolicyOnlyBudgetController, TerminalVictoryPolicy
from spireshift.agents.learned import ProductionCheckpointPolicy
from spireshift.backend_admission import (
    assess_backend_admission,
    load_backend_admission_report,
    verify_backend_admission,
    write_backend_admission,
)
from spireshift.bootstrap_teacher import (
    BootstrapConfig,
    BootstrapPolicyArtifacts,
    combine_curriculum_datasets,
    discover_curriculum_state_set,
    freeze_bootstrap_state_set,
    load_bootstrap_state_set,
    run_bootstrap_teacher_dataset,
    verify_bootstrap_teacher_dataset,
    write_bootstrap_state_set,
)
from spireshift.calibration import (
    CalibrationConfig,
    calibrate_model,
    load_calibration_artifact,
    load_calibration_report,
    verify_calibration_artifacts,
    write_calibration_artifact,
)
from spireshift.conformance import (
    capture_conformance_trace,
    compare_conformance_traces,
    run_environment_conformance,
)
from spireshift.core.manifest import (
    freeze_patch_manifest,
    load_patch_manifest,
    verify_installation_identity,
    write_frozen_manifest,
)
from spireshift.core.objective import load_objective
from spireshift.dagger import (
    DaggerConfig,
    dagger_dataset_index,
    generate_mock_dagger_iteration,
    load_dagger_iteration,
    verify_mock_dagger_iteration,
    write_dagger_iteration,
)
from spireshift.doctor import diagnostics_as_dict, find_game_installation
from spireshift.fixed_search import (
    FixedSearchConfig,
    FixedSearchTier,
    run_fixed_search_suite,
    verify_fixed_search_report,
)
from spireshift.live_actions import (
    BoundAction,
    DurableActionLedger,
    GuardedActionExecutor,
    LiveActionError,
    ReceiptStatus,
    default_live_state_directory,
)
from spireshift.live_coverage import audit_full_run_action_coverage
from spireshift.live_fixture_audit import audit_live_fixture_corpus
from spireshift.live_run import (
    LiveRunRecorder,
    LiveRunStatus,
    LiveRunStrategy,
    WeakLivePolicy,
    run_live_game,
    verify_live_run,
)
from spireshift.mechanics_audit import audit_mechanics_fixture
from spireshift.models import (
    TrainingConfig,
    load_model_checkpoint,
    load_training_report,
    train_initial_models,
    write_model_artifact,
)
from spireshift.production_evaluation import (
    load_production_policy_evaluation,
    run_production_policy_evaluation,
)
from spireshift.production_inference import (
    load_production_inference_smoke,
    run_production_inference_smoke,
    write_production_inference_smoke,
)
from spireshift.production_models import (
    ProductionTrainingConfig,
    load_production_model_checkpoint,
    load_production_training_report,
    train_production_base_model,
    write_production_model_artifact,
)
from spireshift.recording.jsonl import JsonlRecorder
from spireshift.replay import verify_mock_replay
from spireshift.representations import (
    DEFAULT_VECTOR_DIMENSION,
    build_model_input,
    vectorize_model_input,
)
from spireshift.resource_tracking import (
    CostRates,
    ExperimentKind,
    ExperimentMetrics,
    ExperimentStatus,
    ResourceLimits,
    capture_hardware,
    load_cost_rates,
    load_resource_report,
    run_tracked_command,
    verify_resource_report,
    write_experiment_metrics,
)
from spireshift.rollouts import run_mock_rollout_batch, verify_rollout_batch
from spireshift.runner import RunResult, run_episode
from spireshift.search_benchmark import (
    SearchBenchmarkConfig,
    freeze_search_benchmark_state_set,
    load_search_benchmark_state_set,
    run_search_compute_quality_benchmark,
    verify_search_compute_quality_report,
    write_search_benchmark_state_set,
)
from spireshift.search_workers import (
    SearchBackendSpec,
    load_search_task,
    run_search_worker_batch,
    verify_search_worker_batch,
)
from spireshift.splits import (
    SplitName,
    audit_dataset_index,
    freeze_dataset_index,
    freeze_split_manifest,
    load_split_manifest,
    write_frozen_dataset_index,
    write_frozen_split_manifest,
)
from spireshift.tactical_handoff import (
    benchmark_mock_tactical_handoff,
    load_tactical_handoff_report,
    verify_mock_tactical_handoff_report,
    write_tactical_handoff_report,
)
from spireshift.tactical_values import TacticalValueConfig
from spireshift.teacher_data import (
    TeacherConfig,
    generate_mock_teacher_dataset,
    load_teacher_dataset,
    teacher_dataset_index,
    verify_teacher_dataset,
    write_teacher_dataset,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "configs/default.toml"
DEFAULT_LIVE_MANIFEST = PROJECT_ROOT / "manifests/patches/sts2-v0.107.1-sts2mcp-55e0648.json"
DEFAULT_EVANGAMBIT_MANIFEST = (
    PROJECT_ROOT / "manifests/patches/sts2-v0.107.1-evangambit-37e4264.json"
)
DEFAULT_EVANGAMBIT_EXTERNAL_EVIDENCE = (
    PROJECT_ROOT / "docs/evidence/evangambit-v0.107.1-conformance.json"
)
DEFAULT_LIVE_FIXTURE_CORPUS = PROJECT_ROOT / "tests/fixtures/live/public-state-corpus-v1.json"
DEFAULT_LIVE_COVERAGE_SPEC = PROJECT_ROOT / "configs/live-coverage-v0.107.1.json"
DEFAULT_SPLIT_MANIFEST = PROJECT_ROOT / "manifests/splits/mock-v1-seeds-000000-000999-v1.json"
DEFAULT_MECHANICS_FIXTURE = PROJECT_ROOT / "tests/fixtures/mechanics/mock-v1.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spireshift")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="Check local development prerequisites")
    doctor.add_argument(
        "--manifest",
        type=Path,
        help="Write a non-proprietary local game identity manifest",
    )

    manifest = subparsers.add_parser("manifest", help="Freeze or verify patch manifests")
    manifest_commands = manifest.add_subparsers(dest="manifest_command", required=True)
    freeze = manifest_commands.add_parser("freeze", help="Create a content-addressed manifest")
    freeze.add_argument("specification", type=Path)
    freeze.add_argument("output", type=Path)
    verify_manifest = manifest_commands.add_parser("verify", help="Verify immutable manifests")
    verify_manifest.add_argument(
        "--installation",
        type=Path,
        help="Also require this local game identity to match the patch manifest",
    )
    verify_manifest.add_argument("paths", type=Path, nargs="+")

    live = subparsers.add_parser("live", help="Read public state from the installed game")
    live_commands = live.add_subparsers(dest="live_command", required=True)
    live_snapshot = live_commands.add_parser(
        "snapshot", help="Capture one read-only STS2_MCP snapshot"
    )
    live_snapshot.add_argument("--manifest", type=Path, default=DEFAULT_LIVE_MANIFEST)
    live_snapshot.add_argument("--installation", type=Path)
    live_snapshot.add_argument("--base-url", default=DEFAULT_STS2MCP_URL)
    live_snapshot.add_argument("--timeout", type=float, default=3.0)
    live_snapshot.add_argument("--output", type=Path)
    live_project = live_commands.add_parser(
        "project", help="Project a recorded STS2_MCP JSON payload without contacting the game"
    )
    live_project.add_argument("source", type=Path)
    live_project.add_argument("--manifest", type=Path, default=DEFAULT_LIVE_MANIFEST)
    live_project.add_argument("--bridge-version")
    live_project.add_argument("--output", type=Path)
    live_bind = live_commands.add_parser(
        "bind", help="Bind an advertised action to an exact live snapshot"
    )
    live_bind.add_argument("snapshot", type=Path)
    live_bind.add_argument("action_id")
    live_bind.add_argument("--request-id")
    live_bind.add_argument("--output", type=Path)
    live_execute = live_commands.add_parser(
        "execute", help="Validate or apply one guarded bound action"
    )
    live_execute.add_argument("request", type=Path)
    live_execute.add_argument("--manifest", type=Path, default=DEFAULT_LIVE_MANIFEST)
    live_execute.add_argument("--installation", type=Path)
    live_execute.add_argument("--base-url", default=DEFAULT_STS2MCP_URL)
    live_execute.add_argument("--timeout", type=float, default=3.0)
    live_execute.add_argument("--settle-timeout", type=float, default=8.0)
    live_execute.add_argument("--settle-quiet", type=float, default=0.5)
    live_execute.add_argument("--poll-interval", type=float, default=0.1)
    live_execute.add_argument("--state-dir", type=Path, default=default_live_state_directory())
    live_execute.add_argument(
        "--apply",
        action="store_true",
        help="Deliver the action; omission performs a durable dry run",
    )
    live_execute.add_argument("--output", type=Path)
    live_autoplay = live_commands.add_parser(
        "autoplay", help="Continue the visible game with a deliberately weak legal policy"
    )
    live_autoplay.add_argument("--manifest", type=Path, default=DEFAULT_LIVE_MANIFEST)
    live_autoplay.add_argument("--installation", type=Path)
    live_autoplay.add_argument("--base-url", default=DEFAULT_STS2MCP_URL)
    live_autoplay.add_argument("--timeout", type=float, default=3.0)
    live_autoplay.add_argument("--settle-timeout", type=float, default=20.0)
    live_autoplay.add_argument("--settle-quiet", type=float, default=0.5)
    live_autoplay.add_argument("--poll-interval", type=float, default=0.1)
    live_autoplay.add_argument("--readiness-timeout", type=float, default=20.0)
    live_autoplay.add_argument("--max-actions", type=int, default=2000)
    live_autoplay.add_argument("--max-stale-replans", type=int, default=3)
    live_autoplay.add_argument(
        "--strategy",
        choices=[strategy.value for strategy in LiveRunStrategy],
        default=LiveRunStrategy.DETERMINISTIC.value,
    )
    live_autoplay.add_argument("--seed", type=int, default=0)
    live_autoplay.add_argument("--state-dir", type=Path, default=default_live_state_directory())
    live_autoplay.add_argument("--record", type=Path)
    live_autoplay.add_argument(
        "--apply",
        action="store_true",
        help="Acknowledge that the command should control the visible game",
    )
    live_verify_run = live_commands.add_parser(
        "verify-run", help="Audit an append-only live-run record without contacting the game"
    )
    live_verify_run.add_argument("record", type=Path)
    live_verify_run.add_argument("--output", type=Path)
    live_audit_fixtures = live_commands.add_parser(
        "audit-fixtures", help="Audit public-state fixtures and their exact legal-action oracles"
    )
    live_audit_fixtures.add_argument(
        "corpus", type=Path, nargs="?", default=DEFAULT_LIVE_FIXTURE_CORPUS
    )
    live_audit_fixtures.add_argument("--manifest", type=Path, default=DEFAULT_LIVE_MANIFEST)
    live_audit_fixtures.add_argument("--output", type=Path)
    live_coverage = live_commands.add_parser(
        "coverage", help="Gate full-run legal actions and unsupported-decision accounting"
    )
    live_coverage.add_argument("--specification", type=Path, default=DEFAULT_LIVE_COVERAGE_SPEC)
    live_coverage.add_argument("--fixtures", type=Path, default=DEFAULT_LIVE_FIXTURE_CORPUS)
    live_coverage.add_argument("--manifest", type=Path, default=DEFAULT_LIVE_MANIFEST)
    live_coverage.add_argument("--run", dest="runs", type=Path, action="append", required=True)
    live_coverage.add_argument("--output", type=Path)
    live_stop = live_commands.add_parser("stop", help="Activate the local emergency stop")
    live_stop.add_argument("--state-dir", type=Path, default=default_live_state_directory())
    live_resume = live_commands.add_parser(
        "resume", help="Clear the emergency stop and acknowledge uncertain delivery"
    )
    live_resume.add_argument("--state-dir", type=Path, default=default_live_state_directory())
    live_status = live_commands.add_parser("safety-status", help="Inspect live-action safety state")
    live_status.add_argument("--state-dir", type=Path, default=default_live_state_directory())

    conformance = subparsers.add_parser(
        "conformance", help="Run environment contract and differential checks"
    )
    conformance_commands = conformance.add_subparsers(dest="conformance_command", required=True)
    conformance_run = conformance_commands.add_parser(
        "run-mock", help="Run the contract suite against the mock adapter"
    )
    conformance_run.add_argument("--seeds", type=int, nargs="+", default=[1, 7])
    conformance_run.add_argument("--max-steps", type=int, default=4096)
    conformance_run.add_argument("--output", type=Path)
    conformance_trace = conformance_commands.add_parser(
        "trace-mock", help="Capture a public mock conformance trace"
    )
    conformance_trace.add_argument("--seed", type=int, default=7)
    conformance_trace.add_argument("--fixture-id", default="mock-v1-seed-7")
    conformance_trace.add_argument("--output", type=Path)
    conformance_compare = conformance_commands.add_parser(
        "compare", help="Compare reference and candidate public traces"
    )
    conformance_compare.add_argument("reference", type=Path)
    conformance_compare.add_argument("candidate", type=Path)
    conformance_compare.add_argument("--output", type=Path)

    mechanics = subparsers.add_parser(
        "mechanics", help="Audit shared legality, features, and public outcome calculations"
    )
    mechanics_commands = mechanics.add_subparsers(dest="mechanics_command", required=True)
    mechanics_audit = mechanics_commands.add_parser(
        "audit-mock", help="Compare the mechanics service with authoritative mock rules"
    )
    mechanics_audit.add_argument("--fixture", type=Path, default=DEFAULT_MECHANICS_FIXTURE)
    mechanics_audit.add_argument("--output", type=Path)

    search = subparsers.add_parser("search", help="Run isolated planning infrastructure")
    search_commands = search.add_subparsers(dest="search_command", required=True)
    search_workers = search_commands.add_parser(
        "workers", help="Execute prepared search-simulation tasks in isolated processes"
    )
    search_workers.add_argument("tasks", type=Path, nargs="+")
    search_workers.add_argument("--workers", type=int, default=4)
    search_workers.add_argument("--worker-timeout", type=float, default=120.0)
    search_workers.add_argument("--output-dir", type=Path)
    search_verify = search_commands.add_parser(
        "verify-workers",
        help="Verify task identities, evidence, aggregates, and deterministic replay",
    )
    search_verify.add_argument("report", type=Path)
    search_verify.add_argument("--output", type=Path)
    fixed_search = search_commands.add_parser(
        "fixed-suite",
        help="Run shallow, medium, and expensive root-UCT from one public combat state",
    )
    fixed_search.add_argument("output_dir", type=Path)
    fixed_search.add_argument(
        "--backend", choices=("mock", "tactical_mock", "evangambit"), default="evangambit"
    )
    fixed_search.add_argument("--upstream-root", type=Path)
    fixed_search.add_argument("--manifest", type=Path)
    fixed_search.add_argument("--run-seed", type=int, default=0)
    fixed_search.add_argument("--combat-state-index", type=int, default=0)
    fixed_search.add_argument("--maximum-prefix-steps", type=int, default=4096)
    fixed_search.add_argument("--action-prefix", action="append")
    fixed_search.add_argument("--shallow-simulations", type=int, default=16)
    fixed_search.add_argument("--medium-simulations", type=int, default=64)
    fixed_search.add_argument("--expensive-simulations", type=int, default=256)
    fixed_search.add_argument("--exploration-constant", type=float, default=2**0.5)
    fixed_search.add_argument("--sampling-seed", type=int, default=0)
    fixed_search.add_argument("--maximum-rollout-steps", type=int, default=4096)
    fixed_search.add_argument("--workers", type=int, default=4)
    fixed_search.add_argument("--worker-timeout", type=float, default=120.0)
    fixed_verify = search_commands.add_parser(
        "verify-fixed",
        help="Verify fixed-search identities, paired tiers, worker evidence, and exact replay",
    )
    fixed_verify.add_argument("report", type=Path)
    fixed_verify.add_argument("--output", type=Path)
    benchmark_freeze = search_commands.add_parser(
        "freeze-benchmark-states",
        help="Freeze a content-addressed validation state set before benchmark execution",
    )
    benchmark_freeze.add_argument("specification", type=Path)
    benchmark_freeze.add_argument("output", type=Path)
    benchmark_freeze.add_argument("--split-manifest", type=Path)
    search_benchmark = search_commands.add_parser(
        "benchmark-fixed",
        help="Benchmark fixed search budgets on a frozen validation state set",
    )
    search_benchmark.add_argument("output_dir", type=Path)
    search_benchmark.add_argument("--states", type=Path, required=True)
    search_benchmark.add_argument(
        "--backend", choices=("mock", "tactical_mock", "evangambit"), default="evangambit"
    )
    search_benchmark.add_argument("--upstream-root", type=Path)
    search_benchmark.add_argument("--manifest", type=Path)
    search_benchmark.add_argument("--maximum-prefix-steps", type=int, default=4096)
    search_benchmark.add_argument("--shallow-simulations", type=int, default=32)
    search_benchmark.add_argument("--medium-simulations", type=int, default=64)
    search_benchmark.add_argument("--expensive-simulations", type=int, default=256)
    search_benchmark.add_argument("--exploration-constant", type=float, default=2**0.5)
    search_benchmark.add_argument("--sampling-seed", type=int, default=0)
    search_benchmark.add_argument("--maximum-rollout-steps", type=int, default=4096)
    search_benchmark.add_argument("--workers", type=int, default=4)
    search_benchmark.add_argument("--worker-timeout", type=float, default=120.0)
    search_benchmark.add_argument("--evaluation-samples", type=int, default=64)
    search_benchmark.add_argument("--evaluation-sampling-seed", type=int, default=1)
    search_benchmark.add_argument("--evaluation-workers", type=int, default=8)
    search_benchmark.add_argument("--evaluation-worker-timeout", type=float, default=120.0)
    search_benchmark.add_argument("--calibration-bins", type=int, default=10)
    benchmark_verify = search_commands.add_parser(
        "verify-benchmark",
        help="Verify benchmark identities, linked evidence, metrics, and exact replays",
    )
    benchmark_verify.add_argument("report", type=Path)
    benchmark_verify.add_argument("--output", type=Path)

    resources = subparsers.add_parser(
        "resources", help="Measure, cap, cost, and verify experiment resource use"
    )
    resource_commands = resources.add_subparsers(dest="resource_command", required=True)
    resource_run = resource_commands.add_parser(
        "run", help="Run one command with hardware capture and hard optional resource caps"
    )
    resource_run.add_argument(
        "--kind", choices=[kind.value for kind in ExperimentKind], required=True
    )
    resource_run.add_argument("--report", type=Path, required=True)
    resource_run.add_argument("--artifact-root", type=Path, action="append", default=[])
    resource_run.add_argument("--metrics", type=Path)
    resource_run.add_argument("--workers", type=int, default=1)
    resource_run.add_argument("--max-wall-seconds", type=float)
    resource_run.add_argument("--max-cpu-seconds", type=float)
    resource_run.add_argument("--max-storage-bytes", type=int)
    resource_run.add_argument("--max-memory-bytes", type=int)
    resource_run.add_argument("--rates-config", type=Path)
    resource_run.add_argument("--rate-profile", default="local")
    resource_run.add_argument("--currency")
    resource_run.add_argument("--cpu-rate", type=float)
    resource_run.add_argument("--gpu-rate", type=float)
    resource_run.add_argument("--storage-rate", type=float)
    resource_run.add_argument("--electricity-rate", type=float)
    resource_run.add_argument("--cwd", type=Path)
    resource_run.add_argument("--poll-interval", type=float, default=0.25)
    resource_run.add_argument("command_args", nargs=argparse.REMAINDER)
    resource_verify = resource_commands.add_parser(
        "verify", help="Verify a content-addressed experiment resource report"
    )
    resource_verify.add_argument("report", type=Path)
    resource_verify.add_argument("--output", type=Path)
    resource_hardware = resource_commands.add_parser(
        "hardware", help="Show the hardware metadata available to experiment reports"
    )
    resource_hardware.add_argument("--output", type=Path)

    backend = subparsers.add_parser(
        "backend", help="Qualify and admit the optional production training backend"
    )
    backend_commands = backend.add_subparsers(dest="backend_command", required=True)
    backend_conformance = backend_commands.add_parser(
        "conformance", help="Run the environment contract against EvanGambit"
    )
    backend_conformance.add_argument("upstream_root", type=Path)
    backend_conformance.add_argument("--manifest", type=Path, default=DEFAULT_EVANGAMBIT_MANIFEST)
    backend_conformance.add_argument("--seeds", type=int, nargs="+", default=[1, 7])
    backend_conformance.add_argument("--max-steps", type=int, default=4096)
    backend_conformance.add_argument("--output", type=Path, required=True)
    backend_admit = backend_commands.add_parser(
        "admit", help="Create an admitted manifest only after every evidence gate passes"
    )
    backend_admit.add_argument("upstream_root", type=Path)
    backend_admit.add_argument("--manifest", type=Path, default=DEFAULT_EVANGAMBIT_MANIFEST)
    backend_admit.add_argument("--conformance", type=Path, required=True)
    backend_admit.add_argument(
        "--external-evidence", type=Path, default=DEFAULT_EVANGAMBIT_EXTERNAL_EVIDENCE
    )
    backend_admit.add_argument("--installation", type=Path, required=True)
    backend_admit.add_argument("--report", type=Path, required=True)
    backend_admit.add_argument("--admitted-manifest", type=Path, required=True)
    backend_verify = backend_commands.add_parser(
        "verify", help="Verify an immutable backend admission report and manifest"
    )
    backend_verify.add_argument("report", type=Path)
    backend_verify.add_argument("--manifest", type=Path)
    backend_verify.add_argument("--output", type=Path)

    represent = subparsers.add_parser("represent", help="Build a compositional policy/search input")
    represent_commands = represent.add_subparsers(dest="represent_command", required=True)
    represent_mock = represent_commands.add_parser("mock", help="Encode one seeded mock decision")
    represent_mock.add_argument("--seed", type=int, default=7)
    represent_mock.add_argument("--vectorized", action="store_true")
    represent_mock.add_argument("--dimension", type=int, default=DEFAULT_VECTOR_DIMENSION)
    represent_mock.add_argument("--output", type=Path)
    represent_live = represent_commands.add_parser(
        "live", help="Encode a recorded STS2_MCP public-state payload"
    )
    represent_live.add_argument("source", type=Path)
    represent_live.add_argument("--manifest", type=Path, default=DEFAULT_LIVE_MANIFEST)
    represent_live.add_argument("--bridge-version")
    represent_live.add_argument("--vectorized", action="store_true")
    represent_live.add_argument("--dimension", type=int, default=DEFAULT_VECTOR_DIMENSION)
    represent_live.add_argument("--output", type=Path)

    teacher = subparsers.add_parser(
        "teacher", help="Generate or verify independently evaluated teacher data"
    )
    teacher_commands = teacher.add_subparsers(dest="teacher_command", required=True)
    teacher_generate = teacher_commands.add_parser(
        "generate-mock", help="Generate deterministic mock teacher trajectories"
    )
    teacher_generate.add_argument("output", type=Path)
    teacher_generate.add_argument("--index-output", type=Path)
    teacher_generate.add_argument("--split-manifest", type=Path, default=DEFAULT_SPLIT_MANIFEST)
    teacher_generate.add_argument(
        "--partition",
        choices=[split.value for split in SplitName],
        default=SplitName.TRAIN.value,
    )
    teacher_seed_selection = teacher_generate.add_mutually_exclusive_group()
    teacher_seed_selection.add_argument("--seeds", type=int, nargs="+")
    teacher_seed_selection.add_argument("--runs", type=int, default=1)
    teacher_generate.add_argument("--search-simulations", type=int, default=256)
    teacher_generate.add_argument("--evaluation-samples", type=int, default=256)
    teacher_generate.add_argument("--exploration-constant", type=float, default=2**0.5)
    teacher_generate.add_argument("--sampling-seed", type=int, default=0)
    teacher_generate.add_argument("--maximum-rollout-steps", type=int, default=4096)
    teacher_verify = teacher_commands.add_parser(
        "verify", help="Verify teacher identities, independent samples, and split ownership"
    )
    teacher_verify.add_argument("dataset", type=Path)
    teacher_verify.add_argument("--split-manifest", type=Path, default=DEFAULT_SPLIT_MANIFEST)
    teacher_verify.add_argument("--output", type=Path)

    bootstrap = subparsers.add_parser(
        "bootstrap", help="Build and verify the production base-policy curriculum"
    )
    bootstrap_commands = bootstrap.add_subparsers(dest="bootstrap_command", required=True)
    bootstrap_freeze = bootstrap_commands.add_parser(
        "freeze-states", help="Freeze a content-addressed train-state set"
    )
    bootstrap_freeze.add_argument("specification", type=Path)
    bootstrap_freeze.add_argument("output", type=Path)
    bootstrap_freeze.add_argument("--split-manifest", type=Path, required=True)
    bootstrap_discover = bootstrap_commands.add_parser(
        "discover-states",
        help="Discover a frozen train or validation curriculum from exact decision coordinates",
    )
    bootstrap_discover.add_argument("specification", type=Path)
    bootstrap_discover.add_argument("output", type=Path)
    bootstrap_discover.add_argument("--split-manifest", type=Path, required=True)
    bootstrap_discover.add_argument(
        "--backend", choices=("mock", "tactical_mock", "evangambit"), default="evangambit"
    )
    bootstrap_discover.add_argument("--upstream-root", type=Path)
    bootstrap_discover.add_argument("--manifest", type=Path)
    bootstrap_discover.add_argument("--policy-checkpoint", type=Path)
    bootstrap_discover.add_argument("--policy-report", type=Path)
    bootstrap_discover.add_argument("--run-offset", type=int, default=0)
    bootstrap_generate = bootstrap_commands.add_parser(
        "generate", help="Generate paired terminal-first curriculum targets"
    )
    bootstrap_generate.add_argument("output_dir", type=Path)
    bootstrap_generate.add_argument("--states", type=Path, required=True)
    bootstrap_generate.add_argument("--split-manifest", type=Path, required=True)
    bootstrap_generate.add_argument("--objective-config", type=Path, default=DEFAULT_CONFIG)
    bootstrap_generate.add_argument(
        "--backend", choices=("mock", "tactical_mock", "evangambit"), default="evangambit"
    )
    bootstrap_generate.add_argument("--upstream-root", type=Path)
    bootstrap_generate.add_argument("--manifest", type=Path)
    bootstrap_generate.add_argument("--policy-checkpoint", type=Path)
    bootstrap_generate.add_argument("--policy-report", type=Path)
    bootstrap_generate.add_argument("--samples-per-candidate", type=int, default=16)
    bootstrap_generate.add_argument("--sampling-seed", type=int, default=0)
    bootstrap_generate.add_argument("--maximum-prefix-steps", type=int, default=4096)
    bootstrap_generate.add_argument("--maximum-rollout-steps", type=int, default=4096)
    bootstrap_generate.add_argument("--workers", type=int, default=8)
    bootstrap_generate.add_argument("--worker-timeout", type=float, default=120.0)
    bootstrap_generate.add_argument("--resume", action="store_true")
    bootstrap_verify = bootstrap_commands.add_parser(
        "verify", help="Verify identities, train ownership, evidence, and optional exact replay"
    )
    bootstrap_verify.add_argument("report", type=Path)
    bootstrap_verify.add_argument("--split-manifest", type=Path, required=True)
    bootstrap_verify.add_argument("--replay-cases", type=int, default=0)
    bootstrap_verify.add_argument("--output", type=Path)
    bootstrap_combine = bootstrap_commands.add_parser(
        "combine-curricula",
        help="Combine verified, seed-disjoint learned train curricula",
    )
    bootstrap_combine.add_argument("output_dir", type=Path)
    bootstrap_combine.add_argument("components", type=Path, nargs="+")
    bootstrap_combine.add_argument("--split-manifest", type=Path, required=True)

    model = subparsers.add_parser("model", help="Train or verify cheap multi-head models")
    model_commands = model.add_subparsers(dest="model_command", required=True)
    model_train = model_commands.add_parser(
        "train", help="Fit policy, run-value, and tactical-risk heads"
    )
    model_train.add_argument("train_dataset", type=Path)
    model_train.add_argument("validation_dataset", type=Path)
    model_train.add_argument("checkpoint", type=Path)
    model_train.add_argument("--report", type=Path, required=True)
    model_train.add_argument("--split-manifest", type=Path, default=DEFAULT_SPLIT_MANIFEST)
    model_train.add_argument("--epochs", type=int, default=80)
    model_train.add_argument("--learning-rate", type=float, default=0.03)
    model_train.add_argument("--l2-regularization", type=float, default=0.0001)
    model_train.add_argument("--gradient-clip", type=float, default=5.0)
    model_train.add_argument("--vector-dimension", type=int, default=4096)
    model_train.add_argument("--interaction-dimension", type=int, default=8192)
    model_train.add_argument("--tactical-horizon", type=int, default=1)
    model_train.add_argument("--calibration-bins", type=int, default=10)
    model_train.add_argument("--shuffle-seed", type=int, default=0)
    model_train.add_argument(
        "--augmentation",
        type=Path,
        nargs=2,
        action="append",
        default=[],
        metavar=("ITERATION", "SOURCE_CHECKPOINT"),
        help="Add verified selective DAgger labels; may be repeated",
    )
    model_verify = model_commands.add_parser(
        "verify", help="Verify checkpoint and optional training-report identities"
    )
    model_verify.add_argument("checkpoint", type=Path)
    model_verify.add_argument("--report", type=Path)
    model_verify.add_argument("--output", type=Path)
    production_train = model_commands.add_parser(
        "train-curriculum",
        help="Fit the confidence-weighted production base model from curriculum-v2 data",
    )
    production_train.add_argument("train_report", type=Path)
    production_train.add_argument("validation_report", type=Path)
    production_train.add_argument("checkpoint", type=Path)
    production_train.add_argument("--report", type=Path, required=True)
    production_train.add_argument("--split-manifest", type=Path, required=True)
    production_train.add_argument("--epochs", type=int, default=60)
    production_train.add_argument("--learning-rate", type=float, default=0.005)
    production_train.add_argument("--l2-regularization", type=float, default=0.0001)
    production_train.add_argument("--gradient-clip", type=float, default=5.0)
    production_train.add_argument("--vector-dimension", type=int, default=4096)
    production_train.add_argument("--interaction-dimension", type=int, default=8192)
    production_train.add_argument("--tactical-horizon", type=int, default=32)
    production_train.add_argument("--pairwise-noise-floor", type=float, default=0.25)
    production_train.add_argument("--calibration-bins", type=int, default=10)
    production_train.add_argument("--shuffle-seed", type=int, default=0)
    production_train.add_argument("--adagrad-epsilon", type=float, default=1e-8)
    production_train.add_argument("--selection-fraction", type=float, default=0.25)
    production_train.add_argument("--selection-salt", default="production-base-model-selection-v1")
    production_verify = model_commands.add_parser(
        "verify-curriculum",
        help="Verify a production curriculum checkpoint and optional training report",
    )
    production_verify.add_argument("checkpoint", type=Path)
    production_verify.add_argument("--report", type=Path)
    production_verify.add_argument("--output", type=Path)
    production_smoke = model_commands.add_parser(
        "smoke-curriculum",
        help="Run a short candidate-alignment and latency smoke on the admitted backend",
    )
    production_smoke.add_argument("checkpoint", type=Path)
    production_smoke.add_argument("--report", type=Path, required=True)
    production_smoke.add_argument("--upstream-root", type=Path, required=True)
    production_smoke.add_argument("--manifest", type=Path, required=True)
    production_smoke.add_argument("--seeds", type=int, nargs="+", default=[0, 1])
    production_smoke.add_argument("--max-decisions-per-seed", type=int, default=8)
    production_smoke.add_argument("--output", type=Path, required=True)
    production_smoke_verify = model_commands.add_parser(
        "verify-curriculum-smoke",
        help="Verify a production inference smoke and its model/report identities",
    )
    production_smoke_verify.add_argument("smoke", type=Path)
    production_smoke_verify.add_argument("checkpoint", type=Path)
    production_smoke_verify.add_argument("--report", type=Path, required=True)
    production_smoke_verify.add_argument("--output", type=Path)
    production_evaluate = model_commands.add_parser(
        "evaluate-curriculum",
        help="Run a resumable paired full-run evaluation on frozen test seeds",
    )
    production_evaluate.add_argument("checkpoint", type=Path)
    production_evaluate.add_argument("--report", type=Path, required=True)
    production_evaluate.add_argument("--split-manifest", type=Path, required=True)
    production_evaluate.add_argument("--upstream-root", type=Path, required=True)
    production_evaluate.add_argument("--manifest", type=Path, required=True)
    production_evaluate.add_argument("--output-dir", type=Path, required=True)
    production_evaluation_seeds = production_evaluate.add_mutually_exclusive_group()
    production_evaluation_seeds.add_argument("--seeds", type=int, nargs="+")
    production_evaluation_seeds.add_argument("--runs", type=int, default=32)
    production_evaluate.add_argument("--workers", type=int, default=4)
    production_evaluate.add_argument("--max-decisions-per-run", type=int, default=4096)
    production_evaluate.add_argument("--resume", action="store_true")
    production_evaluate_verify = model_commands.add_parser(
        "verify-evaluation-curriculum",
        help="Verify paired full-run cases, aggregates, and frozen identities",
    )
    production_evaluate_verify.add_argument("evaluation", type=Path)
    production_evaluate_verify.add_argument("checkpoint", type=Path)
    production_evaluate_verify.add_argument("--report", type=Path, required=True)
    production_evaluate_verify.add_argument("--split-manifest", type=Path, required=True)
    production_evaluate_verify.add_argument("--output", type=Path)

    calibrate = subparsers.add_parser(
        "calibrate", help="Fit or verify held-out probability calibration"
    )
    calibrate_commands = calibrate.add_subparsers(dest="calibrate_command", required=True)
    calibrate_fit = calibrate_commands.add_parser(
        "fit", help="Fit calibrators and audit uncertainty on disjoint validation runs"
    )
    calibrate_fit.add_argument("checkpoint", type=Path)
    calibrate_fit.add_argument("validation_dataset", type=Path)
    calibrate_fit.add_argument("calibration", type=Path)
    calibrate_fit.add_argument("--report", type=Path, required=True)
    calibrate_fit.add_argument("--split-manifest", type=Path, default=DEFAULT_SPLIT_MANIFEST)
    calibrate_fit.add_argument("--fit-fraction", type=float, default=0.5)
    calibrate_fit.add_argument("--split-salt", default="calibration-v1")
    calibrate_fit.add_argument("--iterations", type=int, default=1000)
    calibrate_fit.add_argument("--learning-rate", type=float, default=0.05)
    calibrate_fit.add_argument("--l2-regularization", type=float, default=0.001)
    calibrate_fit.add_argument("--gradient-clip", type=float, default=5.0)
    calibrate_fit.add_argument("--calibration-bins", type=int, default=10)
    calibrate_fit.add_argument("--policy-confidence-threshold", type=float, default=0.8)
    calibrate_fit.add_argument("--catastrophic-regret-threshold", type=float, default=0.1)
    calibrate_fit.add_argument("--false-safe-risk-threshold", type=float, default=0.2)
    calibrate_fit.add_argument("--false-safe-observed-rate", type=float, default=0.5)
    calibrate_verify = calibrate_commands.add_parser(
        "verify", help="Regenerate and verify calibration artifacts"
    )
    calibrate_verify.add_argument("calibration", type=Path)
    calibrate_verify.add_argument("report", type=Path)
    calibrate_verify.add_argument("checkpoint", type=Path)
    calibrate_verify.add_argument("validation_dataset", type=Path)
    calibrate_verify.add_argument("--split-manifest", type=Path, default=DEFAULT_SPLIT_MANIFEST)
    calibrate_verify.add_argument("--output", type=Path)

    dagger = subparsers.add_parser(
        "dagger", help="Collect student trajectories and selectively relabel decisions"
    )
    dagger_commands = dagger.add_subparsers(dest="dagger_command", required=True)
    dagger_collect = dagger_commands.add_parser(
        "collect-mock", help="Run a reproducible selective DAgger iteration on the mock backend"
    )
    dagger_collect.add_argument("source_checkpoint", type=Path)
    dagger_collect.add_argument("reference_dataset", type=Path)
    dagger_collect.add_argument("output", type=Path)
    dagger_collect.add_argument("--index-output", type=Path)
    dagger_collect.add_argument("--split-manifest", type=Path, default=DEFAULT_SPLIT_MANIFEST)
    dagger_collect.add_argument("--iteration", type=int, default=0)
    dagger_seed_selection = dagger_collect.add_mutually_exclusive_group()
    dagger_seed_selection.add_argument("--seeds", type=int, nargs="+")
    dagger_seed_selection.add_argument("--runs", type=int, default=8)
    dagger_collect.add_argument("--probe-search-simulations", type=int, default=8)
    dagger_collect.add_argument("--probe-evaluation-samples", type=int, default=4)
    dagger_collect.add_argument("--probe-sampling-seed", type=int, default=1)
    dagger_collect.add_argument("--relabel-search-simulations", type=int, default=64)
    dagger_collect.add_argument("--relabel-evaluation-samples", type=int, default=64)
    dagger_collect.add_argument("--relabel-sampling-seed", type=int, default=2)
    dagger_collect.add_argument("--rare-state-max-fraction", type=float, default=0.05)
    dagger_collect.add_argument("--high-entropy-threshold", type=float, default=0.85)
    dagger_collect.add_argument("--confident-error-threshold", type=float, default=0.8)
    dagger_collect.add_argument("--confident-error-regret", type=float, default=0.1)
    dagger_collect.add_argument("--maximum-run-decisions", type=int, default=4096)
    dagger_verify = dagger_commands.add_parser(
        "verify", help="Regenerate and verify a selective DAgger iteration"
    )
    dagger_verify.add_argument("iteration", type=Path)
    dagger_verify.add_argument("source_checkpoint", type=Path)
    dagger_verify.add_argument("reference_dataset", type=Path)
    dagger_verify.add_argument("--split-manifest", type=Path, default=DEFAULT_SPLIT_MANIFEST)
    dagger_verify.add_argument("--output", type=Path)

    tactical_handoff = subparsers.add_parser(
        "tactical-handoff", help="Evaluate tactical leaves with terminal run value"
    )
    tactical_handoff_commands = tactical_handoff.add_subparsers(
        dest="tactical_handoff_command", required=True
    )
    tactical_handoff_benchmark = tactical_handoff_commands.add_parser(
        "benchmark-mock", help="Run the seeded terminal-value versus HP-greedy ablation"
    )
    tactical_handoff_benchmark.add_argument("output", type=Path)
    tactical_handoff_benchmark.add_argument("--seeds", type=int, nargs="+", default=[7, 19, 41])
    tactical_handoff_benchmark.add_argument("--candidate-worlds", type=int, default=2)
    tactical_handoff_benchmark.add_argument("--rollout-samples", type=int, default=8)
    tactical_handoff_benchmark.add_argument("--rollout-horizon", type=int, default=1)
    tactical_handoff_benchmark.add_argument("--exact-terminal-weight", type=float, default=1.0)
    tactical_handoff_benchmark.add_argument("--truncated-rollout-weight", type=float, default=0.5)
    tactical_handoff_benchmark.add_argument("--bootstrap-weight", type=float, default=0.5)
    tactical_handoff_benchmark.add_argument("--maximum-compute-units", type=int, default=128)
    tactical_handoff_benchmark.add_argument("--whole-run-budget", type=int, default=128)
    tactical_handoff_verify = tactical_handoff_commands.add_parser(
        "verify", help="Regenerate and verify a tactical-handoff report"
    )
    tactical_handoff_verify.add_argument("report", type=Path)
    tactical_handoff_verify.add_argument("--output", type=Path)

    demo = subparsers.add_parser("demo", help="Run the seeded mock vertical slice")
    demo.add_argument("--seed", type=int, default=7)
    demo.add_argument("--output", type=Path)

    replay = subparsers.add_parser("replay", help="Verify a recorded mock run")
    replay.add_argument("path", type=Path)

    verify = subparsers.add_parser("verify", help="Alias for deterministic replay verification")
    verify.add_argument("path", type=Path)

    split = subparsers.add_parser("split", help="Freeze and audit complete-run data splits")
    split_commands = split.add_subparsers(dest="split_command", required=True)
    split_freeze = split_commands.add_parser("freeze", help="Create an immutable split manifest")
    split_freeze.add_argument("specification", type=Path)
    split_freeze.add_argument("output", type=Path)
    split_verify = split_commands.add_parser("verify", help="Verify a split manifest identity")
    split_verify.add_argument("manifest", type=Path)
    split_verify.add_argument("--output", type=Path)
    split_freeze_index = split_commands.add_parser(
        "freeze-index", help="Freeze run and encounter membership in a dataset index"
    )
    split_freeze_index.add_argument("manifest", type=Path)
    split_freeze_index.add_argument("specification", type=Path)
    split_freeze_index.add_argument("output", type=Path)
    split_audit = split_commands.add_parser(
        "audit", help="Reject dataset indices that leak records across complete-run splits"
    )
    split_audit.add_argument("manifest", type=Path)
    split_audit.add_argument("dataset_index", type=Path)
    split_audit.add_argument("--output", type=Path)
    split_seeds = split_commands.add_parser("seeds", help="List frozen seeds for one partition")
    split_seeds.add_argument("manifest", type=Path)
    split_seeds.add_argument("partition", choices=[split.value for split in SplitName])
    split_seeds.add_argument("--output", type=Path)

    rollout = subparsers.add_parser("rollout", help="Run and audit isolated full-run workers")
    rollout_commands = rollout.add_subparsers(dest="rollout_command", required=True)
    rollout_run = rollout_commands.add_parser(
        "run-mock", help="Launch a parallel seeded mock rollout batch"
    )
    seed_selection = rollout_run.add_mutually_exclusive_group()
    seed_selection.add_argument("--seeds", type=int, nargs="+")
    seed_selection.add_argument("--episodes", type=int, default=100)
    rollout_run.add_argument("--seed-start", type=int, default=0)
    rollout_run.add_argument("--workers", type=int, default=4)
    rollout_run.add_argument("--maximum-attempts", type=int, default=2)
    rollout_run.add_argument("--worker-timeout", type=float, default=120.0)
    rollout_run.add_argument("--objective-config", type=Path, default=DEFAULT_CONFIG)
    rollout_run.add_argument("--output-dir", type=Path)
    rollout_replay = rollout_commands.add_parser(
        "replay", help="Verify every completed record and aggregate in a rollout batch"
    )
    rollout_replay.add_argument("report", type=Path)
    rollout_replay.add_argument("--output", type=Path)

    benchmark = subparsers.add_parser("benchmark", help="Run the mock fixed-seed benchmark")
    benchmark.add_argument("--episodes", type=int, default=100)
    benchmark.add_argument("--seed-start", type=int, default=0)

    subparsers.add_parser("check", help="Run formatting, typing, tests, and C# build")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "doctor":
        print(json.dumps(diagnostics_as_dict(), indent=2))
        if args.manifest is not None:
            installation = find_game_installation()
            if installation is None:
                return 1
            args.manifest.parent.mkdir(parents=True, exist_ok=True)
            args.manifest.write_text(json.dumps(installation.manifest(), indent=2) + "\n")
        return 0
    if args.command == "manifest":
        if args.manifest_command == "freeze":
            specification = json.loads(args.specification.read_text(encoding="utf-8"))
            manifest = freeze_patch_manifest(
                specification,
                base_directory=args.specification.parent,
            )
            write_frozen_manifest(manifest, args.output)
            print(json.dumps({"path": str(args.output), "manifest_id": manifest.manifest_id}))
            return 0
        installation = None
        if args.installation is not None:
            installation = json.loads(args.installation.read_text(encoding="utf-8"))
        results: list[dict[str, object]] = []
        valid = True
        for path in args.paths:
            try:
                loaded = load_patch_manifest(path)
            except ValueError as error:
                valid = False
                results.append({"path": str(path), "valid": False, "error": str(error)})
            else:
                identity_errors = (
                    verify_installation_identity(loaded, installation)
                    if installation is not None
                    else ()
                )
                if identity_errors:
                    valid = False
                    results.append(
                        {
                            "path": str(path),
                            "valid": False,
                            "errors": list(identity_errors),
                        }
                    )
                else:
                    results.append(
                        {"path": str(path), "valid": True, "manifest_id": loaded.manifest_id}
                    )
        print(json.dumps(results, indent=2))
        return 0 if valid else 1
    if args.command == "live":
        try:
            if args.live_command in {"stop", "resume", "safety-status"}:
                ledger = DurableActionLedger(args.state_dir)
                if args.live_command == "stop":
                    ledger.emergency_stop()
                elif args.live_command == "resume":
                    with ledger.exclusive("safety-resume"):
                        ledger.acknowledge_safety()
                _emit_json(ledger.safety_status(), None)
                return 0
            if args.live_command == "bind":
                snapshot_document = json.loads(args.snapshot.read_text(encoding="utf-8"))
                request = BoundAction.bind(
                    snapshot_document,
                    args.action_id,
                    request_id=args.request_id,
                )
                _emit_json(request.as_dict(), args.output)
                return 0
            if args.live_command == "verify-run":
                verification = verify_live_run(args.record)
                _emit_json(verification.as_dict(), args.output)
                return 0 if verification.valid else 1
            live_manifest = load_patch_manifest(args.manifest)
            if args.live_command == "audit-fixtures":
                fixture_audit = audit_live_fixture_corpus(args.corpus, live_manifest)
                _emit_json(fixture_audit.as_dict(), args.output)
                return 0 if fixture_audit.valid else 1
            if args.live_command == "coverage":
                coverage = audit_full_run_action_coverage(
                    specification_path=args.specification,
                    fixture_corpus_path=args.fixtures,
                    run_paths=tuple(args.runs),
                    manifest=live_manifest,
                )
                _emit_json(coverage.as_dict(), args.output)
                return 0 if coverage.valid else 1
            if args.live_command == "snapshot":
                if args.installation is not None:
                    installation_document: object = json.loads(
                        args.installation.read_text(encoding="utf-8")
                    )
                else:
                    installation = find_game_installation()
                    if installation is None:
                        raise LiveStateError("No supported local STS2 installation was found")
                    installation_document = installation.manifest()
                adapter = Sts2McpLiveStateAdapter(
                    live_manifest,
                    installation_document,
                    Sts2McpHttpTransport(args.base_url, timeout_seconds=args.timeout),
                )
                snapshot = adapter.snapshot()
            elif args.live_command == "project":
                source = json.loads(args.source.read_text(encoding="utf-8"))
                projector = Sts2McpStateProjector(live_manifest)
                snapshot = projector.project(
                    source,
                    bridge_version=args.bridge_version or live_manifest.adapter.version,
                )
            elif args.live_command == "execute":
                request_document = json.loads(args.request.read_text(encoding="utf-8"))
                request = BoundAction.from_mapping(request_document)
                if args.installation is not None:
                    installation_document = json.loads(
                        args.installation.read_text(encoding="utf-8")
                    )
                else:
                    installation = find_game_installation()
                    if installation is None:
                        raise LiveStateError("No supported local STS2 installation was found")
                    installation_document = installation.manifest()
                snapshot_provider = Sts2McpLiveStateAdapter(
                    live_manifest,
                    installation_document,
                    Sts2McpHttpTransport(args.base_url, timeout_seconds=args.timeout),
                )
                executor = GuardedActionExecutor(
                    snapshot_provider=snapshot_provider,
                    action_transport=Sts2McpHttpActionTransport(
                        args.base_url, timeout_seconds=args.timeout
                    ),
                    ledger=DurableActionLedger(args.state_dir),
                    settle_timeout_seconds=args.settle_timeout,
                    settle_quiet_seconds=args.settle_quiet,
                    poll_interval_seconds=args.poll_interval,
                )
                receipt = executor.execute(request, dry_run=not args.apply)
                _emit_json(receipt.as_dict(), args.output)
                return 0 if receipt.status in {ReceiptStatus.APPLIED, ReceiptStatus.DRY_RUN} else 1
            else:
                if not args.apply:
                    raise LiveActionError(
                        "live autoplay controls the visible game; pass --apply to start it"
                    )
                if args.installation is not None:
                    installation_document = json.loads(
                        args.installation.read_text(encoding="utf-8")
                    )
                else:
                    installation = find_game_installation()
                    if installation is None:
                        raise LiveStateError("No supported local STS2 installation was found")
                    installation_document = installation.manifest()
                snapshot_provider = Sts2McpLiveStateAdapter(
                    live_manifest,
                    installation_document,
                    Sts2McpHttpTransport(args.base_url, timeout_seconds=args.timeout),
                )
                executor = GuardedActionExecutor(
                    snapshot_provider=snapshot_provider,
                    action_transport=Sts2McpHttpActionTransport(
                        args.base_url, timeout_seconds=args.timeout
                    ),
                    ledger=DurableActionLedger(args.state_dir),
                    settle_timeout_seconds=args.settle_timeout,
                    settle_quiet_seconds=args.settle_quiet,
                    poll_interval_seconds=args.poll_interval,
                )
                record_path = args.record or _default_live_run_record()
                with LiveRunRecorder(record_path) as recorder:
                    result = run_live_game(
                        snapshot_provider=snapshot_provider,
                        executor=executor,
                        recorder=recorder,
                        policy=WeakLivePolicy(LiveRunStrategy(args.strategy), seed=args.seed),
                        max_actions=args.max_actions,
                        readiness_timeout_seconds=args.readiness_timeout,
                        poll_interval_seconds=args.poll_interval,
                        max_stale_replans=args.max_stale_replans,
                    )
                _emit_json(result.as_dict(), None)
                return 0 if result.status is LiveRunStatus.TERMINAL else 1
        except (
            LiveActionError,
            LiveStateError,
            OSError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            _emit_json({"status": "error", "error": str(error)}, getattr(args, "output", None))
            return 1
        payload = snapshot.as_dict()
        _emit_json(payload, args.output)
        return 0 if snapshot.action_coverage_status != "unsupported" else 1
    if args.command == "conformance":
        if args.conformance_command == "run-mock":
            report = run_environment_conformance(
                MockSpireEnvironment,
                seeds=args.seeds,
                max_steps=args.max_steps,
            ).as_dict()
            _emit_json(report, args.output)
            return 0 if report["verdict"] != "fail" else 1
        if args.conformance_command == "trace-mock":
            trace = capture_conformance_trace(
                MockSpireEnvironment(),
                seed=args.seed,
                fixture_id=args.fixture_id,
            )
            _emit_json(trace, args.output)
            return 0
        reference = json.loads(args.reference.read_text(encoding="utf-8"))
        candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
        differential = compare_conformance_traces(reference, candidate)
        _emit_json(differential, args.output)
        return 0 if differential["verdict"] == "exact_match" else 1
    if args.command == "mechanics":
        fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
        mechanics_report = audit_mechanics_fixture(fixture, MockSpireEnvironment)
        _emit_json(mechanics_report, args.output)
        return 0 if mechanics_report["verdict"] == "pass" else 1
    if args.command == "search":
        if args.search_command == "verify-workers":
            search_verification = verify_search_worker_batch(args.report)
            _emit_json(search_verification.as_dict(), args.output)
            return 0 if search_verification.valid else 1
        if args.search_command == "verify-fixed":
            fixed_verification = verify_fixed_search_report(args.report)
            _emit_json(fixed_verification.as_dict(), args.output)
            return 0 if fixed_verification.valid else 1
        if args.search_command == "verify-benchmark":
            benchmark_verification = verify_search_compute_quality_report(args.report)
            _emit_json(benchmark_verification.as_dict(), args.output)
            return 0 if benchmark_verification.valid else 1
        if args.search_command == "freeze-benchmark-states":
            specification = json.loads(args.specification.read_text(encoding="utf-8"))
            state_set_document = freeze_search_benchmark_state_set(
                specification,
                split_manifest=(
                    load_split_manifest(args.split_manifest)
                    if args.split_manifest is not None
                    else None
                ),
            )
            write_search_benchmark_state_set(state_set_document, args.output)
            _emit_json(state_set_document, None)
            return 0
        if args.search_command == "benchmark-fixed":
            if args.backend == "evangambit":
                if args.upstream_root is None or args.manifest is None:
                    raise ValueError("EvanGambit benchmark requires --upstream-root and --manifest")
                benchmark_backend = SearchBackendSpec.evangambit(
                    args.upstream_root,
                    args.manifest,
                )
            elif args.backend == "tactical_mock":
                benchmark_backend = SearchBackendSpec.tactical_mock()
            else:
                benchmark_backend = SearchBackendSpec.mock()
            benchmark_result = run_search_compute_quality_benchmark(
                backend=benchmark_backend,
                state_set=load_search_benchmark_state_set(args.states),
                config=SearchBenchmarkConfig(
                    search=FixedSearchConfig(
                        tiers=(
                            FixedSearchTier("shallow", args.shallow_simulations),
                            FixedSearchTier("medium", args.medium_simulations),
                            FixedSearchTier("expensive", args.expensive_simulations),
                        ),
                        exploration_constant=args.exploration_constant,
                        sampling_seed=args.sampling_seed,
                        maximum_rollout_steps=args.maximum_rollout_steps,
                        workers=args.workers,
                        worker_timeout_seconds=args.worker_timeout,
                    ),
                    maximum_prefix_steps=args.maximum_prefix_steps,
                    evaluation_samples_per_candidate=args.evaluation_samples,
                    evaluation_sampling_seed=args.evaluation_sampling_seed,
                    evaluation_workers=args.evaluation_workers,
                    evaluation_worker_timeout_seconds=args.evaluation_worker_timeout,
                    calibration_bins=args.calibration_bins,
                ),
                output_directory=args.output_dir,
            )
            benchmark_summary = benchmark_result.report["summary"]
            if isinstance(benchmark_summary, dict):
                write_experiment_metrics(
                    ExperimentMetrics(
                        trajectories=int(benchmark_summary["benchmark_denominator"]),
                        simulations=int(benchmark_summary["simulations"]),
                        transitions=int(benchmark_summary["transitions"]),
                    )
                )
            _emit_json(benchmark_result.report, None)
            return 0 if benchmark_result.successful else 1
        if args.search_command == "fixed-suite":
            if args.backend == "evangambit":
                if args.upstream_root is None or args.manifest is None:
                    raise ValueError(
                        "EvanGambit fixed search requires --upstream-root and --manifest"
                    )
                backend_spec = SearchBackendSpec.evangambit(
                    args.upstream_root,
                    args.manifest,
                )
            elif args.backend == "tactical_mock":
                backend_spec = SearchBackendSpec.tactical_mock()
            else:
                backend_spec = SearchBackendSpec.mock()
            fixed_result = run_fixed_search_suite(
                backend=backend_spec,
                run_seed=args.run_seed,
                output_directory=args.output_dir,
                combat_state_index=args.combat_state_index,
                maximum_prefix_steps=args.maximum_prefix_steps,
                action_prefix=args.action_prefix,
                config=FixedSearchConfig(
                    tiers=(
                        FixedSearchTier("shallow", args.shallow_simulations),
                        FixedSearchTier("medium", args.medium_simulations),
                        FixedSearchTier("expensive", args.expensive_simulations),
                    ),
                    exploration_constant=args.exploration_constant,
                    sampling_seed=args.sampling_seed,
                    maximum_rollout_steps=args.maximum_rollout_steps,
                    workers=args.workers,
                    worker_timeout_seconds=args.worker_timeout,
                ),
            )
            fixed_summary = fixed_result.report["summary"]
            if isinstance(fixed_summary, dict):
                write_experiment_metrics(
                    ExperimentMetrics(
                        simulations=int(fixed_summary["attempted_simulations"]),
                        transitions=int(fixed_summary["transitions"]),
                    )
                )
            _emit_json(fixed_result.report, None)
            return 0 if fixed_result.successful else 1
        search_result = run_search_worker_batch(
            tasks=tuple(load_search_task(path) for path in args.tasks),
            workers=args.workers,
            worker_timeout_seconds=args.worker_timeout,
            output_directory=args.output_dir or _default_search_worker_directory(),
        )
        search_summary = search_result.report["summary"]
        if isinstance(search_summary, dict):
            write_experiment_metrics(
                ExperimentMetrics(
                    simulations=int(search_summary["requested_tasks"]),
                    transitions=int(search_summary["transitions"]),
                )
            )
        _emit_json(search_result.report, None)
        return 0 if search_result.successful else 1
    if args.command == "resources":
        if args.resource_command == "hardware":
            _emit_json(capture_hardware(), args.output)
            return 0
        if args.resource_command == "verify":
            try:
                resource_report = load_resource_report(args.report)
            except (OSError, ValueError, json.JSONDecodeError) as error:
                _emit_json({"valid": False, "errors": [str(error)]}, args.output)
                return 1
            resource_errors = verify_resource_report(resource_report)
            _emit_json(
                {
                    "valid": not resource_errors,
                    "report_id": resource_report.get("report_id"),
                    "errors": list(resource_errors),
                },
                args.output,
            )
            return 0 if not resource_errors else 1
        command_args = tuple(args.command_args)
        if command_args and command_args[0] == "--":
            command_args = command_args[1:]
        try:
            configured_rates = (
                load_cost_rates(args.rates_config, args.rate_profile)
                if args.rates_config is not None
                else CostRates()
            )
            tracked = run_tracked_command(
                command=command_args,
                experiment_kind=ExperimentKind(args.kind),
                report_path=args.report,
                artifact_roots=tuple(args.artifact_root),
                metrics_path=args.metrics,
                workers=args.workers,
                limits=ResourceLimits(
                    wall_seconds=args.max_wall_seconds,
                    cpu_seconds=args.max_cpu_seconds,
                    storage_bytes=args.max_storage_bytes,
                    resident_memory_bytes=args.max_memory_bytes,
                ),
                rates=CostRates(
                    currency=args.currency or configured_rates.currency,
                    cpu_per_hour=(
                        args.cpu_rate
                        if args.cpu_rate is not None
                        else configured_rates.cpu_per_hour
                    ),
                    gpu_per_hour=(
                        args.gpu_rate
                        if args.gpu_rate is not None
                        else configured_rates.gpu_per_hour
                    ),
                    storage_per_gb_month=(
                        args.storage_rate
                        if args.storage_rate is not None
                        else configured_rates.storage_per_gb_month
                    ),
                    electricity_per_kwh=(
                        args.electricity_rate
                        if args.electricity_rate is not None
                        else configured_rates.electricity_per_kwh
                    ),
                ),
                working_directory=args.cwd,
                poll_interval_seconds=args.poll_interval,
            )
        except (OSError, ValueError, json.JSONDecodeError) as error:
            _emit_json({"status": "error", "error": str(error)}, None)
            return 1
        _emit_json(tracked.report, None)
        if tracked.status is ExperimentStatus.CAPPED:
            return 124
        if tracked.status is ExperimentStatus.INTERRUPTED:
            return 130
        return 0 if tracked.exit_code == 0 else tracked.exit_code or 1
    if args.command == "backend":
        try:
            if args.backend_command == "conformance":
                loaded_backend = load_evangambit_backend(
                    args.upstream_root,
                    args.manifest,
                    allow_pending=True,
                    max_episode_steps=args.max_steps,
                )
                backend_report = run_environment_conformance(
                    loaded_backend.factory,
                    seeds=args.seeds,
                    max_steps=args.max_steps,
                ).as_dict()
                _emit_json(backend_report, args.output)
                return 0 if backend_report["verdict"] == "pass" else 1
            if args.backend_command == "admit":
                loaded_backend = load_evangambit_backend(
                    args.upstream_root,
                    args.manifest,
                    allow_pending=True,
                )
                source_manifest = load_patch_manifest(args.manifest)
                assessment = assess_backend_admission(
                    source_manifest,
                    json.loads(args.conformance.read_text(encoding="utf-8")),
                    json.loads(args.external_evidence.read_text(encoding="utf-8")),
                    json.loads(args.installation.read_text(encoding="utf-8")),
                    loaded_backend.evidence,
                    adapter_source=Path(__file__).parent / "adapters/evangambit.py",
                )
                write_backend_admission(
                    assessment,
                    report_path=args.report,
                    manifest_path=(
                        args.admitted_manifest if assessment.admitted_manifest is not None else None
                    ),
                )
                _emit_json(assessment.report, None)
                return 0 if assessment.admitted_manifest is not None else 1
            backend_report = load_backend_admission_report(args.report)
            admitted_manifest = load_patch_manifest(args.manifest) if args.manifest else None
            errors = verify_backend_admission(backend_report, admitted_manifest)
            backend_verification = {
                "valid": not errors,
                "report_id": backend_report.get("report_id"),
                "errors": list(errors),
            }
            _emit_json(backend_verification, args.output)
            return 0 if not errors else 1
        except (
            EvanGambitBackendError,
            OSError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            _emit_json({"status": "error", "error": str(error)}, getattr(args, "output", None))
            return 1
    if args.command == "represent":
        try:
            if args.represent_command == "mock":
                environment = MockSpireEnvironment()
                observation = environment.reset(args.seed)
                representation = build_model_input(
                    environment.ruleset,
                    observation,
                    environment.legal_actions(),
                )
            else:
                live_manifest = load_patch_manifest(args.manifest)
                source = json.loads(args.source.read_text(encoding="utf-8"))
                snapshot = Sts2McpStateProjector(live_manifest).project(
                    source,
                    bridge_version=args.bridge_version or live_manifest.adapter.version,
                )
                representation = build_model_input(
                    snapshot.ruleset,
                    snapshot.observation,
                    snapshot.legal_actions,
                )
            document = (
                vectorize_model_input(representation, dimension=args.dimension).as_dict()
                if args.vectorized
                else representation.as_dict()
            )
            _emit_json(document, args.output)
            return 0
        except (LiveStateError, OSError, ValueError, json.JSONDecodeError) as error:
            _emit_json({"status": "error", "error": str(error)}, args.output)
            return 1
    if args.command == "teacher":
        try:
            split_manifest = load_split_manifest(args.split_manifest)
            if args.teacher_command == "verify":
                teacher_verification = verify_teacher_dataset(
                    load_teacher_dataset(args.dataset),
                    split_manifest,
                )
                _emit_json(teacher_verification.as_dict(), args.output)
                return 0 if teacher_verification.valid else 1
            partition = SplitName(args.partition)
            if args.seeds is None:
                if args.runs <= 0:
                    raise ValueError("--runs must be positive")
                if args.runs > len(split_manifest.seeds(partition)):
                    raise ValueError("--runs exceeds the selected frozen partition")
                seeds = split_manifest.seeds(partition)[: args.runs]
            else:
                seeds = tuple(args.seeds)
            config = TeacherConfig(
                search_simulations=args.search_simulations,
                evaluation_samples_per_candidate=args.evaluation_samples,
                exploration_constant=args.exploration_constant,
                sampling_seed=args.sampling_seed,
                maximum_rollout_steps=args.maximum_rollout_steps,
            )
            dataset = generate_mock_teacher_dataset(
                seeds=seeds,
                partition=partition,
                split_manifest=split_manifest,
                objective=load_objective(DEFAULT_CONFIG),
                config=config,
            )
            index = teacher_dataset_index(dataset, split_manifest)
            index_output = args.index_output or args.output.with_name(
                f"{args.output.stem}-index.json"
            )
            if index_output.resolve() == args.output.resolve():
                raise ValueError("Teacher dataset and index outputs must differ")
            write_teacher_dataset(dataset, args.output)
            write_frozen_dataset_index(index, index_output)
            teacher_summary = dataset["summary"]
            write_experiment_metrics(
                ExperimentMetrics(
                    trajectories=int(teacher_summary["runs"]),
                    simulations=int(teacher_summary["search_simulations"])
                    + int(teacher_summary["evaluation_simulations"]),
                )
            )
            _emit_json(
                {
                    "dataset_path": str(args.output),
                    "dataset_id": dataset["dataset_id"],
                    "index_path": str(index_output),
                    "index_id": index["index_id"],
                    "summary": dataset["summary"],
                },
                None,
            )
            return 0
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
            error_output = args.output if args.teacher_command == "verify" else None
            _emit_json({"status": "error", "error": str(error)}, error_output)
            return 1
    if args.command == "bootstrap":
        try:
            split_manifest = load_split_manifest(args.split_manifest)
            if args.bootstrap_command == "freeze-states":
                specification = json.loads(args.specification.read_text(encoding="utf-8"))
                document = freeze_bootstrap_state_set(
                    specification,
                    split_manifest=split_manifest,
                )
                write_bootstrap_state_set(document, args.output)
                _emit_json(document, None)
                return 0
            if args.bootstrap_command == "discover-states":
                discovery_policy = _bootstrap_policy_artifacts(
                    args.policy_checkpoint,
                    args.policy_report,
                )
                if args.backend == "evangambit":
                    if args.upstream_root is None or args.manifest is None:
                        raise ValueError(
                            "EvanGambit discovery requires --upstream-root and --manifest"
                        )
                    discovery_backend = SearchBackendSpec.evangambit(
                        args.upstream_root, args.manifest
                    )
                elif args.backend == "tactical_mock":
                    discovery_backend = SearchBackendSpec.tactical_mock()
                else:
                    discovery_backend = SearchBackendSpec.mock()
                specification = json.loads(args.specification.read_text(encoding="utf-8"))
                document = discover_curriculum_state_set(
                    specification,
                    backend=discovery_backend,
                    split_manifest=split_manifest,
                    policy_artifacts=discovery_policy,
                    run_offset=args.run_offset,
                )
                write_bootstrap_state_set(document, args.output)
                _emit_json(document, None)
                return 0
            if args.bootstrap_command == "verify":
                bootstrap_verification = verify_bootstrap_teacher_dataset(
                    args.report,
                    split_manifest=split_manifest,
                    replay_cases=args.replay_cases,
                )
                _emit_json(bootstrap_verification.as_dict(), args.output)
                return 0 if bootstrap_verification.valid else 1
            if args.bootstrap_command == "combine-curricula":
                combined = combine_curriculum_datasets(
                    args.components,
                    output_directory=args.output_dir,
                    split_manifest=split_manifest,
                )
                _emit_json(combined.report, None)
                return 0 if combined.successful else 1
            if args.backend == "evangambit":
                if args.upstream_root is None or args.manifest is None:
                    raise ValueError("EvanGambit bootstrap requires --upstream-root and --manifest")
                bootstrap_backend = SearchBackendSpec.evangambit(
                    args.upstream_root,
                    args.manifest,
                )
            elif args.backend == "tactical_mock":
                bootstrap_backend = SearchBackendSpec.tactical_mock()
            else:
                bootstrap_backend = SearchBackendSpec.mock()
            generation_policy = _bootstrap_policy_artifacts(
                args.policy_checkpoint,
                args.policy_report,
            )
            bootstrap_result = run_bootstrap_teacher_dataset(
                backend=bootstrap_backend,
                state_set=load_bootstrap_state_set(args.states),
                split_manifest=split_manifest,
                objective=load_objective(args.objective_config),
                config=BootstrapConfig(
                    samples_per_candidate=args.samples_per_candidate,
                    sampling_seed=args.sampling_seed,
                    maximum_prefix_steps=args.maximum_prefix_steps,
                    maximum_rollout_steps=args.maximum_rollout_steps,
                    workers=args.workers,
                    worker_timeout_seconds=args.worker_timeout,
                ),
                output_directory=args.output_dir,
                resume=args.resume,
                policy_artifacts=generation_policy,
            )
            summary = bootstrap_result.report["summary"]
            if isinstance(summary, dict):
                write_experiment_metrics(
                    ExperimentMetrics(
                        trajectories=int(summary["benchmark_denominator"]),
                        simulations=int(summary["simulations"]),
                        transitions=int(summary["transitions"]),
                    )
                )
            _emit_json(bootstrap_result.report, None)
            return 0 if bootstrap_result.successful else 1
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
            error_output = args.output if args.bootstrap_command == "verify" else None
            _emit_json({"status": "error", "error": str(error)}, error_output)
            return 1
    if args.command == "model":
        try:
            if args.model_command == "verify-evaluation-curriculum":
                evaluation_checkpoint = load_production_model_checkpoint(args.checkpoint)
                evaluation_training_report = load_production_training_report(
                    args.report, checkpoint=evaluation_checkpoint
                )
                evaluation_split = load_split_manifest(args.split_manifest)
                if evaluation_checkpoint["split_manifest_id"] != evaluation_split.manifest_id:
                    raise ValueError("Production evaluation checkpoint and split identities differ")
                evaluation = load_production_policy_evaluation(
                    args.evaluation,
                    model_id=str(evaluation_checkpoint["model_id"]),
                    training_report_id=str(evaluation_training_report["report_id"]),
                    split_manifest=evaluation_split,
                )
                _emit_json(
                    {
                        "valid": True,
                        "model_id": evaluation_checkpoint["model_id"],
                        "training_report_id": evaluation_training_report["report_id"],
                        "evaluation_report_id": evaluation["report_id"],
                    },
                    args.output,
                )
                return 0
            if args.model_command == "evaluate-curriculum":
                evaluation_checkpoint = load_production_model_checkpoint(args.checkpoint)
                evaluation_training_report = load_production_training_report(
                    args.report, checkpoint=evaluation_checkpoint
                )
                evaluation_split = load_split_manifest(args.split_manifest)
                if args.seeds is None:
                    if args.runs <= 0:
                        raise ValueError("Production evaluation --runs must be positive")
                    evaluation_seeds = evaluation_split.seeds(SplitName.TEST)[: args.runs]
                else:
                    evaluation_seeds = tuple(args.seeds)
                evaluation_backend = load_evangambit_backend(
                    args.upstream_root,
                    args.manifest,
                    max_episode_steps=args.max_decisions_per_run + 1,
                )
                probe_environment = evaluation_backend.factory()
                try:
                    evaluation_ruleset = probe_environment.ruleset
                    evaluation_policy = ProductionCheckpointPolicy(
                        checkpoint=evaluation_checkpoint,
                        training_report=evaluation_training_report,
                        ruleset=evaluation_ruleset,
                    )
                finally:
                    close = getattr(probe_environment, "close", None)
                    if callable(close):
                        close()
                evaluation_result = run_production_policy_evaluation(
                    environment_factory=evaluation_backend.factory,
                    ruleset=evaluation_ruleset,
                    learned_policy=evaluation_policy,
                    split_manifest=evaluation_split,
                    training_report_id=str(evaluation_training_report["report_id"]),
                    seeds=evaluation_seeds,
                    workers=args.workers,
                    maximum_decisions_per_run=args.max_decisions_per_run,
                    output_directory=args.output_dir,
                    resume=args.resume,
                )
                evaluation_summary = evaluation_result.report["summary"]
                if isinstance(evaluation_summary, dict):
                    learned_summary = evaluation_summary.get("learned")
                    baseline_summary = evaluation_summary.get("baseline")
                    if isinstance(learned_summary, dict) and isinstance(baseline_summary, dict):
                        write_experiment_metrics(
                            ExperimentMetrics(
                                trajectories=len(evaluation_seeds) * 2,
                                transitions=int(learned_summary["decisions"])
                                + int(baseline_summary["decisions"]),
                            )
                        )
                _emit_json(evaluation_result.report, None)
                return 0 if evaluation_result.successful else 1
            if args.model_command == "verify-curriculum-smoke":
                smoke_checkpoint = load_production_model_checkpoint(args.checkpoint)
                smoke_training_report = load_production_training_report(
                    args.report, checkpoint=smoke_checkpoint
                )
                smoke_document = load_production_inference_smoke(
                    args.smoke,
                    model_id=str(smoke_checkpoint["model_id"]),
                    training_report_id=str(smoke_training_report["report_id"]),
                )
                _emit_json(
                    {
                        "valid": True,
                        "model_id": smoke_checkpoint["model_id"],
                        "training_report_id": smoke_training_report["report_id"],
                        "smoke_report_id": smoke_document["report_id"],
                    },
                    args.output,
                )
                return 0
            if args.model_command == "smoke-curriculum":
                smoke_checkpoint = load_production_model_checkpoint(args.checkpoint)
                smoke_training_report = load_production_training_report(
                    args.report, checkpoint=smoke_checkpoint
                )
                loaded_backend = load_evangambit_backend(args.upstream_root, args.manifest)
                inference_environment = loaded_backend.factory()
                try:
                    inference_policy = ProductionCheckpointPolicy(
                        checkpoint=smoke_checkpoint,
                        training_report=smoke_training_report,
                        ruleset=inference_environment.ruleset,
                    )
                    smoke_document = run_production_inference_smoke(
                        environment=inference_environment,
                        policy=inference_policy,
                        training_report_id=str(smoke_training_report["report_id"]),
                        seeds=tuple(args.seeds),
                        maximum_decisions_per_seed=args.max_decisions_per_seed,
                    )
                    write_production_inference_smoke(smoke_document, args.output)
                finally:
                    close = getattr(inference_environment, "close", None)
                    if callable(close):
                        close()
                _emit_json(smoke_document, None)
                return 0
            if args.model_command == "verify-curriculum":
                checkpoint = load_production_model_checkpoint(args.checkpoint)
                curriculum_training_report = (
                    load_production_training_report(args.report, checkpoint=checkpoint)
                    if args.report is not None
                    else None
                )
                _emit_json(
                    {
                        "valid": True,
                        "model_id": checkpoint["model_id"],
                        "report_id": (
                            None
                            if curriculum_training_report is None
                            else curriculum_training_report["report_id"]
                        ),
                    },
                    args.output,
                )
                return 0
            if args.model_command == "train-curriculum":
                if args.checkpoint.resolve() == args.report.resolve():
                    raise ValueError(
                        "Production checkpoint and training report outputs must differ"
                    )
                split_manifest = load_split_manifest(args.split_manifest)
                production_result = train_production_base_model(
                    train_report_path=args.train_report,
                    validation_report_path=args.validation_report,
                    split_manifest=split_manifest,
                    config=ProductionTrainingConfig(
                        epochs=args.epochs,
                        learning_rate=args.learning_rate,
                        l2_regularization=args.l2_regularization,
                        gradient_clip=args.gradient_clip,
                        vector_dimension=args.vector_dimension,
                        interaction_dimension=args.interaction_dimension,
                        tactical_horizon=args.tactical_horizon,
                        pairwise_noise_floor=args.pairwise_noise_floor,
                        calibration_bins=args.calibration_bins,
                        shuffle_seed=args.shuffle_seed,
                        adagrad_epsilon=args.adagrad_epsilon,
                        selection_fraction=args.selection_fraction,
                        selection_salt=args.selection_salt,
                    ),
                )
                write_production_model_artifact(
                    production_result.checkpoint,
                    args.checkpoint,
                    label="production model checkpoint",
                )
                write_production_model_artifact(
                    production_result.report,
                    args.report,
                    label="production model training report",
                )
                write_experiment_metrics(
                    ExperimentMetrics(
                        trajectories=(
                            int(production_result.report["training_runs"])
                            + int(production_result.report["validation_runs"])
                        ),
                    )
                )
                _emit_json(
                    {
                        "checkpoint_path": str(args.checkpoint),
                        "model_id": production_result.checkpoint["model_id"],
                        "report_path": str(args.report),
                        "report_id": production_result.report["report_id"],
                        "held_out_metrics": production_result.report["held_out_metrics"],
                    },
                    None,
                )
                return 0
            if args.model_command == "verify":
                checkpoint = load_model_checkpoint(args.checkpoint)
                model_training_report = (
                    load_training_report(args.report, checkpoint=checkpoint)
                    if args.report is not None
                    else None
                )
                _emit_json(
                    {
                        "valid": True,
                        "model_id": checkpoint["model_id"],
                        "report_id": (
                            None
                            if model_training_report is None
                            else model_training_report["report_id"]
                        ),
                    },
                    args.output,
                )
                return 0
            if args.checkpoint.resolve() == args.report.resolve():
                raise ValueError("Model checkpoint and training report outputs must differ")
            split_manifest = load_split_manifest(args.split_manifest)
            train_dataset = load_teacher_dataset(args.train_dataset)
            validation_dataset = load_teacher_dataset(args.validation_dataset)
            training_result = train_initial_models(
                train_dataset=train_dataset,
                validation_dataset=validation_dataset,
                split_manifest=split_manifest,
                config=TrainingConfig(
                    epochs=args.epochs,
                    learning_rate=args.learning_rate,
                    l2_regularization=args.l2_regularization,
                    gradient_clip=args.gradient_clip,
                    vector_dimension=args.vector_dimension,
                    interaction_dimension=args.interaction_dimension,
                    tactical_horizon=args.tactical_horizon,
                    calibration_bins=args.calibration_bins,
                    shuffle_seed=args.shuffle_seed,
                ),
                augmentation_iterations=tuple(
                    (
                        load_dagger_iteration(iteration_path),
                        load_model_checkpoint(source_checkpoint_path),
                    )
                    for iteration_path, source_checkpoint_path in args.augmentation
                ),
            )
            write_model_artifact(
                training_result.checkpoint,
                args.checkpoint,
                label="model checkpoint",
            )
            write_model_artifact(
                training_result.report,
                args.report,
                label="model training report",
            )
            write_experiment_metrics(
                ExperimentMetrics(
                    trajectories=len(train_dataset["runs"]) + len(validation_dataset["runs"]),
                )
            )
            _emit_json(
                {
                    "checkpoint_path": str(args.checkpoint),
                    "model_id": training_result.checkpoint["model_id"],
                    "report_path": str(args.report),
                    "report_id": training_result.report["report_id"],
                    "held_out_metrics": training_result.report["held_out_metrics"],
                },
                None,
            )
            return 0
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
            error_output = (
                args.output
                if args.model_command
                in {
                    "verify",
                    "verify-curriculum",
                    "verify-curriculum-smoke",
                    "verify-evaluation-curriculum",
                }
                else None
            )
            _emit_json({"status": "error", "error": str(error)}, error_output)
            return 1
    if args.command == "calibrate":
        try:
            split_manifest = load_split_manifest(args.split_manifest)
            checkpoint = load_model_checkpoint(args.checkpoint)
            validation_dataset = load_teacher_dataset(args.validation_dataset)
            if args.calibrate_command == "verify":
                calibration = load_calibration_artifact(args.calibration, checkpoint=checkpoint)
                report = load_calibration_report(args.report, calibration=calibration)
                calibration_verification = verify_calibration_artifacts(
                    calibration=calibration,
                    report=report,
                    checkpoint=checkpoint,
                    validation_dataset=validation_dataset,
                    split_manifest=split_manifest,
                )
                _emit_json(calibration_verification.as_dict(), args.output)
                return 0 if calibration_verification.valid else 1
            if args.calibration.resolve() == args.report.resolve():
                raise ValueError("Calibration artifact and report outputs must differ")
            calibration_result = calibrate_model(
                checkpoint=checkpoint,
                validation_dataset=validation_dataset,
                split_manifest=split_manifest,
                config=CalibrationConfig(
                    fit_fraction=args.fit_fraction,
                    split_salt=args.split_salt,
                    iterations=args.iterations,
                    learning_rate=args.learning_rate,
                    l2_regularization=args.l2_regularization,
                    gradient_clip=args.gradient_clip,
                    calibration_bins=args.calibration_bins,
                    policy_confidence_threshold=args.policy_confidence_threshold,
                    catastrophic_regret_threshold=args.catastrophic_regret_threshold,
                    false_safe_risk_threshold=args.false_safe_risk_threshold,
                    false_safe_observed_rate=args.false_safe_observed_rate,
                ),
            )
            write_calibration_artifact(
                calibration_result.calibration,
                args.calibration,
                label="model calibration",
            )
            write_calibration_artifact(
                calibration_result.report,
                args.report,
                label="model calibration report",
            )
            write_experiment_metrics(
                ExperimentMetrics(trajectories=len(validation_dataset["runs"]))
            )
            _emit_json(
                {
                    "calibration_path": str(args.calibration),
                    "calibration_id": calibration_result.calibration["calibration_id"],
                    "report_path": str(args.report),
                    "report_id": calibration_result.report["report_id"],
                    "audit": calibration_result.report["audit"],
                },
                None,
            )
            return 0
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
            error_output = args.output if args.calibrate_command == "verify" else None
            _emit_json({"status": "error", "error": str(error)}, error_output)
            return 1
    if args.command == "dagger":
        try:
            split_manifest = load_split_manifest(args.split_manifest)
            source_checkpoint = load_model_checkpoint(args.source_checkpoint)
            reference_dataset = load_teacher_dataset(args.reference_dataset)
            if args.dagger_command == "verify":
                dagger_verification = verify_mock_dagger_iteration(
                    load_dagger_iteration(args.iteration),
                    split_manifest=split_manifest,
                    source_checkpoint=source_checkpoint,
                    reference_dataset=reference_dataset,
                )
                _emit_json(dagger_verification.as_dict(), args.output)
                return 0 if dagger_verification.valid else 1
            reference_seeds = {
                int(run["seed"])
                for run in reference_dataset.get("runs", [])
                if isinstance(run, dict) and isinstance(run.get("seed"), int)
            }
            if args.seeds is None:
                if args.runs <= 0:
                    raise ValueError("--runs must be positive")
                unused_seeds = tuple(
                    seed
                    for seed in split_manifest.seeds(SplitName.TRAIN)
                    if seed not in reference_seeds
                )
                if args.runs > len(unused_seeds):
                    raise ValueError("--runs exceeds unused seeds in the frozen train partition")
                seeds = unused_seeds[: args.runs]
            else:
                seeds = tuple(args.seeds)
            dagger_config = DaggerConfig(
                probe_teacher=TeacherConfig(
                    search_simulations=args.probe_search_simulations,
                    evaluation_samples_per_candidate=args.probe_evaluation_samples,
                    sampling_seed=args.probe_sampling_seed,
                ),
                relabel_teacher=TeacherConfig(
                    search_simulations=args.relabel_search_simulations,
                    evaluation_samples_per_candidate=args.relabel_evaluation_samples,
                    sampling_seed=args.relabel_sampling_seed,
                ),
                rare_state_max_fraction=args.rare_state_max_fraction,
                high_entropy_threshold=args.high_entropy_threshold,
                confident_error_threshold=args.confident_error_threshold,
                confident_error_regret=args.confident_error_regret,
                maximum_run_decisions=args.maximum_run_decisions,
            )
            iteration = generate_mock_dagger_iteration(
                iteration_index=args.iteration,
                seeds=seeds,
                partition=SplitName.TRAIN,
                split_manifest=split_manifest,
                objective=load_objective(DEFAULT_CONFIG),
                source_checkpoint=source_checkpoint,
                reference_dataset=reference_dataset,
                config=dagger_config,
            )
            index = dagger_dataset_index(iteration, split_manifest)
            index_output = args.index_output or args.output.with_name(
                f"{args.output.stem}-index.json"
            )
            if index_output.resolve() == args.output.resolve():
                raise ValueError("DAgger iteration and index outputs must differ")
            write_dagger_iteration(iteration, args.output)
            write_frozen_dataset_index(index, index_output)
            dagger_summary = iteration["summary"]
            write_experiment_metrics(
                ExperimentMetrics(
                    trajectories=int(dagger_summary["runs"]),
                    simulations=sum(
                        int(dagger_summary[key])
                        for key in (
                            "probe_search_simulations",
                            "probe_evaluation_simulations",
                            "relabel_search_simulations",
                            "relabel_evaluation_simulations",
                        )
                    ),
                    transitions=int(dagger_summary["decisions"]),
                )
            )
            _emit_json(
                {
                    "path": str(args.output),
                    "iteration_id": iteration["iteration_id"],
                    "index_path": str(index_output),
                    "index_id": index["index_id"],
                    "source_model_id": iteration["source_model_id"],
                    "summary": iteration["summary"],
                },
                None,
            )
            return 0
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
            error_output = args.output if args.dagger_command == "verify" else None
            _emit_json({"status": "error", "error": str(error)}, error_output)
            return 1
    if args.command == "tactical-handoff":
        try:
            if args.tactical_handoff_command == "verify":
                handoff_verification = verify_mock_tactical_handoff_report(
                    load_tactical_handoff_report(args.report)
                )
                _emit_json(handoff_verification.as_dict(), args.output)
                return 0 if handoff_verification.valid else 1
            handoff_report = benchmark_mock_tactical_handoff(
                seeds=tuple(args.seeds),
                config=TacticalValueConfig(
                    candidate_worlds=args.candidate_worlds,
                    rollout_samples=args.rollout_samples,
                    rollout_horizon=args.rollout_horizon,
                    exact_terminal_weight=args.exact_terminal_weight,
                    truncated_rollout_weight=args.truncated_rollout_weight,
                    bootstrap_weight=args.bootstrap_weight,
                    maximum_compute_units=args.maximum_compute_units,
                ),
                whole_run_budget=args.whole_run_budget,
            )
            write_tactical_handoff_report(handoff_report, args.output)
            sampled_worlds = sum(
                int(case["usage"]["sampled_worlds"])
                for case in handoff_report["cases"]
                if isinstance(case, dict) and isinstance(case.get("usage"), dict)
            )
            write_experiment_metrics(
                ExperimentMetrics(
                    simulations=sampled_worlds,
                    transitions=sum(
                        int(case["usage"]["simulated_transitions"])
                        for case in handoff_report["cases"]
                        if isinstance(case, dict) and isinstance(case.get("usage"), dict)
                    ),
                )
            )
            _emit_json(
                {
                    "path": str(args.output),
                    "report_id": handoff_report["report_id"],
                    "summary": handoff_report["summary"],
                },
                None,
            )
            return 0
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
            error_output = args.output if args.tactical_handoff_command == "verify" else None
            _emit_json({"status": "error", "error": str(error)}, error_output)
            return 1
    if args.command == "demo":
        output = args.output or PROJECT_ROOT / f"artifacts/mock/run-{args.seed}.jsonl"
        run_result = _run_mock(args.seed, output)
        payload = asdict(run_result)
        payload["record_path"] = str(run_result.record_path)
        print(json.dumps(payload, indent=2))
        return 0
    if args.command in {"replay", "verify"}:
        replay_result = verify_mock_replay(args.path)
        print(json.dumps(asdict(replay_result), indent=2))
        return 0 if replay_result.valid else 1
    if args.command == "split":
        try:
            if args.split_command == "freeze":
                specification = json.loads(args.specification.read_text(encoding="utf-8"))
                split_manifest = freeze_split_manifest(specification)
                write_frozen_split_manifest(split_manifest, args.output)
                _emit_json(
                    {
                        "path": str(args.output),
                        "manifest_id": split_manifest.manifest_id,
                        "split_id": split_manifest.split_id,
                    },
                    None,
                )
                return 0
            split_manifest = load_split_manifest(args.manifest)
            if args.split_command == "freeze-index":
                index_specification = json.loads(args.specification.read_text(encoding="utf-8"))
                dataset_index = freeze_dataset_index(index_specification, split_manifest)
                write_frozen_dataset_index(dataset_index, args.output)
                _emit_json(
                    {
                        "path": str(args.output),
                        "index_id": dataset_index["index_id"],
                        "split_manifest_id": split_manifest.manifest_id,
                    },
                    None,
                )
                return 0
            if args.split_command == "verify":
                _emit_json(
                    {
                        "valid": True,
                        "manifest_id": split_manifest.manifest_id,
                        "split_id": split_manifest.split_id,
                        "counts": {
                            split.value: len(split_manifest.seeds(split)) for split in SplitName
                        },
                    },
                    args.output,
                )
                return 0
            if args.split_command == "seeds":
                partition = SplitName(args.partition)
                _emit_json(
                    {
                        "manifest_id": split_manifest.manifest_id,
                        "partition": partition.value,
                        "seeds": list(split_manifest.seeds(partition)),
                    },
                    args.output,
                )
                return 0
            split_audit_result = audit_dataset_index(args.dataset_index, split_manifest)
            _emit_json(split_audit_result.as_dict(), args.output)
            return 0 if split_audit_result.valid else 1
        except (OSError, ValueError, json.JSONDecodeError) as error:
            _emit_json({"status": "error", "error": str(error)}, getattr(args, "output", None))
            return 1
    if args.command == "rollout":
        if args.rollout_command == "replay":
            rollout_replay_result = verify_rollout_batch(args.report)
            _emit_json(rollout_replay_result.as_dict(), args.output)
            return 0 if rollout_replay_result.valid else 1
        seeds = (
            tuple(args.seeds)
            if args.seeds is not None
            else tuple(range(args.seed_start, args.seed_start + args.episodes))
        )
        output_directory = args.output_dir or _default_rollout_directory()
        try:
            rollout_batch_result = run_mock_rollout_batch(
                seeds=seeds,
                workers=args.workers,
                maximum_attempts=args.maximum_attempts,
                worker_timeout_seconds=args.worker_timeout,
                output_directory=output_directory,
                objective_config=args.objective_config,
            )
        except (OSError, ValueError) as error:
            _emit_json({"status": "error", "error": str(error)}, None)
            return 1
        _emit_json(rollout_batch_result.report, None)
        rollout_summary = rollout_batch_result.report["summary"]
        rollout_outcomes = rollout_batch_result.report["outcomes"]
        if isinstance(rollout_summary, dict) and isinstance(rollout_outcomes, list):
            write_experiment_metrics(
                ExperimentMetrics(
                    trajectories=int(rollout_summary["requested_runs"]),
                    simulations=int(rollout_summary["attempts"]),
                    transitions=sum(
                        int(outcome["decisions"])
                        for outcome in rollout_outcomes
                        if isinstance(outcome, dict) and isinstance(outcome.get("decisions"), int)
                    ),
                )
            )
        return 0 if rollout_batch_result.successful else 1
    if args.command == "benchmark":
        if args.episodes <= 0:
            raise SystemExit("--episodes must be positive")
        victories = 0
        compute = 0
        for seed in range(args.seed_start, args.seed_start + args.episodes):
            run_result = _run_mock(seed, PROJECT_ROOT / f"artifacts/mock/benchmark-{seed}.jsonl")
            victories += int(run_result.victory)
            compute += run_result.compute_used
        report = {
            "objective": "terminal_victory",
            "episodes": args.episodes,
            "victories": victories,
            "victory_rate": victories / args.episodes,
            "mean_compute_per_run": compute / args.episodes,
        }
        write_experiment_metrics(
            ExperimentMetrics(
                trajectories=args.episodes,
                simulations=args.episodes,
                transitions=compute,
            )
        )
        print(json.dumps(report, indent=2))
        return 0
    if args.command == "check":
        return _check()
    return 2


def _run_mock(seed: int, output: Path) -> RunResult:
    objective = load_objective(DEFAULT_CONFIG)
    return run_episode(
        environment=MockSpireEnvironment(),
        policy=TerminalVictoryPolicy(),
        budget_controller=PolicyOnlyBudgetController(),
        recorder=JsonlRecorder(output),
        objective=objective,
        seed=seed,
    )


def _emit_json(value: object, output: Path | None) -> None:
    encoded = json.dumps(value, indent=2) + "\n"
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")


def _bootstrap_policy_artifacts(
    checkpoint: Path | None,
    report: Path | None,
) -> BootstrapPolicyArtifacts | None:
    if (checkpoint is None) != (report is None):
        raise ValueError("--policy-checkpoint and --policy-report must be supplied together")
    if checkpoint is None or report is None:
        return None
    return BootstrapPolicyArtifacts.from_paths(checkpoint, report)


def _default_live_run_record() -> Path:
    from datetime import UTC, datetime

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    return PROJECT_ROOT / f"artifacts/live/runs/live-run-{stamp}.jsonl"


def _default_rollout_directory() -> Path:
    from datetime import UTC, datetime

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    return PROJECT_ROOT / f"artifacts/rollouts/mock-{stamp}"


def _default_search_worker_directory() -> Path:
    from datetime import UTC, datetime

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    return PROJECT_ROOT / f"artifacts/search-workers/batch-{stamp}"


def _check() -> int:
    commands = [
        ["ruff", "check", "."],
        ["ruff", "format", "--check", "."],
        ["mypy"],
        ["pytest"],
        ["dotnet", "build", "mod/SpireShift.Protocol/SpireShift.Protocol.csproj", "-v:q"],
        [
            "dotnet",
            "run",
            "--project",
            "mod/SpireShift.Protocol.ContractCheck/SpireShift.Protocol.ContractCheck.csproj",
        ],
    ]
    for command in commands:
        completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
        if completed.returncode != 0:
            return completed.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
