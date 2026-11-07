from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_native_action_context import score
from test_native_shop_continuation import recipe as old_recipe
from test_native_shop_continuation import setup as old_setup

import spireshift.native_runtime_continuation as continuation
import spireshift.native_runtime_execute as execute
import spireshift.native_shop_execute as old_execute
from spireshift.native_context_journal import load_state
from spireshift.native_runtime_plan import STOP_RULE, training_plan, validate


def recipe(short: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    cfg, _ = old_recipe(short)
    cfg.update(
        schema_version="native-runtime-continuation-config-v1",
        stage="short_bridge_control" if short else "bounded_runtime_continuation",
        starting_round=48,
        starting_training_games=1536,
        additional_games_per_player=2 if short else 256,
        milestones=[1538] if short else [1664, 1792],
        stopping_rule=STOP_RULE,
        invocation_wall_seconds=240 if short else 7200,
    )
    rows: list[dict[str, Any]] = []
    for n in (2, 3):
        for part, count in [
            ("control" if short else "train", cfg["additional_games_per_player"]),
            ("control_eval" if short else "development", cfg["evaluation_games"]),
            ("holdout", cfg["holdout_games"]),
        ]:
            for i in range(count):
                rows.append(
                    {
                        "id": 1500000 + len(rows),
                        "seed": f"RUNTIME{n}{part}{i}",
                        "partition": part,
                        "numerical_seed": n,
                    }
                )
    return cfg, {"seeds": rows}


def test_plan_preserves_absolute_schedule_and_uses_fresh_holdout_after_stopping() -> None:
    cfg, seeds = recipe()
    validate(cfg, seeds)
    tasks = continuation.maximum_plan(cfg, seeds)
    assert sum(len(t.get("seeds", [])) for t in tasks) == 960
    for n in (2, 3):
        fits = [t for t in tasks if t["kind"] == "fit" and t["numerical_seed"] == n]
        assert [t["round"] for t in fits] == list(range(49, 57))
        assert fits[0]["state"] == f"seed-{n}-restore"
        assert fits[-1]["milestone"] == 1792
    train = {s["id"] for t in tasks if t.get("training") for s in t["seeds"]}
    evaluations = {
        s["id"]
        for t in tasks
        if t.get("kind") == "collect" and not t["training"]
        for s in t["seeds"]
    }
    assert len(train) == 512 and not train & evaluations
    assert not any("holdout" in str(t) for t in training_plan(cfg, seeds))


@pytest.mark.parametrize(
    "key,value",
    [
        ("starting_round", 0),
        ("starting_training_games", 1120),
        ("additional_games_per_player", 1000000),
        ("checkpoint_selection", "best_seen"),
    ],
)
def test_plan_refuses_reset_or_expansion(key: str, value: Any) -> None:
    cfg, seeds = recipe()
    cfg[key] = value
    with pytest.raises(ValueError):
        validate(cfg, seeds)


def test_short_control_keeps_full_Adam_and_never_repeats_fits_or_games(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    q, old, parent, _, path, node, launched = old_setup(tmp_path, monkeypatch)
    cfg, seeds = recipe(True)
    cfg["players"] = old["players"]
    cfg["seed_manifest"] = old["seed_manifest"]
    path.write_text(json.dumps(cfg))
    sources = {r["path"]: r["sha256"] for r in cfg["players"]}
    monkeypatch.setattr(
        continuation, "load_continuation", lambda *_: (cfg, parent, seeds, dict(sources))
    )
    monkeypatch.setattr(continuation, "load_training_score_spec", lambda *_: score())
    for name in (
        "_require_native_launch_support",
        "_running_games",
        "_shared_snapshot",
        "immutable_checks",
        "collect_panel",
    ):
        monkeypatch.setattr(execute, name, getattr(old_execute, name))
    monkeypatch.setattr(execute, "launch_inputs", lambda *_: {})
    protected = {r["path"]: (q.root / r["path"]).read_bytes() for r in cfg["players"]}
    first = continuation.session(q, path, node, maximum_steps=6)
    assert first["fit_rounds"] == [49]
    fit = q.root / cfg["workspace"] / "chunks/seed-2-round-049-fit/state.json"
    _, adam, _ = load_state(fit)
    assert adam.steps > 3216 and any(adam.first)
    saved = fit.read_bytes()
    final = continuation.session(q, path, node)
    assert final["status"] == continuation.CONTROL and final["games_recorded"] == 12
    assert final["fit_rounds"] == [49, 49]
    assert final["ending_optimizer_steps"]["3"] > 3261
    assert continuation.session(q, path, node, status_only=True) == final
    assert len(launched) == 12 and fit.read_bytes() == saved
    assert all((q.root / p).read_bytes() == data for p, data in protected.items())
