from __future__ import annotations

import copy
import hashlib
import json
import random
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from test_native_action_context import model, score
from test_native_context_trial import case

import spireshift.native_policy_confirmation as trial
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import save_native_episode
from spireshift.engine_experience_stream import compact_case
from spireshift.engine_learning import summarize
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_ppo_math import Adam
from spireshift.native_confirmation_metrics import RULE, compare
from spireshift.native_context_cache import cached_model
from spireshift.native_context_game import predict
from spireshift.native_context_journal import save_state

LOAD = trial.load_confirmation


def setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, short: bool = True) -> tuple[Any, ...]:
    cfg: dict[str, Any] = {
        "schema_version": "native-policy-confirmation-config-v1",
        "stage": "short_bridge_control" if short else "fresh_frozen_confirmation",
        "training_seeds": [2, 3],
        "evaluation_games": 2 if short else 64,
        "chunk_games": 2 if short else 8,
        "behavior": "sampled_softmax",
        "sampling": "unchanged_native_context_frozen_paired_draws_v1",
        "checkpoint_selection": "frozen_initial_and_final_standard_only",
        "confirmation_rule": RULE,
        "invocation_wall_seconds": 180 if short else 3600,
        "session_limits": {
            "wall_seconds": 180 if short else 900,
            "cpu_seconds": 360 if short else 1800,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 1000000000 if short else 2000000000,
        },
        "workspace": "artifacts/confirmation",
        "players": [],
        "seed_manifest": {"path": "seeds.json", "id": "unused"},
    }
    rows = [
        {
            "id": n * 1000 + i,
            "seed": f"FRESH{n}{i}",
            "numerical_seed": n,
            "partition": "control_eval" if short else "confirmation",
        }
        for n in (2, 3)
        for i in range(cfg["evaluation_games"])
    ]
    for n in (2, 3):
        m = cached_model(model(seed=n))
        for version in ("initial", "trained"):
            if version == "trained":
                m = cached_model(
                    m.with_weights([0.01 + w if i == 0 else w for i, w in enumerate(m.weights())])
                )
            state = tmp_path / f"source-{n}-{version}.json"
            optimizer = replace(Adam.zero(m.parameter_count), steps=int(version == "trained"))
            save_state(state, m, optimizer)
            cfg["players"].append(
                {
                    "numerical_seed": n,
                    "version": version,
                    "path": state.name,
                    "model_id": m.model_id,
                    "state_id": json.loads(state.read_text())["state_id"],
                    "sha256": _sha_file(state),
                }
            )
    parent = {
        "environment_manifest": {"id": m.actor.environment_id},
        "training_spec": {"path": "unused", "id": score().spec_id},
    }
    seeds = {"seeds": rows}
    recipe = tmp_path / "recipe.json"
    atomic_json(recipe, cfg)
    q = EngineQualificationConfig(document={}, root=tmp_path)
    sources = {p["path"]: p["sha256"] for p in cfg["players"]}
    monkeypatch.setattr(trial, "load_confirmation", lambda *_: (cfg, parent, seeds, dict(sources)))
    monkeypatch.setattr(trial, "load_training_score_spec", lambda *_: score())
    monkeypatch.setattr(trial, "_require_native_launch_support", lambda: None)
    monkeypatch.setattr(trial, "_running_games", lambda: False)
    monkeypatch.setattr(trial, "_shared_snapshot", lambda *_: {})
    monkeypatch.setattr(trial, "immutable_checks", lambda *_: {"unchanged": True})
    monkeypatch.setattr(trial, "launch_inputs", lambda *_: {})
    node = tmp_path / "node"
    node.touch()
    return q, cfg, parent, seeds, recipe, node


def collector(launched: list[Any]) -> Any:
    def collect(*args: Any) -> tuple[Any, ...]:
        q, cfg, parent, _, seeds, _, out, m, spec, number, label, training, _ = args
        assert not training and label == "fresh-confirmation"
        out.mkdir()
        paths, outcomes, sources = [], [], {}
        for s in seeds:
            sampling = int.from_bytes(
                hashlib.sha256(
                    f"native-context-rng-v1|{number}|frozen|{s['id']}".encode()
                ).digest()[:8],
                "big",
            )
            launched.append((m.model_id, s["id"], sampling))
            c = case(
                s["seed"], lambda p, draw=sampling: predict(m, spec, p, random.Random(draw), 0.8)
            )
            c.update(worker_workspace="fake", game_apps_created=0)
            binding = {
                "environment_id": parent["environment_manifest"]["id"],
                "config_id": manifest_identifier(cfg),
                "seed_manifest_id": cfg["seed_manifest"]["id"],
                "seed_id": s["id"],
                "native_seed": s["seed"],
                "partition": s["partition"],
                "panel": label,
                "model_id": m.model_id,
                "training_spec_id": spec.spec_id,
                "sampling_seed": sampling,
                "behavior": "sampled_softmax",
                "panel_purpose": "frozen_policy_evaluation",
            }
            p = out / f"case-{s['id']}.json"
            save_native_episode(p, c, binding)
            paths.append(p)
            outcomes.append({**compact_case(c), "seed_id": s["id"], "training_return": 0.01})
            sources.update(
                {str(f.relative_to(q.root)): _sha_file(f) for f in (p, p.with_suffix(".jsonl.gz"))}
            )
        summary = {
            **summarize(
                [{**o, "decisions": range(o["decision_count"])} for o in outcomes], len(seeds)
            ),
            "outcomes": outcomes,
            "worker_failures": 0,
        }
        return paths, summary, sources

    return collect


def test_interleaved_four_player_plan_pairs_seeds_and_never_fits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, cfg, _, seeds, _, _ = setup(tmp_path, monkeypatch, False)
    trial.validate_plan(cfg, seeds)
    tasks = trial.plan(cfg, seeds)
    assert len(tasks) == 32 and sum(len(t["seeds"]) for t in tasks) == 256
    assert not any(t.get("training") or t.get("kind") == "fit" for t in tasks)
    assert len({s["seed"] for t in tasks for s in t["seeds"]}) == 128
    for a, b in zip(tasks[::2], tasks[1::2], strict=True):
        assert a["version"] == "initial" and b["version"] == "trained"
        assert a["seeds"] == b["seeds"] and a["player"]["model_id"] != b["player"]["model_id"]


@pytest.mark.parametrize(
    "fault", ["duplicate_id", "duplicate_seed", "owner", "partition", "extent", "rule", "greedy"]
)
def test_plan_rejects_leakage_selection_and_changed_evaluation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    _, cfg, _, seeds, _, _ = setup(tmp_path, monkeypatch)
    if fault == "duplicate_id":
        seeds["seeds"][1]["id"] = seeds["seeds"][0]["id"]
    elif fault == "duplicate_seed":
        seeds["seeds"][1]["seed"] = seeds["seeds"][0]["seed"]
    elif fault == "owner":
        seeds["seeds"][0]["numerical_seed"] = 3
    elif fault == "partition":
        seeds["seeds"][0]["partition"] = "train"
    elif fault == "extent":
        cfg["evaluation_games"] = 1
    elif fault == "rule":
        cfg["confirmation_rule"] = "pick_best_player"
    else:
        cfg["behavior"] = "greedy"
    with pytest.raises(ValueError):
        trial.validate_plan(cfg, seeds)


def test_frozen_collection_resumes_exactly_and_completed_command_only_verifies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    q, cfg, _, _, path, node = setup(tmp_path, monkeypatch)
    launched: list[Any] = []
    monkeypatch.setattr(trial, "collect_panel", collector(launched))
    protected = {p["path"]: (q.root / p["path"]).read_bytes() for p in cfg["players"]}
    status = trial.session(q, path, node, status_only=True)
    assert status["completed_units"] == 0 and not (q.root / cfg["workspace"]).exists()
    first = trial.session(q, path, node, maximum_steps=1)
    assert first["completed_units"] == 1 and len(launched) == 2
    saved = (q.root / cfg["workspace"] / "chunks/seed-2-pair-00-initial/done.json").read_bytes()
    final = trial.session(q, path, node)
    assert final["status"] == trial.CONTROL and final["games_recorded"] == 8
    assert len(launched) == 8 and final["optimizer_steps"] == 0
    assert final["comparison"]["auxiliary_progress_confirmed"] is False
    assert all((q.root / p).read_bytes() == data for p, data in protected.items())
    assert (
        q.root / cfg["workspace"] / "chunks/seed-2-pair-00-initial/done.json"
    ).read_bytes() == saved
    assert trial.session(q, path, node, status_only=True) == final and len(launched) == 8
    assert trial.session(q, path, node) == final and len(launched) == 8
    # Same random stream within each pair, never coupled to a model ID.
    assert [v[2] for v in launched[:2]] == [v[2] for v in launched[2:4]]


@pytest.mark.parametrize(
    "fault",
    ["wrong_owner", "trace", "worker_failure", "interrupt", "running_game", "changed_source"],
)
def test_uncertain_or_changed_evidence_stops_without_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    q, cfg, _, _, path, node = setup(tmp_path, monkeypatch)
    launched: list[Any] = []
    original = collector(launched)

    def broken(*args: Any) -> tuple[Any, ...]:
        paths, summary, sources = original(*args)
        if fault == "interrupt":
            raise TimeoutError("interrupted game")
        if fault == "worker_failure":
            summary["worker_failures"] = 1
        if fault == "changed_source":
            (q.root / cfg["players"][0]["path"]).write_text("changed")
        if fault in {"wrong_owner", "trace"}:
            h = json.loads(paths[0].read_text())
            if fault == "wrong_owner":
                h["binding"]["model_id"] = "other"
                body = {k: v for k, v in h.items() if k not in {"case_id", "trace_file_sha256"}}
                h["case_id"] = manifest_identifier(body)
            else:
                h["trace_file_sha256"] = "changed"
            paths[0].write_text(json.dumps(h))
        return paths, summary, sources

    monkeypatch.setattr(trial, "collect_panel", broken)
    if fault == "running_game":
        monkeypatch.setattr(trial, "_running_games", lambda: True)
    with pytest.raises((ValueError, TimeoutError)):
        trial.session(q, path, node)
    count = len(launched)
    if fault not in {"running_game", "changed_source"}:
        with pytest.raises(FileExistsError, match="uncommitted"):
            trial.session(q, path, node)
    assert len(launched) == count and not (q.root / cfg["workspace"] / "report.json").exists()


def test_paired_stats_count_failures_and_never_promote_or_select_players() -> None:
    cfg = {"training_seeds": [2, 3], "stage": "fresh_frozen_confirmation"}
    seeds = {
        "seeds": [
            {"id": n * 1000 + i, "seed": f"N{n}-{i}", "numerical_seed": n}
            for n in (2, 3)
            for i in range(64)
        ]
    }
    panels: list[dict[str, Any]] = [
        {
            "numerical_seed": n,
            "version": version,
            "outcomes": [
                {
                    "seed_id": s["id"],
                    "seed": s["seed"],
                    "status": "terminal",
                    "maximum_floor": 6 if version == "initial" else 9,
                    "victory": False,
                }
                for s in seeds["seeds"]
                if s["numerical_seed"] == n
            ],
        }
        for n in (2, 3)
        for version in ("initial", "trained")
    ]
    result = compare(cfg, panels, seeds)
    assert result["auxiliary_progress_confirmed"] and result["mean_floor_change"] == 3
    assert result["paired_floor_change_interval95"] == [3.0, 3.0]
    assert not result["checkpoint_promoted"] and not result["automatic_training_follows"]
    changed = copy.deepcopy(panels)
    changed[1]["outcomes"][0].update(status="failed", maximum_floor=50, victory=True)
    failed = compare(cfg, changed, seeds)
    assert failed["aggregate"]["trained"]["wins"] == 0
    assert failed["aggregate"]["trained"]["failed_games"] == 1
    assert failed["aggregate"]["trained"]["denominator"] == 128
    assert failed["aggregate"]["trained"]["mean_floor"] < 9
    assert not failed["auxiliary_progress_confirmed"]
    changed = copy.deepcopy(panels)
    changed[3]["outcomes"] = copy.deepcopy(changed[2]["outcomes"])
    assert not compare(cfg, changed, seeds)["auxiliary_progress_confirmed"]
    panels[-1]["outcomes"].pop()
    with pytest.raises(ValueError, match="paired whole-run"):
        compare(cfg, panels, seeds)


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "earlier_checkpoint",
        "initializer_selection",
        "temperature",
        "overlap_id",
        "overlap_native_seed",
        "omit_exclusion",
        "source_changed",
        "unfinished_source",
    ],
)
def test_loader_binds_completed_final_players_and_excludes_all_old_games(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str | None
) -> None:
    q, cfg, parent, seeds, path, _ = setup(tmp_path, monkeypatch)
    parent["learning"] = {"ppo": {"temperature": 0.8}}
    monkeypatch.setattr(trial, "SOURCES", ())
    old: dict[str, Any] = {
        "stage": "bounded_optimizer_learning_curve",
        "workspace": "artifacts/source",
        "seed_manifest": {"path": "old-seeds.json"},
        "excluded_seed_manifests": [{"path": "older-seeds.json"}],
    }
    old_path = q.root / "old-recipe.json"
    atomic_json(old_path, old)
    monkeypatch.setattr(trial, "load_trial", lambda *_: (old, parent, {}))
    sources, curves = {}, []
    for p in cfg["players"]:
        key = f"seed-{p['numerical_seed']}-standard-" + (
            "initial" if p["version"] == "initial" else "batch-016-fit"
        )
        target = q.root / old["workspace"] / "chunks" / key / "state.json"
        target.parent.mkdir(parents=True)
        target.write_bytes((q.root / p["path"]).read_bytes())
        p["path"] = str(target.relative_to(q.root))
        body = {
            "config_id": manifest_identifier(old),
            "key": key,
            "result": {
                "state_path": p["path"],
                "model_id": p["model_id"],
                "state_id": p["state_id"],
            },
        }
        atomic_json(target.with_name("done.json"), {**body, "report_id": manifest_identifier(body)})
        sources.update(
            {
                str(f.relative_to(q.root)): _sha_file(f)
                for f in (target, target.with_name("done.json"))
            }
        )
        curves.append(
            {
                "arm": "standard",
                "numerical_seed": p["numerical_seed"],
                "training_games": 0 if p["version"] == "initial" else 512,
                "model_id": p["model_id"],
            }
        )
    report = {
        "config_id": manifest_identifier(old),
        "status": "native_optimizer_learning_curve_complete",
        "games_recorded": 2368,
        "planned_games": 2368,
        "completed_units": 340,
        "planned_units": 340,
        "sources": sources,
        "learning_curves": curves,
    }
    if fault == "unfinished_source":
        report["completed_units"] = 339
    report_path = q.root / old["workspace"] / "report.json"
    atomic_json(report_path, {**report, "report_id": manifest_identifier(report)})
    cfg.update(
        source_trial={"path": old_path.name, "id": manifest_identifier(old)},
        source_report={
            "path": str(report_path.relative_to(q.root)),
            "id": manifest_identifier(report),
        },
        implementation_sha256={},
        temperature=0.8,
        excluded_seed_manifests=[],
    )
    (q.root / "scripts").mkdir()
    entry = q.root / "scripts/policy-confirmation-v1.py"
    entry.write_text("frozen entry")
    cfg["entry_sha256"] = _sha_file(entry)
    for i, name in enumerate(("old-seeds.json", "older-seeds.json")):
        prior = {"seeds": [{"id": -i, "seed": f"OLD{i}"}]}
        if i == 0 and fault == "overlap_id":
            prior["seeds"][0]["id"] = seeds["seeds"][0]["id"]
        if i == 0 and fault == "overlap_native_seed":
            prior["seeds"][0]["seed"] = seeds["seeds"][0]["seed"]
        atomic_json(q.root / name, {**prior, "manifest_id": manifest_identifier(prior)})
        cfg["excluded_seed_manifests"].append({"path": name, "id": manifest_identifier(prior)})
    seeds["environment_id"] = parent["environment_manifest"]["id"]
    atomic_json(q.root / "seeds.json", {**seeds, "manifest_id": manifest_identifier(seeds)})
    cfg["seed_manifest"]["id"] = manifest_identifier(seeds)
    if fault == "earlier_checkpoint":
        cfg["players"][1]["state_id"] = cfg["players"][0]["state_id"]
    elif fault == "initializer_selection":
        cfg["players"] = cfg["players"][:2]
    elif fault == "temperature":
        cfg["temperature"] = 0.1
    elif fault == "omit_exclusion":
        cfg["excluded_seed_manifests"].pop()
    elif fault == "source_changed":
        (q.root / cfg["players"][0]["path"]).write_text("changed")
    path.write_text(json.dumps(cfg))
    if fault is None:
        actual, loaded_parent, loaded_seeds, bound = LOAD(q, path)
        assert actual == cfg and loaded_parent == parent and loaded_seeds["seeds"] == seeds["seeds"]
        assert all(p["path"] in bound for p in cfg["players"])
    else:
        with pytest.raises(ValueError):
            LOAD(q, path)
