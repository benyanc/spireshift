"""Continue model-owned A8 learning from the frozen archive-fitted policies."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_own_experience
from spireshift import native_a8_own_training as own
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path, _running_games
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_archive_batch import known_seeds
from spireshift.native_a8_archive_fit_inputs import UPDATES, ArchiveFit, archive_fit
from spireshift.native_a8_archive_fit_session import ERRORS, check_inputs, fit_request, journal
from spireshift.native_a8_mix_session import MixWorker
from spireshift.native_a8_own_training_inputs import declaration
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_tactical_session import boundary, frozen
from spireshift.native_compatibility_contract import verified
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_curriculum_config import THREADS
from spireshift.native_flow_inputs_v12 import canonical_seed
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

AREA = "artifacts/native-a8-archive-own-training"
RECIPE = "configs/native-learning/sts2-v0.111.0-a8-archive-own-training-v1.json"
WRAPPER = "scripts/train-a8-from-archive-v1.sh"
MODULE = "spireshift.native_a8_archive_own_training"
SCHEMA = "native-a8-archive-initialized-model-only-ppo-v1"
LIMITS = {
    "wall_seconds": 2700,
    "cpu_seconds": 7200,
    "storage_bytes": 4_000_000_000,
    "resident_memory_bytes": 4_000_000_000,
}


def plan(control: bool) -> dict[str, Any]:
    phase = "control" if control else "train"
    draws = 2 if control else 8
    rounds = 1 if control else 2
    return {
        "development": [] if control else [f"SP1RESH1FTA8AW1D{i:03d}" for i in range(1, 13)],
        "reload": [f"SP1RESH1FTA8AW1R{p}" for p in PLAYERS] if control else [],
        "minimum_complete_games_per_batch": draws,
        "training": [
            {
                "key": f"{phase}-p{p}-r{r}-{i:02d}",
                "partition": phase,
                "player": p,
                "round": r,
                "seed": f"SP1RESH1FTA8AW1{'C' if control else 'T'}{p}{r}{i:02d}",
                "seed_id": 1000 * p + 100 * r + i,
            }
            for p in PLAYERS
            for r in range(1, rounds + 1)
            for i in range(1, draws + 1)
        ],
    }


def implementation(root: Path, prior: dict[str, Any]) -> dict[str, str]:
    paths = {
        WRAPPER,
        "src/spireshift/native_a8_archive_own_training.py",
        *prior["implementation"],
    }
    return {name: _sha_file(root / name) for name in sorted(paths)}


def inputs(root: Path) -> tuple[ArchiveFit, dict[str, Any], dict[str, Any]]:
    study = archive_fit(root)
    prior = declaration(root)
    cfg = json.loads((root / RECIPE).read_text())
    audit = identified(verified(root, cfg["comparison_audit"]))
    holdout = identified(verified(root, cfg["held_world_agreement"]))
    fit = journal(study, False)
    comparison_path = verified(root, audit["comparison"])
    comparison = identified(comparison_path)
    expected = {
        "schema_version": SCHEMA,
        "workspace": f"{AREA}/study-v1",
        "control_workspace": f"{AREA}/control-v1",
        "control_resource": f"{AREA}/control-v1-resources.json",
        "study": plan(False),
        "control": plan(True),
        "session_limits": LIMITS,
        "implementation": implementation(root, prior),
        "environment_id": study.base.ctx["environment_id"],
        "objective": study.cfg["objective"],
        **{
            key: prior[key]
            for key in (
                "settings",
                "credit",
                "game_limits",
                "control_limits",
                "training_score_id",
                "policy_contract",
                "control_prefix_choices",
            )
        },
    }
    if (
        any(cfg.get(key) != value for key, value in expected.items())
        or comparison_path != fit.workspace / "report.json"
        or comparison["report_id"] != audit["comparison"]["report_id"]
        or holdout["fit_comparison_id"] != comparison["report_id"]
        or audit["games_verified"] != 48
        or holdout["optimizer_updates"] != 0
        or audit["frozen_checks"] != study.frozen_checks
        or holdout["frozen_checks"] != study.frozen_checks
    ):
        raise ValueError("Require the exact fitted copies and saved fresh-world assessment")
    seeds = [
        *cfg["study"]["development"],
        *cfg["control"]["reload"],
        *(task["seed"] for key in ("study", "control") for task in cfg[key]["training"]),
    ]
    used = (
        known_seeds(study.base)
        | {row["seed"] for row in study.bank["worlds"].values()}
        | set(study.cfg["development"] + study.cfg["final_test"])
        | {study.cfg["control"]["prefix_world"], study.cfg["control"]["ending_world"]}
    )
    if len(set(seeds)) != len(seeds) or used.intersection(seeds):
        raise ValueError("Require disjoint training, control, development and final-test worlds")
    for seed in seeds:
        canonical_seed(seed)

    refs = {}
    for p in PLAYERS:
        key = f"fit-p{p}"
        seal = fit.completed(key, fit_request(study, p, UPDATES))
        if seal is None or comparison["seals"][key] != seal["report_id"]:
            raise ValueError("Require the exact sealed archive-fitted checkpoint")
        state = own.restored(fit, key, seal)
        path = fit.path(key) / "state.json"
        ref = {
            "path": str(path.relative_to(root)),
            "sha256": _sha_file(path),
            "model_id": state[0].model_id,
            "state_id": state[2],
            "optimizer_id": seal["result"]["optimizer_id"],
            "optimizer_steps": state[1].steps,
        }
        refs[f"p{p}-original"] = ref
    if cfg["warm_start_states"] != refs:
        raise ValueError("Archive-fitted weights or the full Adam state differ")
    return study, cfg, refs


def play(
    ctx: dict[str, Any],
    task: dict[str, Any],
    target: Path,
    model: CachedContextModel,
    deadline: float,
) -> dict[str, Any]:
    with patch.object(native_a8_own_experience, "worker", MixWorker):
        return native_a8_own_experience.play(ctx, task, target, model, deadline)


def run(
    study: ArchiveFit,
    cfg: dict[str, Any],
    refs: dict[str, Any],
    *,
    control: bool,
    attempt: int,
    deadline: float,
) -> dict[str, Any]:
    base = study.base
    ctx = {**base.ctx, "states": {**base.ctx["states"], **refs}}

    def check_frozen(root: Path, _: dict[str, Any]) -> dict[str, bool]:
        for ref in refs.values():
            verified(root, ref)
        return frozen(root, base.ctx)

    def check_boundary(
        root: Path, _: dict[str, Any], before: dict[str, bool], profile: dict[str, Any]
    ) -> None:
        for ref in refs.values():
            verified(root, ref)
        boundary(root, base.ctx, before, profile)

    check_inputs(study)
    # Reuse the existing collect, exact-delivery audit, PPO and paired
    # evaluation loop. Its reference copy is the frozen archive fit.
    with patch.multiple(
        own, RECIPE=RECIPE, SCHEMA=SCHEMA, frozen=check_frozen, boundary=check_boundary, play=play
    ):
        result = own.run(
            base.root, ctx, base.runtime, cfg, control=control, attempt=attempt, deadline=deadline
        )
    check_inputs(study)
    return result


def require_control(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    with patch.object(own, "MODULE", MODULE):
        proof = own.require_control(root, cfg)
    for p in PLAYERS:
        if (
            proof["rounds"][f"fit-p{p}-r1"]["predecessor_state_id"]
            != cfg["warm_start_states"][f"p{p}-original"]["state_id"]
        ):
            raise ValueError("The short check did not start from the archive fit")
    return proof


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--control", action="store_true")
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--execute-control", type=int, help=argparse.SUPPRESS)
    modes.add_argument("--execute-study", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the launcher with its fixed numerical settings")
        study, cfg, refs = inputs(root)
        control = args.control or args.execute_control is not None
        attempt = args.execute_control if control else args.execute_study
        limits = cfg["control_limits" if control else "session_limits"]
        if not control:
            proof = require_control(root, cfg)
        if args.preflight:
            print(
                json.dumps(
                    {
                        "status": "archive_initialized_a8_training_ready",
                        "control_id": proof["report_id"],
                        "frozen_checks": study.frozen_checks,
                    }
                )
            )
            return 0
        if attempt is not None:
            result = run(
                study,
                cfg,
                refs,
                control=control,
                attempt=attempt,
                deadline=started + limits["wall_seconds"] - 12,
            )
            print(
                json.dumps(
                    {
                        k: result[k]
                        for k in (
                            "status",
                            "report_id",
                            "stop",
                            "training_outcomes",
                            "optimizer_updates_in_sealed_rounds",
                            "development",
                        )
                    }
                ),
                flush=True,
            )
            return 0 if result["stop"] is None else 2
        if _running_games():
            raise ValueError("Close STS2 and wait for any other native worker")
        attempt = time.time_ns()
        workspace = _private_path(root, cfg["control_workspace" if control else "workspace"])
        resource = (
            cfg["control_resource"] if control else f"{AREA}/study-v1-{attempt}-resources.json"
        )
        if control:
            print("Four disposable training games and two native reload checks.", flush=True)
        else:
            print(
                "Close STS2. Train on 32 model-owned games, then compare 48 matched fresh games. "
                "Allow about 12 to 25 minutes.",
                flush=True,
            )
        tracked = run_tracked_command(
            command=[
                "uv",
                "run",
                "--no-sync",
                "python",
                "-m",
                MODULE,
                "--execute-control" if control else "--execute-study",
                str(attempt),
            ],
            experiment_kind=ExperimentKind.TRAINING,
            report_path=_private_path(root, resource),
            artifact_roots=[workspace],
            working_directory=root,
            limits=ResourceLimits(**limits),
        )
        print(json.dumps(tracked.report), flush=True)
        return 2 if tracked.exit_code is None else tracked.exit_code
    except ERRORS as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc)}), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
