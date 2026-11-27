from __future__ import annotations

import copy
import json
from pathlib import Path
from threading import Lock
from types import SimpleNamespace
from typing import Any, cast

import pytest
from test_engine_neural import model
from test_native_gradient_checks import case
from test_native_value_credit import score

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode
from spireshift.engine_learning import summarize
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.native_gradient_stream import (
    SOURCES,
    compact_summary,
    episode_recipe,
    load_stream,
    prepare_union,
)


def test_compact_summary_preserves_denominators_and_failures_without_trace_storage() -> None:
    cases = [case(1), case(2)]
    for i, row in enumerate(cases):
        row.update(worker_workspace="worker", seed=str(i))
    cases[1].update(status="failed", error="Preserved")
    from spireshift.engine_experience_stream import compact_case

    compact = [compact_case(c) for c in cases]
    assert compact_summary(compact, 4) == summarize(cases, 4)
    assert all("decisions" not in row for row in compact)
    assert all(row["decision_count"] > 0 for row in compact)


def test_completion_recipe_never_retries_interrupted_seed_and_preserves_source() -> None:
    cfg = {
        "workspace": "artifacts/recovery",
        "seed_manifest": {"path": "seeds"},
        "interrupted_seed_ids": [700253],
        "unstarted_seed_ids": [700255],
        "additional_seed_ids": [700257],
        "implementation_sha256": {},
        "collection_limits": {},
    }
    source = {"seed_ids": list(range(700001, 700257)), "worker_script": "unchanged"}
    old = copy.deepcopy(source)
    result = episode_recipe(cfg, source, "completion")
    assert result["seed_ids"] == [700255, 700257]
    assert 700253 not in result["seed_ids"] and source == old
    assert result["memory_policy"].startswith("sealed_paths")


@pytest.mark.parametrize("fault", [None, "uncertain"])
def test_collector_drops_each_trace_and_only_passes_paths_to_auditor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str | None
) -> None:
    import spireshift.native_gradient_stream as module

    m = model()
    cfg: dict[str, Any] = {
        "workspace": "artifacts/recovery",
        "collection_limits": {"wall_seconds": 120},
        "seed_manifest": {"path": "seeds.json", "id": "synthetic"},
    }
    source: dict[str, Any] = {
        "workers": 2,
        "worker_script": "engine-native-worker-v9.mjs",
        "helpers_sha256": {},
        "training_spec": {"path": "unused", "id": score().spec_id},
        "source_model": {"path": "player.json"},
        "maximum_decisions": 4096,
        "episode_wall_seconds": 60,
        "environment_manifest": {"id": m.actor.environment_id},
        "learning": {"sampling_seed": 7, "ppo": {"temperature": 0.8}},
    }
    recipe = {
        **source,
        "workspace": "artifacts/recovery/completion",
        "seed_manifest": cfg["seed_manifest"],
        "seed_ids": list(range(256)),
    }
    seeds = {"seeds": [{"id": i, "seed": str(i), "partition": "train"} for i in range(256)]}
    (tmp_path / "seeds.json").write_text(
        json.dumps({**seeds, "manifest_id": manifest_identifier(seeds)})
    )
    (tmp_path / "player.json").write_text(json.dumps(m.as_dict()))
    node = tmp_path / "node"
    node.touch()
    live = peak = 0
    attempts: list[str] = []
    audit_sizes = []
    mutex = Lock()

    class Counted(dict[str, Any]):
        def __init__(self, value: dict[str, Any]) -> None:
            nonlocal live, peak
            super().__init__(value)
            with mutex:
                live += 1
                peak = max(peak, live)

        def __del__(self) -> None:
            nonlocal live
            with mutex:
                live -= 1

    class Worker:
        def __init__(self, q: Any, inputs: Any, workspace: Path, *a: Any, **kw: Any) -> None:
            self.workspace, self.closed = workspace, False
            workspace.mkdir()

        def episode(self, seed: str, **kw: Any) -> dict[str, Any]:
            attempts.append(seed)
            if seed == "0" and fault == "uncertain":
                raise TimeoutError("Unknown delivery; no reset")
            c = case(int(seed))
            c["seed"] = seed
            return Counted(c)

        def close(self) -> None:
            self.closed = True

        def stop(self) -> None:
            self.closed = True

        def retire(self, reason: str) -> None:
            pytest.fail("No synthetic complete game should require retirement")

    def audit(workspace: Path, paths: list[Path], **kwargs: Any) -> dict[str, Any]:
        assert all(isinstance(p, Path) for p in paths)
        audit_sizes.append(len(paths))
        body = {"source_sha256": {}, "valid": True, "games": len(paths)}
        return {**body, "report_id": manifest_identifier(body)}

    monkeypatch.setattr(module, "load_stream", lambda *_: (cfg, source, m))
    monkeypatch.setattr(module, "episode_recipe", lambda *_: recipe)
    monkeypatch.setattr(
        module,
        "_cached",
        lambda p, *_: (
            {"status": "stream_collection_complete", "production_reference": {"passed": True}}
            if p.name in {"recovery.json", "control.json"}
            else None
        ),
    )
    monkeypatch.setattr(module, "_running_games", lambda: False)
    monkeypatch.setattr(module, "launch_inputs", lambda *_: {})
    monkeypatch.setattr(module, "load_training_score_spec", lambda *_: score())
    monkeypatch.setattr(module, "_shared_snapshot", lambda *_: {})
    monkeypatch.setattr(module, "immutable_checks", lambda *_: {"unchanged": True})
    monkeypatch.setattr(module, "EngineWorker", Worker)
    monkeypatch.setattr(module, "audit_worker_streaming", audit)
    monkeypatch.setattr(module, "read_native_episode", lambda *a: Counted(read_native_episode(*a)))
    q = cast(EngineQualificationConfig, SimpleNamespace(root=tmp_path))
    result = module.collect_stream(q, tmp_path / "cfg", node, "completion")
    assert peak <= 2 and live == 0
    assert result["optimizer_steps"] == result["game_apps_created"] == 0
    assert result["maximum_retained_episode_histories_per_lane"] == 1
    if fault is None:
        assert result["status"] == "stream_collection_complete"
        assert result["completed_games"] == 256 and sorted(audit_sizes) == [128, 128]
    else:
        assert result["status"] == "stream_collection_incomplete"
        assert result["completed_games"] == result["not_attempted_games"] == 128
        assert "2" not in attempts and attempts.count("0") == 1


@pytest.mark.parametrize("fault", [None, "retry", "duplicate", "omit"])
def test_union_keeps_interrupted_attempt_in_original_denominator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str | None
) -> None:
    import spireshift.native_gradient_stream as module

    cfg: dict[str, Any] = {
        "workspace": "artifacts/recovery",
        "interrupted_seed_ids": [700253],
        "additional_seed_ids": [700257],
        "target_clean_diagnostic_games": 256,
    }
    source = {"seed_ids": list(range(700001, 700257))}
    recovery: dict[str, Any] = {
        "report_id": "recovered",
        "entries": [{"seed_id": i} for i in source["seed_ids"] if i not in (700253, 700255)],
    }
    completion: dict[str, Any] = {
        "status": "stream_collection_complete",
        "report_id": "new",
        "entries": [{"seed_id": 700255}, {"seed_id": 700257}],
    }
    if fault == "retry":
        completion["entries"][-1]["seed_id"] = 700253
    elif fault == "duplicate":
        completion["entries"][-1]["seed_id"] = 700255
    elif fault == "omit":
        completion["entries"].pop()
    output = tmp_path / cfg["workspace"]
    output.mkdir(parents=True)
    monkeypatch.setattr(module, "load_stream", lambda *_: (cfg, source, model()))
    monkeypatch.setattr(
        module,
        "_cached",
        lambda p, *_: (
            recovery
            if p.name == "recovery.json"
            else (completion if p.name == "completion.json" else None)
        ),
    )
    if fault:
        with pytest.raises(ValueError, match="retry, duplicate"):
            prepare_union(SimpleNamespace(root=tmp_path), tmp_path / "cfg")  # type: ignore[arg-type]
    else:
        result = prepare_union(SimpleNamespace(root=tmp_path), tmp_path / "cfg")  # type: ignore[arg-type]
        assert result["clean_diagnostic_games"] == 256
        assert result["original_planned_games"] == 256
        assert result["original_completed_games_after_completion"] == 255
        assert result["total_planned_and_attempted_games_including_interruption"] == 257
        assert result["interrupted_attempts_excluded_from_gradient_inputs_but_counted"] == 1
        assert not result["ordinary_training_allowed"]


@pytest.mark.parametrize("fault", [None, "retry", "alias", "reserved", "memory", "source"])
def test_frozen_recovery_contract_cannot_hide_attempts_or_raise_memory_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str | None
) -> None:
    import spireshift.native_gradient_stream as module

    repo = Path(__file__).resolve().parents[2]
    cfg = json.loads(
        (repo / "configs/native-gradient/sts2-v0.111.0-a8-stream-recovery-v1.json").read_text()
    )
    m = model()
    old_seeds: dict[str, Any] = {
        "environment_id": m.actor.environment_id,
        "seeds": [{"id": i, "seed": str(i), "partition": "train"} for i in range(700001, 700257)],
    }
    (tmp_path / "old.json").write_text(
        json.dumps({**old_seeds, "manifest_id": manifest_identifier(old_seeds)})
    )
    source = {
        "seed_manifest": {"path": "old.json"},
        "environment_manifest": {"id": m.actor.environment_id},
    }
    cfg["source_pool_config"]["id"] = manifest_identifier(source)
    seeds: dict[str, Any] = {
        **old_seeds,
        "seeds": [
            *old_seeds["seeds"],
            {"id": 700257, "seed": "SP1RESH1FTA8GRD100257", "partition": "train"},
        ],
    }
    if fault == "alias":
        seeds["seeds"][-1]["seed"] = seeds["seeds"][0]["seed"]
    elif fault == "reserved":
        seeds["seeds"][-1]["partition"] = "development"
    cfg["seed_manifest"] = {"path": "new.json", "id": manifest_identifier(seeds)}
    (tmp_path / "new.json").write_text(
        json.dumps({**seeds, "manifest_id": manifest_identifier(seeds)})
    )
    for name in SOURCES:
        p = tmp_path / "src/spireshift" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("frozen synthetic source")
    cfg["implementation_sha256"] = {n: _sha_file(tmp_path / "src/spireshift" / n) for n in SOURCES}
    if fault == "retry":
        cfg["additional_seed_ids"] = [700253]
    elif fault == "memory":
        cfg["collection_limits"]["resident_memory_bytes"] *= 2
    elif fault == "source":
        cfg["implementation_sha256"][SOURCES[0]] = "0" * 64
    config = tmp_path / "cfg.json"
    config.write_text(json.dumps(cfg))
    monkeypatch.setattr(module, "load_pool", lambda *_: (source, m))
    q = cast(EngineQualificationConfig, SimpleNamespace(root=tmp_path))
    if fault:
        with pytest.raises(ValueError):
            load_stream(q, config)
    else:
        result, _, _ = load_stream(q, config)
        assert result["ordinary_training_allowed"] is False


def test_cached_stream_report_rechecks_sources_relative_to_repo(
    tmp_path: Path,
) -> None:
    from spireshift.native_gradient_stream import _cached

    cfg = {"scope": "frozen"}
    source = tmp_path / "source.txt"
    source.write_text("original")
    body = {
        "config_id": manifest_identifier(cfg),
        "sources": [{"path": "source.txt", "sha256": _sha_file(source)}],
    }
    report = tmp_path / "report.json"
    report.write_text(json.dumps({**body, "report_id": manifest_identifier(body)}))
    assert _cached(report, cfg, tmp_path) is not None
    source.write_text("changed")
    with pytest.raises(ValueError, match="evidence changed"):
        _cached(report, cfg, tmp_path)
