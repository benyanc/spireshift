from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from test_native_action_context import model, score

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_ppo_math import Adam
from spireshift.native_context_cache import cached_model
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_experience_comparison import run
from spireshift.native_experience_inputs import ARMS, migrate
from spireshift.native_experience_plan import plan, request, summarize
from spireshift.native_structured_state import load, save


def config(control: bool = True) -> dict[str, Any]:
    return {
        "stage": "short_control" if control else "bounded_experience_comparison",
        "arms": list(ARMS),
        "rounds": 1 if control else 2,
        "batch_sizes": dict(zip(ARMS, (2, 4) if control else (32, 128), strict=True)),
        "chunk_games": 2 if control else 8,
        "evaluation_worlds": 1 if control else 32,
        "episode_wall_seconds": 120,
        "workspace": "artifacts/experience-test",
        "session_limits": {"wall_seconds": 240 if control else 900},
    }


def seeds(control: bool = True) -> list[dict[str, Any]]:
    c = config(control)
    count = c["rounds"] * c["batch_sizes"][ARMS[1]]
    return [
        {"id": i, "seed": f"CAN0N1CAL{i}", "partition": "train" if i < count else "development"}
        for i in range(count + c["evaluation_worlds"])
    ]


@pytest.mark.parametrize("control,total,fits", [(True, 18, 4), (False, 832, 8)])
def test_fresh_nested_whole_game_pools_and_all_finals_before_evaluation(
    control: bool, total: int, fits: int
) -> None:
    tasks = plan(config(control), seeds(control))
    assert len({t["key"] for t in tasks}) == len(tasks)
    assert (
        sum(len(t["seeds"]) if t["kind"] == "collect" else t["kind"] == "evaluate" for t in tasks)
        == total
    )
    assert sum(t["kind"] == "fit" for t in tasks) == fits
    first = next(i for i, t in enumerate(tasks) if t["kind"] == "evaluate")
    assert all(t["kind"] == "evaluate" for t in tasks[first:])
    for p in (2, 3):
        for index in range(1, config(control)["rounds"] + 1):
            fits_for_round = {
                t["arm"]: {s["id"] for s in t["seeds"]}
                for t in tasks
                if t["kind"] == "fit" and t["player"] == p and t["round"] == index
            }
            assert fits_for_round[ARMS[0]] < fits_for_round[ARMS[1]]
    development = {s["id"] for s in seeds(control) if s["partition"] == "development"}
    assert not development & {s["id"] for t in tasks if t["kind"] == "collect" for s in t["seeds"]}


def test_observation_identity_migration_keeps_every_weight_and_warm_Adam_exact(
    tmp_path: Path,
) -> None:
    parent = cached_model(model())
    adam = Adam(5658, (0.1,) * parent.parameter_count, (0.2,) * parent.parameter_count)
    before = parent.as_dict(), adam.as_dict()
    fork = migrate(parent, "sha256:" + "a" * 64)
    assert fork.weights() == parent.weights() and fork.model_id != parent.model_id
    save(tmp_path / "state.json", fork, adam)
    restored, optimizer, _ = load(tmp_path / "state.json")
    assert restored.weights() == parent.weights() and optimizer == adam
    assert optimizer.steps == 5658 and (parent.as_dict(), adam.as_dict()) == before
    with pytest.raises(FileExistsError):
        save(tmp_path / "state.json", fork, adam)


def fixture(root: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, dict[str, int]]:
    import spireshift.native_experience_comparison as m

    original = root / "original.txt"
    original.write_text("Original weights and all Adam moments")
    context = {
        "config": config(),
        "seeds": seeds(),
        "score": score(),
        "sources": {"original.txt": _sha_file(original)},
    }
    monkeypatch.setattr(m, "load", lambda *a, **kw: context)
    monkeypatch.setattr(m, "launch", lambda *a: (None, {}))
    monkeypatch.setattr(m, "_running_games", lambda: [])
    calls = {"games": 0, "fits": 0, "imports": 0, "checks": 0}

    def execute(
        root: Path, ctx: Any, journal: ChunkJournal, task: Any, req: Any, done: Any, *_: Any
    ) -> None:
        target = journal.begin(task["key"], req)
        r = {"kind": task["kind"], "games_recorded": 0}
        if task["kind"] == "qualify":
            r["passed"] = True
            calls["checks"] += 1
        else:
            r.update(player=task["player"], arm=task["arm"])
            if task["kind"] in {"import", "fit"}:
                fit = task["kind"] == "fit"
                calls["fits" if fit else "imports"] += 1
                steps = done[task["state"]]["optimizer_steps"] + 2 if fit else 5658
                state = {"weights": "exact", "Adam": steps}
                atomic_json(target / "state.json", state)
                r.update(
                    state_id=manifest_identifier(state),
                    state_path=str((target / "state.json").relative_to(root)),
                    optimizer_steps=steps,
                    new_optimizer_steps=2 if fit else 0,
                )
                if fit:
                    r["round"] = task["round"]
            elif task["kind"] == "collect":
                calls["games"] += len(task["seeds"])
                r.update(
                    round=task["round"],
                    failed_games=0,
                    games_recorded=len(task["seeds"]),
                    collection_id=manifest_identifier(task),
                )
            else:
                calls["games"] += 1
                r.update(
                    seed_id=task["seed"]["id"],
                    status="terminal",
                    victory=False,
                    completed_acts=0,
                    maximum_floor=8,
                    training_return=0.01,
                    games_recorded=1,
                )
        atomic_json(target / "result.json", r)
        journal.commit(task["key"], req, r)

    monkeypatch.setattr(m, "execute", execute)
    return root / "recipe.json", calls


def test_short_chunks_resume_full_state_without_replaying_games_or_imports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, calls = fixture(tmp_path, monkeypatch)
    assert run(tmp_path, path, offline_only=True)["completed_units"] == 3
    first = run(tmp_path, path, max_units=2)
    assert first["new_units_this_session"] == 2
    result = run(tmp_path, path)
    assert (
        result["status"] == "native_experience_control_complete" and result["games_recorded"] == 18
    )
    assert calls == {"games": 18, "fits": 4, "imports": 2, "checks": 1}
    assert result["optimizer_steps_this_experiment"] == 8
    assert run(tmp_path, path) == result and calls["games"] == 18


def test_uncertain_unit_is_preserved_and_not_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, calls = fixture(tmp_path, monkeypatch)
    run(tmp_path, path, offline_only=True)
    journal = ChunkJournal(tmp_path, config())
    done: dict[str, dict[str, Any]] = {}
    schedule = plan(config(), seeds())
    for task in schedule[:3]:
        receipt = journal.completed(task["key"], request(task, done))
        assert receipt is not None
        done[task["key"]] = receipt["result"]
    with journal.lock():
        folder = journal.begin(schedule[3]["key"], request(schedule[3], done))
        (folder / "uncertain.txt").write_text("Do not repeat this delivery")
    with pytest.raises(FileExistsError, match="uncommitted"):
        run(tmp_path, path)
    assert calls["games"] == 0 and (folder / "uncertain.txt").exists()


def test_changed_saved_Adam_stops_before_any_new_collection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, calls = fixture(tmp_path, monkeypatch)
    r = run(tmp_path, path)
    (tmp_path / r["final_states"][0]["state_path"]).write_text("Changed optimizer")
    with pytest.raises(ValueError):
        run(tmp_path, path)
    assert calls["games"] == 18 and calls["fits"] == 4


def test_failures_keep_the_original_evaluation_denominator() -> None:
    cfg, worlds = config(), seeds()
    tasks = [t for t in plan(cfg, worlds) if t["kind"] == "evaluate"]
    done = {
        t["key"]: {
            "kind": "evaluate",
            "player": t["player"],
            "arm": t["arm"],
            "seed_id": t["seed"]["id"],
            "status": "failed" if t["arm"] == ARMS[1] else "terminal",
            "victory": True,
            "maximum_floor": 100,
            "completed_acts": 3,
            "training_return": 1,
        }
        for t in tasks
    }
    r = summarize(cfg, worlds, done)
    assert r["pooled_paired_comparisons"]["batch128_minus_batch32"]["maximum_floor"]["mean"] == -100
    assert r["players"][0]["arms"][ARMS[1]]["denominator"] == 1
    assert r["players"][0]["arms"][ARMS[1]]["wins"] == 0
