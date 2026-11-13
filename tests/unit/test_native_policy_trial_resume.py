from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_native_action_context import score
from test_native_policy_trial_plan import config, worlds

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_policy_trial import run
from spireshift.native_policy_trial_execute import training_paths
from spireshift.native_policy_trial_plan import plan, request


def fixture(root: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, dict[str, int]]:
    import spireshift.native_policy_trial as module

    cfg = {**config(), "workspace": "artifacts/control", "players": []}
    seeds = worlds()
    source = root / "originals.txt"
    source.write_text("Original weights and all optimizer moments")
    context = {
        "config": cfg,
        "seeds": seeds,
        "score": score(),
        "sources": {"originals.txt": _sha_file(source)},
    }
    monkeypatch.setattr(module, "load", lambda *_: context)
    monkeypatch.setattr(module, "launch", lambda *_: (None, {}))
    monkeypatch.setattr(module, "_running_games", lambda: [])
    calls = {"games": 0, "fits": 0, "imports": 0, "checks": 0}

    def execute(
        root: Path, ctx: Any, store: ChunkJournal, task: Any, req: Any, done: Any, *_: Any
    ) -> Any:
        target = store.begin(task["key"], req)
        kind = task["kind"]
        result: dict[str, Any] = {"kind": kind, "games_recorded": 0}
        if kind == "qualify":
            calls["checks"] += 1
            result["passed"] = True
        elif kind in {"import", "fit"}:
            calls["imports" if kind == "import" else "fits"] += 1
            steps = (
                100 + task["player"]
                if kind == "import"
                else done[task["state"]]["optimizer_steps"] + 2
            )
            state = {"steps": steps, "moments": "retained", "full_weights": task["player"]}
            atomic_json(target / "state.json", state)
            result.update(
                player=task["player"],
                state_path=str((target / "state.json").relative_to(root)),
                state_id=manifest_identifier(state),
                model_id="model",
                optimizer_steps=steps,
                new_optimizer_steps=2 if kind == "fit" else 0,
            )
        elif kind == "collect":
            calls["games"] += len(task["seeds"])
            result.update(
                player=task["player"],
                round=task["round"],
                paths=[],
                summary={"failed_games": 0},
                collection_id=manifest_identifier(task),
                games_recorded=len(task["seeds"]),
            )
        elif kind == "evaluate":
            calls["games"] += 1
            result.update(
                player=task["player"],
                variant=task["variant"],
                seed_id=task["seed"]["id"],
                status="terminal",
                victory=False,
                completed_acts=0,
                maximum_floor=8,
                training_return=0.01,
                games_recorded=1,
            )
        atomic_json(target / "numeric.json", result)
        store.commit(task["key"], req, result)
        return result

    monkeypatch.setattr(module, "execute", execute)
    return root / "recipe.json", calls


def test_clean_pause_reuses_qualification_exact_imports_collection_and_model_Adam_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, calls = fixture(tmp_path, monkeypatch)
    r = run(tmp_path, path, max_units=4)
    assert r["status"] == "paused_between_sealed_units" and calls["games"] == 2
    assert calls["checks"] == 1 and calls["imports"] == 2
    r = run(tmp_path, path)
    assert r["status"] == "native_policy_update_control_complete" and r["games_recorded"] == 8
    assert calls == {"games": 8, "fits": 2, "imports": 2, "checks": 1}
    assert r["optimizer_steps_this_experiment"] == 4
    assert {r["optimizer_steps"] for r in r["final_states"]} == {104, 105}
    assert run(tmp_path, path) == r
    assert calls["games"] == 8 and (tmp_path / "originals.txt").read_text().startswith("Original")


def test_offline_and_status_modes_launch_no_games_or_player_fits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, calls = fixture(tmp_path, monkeypatch)
    r = run(tmp_path, path, status_only=True)
    assert r["games_launched"] == 0 and not (tmp_path / "artifacts/control").exists()
    r = run(tmp_path, path, offline_only=True)
    assert r["completed_units"] == 3
    assert calls == {"games": 0, "fits": 0, "imports": 2, "checks": 1}


def test_uncertain_collection_is_preserved_and_never_automatically_replayed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, calls = fixture(tmp_path, monkeypatch)
    run(tmp_path, path, offline_only=True)
    store = ChunkJournal(tmp_path, {**config(), "workspace": "artifacts/control", "players": []})
    tasks = plan(store.recipe, worlds())
    done: dict[str, dict[str, Any]] = {}
    for task in tasks[:3]:
        receipt = store.completed(task["key"], request(task, done))
        assert receipt is not None
        done[task["key"]] = receipt["result"]
    task = tasks[3]
    with store.lock():
        directory = store.begin(task["key"], request(task, done))
        (directory / "unknown-delivery.txt").write_text("Do not replay this seed")
    with pytest.raises(FileExistsError, match="uncommitted"):
        run(tmp_path, path)
    assert calls["games"] == 0 and (directory / "unknown-delivery.txt").exists()


def test_changed_committed_state_stops_cached_results_without_refit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, calls = fixture(tmp_path, monkeypatch)
    r = run(tmp_path, path)
    state = tmp_path / r["final_states"][0]["state_path"]
    state.write_text("Changed optimizer state")
    with pytest.raises(ValueError):
        run(tmp_path, path)
    assert calls["games"] == 8 and calls["fits"] == 2


@pytest.mark.parametrize(
    "fault",
    [
        "none",
        "stale_model",
        "foreign_recipe",
        "greedy_eval",
        "development",
        "duplicate",
        "missing",
        "different_world",
        "teacher",
    ],
)
def test_training_only_accepts_its_fresh_sampled_complete_game_ownership(
    tmp_path: Path, fault: str
) -> None:
    cfg = {"seed_manifest": {"id": "fresh-seeds"}}
    paths = []
    for seed in (1, 2):
        bound = {
            "config_id": manifest_identifier(cfg),
            "partition": "train",
            "panel_purpose": "training",
            "model_id": "current",
            "seed_manifest_id": "fresh-seeds",
            "seed_id": seed,
            "native_seed": f"NATIVE{seed}",
        }
        body: dict[str, Any] = {"binding": bound, "episode": {}}
        if seed == 1:
            if fault == "stale_model":
                bound["model_id"] = "old"
            if fault == "foreign_recipe":
                bound["config_id"] = "other"
            if fault == "greedy_eval":
                bound["panel_purpose"] = "frozen_policy_evaluation"
            if fault == "development":
                bound["partition"] = "development"
            if fault == "different_world":
                bound["native_seed"] = "UNPLANNED"
            if fault == "teacher":
                body["episode"]["privileged_fixed_world_teacher"] = True
        path = tmp_path / f"{seed}.json"
        path.write_text(json.dumps(body))
        paths.append(path.name)
    if fault == "duplicate":
        paths[1] = paths[0]
    if fault == "missing":
        paths.pop()
    done = {"collect": {"paths": paths}}
    task = {"collections": ["collect"], "seed_ids": [1, 2], "native_seeds": ["NATIVE1", "NATIVE2"]}
    if fault == "none":
        assert training_paths(tmp_path, cfg, task, done, "current") == [tmp_path / p for p in paths]
    else:
        with pytest.raises(ValueError):
            training_paths(tmp_path, cfg, task, done, "current")
