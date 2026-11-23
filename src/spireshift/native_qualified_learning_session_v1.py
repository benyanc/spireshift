"""Sustained whole-game PPO on copies, followed by fixed fresh-start A8 pairs."""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_head_policy import HeadState, save
from spireshift.native_a8_paired_report import summarize
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_combat_intent_model import load as load_state
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_qualified_learning_audit_v1 import saved_menus
from spireshift.native_qualified_learning_fit_v1 import fit
from spireshift.native_qualified_learning_inputs_v1 import MODULE, SCHEMA, context, load
from spireshift.native_qualified_learning_worker_v1 import play
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

CONTROL = "qualified_model_only_collect_fit_reload_verified"
COMPLETE = "qualified_model_only_training_and_development_complete"
TERMINAL = {"win", "loss"}


def development_report(
    worlds: list[str], games: dict[tuple[str, int, str], dict[str, Any]]
) -> dict[str, Any]:
    report = summarize(worlds, games)
    for p in (2, 3):
        for arm in ("original", "fitted"):
            rows = [
                row
                for (seed, player, name), row in games.items()
                if seed in worlds and player == p and name == arm and row["outcome"] in TERMINAL
            ]
            report["by_initializer"][str(p)]["arms"][arm].update(
                act1_clears=sum(row["completed_acts"] >= 1 for row in rows),
                act2_clears=sum(row["completed_acts"] >= 2 for row in rows),
                mean_terminal_floor=(sum(row["maximum_floor"] for row in rows) / len(rows))
                if rows
                else None,
            )
    report["comparison"] = "inconclusive"
    ci = report["seed_clustered_bootstrap_95"]
    if ci is not None:
        lo, hi = ci["intervals"]["pooled_wins"]
        if lo > 0:
            report["comparison"] = "development_gain_candidate_needs_independent_confirmation"
        elif hi < 0:
            report["comparison"] = "development_regression"
    report["scope"] = "descriptive_fresh_normal_starts_two_fixed_initializers_not_final_test"
    return report


class CleanPause(RuntimeError):
    pass


class Session:
    def __init__(self, root: Path, cfg: dict[str, Any], control: bool, deadline: float):
        self.root, self.cfg, self.control, self.deadline = root, cfg, control, deadline
        self.ctx = context(root, cfg)
        self.store = ChunkJournal(
            root, {**cfg, "workspace": cfg["control_workspace"]} if control else cfg
        )
        self.before = frozen(root, self.ctx)
        self.profile = _shared_snapshot(Path.home() / SHARED_PROFILE)
        self.active = "initialization"
        self.seals: dict[str, str] = {}
        self.training: list[dict[str, Any]] = []
        self.evaluation: dict[tuple[str, int, str], dict[str, Any]] = {}
        self.game_counts: dict[str, Counter[str]] = {}
        self.saved_input_checks: dict[str, Any] | None = None
        self.starting = {
            p: load_state(verified(root, cfg["starting_states"][str(p)])) for p in (2, 3)
        }

    def unchanged(self) -> None:
        if load(self.root) != self.cfg or frozen(self.root, self.ctx) != self.before:
            raise ValueError(
                "Frozen build, full source checkpoints/Adam or learning inputs changed"
            )
        if _shared_snapshot(Path.home() / SHARED_PROFILE) != self.profile:
            raise ValueError("The personal game profile changed")

    def unit(
        self,
        key: str,
        request: dict[str, Any],
        reserve: float,
        action: Callable[[Path], dict[str, Any]],
    ) -> dict[str, Any]:
        self.active = key
        seal = self.store.completed(key, request)
        if seal is None:
            if time.monotonic() + reserve >= self.deadline:
                raise CleanPause("Stopped before a new unit at the clean session boundary")
            if _running_games():
                raise ValueError("Close STS2 and wait for other native workers")
            target = self.store.begin(key, request)
            result = action(target)
            seal = self.store.commit(key, request, result)
        self.seals[key] = seal["report_id"]
        return {"seal_id": seal["report_id"], **seal["result"]}

    def game(
        self,
        seed: str,
        index: int,
        p: int,
        round_index: int,
        partition: str,
        arm: str,
        state: tuple[HeadState, str],
    ) -> dict[str, Any]:
        task: dict[str, Any] = {
            "key": f"{partition}-{index:04d}-p{p}-{arm}",
            "seed": seed,
            "seed_id": index,
            "player": p,
            "round": round_index,
            "partition": partition,
            "arm": "shared",
        }
        ctx = {
            **self.ctx,
            "config": {"plan": self.cfg["game_limits"]},
            "execution_id": self.store.config_id,
        }
        counts = self.game_counts.setdefault(f"{partition}-p{p}", Counter())
        try:
            row = self.unit(
                task["key"],
                {"task": task, "behavior_state_id": state[1]},
                110,
                lambda target: play(ctx, task, target, state[0], self.deadline - 10),
            )
        except (ValueError, OSError, KeyError, TimeoutError):
            counts["failed"] += 1
            if partition == "development":
                self.evaluation[seed, p, arm] = {"outcome": "failed"}
            raise
        if (
            row["task"] != task
            or row["model_id"] != state[0].model.model_id
            or row["outcome"] not in {*TERMINAL, "capped"}
        ):
            raise ValueError("A saved game differs from its normal start or behavior copy")
        counts[row["outcome"]] += 1
        return row

    def learn(
        self, p: int, r: int, rows: list[dict[str, Any]], state: tuple[HeadState, str]
    ) -> tuple[HeadState, str]:
        key = f"fit-p{p}-r{r:03d}"
        request = {
            "player": p,
            "round": r,
            "prior_state_id": state[1],
            "game_seals": [row["seal_id"] for row in rows],
        }

        def update(target: Path) -> dict[str, Any]:
            self.unchanged()
            eligible = [
                (self.store.path(row["task"]["key"]), row)
                for row in rows
                if row["outcome"] in TERMINAL
            ]
            minimum = (
                self.cfg["plan"]["control_worlds"]
                if self.control
                else self.cfg["plan"]["minimum_terminal_training_worlds"]
            )
            after = state[0]
            work: dict[str, Any] = {
                "optimizer_updates": 0,
                "stop_reason": "insufficient_terminal_worlds",
            }
            if len(eligible) >= minimum:
                after, work = fit(
                    state[0],
                    eligible,
                    self.ctx["score"],
                    self.cfg["credit"],
                    self.cfg["settings"],
                    r,
                    230_000 + p * 1000 + r,
                    self.deadline - 15,
                    control_steps=self.cfg["plan"]["control_updates_per_copy"]
                    if self.control
                    else None,
                )
            state_id = save(target / "shared.json", after)
            return {
                "player": p,
                "round": r,
                "state_id": state_id,
                "model_id": after.model.model_id,
                "actor_steps": after.actor_adam.steps,
                "value_steps": after.value_adam.steps,
                "eligible_terminal_worlds": len(eligible),
                "outcomes": dict(Counter(row["outcome"] for row in rows)),
                "act1_clears": sum(
                    row["completed_acts"] >= 1 for row in rows if row["outcome"] in TERMINAL
                ),
                "act2_clears": sum(
                    row["completed_acts"] >= 2 for row in rows if row["outcome"] in TERMINAL
                ),
                "work": work,
            }

        row = self.unit(key, request, 25 if self.control else 300, update)
        restored, state_id = load_state(self.store.path(key) / "shared.json")
        updates = row["work"]["optimizer_updates"]
        if (
            state_id != row["state_id"]
            or restored.model.model_id != row["model_id"]
            or restored.actor_adam.steps - state[0].actor_adam.steps != updates
            or restored.value_adam.steps - state[0].value_adam.steps != updates
        ):
            raise ValueError("Reloaded actor, critic or their complete Adam differs")
        if self.control and (updates != 2 or restored.model.weights() == state[0].model.weights()):
            raise ValueError("Short control did not collect, update and reload the disposable copy")
        self.training.append(row)
        return restored, state_id

    def run(self) -> dict[str, Any]:
        current = self.starting.copy()
        if self.control:
            self.saved_input_checks = saved_menus(
                self.root, self.cfg, self.starting, self.ctx["score"]
            )
        rounds = 1 if self.control else self.cfg["plan"]["rounds"]
        count = (
            self.cfg["plan"]["control_worlds"]
            if self.control
            else self.cfg["plan"]["worlds_per_round"]
        )
        for r in range(1, rounds + 1):
            seeds = (
                self.cfg["plan"]["control"]
                if self.control
                else self.cfg["plan"]["training"][(r - 1) * count : r * count]
            )
            for p in (2, 3):
                rows = [
                    self.game(
                        seed,
                        (r - 1) * count + i,
                        p,
                        r,
                        "control" if self.control else "train",
                        "learner",
                        current[p],
                    )
                    for i, seed in enumerate(seeds, 1)
                ]
                current[p] = self.learn(p, r, rows, current[p])
                outcomes = dict(Counter(row["outcome"] for row in rows))
                print(
                    f"Round {r}/{rounds}, player {p}: {outcomes}; "
                    f"Act 1 clears {self.training[-1]['act1_clears']}/{len(rows)}; "
                    f"{self.training[-1]['work']['optimizer_updates']} updates",
                    flush=True,
                )
        if self.control:
            for p in (2, 3):
                row = self.game(
                    self.cfg["plan"]["reload"][0], 1, p, 1, "reload_control", "learner", current[p]
                )
                if row["outcome"] not in TERMINAL:
                    raise ValueError(
                        "The reloaded normal-start control did not reach a genuine ending"
                    )
        else:
            for i, seed in enumerate(self.cfg["plan"]["development"], 1):
                for p in (2, 3):
                    for arm, state in (("original", self.starting[p]), ("fitted", current[p])):
                        row = self.game(seed, i, p, rounds, "development", arm, state)
                        self.evaluation[seed, p, arm] = row
                        label = "frozen-start" if arm == "original" else "trained-round-64"
                        print(f"Development {i}/32 p{p} {label}: {row['outcome']}", flush=True)
        self.unchanged()
        return {
            "status": CONTROL if self.control else COMPLETE,
            "final_states": {str(p): current[p][1] for p in (2, 3)},
        }


def execute(root: Path, cfg: dict[str, Any], control: bool, deadline: float) -> dict[str, Any]:
    session = Session(root, cfg, control, deadline)
    with session.store.lock():
        final = session.store.workspace / "report.json"
        if final.exists():
            result = identified(final)
            if result["config_id"] != session.store.config_id:
                raise ValueError("The completed learning report has a different declaration")
            check_sources(root, result["sources"])
            session.unchanged()
            return result
        stopped = None
        try:
            outcome = session.run()
        except (ValueError, OSError, KeyError, TimeoutError, CleanPause) as exc:
            outcome = {
                "status": "paused" if isinstance(exc, CleanPause) else "stopped_preserving_evidence"
            }
            stopped = {"unit": session.active, "error": f"{type(exc).__name__}: {exc}"}
            session.unchanged()
        result = {
            "schema_version": SCHEMA,
            "config_id": session.store.config_id,
            **outcome,
            "stop": stopped,
            "training": session.training,
            "chunk_seals": session.seals,
            "optimizer_updates_on_copies": sum(
                row["work"]["optimizer_updates"] for row in session.training
            ),
            "starting_states": {str(p): session.starting[p][1] for p in (2, 3)},
            "development": None
            if control
            else development_report(cfg["plan"]["development"], session.evaluation),
            "game_counts": {name: dict(counts) for name, counts in session.game_counts.items()},
            "saved_input_checks": session.saved_input_checks,
            "planned_training_games_per_initializer": cfg["plan"]["control_worlds"]
            if control
            else 1024,
            "planned_development_games_per_initializer_per_arm": 0 if control else 32,
            "frozen_checks": session.before,
            "original_optimizer_updates": 0,
            "normal_starts_only": True,
            "promotion_allowed": False,
            "official_live_qualification_granted": False,
            "final_test_worlds_used": False,
            "adaptive_controller_allowed": False,
            "automatic_follow_up": False,
        }
        result["sources"] = {
            str(p.relative_to(root)): __import__("hashlib").sha256(p.read_bytes()).hexdigest()
            for p in sorted(session.store.workspace.rglob("*"))
            if p.is_file() and p != final
        }
        path = (
            final
            if outcome["status"] in {CONTROL, COMPLETE}
            else session.store.workspace / f"stop-{time.time_ns()}.json"
        )
        return write(path, result)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("short", "saved", "run"), nargs="?", default="run")
    parser.add_argument("--execute", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = Path.cwd()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the pinned single-thread numerical runtime")
        cfg = load(root)
        control = args.mode != "run"
        if args.mode == "saved":
            result = identified(root / cfg["control_workspace"] / "report.json")
            expected = manifest_identifier({**cfg, "workspace": cfg["control_workspace"]})
            if result["status"] != CONTROL or result["config_id"] != expected:
                raise ValueError("Require the exact collect/fit/reload control")
            check_sources(root, result["sources"])
            print(
                json.dumps(
                    {
                        "status": "saved_control_verified",
                        "report_id": result["report_id"],
                        "games_launched": 0,
                        "optimizer_updates": 0,
                    }
                )
            )
            return 0
        if args.mode == "run":
            control_path = root / cfg["control_workspace"] / "report.json"
            result = identified(control_path)
            if result["status"] != CONTROL or result["config_id"] != manifest_identifier(
                {**cfg, "workspace": cfg["control_workspace"]}
            ):
                raise ValueError("Run the short native learning control before sustained training")
            check_sources(root, result["sources"])
        limits = cfg["control_limits"] if control else cfg["limits"]
        area = root / (cfg["control_workspace"] if control else cfg["workspace"])
        area.mkdir(parents=True, exist_ok=True)
        if args.execute is None:
            attempt = time.time_ns()
            tracked = run_tracked_command(
                command=[
                    "uv",
                    "run",
                    "--no-sync",
                    "python",
                    "-B",
                    "-m",
                    MODULE,
                    args.mode,
                    "--execute",
                    str(attempt),
                ],
                working_directory=root,
                experiment_kind=ExperimentKind.TRAINING,
                report_path=area / f"resources-{attempt}.json",
                artifact_roots=[area],
                limits=ResourceLimits(**limits),
            )
            print(json.dumps(tracked.report))
            return 0 if tracked.exit_code == 0 and tracked.report["cap"] is None else 2
        if _running_games():
            raise ValueError("Close STS2 and wait for other native workers")
        result = execute(root, cfg, control, time.monotonic() + limits["wall_seconds"] - 15)
        print(
            json.dumps(
                {
                    key: value
                    for key, value in result.items()
                    if key not in {"sources", "training", "chunk_seals"}
                }
            )
        )
        return 0 if result["status"] in {CONTROL, COMPLETE, "paused"} else 2
    except (ValueError, OSError, KeyError, TimeoutError) as exc:
        print(
            json.dumps(
                {
                    "status": "stopped_preserving_evidence",
                    "error": str(exc),
                    "original_optimizer_updates": 0,
                    "automatic_follow_up": False,
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
