"""Compose preserved mechanics evidence with a reviewed presentation-only host delta.

The earlier sweep belongs to host v32, never v33. Carry forward its unchanged
game-model and combat-projection coverage, qualify the added belt/merchant seam
separately, and require fresh lifecycle, worker and learning controls afterward.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_cli_probe import verify_local_build_report
from spireshift.engine_coverage import _read_sealed, _saved_case
from spireshift.engine_mechanics_followups import assert_completed_sweep
from spireshift.engine_potion_checks import verify_potion_checks
from spireshift.engine_potion_queue_checks import verify_queue_checks
from spireshift.engine_progression import verify_native_progression
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.engine_worker import worker_helpers


def require_composed_mechanics(
    q: EngineQualificationConfig, inputs: dict[str, Any], reference: dict[str, Any] | None
) -> dict[str, Any]:
    if not isinstance(reference, dict) or set(reference) != {"config", "id"}:
        raise ValueError("The native belt needs its separate composed mechanics gate")
    cfg = json.loads((q.root / reference["config"]).read_text())
    if (
        manifest_identifier(cfg) != reference["id"]
        or cfg.get("schema_version") != "native-composed-mechanics-config-v1"
        or cfg.get("qualification_config_id") != q.config_id
        or cfg.get("input_config_id") != inputs["recipe"]["input_config_id"]
        or cfg.get("build_report_id") != inputs["inputs"]["build_report_id"]
        or cfg.get("helpers_sha256")
        != worker_helpers(q.root, cfg.get("worker_script", "engine-native-worker-v7.mjs"))
        or cfg.get("worker_script", "engine-native-worker-v7.mjs")
        not in {
            "engine-native-worker-v7.mjs",
            "engine-native-worker-v8.mjs",
            "engine-native-worker-v9.mjs",
        }
        or cfg.get("training_allowed") is not False
        or cfg.get("all_interactions_proven") is not False
        or inputs["inputs"].get("potion_surface_revision") != "native_belt_v1"
    ):
        raise ValueError("Composed mechanics scope, host or public inputs changed")

    sweep_cfg = json.loads((q.root / cfg["sweep"]["config"]).read_text())
    workspace = q.root / sweep_cfg["workspace"]
    report = _read_sealed(workspace / "sweep-summary.json")
    plan = _read_sealed(workspace / "plan.json", "plan_id")
    catalog = _read_sealed(workspace / "catalog.json")
    if (
        manifest_identifier(sweep_cfg) != cfg["sweep"]["config_id"]
        or report["report_id"] != cfg["sweep"]["report_id"]
        or catalog["assembly_sha256"] != inputs["build"]["runtime_sts2_sha256"]
        or plan["catalog_id"] != catalog["report_id"]
    ):
        raise ValueError("Inherited mechanics inventory belongs to different game rules")
    unresolved = {
        key
        for key, value in report["requirements"].items()
        if value["status"] not in {"exercised_native_diagnostic", "observed_all_planned_contexts"}
    }
    if unresolved != {
        "act_and_terminal_transitions",
        "random_legal_action_sequences",
        "out_of_combat_potion_use",
        "non_creature_potion_target",
    }:
        raise ValueError("The inherited sweep has additional unresolved requirements")
    cases = []
    for spec in plan["cases"]:
        path = workspace / "sweep" / f"case-{spec['case_id']}" / "result.json"
        if not path.exists():
            path = workspace / "smoke" / f"case-{spec['case_id']}" / "result.json"
        cases.append(_saved_case(path, spec, plan["plan_id"]))
    assert_completed_sweep(sweep_cfg, plan, report, cases)

    followup_cfg = json.loads((q.root / cfg["followups"]["config"]).read_text())
    followup = _read_sealed(q.root / followup_cfg["workspace"] / "summary.json")
    if (
        followup["report_id"] != cfg["followups"]["report_id"]
        or followup["config_id"] != manifest_identifier(followup_cfg)
        or followup["status"] != "scoped_followups_pass"
        or followup["sweep_report_id"] != report["report_id"]
        or set(followup["unresolved_requirements"])
        != {"out_of_combat_potion_use", "non_creature_potion_target"}
    ):
        raise ValueError("Preserved post-sweep evidence is incomplete")

    # Hash every old supplementary artifact again without running old code against
    # changed current sources, or relabelling the old report as a new-host sweep.
    for ref in cfg["preserved_evidence_files"]:
        if _sha_file(q.root / ref["path"]) != ref["sha256"]:
            raise ValueError("Preserved mechanics supplementary evidence changed")
    transfer = cfg["host_transfer"]
    old_build = json.loads((q.root / transfer["old_build_report"]).read_text())
    old_build_config = json.loads((q.root / transfer["old_build_config"]).read_text())
    verify_local_build_report(old_build, old_build_config, q)
    if old_build["report_id"] != transfer["old_build_report_id"]:
        raise ValueError("Inherited mechanics host identity changed")
    old = old_build["build"]["repaired"][0]
    if old["runtime_sts2_sha256"] != inputs["build"]["runtime_sts2_sha256"]:
        raise ValueError("Cannot transfer a mechanics sweep across changed game rules")
    for name, digests in transfer["native_sources"].items():
        if (
            _sha_file(Path(old["candidate_directory"]) / name) != digests["old"]
            or _sha_file(inputs["candidate"] / name) != digests["new"]
            or (name != "src/Sts2Headless/RunSimulator.cs" and digests["old"] != digests["new"])
        ):
            raise ValueError("Reviewed native presentation delta changed")
    for name, digest in transfer["unchanged_public_helpers"].items():
        if (
            sweep_cfg["helpers_sha256"].get(name) != digest
            or _sha_file(q.root / "scripts" / name) != digest
        ):
            raise ValueError("Inherited combat/selection public projection changed")
    potion = verify_potion_checks(q, q.root / cfg["potions"]["config"])
    if potion["report_id"] != cfg["potions"]["report_id"]:
        raise ValueError("Potion supplement belongs to another frozen run")
    potion_cfg = json.loads((q.root / cfg["potions"]["config"]).read_text())
    potion_report = _read_sealed(q.root / potion_cfg["workspace"] / "summary.json")
    if (
        potion_report["input_config_id"] != cfg["input_config_id"]
        or potion_report["build_report_id"] != cfg["build_report_id"]
    ):
        raise ValueError("Potion effects were checked on another host/input surface")
    lifecycle = verify_native_progression(q, q.root / cfg["lifecycle"]["config"])
    lifecycle_cfg = json.loads((q.root / cfg["lifecycle"]["config"]).read_text())
    if (
        lifecycle["native_report_id"] != cfg["lifecycle"]["report_id"]
        or lifecycle_cfg["build_report_id"] != cfg["build_report_id"]
    ):
        raise ValueError("New host lifecycle was not separately qualified")
    queue = None
    if cfg.get("worker_script") == "engine-native-worker-v9.mjs":
        if not isinstance(cfg.get("queued_potion_discard"), dict):
            raise ValueError("Shared-worker host requires its queued-discard controls")
        queue = verify_queue_checks(q, cfg["queued_potion_discard"], cfg["build_report_id"])
    return {
        "valid": True,
        "gate_id": reference["id"],
        "inherited_sweep_report_id": report["report_id"],
        "inherited_sweep_host": "v32",
        "current_host": "v34" if queue is not None else "v33",
        "verified_queued_discard_cases": queue["verified_cases"] if queue is not None else 0,
        "verified_sweep_cases": len(cases),
        "verified_potion_cases": potion["verified_cases"],
        "all_interactions_proven": False,
        "games_launched": 0,
        "optimizer_steps": 0,
        "training_allowed": False,
        "claim_scope": "scoped_inherited_native_models_plus_new_presentation_controls",
    }
