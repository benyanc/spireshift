"""Independently verify the completed normalization study without games or updates."""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_capacity_recovery_v1 import game_task
from spireshift.native_capacity_result_v1 import episode
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_curriculum_config import THREADS
from spireshift.native_normalization_inputs_v1 import EVALUATION
from spireshift.native_normalization_inputs_v1 import load as load_parent
from spireshift.native_normalization_inputs_v2 import RECIPE, assessment, context, load
from spireshift.native_normalization_recovery_v1 import FAILED, failure_facts
from spireshift.native_normalization_session_v1 import COMPLETE, comparison_report
from spireshift.native_normalized_actor_v1 import METHODS, CorrectionActor, initialize
from spireshift.native_normalized_actor_v1 import load as load_state
from spireshift.native_sealed_continuation_v1 import SealedPrefixJournal
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

MODULE = "spireshift.native_normalization_result_v1"
WORKSPACE = "artifacts/native-hidden-normalization/assessment-v1"
STATUS = "normalization_seals_lineages_and_native_endings_verified"
TOGGLES = ("Open inventory", "Close shop inventory")
LIMITS = dict(
    wall_seconds=540,
    cpu_seconds=900,
    storage_bytes=1_000_000_000,
    resident_memory_bytes=4_000_000_000,
)


def clustered(
    worlds: list[str],
    games: dict[tuple[str, int, str], dict[str, Any]],
    left: str,
    right: str,
    seed: int = 20261127,
    resamples: int = 10000,
) -> dict[str, Any]:
    """World-clustered bootstrap of right-minus-left rates, counting caps as no progress."""

    def score(row: dict[str, Any], what: str) -> int:
        if row["outcome"] not in {"win", "loss"}:
            return 0
        return int(row["outcome"] == "win") if what == "wins" else int(row["completed_acts"] >= 1)

    out: dict[str, Any] = {}
    for what in ("wins", "act1_clears"):
        diffs = [
            sum(score(games[w, p, right], what) - score(games[w, p, left], what) for p in (2, 3))
            for w in worlds
        ]
        rng = random.Random(seed)
        n = len(diffs)
        stats = sorted(
            sum(diffs[rng.randrange(n)] for _ in range(n)) / (2 * n) for _ in range(resamples)
        )
        discordant = Counter(
            (score(games[w, p, left], what), score(games[w, p, right], what))
            for w in worlds
            for p in (2, 3)
        )
        out[what] = {
            "difference": sum(diffs) / (2 * n),
            "interval_95": [stats[int(0.025 * resamples)], stats[int(0.975 * resamples) - 1]],
            "right_only": discordant[0, 1],
            "left_only": discordant[1, 0],
        }
    return {
        **out,
        "caps_counted_as_no_progress": True,
        "scope": "descriptive_these_128_worlds_two_fixed_initializers",
        "resamples": resamples,
        "seed": seed,
    }


def behaviour(rows: list[dict[str, Any]]) -> dict[str, Any]:
    decisions = sum(r["native_decisions"] for r in rows)
    toggles = sum(sum(r["shop_actions"].get(t, 0) for t in TOGGLES) for r in rows)
    return {
        "games": len(rows),
        "mean_native_decisions": decisions / len(rows),
        "shop_inventory_toggle_share": toggles / decisions,
        "games_over_100_toggles": sum(
            sum(r["shop_actions"].get(t, 0) for t in TOGGLES) > 100 for r in rows
        ),
        "act1_boss_reached": sum(any(b["act"] == 1 for b in r["bosses_reached"]) for r in rows),
        "act1_clears": sum(r["completed_acts"] >= 1 for r in rows),
        "capped": sum(r["outcome"] == "capped" for r in rows),
    }


def audit(root: Path, deadline: float) -> dict[str, Any]:
    cfg = load(root)
    ctx = context(root, cfg)
    before = frozen(root, ctx)
    profile = _shared_snapshot(Path.home() / SHARED_PROFILE)
    out = root / WORKSPACE
    out.mkdir(parents=True, exist_ok=True)
    final = out / "report.json"
    if final.exists():
        result = identified(final)
        check_sources(root, result["sources"])
        return result
    proof = assessment(root, cfg)
    parent = load_parent(root)
    result_path = root / cfg["workspace"] / "report.json"
    saved = identified(result_path)
    if (
        saved["status"] != COMPLETE
        or saved["config_id"] != manifest_identifier(cfg)
        or saved["stop"] is not None
        or saved["excluded_training_units"] != [FAILED]
        or saved["inherited_completed_units"] != 4234
        or saved["inherited_optimizer_updates"] != 15252
    ):
        raise ValueError("Require the exact completed normalization continuation")
    check_sources(root, {k: v for k, v in saved["sources"].items() if "/chunks/" not in k})
    store = SealedPrefixJournal(root, cfg, parent, proof["inherited_units"], frozenset({FAILED}))
    seals: dict[str, str] = {}
    sources = {
        RECIPE: _sha_file(root / RECIPE),
        str(result_path.relative_to(root)): _sha_file(result_path),
        str(Path(__file__).relative_to(root)): _sha_file(Path(__file__)),
    }

    def require(key: str, request: dict[str, Any]) -> dict[str, Any]:
        if time.monotonic() >= deadline:
            raise TimeoutError("The saved-only normalization audit reached its boundary")
        seal = store.completed(key, request)
        if seal is None or saved["chunk_seals"].get(key) != seal["report_id"]:
            raise ValueError(f"A normalization unit is missing or changed: {key}")
        seals[key] = seal["report_id"]
        path = store.path(key) / "done.json"
        sources[str(path.relative_to(root))] = _sha_file(path)
        return {"seal_id": seal["report_id"], **seal["result"]}

    counts: dict[str, Any] = {}
    curves: dict[str, list[int]] = {}
    fits = []
    capped = []
    failed_seen = False
    with store.lock():
        starting = {p: load_state(verified(root, cfg["starting_states"][str(p)])) for p in (2, 3)}
        require(
            "source-copies",
            {
                "source_states": {str(p): starting[p][1] for p in (2, 3)},
                "initialization": cfg["initialization"],
            },
        )
        current = {
            m: {p: load_state(store.path("source-copies") / f"p{p}-{m}.json") for p in (2, 3)}
            for m in METHODS
        }
        for m in METHODS:
            for p in (2, 3):
                if current[m][p][0] != initialize(
                    starting[p][0], m, cfg["initialization"]["correction_seeds"][str(p)]
                ):
                    raise ValueError("An initial full correction/reference/critic/Adam changed")
        count = cfg["plan"]["worlds_per_round"]
        for r in range(1, cfg["plan"]["rounds"] + 1):
            for p in (2, 3):
                for method in METHODS if (r + p) % 2 else METHODS[::-1]:
                    name = f"p{p}-{method}"
                    cohort = counts.setdefault(
                        name, dict(outcomes=Counter(), act1_clears=0, act2_clears=0, fits=0)
                    )
                    rows = []
                    clears = 0
                    for i in range((r - 1) * count + 1, r * count + 1):
                        task = game_task(cfg["plan"]["training"][i - 1], i, p, r, method)
                        request = {"task": task, "behavior_state_id": current[method][p][1]}
                        if task["key"] == FAILED:
                            if request != proof["failed_request"]:
                                raise ValueError("The failed-cell exclusion changed its behavior")
                            cohort["outcomes"]["failed"] += 1
                            rows.append({"outcome": "failed", "seal_id": proof["report_id"]})
                            failed_seen = True
                            continue
                        row = require(task["key"], request)
                        if (
                            row["task"] != task
                            or row["model_id"] != current[method][p][0].model.model_id
                        ):
                            raise ValueError("A training game used a different behavior or world")
                        episode(store.path(task["key"]), row)
                        cohort["outcomes"][row["outcome"]] += 1
                        if row["outcome"] == "capped":
                            capped.append(task["key"])
                        else:
                            clears += row["completed_acts"] >= 1
                            cohort["act1_clears"] += row["completed_acts"] >= 1
                            cohort["act2_clears"] += row["completed_acts"] >= 2
                        rows.append(row)
                    curves.setdefault(name, []).append(clears)
                    key = f"fit-p{p}-{method}-r{r:03d}"
                    fitted = require(
                        key,
                        {
                            "player": p,
                            "method": method,
                            "round": r,
                            "prior_state_id": current[method][p][1],
                            "game_seals": [row["seal_id"] for row in rows],
                        },
                    )
                    state, state_id = load_state(store.path(key) / "shared.json")
                    prior = current[method][p][0]
                    steps = fitted["work"]["optimizer_updates"]
                    if (
                        state_id != fitted["state_id"]
                        or state.model.model_id != fitted["model_id"]
                        or state.actor_adam.steps != prior.actor_adam.steps + steps
                        or state.value_adam.steps != prior.value_adam.steps + steps
                        or state.actor_adam.steps != fitted["actor_steps"]
                        or state.value_adam.steps != fitted["value_steps"]
                        or not isinstance(state.model.actor, CorrectionActor)
                        or state.model.actor.reference != starting[p][0].model.actor
                        or state.model.actor.correction_normalization != method
                        or fitted["eligible_terminal_worlds"]
                        != sum(row["outcome"] in {"win", "loss"} for row in rows)
                    ):
                        raise ValueError("A complete full-Adam/model/credit lineage changed")
                    current[method][p] = state, state_id
                    fits.append(fitted)
                    cohort["fits"] += 1
        if (
            not failed_seen
            or fits != saved["training"]
            or {m: {str(p): current[m][p][1] for p in (2, 3)} for m in METHODS}
            != saved["final_states"]
        ):
            raise ValueError("The round-64 selection or full fitting history changed")
        failed = failure_facts(store.original.path(FAILED))
        games: dict[tuple[str, int, str], dict[str, Any]] = {}
        arms: dict[str, list[dict[str, Any]]] = {}
        for i, seed in enumerate(cfg["plan"]["development"], 1):
            for p in (2, 3):
                for method in EVALUATION:
                    behavior = starting[p] if method == "reference" else current[method][p]
                    key = f"development-{i:04d}-p{p}-{method}"
                    task = dict(
                        key=key,
                        seed=seed,
                        seed_id=i,
                        player=p,
                        round=64,
                        partition="development",
                        arm="shared",
                    )
                    row = require(key, {"task": task, "behavior_state_id": behavior[1]})
                    if (
                        row["task"] != task
                        or row["model_id"] != behavior[0].model.model_id
                        or row["outcome"] not in {"win", "loss", "capped"}
                    ):
                        raise ValueError("A frozen evaluation policy, world or outcome changed")
                    episode(store.path(key), row)
                    games[seed, p, method] = row
                    arms.setdefault(f"p{p}-{method}", []).append(row)
        comparisons = comparison_report(cfg["plan"]["development"], games)
        if comparisons != saved["comparisons"] or seals != saved["chunk_seals"]:
            raise ValueError("The paired results or linked denominator differ")
        worlds = cfg["plan"]["development"]
        uncertainty = {
            f"{right}_versus_{left}": clustered(worlds, games, left, right)
            for left, right in (
                ("reference", "raw"),
                ("reference", "normalized"),
                ("raw", "normalized"),
            )
        }
        pooled = {
            arm: {
                "wins": sum(games[w, p, arm]["outcome"] == "win" for w in worlds for p in (2, 3)),
                "act1_clears": sum(
                    games[w, p, arm]["outcome"] != "capped"
                    and games[w, p, arm]["completed_acts"] >= 1
                    for w in worlds
                    for p in (2, 3)
                ),
                "act2_clears": sum(
                    games[w, p, arm]["outcome"] != "capped"
                    and games[w, p, arm]["completed_acts"] >= 2
                    for w in worlds
                    for p in (2, 3)
                ),
                "capped": sum(
                    games[w, p, arm]["outcome"] == "capped" for w in worlds for p in (2, 3)
                ),
                "planned": 2 * len(worlds),
            }
            for arm in EVALUATION
        }
        if frozen(root, ctx) != before or _shared_snapshot(Path.home() / SHARED_PROFILE) != profile:
            raise ValueError("Frozen build, checkpoints/full Adam or personal profile changed")
    return write(
        final,
        {
            "status": STATUS,
            "source_report_id": saved["report_id"],
            "source_config_id": saved["config_id"],
            "verified_units": len(seals),
            "training_counts": {
                k: {**v, "outcomes": dict(v["outcomes"])} for k, v in counts.items()
            },
            "training_act1_clears_by_quarter": {
                k: [sum(v[q * 16 : (q + 1) * 16]) for q in range(4)] for k, v in curves.items()
            },
            "capped_training_units": capped,
            "failed_training_units": [FAILED],
            "failed_game": failed,
            "failed_prefix_training_admitted": False,
            "full_model_and_Adam_fits_reloaded": len(fits),
            "optimizer_updates_on_copies": sum(row["work"]["optimizer_updates"] for row in fits),
            "development_games_verified": len(games),
            "development_pooled": pooled,
            "development_behaviour": {k: behaviour(v) for k, v in sorted(arms.items())},
            "comparisons": comparisons,
            "world_clustered_uncertainty": uncertainty,
            "final_states": saved["final_states"],
            "frozen_checks": before,
            "shared_profile_unchanged": True,
            "games_launched": 0,
            "optimizer_updates": 0,
            "promotion_allowed": False,
            "official_live_qualification_granted": False,
            "final_test_worlds_used": False,
            "scope": "128_worlds_two_fixed_initializers_native_only_no_competence_claim",
            "sources": sources,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = Path.cwd()
    if any(os.environ.get(k) != "1" for k in THREADS):
        raise ValueError("Require the pinned numerical runtime")
    out = root / WORKSPACE
    out.mkdir(parents=True, exist_ok=True)
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
                "--execute",
                str(attempt),
            ],
            working_directory=root,
            experiment_kind=ExperimentKind.OTHER,
            report_path=out / f"resources-{attempt}.json",
            artifact_roots=[out],
            limits=ResourceLimits(**LIMITS),
        )
        print(json.dumps(tracked.report))
        return 0 if tracked.exit_code == 0 and tracked.report["cap"] is None else 2
    result = audit(root, time.monotonic() + LIMITS["wall_seconds"] - 10)
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in {"sources", "comparisons", "training_counts", "failed_game"}
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
