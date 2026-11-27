"""Freeze every final before matched fights/games; retain failures in paired denominators."""

from __future__ import annotations

from typing import Any

from spireshift.native_combat_behavior_data import intervals
from spireshift.native_teaching_data import ARMS, VARIANTS


def schedule(cfg: dict[str, Any], bank: dict[str, Any]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = [
        {"key": f"initial-p{p}", "kind": "import", "player": p} for p in (2, 3)
    ]
    states = {(p, a): f"initial-p{p}" for p in (2, 3) for a in ARMS}
    for e in range(1, cfg["learning"]["epochs"] + 1):
        for p in (2, 3):
            for arm in ARMS:
                key = f"fit-p{p}-{arm.replace('_', '-')}-e{e:02d}"
                tasks.append(
                    {
                        "key": key,
                        "kind": "fit",
                        "player": p,
                        "arm": arm,
                        "epoch": e,
                        "state": states[p, arm],
                    }
                )
                states[p, arm] = key
    finals = {
        f"p{p}-{a}": f"initial-p{p}" if a == "initial" else states[p, a]
        for p in (2, 3)
        for a in VARIANTS
    }
    tasks.append({"key": "frozen-finals", "kind": "freeze", "states": finals})
    fitting_ids = {r["root_id"] for r in bank["lessons"]}
    roots = [r for r in bank["roots"] if r["root_id"] in fitting_ids or r["partition"] == "heldout"]
    if cfg["stage"] == "short_control":
        roots = [r for r in roots if r["root_id"] in fitting_ids][:1]
    for i, root in enumerate(roots):
        for p in (2,) if cfg["stage"] == "short_control" else (2, 3):
            order = VARIANTS[(i + p) % 3 :] + VARIANTS[: (i + p) % 3]
            for arm in order:
                tasks.append(
                    {
                        "key": f"fight-{i:02d}-p{p}-{arm.replace('_', '-')}",
                        "kind": "fight",
                        "player": p,
                        "arm": arm,
                        "root_id": root["root_id"],
                        "partition": root["partition"],
                        "state": finals[f"p{p}-{arm}"],
                    }
                )
    for i, seed in enumerate(cfg["evaluation_seeds"]):
        for p in (2, 3):
            order = VARIANTS[(i + p) % 3 :] + VARIANTS[: (i + p) % 3]
            for arm in order:
                tasks.append(
                    {
                        "key": f"fresh-{seed['id']}-p{p}-{arm.replace('_', '-')}",
                        "kind": "fresh",
                        "player": p,
                        "arm": arm,
                        "seed": seed,
                        "state": finals[f"p{p}-{arm}"],
                    }
                )
    return tasks


def summary(cfg: dict[str, Any], done: dict[str, Any]) -> dict[str, Any]:
    seeds = cfg["evaluation_seeds"]
    cells = {
        (r["player"], r["arm"], r["seed_id"]): r for r in done.values() if r["kind"] == "fresh"
    }
    if len(cells) != sum(r["kind"] == "fresh" for r in done.values()):
        raise ValueError("Duplicate full-game cells do not create more independent evidence")
    expected = {(p, a, s["id"]) for p in (2, 3) for a in VARIANTS for s in seeds}
    if not cells.keys() <= expected:
        raise ValueError("Never add an unplanned or replacement evaluation world")
    columns = ("victory", "completed_acts", "maximum_floor", "training_return")
    values, players = {}, []
    for p in (2, 3):
        arms = {}
        for arm in VARIANTS:
            observed = [cells[p, arm, s["id"]] for s in seeds if (p, arm, s["id"]) in cells]
            clean = [r for r in observed if r["status"] == "terminal"]
            arms[arm] = {
                "denominator": len(seeds),
                "recorded": len(observed),
                "failed_games": len(observed) - len(clean),
                "not_attempted_games": len(seeds) - len(observed),
                "wins": sum(bool(r["victory"]) for r in clean),
                "mean_floor": sum(r["maximum_floor"] for r in clean) / len(seeds),
                "best_floor": max((r["maximum_floor"] for r in clean), default=0),
            }
            for s in seeds:
                r = cells.get((p, arm, s["id"]))
                values[p, arm, s["id"]] = [
                    float(r[k]) if r and r["status"] == "terminal" else 0.0 for k in columns
                ]
        players.append({"player": p, "arms": arms})
    paired: dict[str, Any] = {}
    by_player: dict[str, dict[str, Any]] = {str(p): {} for p in (2, 3)}
    complete = len(cells) == len(seeds) * 6
    if complete:
        for a, b in ((ARMS[1], ARMS[0]), (ARMS[1], "initial"), (ARMS[0], "initial")):
            differences = {}
            for p in (2, 3):
                differences[p] = [
                    [
                        x - y
                        for x, y in zip(values[p, a, s["id"]], values[p, b, s["id"]], strict=True)
                    ]
                    for s in seeds
                ]
                ci = intervals(differences[p]) if cfg["stage"] != "short_control" else [None] * 4
                by_player[str(p)][f"{a}_minus_{b}"] = {
                    k: {"mean": sum(x[j] for x in differences[p]) / len(seeds), "interval95": ci[j]}
                    for j, k in enumerate(columns)
                }
            pooled = [
                [(x + y) / 2 for x, y in zip(xx, yy, strict=True)]
                for xx, yy in zip(differences[2], differences[3], strict=True)
            ]
            ci = intervals(pooled) if cfg["stage"] != "short_control" else [None] * 4
            paired[f"{a}_minus_{b}"] = {
                k: {"mean": sum(x[j] for x in pooled) / len(seeds), "interval95": ci[j]}
                for j, k in enumerate(columns)
            }
    return {
        "players": players,
        "paired_by_player": by_player,
        "pooled_paired": paired,
        "complete": complete,
        "primary_comparison": "teacher_clone_minus_reference_clone",
        "untouched_original_comparisons_required": True,
        "terminal_victory_primary": True,
        "independent_unit": "native_seed_jointly_across_two_fixed_initializers",
        "training_worlds": 2,
        "uncertainty_covers_population_of_initializers": False,
        "failures_and_unattempted_value": 0,
        "checkpoint_promoted": False,
    }
