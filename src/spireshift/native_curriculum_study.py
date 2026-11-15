"""Guarded, separately selected curriculum, fitting, canary and evaluation phases."""

from __future__ import annotations

import argparse
import copy
import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_curriculum_collect import collect
from spireshift.native_curriculum_config import PHASES, load
from spireshift.native_curriculum_evaluate import canary, evaluate
from spireshift.native_curriculum_fit import fit
from spireshift.native_curriculum_policy import RoutedChooser
from spireshift.native_flow_verification_v12 import records
from spireshift.native_learner_guard import require_scope
from spireshift.native_structured_policy import Chooser
from spireshift.native_structured_state import load as load_state


def require_control(context: dict[str, Any]) -> None:
    root, cfg = context["qualification"].root, context["config"]
    if cfg["stage"] == "short_control":
        return
    control_cfg = json.loads(verified(root, cfg["control_recipe"]).read_text())
    p = root / control_cfg["workspace"] / "control/report.json"
    report = identified(p)
    if (
        report["status"] != "learner_curriculum_control_pass"
        or report["config_id"] != manifest_identifier(control_cfg)
        or control_cfg["implementation"] != cfg["implementation"]
        or not all(report["checks"].values())
    ):
        raise ValueError(
            "The exact learner guard, branch and warm-Adam integration control must pass"
        )
    check_sources(root, report["sources"])
    check_sources(root, report["evidence"])


def short_control(context: dict[str, Any], deadline: float) -> dict[str, Any]:
    root, cfg = context["qualification"].root, context["config"]
    if cfg["stage"] != "short_control":
        raise ValueError(
            "Use the separately pinned control worlds; never fit on final/canary worlds"
        )
    target = root / cfg["workspace"] / "control"
    if (target / "report.json").exists():
        saved = identified(target / "report.json")
        check_sources(root, saved["sources"])
        check_sources(root, saved["evidence"])
        return saved
    collected = collect(context, deadline=deadline)
    if collected["status"] != "curriculum_qualified":
        raise ValueError(
            "The finite native control did not complete its declared source/branch checks"
        )
    partial = fit(context, max_units=3, deadline=deadline)
    if partial.get("status") != "clean_session_boundary":
        raise ValueError("The control must exercise a clean fitting pause")
    first = root / cfg["workspace"] / "fitting/chunks/fit-p2-reference-e01/state.json"
    first_digest = _sha_file(first)
    fitted = fit(context, deadline=deadline)
    if fitted["status"] != "diagnostic_finals_frozen" or _sha_file(first) != first_digest:
        raise ValueError("Fitting resume rewrote a sealed copied checkpoint")
    target.mkdir(exist_ok=False)
    probes = []
    for case in cfg["plan"]["worlds"]:
        p = case["player"]
        taught = load_state(root / fitted["finals"][f"p{p}-teacher"]["state_path"])[0]
        original = context["models"][p]
        directory = (
            root / cfg["workspace"] / "collection/chunks" / ("source-" + case["key"]) / "native"
        )
        frames = [
            r["frame"]
            for r in records(directory / "shared-public.jsonl.gz")
            if r["kind"] == "policy_input" and not r["frame"]["terminal"]
        ]
        for combat in [False, True]:
            frame = next(f for f in frames if (f["source_family"] == "combat_turn") is combat)
            public = frame["public_input"]
            routed = RoutedChooser(taught, original, context["score"], case["seed"])
            reference = Chooser(
                taught if combat else original, context["score"], case["seed"], False
            )
            a, b = routed(public), reference(public)
            fields = [
                "action_index",
                "draw_key",
                "log_probability",
                "policy_log_probability",
                "value",
                "effective_input_id",
            ]
            if any(a[k] != b[k] for k in fields) or a["routed_actor"] != (
                "taught" if combat else "original"
            ):
                raise ValueError(
                    "The interference routing changes the declared actor "
                    "or RNG/navigation semantics"
                )
            probes.append(
                {"player": p, "combat_owned": combat, "exact_actor_choices_and_numbers": True}
            )
    blocked = []
    for operation, mutation in [
        ("promote", None),
        ("fit_diagnostic_copy", "original_checkpoint_official_delivery_verified"),
        ("fit_diagnostic_copy", "recorded_original_inputs_verified"),
    ]:
        receipt = copy.deepcopy(context["guard_receipt"])
        if mutation:
            receipt[mutation] = False
            receipt["report_id"] = manifest_identifier(
                {k: v for k, v in receipt.items() if k != "report_id"}
            )
        try:
            require_scope(receipt, context["guard_binding"], operation)
        except ValueError:
            blocked.append(True)
        else:
            raise ValueError("A missing-scope or promotion command passed the learner guard")
    check_sources(root, json.loads(verified(root, cfg["protection"]).read_text()))
    checks = {
        "current_original_guard_scopes_verified": True,
        "all_control_sources_and_branch_deliveries_reconstructed": True,
        "warm_full_Adam_pause_restore_and_sealed_predecessor_exact": True,
        "matched_16_copied_optimizer_updates": fitted["optimizer_updates"] == 16,
        "original_numerical_weights_and_full_Adam_unchanged": True,
        "shared_and_routed_actor_rng_navigation_probes": len(probes) == 4,
        "missing_scopes_and_promotion_block_before_work": len(blocked) == 3,
        "no_changed_player_live_scope_inherited": fitted["new_checkpoint_live_delivery_qualified"]
        is False,
    }
    if not all(checks.values()):
        raise ValueError("Learner/curriculum control failed; main remains blocked")
    body = {
        "schema_version": "native-varied-teaching-control-v1",
        "status": "learner_curriculum_control_pass",
        "config_id": context["config_id"],
        "guard_receipt_id": context["guard_receipt"]["report_id"],
        "environment_id": context["environment"]["manifest_id"],
        "checks": checks,
        "routing_probes": probes,
        "collection_report_id": collected["report_id"],
        "fitting_report_id": fitted["report_id"],
        "optimizer_updates_on_control_copies": 16,
        "control_finals_used_by_main": False,
        "new_official_app_games": 0,
        "playing_strength_claimed": False,
        "training_allowed": False,
        "promotion_allowed": False,
        "automatic_follow_up": False,
        "sources": context["sources"],
        "evidence": {
            **collected["evidence"],
            **fitted["evidence"],
            **{
                str(p.relative_to(root)): _sha_file(p)
                for p in [
                    root / cfg["workspace"] / "collection/report.json",
                    root / cfg["workspace"] / "fitting/report.json",
                ]
            },
        },
    }
    body["report_id"] = manifest_identifier(body)
    atomic_json(target / "report.json", body)
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--phase", choices=(*PHASES, "control", "guard"), default="collect")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--max-units", type=int)
    args = parser.parse_args()
    started, root = time.monotonic(), Path.cwd()
    try:
        context = load(root, args.recipe.resolve())
        if args.phase == "guard":
            print(
                json.dumps(
                    {
                        "status": "current_original_learner_guard_verified",
                        "guard_receipt_id": context["guard_receipt"]["report_id"],
                        "new_games": 0,
                        "optimizer_updates": 0,
                    }
                )
            )
            return 0
        if args.phase != "control":
            require_control(context)
        if args.preflight:
            print(
                json.dumps(
                    {
                        "valid": True,
                        "guard_receipt_id": context["guard_receipt"]["report_id"],
                        "phase": args.phase,
                        "prospective_source_worlds": len(context["config"]["plan"]["worlds"]),
                        "fit_on_compatibility_or_withheld_worlds": False,
                        "new_games": 0,
                        "optimizer_updates": 0,
                        "automatic_follow_up": False,
                    }
                )
            )
            return 0
        deadline = started + context["config"]["session_limits"]["wall_seconds"] - 15
        if args.phase == "control":
            value = short_control(context, deadline)
        else:
            function = {"collect": collect, "fit": fit, "canary": canary, "evaluate": evaluate}[
                args.phase
            ]
            value = function(context, max_units=args.max_units, deadline=deadline)
        print(
            json.dumps(
                {
                    k: v
                    for k, v in value.items()
                    if k
                    not in {
                        "sources",
                        "evidence",
                        "finals",
                        "cells",
                        "source_games",
                        "cases",
                        "withheld_fights",
                    }
                },
                indent=2,
            )
        )
        return (
            2
            if value["status"]
            in {"curriculum_quality_blocked", "evaluation_stopped_failure_allowance"}
            else 0
        )
    except (ValueError, OSError, KeyError, TimeoutError) as error:
        print(
            json.dumps(
                {
                    "status": "blocked_preserving_evidence",
                    "error": str(error),
                    "automatic_follow_up": False,
                }
            ),
            flush=True,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
