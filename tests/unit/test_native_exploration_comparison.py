from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import pytest
from test_native_action_context import score
from test_native_context_trial import case
from test_native_exploration_plan import recipe
from test_native_rest_exploration import rest
from test_native_shop_continuation import setup as old_setup

import spireshift.native_exploration_comparison as comparison
import spireshift.native_exploration_execute as execute
from spireshift.engine_experience import save_native_episode
from spireshift.engine_experience_stream import compact_case
from spireshift.engine_learning import summarize
from spireshift.native_context_journal import load_state
from spireshift.native_rest_exploration import CONTRACT, choose
from spireshift.native_shop_policy import ShopNavigation


def test_full_nonzero_Adam_forks_and_restart_never_replay_games_or_reset_moments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    q, old, parent, _, path, node, launched = old_setup(tmp_path, monkeypatch)
    parent["training_spec"]["id"] = score().spec_id
    cfg, seeds = recipe(True)
    cfg.update(
        workspace="artifacts/rest-comparison-test",
        worker_helpers_sha256={},
        seed_manifest={"id": "manifest", "path": "unused"},
    )
    cfg["players"] = old["players"]
    for r in cfg["players"]:
        r["optimizer_steps"] = load_state(q.root / r["path"])[1].steps
    path.write_text(json.dumps(cfg))
    sources = {r["path"]: r["sha256"] for r in cfg["players"]}
    protected = {p: (q.root / p).read_bytes() for p in sources}
    monkeypatch.setattr(comparison, "load", lambda *_: (cfg, parent, seeds, dict(sources)))
    monkeypatch.setattr(comparison, "load_training_score_spec", lambda *_: score())
    monkeypatch.setattr(execute, "launch_inputs", lambda *_: {})
    monkeypatch.setattr(execute, "_running_games", lambda: [])
    monkeypatch.setattr(execute, "_shared_snapshot", lambda *_: {})
    monkeypatch.setattr(execute, "immutable_checks", lambda *_: {"unchanged": True})

    def collect(*args: Any) -> tuple[Any, ...]:
        rows, out, m, weight = args[4], args[6], args[7], args[13]
        out.mkdir()
        paths = []
        outcomes = []
        for seed in rows:
            launched.append((str(out), seed["id"]))
            p = rest()
            choice = choose(m, score(), p, ShopNavigation(), random.Random(seed["id"]), 0.8, weight)
            c = case(seed["seed"], lambda _, selected=choice: selected)
            c.update(decisions=[{"public_input": p, "choice": choice}], worker_workspace="fake")
            target = out / f"case-{seed['id']}.json"
            binding = {
                "partition": seed["partition"],
                "panel_purpose": "training" if args[11] else "frozen_policy_evaluation",
                "seed_id": seed["id"],
                "environment_id": m.actor.environment_id,
                "model_id": m.model_id,
                "training_spec_id": score().spec_id,
                "policy_contract": CONTRACT,
                "rest_uniform_weight": weight,
            }
            save_native_episode(target, c, binding)
            paths.append(target)
            outcomes.append({**compact_case(c), "seed_id": seed["id"], "training_return": 0.03})
        summary = {
            **summarize(
                [{**o, "decisions": range(o["decision_count"])} for o in outcomes], len(rows)
            ),
            "outcomes": outcomes,
            "rest_choices": {"Rest": len(rows)},
        }
        return paths, summary, {}

    monkeypatch.setattr(execute, "collect_panel", collect)
    assert comparison.session(q, path, node, status_only=True)["completed_units"] == 0
    assert not (q.root / cfg["workspace"]).exists()
    first = comparison.session(q, path, node, maximum_steps=6)
    assert first["games_recorded"] == 2 and first["fit_rounds"] == [
        {"player": 2, "arm": "standard", "round": 57}
    ]
    checkpoint = q.root / first["ending_states"]["2-standard"]["state_path"]
    data = checkpoint.read_bytes()
    final = comparison.session(q, path, node)
    assert final["status"] == comparison.CONTROL and final["games_recorded"] == 20
    assert len(launched) == 20 and checkpoint.read_bytes() == data
    for n in (2, 3):
        for arm in ("standard", "rest_mix20"):
            state = final["ending_states"][f"{n}-{arm}"]
            _, optimizer, _ = load_state(q.root / state["state_path"])
            assert optimizer.steps > cfg["players"][n - 2]["optimizer_steps"] and any(
                optimizer.first
            )
    assert all((q.root / p).read_bytes() == b for p, b in protected.items())
    assert comparison.session(q, path, node, status_only=True) == final
    assert comparison.session(q, path, node) == final and len(launched) == 20
    # A completed directory is sealed; unexpected files cannot be silently reused.
    checkpoint.with_name("unexpected.txt").write_text("tampered")
    with pytest.raises(ValueError, match="unexpected"):
        comparison.session(q, path, node, status_only=True)
