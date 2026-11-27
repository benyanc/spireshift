"""Four copied learners: continue 32 units versus expand to 128, then fresh full-run A8 pairs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_qualified_learning_session_v1 as previous
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_head_policy import HeadState, save
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_capacity_control_v1 import same_initial_games, saved_menus
from spireshift.native_capacity_inputs_v1 import EVALUATION, METHODS, MODULE, SCHEMA, context, load
from spireshift.native_combat_intent_model import load as load_state
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_curriculum_config import THREADS
from spireshift.native_policy_capacity_v1 import expand
from spireshift.native_qualified_learning_fit_v1 import fit
from spireshift.native_qualified_learning_worker_v3 import play
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

CONTROL = "capacity_collect_fit_reload_and_initial_equivalence_verified"
COMPLETE = "capacity_training_and_fresh_comparisons_complete"


def comparison_report(
    worlds: list[str], games: dict[tuple[str, int, str], dict[str, Any]]
) -> dict[str, Any]:
    result = {}
    for left, right in (
        ("reference", "standard"),
        ("reference", "expanded"),
        ("standard", "expanded"),
    ):
        selected = {
            (seed, p, "original" if arm == left else "fitted"): row
            for (seed, p, arm), row in games.items()
            if arm in (left, right)
        }
        result[f"{right}_versus_{left}"] = previous.development_report(worlds, selected)
    return result


def control_receipt(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    result = identified(root / cfg["control_workspace"] / "report.json")
    check_sources(root, result["sources"])
    if (
        result["status"] != CONTROL
        or result["config_id"]
        != manifest_identifier({**cfg, "workspace": cfg["control_workspace"]})
        or result["optimizer_updates_on_copies"] != 8
        or result["initial_native_pairs_verified"] != 4
        or not all(result["frozen_checks"].values())
    ):
        raise ValueError(
            "Require the exact saved/native collect-fit-reload controls on four copies"
        )
    return result


class Session(previous.Session):
    def __init__(self, root: Path, cfg: dict[str, Any], control: bool, deadline: float):
        super().__init__(root, cfg, control, deadline)
        self.cohort_counts: dict[str, Counter[str]] = {}
        self.initial_states: dict[str, Any] = {}
        self.initial_native_pairs_verified = 0
        self.initial_native_choices_verified = 0

    def unchanged(self) -> None:
        if load(self.root) != self.cfg or frozen(self.root, self.ctx) != self.before:
            raise ValueError(
                "The frozen build, full source checkpoints/Adam or declared study changed"
            )
        if _shared_snapshot(Path.home() / SHARED_PROFILE) != self.profile:
            raise ValueError("The personal game profile changed")

    def source_copies(self) -> dict[str, dict[int, tuple[HeadState, str]]]:
        request = {
            "source_states": {str(p): self.starting[p][1] for p in (2, 3)},
            "initialization": self.cfg["initialization"],
        }

        def prepare(target: Path) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for method in METHODS:
                result[method] = {}
                for p in (2, 3):
                    state = self.starting[p][0]
                    if method == "expanded":
                        state = expand(
                            state, 128, self.cfg["initialization"]["expansion_seeds"][str(p)]
                        )
                    state_id = save(target / f"p{p}-{method}.json", state)
                    result[method][str(p)] = {
                        "state_id": state_id,
                        "model_id": state.model.model_id,
                        "hidden_units": state.model.actor.hidden_units,
                        "actor_parameters": state.model.actor.parameter_count,
                        "actor_steps": state.actor_adam.steps,
                        "value_steps": state.value_adam.steps,
                    }
            return {"states": result, "optimizer_updates": 0}

        row = self.unit("source-copies", request, 40, prepare)
        self.initial_states = row["states"]
        states = {
            m: {p: load_state(self.store.path("source-copies") / f"p{p}-{m}.json") for p in (2, 3)}
            for m in METHODS
        }
        for method in METHODS:
            for p in (2, 3):
                if states[method][p][1] != self.initial_states[method][str(p)]["state_id"]:
                    raise ValueError("A copied complete starting state changed on reload")
        return states

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
        counts = self.cohort_counts.setdefault(f"{partition}-p{p}-{arm}", Counter())
        try:
            row = super().game(seed, index, p, round_index, partition, arm, state)
        except (ValueError, OSError, KeyError, TimeoutError):
            counts["failed"] += 1
            raise
        counts[row["outcome"]] += 1
        return row

    def learn_method(
        self, p: int, method: str, r: int, rows: list[dict[str, Any]], state: tuple[HeadState, str]
    ) -> tuple[HeadState, str]:
        key = f"fit-p{p}-{method}-r{r:03d}"
        request = {
            "player": p,
            "method": method,
            "round": r,
            "prior_state_id": state[1],
            "game_seals": [row["seal_id"] for row in rows],
        }

        def update(target: Path) -> dict[str, Any]:
            self.unchanged()
            eligible = [
                (self.store.path(row["task"]["key"]), row)
                for row in rows
                if row["outcome"] in previous.TERMINAL
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
                    820_000 + p * 1000 + r,
                    self.deadline - 10,
                    control_steps=2 if self.control else None,
                )
            identifier = save(target / "shared.json", after)
            return {
                "player": p,
                "method": method,
                "round": r,
                "state_id": identifier,
                "model_id": after.model.model_id,
                "actor_steps": after.actor_adam.steps,
                "value_steps": after.value_adam.steps,
                "eligible_terminal_worlds": len(eligible),
                "outcomes": dict(Counter(row["outcome"] for row in rows)),
                "act1_clears": sum(
                    row["completed_acts"] >= 1
                    for row in rows
                    if row["outcome"] in previous.TERMINAL
                ),
                "act2_clears": sum(
                    row["completed_acts"] >= 2
                    for row in rows
                    if row["outcome"] in previous.TERMINAL
                ),
                "work": work,
            }

        row = self.unit(key, request, 20 if self.control else 300, update)
        restored, identifier = load_state(self.store.path(key) / "shared.json")
        steps = row["work"]["optimizer_updates"]
        if (
            identifier != row["state_id"]
            or restored.model.model_id != row["model_id"]
            or restored.actor_adam.steps - state[0].actor_adam.steps != steps
            or restored.value_adam.steps - state[0].value_adam.steps != steps
        ):
            raise ValueError("A complete copied actor/critic/Adam restore differs")
        if self.control and (steps != 2 or restored.model.weights() == state[0].model.weights()):
            raise ValueError("Each disposable capacity copy must really collect, update and reload")
        self.training.append(row)
        return restored, identifier

    def run(self) -> dict[str, Any]:
        current = self.source_copies()
        reference = current["standard"].copy()
        if self.control:
            self.saved_input_checks = self.unit(
                "saved-menu-equivalence",
                {"states": self.initial_states},
                30,
                lambda _: saved_menus(self.root, self.cfg, current, self.ctx["score"]),
            )
            collected: dict[tuple[int, str], list[dict[str, Any]]] = {}
            for p in (2, 3):
                for method in METHODS:
                    rows = [
                        self.game(seed, i, p, 1, "control", method, current[method][p])
                        for i, seed in enumerate(self.cfg["plan"]["control"], 1)
                    ]
                    if any(row["outcome"] not in previous.TERMINAL for row in rows):
                        raise ValueError(
                            "Initial native capacity controls must reach genuine endings"
                        )
                    collected[p, method] = rows
                for i in range(1, 3):
                    checked = same_initial_games(
                        self.store.path(f"control-{i:04d}-p{p}-standard"),
                        self.store.path(f"control-{i:04d}-p{p}-expanded"),
                    )
                    self.initial_native_pairs_verified += 1
                    self.initial_native_choices_verified += checked["matching_model_choices"]
            for p in (2, 3):
                for method in METHODS:
                    current[method][p] = self.learn_method(
                        p, method, 1, collected[p, method], current[method][p]
                    )
            for p in (2, 3):
                for method in METHODS:
                    row = self.game(
                        self.cfg["plan"]["reload"][0],
                        1,
                        p,
                        1,
                        "reload-control",
                        method,
                        current[method][p],
                    )
                    if row["outcome"] not in previous.TERMINAL:
                        raise ValueError(
                            "Reloaded capacity copy did not finish a normal-start game"
                        )
        else:
            control = control_receipt(self.root, self.cfg)
            if control["initial_states"] != self.initial_states:
                raise ValueError(
                    "Main copies differ from the exactly qualified initial policies/full Adam"
                )
            count = self.cfg["plan"]["worlds_per_round"]
            for r in range(1, self.cfg["plan"]["rounds"] + 1):
                seeds = self.cfg["plan"]["training"][(r - 1) * count : r * count]
                for p in (2, 3):
                    order = METHODS if (r + p) % 2 else METHODS[::-1]
                    for method in order:
                        rows = [
                            self.game(
                                seed, (r - 1) * count + i, p, r, "train", method, current[method][p]
                            )
                            for i, seed in enumerate(seeds, 1)
                        ]
                        key = f"fit-p{p}-{method}-r{r:03d}"
                        reused = (self.store.path(key) / "done.json").exists()
                        current[method][p] = self.learn_method(
                            p, method, r, rows, current[method][p]
                        )
                        if not reused:
                            row = self.training[-1]
                            print(
                                f"Round {r}/64 p{p} {method}: {row['outcomes']}; "
                                f"Act 1 clears {row['act1_clears']}/{len(rows)}; "
                                f"{row['work']['optimizer_updates']} new updates",
                                flush=True,
                            )
            for i, seed in enumerate(self.cfg["plan"]["development"], 1):
                for p in (2, 3):
                    for method in EVALUATION:
                        state = reference[p] if method == "reference" else current[method][p]
                        row = self.game(seed, i, p, 64, "development", method, state)
                        self.evaluation[seed, p, method] = row
                        print(f"Development {i}/128 p{p} {method}: {row['outcome']}", flush=True)
        self.unchanged()
        return {
            "status": CONTROL if self.control else COMPLETE,
            "final_states": {m: {str(p): current[m][p][1] for p in (2, 3)} for m in METHODS},
        }


def execute(root: Path, cfg: dict[str, Any], control: bool, deadline: float) -> dict[str, Any]:
    session = Session(root, cfg, control, deadline)
    with session.store.lock():
        final = session.store.workspace / "report.json"
        if final.exists():
            result = identified(final)
            if result["config_id"] != session.store.config_id:
                raise ValueError("The saved capacity study declaration changed")
            check_sources(root, result["sources"])
            session.unchanged()
            return result
        stopped = None
        try:
            outcome = session.run()
        except (ValueError, OSError, KeyError, TimeoutError, previous.CleanPause) as exc:
            outcome = {
                "status": "paused"
                if isinstance(exc, previous.CleanPause)
                else "stopped_preserving_evidence"
            }
            stopped = {"unit": session.active, "error": f"{type(exc).__name__}: {exc}"}
            session.unchanged()
        result = {
            "schema_version": SCHEMA,
            "config_id": session.store.config_id,
            **outcome,
            "stop": stopped,
            "initial_states": session.initial_states,
            "initial_native_pairs_verified": session.initial_native_pairs_verified,
            "initial_native_choices_verified": session.initial_native_choices_verified,
            "saved_input_checks": session.saved_input_checks,
            "training": session.training,
            "chunk_seals": session.seals,
            "cohort_counts": {k: dict(v) for k, v in session.cohort_counts.items()},
            "optimizer_updates_on_copies": sum(
                r["work"]["optimizer_updates"] for r in session.training
            ),
            "comparisons": None
            if control
            else comparison_report(cfg["plan"]["development"], session.evaluation),
            "planned_training_games": 4096 if not control else 8,
            "planned_development_games": 768 if not control else 0,
            "matched_optimizer_work_claimed": False,
            "frozen_checks": session.before,
            "original_optimizer_updates": 0,
            "training_starts": "fresh_normal_starts_only",
            "fixture_choices_used_as_labels": False,
            "promotion_allowed": False,
            "official_live_qualification_granted": False,
            "final_test_worlds_used": False,
            "adaptive_controller_allowed": False,
            "automatic_follow_up": False,
        }
        result["sources"] = {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in session.store.workspace.rglob("*")
            if p.is_file() and p != final
        }
        return write(
            final
            if outcome["status"] in {CONTROL, COMPLETE}
            else session.store.workspace / f"stop-{time.time_ns()}.json",
            result,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("short", "saved", "run"), nargs="?", default="run")
    parser.add_argument("--execute", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = Path.cwd()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the pinned numerical runtime")
        cfg = load(root)
        if args.mode in {"saved", "run"}:
            receipt = control_receipt(root, cfg)
            if args.mode == "saved":
                print(
                    json.dumps(
                        {
                            "status": "capacity_control_verified",
                            "report_id": receipt["report_id"],
                            "games_launched": 0,
                            "optimizer_updates": 0,
                        }
                    )
                )
                return 0
        control = args.mode == "short"
        limits = cfg["control_limits"] if control else cfg["limits"]
        area = root / (cfg["control_workspace"] if control else cfg["workspace"])
        area.mkdir(parents=True, exist_ok=True)
        if args.execute is None:
            attempt = time.time_ns()
            if not control:
                print(
                    "Four checkpoint copies: continue 32 units versus expand to 128. "
                    "4,096 model-owned training games, then 768 fresh A8 comparison games. "
                    "Allow 14–24 hours; 48-hour outer cap. "
                    "Originals, finals/full Adam and game stay frozen.",
                    flush=True,
                )
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
                experiment_kind=ExperimentKind.OTHER if control else ExperimentKind.TRAINING,
                report_path=area / f"resources-{attempt}.json",
                artifact_roots=[area],
                limits=ResourceLimits(**limits),
            )
            print(json.dumps(tracked.report))
            return 0 if tracked.exit_code == 0 and tracked.report["cap"] is None else 2
        if _running_games():
            raise ValueError("Close STS2 and wait for other native workers")
        with patch.multiple(previous, context=context, load=load, play=play):
            result = execute(root, cfg, control, time.monotonic() + limits["wall_seconds"] - 10)
        print(
            json.dumps(
                {k: v for k, v in result.items() if k not in {"sources", "training", "chunk_seals"}}
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
