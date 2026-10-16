"""Explicit, scoped learning admission and saved-only inspection; never starts a game."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode, score_episode, verified_native_samples
from spireshift.engine_learning import identified, load_learning_config
from spireshift.engine_neural import NativeActorCritic
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.engine_run import _run_inputs
from spireshift.engine_startup import _script_closure
from spireshift.engine_worker_qualification import load_worker_config, worker_script
from spireshift.full_run_experience import atomic_json
from spireshift.training_objective import load_training_score_spec


def audit_learning_control(q: EngineQualificationConfig, config_path: Path) -> dict[str, Any]:
    d = load_learning_config(config_path, q)
    if d["stage"] != "short_learning_control":
        raise ValueError("Learning admission requires a separate short control")
    root = q.root / d["workspace"]
    report = identified(root / "summary.json")
    if (
        report["config_id"] != manifest_identifier(d)
        or report["status"] != "short_learning_control_pass"
        or report["completed_games"] != 4
        or report["failed_games"]
        or report["not_attempted_games"]
        or report["worker_failures"]
        or report["game_apps_created"]
        or report["optimizer_steps"] <= 0
        or report["sampled_decisions_verified"] <= 0
        or not all(report["checks"].values())
        or any(r["actor_l2_change"] <= 0 or r["critic_l2_change"] <= 0 for r in report["rounds"])
    ):
        raise ValueError("Native short learning control is incomplete")
    initial = NativeActorCritic.from_mapping(
        json.loads((root / "initial-checkpoint.json").read_text())
    )
    selected = NativeActorCritic.from_mapping(
        json.loads((root / "selected-checkpoint.json").read_text())
    )
    if (
        initial.model_id != report["initial_model_id"]
        or selected.model_id != report["selected_model_id"]
    ):
        raise ValueError("Saved native learning control checkpoints changed")
    audits = []
    for path in sorted(root.glob("*/worker-*/experience-audit.json")):
        audit = identified(path)
        if audit.get("valid") is not True:
            raise ValueError("Native saved experience delivery audit failed")
        for name, digest in audit["source_sha256"].items():
            if _sha_file(path.parent / name) != digest:
                raise ValueError("Audited native public/receipt/source bytes changed")
        for name, digest in d["helpers_sha256"].items():
            if _sha_file(path.parent / "source-at-launch" / name) != digest:
                raise ValueError("Audited native helper source changed")
        audits.append(audit)
    if sum(a["games"] for a in audits) != 4 or sum(a["decisions"] for a in audits) != sum(
        p["decisions"] for p in report["panels"]
    ):
        raise ValueError("Native experience audit denominator differs")
    verified = 0
    score = load_training_score_spec(q.root / d["training_spec"]["path"])
    for path in sorted((root / "round-001-sampled").glob("case-*.json")):
        binding = json.loads(path.read_text())["binding"]
        if (
            binding["config_id"] != manifest_identifier(d)
            or binding["model_id"] != initial.model_id
            or binding["seed_id"] not in d["learning"]["rollout_panels"][0]
            or binding["partition"] != "train"
        ):
            raise ValueError("Native control experience crosses policy/seed ownership")
        case = read_native_episode(path, binding)
        target = score_episode(case, binding["seed_id"], score)["training_return"]
        verified += len(
            verified_native_samples(case, initial, target, d["learning"]["ppo"]["temperature"])
        )
    if verified != report["sampled_decisions_verified"]:
        raise ValueError("Native control sampled decision denominator differs")
    return {
        "valid": True,
        "control_report_id": report["report_id"],
        "verified_sampled_decisions": verified,
        "delivery_audit_ids": [a["report_id"] for a in audits],
        "games_replayed": 0,
        "optimizer_steps": 0,
    }


def create_learning_admission(
    q: EngineQualificationConfig, control_path: Path, id_audit_path: Path, output: Path
) -> dict[str, Any]:
    d = load_learning_config(control_path, q)
    control = audit_learning_control(q, control_path)
    id_audit = json.loads(id_audit_path.read_text())
    current_worker = worker_script(d)
    new_policy = current_worker in {"engine-native-worker-v8.mjs", "engine-native-worker-v9.mjs"}
    observations = id_audit.get("observations", 0)
    if (
        id_audit.get("schema_version")
        != (
            "actual-engine-id-invariance-audit-v2"
            if new_policy
            else "actual-engine-id-invariance-audit-v1"
        )
        or id_audit.get("valid") is not True
        or (observations < 100 if new_policy else observations != 783)
        or id_audit.get("comparisons", 0) < observations * 3
        or id_audit.get("game_attempts") != 0
        or (
            new_policy
            and not {"shop_inventory", "rest_site", "reward_claim", "map_navigation", "combat_turn"}
            <= set(id_audit.get("families", {}))
        )
    ):
        raise ValueError("Public ID invariance is not verified over the frozen saved panel")
    for ref in id_audit["files"]:
        if _sha_file(Path(ref["path"])) != ref["sha256"]:
            raise ValueError("ID audit source trace bytes changed")
    helpers = {
        name: _sha_file(q.root / "scripts" / name)
        for name in _script_closure(
            q.root / "scripts",
            {
                "audit-engine-public-input-v2.mjs"
                if new_policy
                else "audit-engine-public-input-v1.mjs"
            },
        )
    }
    if id_audit.get("helpers_sha256") != helpers:
        raise ValueError(
            "ID audit does not bind the current public graph/diagnostic implementation"
        )
    scope_evidence = q.root / "docs/evidence/actual-engine-v0.111.0-progression-v1.json"
    body = {
        "schema_version": "actual-engine-bounded-learning-admission-v1",
        "status": "admitted_for_bounded_native_policy_only_pilot",
        "environment_id": d["environment_manifest"]["id"],
        "worker_report_id": d["worker_report"]["id"],
        "implementation_sha256": d["implementation_sha256"],
        "control_config": str(control_path.relative_to(q.root)),
        "control_audit": control,
        "id_audit": {
            "path": str(id_audit_path.relative_to(q.root)),
            "sha256": _sha_file(id_audit_path),
        },
        "bounded_environment_evidence": {
            "path": str(scope_evidence.relative_to(q.root)),
            "sha256": _sha_file(scope_evidence),
        },
        "maximum_planned_games": 336,
        "character": "Ironclad",
        "ascension": 8,
        "scope": "native_v0.111.0_policy_only_bootstrap_pilot",
        "evaluation_policy": d.get("evaluation_policy", {"behavior": "greedy"}),
        "mechanics_coverage": d.get("mechanics_coverage"),
        "base_readiness_passed": False,
        "adaptive_controller_allowed": False,
        "gameplay_strength_proven": False,
        "games_launched": 0,
        "optimizer_steps": 0,
    }
    result = {**body, "report_id": manifest_identifier(body)}
    atomic_json(output, result)
    return result


def preflight_native_learning(q: EngineQualificationConfig, path: Path) -> dict[str, Any]:
    d = load_learning_config(path, q)
    if d["stage"] != "bounded_policy_only_pilot":
        raise ValueError("Pilot preflight cannot launch or substitute a short control")
    admission = identified(q.root / d["admission"]["path"])
    control = audit_learning_control(q, q.root / admission["control_config"])
    if control != admission["control_audit"]:
        raise ValueError("Native admission control evidence changed")
    for key in ("id_audit", "bounded_environment_evidence"):
        ref = admission[key]
        if _sha_file(q.root / ref["path"]) != ref["sha256"]:
            raise ValueError("Native bounded admission evidence changed")
    wcfg = load_worker_config(q.root / d["worker_qualification_config"], q)
    _run_inputs(q, q.root / wcfg["base_run_recipe"])
    workspace = q.root / d["workspace"]
    return {
        "ready": not workspace.exists(),
        "workspace": str(workspace),
        "config_id": manifest_identifier(d),
        "planned_games": 336,
        "workers": 2,
        "maximum_wall_seconds": d["maximum_wall_seconds"],
        "games_launched": 0,
        "optimizer_steps": 0,
        "adaptive_controller_allowed": False,
    }


def show_native_learning(q: EngineQualificationConfig, path: Path) -> dict[str, Any]:
    d = json.loads(path.read_text())
    report = identified(q.root / d["workspace"] / "summary.json")
    if report["config_id"] != manifest_identifier(d):
        raise ValueError("Saved native experiment belongs to another recipe")
    return {
        k: report[k]
        for k in (
            "status",
            "error",
            "planned_games",
            "completed_games",
            "failed_games",
            "not_attempted_games",
            "sampled_decisions_verified",
            "optimizer_steps",
            "panels",
            "selected_model_id",
            "checkpoint_promoted",
            "base_readiness_passed",
            "adaptive_controller_allowed",
            "report_id",
        )
    }
