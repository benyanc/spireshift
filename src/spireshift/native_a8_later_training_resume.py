"""Continue shared-head training without replaying an uncertain save load."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import time
from pathlib import Path
from typing import Any

from spireshift import native_a8_head_grid_resume as prior
from spireshift import native_a8_later_load_v2 as file_load
from spireshift import native_a8_later_recovery as recovery
from spireshift import native_a8_later_training as previous
from spireshift import native_a8_later_training_plan as plan
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.engine_worker import worker_helpers
from spireshift.native_a8_archive_fit_session import ERRORS
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_head_study import CleanPause, Saved
from spireshift.native_a8_own_training import SCOPE
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_reward_exit_recovery import chunk_evidence_id
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_flow_verification_v12 import records
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

MODULE = "spireshift.native_a8_later_training_resume"
RECIPE = "configs/native-learning/sts2-v0.111.0-a8-shared-later-act-resume-v1.json"
WRAPPER = "scripts/resume-a8-shared-later-acts-v1.sh"
SCHEMA = "native-a8-shared-later-act-load-continuation-v1"
CONTROL = "prepared_file_load_verified"
CONTROL_WORLDS = ("c04a2v2", "c04a3v2")


def implementation(root: Path) -> dict[str, str]:
    names = {
        WRAPPER,
        *(f"scripts/{name}" for name in worker_helpers(root, file_load.SCRIPT)),
        *(
            f"src/spireshift/native_a8_later_{part}.py"
            for part in ("load_v2", "recovery", "training_resume")
        ),
    }
    return {name: _sha_file(root / name) for name in sorted(names)}


def control_store(root: Path, cfg: dict[str, Any]) -> ChunkJournal:
    launch = verified(root, cfg["file_load_control"]["launch"])
    recipe = json.loads(launch.read_text())
    expected = {key: value for key, value in cfg.items() if key != "file_load_control"}
    expected["workspace"] = cfg["control_workspace"]
    # The controls exercised the same load path before the continuation could
    # restore the stopped training slot. Allow only that orchestration change.
    runner = f"src/{MODULE.replace('.', '/')}.py"
    expected["implementation"] = {**cfg["implementation"], runner: recipe["implementation"][runner]}
    store = ChunkJournal(root, recipe)
    if recipe != expected or launch != store.workspace / "config-at-launch.json":
        raise ValueError("The file-load control and continuation inputs differ")
    return store


def verify_control_delivery(target: Path, start: dict[str, Any]) -> dict[str, Any]:
    worker = target / "worker"
    dispatch, response = [
        json.loads(line) for line in (worker / "prepared-load.jsonl").read_text().splitlines()
    ]
    loads = [
        row
        for row in records(worker / "private-transcript.jsonl.gz")
        if row["request"]["cmd"] == "load_save"
    ]
    file = worker / "private-profile/prepared-start.save"
    if (
        dispatch["status"] != "dispatching"
        or dispatch["seed"] != start["seed"]
        or dispatch["transport"] != "native_save_path"
        or dispatch["bytes"] != file.stat().st_size
        or dispatch["save_sha256"] != start["save_sha256"]
        or _sha_file(file) != start["save_sha256"]
        or response["status"] != "native_response"
        or len(loads) != 1
        or loads[0]["request"] != {"cmd": "load_save", "path": str(file)}
        or loads[0]["response"]["decision"] != response["decision"]
    ):
        raise ValueError("The exact staged save and single native load must match")
    return {
        "transport": "native_save_path",
        "native_load_requests": 1,
        "save_sha256": dispatch["save_sha256"],
        "loaded_decision": response["decision"],
    }


def require_control(study: previous.Study, cfg: dict[str, Any]) -> str:
    root = study.recovery.root
    store = control_store(root, cfg)
    path = verified(root, cfg["file_load_control"]["report"])
    if path != store.workspace / "report.json":
        raise ValueError("Use the sealed file-load control report")
    report = identified(path)
    if (
        report["status"] != CONTROL
        or report["config_id"] != store.config_id
        or report["optimizer_updates"] != 0
        or set(report["seals"]) != {f"{key}-p2" for key in CONTROL_WORLDS}
        or report["frozen_checks"] != study.recovery.original.source.study.frozen_checks
    ):
        raise ValueError("Require the two verified file-load controls")
    old_control = study.store(True)
    worlds = {world["key"]: world for world in study.worlds["controls"]}
    for key in CONTROL_WORLDS:
        world = worlds[key]
        start = recovery.require_seal(old_control, f"{key}-start", recovery.start_request(world))[
            "result"
        ]
        task = plan.training_task(world, 2, 1, start["seed"], True)
        request = recovery.game_request(task, study.parents[2], start)
        game_key = task["key"]
        seal = recovery.require_seal(store, game_key, request)
        old = recovery.require_seal(old_control, game_key, request)["result"]
        delivery = verify_control_delivery(store.path(game_key), start)
        expected = {**old, **delivery}
        # Resource measurements and episode receipts include the new process.
        same = expected.keys() - {"native_cpu_seconds", "episode_report_id"}
        if seal["report_id"] != report["seals"][game_key] or any(
            seal["result"][field] != expected[field] for field in same
        ):
            raise ValueError(f"The prepared file-load control changed: {game_key}")
    return str(report["report_id"])


class Study(previous.Study):
    def __init__(
        self,
        study: previous.Study,
        history: ChunkJournal,
        resume: dict[str, Any],
        carried: dict[str, Any],
    ) -> None:
        super().__init__(
            study.recovery,
            study.cfg,
            study.ctx,
            study.worlds,
            study.parents,
            study.checkpoint_sources,
            study.bank,
        )
        self.history, self.resume, self.carried = history, resume, carried

    def store(self, control: bool) -> ChunkJournal:
        if control:
            return control_store(self.recovery.root, self.resume)
        return recovery.HistoryJournal(self.history, self.resume, self.carried["carried"])

    def unchanged(self, profile: dict[str, Any]) -> None:
        super().unchanged(profile)
        root = self.recovery.root
        if json.loads((root / RECIPE).read_text()) != self.resume:
            raise ValueError("The continuation recipe changed")
        check_sources(root, self.resume["implementation"])
        for key in ("interrupted_report", "interrupted_resources"):
            verified(root, self.resume[key])
        if chunk_evidence_id(self.history.path(recovery.FAILED)) != self.resume["failed_chunk_id"]:
            raise ValueError("The interrupted prepared game changed")


class Session(previous.Session):
    def __init__(self, study: Study, control: bool, deadline: float) -> None:
        super().__init__(study, control, deadline)
        self.failure: dict[str, Any] = study.carried["failure"]

    def play_saved(
        self, task: dict[str, Any], start: dict[str, Any], saved: Saved
    ) -> dict[str, Any]:
        request = recovery.game_request(task, saved, start)
        if task["key"] == recovery.FAILED:
            if any(self.failure[key] != value for key, value in request.items()):
                raise ValueError("The excluded prepared game changed its training lineage")
            self.active = recovery.FAILED
            return {**self.failure, "seal_id": manifest_identifier(self.failure)}
        seal = self.unit(
            task["key"],
            request,
            self.study.cfg["game_limits"]["episode_wall_seconds"] + 30,
            lambda target: file_load.play(self.ctx, task, start, target, saved[0], self.deadline),
        )
        row = seal["result"]
        if (row["task"], row["setup_id"], row["model_id"]) != (
            task,
            start["report_id"],
            saved[0].model.model_id,
        ):
            raise ValueError("A continued prepared game differs from its verified source")
        self.games_seen += 1
        return {**row, "seal_id": seal["report_id"]}

    def matched_start(self, task: dict[str, Any], row: dict[str, Any]) -> None:
        if task["key"] != recovery.FAILED:
            super().matched_start(task, row)
        elif row["outcome"] != "failed" or row["native_decisions"] != 0:
            raise ValueError("An unresolved load cannot supply a public start or decisions")


def run(study: Study, control_id: str, attempt: int, deadline: float) -> dict[str, Any]:
    session = Session(study, False, deadline)
    final = session.store.workspace / "report.json"
    with session.store.lock():
        if final.exists():
            result = identified(final)
            if (result["config_id"], result["control_id"], result["status"]) != (
                session.store.config_id,
                control_id,
                previous.COMPLETE,
            ):
                raise ValueError("The saved continuation belongs to a different plan")
            return result
        status, stop = previous.COMPLETE, None
        finalists: dict[str, str] = {}
        try:
            states = session.train(PLAYERS)
            finalists = {str(p): state_id for p, (_, state_id) in states.items()}
            session.evaluate(states)
        except CleanPause as exc:
            status, stop = "paused", {"unit": session.active, "reason": str(exc)}
        except ERRORS as exc:
            status, stop = (
                "stopped_preserving_evidence",
                {
                    "unit": session.active,
                    "error": f"{type(exc).__name__}: {exc}",
                },
            )
            task = session.active_evaluation
            if task is not None and session.store.path(task["key"]).exists():
                session.evaluation_rows[task["seed"], task["player"], task["comparison_arm"]] = {
                    "outcome": "failed"
                }
        study.unchanged(session.profile)
        carried = study.carried
        updates = sum(r["work"]["optimizer_steps"] for r in session.training)
        if updates < carried["updates"] or session.games_seen < carried["games"]:
            raise ValueError("The continuation failed to restore its sealed prefix")
        target = (
            final
            if status == previous.COMPLETE
            else session.store.workspace / f"session-{attempt}.json"
        )
        return write(
            target,
            {
                "schema_version": SCHEMA,
                "config_id": session.store.config_id,
                "status": status,
                "control_id": control_id,
                "starting_states": study.cfg["starting_states"],
                "continued_from": carried["report_id"],
                "preserved_training_failure": carried["failure"],
                "carried_optimizer_updates": carried["updates"],
                "new_optimizer_updates": updates - carried["updates"],
                "final_checkpoint_ids": finalists,
                "verified_games": session.games_seen,
                "optimizer_updates": updates,
                "training": session.training,
                "normal_start_evaluation": session.summary(),
                "stop": stop,
                "frozen_checks": study.recovery.original.source.study.frozen_checks,
                **SCOPE,
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the launcher with the pinned numerical thread settings")
        cfg = json.loads((root / RECIPE).read_text())
        if (
            cfg["schema_version"] != SCHEMA
            or cfg["limits"] != previous.LIMITS
            or cfg["implementation"] != implementation(root)
            or verified(root, cfg["original_recipe"]) != root / previous.RECIPE
        ):
            raise ValueError("Require the pinned continuation and original recipe")
        if args.check or args.preflight or args.execute is not None:
            original = json.loads((root / previous.RECIPE).read_text())
            predecessor = prior.load(root)
            heads = ChunkJournal(root, predecessor.cfg)
            history = ChunkJournal(root, original)
            with (
                predecessor.source_lock(),
                (heads.workspace / "session.lock").open("rb") as head_lock,
                (history.workspace / "session.lock").open("rb") as history_lock,
            ):
                for lock in (head_lock, history_lock):
                    fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
                study = previous.admit(root, predecessor, heads, original)
                control_id = previous.require_control(study)
                saved = recovery.inspect(study, history, cfg, control_id)
                if (
                    len(
                        {
                            cfg["workspace"],
                            cfg["control_workspace"],
                            original["workspace"],
                            original["control_workspace"],
                        }
                    )
                    != 4
                ):
                    raise ValueError("Continuation and control require separate workspaces")
                resume = Study(study, history, cfg, saved)
                resume.unchanged(_shared_snapshot(Path.home() / SHARED_PROFILE))
                proof = require_control(study, cfg)
                if args.check:
                    print(json.dumps({"status": CONTROL, "report_id": proof}))
                    return 0
                if args.preflight:
                    print(
                        json.dumps(
                            {
                                "status": "later_act_continuation_ready",
                                "control_id": proof,
                                "sealed_training_games": saved["games"],
                                "sealed_updates": saved["updates"],
                                "sealed_outcomes_by_start_act": saved["outcomes"],
                                "latest_checkpoints": saved["latest_checkpoints"],
                                "preserved_failure": recovery.FAILED,
                                "new_training_games": plan.ROUNDS * (plan.NORMAL_PER_ROUND + 8) * 2
                                - saved["games"]
                                - 1,
                                "normal_start_evaluation_games": plan.EVALUATION_WORLDS * 4,
                                "frozen_checks": study.recovery.original.source.study.frozen_checks,
                            }
                        )
                    )
                    return 0
                if _running_games():
                    raise ValueError("Close STS2 and wait for any other native worker")
                result = run(
                    resume, proof, args.execute, started + previous.LIMITS["wall_seconds"] - 45
                )
                print(json.dumps({k: v for k, v in result.items() if k != "training"}))
                return 0 if result["status"] in {previous.COMPLETE, "paused"} else 2
        store = ChunkJournal(root, cfg)
        attempt = time.time_ns()
        print(
            "Continue shared-head A8 training from the verified games and checkpoints.", flush=True
        )
        tracked = run_tracked_command(
            command=["uv", "run", "--no-sync", "python", "-m", MODULE, "--execute", str(attempt)],
            experiment_kind=ExperimentKind.TRAINING,
            working_directory=root,
            report_path=store.workspace / f"resources-{attempt}.json",
            artifact_roots=[store.workspace],
            limits=ResourceLimits(**previous.LIMITS),
            poll_interval_seconds=8,
        )
        print(json.dumps(tracked.report))
        return 0 if tracked.exit_code == 0 and tracked.report["cap"] is None else 2
    except ERRORS as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc), **SCOPE}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
