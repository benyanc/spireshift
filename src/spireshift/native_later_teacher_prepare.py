"""Freeze eight later-turn TRAIN-only public combat roots without launching games or fitting."""

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_action_context import policy
from spireshift.native_combat_teacher_data import INFORMATION, prefix_root
from spireshift.native_context_journal import load_state
from spireshift.native_context_reuse import check_sources
from spireshift.native_feedback_audit import source_cohorts
from spireshift.native_later_teacher_roots import QUOTAS_BY_PLAYER, SELECTION, first_positions
from spireshift.training_objective import load_training_score_spec


def prepare(root: Path, output: Path, *, deadline: float) -> dict[str, Any]:
    if not output.is_relative_to(root) or output != _private_path(
        root, str(output.relative_to(root))
    ):
        raise ValueError("Later root evidence must stay in its private artifact workspace")
    cfg_path = root / "configs/native-controls/completed-learning-feedback-audit-v1.json"
    cfg = json.loads(cfg_path.read_text())
    audit_path = root / cfg["workspace"] / "report.json"
    audit = identified(audit_path)
    if (
        audit["status"] != "completed_train_feedback_complete"
        or audit["stage"] != "completed_train_audit"
        or audit["games"] != 512
        or audit["completed_batches"] != 16
        or not audit["production_states_unchanged"]
        or not audit["decision"]["finite_input_checks_passed"]
    ):
        raise ValueError("Require the completed current TRAIN feedback audit")
    check_sources(root, audit["sources"])
    if (output / "report.json").exists():
        saved = identified(output / "report.json")
        if saved.get("selection") != SELECTION or saved.get("schema_version") != (
            "native-later-combat-teacher-roots-v2"
        ):
            raise ValueError("Preserve a different saved root corpus")
        check_sources(root, saved["sources"])
        return saved
    output.mkdir(parents=True, exist_ok=False)
    cohorts, parent, sources = source_cohorts(root, cfg)
    score = load_training_score_spec(root / parent["training_spec"]["path"])
    selected: list[dict[str, Any]] = []
    models = []
    for n in (2, 3):
        cohort = next(
            c
            for c in cohorts
            if c["numerical_seed"] == n and c["round"] == 60 and c["arm"] == "standard"
        )
        model, optimizer, state_id = load_state(root / cohort["after"]["state_path"])
        if state_id != cohort["after"]["state_id"]:
            raise ValueError("Continuation model/full Adam state changed")
        models.append({"numerical_seed": n, **cohort["after"]})
        needed = Counter(QUOTAS_BY_PLAYER[str(n)])
        paths = sorted(
            cohort["paths"],
            key=lambda p: hashlib.sha256(f"native-teacher-root-order-v1|{p}".encode()).digest(),
        )
        for name in paths:
            if time.monotonic() >= deadline:
                raise TimeoutError("Later-root selection reached its cap; preserve evidence")
            header = json.loads((root / name).read_text())
            binding = header["binding"]
            case = read_native_episode(root / name, binding)
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    "Later-root selection reached its short cap; preserve partial evidence"
                )
            candidates = {
                kind: value
                for kind, value in first_positions(case["decisions"]).items()
                if needed[kind]
            }
            kind = next((k for k in ("boss", "elite", "normal") if k in candidates), None)
            if kind is None:
                del case
                continue
            index, selection_evidence = candidates[kind]
            value = prefix_root(case, binding, index)
            _, _, logs = policy(
                value["public_input"], model, score, parent["learning"]["ppo"]["temperature"]
            )
            body = {
                **value,
                "root_selection": SELECTION,
                "selection_evidence": selection_evidence,
                "source_episode": name,
                "source_case_id": header["case_id"],
                "source_seed_id": binding["seed_id"],
                "native_seed": binding["native_seed"],
                "decision_index": index,
                "numerical_seed": n,
                "encounter_type": kind,
                "reference_action": max(range(len(logs)), key=lambda j: (logs[j], -j)),
                "model_state": cohort["after"],
                "continuation_model_id": model.model_id,
                "original_optimizer_steps": optimizer.steps,
                "information_scope": INFORMATION,
            }
            value = {**body, "root_id": manifest_identifier(body)}
            path = output / f"root-{len(selected):03d}.json"
            atomic_json(path, value)
            selected.append(
                {
                    "path": str(path.relative_to(root)),
                    "id": value["root_id"],
                    "numerical_seed": n,
                    "encounter_type": kind,
                    "source_seed_id": binding["seed_id"],
                    "actions": len(logs),
                    "prefix_decisions": index,
                    "selection_evidence": selection_evidence,
                }
            )
            needed[kind] -= 1
            del case
            if not any(needed.values()):
                break
        if any(needed.values()):
            raise ValueError(
                f"Declared eight-root curriculum unavailable: initializer {n}, {dict(needed)}"
            )
    if len({r["source_seed_id"] for r in selected}) != len(selected):
        raise ValueError("Use one public root per distinct natural TRAIN seed")
    sources.update({str(p.relative_to(root)): _sha_file(p) for p in output.glob("root-*.json")})
    sources[str(audit_path.relative_to(root))] = _sha_file(audit_path)
    sources[str(cfg_path.relative_to(root))] = _sha_file(cfg_path)
    for name in (
        "native_later_teacher_prepare.py",
        "native_later_teacher_roots.py",
        "native_combat_teacher_data.py",
    ):
        sources[f"src/spireshift/{name}"] = _sha_file(root / "src/spireshift" / name)
    report = {
        "schema_version": "native-later-combat-teacher-roots-v2",
        "roots": selected,
        "models": models,
        "training_spec": parent["training_spec"],
        "environment_manifest": parent["environment_manifest"],
        "temperature": parent["learning"]["ppo"]["temperature"],
        "selection": SELECTION,
        "selection_uses_final_outcomes": False,
        "ordinary_PPO_eligible": False,
        "encounter_quotas_per_initializer": QUOTAS_BY_PLAYER,
        "curriculum_availability_revision": "player_3_has_no_eligible_later_boss_use_third_normal",
        "source_audit_report_id": audit["report_id"],
        "information_scope": INFORMATION,
        "new_games": 0,
        "optimizer_steps": 0,
        "sources": sources,
        "training_allowed": False,
        "checkpoint_promoted": False,
        "adaptive_controller_allowed": False,
    }
    result = {**report, "report_id": manifest_identifier(report)}
    check_sources(root, sources)
    atomic_json(output / "report.json", result)
    return result
