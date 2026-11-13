from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_structured_comparison import run
from spireshift.native_structured_inputs import validate
from spireshift.native_structured_model import ARMS
from spireshift.native_structured_plan import plan, request, summarize


def config(control: bool = True) -> dict[str, Any]:
    return {
        "schema_version": "native-structured-input-comparison-config-v1",
        "stage": "short_control" if control else "bounded_representation_comparison",
        "arms": list(ARMS),
        "rounds": 1 if control else 2,
        "batch_games": 2 if control else 32,
        "chunk_games": 2 if control else 8,
        "evaluation_worlds": 1 if control else 32,
        "episode_wall_seconds": 120,
        "workspace": "artifacts/trial",
        "players": [],
        "session_limits": {
            "wall_seconds": 240 if control else 900,
            "cpu_seconds": 480 if control else 1800,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 1000000000 if control else 4000000000,
        },
    }


def seeds(control: bool = True) -> list[dict[str, Any]]:
    c = config(control)
    count = c["rounds"] * c["batch_games"]
    return [
        {"id": i, "seed": f"CAN0N1CAL{i}", "partition": "train" if i < count else "development"}
        for i in range(count + c["evaluation_worlds"])
    ]


@pytest.mark.parametrize("control,total,fits", [(True, 20, 6), (False, 640, 12)])
def test_three_arm_schedule_freezes_every_final_before_fresh_full_game_evaluation(
    control: bool, total: int, fits: int
) -> None:
    cfg = config(control)
    validate(cfg)
    tasks = plan(cfg, seeds(control))
    assert len({t["key"] for t in tasks}) == len(tasks)
    assert (
        sum(len(t["seeds"]) if t["kind"] == "collect" else t["kind"] == "evaluate" for t in tasks)
        == total
    )
    assert sum(t["kind"] == "fit" for t in tasks) == fits
    first = next(i for i, t in enumerate(tasks) if t["kind"] == "evaluate")
    assert all(t["kind"] == "evaluate" for t in tasks[first:])
    for task in tasks:
        if task["kind"] == "evaluate":
            assert task["seed"]["partition"] == "development"
        if task["kind"] in {"collect", "fit"}:
            assert all(s["partition"] == "train" for s in task["seeds"])


def fixture(root: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, dict[str, int]]:
    from test_native_action_context import score

    import spireshift.native_structured_comparison as m

    cfg = config()
    original = root / "original.txt"
    original.write_text("Original weights and all Adam moments")
    ctx = {
        "config": cfg,
        "seeds": seeds(),
        "score": score(),
        "layout": {"vocabulary_id": "frozen"},
        "sources": {"original.txt": _sha_file(original)},
    }
    monkeypatch.setattr(m, "load", lambda *a, **kw: ctx)
    monkeypatch.setattr(m, "launch", lambda *a: (None, {}))
    monkeypatch.setattr(m, "_running_games", lambda: [])
    calls = {"games": 0, "fits": 0, "imports": 0, "checks": 0}

    def execute(
        root: Path, ctx: Any, store: ChunkJournal, task: Any, req: Any, done: Any, *_: Any
    ) -> None:
        target = store.begin(task["key"], req)
        result = {"kind": task["kind"], "games_recorded": 0}
        if task["kind"] == "qualify":
            result["passed"] = True
            calls["checks"] += 1
        else:
            result.update(player=task["player"], arm=task["arm"])
            if task["kind"] in {"import", "fit"}:
                fit = task["kind"] == "fit"
                calls["fits" if fit else "imports"] += 1
                steps = done[task["state"]]["optimizer_steps"] + 2 if fit else 100 + task["player"]
                state = {"player": task["player"], "weights": "retained", "Adam": steps}
                atomic_json(target / "state.json", state)
                result.update(
                    state_id=manifest_identifier(state),
                    state_path=str((target / "state.json").relative_to(root)),
                    optimizer_steps=steps,
                    new_optimizer_steps=2 if fit else 0,
                )
                if fit:
                    result["round"] = task["round"]
            elif task["kind"] == "collect":
                calls["games"] += len(task["seeds"])
                result.update(
                    round=task["round"],
                    paths=[],
                    failed_games=0,
                    games_recorded=len(task["seeds"]),
                    collection_id=manifest_identifier(task),
                )
            else:
                calls["games"] += 1
                result.update(
                    seed_id=task["seed"]["id"],
                    status="terminal",
                    victory=False,
                    completed_acts=0,
                    maximum_floor=8,
                    training_return=0.01,
                    cpu_seconds=0.2,
                    games_recorded=1,
                )
        atomic_json(target / "numeric.json", result)
        store.commit(task["key"], req, result)

    monkeypatch.setattr(m, "execute", execute)
    return root / "recipe.json", calls


def test_saved_chunks_resume_without_resetting_weights_moments_or_replaying_games(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, calls = fixture(tmp_path, monkeypatch)
    first = run(tmp_path, path, max_units=8)
    assert first["games_recorded"] == 2 and first["completed_units"] == 8
    result = run(tmp_path, path)
    assert (
        result["status"] == "native_structured_control_complete" and result["games_recorded"] == 20
    )
    assert calls == {"games": 20, "fits": 6, "imports": 6, "checks": 1}
    assert result["optimizer_steps_this_experiment"] == 12
    assert len(result["final_states"]) == 6
    assert run(tmp_path, path) == result and calls["games"] == 20


def test_status_and_offline_checks_do_not_collect_or_fit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, calls = fixture(tmp_path, monkeypatch)
    assert run(tmp_path, path, status_only=True)["games_launched"] == 0
    assert not (tmp_path / "artifacts/trial").exists()
    assert run(tmp_path, path, offline_only=True)["completed_units"] == 7
    assert calls == {"games": 0, "fits": 0, "imports": 6, "checks": 1}


def test_uncertain_unit_is_preserved_and_not_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, calls = fixture(tmp_path, monkeypatch)
    run(tmp_path, path, offline_only=True)
    store = ChunkJournal(tmp_path, config())
    done: dict[str, dict[str, Any]] = {}
    schedule = plan(config(), seeds())
    for task in schedule[:7]:
        receipt = store.completed(task["key"], request(task, done))
        assert receipt is not None
        done[task["key"]] = receipt["result"]
    with store.lock():
        target = store.begin(schedule[7]["key"], request(schedule[7], done))
        (target / "uncertain.txt").write_text("Do not repeat this native delivery")
    with pytest.raises(FileExistsError, match="uncommitted"):
        run(tmp_path, path)
    assert calls["games"] == 0 and (target / "uncertain.txt").exists()


def test_altered_completed_state_stops_instead_of_refitting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, calls = fixture(tmp_path, monkeypatch)
    result = run(tmp_path, path)
    (tmp_path / result["final_states"][0]["state_path"]).write_text("Changed optimizer")
    with pytest.raises(ValueError):
        run(tmp_path, path)
    assert calls["fits"] == 6 and calls["games"] == 20


def test_primary_comparison_is_named_vs_equal_capacity_and_failures_keep_denominator() -> None:
    cfg, worlds = config(), seeds()
    task = [t for t in plan(cfg, worlds) if t["kind"] == "evaluate"]
    done = {
        t["key"]: {
            "kind": "evaluate",
            "player": t["player"],
            "arm": t["arm"],
            "seed_id": t["seed"]["id"],
            "status": "failed" if t["arm"] == "named" else "terminal",
            "maximum_floor": 100,
            "completed_acts": 0,
            "training_return": 0.2,
            "victory": True,
            "cpu_seconds": 1.0,
        }
        for t in task
    }
    result = summarize(cfg, worlds, done)
    assert result["primary_comparison"] == "named_minus_hashed"
    assert (
        result["pooled_paired_comparisons"]["named_minus_hashed"]["maximum_floor"]["mean"] == -100
    )
    assert all(p["arms"]["named"]["failed_games"] == 1 for p in result["players"])
