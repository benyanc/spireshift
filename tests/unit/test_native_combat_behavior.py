from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_native_action_context import model, score

from spireshift import native_combat_behavior as module
from spireshift import native_combat_behavior_config as admission
from spireshift import native_combat_behavior_data as data
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_ppo_math import Adam
from spireshift.native_action_context import CROSSED, initialize
from spireshift.native_combat_behavior_policy import ARMS, CONTRACT, RNG
from spireshift.native_context_cache import cached_model
from spireshift.native_context_journal import save_state


def sealed(root: Path, name: str, body: dict[str, Any], key: str = "report_id") -> dict[str, str]:
    value = {**body, key: manifest_identifier(body)}
    atomic_json(root / name, value)
    return {"path": name, "id": value[key]}


def recipe(root: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[dict[str, Any], Path]:
    (root / "src/spireshift").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "src/spireshift/stub.py").write_text("source")
    (root / "scripts/stub.py").write_text("entry")
    monkeypatch.setattr(admission, "SOURCES", ("stub.py",))
    monkeypatch.setattr(admission, "ENTRIES", ("stub.py",))
    monkeypatch.setattr(admission, "worker_helpers", lambda *a: {"helper": "frozen"})
    spec = score()
    spec_path = (
        Path(__file__).resolve().parents[2]
        / "configs/training-objective/sts2-v0.111.0-ironclad-a8-native-bootstrap-v8.json"
    )
    (root / "score.json").write_bytes(spec_path.read_bytes())
    env = sealed(
        root,
        "environment.json",
        {"ascension": 8, "character": "Ironclad", "version": "v0.111.0", "commit": "41cef1ea"},
        "manifest_id",
    )
    players, original = [], []
    for n in (2, 3):
        m = initialize(env["id"], spec.spec_id, n, CROSSED)
        path = root / f"artifacts/player-{n}.json"
        save_state(path, cached_model(m), Adam.zero(m.parameter_count))
        d = json.loads(path.read_text())
        ref = {
            "numerical_seed": n,
            "path": str(path.relative_to(root)),
            "sha256": _sha_file(path),
            "state_id": d["state_id"],
            "model_id": m.model_id,
            "optimizer_steps": 0,
        }
        players.append(ref)
        original.append({**ref, "state_path": ref["path"]})
    corpus = sealed(
        root,
        "corpus.json",
        {
            "models": original,
            "environment_manifest": env,
            "training_spec": {"path": "score.json", "id": spec.spec_id},
        },
    )
    native = {
        "qualification": "native.json",
        "qualification_id": "qualified",
        "node": str(root / "node"),
        "native_inputs": {"path": "inputs.json", "id": "inputs"},
        "helpers_sha256": {"helper": "frozen"},
    }
    (root / "old-recipe.json").write_text(json.dumps(native))
    prior = sealed(
        root,
        "prior.json",
        {
            "recipe_path": "old-recipe.json",
            "sources": {},
            "status": "native_bounded_combat_comparison_complete",
            "failed_branches": 0,
            "skipped_branches": 0,
            "baseline_control_traces_match": True,
            "duplicate_selected_traces_match": True,
        },
    )
    fresh = sealed(
        root,
        "fresh.json",
        {
            "schema_version": "native-combat-behavior-seeds-v1",
            "environment_id": env["id"],
            "partition": "control",
            "seeds": [{"id": i, "seed": f"FRESH{i}"} for i in (10, 11)],
        },
        "manifest_id",
    )
    history = sealed(root, "history.json", {"seeds": [{"id": 1, "seed": "OLD"}]}, "manifest_id")
    cfg = {
        **native,
        "schema_version": "native-combat-behavior-config-v1",
        "stage": "short_control",
        "workspace": "artifacts/behavior",
        "policy_contract": CONTRACT,
        "rng_contract": RNG,
        "arms": list(ARMS),
        "temperature": 0.8,
        "information_scope": "current_public_state_only_no_search",
        "ordinary_PPO_eligible": False,
        "episode_wall_seconds": 120,
        "maximum_decisions": 4096,
        "implementation_sha256": {"stub.py": _sha_file(root / "src/spireshift/stub.py")},
        "entry_sha256": {"stub.py": _sha_file(root / "scripts/stub.py")},
        "session_limits": {
            "wall_seconds": 240,
            "cpu_seconds": 480,
            "resident_memory_bytes": 2000000000,
            "storage_bytes": 1000000000,
        },
        "qualified_native_control": prior,
        "players_source": corpus,
        "environment_manifest": env,
        "training_spec": {"path": "score.json", "id": spec.spec_id},
        "players": players,
        "seed_manifest": fresh,
        "historical_seed_manifests": [history],
        "excluded_seed_manifests": [],
    }
    path = root / "recipe.json"
    path.write_text(json.dumps(cfg))
    return cfg, path


def test_recipe_preserves_full_states_and_distinct_paired_seeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, path = recipe(tmp_path, monkeypatch)
    _, seeds, models, _, sources = admission.load(tmp_path, path)
    assert len(seeds) == 2 and set(models) == {2, 3}
    assert all(sources[p["path"]] == p["sha256"] for p in cfg["players"])


@pytest.mark.parametrize(
    "fault", ["source", "temperature", "scope", "rng", "budget", "state", "history", "seed"]
)
def test_recipe_refuses_drift_leakage_and_reused_seeds(
    fault: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, path = recipe(tmp_path, monkeypatch)
    if fault == "source":
        (tmp_path / "src/spireshift/stub.py").write_text("changed")
    elif fault == "state":
        (tmp_path / cfg["players"][0]["path"]).write_text("changed")
    elif fault == "temperature":
        cfg["temperature"] = 1.2
    elif fault == "scope":
        cfg["ordinary_PPO_eligible"] = True
    elif fault == "rng":
        cfg["rng_contract"] = "shared_combat_noncombat_stream"
    elif fault == "budget":
        cfg["session_limits"]["wall_seconds"] = 3600
    elif fault == "history":
        cfg["historical_seed_manifests"] = []
    else:
        fresh = json.loads((tmp_path / "fresh.json").read_text())
        fresh.pop("manifest_id")
        fresh["seeds"][0]["seed"] = "OLD"
        (tmp_path / "fresh.json").unlink()
        cfg["seed_manifest"] = sealed(tmp_path, "fresh.json", fresh, "manifest_id")
    path.write_text(json.dumps(cfg))
    with pytest.raises((ValueError, KeyError, json.JSONDecodeError)):
        admission.load(tmp_path, path)


def fake_native(
    root: Path, monkeypatch: pytest.MonkeyPatch, *, control: bool = True
) -> tuple[dict[str, Any], Path]:
    cfg: dict[str, Any] = {
        "stage": "short_control" if control else "fresh_game_comparison",
        "workspace": "artifacts/games",
        "node": str(root / "node"),
        "arms": list(ARMS),
        "qualification": "q.json",
        "qualification_id": "q",
        "native_inputs": {"path": "inputs.json", "id": manifest_identifier({})},
        "session_limits": {"wall_seconds": 240},
        "information_scope": "current_public_state_only_no_search",
        "players": [{"numerical_seed": n, "optimizer_steps": 123} for n in (2, 3)],
    }
    seeds = [{"id": i, "seed": f"FRESH{i}"} for i in (10, 11)]
    monkeypatch.setattr(
        module, "load", lambda *_: (cfg, seeds, {2: model(), 3: model()}, score(), {})
    )
    monkeypatch.setattr(module, "_running_games", lambda: [])
    monkeypatch.setattr(
        module, "load_engine_qualification_config", lambda *_: SimpleNamespace(config_id="q")
    )
    monkeypatch.setattr(
        module,
        "_run_inputs",
        lambda *_: {"recipe": {}, "objective": score().evaluation_objective.as_dict()},
    )
    monkeypatch.setattr(module, "immutable_checks", lambda *_: {"fixed": True})
    monkeypatch.setattr(module, "_shared_snapshot", lambda *_: {})
    monkeypatch.setattr(data, "RESAMPLES", 100)
    (root / "node").write_text("node")
    path = root / "recipe.json"
    path.write_text(json.dumps(cfg))

    def branch(
        _q: Any,
        _cfg: Any,
        _inputs: Any,
        target: Path,
        _node: Any,
        task: dict[str, Any],
        *_args: Any,
    ) -> dict[str, Any]:
        ref = sealed(
            root,
            str((target / "rng-receipt.json").relative_to(root)),
            {
                "noncombat": [
                    {
                        "draw_key": "shared",
                        "draw": 0.5,
                        "effective_input_id": "same",
                        "action_index": 0,
                        "policy_log_probability": 0.0,
                    }
                ]
            },
        )
        return {
            "status": "terminal",
            "victory": False,
            "maximum_floor": 10,
            "completed_acts": 0,
            "training_return": 0.1,
            "cpu_seconds": 1.0,
            "numerical_seed": task["numerical_seed"],
            "arm": task["arm"],
            "seed_id": task["seed"]["id"],
            "duplicate_of": task["duplicate_of"],
            "trace_id": f"{task['seed']['id']}-{task['numerical_seed']}-{task['arm']}",
            "rng_receipt_path": ref["path"],
            "rng_receipt_id": ref["id"],
            "native_audit_valid": True,
            "inference_audit_valid": True,
            "counts": {f"{task['arm']}_combat": 1},
        }

    monkeypatch.setattr(module, "branch", branch)
    return cfg, path


def test_status_and_cached_completion_cannot_start_a_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, path = fake_native(tmp_path, monkeypatch)
    monkeypatch.setattr(module, "_running_games", lambda: pytest.fail("No host for status"))
    assert (
        module.run(tmp_path, path, Path("unused"), status_only=True)["native_attempt_upper_bound"]
        == 12
    )
    assert not (tmp_path / cfg["workspace"]).exists()
    saved = {"status": module.COMPLETE, "config_id": manifest_identifier(cfg), "sources": {}}
    ref = sealed(tmp_path, cfg["workspace"] + "/report.json", saved)
    assert module.run(tmp_path, path, Path("unused"))["report_id"] == ref["id"]


def test_complete_controls_resume_without_replaying_games(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, path = fake_native(tmp_path, monkeypatch)
    first = module.run(tmp_path, path, Path(cfg["node"]))
    assert first["completed_units"] == 12 and first["duplicate_traces_match"]
    assert (
        first["summary"]["denominator"] == 8
        and first["noncombat_matching"]["shared_noncombat_draw_keys"] == 4
    )
    monkeypatch.setattr(module, "branch", lambda *_: pytest.fail("Saved games cannot replay"))
    assert module.run(tmp_path, path, Path("unused")) == first


def test_clean_pause_resumes_only_unfinished_cells(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, path = fake_native(tmp_path, monkeypatch)
    original: Callable[..., dict[str, Any]] = vars(module)["branch"]
    clock, calls = [0.0], [0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])

    def branch(*args: Any) -> dict[str, Any]:
        result = original(*args)
        calls[0] += 1
        if calls[0] == 1:
            clock[0] = 100.0
        return result

    monkeypatch.setattr(module, "branch", branch)
    first = module.run(tmp_path, path, Path(cfg["node"]))
    assert first["completed_units"] == 1 and first["status"] == "paused_between_committed_games"
    clock[0] = 0.0
    final = module.run(tmp_path, path, Path(cfg["node"]))
    assert (
        final["completed_units"] == 12 and final["new_games_this_session"] == 11 and calls[0] == 12
    )


def test_failed_game_is_counted_and_other_planned_games_continue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, path = fake_native(tmp_path, monkeypatch, control=False)
    original: Callable[..., dict[str, Any]] = vars(module)["branch"]

    def branch(*args: Any) -> dict[str, Any]:
        result = original(*args)
        if result["seed_id"] == 10 and result["numerical_seed"] == 2 and result["arm"] == "greedy":
            result.update(status="failed", maximum_floor=99, training_return=None)
        return result

    monkeypatch.setattr(module, "branch", branch)
    final = module.run(tmp_path, path, Path(cfg["node"]))
    assert final["completed_units"] == 8 and final["failed_games"] == 1
    assert final["summary"]["denominator"] == 8 and final["summary"]["failed_games"] == 1
    assert final["summary"]["players"][0]["arms"]["greedy"]["mean_floor"] == 5


def test_uncertain_uncommitted_game_is_preserved_and_never_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, path = fake_native(tmp_path, monkeypatch)
    target = tmp_path / cfg["workspace"] / "chunks/game-10-p2-sampled"
    target.mkdir(parents=True)
    (target / "active.json").write_text("uncertain")
    monkeypatch.setattr(module, "branch", lambda *_: pytest.fail("No uncertain replay"))
    with pytest.raises(FileExistsError, match="uncommitted"):
        module.run(tmp_path, path, Path(cfg["node"]))
    assert (target / "active.json").read_text() == "uncertain"
