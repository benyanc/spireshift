"""Verify the sealed short fits and complete fresh reload checks separately."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_world_credit_session as first
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_feedback_session import LIMITS, copied_state
from spireshift.native_a8_mix_session import PREFIX_CHOICES, Study, game, unchanged
from spireshift.native_a8_own_training import FAILURES, SCOPE, State
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_rescue_game import TRACE
from spireshift.native_a8_tactical_session import boundary, frozen
from spireshift.native_a8_world_credit import FITTED
from spireshift.native_compatibility_contract import verified
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS, execution_runtime
from spireshift.native_flow_verification_v12 import records
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

MODULE = "spireshift.native_a8_world_credit_reload"
RECIPE = "configs/native-learning/sts2-v0.111.0-a8-world-credit-reload-v3.json"
STUDY_RECIPE = "configs/native-learning/sts2-v0.111.0-a8-world-credit-study-v3.json"
WRAPPER = "scripts/train-a8-world-credit-v3.sh"
SCHEMA = "native-a8-world-credit-reload-v3"
READY = "world_credit_short_checks_verified"
SEED = "SP1RESH1FTA8WR3P001"
SHORT_LIMITS = {**LIMITS, "wall_seconds": 115, "cpu_seconds": 170}


def implementation(root: Path) -> dict[str, str]:
    paths = (WRAPPER, "src/spireshift/native_a8_world_credit_reload.py")
    return {name: _sha_file(root / name) for name in paths}


def case_key(key: str) -> str:
    return key.replace("_", "-")


def corrected_study(recipe: dict[str, Any]) -> dict[str, Any]:
    evaluation = [{**task, "key": case_key(task["key"])} for task in recipe["study"]["evaluation"]]
    return {
        **recipe,
        "study": {**recipe["study"], "evaluation": evaluation},
        "workspace": f"{first.AREA}/study-v3",
    }


def tasks() -> list[dict[str, Any]]:
    return [
        {
            "key": case_key(f"reload-p{p}-{arm}"),
            "seed": SEED,
            "player": p,
            "arm": arm,
            "partition": "reload_control",
        }
        for p in PLAYERS
        for arm in FITTED
    ]


def admitted(
    root: Path,
) -> tuple[Study, dict[str, Any], dict[str, Any], dict[tuple[int, str], State]]:
    base, recipe = first.inputs(root)
    cfg = json.loads((root / RECIPE).read_text())
    corrected_path = verified(root, cfg["corrected_study_recipe"])
    corrected = json.loads(corrected_path.read_text())
    if (
        cfg["schema_version"] != SCHEMA
        or verified(root, cfg["study_recipe"]) != root / first.RECIPE
        or corrected_path != root / STUDY_RECIPE
        or corrected != corrected_study(recipe)
        or cfg["implementation"] != implementation(root)
        or cfg["reloads"] != tasks()
        or SEED
        in {
            t["seed"]
            for phase in ("control", "study")
            for rows in recipe[phase].values()
            for t in rows
        }
    ):
        raise ValueError("Require the exact short-check continuation")
    original = first.journal(root, recipe, True)
    resource_path = verified(root, cfg["first_resources"])
    report_path = verified(root, cfg["first_report"])
    resource, report = (identified(path) for path in (resource_path, report_path))
    if (
        resource_path != _private_path(root, recipe["control_resource"])
        or report_path != original.workspace / f"attempt-{int(resource['command'][-1])}.json"
        or resource["command"][:-1]
        != ["uv", "run", "--no-sync", "python", "-m", first.MODULE, "--check"]
        or resource["limits"] != first.SHORT_LIMITS
        or resource["status"] != "failed"
        or resource["exit_code"] != 2
        or resource["cap"] is not None
        or resource["artifacts"]["roots"] != [str(original.workspace)]
        or report["status"] != "world_credit_incomplete"
        or report["config_id"] != original.config_id
        or report["training"] != {"win": 0, "loss": 12, "capped": 0, "failed": 0, "unattempted": 0}
        or report["stop"]["unit"] != recipe["control"]["evaluation"][0]["key"]
        or report["original_optimizer_updates"] != 0
        or report["forced_action_probes_used"] != 0
    ):
        raise ValueError("Require the exact stopped short check with sealed training games")
    states = {}
    with (original.workspace / "session.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        if (
            json.loads((original.workspace / "config-at-launch.json").read_text())
            != original.recipe
        ):
            raise ValueError("The first short-check recipe changed")
        fit_seals: dict[int, list[str]] = {p: [] for p in PLAYERS}
        for task in recipe["control"]["training"]:
            key, player = task["key"], task["player"]
            seal = original.completed(key, {"task": task, "state_id": base.originals[player][2]})
            if (
                seal is None
                or seal["report_id"] != report["seals"][key]
                or seal["result"] != report["games"][key]
            ):
                raise ValueError("The sealed full-menu short run changed")
            fit_seals[player].append(seal["report_id"])
        for p in PLAYERS:
            key = f"fit-p{p}"
            request = {
                "player": p,
                "original_id": base.originals[p][2],
                "training_seals": fit_seals[p],
            }
            seal = original.completed(key, request)
            if (
                seal is None
                or seal["report_id"] != report["seals"][key]
                or seal["result"] != report["fits"][str(p)]
            ):
                raise ValueError("The sealed full weights or Adam state changed")
            for arm in FITTED:
                states[p, arm] = copied_state(original, p, arm, seal["result"])
        pending = original.path(report["stop"]["unit"])
        closed = json.loads((pending / "worker/closed.json").read_text())
        (last,) = records(pending / TRACE)
        if (
            (pending / "done.json").exists()
            or (pending / "worker/public-receipts.jsonl.gz").exists()
            or (pending / "worker/answer-plan-deliveries.jsonl.gz").exists()
            or last["kind"] != "final_observation"
            or last["frame"]["terminal"] is not False
            or closed["clean_exit"] is not True
            or closed["runtime_errors"]
            or cfg["preserved_trace_sha256"] != _sha_file(pending / TRACE)
            or cfg["preserved_marker_sha256"] != _sha_file(pending / "active.json")
        ):
            raise ValueError("The preserved zero-delivery reload boundary differs")
    return base, corrected, cfg, states


def reloads(
    base: Study, cfg: dict[str, Any], states: dict[tuple[int, str], State], deadline: float
) -> dict[str, Any]:
    store = ChunkJournal(base.root, cfg)
    before, profile = frozen(base.root, base.ctx), _shared_snapshot(Path.home() / SHARED_PROFILE)
    verified_games: dict[str, Any] = {}
    initials = set()
    with store.lock():
        for task in tasks():
            key = task["key"]
            state = states[task["player"], task["arm"]]
            request = {"task": task, "state_id": state[2]}
            unchanged(base, before, deadline)
            boundary(base.root, base.ctx, before, profile)
            seal = store.completed(key, request)
            if seal is None:
                store.begin(key, request)
                row = game(base, store, task, state, deadline)
                if row["outcome"] != "capped" or row["native_decisions"] != PREFIX_CHOICES:
                    raise ValueError("The fresh reload did not deliver exactly four choices")
                boundary(base.root, base.ctx, before, profile)
                seal = store.commit(key, request, row)
            row = seal["result"]
            initials.add(row["initial_public_input_id"])
            verified_games[key] = {
                "seal_id": seal["report_id"],
                "decisions": row["native_decisions"],
            }
            print(f"{key} verified {row['native_decisions']} native choices", flush=True)
        unchanged(base, before, deadline)
        if (
            len(initials) != 1
            or execution_runtime(base.ctx["node"]) != base.runtime
            or json.loads((base.root / RECIPE).read_text()) != cfg
            or cfg["implementation"] != implementation(base.root)
        ):
            raise ValueError("Fresh reload starts or protected inputs differ")
        return write(
            store.workspace / "report.json",
            {
                "schema_version": SCHEMA,
                "status": READY,
                "config_id": store.config_id,
                "first_report": cfg["first_report"],
                "games": verified_games,
                "frozen_checks": before,
                "optimizer_updates": 0,
                **SCOPE,
            },
        )


def require_reloads(
    base: Study, cfg: dict[str, Any], states: dict[tuple[int, str], State]
) -> dict[str, Any]:
    store = ChunkJournal(base.root, cfg)
    proof = identified(store.workspace / "report.json")
    resource = identified(_private_path(base.root, cfg["control_resource"]))
    if (
        proof["status"] != READY
        or proof["config_id"] != store.config_id
        or proof["first_report"] != cfg["first_report"]
        or proof["frozen_checks"] != frozen(base.root, base.ctx)
        or proof["optimizer_updates"] != 0
        or resource["status"] != "completed"
        or resource["exit_code"] != 0
        or resource["cap"] is not None
        or resource["command"] != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--check"]
        or resource["limits"] != SHORT_LIMITS
        or resource["artifacts"]["roots"] != [str(store.workspace)]
    ):
        raise ValueError("Require the exact passing independent reload check")
    for task in tasks():
        state = states[task["player"], task["arm"]]
        seal = store.completed(task["key"], {"task": task, "state_id": state[2]})
        expected = proof["games"][task["key"]]
        if (
            seal is None
            or seal["report_id"] != expected["seal_id"]
            or expected["decisions"] != PREFIX_CHOICES
        ):
            raise ValueError("Fresh reload evidence changed")
    return proof


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--control", action="store_true")
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--study", type=int)
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the launcher with its fixed numerical settings")
        base, recipe, cfg, states = admitted(root)
        if args.check:
            print(
                json.dumps(reloads(base, cfg, states, started + SHORT_LIMITS["wall_seconds"] - 15))
            )
            return 0
        if args.control:
            workspace = ChunkJournal(root, cfg).workspace
            resource = _private_path(root, cfg["control_resource"])
            mode, limits = ["--check"], SHORT_LIMITS
        else:
            proof = require_reloads(base, cfg, states)
            if args.preflight:
                print(
                    json.dumps(
                        {
                            "status": READY,
                            "short_check_id": proof["report_id"],
                            **{k: len(v) for k, v in recipe["study"].items()},
                        }
                    )
                )
                return 0
            if args.study is not None:
                with patch.object(first, "RECIPE", STUDY_RECIPE):
                    result = first.execute(
                        base,
                        recipe,
                        args.study,
                        started + LIMITS["wall_seconds"] - 40,
                        control=False,
                    )
                after = admitted(root)
                if after[2] != cfg or require_reloads(after[0], cfg, after[3]) != proof:
                    raise ValueError("The short-check admission changed during the study")
                print(json.dumps({k: v for k, v in result.items() if k not in {"games", "seals"}}))
                return 0 if result["status"] == first.COMPLETE else 2
            attempt = time.time_ns()
            workspace = first.journal(root, recipe, False).workspace
            resource = workspace.with_name(f"{workspace.name}-{attempt}-resources.json")
            mode, limits = ["--study", str(attempt)], LIMITS
            print(
                "Close STS2. Allow 25–40 minutes for 48 training games "
                "and up to 48 evaluation games.",
                flush=True,
            )
        if resource.exists():
            raise FileExistsError("Preserve the previous resource receipt")
        tracked = run_tracked_command(
            command=["uv", "run", "--no-sync", "python", "-m", MODULE, *mode],
            experiment_kind=ExperimentKind.OTHER if args.control else ExperimentKind.TRAINING,
            report_path=resource,
            artifact_roots=[workspace],
            working_directory=root,
            limits=ResourceLimits(**limits),
        )
        print(json.dumps(tracked.report, indent=2))
        return 0 if tracked.exit_code == 0 and tracked.status == "completed" else 2
    except FAILURES as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
