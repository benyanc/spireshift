from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

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
from spireshift.doctor import diagnostics_as_dict, find_game_installation
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
from spireshift.models import (
    TrainingConfig,
    load_model_checkpoint,
    load_training_report,
    train_initial_models,
    write_model_artifact,
)
from spireshift.recording.jsonl import JsonlRecorder
from spireshift.replay import verify_mock_replay
from spireshift.representations import (
    DEFAULT_VECTOR_DIMENSION,
    build_model_input,
    vectorize_model_input,
)
from spireshift.rollouts import run_mock_rollout_batch, verify_rollout_batch
from spireshift.runner import RunResult, run_episode
from spireshift.splits import (
    SplitName,
    audit_dataset_index,
    freeze_dataset_index,
    freeze_split_manifest,
    load_split_manifest,
    write_frozen_dataset_index,
    write_frozen_split_manifest,
)
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
DEFAULT_LIVE_FIXTURE_CORPUS = PROJECT_ROOT / "tests/fixtures/live/public-state-corpus-v1.json"
DEFAULT_LIVE_COVERAGE_SPEC = PROJECT_ROOT / "configs/live-coverage-v0.107.1.json"
DEFAULT_SPLIT_MANIFEST = PROJECT_ROOT / "manifests/splits/mock-v1-seeds-000000-000999-v1.json"


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
    model_verify = model_commands.add_parser(
        "verify", help="Verify checkpoint and optional training-report identities"
    )
    model_verify.add_argument("checkpoint", type=Path)
    model_verify.add_argument("--report", type=Path)
    model_verify.add_argument("--output", type=Path)

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
    if args.command == "model":
        try:
            if args.model_command == "verify":
                checkpoint = load_model_checkpoint(args.checkpoint)
                loaded_training_report = (
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
                            if loaded_training_report is None
                            else loaded_training_report["report_id"]
                        ),
                    },
                    args.output,
                )
                return 0
            if args.checkpoint.resolve() == args.report.resolve():
                raise ValueError("Model checkpoint and training report outputs must differ")
            split_manifest = load_split_manifest(args.split_manifest)
            training_result = train_initial_models(
                train_dataset=load_teacher_dataset(args.train_dataset),
                validation_dataset=load_teacher_dataset(args.validation_dataset),
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
            error_output = args.output if args.model_command == "verify" else None
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


def _default_live_run_record() -> Path:
    from datetime import UTC, datetime

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    return PROJECT_ROOT / f"artifacts/live/runs/live-run-{stamp}.jsonl"


def _default_rollout_directory() -> Path:
    from datetime import UTC, datetime

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    return PROJECT_ROOT / f"artifacts/rollouts/mock-{stamp}"


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
