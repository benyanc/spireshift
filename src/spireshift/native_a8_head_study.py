"""Sustained native A8 comparison of shared and separate scoring heads."""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Any

from spireshift import native_a8_archive_selector_continue as adapter
from spireshift import native_a8_head_policy as policy
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_archive_batch import known_seeds
from spireshift.native_a8_archive_fit_session import ERRORS
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_head_policy import ARMS, HeadState
from spireshift.native_a8_head_training import matched_update, training_examples
from spireshift.native_a8_mix_audit import first_difference
from spireshift.native_a8_own_training import SCOPE
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_paired_report import TERMINAL, summarize
from spireshift.native_a8_rescue_game import TRACE
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_flow_inputs_v12 import canonical_seed
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

MODULE = "spireshift.native_a8_head_study"
RECIPE = "configs/native-learning/sts2-v0.111.0-a8-scoring-heads-v1.json"
PPO_RECIPE = "configs/native-learning/sts2-v0.111.0-a8-archive-own-training-v1.json"
WRAPPER = "scripts/compare-a8-scoring-heads-v1.sh"
SCHEMA = "native-a8-scoring-heads-comparison-v1"
CONTROL_PASSED = "scoring_heads_collect_fit_reload_verified"
COMPLETE = "scoring_heads_comparison_complete"
ROUNDS = 64
WORLDS_PER_ROUND = 16
PROGRESS_ROUNDS = (0, 16, 32, 48, 64)
PROGRESS_WORLDS = 16
HOLDOUT_WORLDS = 128
CONTROL_TRAIN_WORLDS = 3
CONTROL_PREFIX_CHOICES = 8
LIMITS = {
    "wall_seconds": 86_400,
    "cpu_seconds": 86_400,
    "storage_bytes": 72_000_000_000,
    "resident_memory_bytes": 4_000_000_000,
}
CONTROL_LIMITS = {
    **LIMITS,
    "wall_seconds": 275,
    "cpu_seconds": 600,
    "storage_bytes": 500_000_000,
}
FIT_RESERVE = 480
SOURCES = (
    "engine_neural",
    "full_run_policy",
    "full_run_ppo_math",
    "native_a8_head_policy",
    "native_a8_head_study",
    "native_a8_head_training",
    "native_a8_own_experience",
    "native_a8_own_ppo",
    "native_a8_paired_report",
    "native_action_context",
    "native_combat_behavior_policy",
    "native_context_journal",
    "native_structured_model",
    "native_structured_policy",
    "native_systematic_selectors_v2",
    "native_value_credit",
    "native_win4_game",
    "native_win4_plan",
    "resource_tracking",
)


def implementation(root: Path) -> dict[str, str]:
    files = [WRAPPER, *(f"src/spireshift/{name}.py" for name in SOURCES)]
    return {name: _sha_file(root / name) for name in files}


def world_schedule() -> dict[str, list[str]]:
    return {
        partition: [f"SP1RESH1FTA8HD{code}{i:04d}" for i in range(1, count + 1)]
        for partition, code, count in (
            ("train", "T", ROUNDS * WORLDS_PER_ROUND),
            ("progress", "D", PROGRESS_WORLDS),
            ("holdout", "F", HOLDOUT_WORLDS),
            ("control", "S", CONTROL_TRAIN_WORLDS),
            ("reload", "Q", 1),
        )
    }


def declaration() -> dict[str, Any]:
    return {
        "rounds": ROUNDS,
        "worlds_per_round": WORLDS_PER_ROUND,
        "minimum_paired_terminal_worlds": 12,
        "progress_rounds": list(PROGRESS_ROUNDS),
        "progress_worlds": PROGRESS_WORLDS,
        "holdout_worlds": HOLDOUT_WORLDS,
        "control_training_worlds": CONTROL_TRAIN_WORLDS,
        "control_reload_choices": CONTROL_PREFIX_CHOICES,
        "world_schedule_id": manifest_identifier(world_schedule()),
        "arms": list(ARMS),
        "initializers": list(PLAYERS),
    }


@dataclass
class Study:
    root: Path
    cfg: dict[str, Any]
    source: adapter.Comparison

    def store(self, control: bool) -> ChunkJournal:
        recipe = {**self.cfg, "workspace": self.cfg["control_workspace"]} if control else self.cfg
        return ChunkJournal(self.root, recipe)

    def unchanged(self, profile: dict[str, Any]) -> None:
        if json.loads((self.root / RECIPE).read_text()) != self.cfg:
            raise ValueError("The head study recipe changed")
        check_sources(self.root, self.cfg["implementation"])
        verified(self.root, self.cfg["ppo_recipe"])
        verified(self.root, self.cfg["selector_recipe"])
        adapter.verify_boundary(self.source, profile)


def load(root: Path) -> Study:
    cfg = json.loads((root / RECIPE).read_text())
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["plan"] != declaration()
        or cfg["limits"] != LIMITS
        or cfg["control_limits"] != CONTROL_LIMITS
        or cfg["workspace"] == cfg["control_workspace"]
        or cfg["implementation"] != implementation(root)
        or verified(root, cfg["selector_recipe"]) != root / adapter.RECIPE
        or verified(root, cfg["ppo_recipe"]) != root / PPO_RECIPE
    ):
        raise ValueError("Require the exact head comparison plan and sources")
    source = adapter.load(root)
    base = source.study.base
    ppo = json.loads((root / PPO_RECIPE).read_text())
    for field in ("objective", "game_limits", "training_score_id", "credit", "settings"):
        if cfg[field] != ppo[field]:
            raise ValueError(f"Require the same declared PPO {field} in both arms")
    if (
        cfg["objective"] != source.study.cfg["objective"]
        or cfg["training_score_id"] != base.ctx["score"].spec_id
        or cfg["environment_id"] != base.ctx["environment_id"]
        or cfg["starting_states"] != {str(p): source.states[p, "fitted"][2] for p in PLAYERS}
    ):
        raise ValueError("Require the same exact archived actors, critics and full Adam states")
    proof = adapter.saved_report(
        source.store(True),
        adapter.control_plan(source),
        adapter.CONTROL_PASSED,
        fit_report_id=source.fit_proof["report_id"],
        frozen_checks=source.study.frozen_checks,
        **adapter.SCOPE_LIMITS,
    )
    if proof is None or proof["report_id"] != cfg["selector_control_id"]:
        raise ValueError("Require sealed native adapter checks for both selector formats")
    parent = json.loads(verified(root, source.cfg["parent_recipe"]).read_text())
    used = (
        known_seeds(base)
        | set(source.fit_proof["partitions"]["train"])
        | set(source.fit_proof["partitions"]["holdout"])
        | {case["seed"] for case in source.study.bank["worlds"].values()}
        | set(source.study.cfg["development"] + source.study.cfg["final_test"])
        | set(parent["development"] + [parent["prefix_world"], parent["ending_world"]])
        | set(source.cfg["control_seeds"].values())
    )
    for phase in ("study", "control"):
        used.update(ppo[phase].get("development", []))
        used.update(ppo[phase].get("reload", []))
        used.update(task["seed"] for task in ppo[phase]["training"])
    seeds = [seed for partition in world_schedule().values() for seed in partition]
    if (
        len(set(seeds)) != len(seeds)
        or set(seeds) & used
        or any(canonical_seed(seed) != seed for seed in seeds)
    ):
        raise ValueError("The training, progress, holdout and control worlds must be disjoint")
    return Study(root, cfg, source)


def evaluate(worlds: list[str], rows: dict[tuple[str, int, str], dict[str, Any]]) -> dict[str, Any]:
    outcome = summarize(
        worlds,
        {
            (world, p, "original" if arm == "shared" else "fitted"): row
            for (world, p, arm), row in rows.items()
        },
    )
    for p in PLAYERS:
        info = outcome["by_initializer"][str(p)]
        info["arms"] = {"shared": info["arms"]["original"], "split": info["arms"]["fitted"]}
        for old, new in (
            ("fitted_only_wins", "split_only_wins"),
            ("original_only_wins", "shared_only_wins"),
            ("fitted_minus_original_win_rate_bounds", "split_minus_shared_win_rate_bounds"),
        ):
            info[new] = info.pop(old)
        for arm in ARMS:
            games = [
                row
                for (_, player, name), row in rows.items()
                if player == p and name == arm and row["outcome"] in TERMINAL
            ]
            info["arms"][arm].update(
                act1_clears=sum(row["completed_acts"] > 0 for row in games),
                mean_terminal_floor=fmean(row["maximum_floor"] for row in games) if games else None,
            )
    outcome["pooled_split_minus_shared_win_rate_bounds"] = outcome.pop(
        "pooled_fitted_minus_original_win_rate_bounds"
    )
    # In a zero-win panel a bootstrap of all zero differences stays at zero.
    # Record that as inconclusive, and require complete paired terminal evidence
    # before interpreting a directional interval.
    outcome["comparison"] = "inconclusive"
    ci = outcome["seed_clustered_bootstrap_95"]
    if ci is not None:
        lo, hi = ci["intervals"]["pooled_wins"]
        if lo > 0:
            outcome["comparison"] = "split_higher_win_rate"
        elif hi < 0:
            outcome["comparison"] = "shared_higher_win_rate"
    return outcome


class CleanPause(RuntimeError):
    """Stop before beginning a new sealed unit."""


Saved = tuple[HeadState, str]


class Session:
    def __init__(self, study: Study, *, control: bool, deadline: float) -> None:
        self.study, self.control, self.deadline = study, control, deadline
        self.store = study.store(control)
        self.ctx = study.source.study.base.ctx
        self.profile = _shared_snapshot(Path.home() / SHARED_PROFILE)
        self.active = "initialization"
        self.training: list[dict[str, Any]] = []
        self.progress: dict[str, Any] = {}
        self.holdout: dict[str, Any] | None = None
        self.reload: dict[str, Any] = {}
        self.seals: dict[str, str] = {}
        self.games_seen = 0

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
                raise CleanPause("Session time reserve reached at a clean boundary")
            target = self.store.begin(key, request)
            result = action(target)
            seal = self.store.commit(key, request, result)
        if self.control:
            self.seals[key] = seal["report_id"]
        return seal

    def checkpoint(self, key: str, arm: str, expected: dict[str, Any]) -> Saved:
        state, state_id = policy.load(self.store.path(key) / f"{arm}.json")
        if (
            state.model.arm != arm
            or state_id != expected["state_id"]
            or state.model.model_id != expected["model_id"]
            or state.value_adam.steps != expected["value_steps"]
            or state.actor_adam.steps != expected["actor_steps"]
            or (state.combat_adam.steps if state.combat_adam else None) != expected["combat_steps"]
        ):
            raise ValueError("Reloaded scoring weights or optimizer identity differs")
        return state, state_id

    @staticmethod
    def persist(target: Path, states: dict[str, HeadState]) -> dict[str, dict[str, Any]]:
        return {
            arm: {
                "state_id": policy.save(target / f"{arm}.json", state),
                "model_id": state.model.model_id,
                "value_steps": state.value_adam.steps,
                "actor_steps": state.actor_adam.steps,
                "combat_steps": state.combat_adam.steps if state.combat_adam else None,
            }
            for arm, state in states.items()
        }

    def start(self, p: int) -> dict[str, Saved]:
        model, adam, state_id = self.study.source.states[p, "fitted"]
        initial = {arm: policy.initialize(model, adam, arm) for arm in ARMS}
        key = f"initial-p{p}"
        seal = self.unit(
            key,
            {"parent_state_id": state_id},
            5,
            lambda target: {"states": self.persist(target, initial)},
        )
        states = {arm: self.checkpoint(key, arm, seal["result"]["states"][arm]) for arm in ARMS}
        if any(states[arm][0] != initial[arm] for arm in ARMS):
            raise ValueError("Initial actor weights, critic or Adam differ from the parent")
        return states

    def game(self, task: dict[str, Any], saved: Saved) -> dict[str, Any]:
        state, state_id = saved
        if state.model.arm != task["arm"]:
            raise ValueError("A game must use the declared scoring-head checkpoint")
        limits = self.study.cfg["game_limits"].copy()
        reserve = limits["episode_wall_seconds"] + 30
        if task["partition"] == "reload_control":
            limits["maximum_decisions"] = CONTROL_PREFIX_CHOICES
            reserve = 45
        ctx = {**self.ctx, "config": {"plan": limits}, "execution_id": self.store.config_id}
        self.active = task["key"]
        if not self.store.path(task["key"]).exists() and _running_games():
            raise ValueError("Close STS2 and wait for other native workers")

        def collect(target: Path) -> dict[str, Any]:
            check_sources(self.study.root, self.study.source.cfg["implementation"])
            return policy.play(ctx, task, target, state, self.deadline)

        seal = self.unit(
            task["key"],
            {"task": task, "behavior_state_id": state_id, "model_id": state.model.model_id},
            reserve,
            collect,
        )
        row = seal["result"]
        if (
            row["task"] != task
            or row["model_id"] != state.model.model_id
            or row["outcome"] not in {*TERMINAL, "capped"}
        ):
            raise ValueError("A saved game differs from its planned world or behavior checkpoint")
        self.games_seen += 1
        return {"seal_id": seal["report_id"], **row}

    def fit(
        self, p: int, r: int, games: dict[str, list[dict[str, Any]]], current: dict[str, Saved]
    ) -> dict[str, Saved]:
        key = f"fit-p{p}-r{r:03d}"
        request = {
            "prior": {arm: current[arm][1] for arm in ARMS},
            "games": {arm: [row["seal_id"] for row in games[arm]] for arm in ARMS},
        }

        def fit_pair(target: Path) -> dict[str, Any]:
            self.study.unchanged(self.profile)
            states = {arm: current[arm][0] for arm in ARMS}
            paired = [
                pair
                for pair in zip(*(games[arm] for arm in ARMS), strict=True)
                if all(row["outcome"] in TERMINAL for row in pair)
            ]
            minimum = (
                CONTROL_TRAIN_WORLDS
                if self.control
                else self.study.cfg["plan"]["minimum_paired_terminal_worlds"]
            )
            credit, examples = {}, {}
            work: dict[str, Any] = {
                "optimizer_steps_per_arm": 0,
                "stop_reason": "insufficient_paired_terminal_worlds",
            }
            if len(paired) >= minimum:
                for i, arm in enumerate(ARMS):
                    paths = [(self.store.path(pair[i]["task"]["key"]), pair[i]) for pair in paired]
                    examples[arm], credit[arm] = training_examples(
                        paths, states[arm], self.ctx["score"], self.study.cfg["credit"], r
                    )
                states, work = matched_update(
                    states,
                    examples,
                    self.study.cfg["settings"],
                    90_000 + p * 1000 + r,
                    deadline=self.deadline - 15,
                )
            return {
                "player": p,
                "round": r,
                "paired_terminal_worlds": len(paired),
                "game_outcomes": {
                    arm: dict(Counter(row["outcome"] for row in games[arm])) for arm in ARMS
                },
                "states": self.persist(target, states),
                "credit": credit,
                "work": work,
            }

        seal = self.unit(key, request, 25 if self.control else FIT_RESERVE, fit_pair)
        result = seal["result"]
        states = {arm: self.checkpoint(key, arm, result["states"][arm]) for arm in ARMS}
        if any(
            states[arm][0].value_adam.steps - current[arm][0].value_adam.steps
            != result["work"]["optimizer_steps_per_arm"]
            for arm in ARMS
        ):
            raise ValueError("Matched optimizer work differs after reload")
        if self.control:
            split, prior = states["split"][0], current["split"][0]
            if (
                result["work"]["optimizer_steps_per_arm"] < 1
                or states["shared"][0].model.actor == current["shared"][0].model.actor
                or split.model.actor == prior.model.actor
                or split.model.combat_actor == prior.model.combat_actor
            ):
                raise ValueError("Control must update the shared actor and both separate heads")
        self.training.append({**result, "seal_id": seal["report_id"]})
        print(
            f"Round {r}/{1 if self.control else ROUNDS}, player {p}, "
            f"{result['paired_terminal_worlds']} matched games, "
            f"{result['work']['optimizer_steps_per_arm']} PPO steps per method",
            flush=True,
        )
        return states

    def train_round(self, r: int, worlds: list[str], states: dict[int, dict[str, Saved]]) -> None:
        initials: dict[str, str] = {}
        for p in PLAYERS:
            games: dict[str, list[dict[str, Any]]] = {arm: [] for arm in ARMS}
            for i, world in enumerate(worlds, 1):
                for arm in ARMS if (i + p + r) % 2 else ARMS[::-1]:
                    task: dict[str, Any] = {
                        "key": f"train-r{r:03d}-{i:02d}-p{p}-{arm}",
                        "round": r,
                        "player": p,
                        "arm": arm,
                        "seed": world,
                        "seed_id": (r - 1) * WORLDS_PER_ROUND + i,
                        "partition": "control" if self.control else "train",
                    }
                    game = self.game(task, states[p][arm])
                    if (
                        initials.setdefault(world, game["initial_public_input_id"])
                        != game["initial_public_input_id"]
                    ):
                        raise ValueError("A matched training world has different public starts")
                    games[arm].append(game)
                if self.control:
                    left, right = (
                        self.store.path(games[arm][-1]["task"]["key"]) / TRACE for arm in ARMS
                    )
                    if first_difference(left, right) is not None:
                        raise ValueError("Initial shared and split actors must choose identically")
            states[p] = self.fit(p, r, games, states[p])

    def assessment(
        self, stage: str, r: int, worlds: list[str], states: dict[int, dict[str, Saved]]
    ) -> dict[str, Any]:
        rows: dict[tuple[str, int, str], dict[str, Any]] = {}
        initials: dict[str, str] = {}
        ids = {str(p): {arm: states[p][arm][1] for arm in ARMS} for p in PLAYERS}
        for i, world in enumerate(worlds, 1):
            for p in PLAYERS:
                for arm in ARMS if (i + p) % 2 else ARMS[::-1]:
                    task: dict[str, Any] = {
                        "key": f"{stage}-r{r:03d}-{i:03d}-p{p}-{arm}",
                        "round": r,
                        "player": p,
                        "arm": arm,
                        "seed": world,
                        "partition": "reload_control" if self.control else "development",
                    }
                    try:
                        game = self.game(task, states[p][arm])
                        if (
                            initials.setdefault(world, game["initial_public_input_id"])
                            != game["initial_public_input_id"]
                        ):
                            raise ValueError(
                                "A matched evaluation world has different public starts"
                            )
                        if self.control and (game["outcome"], game["native_decisions"]) != (
                            "capped",
                            CONTROL_PREFIX_CHOICES,
                        ):
                            raise ValueError(
                                "Reloaded model did not deliver its exact short prefix"
                            )
                        rows[world, p, arm] = game
                    except (CleanPause, *ERRORS) as exc:
                        if (
                            not isinstance(exc, CleanPause)
                            and self.store.path(task["key"]).exists()
                        ):
                            rows[world, p, arm] = {"outcome": "failed"}
                        partial = {"checkpoint_ids": ids, **evaluate(worlds, rows)}
                        if stage == "holdout":
                            self.holdout = partial
                        else:
                            self.progress[str(r)] = partial
                        raise
            if not self.control and i % 16 == 0:
                print(f"{stage} round {r}: {i}/{len(worlds)} matched worlds", flush=True)
        if self.control:
            return {f"p{p}-{arm}": rows[worlds[0], p, arm] for p in PLAYERS for arm in ARMS}
        return {"checkpoint_ids": ids, **evaluate(worlds, rows)}

    def execute(self, until: int, attempt: int, control_id: str | None) -> dict[str, Any]:
        worlds = world_schedule()
        final = self.store.workspace / "report.json"
        with self.store.lock():
            if final.is_file():
                report = identified(final)
                if (
                    report["config_id"] != self.store.config_id
                    or report["status"] != (CONTROL_PASSED if self.control else COMPLETE)
                    or report["control_id"] != control_id
                ):
                    raise ValueError("The completed head comparison belongs to another recipe")
                return report
            status, stop = "paused", None
            try:
                self.study.unchanged(self.profile)
                states = {p: self.start(p) for p in PLAYERS}
                if self.control:
                    self.train_round(1, worlds["control"], states)
                    self.reload = self.assessment("reload", 1, worlds["reload"], states)
                    status = CONTROL_PASSED
                else:
                    self.progress["0"] = self.assessment("progress", 0, worlds["progress"], states)
                    for r in range(1, until + 1):
                        start = (r - 1) * WORLDS_PER_ROUND
                        self.train_round(
                            r, worlds["train"][start : start + WORLDS_PER_ROUND], states
                        )
                        self.study.unchanged(self.profile)
                        if r in PROGRESS_ROUNDS:
                            self.progress[str(r)] = self.assessment(
                                "progress", r, worlds["progress"], states
                            )
                    if until == ROUNDS:
                        self.holdout = self.assessment("holdout", ROUNDS, worlds["holdout"], states)
                        status = COMPLETE
                    else:
                        stop = {"reason": "requested_round_boundary", "round": until}
                self.study.unchanged(self.profile)
            except CleanPause as exc:
                self.study.unchanged(self.profile)
                stop = {"reason": str(exc), "next_unit": self.active}
            except ERRORS as exc:
                status = "stopped_preserving_evidence"
                stop = {"unit": self.active, "error": f"{type(exc).__name__}: {exc}"}
            report = {
                "schema_version": SCHEMA,
                "status": status,
                "config_id": self.store.config_id,
                "control_id": control_id,
                "attempt": attempt,
                "selector_control_id": self.study.cfg["selector_control_id"],
                "starting_states": self.study.cfg["starting_states"],
                "frozen_checks": (
                    None
                    if status == "stopped_preserving_evidence"
                    else self.study.source.study.frozen_checks
                ),
                "verified_games": self.games_seen,
                "depth": {
                    str(p): {
                        "training_rounds_with_updates": sum(
                            row["work"]["optimizer_steps_per_arm"] > 0
                            for row in self.training
                            if row["player"] == p
                        ),
                        "optimizer_steps_per_method": sum(
                            row["work"]["optimizer_steps_per_arm"]
                            for row in self.training
                            if row["player"] == p
                        ),
                        "paired_terminal_training_worlds": sum(
                            row["paired_terminal_worlds"]
                            for row in self.training
                            if row["player"] == p
                        ),
                        "selected_decisions_per_method": sum(
                            row["work"].get("selected_decisions_per_arm", 0)
                            for row in self.training
                            if row["player"] == p and row["work"]["optimizer_steps_per_arm"] > 0
                        ),
                    }
                    for p in PLAYERS
                },
                "training_rounds": self.training,
                "progress": self.progress,
                "holdout": self.holdout,
                "reload": self.reload,
                "seals": self.seals,
                "stop": stop,
                **SCOPE,
            }
            if status in {COMPLETE, CONTROL_PASSED}:
                return write(final, report)
            return write(self.store.workspace / f"session-{attempt}.json", report)


def require_control(study: Study) -> str:
    store = study.store(True)
    report = identified(store.workspace / "report.json")
    if (
        report["status"] != CONTROL_PASSED
        or report["config_id"] != store.config_id
        or report["stop"] is not None
        or report["verified_games"] != (CONTROL_TRAIN_WORLDS + 1) * len(PLAYERS) * len(ARMS)
        or len(report["training_rounds"]) != len(PLAYERS)
        or len(report["reload"]) != len(PLAYERS) * len(ARMS)
        or len(report["seals"]) != report["verified_games"] + 2 * len(PLAYERS)
        or report["frozen_checks"] != study.source.study.frozen_checks
    ):
        raise ValueError("Require sealed collect, fit, reload and matched-choice controls")
    for key, report_id in report["seals"].items():
        request = json.loads((store.path(key) / "active.json").read_text())["request"]
        seal = store.completed(key, request)
        if seal is None or seal["report_id"] != report_id:
            raise ValueError("A native learner control seal changed")
    resource = identified(store.workspace / f"resources-{report['attempt']}.json")
    if (
        resource["status"] != "completed"
        or resource["exit_code"] != 0
        or resource["cap"] is not None
        or resource["limits"] != CONTROL_LIMITS
        or resource["artifacts"]["roots"] != [str(store.workspace)]
        or resource["command"][:8]
        != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--execute", "control"]
    ):
        raise ValueError("Require the matching bounded learner control receipt")
    return str(report["report_id"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", choices=("control", "study"), help=argparse.SUPPRESS)
    parser.add_argument("--until-round", type=int, default=ROUNDS)
    parser.add_argument("--attempt", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 1 <= args.until_round <= ROUNDS:
        parser.error(f"--until-round must be between 1 and {ROUNDS}")
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the launcher with the pinned numerical thread settings")
        started = time.monotonic()
        study = load(Path.cwd())
        control = args.check or args.execute == "control"
        store = study.store(control)
        control_id = None if control else require_control(study)
        if args.preflight:
            complete = (store.workspace / "report.json").is_file()
            print(
                json.dumps(
                    {
                        "status": COMPLETE if complete else "scoring_heads_study_ready",
                        "training_rounds": ROUNDS,
                        "training_games_per_method_per_initializer": ROUNDS * WORLDS_PER_ROUND,
                        "training_games": ROUNDS * WORLDS_PER_ROUND * len(ARMS) * len(PLAYERS),
                        "progress_rounds": PROGRESS_ROUNDS,
                        "progress_worlds": PROGRESS_WORLDS,
                        "holdout_worlds": HOLDOUT_WORLDS,
                        "planned_evaluation_games": (
                            (len(PROGRESS_ROUNDS) * PROGRESS_WORLDS + HOLDOUT_WORLDS)
                            * len(ARMS)
                            * len(PLAYERS)
                        ),
                        "control_id": control_id,
                        "frozen_checks": study.source.study.frozen_checks,
                    }
                )
            )
            return 0
        if control and (store.workspace / "report.json").is_file():
            print(json.dumps({"status": CONTROL_PASSED, "report_id": require_control(study)}))
            return 0
        limits = CONTROL_LIMITS if control else LIMITS
        if args.execute is None:
            if _running_games():
                raise ValueError("Close STS2 and wait for any other native worker")
            attempt = time.time_ns()
            if not control:
                print(
                    "Compare shared and split heads on fresh Ironclad/A8 worlds. "
                    "Sealed games and checkpoints resume from the same command.",
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
                    "--execute",
                    "control" if control else "study",
                    "--attempt",
                    str(attempt),
                    "--until-round",
                    str(args.until_round),
                ],
                experiment_kind=ExperimentKind.TRAINING,
                working_directory=study.root,
                report_path=store.workspace / f"resources-{attempt}.json",
                artifact_roots=[store.workspace],
                limits=ResourceLimits(**limits),
                poll_interval_seconds=8 if not control else 0.5,
            )
            print(json.dumps(tracked.report))
            if tracked.report["cap"] is not None:
                return 2
            return tracked.exit_code if tracked.exit_code is not None else 2
        if args.attempt is None or args.attempt < 1:
            raise ValueError("Use the launcher for a resource-tracked session")
        session = Session(study, control=control, deadline=started + limits["wall_seconds"] - 45)
        report = session.execute(args.until_round, args.attempt, control_id)
        print(
            json.dumps(
                {
                    key: value
                    for key, value in report.items()
                    if key not in {"training_rounds", "progress", "seals", "reload"}
                }
            )
        )
        accepted = {CONTROL_PASSED} if control else {COMPLETE, "paused"}
        return 0 if report["status"] in accepted else 2
    except ERRORS as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc), **SCOPE}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
