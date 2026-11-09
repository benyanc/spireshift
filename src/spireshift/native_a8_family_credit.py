"""Measure combat and noncombat credit on the same sealed training games."""

from __future__ import annotations

import fcntl
import json
import math
import os
import time
from collections import Counter
from dataclasses import replace
from itertools import combinations
from pathlib import Path
from statistics import median
from typing import Any

from spireshift.engine_native import _private_path
from spireshift.native_a8_mix_fit import batches
from spireshift.native_a8_mix_session import unchanged
from spireshift.native_a8_own_experience import groups
from spireshift.native_a8_own_ppo import Decision, loss_gradient
from spireshift.native_a8_own_training import SCOPE
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_a8_temporal_credit import METHODS, build_credit
from spireshift.native_a8_temporal_credit_session import AREA, Session, inputs
from spireshift.native_a8_world_credit import SETTINGS
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_curriculum_config import THREADS, execution_runtime
from spireshift.native_gradient_checks import cosine
from spireshift.native_win4_game import write
from spireshift.neural_combat import _numpy

SCHEMA = "native-a8-family-credit-screen-v1"
REPORT = f"{AREA}/family-credit-screen-v1/report.json"
GATE = {"opposing_same_worlds": 6, "opposing_disjoint_half_pairs": 47}
OWNERS = ("combat", "noncombat")


def training_menus(
    session: Session, p: int
) -> tuple[dict[str, list[tuple[str, float]]], dict[str, Any]]:
    store, model = session.source, session.references[p, "original"][0]
    menus: dict[str, list[tuple[str, float]]] = {}
    coverage: Counter[tuple[str, str]] = Counter()
    worlds: dict[tuple[str, str], set[str]] = {}
    acts: Counter[int] = Counter()
    tasks = [t for t in store.recipe["study"]["training"] if t["player"] == p]
    for task in tasks:
        key, seed = task["key"], task["seed"]
        if task["partition"] != "train":
            raise ValueError("Decision-family diagnostics require training-only episodes")
        tagged = menus.setdefault(seed, [])
        for group in groups(store.path(key), model.model_id):
            frame, first = group[0]
            owner = "combat" if first["combat_owned"] else "noncombat"
            tagged.append((owner, math.fsum(c["log_probability"] for _, c in group)))
            if any(len(f["actions"]) > 1 for f, _ in group):
                context = frame["public_input"]["context"]
                family = owner, context["interaction"]["kind"]
                coverage[family] += 1
                worlds.setdefault(family, set()).add(seed)
                acts[context["persistent"]["run"]["act"]] += 1
    return menus, {
        "games": len(tasks),
        "independent_worlds": len(menus),
        "multi_choice_native_decisions_by_act": {str(a): n for a, n in sorted(acts.items())},
        "by_family": [
            {"owner": owner, "family": family, "decisions": n, "worlds": len(worlds[owner, family])}
            for (owner, family), n in sorted(coverage.items())
        ],
    }


def alignment(values: list[float | None]) -> dict[str, Any]:
    valid = [value for value in values if value is not None]
    return {
        "planned": len(values),
        "defined": len(valid),
        "opposing": sum(value < 0 for value in valid),
        "median_cosine": median(valid) if valid else None,
    }


def directions(
    model: CachedContextModel,
    worlds: dict[str, list[Decision]],
    menus: dict[str, list[tuple[str, float]]],
) -> dict[str, Any]:
    if len(worlds) != 8 or set(worlds) != set(menus):
        raise ValueError("Require eight complete independent training worlds")
    np = _numpy()
    raw = [decision.advantage for rows in worlds.values() for decision in rows]
    mean = math.fsum(raw) / len(raw)
    std = math.sqrt(math.fsum((value - mean) ** 2 for value in raw) / len(raw))
    if std <= 1e-8:
        raise ValueError("A constant advantage supplies no training direction")
    settings: dict[str, Any] = {**SETTINGS, "value_coefficient": 0.0, "entropy_coefficient": 0.0}
    size = model.actor.parameter_count
    gradients = np.zeros((len(worlds), len(OWNERS), size))
    for i, (world, rows) in enumerate(worlds.items()):
        split: dict[str, list[Decision]] = {owner: [] for owner in OWNERS}
        for decision, (owner, logp) in zip(rows, menus[world], strict=True):
            if not math.isclose(decision.old_log_probability, logp, rel_tol=0, abs_tol=1e-12):
                raise ValueError("Training credit lost its delivered menu and owner")
            split[owner].append(replace(decision, advantage=(decision.advantage - mean) / std))
        for j, owner in enumerate(OWNERS):
            for batch in batches(split[owner], settings["minibatch_decisions"]):
                _, grad, stats = loss_gradient(model, batch, settings)
                if stats["approximate_joint_kl"] > 1e-12:
                    raise ValueError("Behavior weights must reconstruct the saved policy")
                gradients[i, j] += np.asarray(grad[:size]) * (len(batch) / len(rows))

    same = alignment([cosine(g[0], g[1]) for g in gradients])
    total = gradients.sum(axis=0)
    different: list[float | None] = []
    for half in combinations(range(1, len(worlds)), 3):
        left = gradients[0] + gradients[list(half)].sum(axis=0)
        right = total - left
        different.extend((cosine(left[0], right[1]), cosine(right[0], left[1])))
    disjoint = alignment(different)
    return {
        "same_world": same,
        "disjoint_four_world_halves": disjoint,
        "pooled_direction_cosine": cosine(total[0], total[1]),
        "world_equal_contribution_l2": {
            owner: float(np.linalg.norm(total[i] / len(worlds))) for i, owner in enumerate(OWNERS)
        },
        "recurring_conflict": (
            same["defined"] == same["planned"]
            and disjoint["defined"] == disjoint["planned"]
            and same["opposing"] >= GATE["opposing_same_worlds"]
            and disjoint["opposing"] >= GATE["opposing_disjoint_half_pairs"]
        ),
    }


def screen(root: Path, deadline: float) -> dict[str, Any]:
    session = inputs(root)
    base, store = session.base, session.source
    before = frozen(root, base.ctx)
    by_initializer: dict[str, Any] = {}
    with (store.workspace / "session.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        for p in PLAYERS:
            credit = build_credit(base, store.recipe, store, session.owner, p)
            menus, coverage = training_menus(session, p)
            by_initializer[str(p)] = {
                "coverage": coverage,
                "credit_training_seals": credit.diagnostics["credit_training_seals"],
                "directions": {
                    trace: directions(base.originals[p][0], credit.rows[trace], menus)
                    for trace in METHODS
                },
            }
            print(f"Measured saved decision coverage and directions for player {p}.", flush=True)
        unchanged(base, before, deadline)
        if execution_runtime(base.ctx["node"]) != base.runtime:
            raise ValueError("Frozen numerical runtime changed")
    qualifying = [
        trace
        for trace in METHODS
        if all(row["directions"][trace]["recurring_conflict"] for row in by_initializer.values())
    ]
    path = _private_path(root, REPORT)
    path.parent.mkdir()
    return write(
        path,
        {
            "schema_version": SCHEMA,
            "status": "family_credit_screen_complete",
            "training_source": session.screen["source_audit"],
            "training_config_id": store.config_id,
            "temporal_screen_id": session.screen["report_id"],
            "objective": base.cfg["objective"],
            "diagnostic_gate_per_initializer": GATE,
            "scope": (
                "behavior_actor_gradient_only_with_global_credit_normalization_and_equal_worlds"
            ),
            "by_initializer": by_initializer,
            "qualifying_traces": qualifying,
            "held_out_evaluation_data_used": False,
            "native_game_launches": 0,
            "optimizer_updates": 0,
            "frozen_checks": before,
            **SCOPE,
        },
    )


if __name__ == "__main__":
    if any(os.environ.get(name) != "1" for name in THREADS):
        raise SystemExit("Use the pinned numerical environment")
    result = screen(Path.cwd(), time.monotonic() + 260)
    print(json.dumps({k: result[k] for k in ("status", "qualifying_traces", "report_id")}))
