"""Qualify shorter actor credit on sealed model-owned training episodes."""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from dataclasses import dataclass, replace
from itertools import combinations
from pathlib import Path
from statistics import median
from typing import Any

from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path
from spireshift.native_a8_mix_audit import source
from spireshift.native_a8_mix_fit import batches
from spireshift.native_a8_mix_session import Study, unchanged
from spireshift.native_a8_own_experience import samples
from spireshift.native_a8_own_ppo import Decision, loss_gradient
from spireshift.native_a8_own_training import State
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_a8_world_credit import SETTINGS
from spireshift.native_a8_world_credit_audit import STATUS as AUDITED
from spireshift.native_a8_world_credit_reload import admitted, require_reloads
from spireshift.native_a8_world_credit_session import AREA as SOURCE_AREA
from spireshift.native_a8_world_credit_session import journal
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS, execution_runtime
from spireshift.native_gradient_checks import cosine
from spireshift.native_value_credit import (
    ValueRun,
    action_advantages,
    fit_baseline,
    prediction_metrics,
    redistribute_terminal_return,
)
from spireshift.native_win4_game import write
from spireshift.neural_combat import _numpy

AREA = "artifacts/native-a8-temporal-credit"
SCHEMA = "native-a8-temporal-credit-screen-v1"
FULL, SHORT = "full_trace", "short_trace"
METHODS = {FULL: 1.0, SHORT: 0.95}
REGULARIZATION = 0.001
MAX_ERROR_RATIO = 0.90
MAX_MEDIAN_DECREASE = 0.05


@dataclass
class Credit:
    rows: dict[str, dict[str, list[Decision]]]
    diagnostics: dict[str, Any]


def predictor_source(base: Study, p: int, original: State) -> tuple[list[ValueRun], list[str]]:
    source_store = base.source
    model, _, state_id = original
    examples, seals = [], []
    for task in source_store.recipe["study"]["training"]:
        if (task["partition"], task["player"], task["round"]) != ("train", p, 1):
            continue
        key = task["key"]
        seal = source_store.completed(
            key, {"task": task, "behavior_state_id": state_id, "model_id": model.model_id}
        )
        if (
            seal is None
            or seal["report_id"] != base.source_report["seals"][key]
            or seal["result"] != base.source_report["games"][key]
        ):
            raise ValueError("Require exact historical training-only forecast examples")
        _, run, _ = samples(
            source_store.path(key), seal["result"], model, base.ctx["score"], "train", 1
        )
        examples.append(run)
        seals.append(seal["report_id"])
    if len(examples) != 12:
        raise ValueError("Require the twelve exact historical forecast training games")
    return examples, seals


def direction(model: CachedContextModel, worlds: dict[str, list[Decision]]) -> dict[str, Any]:
    np = _numpy()
    raw = [d.advantage for rows in worlds.values() for d in rows]
    mean = math.fsum(raw) / len(raw)
    scale = math.sqrt(math.fsum((v - mean) ** 2 for v in raw) / len(raw))
    if scale <= 1e-8:
        raise ValueError("Cannot compare gradients from constant credit")
    size = model.actor.parameter_count
    settings: dict[str, Any] = {**SETTINGS, "value_coefficient": 0.0, "entropy_coefficient": 0.0}
    gradients = []
    for rows in worlds.values():
        result = np.zeros(size)
        for batch in batches(rows, settings["minibatch_decisions"]):
            normalized = [replace(d, advantage=(d.advantage - mean) / scale) for d in batch]
            _, grad, stats = loss_gradient(model, normalized, settings)
            if stats["approximate_joint_kl"] > 1e-12:
                raise ValueError("Behavior checkpoint must reconstruct the saved training choices")
            result += np.asarray(grad[:size]) * len(batch)
        gradients.append(result)
    total = np.sum(gradients, axis=0)
    splits = []
    for idx in combinations(range(1, len(worlds)), len(worlds) // 2 - 1):
        half = gradients[0] + np.sum([gradients[i] for i in idx], axis=0)
        splits.append(cosine(half, total - half))
    agreements = [v for v in splits if v is not None]
    if len(agreements) != len(splits):
        raise ValueError("A world split has no usable actor direction")
    return {
        "worlds": len(worlds),
        "complementary_splits": len(splits),
        "median_cosine": median(agreements),
        "opposing_splits": sum(v < 0 for v in agreements),
    }


def build_credit(
    base: Study, recipe: dict[str, Any], store: ChunkJournal, owner: dict[str, Any], p: int
) -> Credit:
    original = base.originals[p]
    model = original[0]
    forecast_runs, forecast_seals = predictor_source(base, p, original)
    state_model = fit_baseline(forecast_runs, "public_residual_ridge", REGULARIZATION)
    constant = fit_baseline(forecast_runs, "constant", REGULARIZATION)
    held, held_seals = [], []
    predictions, constants = {}, {}
    worlds: dict[str, dict[str, list[Decision]]] = {arm: {} for arm in METHODS}
    for task in recipe["study"]["training"]:
        if task["player"] != p:
            continue
        key = task["key"]
        seal = store.completed(key, {"task": task, "state_id": original[2]})
        if (
            seal is None
            or seal["report_id"] != owner["seals"][key]
            or seal["result"] != owner["games"][key]
        ):
            raise ValueError("Only the exact model-owned world-credit training runs are eligible")
        batch, run, _ = samples(
            store.path(key), seal["result"], model, base.ctx["score"], "train", 1
        )
        held.append(run)
        held_seals.append(seal["report_id"])
        values = predictions[run.seed] = state_model.predict(run)
        constants[run.seed] = constant.predict(run)
        rewards = redistribute_terminal_return(run.target, run.potentials)
        if not math.isclose(
            math.fsum(rewards) + run.potentials[0], run.target, abs_tol=1e-12, rel_tol=0
        ):
            raise ValueError("Progress pulses changed the declared full-run training score")
        for arm, trace in METHODS.items():
            credit = action_advantages(run.target, run.potentials, values, trace)
            if trace == 1 and any(
                not math.isclose(value, run.target - baseline, abs_tol=1e-12, rel_tol=0)
                for value, baseline in zip(credit, values, strict=True)
            ):
                raise ValueError("The full trace must reproduce return-minus-value credit")
            worlds[arm].setdefault(task["seed"], []).extend(
                replace(d, advantage=a) for d, a in zip(batch, credit, strict=True)
            )
    if len(held) != 24 or len(worlds[FULL]) != 8:
        raise ValueError("Require all 24 training runs per initializer")
    metric, control = prediction_metrics(held, predictions), prediction_metrics(held, constants)
    gradients = {arm: direction(model, rows) for arm, rows in worlds.items()}
    ratio = metric["mse"] / control["mse"]
    return Credit(
        worlds,
        {
            "forecast_training_seals": forecast_seals,
            "credit_training_seals": held_seals,
            "held_prediction_mse_ratio": ratio,
            "held_prediction": metric,
            "held_constant": control,
            "gradient_splits": gradients,
            "forecast_passed": ratio <= MAX_ERROR_RATIO and metric["explained_variance"] > 0,
            "direction_passed": (
                gradients[SHORT]["median_cosine"] > 0
                and gradients[SHORT]["median_cosine"]
                >= gradients[FULL]["median_cosine"] - MAX_MEDIAN_DECREASE
            ),
            "decisions": sum(len(rows) for rows in worlds[FULL].values()),
        },
    )


def screen(root: Path, attempt: int, deadline: float) -> dict[str, Any]:
    base, recipe, reload_cfg, short_states = admitted(root)
    require_reloads(base, reload_cfg, short_states)
    before = frozen(root, base.ctx)
    store = journal(root, recipe, False)
    audit_path = _private_path(root, f"{SOURCE_AREA}/assessment-v3-{attempt}/report.json")
    audit = identified(audit_path)
    owner_path = store.workspace / f"attempt-{attempt}.json"
    owner = identified(owner_path)
    if (
        audit["status"] != AUDITED
        or audit["owner"] != source(root, owner_path)
        or audit["frozen_checks"] != before
        or audit["fitting_qualified"] is not True
    ):
        raise ValueError("The saved world-credit outcome must have passed independent verification")
    path = _private_path(root, f"{AREA}/screen-v1")
    path.mkdir(parents=True)
    checks = {}
    for p in PLAYERS:
        credit = build_credit(base, recipe, store, owner, p)
        checks[str(p)] = credit.diagnostics
        print(f"Verified the held-world forecast and gradient splits for player {p}.", flush=True)
    unchanged(base, before, deadline)
    if execution_runtime(base.ctx["node"]) != base.runtime:
        raise ValueError("Numerical runtime changed during credit diagnostics")
    gains = [
        check["gradient_splits"][SHORT]["median_cosine"]
        - check["gradient_splits"][FULL]["median_cosine"]
        for check in checks.values()
    ]
    passed = (
        all(check["forecast_passed"] and check["direction_passed"] for check in checks.values())
        and math.fsum(gains) > 0
    )
    return write(
        path / "report.json",
        {
            "schema_version": SCHEMA,
            "status": "temporal_credit_screen_passed"
            if passed
            else "temporal_credit_screen_blocked",
            "source_audit": source(root, audit_path),
            "objective": base.cfg["objective"],
            "traces": METHODS,
            "regularization": REGULARIZATION,
            "maximum_held_forecast_error_ratio": MAX_ERROR_RATIO,
            "maximum_per_initializer_cosine_decrease": MAX_MEDIAN_DECREASE,
            "players": checks,
            "passed": passed,
            "frozen_checks": before,
            "optimizer_updates": 0,
            "native_game_launches": 0,
            "held_out_evaluation_data_used": False,
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt", type=int)
    args = parser.parse_args()
    if any(os.environ.get(name) != "1" for name in THREADS):
        raise SystemExit("Use the pinned numerical environment")
    report = screen(Path.cwd(), args.attempt, time.monotonic() + 250)
    print(json.dumps(report, indent=2))
