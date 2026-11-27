"""Checkpoint-bound learner admission from the assessed, frozen two-player workflow.

This is a new receipt contract. Historical recorded-only guards stay unchanged.
Original live evidence permits the declared diagnostic on copies, not live claims
for descendants, ordinary PPO, promotion, scaling or an adaptive controller.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _inventory, _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_compatibility_contract import compare_inputs, verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import load_state as load_old_state
from spireshift.native_flow_verification_v12 import records, same
from spireshift.native_render_inputs import load as load_render
from spireshift.native_structured_state import load as load_state

CONTRACT = "assessed_native_workflow_diagnostic_learner_guard_v1"
OPERATIONS = {"collect_original_curriculum", "fit_diagnostic_copy"}


def bind_candidate_freeze(root: Path, cfg: dict[str, Any], native: dict[str, Any]) -> str:
    """Bind the current verified CLI tree, not an inherited older build's tree.

    Earlier versioned loaders replace candidate/build but preserve the original
    constructor's candidate_before. No file is filtered, normalized or changed.
    The new recipe pins the entire actual CLI56 tree before any new unit.
    """
    snapshot = identified(verified(root, cfg["native_candidate_inventory"]))
    if (
        snapshot["schema_version"] != "current-native-candidate-freeze-v1"
        or snapshot["qualified_build_report_id"] != native["inputs"]["build_report_id"]
        or (root / snapshot["candidate"]).resolve() != native["candidate"].resolve()
        or snapshot["inventory"] != _inventory(native["candidate"])
    ):
        raise ValueError("The current qualified CLI build or its full input inventory changed")
    native["candidate_before"] = snapshot["inventory"]
    return str(snapshot["report_id"])


def state(path: Path) -> tuple[Any, Any, str]:
    try:
        return load_state(path)
    except ValueError:
        return load_old_state(path)


def assessment_checks(report: dict[str, Any], panel: dict[str, Any], cfg: dict[str, Any]) -> None:
    if (
        report.get("status") != "scoped_current_checkpoint_natural_workflow_verified"
        or report.get("source_panel_id") != panel.get("report_id")
        or report.get("config_id") != manifest_identifier(cfg)
        or report.get("environment_id") != panel.get("environment_id")
        or report.get("independently_reconstructed_actual_deliveries") != 584
        or report.get("matching_decision_pairs") != 292
        or report.get("genuine_matching_ending_pairs") != 2
        or report.get("scoped_natural_workflow_qualification_verified") is not True
        or panel.get("workflow_qualification_candidate") is not True
        or panel.get("genuine_matching_ending_pairs") != 2
        or len(panel.get("cases", [])) != 2
        or any(
            c.get("status") != "natural_workflow_pass"
            or c.get("clean_reset") is not True
            or c.get("comparison", {}).get("complete_workflow_equal") is not True
            or c.get("verification_errors") != {}
            for c in panel["cases"]
        )
    ):
        raise ValueError("Require the assessed exact two-original-player natural workflow")


def require_scope(receipt: dict[str, Any], binding: dict[str, Any], operation: str) -> None:
    if (
        receipt.get("schema_version") != "native-learner-guard-receipt-v1"
        or receipt.get("contract") != CONTRACT
        or receipt.get("binding") != binding
        or receipt.get("report_id")
        != manifest_identifier({k: v for k, v in receipt.items() if k != "report_id"})
        or operation not in OPERATIONS
        or receipt.get("environment_verified") is not True
        or receipt.get("recorded_original_inputs_verified") is not True
        or receipt.get("original_checkpoint_official_delivery_verified") is not True
        or receipt.get("diagnostic_copies_only") is not True
        or receipt.get("diagnostic_fitting_on_verified_copies_allowed") is not True
        or receipt.get("allowed_operations") != sorted(OPERATIONS)
        or receipt.get("ordinary_PPO_allowed") is not False
        or receipt.get("training_allowed") is not False
        or receipt.get("promotion_allowed") is not False
        or receipt.get("adaptive_controller_allowed") is not False
    ):
        raise ValueError(
            "Learner guard rejects changed identity, missing scope or broader permission"
        )


def pairs(root: Path, context: dict[str, Any]) -> list[dict[str, Any]]:
    base = root / context["parent_config"]["workspace"]
    result = []
    for case in context["parent_config"]["cases"]:
        streams = []
        for host, filename in [
            ("native", "shared-public.jsonl.gz"),
            ("official", "live-public.jsonl.gz"),
        ]:
            streams.append(
                [
                    r["frame"]
                    for r in records(base / case["key"] / host / filename)
                    if r["kind"] == "policy_input"
                ]
            )
        for index, (native, official) in enumerate(zip(*streams, strict=True)):
            if native["terminal"]:
                if official["terminal"] is not True:
                    raise ValueError("Recorded bank has inconsistent native endings")
                continue
            result.append(
                {
                    "key": f"{case['key']}-{index}",
                    "family": native["source_family"],
                    "native_input": native["public_input"],
                    "official_input": official["public_input"],
                    "native_action_keys": [a["key"] for a in native["actions"]],
                    "official_action_keys": [a["key"] for a in official["actions"]],
                    "missing_native_reads": [],
                    "missing_official_reads": [],
                }
            )
    if len(result) != 292:
        raise ValueError("The assessed complete 292-input bank changed")
    return result


def recorded(
    context: dict[str, Any], model: CachedContextModel, state_id: str, optimizer_id: str
) -> dict[str, Any]:
    if (
        model.actor.environment_id != context["environment"]["manifest_id"]
        or model.feature_spec_id != context["score"].spec_id
    ):
        raise ValueError("No implicit model environment/encoder/score migration")
    checks = [compare_inputs(model, context["score"], pair) for pair in context["recorded_pairs"]]
    if not checks or not all(c["passed"] for c in checks):
        raise ValueError(
            "Current checkpoint fails exact paired input/encoding/distribution regression"
        )
    body = {
        "schema_version": "native-learner-recorded-check-v1",
        "guard_binding_id": manifest_identifier(context["guard_binding"]),
        "state_id": state_id,
        "model_id": model.model_id,
        "optimizer_id": optimizer_id,
        "paired_inputs": len(checks),
        "checks_id": manifest_identifier(checks),
        "all_inputs_features_distributions_equal": True,
        "static_recorded_states_only": True,
        "current_checkpoint_live_delivery_qualified": False,
        "fitting_labels_from_compatibility_worlds": False,
    }
    return {**body, "report_id": manifest_identifier(body)}


def qualify(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    parent_recipe = verified(root, cfg["compatibility_recipe"])
    context = load_render(root, parent_recipe)
    candidate_freeze_id = bind_candidate_freeze(root, cfg, context["native"])
    parent = context["config"]
    if cfg["node"] != parent["node"]:
        raise ValueError("The learner must use the qualified Node executable")
    assessment_path = verified(root, cfg["compatibility_assessment"])
    assessed = identified(assessment_path)
    panel_path = root / parent["workspace"] / "report.json"
    panel = identified(panel_path)
    assessment_checks(assessed, panel, parent)
    for document in [assessed, panel]:
        check_sources(root, document["sources"])
        check_sources(root, document["evidence"])
    check_sources(root, json.loads(verified(root, cfg["protection"]).read_text()))
    models, optimizers, originals = {}, {}, {}
    for number, ref in parent["players"].items():
        original, adam, sid = state(verified(root, ref))
        imported_path = root / parent["workspace"] / f"imports/player-{number}.json"
        model, copied, imported_sid = load_state(imported_path)
        if original.weights() != model.weights() or not same(adam.as_dict(), copied.as_dict()):
            raise ValueError("Compatibility import changed numerical weights or complete Adam")
        models[int(number)], optimizers[int(number)] = model, copied
        originals[number] = {
            "original_state_id": sid,
            "original_sha256": ref["sha256"],
            "imported_state_id": imported_sid,
            "imported_model_id": model.model_id,
            "optimizer_id": manifest_identifier(copied.as_dict()),
            "optimizer_steps": copied.steps,
            "imported_path": str(imported_path.relative_to(root)),
            "imported_sha256": _sha_file(imported_path),
        }
    sources = {
        **context["sources"],
        **cfg["implementation"],
        str(assessment_path.relative_to(root)): _sha_file(assessment_path),
        str(panel_path.relative_to(root)): _sha_file(panel_path),
        cfg["protection"]["path"]: cfg["protection"]["sha256"],
        cfg["native_candidate_inventory"]["path"]: cfg["native_candidate_inventory"]["sha256"],
        **{v["imported_path"]: v["imported_sha256"] for v in originals.values()},
    }
    binding = {
        "contract": CONTRACT,
        "environment_id": context["environment"]["manifest_id"],
        "assessment_id": assessed["report_id"],
        "natural_panel_id": panel["report_id"],
        "players": originals,
        "implementation_id": manifest_identifier(cfg["implementation"]),
        "study_contract": cfg["contract"],
        "study_plan_id": manifest_identifier(cfg["plan"]),
        "execution_runtime_id": manifest_identifier(cfg["execution_runtime"]),
        "current_native_candidate_freeze_id": candidate_freeze_id,
    }
    context.update(
        parent_config=parent,
        models=models,
        adams=optimizers,
        guard_binding=binding,
        sources=sources,
    )
    context["recorded_pairs"] = pairs(root, context)
    directory = (
        root / "artifacts/native-varied-teaching/guard-v1" / manifest_identifier(binding)[7:]
    )
    report_path = directory / "report.json"
    if report_path.exists():
        receipt = identified(report_path)
        require_scope(receipt, binding, "fit_diagnostic_copy")
        check_sources(root, receipt["sources"])
        check_sources(root, receipt["evidence"])
    else:
        directory.mkdir(parents=True, exist_ok=False)
        regressions = {
            p: recorded(context, models[int(p)], row["imported_state_id"], row["optimizer_id"])
            for p, row in originals.items()
        }
        body = {
            "schema_version": "native-learner-guard-receipt-v1",
            "status": "scoped_original_workflow_admitted_for_declared_copy_diagnostic",
            "contract": CONTRACT,
            "binding": binding,
            "sources": sources,
            "evidence": {
                **panel["evidence"],
                str(assessment_path.relative_to(root)): _sha_file(assessment_path),
            },
            "environment_verified": True,
            "recorded_original_inputs_verified": True,
            "original_checkpoint_official_delivery_verified": True,
            "original_recorded_regressions": regressions,
            "diagnostic_copies_only": True,
            "diagnostic_fitting_on_verified_copies_allowed": True,
            "allowed_operations": sorted(OPERATIONS),
            "descendant_live_scope_inherited": False,
            "ordinary_PPO_allowed": False,
            "training_allowed": False,
            "promotion_allowed": False,
            "adaptive_controller_allowed": False,
            "new_games": 0,
            "optimizer_updates": 0,
            "wall_seconds": time.monotonic() - started,
        }
        receipt = {**body, "report_id": manifest_identifier(body)}
        atomic_json(report_path, receipt)
    context.update(guard_receipt=receipt, guard_path=str(report_path.relative_to(root)))
    return context


def require_copy(
    context: dict[str, Any], model: CachedContextModel, adam: Any, saved: dict[str, Any]
) -> None:
    require_scope(context["guard_receipt"], context["guard_binding"], "fit_diagnostic_copy")
    if (
        saved.get("report_id")
        != manifest_identifier({k: v for k, v in saved.items() if k != "report_id"})
        or saved.get("schema_version") != "native-learner-recorded-check-v1"
        or saved.get("model_id") != model.model_id
        or saved.get("optimizer_id") != manifest_identifier(adam.as_dict())
        or saved.get("guard_binding_id") != manifest_identifier(context["guard_binding"])
        or saved.get("all_inputs_features_distributions_equal") is not True
        or saved.get("paired_inputs") != 292
        or saved.get("current_checkpoint_live_delivery_qualified") is not False
    ):
        raise ValueError("Fitting predecessor lacks its exact model/full-Adam recorded regression")
