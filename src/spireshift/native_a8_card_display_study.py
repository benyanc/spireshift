"""Compare exact shared-head replay fits with and without current card stats."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from spireshift import native_a8_act1_success_bank as bank
from spireshift import native_a8_act1_success_study as replay
from spireshift import native_a8_archive_fit_inputs as fit_inputs
from spireshift import native_a8_card_display_model as display
from spireshift import native_a8_head_policy as head_policy
from spireshift import native_a8_later_merchant_resume as later
from spireshift import native_structured_policy
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_policy import score_features
from spireshift.native_a8_archive_fit_session import ERRORS
from spireshift.native_a8_bank_fit import world_schedule
from spireshift.native_a8_head_study import CleanPause, Saved
from spireshift.native_a8_own_training import SCOPE
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_flow_verification_v12 import records
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

MODULE = "spireshift.native_a8_card_display_study"
RECIPE = "configs/native-learning/sts2-v0.111.0-a8-card-display-v1.json"
WRAPPER = "scripts/compare-a8-card-display-v1.sh"
SCHEMA = "native-a8-card-display-study-v1"
WORK = "artifacts/native-a8-card-display"
CONTROL = "card_display_control_verified"
COMPLETE = "card_display_comparison_complete"


def implementation(root: Path) -> dict[str, str]:
    sources = (
        WRAPPER,
        *(
            f"src/spireshift/{name}.py"
            for name in (
                "native_a8_card_display_model",
                "native_a8_card_display_study",
            )
        ),
    )
    return {**replay.implementation(root), **{name: _sha_file(root / name) for name in sources}}


def declaration() -> dict[str, Any]:
    return {
        **replay.declaration(),
        "development": [f"SP1RESH1FTA8CS1E{i:03}" for i in range(1, 33)],
        "controls": ["SP1RESH1FTA8CS1C001"],
    }


def vocabulary(root: Path, proof: dict[str, Any]) -> tuple[str, ...]:
    names: set[str] = set()
    for seed in proof["partitions"]["fit"]:
        for row in records(verified(root, proof["worlds"][seed]["labels"])):
            for factor in row["factors"]:
                for stats in display.candidate_stats(factor["public_input"]):
                    names.update(stats)
    return tuple(sorted(names))


def load_fit(
    store: ChunkJournal, player: int, parent: Saved, fit: dict[str, Any], updates: int, bank_id: str
) -> tuple[Saved, str]:
    key = f"fit-p{player}"
    target = store.path(key)
    request = json.loads((target / "active.json").read_text())["request"]
    seal = store.completed(key, request)
    if (
        seal is None
        or fit != {"player": player, "seal_id": seal["report_id"], **seal["result"]}
        or request["parent_state_id"] != parent[1]
        or request["bank_id"] != bank_id
        or request["updates"] != updates
        or fit["optimizer_updates"] != updates
    ):
        raise ValueError("The saved fit has a different parent, bank or update count")
    state = display.load(target / "shared.json")
    before, after = parent[0], state[0]
    if (
        state[1] != fit["states"]["shared"]["state_id"]
        or after.model.model_id != fit["states"]["shared"]["model_id"]
        or type(after.model) is not type(before.model)
        or after.actor_adam.steps != before.actor_adam.steps + updates
        or after.model.value_weights != before.model.value_weights
        or after.value_adam != before.value_adam
        or after.model.actor == before.model.actor
    ):
        raise ValueError("The fitted actor or frozen critic state differs")
    return state, str(request["schedule_id"])


@dataclass(frozen=True)
class Inputs:
    study: later.Study
    proof: dict[str, Any]
    legacy_finals: dict[int, Saved]
    expanded: dict[int, Saved]
    schedule_id: str
    legacy_result_id: str


@contextmanager
def admitted(root: Path, cfg: dict[str, Any]) -> Iterator[Inputs]:
    path = verified(root, cfg["replay_recipe"])
    legacy_cfg = json.loads(path.read_text())
    if (
        path != root / replay.RECIPE
        or cfg["bank"] != legacy_cfg["bank"]
        or cfg["comparison"] != legacy_cfg["comparison"]
        or cfg["objective"] != legacy_cfg["objective"]
        or cfg["environment_id"] != legacy_cfg["environment_id"]
        or cfg["score_id"] != legacy_cfg["score_id"]
        or set(cfg["plan"]["controls"] + cfg["plan"]["development"]).intersection(
            legacy_cfg["plan"]["controls"] + legacy_cfg["plan"]["development"]
        )
    ):
        raise ValueError("Match the completed replay experiment with new evaluation worlds")
    with bank.completed_study(root) as (study, completed):
        proof = replay.load_bank(study, completed, cfg)
        store = ChunkJournal(root, legacy_cfg)
        with (store.workspace / "session.lock").open("rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
            path = verified(root, cfg["replay_result"])
            result = identified(path)
            if (
                path != store.workspace / "report.json"
                or result["status"] != replay.COMPLETE
                or result["config_id"] != store.config_id
                or result["bank_id"] != proof["report_id"]
                or result["verified_games"] != 128
                or result["original_optimizer_updates"] != 0
                or result["frozen_checks"] != proof["frozen_checks"]
                or result["starting_states"] != {str(p): study.parents[p][1] for p in PLAYERS}
                or json.loads((store.workspace / "config-at-launch.json").read_text()) != legacy_cfg
            ):
                raise ValueError("Require the exact completed replay comparison")
            legacy, schedules = {}, set()
            for fit in result["fits"]:
                p = fit["player"]
                legacy[p], schedule = load_fit(
                    store, p, study.parents[p], fit, replay.UPDATES, proof["report_id"]
                )
                schedules.add(schedule)
            if (
                sorted(legacy) != list(PLAYERS)
                or len(schedules) != 1
                or {str(p): state[1] for p, state in legacy.items()} != result["final_states"]
            ):
                raise ValueError(
                    "Both sealed legacy comparators and the common schedule are required"
                )
            names = tuple(cfg["stat_names"])
            if names != vocabulary(root, proof):
                raise ValueError("Display columns must come only from the fitting-world menus")
            expanded: dict[int, Saved] = {}
            for p in PLAYERS:
                state = display.extend(study.parents[p][0], names)
                expanded[p] = state, manifest_identifier(state.document())
            yield Inputs(study, proof, legacy, expanded, schedules.pop(), result["report_id"])


class Session(replay.Session):
    def __init__(self, inputs: Inputs, cfg: dict[str, Any], control: bool, deadline: float) -> None:
        super().__init__(inputs.study, cfg, inputs.proof, control, deadline)
        self.inputs = inputs
        self.later = replace(self.later, parents=inputs.expanded)

    def checkpoint(self, key: str, arm: str, expected: dict[str, Any]) -> Saved:
        with patch.object(head_policy, "load", display.load):
            return super().checkpoint(key, arm, expected)

    def game(self, task: dict[str, Any], saved: Saved) -> dict[str, Any]:
        with patch.object(native_structured_policy, "encode", display.encode):
            return super().game(task, saved)

    def compare(self, states: dict[int, Saved]) -> None:
        with patch.object(self, "later", replace(self.later, parents=self.inputs.legacy_finals)):
            super().compare(states)


def check_initial_scores(inputs: Inputs, deadline: float) -> int:
    """Keep the warm start and every original candidate score aligned."""
    root, proof, study = inputs.study.recovery.root, inputs.proof, inputs.study
    checked = count = 0
    for seed in proof["partitions"]["fit"][:4]:
        for row in records(verified(root, proof["worlds"][seed]["labels"])):
            if time.monotonic() >= deadline:
                raise TimeoutError("The saved initial-score check reached its time limit")
            for factor in row["factors"]:
                public = factor["public_input"]
                for p in PLAYERS:
                    original = study.parents[p][0].model
                    expanded = inputs.expanded[p][0].model
                    baseline, _ = display.encode(public, original, study.ctx["score"])
                    current, _ = display.encode(public, expanded, study.ctx["score"])
                    old = score_features(cast(Any, original.actor), baseline)
                    new = score_features(cast(Any, expanded.actor), current)
                    if any(abs(a - b) > 1e-10 for a, b in zip(old, new, strict=True)):
                        raise ValueError("The new public inputs changed an inherited choice score")
                    checked += len(old)
            count += 1
            if count == 64:
                return checked
    raise ValueError("Require 64 verified training decisions for the initial-score check")


def run(
    inputs: Inputs, cfg: dict[str, Any], attempt: int, control: bool, deadline: float
) -> dict[str, Any]:
    s = Session(inputs, cfg, control, deadline)
    root = s.store.root
    final = s.store.workspace / "report.json"
    complete = CONTROL if control else COMPLETE
    with s.store.lock():
        if final.exists():
            saved = identified(final)
            if saved["config_id"] != s.store.config_id or saved["status"] != complete:
                raise ValueError("The sealed card-display study has a different identity")
            return saved
        status, stop = complete, None
        initial_scores = 0
        states: dict[int, Saved] = {}
        try:
            if control:
                initial_scores = check_initial_scores(inputs, deadline - 35)
            with patch.object(fit_inputs, "encode", display.encode):
                train, held = [
                    replay.dataset(
                        root,
                        inputs.proof,
                        partition,
                        inputs.expanded[2],
                        inputs.study.ctx["score"],
                        deadline - 20,
                        short=control,
                    )
                    for partition in ("fit", "fit_holdout")
                ]
            if (
                not control
                and manifest_identifier(
                    world_schedule(train, replay.UPDATES, inputs.proof["report_id"])
                )
                != inputs.schedule_id
            ):
                raise ValueError("The fits must use the exact same world-balanced draws")
            for p in PLAYERS:
                states[p] = s.fit_replay(p, train, held)
            s.check_frozen(s.profile)
            s.compare(states)
            if control and (
                s.games_seen != 4
                or any(row["outcome"] not in {"win", "loss"} for row in s.evaluation_rows.values())
            ):
                raise ValueError("Require four short control games with native endings")
        except CleanPause as exc:
            status, stop = "paused", {"unit": s.active, "reason": str(exc)}
        except ERRORS as exc:
            status = "stopped_preserving_evidence"
            stop = {"unit": s.active, "error": f"{type(exc).__name__}: {exc}"}
            task = s.active_evaluation
            if task is not None and s.store.path(task["key"]).exists():
                s.evaluation_rows[task["seed"], task["player"], task["comparison_arm"]] = {
                    "outcome": "failed"
                }
        s.check_frozen(s.profile)
        verified(root, cfg["replay_result"])
        verified(root, cfg["bank"])
        check_sources(root, cfg["implementation"])
        return write(
            final if status == complete else s.store.workspace / f"session-{attempt}.json",
            {
                "schema_version": SCHEMA,
                "status": status,
                "config_id": s.store.config_id,
                "bank_id": inputs.proof["report_id"],
                "legacy_result_id": inputs.legacy_result_id,
                "stat_names": cfg["stat_names"],
                "objective": cfg["objective"],
                "matched_fit_schedule_id": inputs.schedule_id,
                "original_arm_is_legacy_replay_fit": True,
                "matched_initial_candidate_scores": initial_scores,
                "legacy_states": {str(p): st[1] for p, st in inputs.legacy_finals.items()},
                "expanded_starts": {str(p): st[1] for p, st in inputs.expanded.items()},
                "final_states": {str(p): st[1] for p, st in states.items()},
                "game_seals": s.game_seals,
                "fits": s.training,
                "verified_games": s.games_seen,
                "copied_optimizer_updates": sum(row["optimizer_updates"] for row in s.training),
                "original_optimizer_updates": 0,
                "normal_start_evaluation": s.summary(),
                "frozen_checks": inputs.proof["frozen_checks"],
                "stop": stop,
                **SCOPE,
            },
        )


def verify_control(inputs: Inputs, cfg: dict[str, Any]) -> str:
    s = Session(inputs, cfg, True, 0)
    control = identified(s.store.workspace / "report.json")
    if (
        control["status"] != CONTROL
        or control["config_id"] != s.store.config_id
        or control["bank_id"] != inputs.proof["report_id"]
        or control["legacy_result_id"] != inputs.legacy_result_id
        or control["frozen_checks"] != inputs.proof["frozen_checks"]
        or control["matched_initial_candidate_scores"] < 128
        or control["verified_games"] != 4
        or sorted(fit["player"] for fit in control["fits"]) != list(PLAYERS)
        or control["copied_optimizer_updates"] != len(PLAYERS) * replay.CONTROL_UPDATES
    ):
        raise ValueError("Require the exact short fit, initial scores and native ending controls")
    states = {
        fit["player"]: load_fit(
            s.store,
            fit["player"],
            inputs.expanded[fit["player"]],
            fit,
            replay.CONTROL_UPDATES,
            inputs.proof["report_id"],
        )[0]
        for fit in control["fits"]
    }
    if {str(p): st[1] for p, st in states.items()} != control["final_states"]:
        raise ValueError("The fitted control copies differ")
    # A zero deadline makes this reconstruction read-only even if a seal is absent.
    s.compare(states)
    if (
        s.game_seals != control["game_seals"]
        or s.summary() != control["normal_start_evaluation"]
        or any(row["outcome"] not in {"loss", "win"} for row in s.evaluation_rows.values())
    ):
        raise ValueError("The saved native control games differ")
    return str(control["report_id"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--execute", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    try:
        cfg = json.loads((root / RECIPE).read_text())
        if (
            any(os.environ.get(name) != "1" for name in THREADS)
            or cfg["schema_version"] != SCHEMA
            or cfg["implementation"] != implementation(root)
            or cfg["plan"] != declaration()
            or cfg["limits"] != replay.LIMITS
            or cfg["workspace"] != f"{WORK}/study-v1"
            or cfg["control_workspace"] != f"{WORK}/control-v1"
        ):
            raise ValueError("Use the launcher with the pinned card-display comparison")
        if args.check or args.preflight or args.execute is not None:
            with admitted(root, cfg) as inputs:
                if not args.check:
                    control = verify_control(inputs, cfg)
                    if args.preflight:
                        print(
                            json.dumps(
                                {
                                    "status": "card_display_comparison_ready",
                                    "control_id": control,
                                    "public_stat_fields": len(cfg["stat_names"]),
                                    "fresh_evaluation_games": len(cfg["plan"]["development"]) * 4,
                                    "frozen_checks": inputs.proof["frozen_checks"],
                                }
                            )
                        )
                        return 0
                if _running_games():
                    raise ValueError("Close STS2 and wait for other native workers")
                cap = replay.CONTROL_SECONDS if args.check else replay.LIMITS["wall_seconds"] - 45
                result = run(inputs, cfg, args.execute or time.time_ns(), args.check, started + cap)
                print(json.dumps(result))
                return 0 if result["status"] in {COMPLETE, CONTROL, "paused"} else 2
        attempt = time.time_ns()
        store = ChunkJournal(root, cfg)
        print("Compare the frozen replay fits with copies trained on current public card stats.")
        tracked = run_tracked_command(
            command=["uv", "run", "--no-sync", "python", "-m", MODULE, "--execute", str(attempt)],
            working_directory=root,
            experiment_kind=ExperimentKind.TRAINING,
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
