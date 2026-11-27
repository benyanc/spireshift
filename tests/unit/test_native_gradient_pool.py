from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_engine_neural import model
from test_native_gradient_checks import case
from test_native_value_credit import score

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _sha_file
from spireshift.native_gradient_pool import POOL_SOURCES, collect, require_pool_seeds


@pytest.mark.parametrize(
    "bad", ["reserved", "duplicate", "missing", "wrong_count", "native_duplicate"]
)
def test_frozen_pool_uses_distinct_declared_control_or_train_games(bad: str) -> None:
    d: dict[str, Any] = {
        "stage": "short_collection_control",
        "seed_ids": [1, 2, 3, 4],
        "environment_manifest": {"id": "env"},
    }
    seeds: dict[str, Any] = {
        "environment_id": "env",
        "seeds": [{"id": i, "partition": "control", "seed": str(i)} for i in range(1, 5)],
    }
    require_pool_seeds(d, seeds)
    if bad == "reserved":
        seeds["seeds"][0]["partition"] = "development"
    elif bad == "duplicate":
        d["seed_ids"][0] = 2
    elif bad == "missing":
        seeds["seeds"].pop()
    elif bad == "wrong_count":
        d["seed_ids"].pop()
    else:
        seeds["seeds"][0]["seed"] = "2"
    with pytest.raises(ValueError):
        require_pool_seeds(d, seeds)


@pytest.mark.parametrize("failure", [None, "failed_game", "uncertain_worker"])
def test_frozen_collection_never_updates_weights_retries_failed_seed_or_resets_uncertain_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str | None
) -> None:
    import spireshift.native_gradient_pool as module

    m = model()
    d: dict[str, Any] = {
        "workspace": "artifacts/pool",
        "stage": "short_collection_control",
        "workers": 2,
        "seed_ids": [1, 2, 3, 4],
        "worker_script": "engine-native-worker-v9.mjs",
        "helpers_sha256": {},
        "training_spec": {"path": "unused", "id": score().spec_id},
        "environment_manifest": {"id": m.actor.environment_id},
        "seed_manifest": {"path": "seeds.json", "id": "unused"},
        "source_model": {"path": "player.json", "id": m.model_id},
        "learning": {"sampling_seed": 7, "ppo": {"temperature": 0.8}},
        "evaluation_policy": {
            "behavior": "sampled_softmax",
            "temperature": 0.8,
            "sampling_seed": 7,
            "coupling": "same_run_seed_across_checkpoints",
        },
        "resource_limits": {"wall_seconds": 100},
        "maximum_decisions": 4096,
        "episode_wall_seconds": 60,
    }
    (tmp_path / "player.json").write_text(json.dumps(m.as_dict()))
    seeds = {"seeds": [{"id": i, "seed": str(i), "partition": "control"} for i in range(1, 5)]}
    (tmp_path / "seeds.json").write_text(
        json.dumps({**seeds, "manifest_id": manifest_identifier(seeds)})
    )
    for n in POOL_SOURCES:
        p = tmp_path / "src/spireshift" / n
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("synthetic pinned source")
    node = tmp_path / "node"
    node.touch()
    attempts: list[str] = []
    workers: list[Any] = []

    class Worker:
        def __init__(self, q: Any, inputs: Any, workspace: Path, *args: Any, **kwargs: Any):
            self.workspace, self.closed, self.retired = workspace, False, False
            self.workspace.mkdir()
            workers.append(self)

        def episode(self, seed: str, **kwargs: Any) -> dict[str, Any]:
            attempts.append(seed)
            if seed == "1" and failure == "uncertain_worker":
                raise TimeoutError("Uncertain native action")
            c = case(int(seed))
            c["seed"] = seed
            if seed == "1" and failure == "failed_game":
                c.update(status="failed", error="Preserved failure")
            return c

        def close(self) -> None:
            self.closed = True

        def stop(self) -> None:
            self.closed = True

        def retire(self, error: str) -> None:
            self.closed = self.retired = True

    monkeypatch.setattr(module, "_require_native_launch_support", lambda: None)
    monkeypatch.setattr(module, "_running_games", lambda: False)
    monkeypatch.setattr(module, "load_pool", lambda q, path: (d, m))
    monkeypatch.setattr(module, "launch_inputs", lambda q, cfg: {})
    monkeypatch.setattr(module, "load_training_score_spec", lambda p: score())
    monkeypatch.setattr(module, "_shared_snapshot", lambda p: {})
    monkeypatch.setattr(module, "immutable_checks", lambda q, inputs: {"candidate_unchanged": True})
    monkeypatch.setattr(module, "EngineWorker", Worker)
    monkeypatch.setattr(
        module, "audit_worker_experience", lambda p, cases: {"valid": True, "games": len(cases)}
    )
    before = m.as_dict()
    result = collect(SimpleNamespace(root=tmp_path), tmp_path / "config", node)  # type: ignore[arg-type]
    assert result["optimizer_steps"] == 0 and not result["checkpoint_promoted"]
    assert result["game_apps_created"] == 0 and result["checks"]["source_player_unchanged"]
    assert all(w.closed for w in workers) and m.as_dict() == before
    assert attempts.count("1") == 1
    if failure is None:
        assert result["status"] == "frozen_collection_complete" and result["completed_games"] == 4
    elif failure == "failed_game":
        assert result["status"] == "frozen_collection_incomplete" and result["failed_games"] == 1
        assert result["not_attempted_games"] == 0 and any(w.retired for w in workers)
        assert "3" in attempts
    else:
        assert result["worker_failures"] == 1 and result["not_attempted_games"] == 2
        assert "3" not in attempts


def test_large_analysis_retains_sparse_reference_menus_for_only_four_games(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import spireshift.native_gradient_pool as module

    m, output = model(), tmp_path / "artifacts/pool"
    (output / "frozen-pool").mkdir(parents=True)
    (output / "source-at-launch").mkdir()
    digests = {}
    for name in POOL_SOURCES:
        path = output / "source-at-launch" / name
        path.write_text("synthetic collection source")
        digests[name] = _sha_file(path)
    d: dict[str, Any] = {
        "workspace": "artifacts/pool",
        "stage": "frozen_train_pool",
        "workers": 2,
        "seed_ids": list(range(256)),
        "implementation_sha256": digests,
        "analysis_limits": {"wall_seconds": 60},
        "training_spec": {"path": "score.json"},
        "source_model": {"path": "player.json"},
        "seed_manifest": {"path": "seeds.json"},
        "learning": {"ppo": {"temperature": 0.8, "entropy_coefficient": 0.01}},
        "batch_sizes": [4, 8, 16, 32, 64, 128],
        "partitions": 32,
        "partition_salt": 17,
    }
    summary = {
        "config_id": manifest_identifier(d),
        "status": "frozen_collection_complete",
        "completed_games": 256,
        "checks": {"unchanged": True},
    }
    (output / "summary.json").write_text(
        json.dumps({**summary, "report_id": manifest_identifier(summary)})
    )
    seeds = {"seeds": [{"id": i, "partition": "train"} for i in range(256)]}
    (tmp_path / "seeds.json").write_text(
        json.dumps({**seeds, "manifest_id": manifest_identifier(seeds)})
    )
    for name in ("score.json", "player.json", "config.json"):
        (tmp_path / name).write_text("synthetic source")
    for seed in d["seed_ids"]:
        (output / "frozen-pool" / f"case-{seed}.json").write_text('{"binding": {}}')
    monkeypatch.setattr(module, "load_pool", lambda q, p: (d, m))
    monkeypatch.setattr(module, "load_training_score_spec", lambda p: score())
    monkeypatch.setattr(module, "_case", lambda *args: {})
    monkeypatch.setattr(module, "_worker_audits", lambda *args: None)
    monkeypatch.setattr(module, "read_native_episode", lambda *args: {})
    monkeypatch.setattr(
        module,
        "game_gradient",
        lambda *args: (SimpleNamespace(run=SimpleNamespace(choices=(2,))), [object()]),
    )

    def reference(
        model: Any, games: list[Any], samples: list[Any], settings: Any
    ) -> dict[str, Any]:
        assert len(games) == len(samples) == 4
        return {"passed": True}

    def curves(games: list[Any], *args: Any) -> dict[str, Any]:
        assert len(games) == 256
        return {"available_independent_games": len(games)}

    monkeypatch.setattr(module, "production_gradient_check", reference)
    monkeypatch.setattr(module, "batch_size_checks", curves)
    result = module.analyze(SimpleNamespace(root=tmp_path), tmp_path / "config.json")  # type: ignore[arg-type]
    assert result["available_independent_games"] == 256
    assert result["production_reference"]["checked_games"] == 4
    assert result["production_reference"]["covers_entire_pool"] is False
