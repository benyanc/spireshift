"""Compare raw and normalized shared corrections with equal starting behavior."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_capacity_session_v1 as capacity
from spireshift import native_qualified_learning_session_v1 as previous
from spireshift.engine_native import _running_games
from spireshift.native_a8_head_policy import HeadState, save
from spireshift.native_capacity_control_v1 import same_initial_games, saved_menus
from spireshift.native_curriculum_config import THREADS
from spireshift.native_normalization_fit_v1 import fit
from spireshift.native_normalization_inputs_v1 import (
    EVALUATION,
    MODULE,
    SCHEMA,
    context,
    load,
)
from spireshift.native_normalized_actor_v1 import METHODS, initialize, using_correction_scoring
from spireshift.native_normalized_actor_v1 import load as load_state
from spireshift.native_qualified_learning_worker_v3 import play
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

CONTROL = "normalization_collect_fit_reload_and_reference_equivalence_verified"
COMPLETE = "normalization_training_and_fresh_comparisons_complete"


def comparison_report(
    worlds: list[str], games: dict[tuple[str, int, str], dict[str, Any]]
) -> dict[str, Any]:
    result = {}
    for left, right in (("reference", "raw"), ("reference", "normalized"), ("raw", "normalized")):
        selected = {
            (seed, p, "original" if arm == left else "fitted"): row
            for (seed, p, arm), row in games.items()
            if arm in (left, right)
        }
        result[f"{right}_versus_{left}"] = previous.development_report(worlds, selected)
    return result


class Session(capacity.Session):
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
                    state = initialize(
                        self.starting[p][0],
                        method,
                        self.cfg["initialization"]["correction_seeds"][str(p)],
                    )
                    identifier = save(target / f"p{p}-{method}.json", state)
                    result[method][str(p)] = {
                        "state_id": identifier,
                        "model_id": state.model.model_id,
                        "hidden_units": state.model.actor.hidden_units,
                        "trainable_actor_parameters": state.model.actor.parameter_count,
                        "frozen_reference_model_id": self.starting[p][0].model.actor.model_id,
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
                expected = initialize(
                    self.starting[p][0],
                    method,
                    self.cfg["initialization"]["correction_seeds"][str(p)],
                )
                if (
                    states[method][p][1] != self.initial_states[method][str(p)]["state_id"]
                    or states[method][p][0] != expected
                ):
                    raise ValueError("A full correction/reference/critic/Adam source copy changed")
        return states

    def check_menus(self, states: dict[str, Any]) -> dict[str, Any]:
        paired = saved_menus(
            self.root,
            self.cfg,
            {
                "standard": states["raw"],
                "expanded": states["normalized"],
            },
            self.ctx["score"],
        )
        reference = saved_menus(
            self.root,
            self.cfg,
            {
                "standard": self.starting,
                "expanded": states["raw"],
            },
            self.ctx["score"],
        )
        return {
            **paired,
            "plain_reference_comparison": reference,
            "identical_initial_logits_and_critic": True,
        }

    def run(self) -> dict[str, Any]:
        current = self.source_copies()
        if self.control:
            self.saved_input_checks = self.unit(
                "saved-menu-equivalence",
                {"states": self.initial_states},
                30,
                lambda _: self.check_menus(current),
            )
            collected: dict[tuple[int, str], list[dict[str, Any]]] = {}
            for p in (2, 3):
                for method in METHODS:
                    rows = [
                        self.game(seed, i, p, 1, "control", method, current[method][p])
                        for i, seed in enumerate(self.cfg["plan"]["control"], 1)
                    ]
                    if any(row["outcome"] not in previous.TERMINAL for row in rows):
                        raise ValueError("Initial native controls must reach genuine endings")
                    collected[p, method] = rows
                for i in range(1, 3):
                    checked = same_initial_games(
                        self.store.path(f"control-{i:04d}-p{p}-raw"),
                        self.store.path(f"control-{i:04d}-p{p}-normalized"),
                    )
                    self.initial_native_pairs_verified += 1
                    self.initial_native_choices_verified += checked["matching_model_choices"]
            for p in (2, 3):
                for method in METHODS:
                    current[method][p] = self.learn_method(
                        p,
                        method,
                        1,
                        collected[p, method],
                        current[method][p],
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
                            "A reloaded correction copy did not finish its native game"
                        )
        else:
            control = capacity.control_receipt(self.root, self.cfg)
            if control["initial_states"] != self.initial_states:
                raise ValueError("Production initial states differ from the qualified controls")
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
                            work = self.training[-1]
                            print(
                                f"Round {r}/64 p{p} {method}: {work['outcomes']}; "
                                f"Act 1 clears {work['act1_clears']}/{len(rows)}; "
                                f"{work['work']['optimizer_updates']} new updates",
                                flush=True,
                            )
            for i, seed in enumerate(self.cfg["plan"]["development"], 1):
                for p in (2, 3):
                    for method in EVALUATION:
                        # The reference is the actual plain source, never a trainable correction.
                        state = self.starting[p] if method == "reference" else current[method][p]
                        row = self.game(seed, i, p, 64, "development", method, state)
                        self.evaluation[seed, p, method] = row
                        print(f"Development {i}/128 p{p} {method}: {row['outcome']}", flush=True)
        self.unchanged()
        return {
            "status": CONTROL if self.control else COMPLETE,
            "final_states": {m: {str(p): current[m][p][1] for p in (2, 3)} for m in METHODS},
        }


def execute(root: Path, cfg: dict[str, Any], control: bool, deadline: float) -> dict[str, Any]:
    with (
        using_correction_scoring(),
        patch.multiple(previous, context=context, load=load, play=play, load_state=load_state),
        patch.multiple(
            capacity,
            Session=Session,
            load=load,
            load_state=load_state,
            fit=fit,
            SCHEMA=SCHEMA,
            CONTROL=CONTROL,
            COMPLETE=COMPLETE,
            comparison_report=comparison_report,
        ),
    ):
        return capacity.execute(root, cfg, control, deadline)


def control_receipt(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    with patch.object(capacity, "CONTROL", CONTROL):
        result = capacity.control_receipt(root, cfg)
    if not result["saved_input_checks"]["identical_initial_logits_and_critic"] or any(
        not row["work"]["reference_actor_unchanged"] for row in result["training"]
    ):
        raise ValueError("The normalization controls did not preserve exact reference behavior")
    return result


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
                            "status": "normalization_control_verified",
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
                    "Close STS2. Raw versus normalized shared scoring corrections on four copies. "
                    "4,096 fresh training games, then 768 fresh A8 comparison games. "
                    "Allow 14–24 hours; 48-hour cap. "
                    "Original/full source Adam and game stay frozen. "
                    "Clean seals resume; incomplete or uncertain work stops without retry. "
                    "No automatic promotion or follow-up.",
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
