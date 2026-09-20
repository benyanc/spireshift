from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.agents.baseline import PolicyOnlyBudgetController, TerminalVictoryPolicy
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
