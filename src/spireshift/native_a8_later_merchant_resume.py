"""Continue the shared-head A8 study with current merchant-map observations."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import time
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_head_grid_resume as prior
from spireshift import native_a8_head_policy as policy
from spireshift import native_a8_later_merchant_recovery as merchant_recovery
from spireshift import native_a8_later_recovery as recovery
from spireshift import native_a8_later_training as original
from spireshift import native_a8_later_training_plan as plan
from spireshift import native_a8_later_training_resume as previous
from spireshift import native_a8_merchant_map as merchant
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.engine_worker import worker_helpers
from spireshift.native_a8_archive_fit_session import ERRORS
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_head_study import CleanPause, Saved
from spireshift.native_a8_head_study import Session as HeadSession
from spireshift.native_a8_own_training import SCOPE
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_reward_exit_recovery import chunk_evidence_id
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

MODULE = "spireshift.native_a8_later_merchant_resume"
RECIPE = "configs/native-learning/sts2-v0.111.0-a8-shared-later-act-merchant-resume-v1.json"
WRAPPER = "scripts/resume-a8-shared-later-acts-v2.sh"
SCHEMA = "native-a8-shared-later-act-merchant-continuation-v1"


def implementation(root: Path) -> dict[str, str]:
    files = {
        WRAPPER,
        *(f"scripts/{name}" for name in worker_helpers(root, merchant.SCRIPT)),
        *(f"scripts/{name}" for name in worker_helpers(root, merchant.SAVED)),
        *(
            f"src/spireshift/native_a8_{name}.py"
            for name in ("merchant_map", "later_merchant_resume", "later_merchant_recovery")
        ),
    }
    return {name: _sha_file(root / name) for name in sorted(files)}


def require_control(study: original.Study, cfg: dict[str, Any], stopped: Path) -> str:
    root = study.recovery.root
    path = verified(root, cfg["merchant_control"])
    report = identified(path)
    if (
        report["status"] != merchant.CONTROL
        or report["optimizer_updates"] != 0
        or report["frozen_checks"] != study.recovery.original.source.study.frozen_checks
        or set(report["cases"]) != {"real-exit", "fake-exit", "real-use", "fake-use", "prepared"}
        or report["saved"] != merchant.saved_control(study.ctx, stopped)
        or chunk_evidence_id(path.parent) != cfg["merchant_control_evidence_id"]
    ):
        raise ValueError("Require the exact saved and native merchant-map controls")
    return str(report["report_id"])


class Study(original.Study):
    def __init__(
        self, preceding: previous.Study, cfg: dict[str, Any], restored: dict[str, Any]
    ) -> None:
        super().__init__(
            preceding.recovery,
            preceding.cfg,
            preceding.ctx,
            preceding.worlds,
            preceding.parents,
            preceding.checkpoint_sources,
            preceding.bank,
        )
        self.preceding, self.resume, self.restored = preceding, cfg, restored

    def store(self, control: bool) -> ChunkJournal:
        if control:
            return super().store(True)
        return merchant_recovery.HistoryJournal(
            self.restored["history"], self.resume, self.restored["carried"]
        )

    def unchanged(self, profile: dict[str, Any]) -> None:
        self.preceding.unchanged(profile)
        root = self.recovery.root
        if json.loads((root / RECIPE).read_text()) != self.resume:
            raise ValueError("The merchant continuation recipe changed")
        check_sources(root, self.resume["implementation"])
        for key in ("interrupted_report", "interrupted_resources", "previous_recipe"):
            verified(root, self.resume[key])
        stopped = self.restored["history"].path(merchant_recovery.FAILED)
        if chunk_evidence_id(stopped) != self.resume["failed_chunk_id"]:
            raise ValueError("The interrupted merchant evidence changed")


class Session(original.Session):
    def __init__(self, study: Study, deadline: float) -> None:
        super().__init__(study, False, deadline)
        self.failures: dict[str, dict[str, Any]] = study.restored["failures"]

    def game(self, task: dict[str, Any], saved: Saved) -> dict[str, Any]:
        if task["start_act"] != 1:
            raise ValueError("Only normal starts enter the normal-game path")
        with patch.object(policy, "SelectorWorker", merchant.MerchantMapWorker):
            return HeadSession.game(self, task, saved)

    def play_saved(
        self, task: dict[str, Any], start: dict[str, Any], saved: Saved
    ) -> dict[str, Any]:
        key = task["key"]
        request = recovery.game_request(task, saved, start)
        if key in self.failures:
            self.active = key
            failure = self.failures[key]
            if any(failure[name] != value for name, value in request.items()):
                raise ValueError("A failed game must keep its original training lineage")
            return {**failure, "seal_id": manifest_identifier(failure)}
        seal = self.unit(
            key,
            request,
            self.study.cfg["game_limits"]["episode_wall_seconds"] + 30,
            lambda target: merchant.play_saved(
                self.ctx, task, start, target, saved[0], self.deadline
            ),
        )
        row = seal["result"]
        if (row["task"], row["setup_id"], row["model_id"]) != (
            task,
            start["report_id"],
            saved[0].model.model_id,
        ):
            raise ValueError("The prepared game differs from its declared start or checkpoint")
        self.games_seen += 1
        return {**row, "seal_id": seal["report_id"]}

    def matched_start(self, task: dict[str, Any], row: dict[str, Any]) -> None:
        if task["key"] not in self.failures:
            super().matched_start(task, row)
        elif row["outcome"] != "failed" or row["native_decisions"] != 0:
            raise ValueError("An incomplete game cannot supply training decisions")


@contextmanager
def admitted(root: Path, cfg: dict[str, Any]) -> Iterator[tuple[Study, str]]:
    prior_path = verified(root, cfg["previous_recipe"])
    if prior_path != root / previous.RECIPE:
        raise ValueError("Require the original file-load continuation recipe")
    prior_cfg = json.loads(prior_path.read_text())
    if verified(root, prior_cfg["original_recipe"]) != root / original.RECIPE:
        raise ValueError("Require the original later-act recipe")
    original_cfg = json.loads((root / original.RECIPE).read_text())
    predecessor = prior.load(root)
    heads = ChunkJournal(root, predecessor.cfg)
    history, continued = ChunkJournal(root, original_cfg), ChunkJournal(root, prior_cfg)
    new_workspace = ChunkJournal(root, cfg).workspace
    with predecessor.source_lock(), ExitStack() as locks:
        for store in (heads, history, continued):
            lock = locks.enter_context((store.workspace / "session.lock").open("rb"))
            fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
            if new_workspace.is_relative_to(store.workspace):
                raise ValueError("The continuation needs a separate workspace")
        study = original.admit(root, predecessor, heads, original_cfg)
        first = recovery.inspect(study, history, prior_cfg, original.require_control(study))
        previous_control = previous.require_control(study, prior_cfg)
        report = merchant_recovery.check_attempt(study, continued, cfg, previous_control)
        restored = merchant_recovery.inspect(study, history, continued, cfg, first, report)
        resume = Study(previous.Study(study, history, prior_cfg, first), cfg, restored)
        resume.unchanged(_shared_snapshot(Path.home() / SHARED_PROFILE))
        yield resume, require_control(study, cfg, continued.path(merchant_recovery.FAILED))


def run(study: Study, control_id: str, attempt: int, deadline: float) -> dict[str, Any]:
    session = Session(study, deadline)
    final = session.store.workspace / "report.json"
    with session.store.lock():
        if final.exists():
            result = identified(final)
            if (result["config_id"], result["control_id"], result["status"]) != (
                session.store.config_id,
                control_id,
                original.COMPLETE,
            ):
                raise ValueError("The saved continuation belongs to a different plan")
            return result
        status, stop = original.COMPLETE, None
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
        saved = study.restored
        updates = sum(row["work"]["optimizer_steps"] for row in session.training)
        if updates < saved["updates"] or session.games_seen < saved["games"]:
            raise ValueError(f"The sealed prefix failed restoration: {stop}")
        target = (
            final
            if status == original.COMPLETE
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
                "continued_from": saved["report_id"],
                "preserved_training_failures": saved["failures"],
                "carried_optimizer_updates": saved["updates"],
                "new_optimizer_updates": updates - saved["updates"],
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
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--execute", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the launcher with the pinned numerical thread settings")
        cfg = json.loads((root / RECIPE).read_text())
        if (
            cfg["schema_version"] != SCHEMA
            or cfg["limits"] != original.LIMITS
            or cfg["implementation"] != implementation(root)
        ):
            raise ValueError("Require the pinned merchant continuation")
        if args.preflight or args.execute is not None:
            with admitted(root, cfg) as (study, control_id):
                saved = study.restored
                if args.preflight:
                    print(
                        json.dumps(
                            {
                                "status": "later_act_merchant_continuation_ready",
                                "control_id": control_id,
                                "sealed_training_games": saved["games"],
                                "sealed_updates": saved["updates"],
                                "sealed_outcomes_by_start_act": saved["outcomes"],
                                "normal_start_act1_clears": saved["normal_start_act1_clears"],
                                "latest_checkpoints": saved["latest_checkpoints"],
                                "preserved_failures": list(saved["failures"]),
                                "new_training_games": plan.ROUNDS
                                * (plan.NORMAL_PER_ROUND + 8)
                                * len(PLAYERS)
                                - saved["games"]
                                - len(saved["failures"]),
                                "normal_start_evaluation_games": plan.EVALUATION_WORLDS * 4,
                                "frozen_checks": study.recovery.original.source.study.frozen_checks,
                            }
                        )
                    )
                    return 0
                if _running_games():
                    raise ValueError("Close STS2 and wait for any other native worker")
                result = run(
                    study, control_id, args.execute, started + cfg["limits"]["wall_seconds"] - 45
                )
                print(
                    json.dumps({key: value for key, value in result.items() if key != "training"})
                )
                return 0 if result["status"] in {original.COMPLETE, "paused"} else 2
        store = ChunkJournal(root, cfg)
        attempt = time.time_ns()
        print("Continue shared-head A8 training from the verified checkpoints.", flush=True)
        tracked = run_tracked_command(
            command=["uv", "run", "--no-sync", "python", "-m", MODULE, "--execute", str(attempt)],
            experiment_kind=ExperimentKind.TRAINING,
            working_directory=root,
            report_path=store.workspace / f"resources-{attempt}.json",
            artifact_roots=[store.workspace],
            limits=ResourceLimits(**cfg["limits"]),
            poll_interval_seconds=8,
        )
        print(json.dumps(tracked.report))
        return 0 if tracked.exit_code == 0 and tracked.report["cap"] is None else 2
    except ERRORS as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc), **SCOPE}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
