"""Bind consumed original states, fresh seeds, old native admission and new code."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_context_journal import load_state
from spireshift.native_context_reuse import check_sources
from spireshift.native_exploration_admission import SOURCES as PRIOR_SOURCES
from spireshift.native_policy_updates import SETTINGS
from spireshift.training_objective import load_training_score_spec

NEW_SOURCES = (
    "native_policy_updates.py",
    "native_policy_trial_inputs.py",
    "native_policy_trial_plan.py",
    "native_policy_trial_execute.py",
    "native_policy_trial.py",
)
SOURCES = tuple(
    dict.fromkeys(
        (
            *PRIOR_SOURCES,
            "native_combat_behavior_policy.py",
            "native_combat_behavior_game.py",
            "native_combat_behavior_data.py",
            "native_turn_teacher_policy.py",
            "native_combat_teacher_data.py",
            *NEW_SOURCES,
        )
    )
)
ENTRIES = ("compare-native-policy-updates-v1.sh", "compare-native-policy-updates-v1.py")
SHARED = (
    "source_result",
    "source_assessment",
    "engine_source",
    "players",
    "training_spec",
    "environment_manifest",
    "qualification",
    "qualification_id",
    "native_inputs",
    "node",
    "helpers_sha256",
    "learning",
    "credit",
    "maximum_decisions",
    "episode_wall_seconds",
    "implementation_sha256",
    "entry_sha256",
    "checkpoint_selection",
    "evaluation_behavior",
)


def validate(cfg: dict[str, Any]) -> None:
    control = cfg.get("stage") == "short_control"
    if (
        cfg.get("schema_version") != "native-policy-update-comparison-config-v1"
        or cfg.get("stage") not in {"short_control", "bounded_policy_comparison"}
        or cfg.get("rounds") != (1 if control else 2)
        or cfg.get("batch_games") != (2 if control else 32)
        or cfg.get("chunk_games") != (2 if control else 8)
        or cfg.get("evaluation_worlds") != (1 if control else 32)
        or cfg.get("checkpoint_selection") != "final_only_no_development_selection"
        or cfg.get("evaluation_behavior") != "greedy_combat_sampled_noncombat_v1"
        or cfg.get("learning") != SETTINGS
        or cfg.get("credit")
        != {
            "baseline": "public_residual_ridge",
            "regularization": 0.001,
            "folds": 4,
            "fold_salt": "native-whole-run-value-crossfit-v1",
        }
        or cfg.get("maximum_decisions") != 4096
        or cfg.get("episode_wall_seconds") != 120
        or cfg.get("session_limits")
        != {
            "wall_seconds": 240 if control else 900,
            "cpu_seconds": 480 if control else 1800,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 1000000000 if control else 4000000000,
        }
    ):
        raise ValueError("Freeze the finite, all-family, final-only on-policy comparison")


def seed_inputs(
    root: Path, cfg: dict[str, Any], environment: str
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    ref = cfg["seed_manifest"]
    manifest = identified(root / ref["path"], "manifest_id")
    seeds = manifest["seeds"]
    if (
        manifest["manifest_id"] != ref["id"]
        or manifest["environment_id"] != environment
        or manifest["schema_version"] != "native-policy-update-seeds-v1"
        or len(seeds) != cfg["rounds"] * cfg["batch_games"] + cfg["evaluation_worlds"]
        or any(
            set(s) != {"id", "seed", "partition"}
            or type(s["id"]) is not int
            or not re.fullmatch(r"[A-HJ-NP-Z0-9]+", str(s["seed"]))
            or s["partition"] not in {"train", "development"}
            for s in seeds
        )
        or len({s["id"] for s in seeds}) != len(seeds)
        or len({s["seed"] for s in seeds}) != len(seeds)
        or sum(s["partition"] == "train" for s in seeds) != cfg["rounds"] * cfg["batch_games"]
    ):
        raise ValueError(
            "Fresh training and development worlds must be distinct, canonical and finite"
        )
    sources = {ref["path"]: _sha_file(root / ref["path"])}
    for ref in cfg["freshness_exclusions"]:
        other = identified(root / ref["path"], "manifest_id")
        if other["manifest_id"] != ref["id"]:
            raise ValueError("A frozen historical seed manifest changed")
        names = {str(s["seed"]).upper().replace("I", "1").replace("O", "0") for s in other["seeds"]}
        if {s["id"] for s in seeds} & {s["id"] for s in other["seeds"]} or {
            s["seed"] for s in seeds
        } & names:
            raise ValueError("Do not reuse a prior training, control, development or test world")
        sources[ref["path"]] = _sha_file(root / ref["path"])
    if cfg["stage"] != "short_control" and cfg["control_seeds"] not in cfg["freshness_exclusions"]:
        raise ValueError("The comparison must also exclude its separate short-control worlds")
    return seeds, sources


def load(root: Path, path: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    validate(cfg)
    if cfg["implementation_sha256"] != {
        n: _sha_file(root / "src/spireshift" / n) for n in SOURCES
    } or cfg["entry_sha256"] != {n: _sha_file(root / "scripts" / n) for n in ENTRIES}:
        raise ValueError("Policy-update implementation or entry points changed")
    sources = {str(path.relative_to(root)): _sha_file(path)}
    sources.update({f"src/spireshift/{n}": v for n, v in cfg["implementation_sha256"].items()})
    sources.update({f"scripts/{n}": v for n, v in cfg["entry_sha256"].items()})
    reports = {}
    for name in ("source_result", "source_assessment"):
        ref = cfg[name]
        report = identified(root / ref["path"])
        if report["report_id"] != ref["id"] or _sha_file(root / ref["path"]) != ref["sha256"]:
            raise ValueError("Completed separation evidence changed")
        reports[name] = report
        sources[ref["path"]] = ref["sha256"]
    source, assessment = reports["source_result"], reports["source_assessment"]
    if (
        source["status"] != "native_prediction_separation_complete"
        or source["ranking"]["episodes"] != 192
        or not source["fitted_prediction_did_not_change_action_scores_or_probabilities"]
        or assessment["source_report_id"] != source["report_id"]
        or assessment["verified_rank_cases"] != 192
        or not assessment["every_numeric_history_summary_and_equal_game_stratum_reconstructed"]
        or cfg["players"] != source["parents"]
    ):
        raise ValueError(
            "Require the complete saved-ranking separation control and exact originals"
        )
    models, adams = {}, {}
    for p in cfg["players"]:
        model, adam, sid = load_state(root / p["path"])
        if (
            sid != p["state_id"]
            or model.model_id != p["model_id"]
            or adam.steps != p["optimizer_steps"]
            or _sha_file(root / p["path"]) != p["sha256"]
        ):
            raise ValueError("Keep both complete original weights and Adam moments unchanged")
        models[p["numerical_seed"]], adams[p["numerical_seed"]] = model, adam
        sources[p["path"]] = p["sha256"]
    if set(models) != {2, 3} or len(cfg["players"]) != 2:
        raise ValueError("Keep both original fixed players")
    engine = cfg["engine_source"]
    if source["sources"].get(engine["path"]) != _sha_file(root / engine["path"]):
        raise ValueError("Historical native source recipe changed")
    old = json.loads((root / engine["path"]).read_text())
    if manifest_identifier(old) != engine["id"] or any(
        cfg[k] != old[k]
        for k in (
            "qualification",
            "qualification_id",
            "native_inputs",
            "node",
            "helpers_sha256",
            "maximum_decisions",
            "episode_wall_seconds",
        )
    ):
        raise ValueError("Preserve the previously qualified actual A8 native bridge")
    score = load_training_score_spec(root / cfg["training_spec"]["path"])
    if (
        score.spec_id != cfg["training_spec"]["id"]
        or score.spec_id != source["training_spec_id"]
        or score.evaluation_objective.as_dict() != source["full_run_objective"]
        or any(m.actor.environment_id != cfg["environment_manifest"]["id"] for m in models.values())
    ):
        raise ValueError("Keep terminal victory, A8 environment and declared bootstrap score")
    for ref in (engine, cfg["training_spec"], cfg["environment_manifest"]):
        if source["sources"].get(ref["path"]) != _sha_file(root / ref["path"]):
            raise ValueError("Consumed source input differs from its completed qualification seal")
        sources[ref["path"]] = _sha_file(root / ref["path"])
    seeds, extra = seed_inputs(root, cfg, cfg["environment_manifest"]["id"])
    sources.update(extra)
    return {
        "config": cfg,
        "models": models,
        "adams": adams,
        "score": score,
        "seeds": seeds,
        "sources": sources,
    }


def control_sources(root: Path, cfg: dict[str, Any]) -> dict[str, str]:
    ref = cfg["control_report"]
    report = identified(root / ref["path"])
    old_path = root / cfg["control_recipe"]["path"]
    old = json.loads(old_path.read_text())
    if (
        report["report_id"] != ref["id"]
        or report["status"] != "native_policy_update_control_complete"
        or report["config_id"] != manifest_identifier(old)
        or old["stage"] != "short_control"
        or any(cfg[k] != old[k] for k in SHARED)
        or report["games_recorded"] != 8
        or report["failed_games"] != 0
        or not report["policy_checks"]["passed"]
        or not report["original_full_states_and_Adam_unchanged"]
    ):
        raise ValueError("Pass the matching eight-game policy-update bridge control first")
    check_sources(root, report["sources"])
    return {
        **report["sources"],
        ref["path"]: _sha_file(root / ref["path"]),
        str(old_path.relative_to(root)): _sha_file(old_path),
    }
