from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.native_policy_trial_inputs import seed_inputs, validate
from spireshift.native_policy_trial_plan import plan, request, summary
from spireshift.native_policy_updates import SETTINGS


def config(control: bool = True) -> dict[str, Any]:
    return {
        "schema_version": "native-policy-update-comparison-config-v1",
        "stage": "short_control" if control else "bounded_policy_comparison",
        "rounds": 1 if control else 2,
        "batch_games": 2 if control else 32,
        "chunk_games": 2 if control else 8,
        "evaluation_worlds": 1 if control else 32,
        "checkpoint_selection": "final_only_no_development_selection",
        "evaluation_behavior": "greedy_combat_sampled_noncombat_v1",
        "learning": dict(SETTINGS),
        "maximum_decisions": 4096,
        "episode_wall_seconds": 120,
        "credit": {
            "baseline": "public_residual_ridge",
            "regularization": 0.001,
            "folds": 4,
            "fold_salt": "native-whole-run-value-crossfit-v1",
        },
        "session_limits": {
            "wall_seconds": 240 if control else 900,
            "cpu_seconds": 480 if control else 1800,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 1000000000 if control else 4000000000,
        },
    }


def worlds(control: bool = True) -> list[dict[str, Any]]:
    cfg = config(control)
    train = cfg["rounds"] * cfg["batch_games"]
    return [
        {
            "id": i,
            "seed": f"SP1RESH1FTPG{i:04d}",
            "partition": "train" if i < train else "development",
        }
        for i in range(train + cfg["evaluation_worlds"])
    ]


@pytest.mark.parametrize("control,games,fits", [(True, 8, 2), (False, 256, 4)])
def test_finite_schedule_copies_both_states_and_freezes_finals_before_evaluation(
    control: bool, games: int, fits: int
) -> None:
    cfg, seeds = config(control), worlds(control)
    validate(cfg)
    tasks = plan(cfg, seeds)
    assert len({t["key"] for t in tasks}) == len(tasks)
    assert sum(len(t.get("seeds", [])) + (t["kind"] == "evaluate") for t in tasks) == games
    assert sum(t["kind"] == "fit" for t in tasks) == fits
    first_eval = next(i for i, t in enumerate(tasks) if t["kind"] == "evaluate")
    assert all(t["kind"] == "evaluate" for t in tasks[first_eval:])
    for t in tasks:
        if t["kind"] == "collect":
            assert all(s["partition"] == "train" for s in t["seeds"])
        elif t["kind"] == "evaluate":
            assert t["seed"]["partition"] == "development"
            assert t["state"] == (
                f"initial-p{t['player']}"
                if t["variant"] == "original"
                else f"fit-p{t['player']}-r{cfg['rounds']:02d}"
            )


@pytest.mark.parametrize(
    "field,value",
    [
        ("rounds", 1000),
        ("batch_games", 1),
        ("checkpoint_selection", "best_development"),
        ("episode_wall_seconds", 9999),
        ("evaluation_behavior", "different_rules_for_each_variant"),
    ],
)
def test_unbounded_or_selected_recipes_are_rejected(field: str, value: Any) -> None:
    cfg = config()
    cfg[field] = value
    with pytest.raises(ValueError):
        validate(cfg)


def manifest(path: Path, seeds: list[dict[str, Any]]) -> str:
    body = {
        "schema_version": "native-policy-update-seeds-v1",
        "environment_id": "env",
        "seeds": seeds,
    }
    sid = manifest_identifier(body)
    path.write_text(json.dumps({**body, "manifest_id": sid}))
    return sid


@pytest.mark.parametrize(
    "fault",
    [
        "none",
        "duplicate_id",
        "duplicate_world",
        "noncanonical",
        "wrong_partition",
        "historical_alias",
    ],
)
def test_seed_ownership_and_canonical_historical_aliases(tmp_path: Path, fault: str) -> None:
    cfg = config()
    seeds = worlds()
    old = [{"id": 1000, "seed": "DIFFERENT", "partition": "train"}]
    if fault == "duplicate_id":
        seeds[1]["id"] = seeds[0]["id"]
    if fault == "duplicate_world":
        seeds[1]["seed"] = seeds[0]["seed"]
    if fault == "noncanonical":
        seeds[0]["seed"] = "SPIRESHIFTPG0000"
    if fault == "wrong_partition":
        seeds[0]["partition"] = "development"
    if fault == "historical_alias":
        old[0]["seed"] = seeds[0]["seed"].replace("1", "I")
    cfg["seed_manifest"] = {"path": "new.json", "id": manifest(tmp_path / "new.json", seeds)}
    cfg["freshness_exclusions"] = [{"path": "old.json", "id": manifest(tmp_path / "old.json", old)}]
    if fault == "none":
        result, sources = seed_inputs(tmp_path, cfg, "env")
        assert result == seeds and len(sources) == 2
    else:
        with pytest.raises(ValueError):
            seed_inputs(tmp_path, cfg, "env")


def test_fit_request_seals_behavior_state_and_exact_training_collections() -> None:
    task = next(t for t in plan(config(), worlds()) if t["kind"] == "fit")
    done = {
        task["state"]: {"state_id": "original-full-state"},
        task["collections"][0]: {"collection_id": "first-sealed-collection"},
    }
    a = request(task, done)
    changed = copy.deepcopy(done)
    changed[task["state"]]["state_id"] = "other-state"
    assert a != request(task, changed)
    changed = copy.deepcopy(done)
    changed[task["collections"][0]]["collection_id"] = "other-games"
    assert a != request(task, changed)


def test_failed_evaluation_counts_in_original_denominator_and_zero_wins_are_not_proof() -> None:
    cfg, seeds = config(), worlds()
    done = {}
    for t in plan(cfg, seeds):
        if t["kind"] != "evaluate":
            continue
        failed = t["player"] == 2 and t["variant"] == "ppo"
        done[t["key"]] = {
            "kind": "evaluate",
            "player": t["player"],
            "variant": t["variant"],
            "seed_id": t["seed"]["id"],
            "status": "failed" if failed else "terminal",
            "victory": False,
            "maximum_floor": 99 if failed else 10,
            "completed_acts": 0,
            "training_return": 1 if failed else 0.01,
        }
    result = summary(cfg, seeds, done)
    p2 = result["players"][0]
    assert p2["arms"]["ppo"]["denominator"] == 1 and p2["arms"]["ppo"]["mean_floor"] == 0
    assert p2["ppo_minus_original"]["maximum_floor"]["mean"] == -10
    assert result["pooled_ppo_minus_original"]["maximum_floor"]["mean"] == -5
    assert result["zero_observed_wins_do_not_establish_zero_true_win_probability"]
    assert not result["checkpoint_promoted"]
