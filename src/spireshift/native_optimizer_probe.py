"""Finite TRAIN-only optimizer sensitivity study on exact saved behavior batches.

Reconstruct two first-round cohorts, preserving historical code and experiences.
Training-surrogate movement is diagnostic, never proof of improved game outcomes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode
from spireshift.engine_learning import identified
from spireshift.engine_qualification import (
    EngineQualificationConfig,
    _sha_file,
    load_engine_qualification_config,
)
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_policy import dense_features
from spireshift.full_run_ppo_math import Adam, Sample, fit_round, log_softmax, loss_gradient
from spireshift.native_action_context import CROSSED
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_game import verified_samples
from spireshift.native_context_journal import ChunkJournal, load_state, save_state
from spireshift.native_context_resume import SOURCES as CONTEXT_SOURCES
from spireshift.native_context_resume import load_resume, ordered_paths
from spireshift.native_context_reuse import check_sources
from spireshift.native_gradient_checks import cosine
from spireshift.native_value_credit import ValueRun, cross_fitted_predictions, value_run
from spireshift.neural_combat import _numpy
from spireshift.training_objective import TrainingScoreSpec, load_training_score_spec

SOURCES = (*CONTEXT_SOURCES, "native_gradient_checks.py", "native_optimizer_probe.py")
VARIANTS = (
    {"name": "standard", "actor_rate_multiplier": 1, "epochs_multiplier": 1},
    {"name": "larger-step", "actor_rate_multiplier": 3, "epochs_multiplier": 1},
    {"name": "more-passes", "actor_rate_multiplier": 1, "epochs_multiplier": 3},
)


@dataclass(frozen=True)
class GameBatch:
    run: ValueRun
    samples: tuple[Sample, ...]


def credit_samples(games: list[GameBatch], credit: dict[str, Any]) -> list[Sample]:
    if len(games) < 4 or len({g.run.seed for g in games}) != len(games):
        raise ValueError("Optimizer probe requires distinct complete games")
    runs = sorted((g.run for g in games), key=lambda r: r.seed)
    predictions, _ = cross_fitted_predictions(
        runs,
        credit["baseline"],
        credit["regularization"],
        min(credit["folds"], len(runs)),
        credit["fold_salt"],
    )
    return [
        replace(s, advantage=s.target - v)
        for g in games
        for s, v in zip(g.samples, predictions[g.run.seed], strict=True)
    ]


def normalized(samples: list[Sample]) -> list[Sample]:
    np = _numpy()
    a = np.asarray([s.advantage for s in samples])
    return [
        replace(s, advantage=float(v))
        for s, v in zip(samples, (a - a.mean()) / max(float(a.std()), 1e-8), strict=True)
    ]


def actor_gradient(
    model: CachedContextModel, samples: list[Sample], settings: dict[str, Any], entropy: float
) -> Any:
    np = _numpy()
    result = np.zeros(model.actor.parameter_count)
    for i in range(0, len(samples), settings["minibatch_decisions"]):
        batch = samples[i : i + settings["minibatch_decisions"]]
        _, g, _ = loss_gradient(
            cast(Any, model),
            batch,
            clip=settings["clip"],
            entropy_coefficient=entropy,
            value_coefficient=0,
            temperature=settings["temperature"],
        )
        result += np.asarray(g[: len(result)]) * len(batch) / len(samples)
    return result


def independent_groups(
    model: CachedContextModel,
    games: list[GameBatch],
    settings: dict[str, Any],
    credit: dict[str, Any],
) -> dict[str, Any]:
    order = sorted(
        games,
        key=lambda g: hashlib.sha256(
            f"optimizer-whole-game-split-v1|{g.run.seed}".encode()
        ).digest(),
    )
    groups = (order[::2], order[1::2])
    vectors = [
        actor_gradient(model, normalized(credit_samples(group, credit)), settings, 0)
        for group in groups
    ]
    return {
        "groups": [[g.run.seed for g in group] for group in groups],
        "games_per_group": [len(g) for g in groups],
        "data_gradient_cosine": cosine(*vectors),
        "group_data_gradient_norms": [float(_numpy().linalg.norm(v)) for v in vectors],
        "each_group_fits_own_baseline_and_normalization": True,
        "single_split_diagnostic_not_population_confidence": True,
    }


def logits(model: CachedContextModel, samples: list[Sample]) -> Any:
    np = _numpy()
    x = dense_features(tuple(row for s in samples for row in s.rows), model.actor.dimension)
    w, b, out, linear = model.actor.unpack()
    return np.tanh(x @ w.T + b) @ out + x @ linear


def movement(
    before: CachedContextModel,
    after: CachedContextModel,
    samples: list[Sample],
    settings: dict[str, Any],
) -> dict[str, Any]:
    """Policy changes on the same frozen rows, with exact menu KL and explicit units."""
    np = _numpy()
    total = {
        k: 0.0
        for k in (
            "surrogate",
            "log_alignment",
            "menu_kl",
            "tv",
            "entropy_before",
            "entropy_after",
            "positive_delta",
            "negative_delta",
        )
    }
    choices = flips = positives = negatives = 0
    for start in range(0, len(samples), settings["minibatch_decisions"]):
        batch = samples[start : start + settings["minibatch_decisions"]]
        a, b, offset = logits(before, batch), logits(after, batch), 0
        for s in batch:
            n = len(s.rows)
            la = np.asarray(log_softmax(a[offset : offset + n], settings["temperature"]))
            lb = np.asarray(log_softmax(b[offset : offset + n], settings["temperature"]))
            pa, pb = np.exp(la), np.exp(lb)
            if not math.isclose(
                float(la[s.action]), s.old_log_probability, abs_tol=1e-10, rel_tol=0
            ):
                raise ValueError("Probe movement uses a different behavior checkpoint")
            d = float(lb[s.action] - la[s.action])
            ratio = math.exp(d)
            bounded = max(1 - settings["clip"], min(1 + settings["clip"], ratio))
            total["surrogate"] += min(ratio * s.advantage, bounded * s.advantage) - s.advantage
            total["log_alignment"] += s.advantage * d
            if n > 1:
                choices += 1
                flips += int(int(pa.argmax()) != int(pb.argmax()))
                total["menu_kl"] += float(pa @ (la - lb))
                total["tv"] += float(np.abs(pa - pb).sum()) / 2
                total["entropy_before"] -= float(pa @ la)
                total["entropy_after"] -= float(pb @ lb)
                delta = float(pb[s.action] - pa[s.action])
                if s.advantage > 0:
                    positives += 1
                    total["positive_delta"] += delta
                elif s.advantage < 0:
                    negatives += 1
                    total["negative_delta"] += delta
            offset += n
    return {
        "decisions": len(samples),
        "choice_decisions": choices,
        "forced_menus_retained_in_production_normalization": len(samples) - choices,
        "clipped_training_surrogate_gain": total["surrogate"] / len(samples),
        "advantage_weighted_log_probability_movement": total["log_alignment"] / len(samples),
        "mean_choice_menu_forward_kl": total["menu_kl"] / max(choices, 1),
        "mean_choice_total_variation": total["tv"] / max(choices, 1),
        "greedy_choice_changed_fraction": flips / max(choices, 1),
        "mean_choice_entropy_before": total["entropy_before"] / max(choices, 1),
        "mean_choice_entropy_after": total["entropy_after"] / max(choices, 1),
        "positive_advantage_chosen_probability_change": total["positive_delta"] / positives
        if positives
        else None,
        "negative_advantage_chosen_probability_change": total["negative_delta"] / negatives
        if negatives
        else None,
        "claim_scope": "in_sample_training_signal_fit_not_action_quality_or_gameplay",
    }


def cohort(
    q: EngineQualificationConfig,
    cfg: dict[str, Any],
    parent: dict[str, Any],
    rep: int,
    score: TrainingScoreSpec,
) -> tuple[CachedContextModel, Adam, list[GameBatch], str, dict[str, str]]:
    context = json.loads((q.root / cfg["source_recipe"]["path"]).read_text())
    if rep == 0:
        legacy = json.loads((q.root / context["legacy_recipe"]["path"]).read_text())
        arm = q.root / legacy["workspace"] / f"{CROSSED}-seed-0"
        before_path, after_path = arm / "initial-model.json", arm / "round-001-model.json"
        model = CachedContextModel.from_mapping(json.loads(before_path.read_text()))
        optimizer = Adam.zero(model.parameter_count)
        expected = CachedContextModel.from_mapping(json.loads(after_path.read_text())).model_id
        paths = ordered_paths(
            list((arm / "round-001").glob("case-*.json")), list(range(820001, 820033))
        )
        source_cfg = legacy
    else:
        arm = q.root / context["workspace"] / "chunks"
        before_path = arm / "cross-initial/state.json"
        after_path = arm / "cross-round-001-fit/state.json"
        model, optimizer, _ = load_state(before_path)
        expected = load_state(after_path)[0].model_id
        paths = ordered_paths(
            [
                p
                for i in range(4)
                for p in (arm / f"cross-round-001-collect-{i:02d}/games").glob("case-*.json")
            ],
            list(range(840001, 840033)),
        )
        source_cfg = context
    if (
        rep not in (0, 1)
        or model.mode != CROSSED
        or model.actor.environment_id != parent["environment_manifest"]["id"]
        or model.feature_spec_id != score.spec_id
        or optimizer.steps != 0
        or any(optimizer.first)
        or any(optimizer.second)
    ):
        raise ValueError("Probe scope is two exact first-round crossed behavior checkpoints")
    games = []
    sources = {str(p.relative_to(q.root)): _sha_file(p) for p in (before_path, after_path)}
    for p in paths:
        header = json.loads(p.read_text())
        binding = header["binding"]
        if (
            binding["partition"] != "train"
            or binding["panel_purpose"] != "training"
            or binding["model_id"] != model.model_id
            or binding["panel"] != "round-001"
            or binding["config_id"] != manifest_identifier(source_cfg)
            or binding["seed_manifest_id"] != source_cfg["seed_manifest"]["id"]
            or binding["environment_id"] != parent["environment_manifest"]["id"]
            or binding["training_spec_id"] != score.spec_id
        ):
            raise ValueError("Only the sealed own-behavior TRAIN batch may supply this probe")
        case = read_native_episode(p, binding)
        run = value_run(case, binding["seed_id"], 1, score)
        samples = verified_samples(
            case, model, score, run.target, parent["learning"]["ppo"]["temperature"]
        )
        games.append(GameBatch(run, tuple(samples)))
        for f in (p, p.with_suffix(".jsonl.gz")):
            sources[str(f.relative_to(q.root))] = _sha_file(f)
    return model, optimizer, games, expected, sources


def load_probe(q: EngineQualificationConfig, path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    cfg = json.loads(path.read_text())
    source, parent, _ = load_resume(q, q.root / cfg["source_recipe"]["path"])
    report = identified(q.root / source["workspace"] / "report.json")
    if (
        cfg.get("schema_version") != "native-optimizer-probe-config-v1"
        or cfg["source_recipe"]["id"] != manifest_identifier(source)
        or cfg.get("source_report_id") != report["report_id"]
        or report["status"] != "chunked_comparison_complete"
        or cfg.get("variants") != list(VARIANTS)
        or cfg.get("cohorts") != [0, 1]
        or cfg.get("implementation_sha256")
        != {n: _sha_file(q.root / "src/spireshift" / n) for n in SOURCES}
        or cfg.get("resource_limits")
        != {
            "wall_seconds": 240,
            "cpu_seconds": 480,
            "resident_memory_bytes": 2000000000,
            "storage_bytes": 500000000,
        }
    ):
        raise ValueError("Freeze TRAIN-only source, finite optimizer variants and implementation")
    check_sources(q.root, report["sources"])
    return cfg, parent


def run(q: EngineQualificationConfig, path: Path) -> dict[str, Any]:
    cfg, parent = load_probe(q, path)
    store = ChunkJournal(q.root, cfg)
    score = load_training_score_spec(q.root / parent["training_spec"]["path"])
    started, results, sources = (
        time.monotonic(),
        [],
        {str(path.relative_to(q.root)): _sha_file(path)},
    )
    sources.update({f"src/spireshift/{n}": v for n, v in cfg["implementation_sha256"].items()})
    source_cfg_path = q.root / cfg["source_recipe"]["path"]
    source_report_path = (
        q.root / json.loads(source_cfg_path.read_text())["workspace"] / "report.json"
    )
    sources.update(
        {str(p.relative_to(q.root)): _sha_file(p) for p in (source_cfg_path, source_report_path)}
    )
    with store.lock():
        final = store.workspace / "report.json"
        if final.exists():
            result = identified(final)
            check_sources(q.root, result["sources"])
            return result
        for rep in cfg["cohorts"]:
            model, optimizer, games, expected, inputs = cohort(q, cfg, parent, rep, score)
            sources.update(inputs)
            samples = credit_samples(games, parent["learning"]["credit_assignment"])
            prepared = normalized(samples)
            agreement = independent_groups(
                model, games, parent["learning"]["ppo"], parent["learning"]["credit_assignment"]
            )
            for variant in cfg["variants"]:
                key = f"seed-{rep}-{variant['name']}"
                settings = {
                    **parent["learning"]["ppo"],
                    "actor_learning_rate": parent["learning"]["ppo"]["actor_learning_rate"]
                    * variant["actor_rate_multiplier"],
                    "epochs": parent["learning"]["ppo"]["epochs"] * variant["epochs_multiplier"],
                }
                request = {
                    "cohort": rep,
                    "before_model_id": model.model_id,
                    "settings": settings,
                    "inputs_id": manifest_identifier(inputs),
                }
                receipt = store.completed(key, request)
                if receipt is None:
                    target = store.begin(key, request)
                    updated, opt, work = fit_round(
                        cast(Any, model), optimizer, samples, settings, 1
                    )
                    if not isinstance(updated, CachedContextModel):
                        raise ValueError("Probe lost native encoding/cache identity")
                    exact = updated.model_id == expected
                    if variant["name"] == "standard" and not exact:
                        raise ValueError(
                            "Standard probe must exactly reconstruct the historical fitted model"
                        )
                    save_state(target / "state.json", updated, opt)
                    change = movement(model, updated, prepared, settings)
                    result = {
                        "cohort": rep,
                        "variant": variant["name"],
                        "before_model_id": model.model_id,
                        "after_model_id": updated.model_id,
                        "work": work,
                        "settings": settings,
                        "movement": change,
                        "standard_reconstructs_saved_model": exact
                        if variant["name"] == "standard"
                        else None,
                        "independent_groups": agreement,
                        "source_games": len(games),
                        "games_launched": 0,
                    }
                    receipt = store.commit(key, request, result, inputs)
                    print(
                        f"Cohort {rep}, {variant['name']}: {work['optimizer_steps']} steps; "
                        f"surrogate gain {change['clipped_training_surrogate_gain']:.5f}; "
                        f"choice KL {change['mean_choice_menu_forward_kl']:.5f}. "
                        "No games run.",
                        flush=True,
                    )
                results.append(receipt["result"])
                sources[str((store.path(key) / "done.json").relative_to(q.root))] = _sha_file(
                    store.path(key) / "done.json"
                )
                sources.update(receipt["sources"])
            del games, samples, prepared
        check_sources(q.root, identified(source_report_path)["sources"])
        check_sources(q.root, sources)
        body = {
            "schema_version": "native-optimizer-probe-v1",
            "config_id": store.config_id,
            "status": "train_only_optimizer_probe_complete",
            "results": results,
            "source_unique_games": 64,
            "training_replicates": 2,
            "source_round": 1,
            "games_launched": 0,
            "optimizer_steps": sum(r["work"]["optimizer_steps"] for r in results),
            "source_reports_unchanged": True,
            "sources": sources,
            "wall_seconds": time.monotonic() - started,
            "checkpoint_promoted": False,
            "adaptive_controller_allowed": False,
            "stronger_play_established": False,
            "claim_scope": "saved_TRAIN_behavior_batch_optimizer_sensitivity_only",
        }
        result = {**body, "report_id": manifest_identifier(body)}
        atomic_json(final, result)
        return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("qualification", type=Path)
    p.add_argument("config", type=Path)
    args = p.parse_args()
    q = load_engine_qualification_config(args.qualification)
    report = run(q, q.root / args.config)
    print(
        json.dumps({k: v for k, v in report.items() if k not in {"sources", "results"}}, indent=2)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
