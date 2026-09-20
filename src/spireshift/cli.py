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
from spireshift.recording.jsonl import JsonlRecorder
from spireshift.replay import verify_mock_replay
from spireshift.runner import RunResult, run_episode

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "configs/default.toml"
DEFAULT_LIVE_MANIFEST = PROJECT_ROOT / "manifests/patches/sts2-v0.107.1-sts2mcp-55e0648.json"


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

    demo = subparsers.add_parser("demo", help="Run the seeded mock vertical slice")
    demo.add_argument("--seed", type=int, default=7)
    demo.add_argument("--output", type=Path)

    replay = subparsers.add_parser("replay", help="Verify a recorded mock run")
    replay.add_argument("path", type=Path)

    verify = subparsers.add_parser("verify", help="Alias for deterministic replay verification")
    verify.add_argument("path", type=Path)

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
            live_manifest = load_patch_manifest(args.manifest)
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
            else:
                source = json.loads(args.source.read_text(encoding="utf-8"))
                projector = Sts2McpStateProjector(live_manifest)
                snapshot = projector.project(
                    source,
                    bridge_version=args.bridge_version or live_manifest.adapter.version,
                )
        except (LiveStateError, OSError, ValueError, json.JSONDecodeError) as error:
            _emit_json({"status": "error", "error": str(error)}, args.output)
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
