"""Frozen-final live canaries and a separate common-world routing-interference test."""

from __future__ import annotations

import json
import time
from typing import Any

from spireshift.engine_native import _running_games
from spireshift.full_run_experience import atomic_json
from spireshift.native_combat_behavior_data import intervals
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_curriculum_config import VARIANTS
from spireshift.native_curriculum_native import adapter_context, branch, verify_branch
from spireshift.native_curriculum_policy import policy
from spireshift.native_curriculum_store import (
    Pause,
    admit_result,
    final,
    finish,
    journal,
    reserve,
    snapshot,
)
from spireshift.native_curriculum_verification import verify_host
from spireshift.native_e2e_contract import compare_observations, terminal_facts
from spireshift.native_flow_verification_v12 import records
from spireshift.native_render_endings import native_run
from spireshift.native_shop_ending_session import official_prefix
from spireshift.native_shop_verification import verify_shop_proofs


def require_canaries(
    report: dict[str, Any], config_id: str, finals_id: str, expected: list[dict[str, Any]]
) -> None:
    if (
        report.get("status") != "trained_policy_canaries_verified"
        or report.get("config_id") != config_id
        or report.get("frozen_finals_id") != finals_id
        or [r.get("case") for r in report.get("cases", [])] != expected
        or any(c.get("status") != "matching_genuine_endings" for c in report["cases"])
        or report.get("all_current_policy_modes_live_qualified") is not True
        or report.get("promotion_allowed") is not False
    ):
        raise ValueError("Changed final or routed policy lacks its own exact live canary")


def canary(
    context: dict[str, Any], *, max_units: int | None = None, deadline: float | None = None
) -> dict[str, Any]:
    saved = final(context, "canaries")
    if saved is not None:
        return saved
    fitted = final(context, "fitting")
    if (
        fitted is None
        or fitted["status"] != "diagnostic_finals_frozen"
        or context["config"]["stage"] == "short_control"
    ):
        raise ValueError("Seal all main finals before current-checkpoint official canaries")
    root, cfg = context["qualification"].root, context["config"]
    store, sources, cases, new = journal(context, "canaries"), dict(context["sources"]), [], 0
    sources.update(fitted["sources"])
    sources.update(fitted["evidence"])
    adapted = {**adapter_context(context), "evaluation_finals": fitted["finals"]}
    deadline = deadline or time.monotonic() + cfg["session_limits"]["wall_seconds"] - 15
    with store.lock():
        sources.update(snapshot(context, store))
        try:
            for case in cfg["plan"]["canary_cases"]:
                request = {
                    "case": case,
                    "frozen_finals_id": fitted["frozen_finals_id"],
                    "guard_id": context["guard_receipt"]["report_id"],
                }
                receipt = store.completed(case["key"], request)
                if receipt is None:
                    reserve(deadline, 650, new, max_units)
                    if _running_games():
                        raise ValueError("Close STS2 before a changed-player official canary")
                    target = store.begin(case["key"], request)
                    boundary = time.monotonic() + cfg["plan"]["maximum_pair_wall_seconds"]
                    native = native_run(
                        adapted,
                        case,
                        target / "native",
                        policy(
                            context, case["player"], case["variant"], case["seed"], fitted["finals"]
                        ),
                        boundary,
                    )
                    if (
                        native["status"] != "native_natural_ending_pass"
                        or native["shutdown"]["clean_exit"] is not True
                    ):
                        raise ValueError(
                            "Changed-player native canary incomplete; preserve without retry"
                        )
                    official = official_prefix(
                        adapted,
                        case,
                        target / "official",
                        policy(
                            context, case["player"], case["variant"], case["seed"], fitted["finals"]
                        ),
                        boundary,
                    )
                    if official["status"] != "official_prefix_pass" or not all(
                        official["checks"].values()
                    ):
                        raise ValueError(
                            "Changed-player official canary incomplete; preserve without retry"
                        )
                    verification = target / "verification"
                    verification.mkdir()
                    counts, frames = {}, {}
                    for host, filename in [
                        ("native", "shared-public.jsonl.gz"),
                        ("official", "live-public.jsonl.gz"),
                    ]:
                        counts[host] = verify_host(
                            root, adapted, case, host, target / host, verification, boundary
                        )
                        frames[host] = [
                            r["frame"]
                            for r in records(target / host / filename)
                            if r["kind"] in {"policy_input", "final_observation"}
                        ]
                    verify_shop_proofs(
                        root,
                        context["parent_config"]["node"],
                        target / "official",
                        verification,
                        boundary,
                    )
                    comparison = compare_observations(frames["native"], frames["official"])
                    if comparison["complete_workflow_equal"] is not True:
                        atomic_json(target / "mismatch.json", comparison)
                        raise ValueError(
                            "Changed-player exact canary mismatch; no divergent suffix alignment"
                        )
                    result = {
                        "case": case,
                        "status": "matching_genuine_endings",
                        "counts": counts,
                        "comparison": comparison,
                        "official_report_id": official["report_id"],
                        "native_report_id": native["report_id"],
                        "clean_reset": True,
                    }
                    store.commit(case["key"], request, result, context["sources"])
                    receipt = store.completed(case["key"], request)
                    assert receipt is not None
                    new += 1
                cases.append(receipt["result"])
                admit_result(root, sources, store, case["key"], receipt)
            return finish(
                context,
                store,
                {
                    "schema_version": "native-varied-final-canaries-v1",
                    "status": "trained_policy_canaries_verified",
                    "frozen_finals_id": fitted["frozen_finals_id"],
                    "cases": cases,
                    "all_current_policy_modes_live_qualified": True,
                    "qualification_scope": "named_frozen_finals_policy_modes_declared_worlds_only",
                    "broader_live_admission": False,
                    "optimizer_updates": 0,
                },
                sources,
            )
        except Pause:
            value = {
                "status": "clean_session_boundary",
                "phase": "canary",
                "new_units": new,
                "automatic_follow_up": False,
            }
            atomic_json(store.workspace / "progress.json", value)
            return value


def summary(
    seeds: list[str], rows: list[dict[str, Any]], *, bootstrap: bool = True
) -> dict[str, Any]:
    cells = {(r["seed"], r["player"], r["variant"]): r for r in rows}
    expected = {(s, p, a) for s in seeds for p in (2, 3) for a in VARIANTS}
    if len(cells) != len(rows) or not cells.keys() <= expected or not seeds:
        raise ValueError("Duplicate or replacement evaluations do not create independent worlds")
    arms = {}
    for arm in VARIANTS:
        observed = [r for r in rows if r["variant"] == arm]
        clean = [r for r in observed if r["status"] == "terminal"]
        arms[arm] = {
            "denominator": len(seeds) * 2,
            "recorded": len(observed),
            "not_attempted": len(seeds) * 2 - len(observed),
            "failed_or_capped": len(observed) - len(clean),
            "wins": sum(r["victory"] for r in clean),
            "mean_floor_including_failures": sum(r["floor"] for r in clean) / (len(seeds) * 2),
        }
    contrasts = {}
    if cells.keys() == expected:
        for a, b in [
            ("teacher", "reference"),
            ("teacher", "original"),
            ("reference", "original"),
            ("teacher_original_noncombat", "teacher"),
        ]:
            by_world = []
            for seed in seeds:
                row = []
                for field in ["victory", "floor"]:
                    row.append(
                        sum(
                            (
                                float(cells[seed, p, a][field])
                                if cells[seed, p, a]["status"] == "terminal"
                                else 0.0
                            )
                            - (
                                float(cells[seed, p, b][field])
                                if cells[seed, p, b]["status"] == "terminal"
                                else 0.0
                            )
                            for p in (2, 3)
                        )
                        / 2
                    )
                by_world.append(row)
            bounds = intervals(by_world) if bootstrap else [None, None]
            contrasts[f"{a}_minus_{b}"] = {
                field: {"mean": sum(r[i] for r in by_world) / len(seeds), "interval95": bounds[i]}
                for i, field in enumerate(["victory", "floor"])
            }
    return {
        "arms": arms,
        "paired_contrasts": contrasts,
        "complete": cells.keys() == expected,
        "primary_metric": "terminal_victory",
        "floor_auxiliary_only": True,
        "independent_unit": "world_jointly_across_two_fixed_initializers",
        "all_zero_wins_do_not_prove_equal_population_win_probabilities": True,
        "interference_contrast": "teacher_original_noncombat_minus_teacher",
        "interference_is_separate_routing_ablation_not_extra_fitting": True,
        "untouched_original_required": True,
    }


def evaluate(
    context: dict[str, Any], *, max_units: int | None = None, deadline: float | None = None
) -> dict[str, Any]:
    saved = final(context, "evaluation")
    if saved is not None:
        return saved
    fitted, canaries = final(context, "fitting"), final(context, "canaries")
    if fitted is None or canaries is None:
        raise ValueError("Frozen finals and their new official canaries must precede evaluation")
    root, cfg = context["qualification"].root, context["config"]
    require_canaries(
        canaries, context["config_id"], fitted["frozen_finals_id"], cfg["plan"]["canary_cases"]
    )
    store, sources, rows, held, new = (
        journal(context, "evaluation"),
        dict(context["sources"]),
        [],
        [],
        0,
    )
    sources.update(fitted["sources"])
    sources.update(fitted["evidence"])
    sources.update(canaries["sources"])
    sources.update(canaries["evidence"])
    collection = final(context, "collection")
    assert collection is not None
    withheld = [
        r
        for r in json.loads((root / collection["roots_path"]).read_text())["roots"]
        if r["partition"] == "heldout"
    ]
    adapted = adapter_context(context)
    deadline = deadline or time.monotonic() + cfg["session_limits"]["wall_seconds"] - 15
    with store.lock():
        sources.update(snapshot(context, store))
        try:
            for i, source in enumerate(withheld):
                for p in (2, 3):
                    for arm in VARIANTS:
                        key = f"withheld-{i:02d}-p{p}-{arm.replace('_', '-')}"
                        request = {
                            "root_id": source["root_id"],
                            "player": p,
                            "variant": arm,
                            "frozen_finals_id": fitted["frozen_finals_id"],
                            "canary_report_id": canaries["report_id"],
                        }
                        receipt = store.completed(key, request)
                        if receipt is None:
                            reserve(deadline, 85, new, max_units)
                            check_sources(root, cfg["implementation"])
                            if _running_games():
                                raise ValueError("Close STS2 before a declared withheld encounter")
                            target = store.begin(key, request)
                            actor = policy(context, p, arm, source["world"], fitted["finals"])
                            from spireshift.native_structured_state import load

                            original = (
                                load(root / fitted["finals"][f"p{p}-original"]["state_path"])[0]
                                if arm == "teacher_original_noncombat"
                                else None
                            )
                            outcome = branch(
                                context,
                                source,
                                target,
                                deadline,
                                proposal=[],
                                candidate=0,
                                model=actor.model,
                                original=original,
                            )
                            value = {
                                "root_id": source["root_id"],
                                "world": source["world"],
                                "player": p,
                                "variant": arm,
                                "status": outcome["status"],
                                "outcome": outcome["outcome"],
                                "resources": outcome["resources"],
                                "branch_id": outcome["report_id"],
                                "fitting_labels_or_teacher_actions_forced_after_root": False,
                            }
                            store.commit(key, request, value, context["sources"])
                            receipt = store.completed(key, request)
                            assert receipt is not None
                            new += 1
                        held.append(receipt["result"])
                        admit_result(root, sources, store, key, receipt)
            for i, seed in enumerate(cfg["plan"]["evaluation_seeds"]):
                for p in (2, 3):
                    offset = (i + p) % len(VARIANTS)
                    for arm in VARIANTS[offset:] + VARIANTS[:offset]:
                        key = f"fresh-{i:02d}-p{p}-{arm.replace('_', '-')}"
                        request = {
                            "seed": seed,
                            "player": p,
                            "variant": arm,
                            "frozen_finals_id": fitted["frozen_finals_id"],
                            "canary_report_id": canaries["report_id"],
                        }
                        receipt = store.completed(key, request)
                        if receipt is None:
                            reserve(deadline, 180, new, max_units)
                            check_sources(root, cfg["implementation"])
                            if _running_games():
                                raise ValueError(
                                    "Close STS2 before a declared fresh native evaluation"
                                )
                            target = store.begin(key, request)
                            case = {"key": key, "seed": seed, "player": p}
                            result = native_run(
                                adapted,
                                case,
                                target / "native",
                                policy(context, p, arm, seed, fitted["finals"]),
                                min(deadline, time.monotonic() + 150),
                            )
                            if result["shutdown"]["clean_exit"] is not True:
                                raise ValueError("Uncertain evaluation shutdown; preserve and stop")
                            # Rebuild even an incomplete capped prefix, without
                            # substituting its last state for a genuine ending.
                            count = verify_branch(
                                context,
                                target / "native",
                                policy(context, p, arm, seed, fitted["finals"]),
                                deadline,
                            )
                            clean = result["status"] == "native_natural_ending_pass"
                            frames = [
                                r["frame"]
                                for r in records(target / "native/shared-public.jsonl.gz")
                                if "frame" in r
                            ]
                            facts = terminal_facts(frames[-1]) if clean else None
                            value = {
                                "seed": seed,
                                "player": p,
                                "variant": arm,
                                "status": "terminal" if clean else "failed_or_capped",
                                "victory": facts["victory"] if facts else False,
                                "floor": facts["persistent"]["run"]["floor"] if facts else 0,
                                "actual_deliveries_reconstructed": count,
                                "native_report_id": result["report_id"],
                                "policy_cpu_seconds": result["policy_cpu_seconds"],
                                "partial_episode_used_for_fitting": False,
                            }
                            store.commit(key, request, value, context["sources"])
                            receipt = store.completed(key, request)
                            assert receipt is not None
                            new += 1
                            print(f"Fresh evaluation: {key}: {value['status']}", flush=True)
                        rows.append(receipt["result"])
                        admit_result(root, sources, store, key, receipt)
                        if (
                            sum(r["status"] != "terminal" for r in rows)
                            > cfg["plan"]["maximum_technical_failures"]
                        ):
                            return finish(
                                context,
                                store,
                                {
                                    "schema_version": "native-varied-learning-result-v1",
                                    "status": "evaluation_stopped_failure_allowance",
                                    "withheld_fights": held,
                                    "summary": summary(cfg["plan"]["evaluation_seeds"], rows),
                                    "frozen_finals_id": fitted["frozen_finals_id"],
                                    "optimizer_updates": 0,
                                },
                                sources,
                            )
            return finish(
                context,
                store,
                {
                    "schema_version": "native-varied-learning-result-v1",
                    "status": "bounded_teaching_and_interference_evaluation_complete",
                    "withheld_fights": held,
                    "summary": summary(cfg["plan"]["evaluation_seeds"], rows),
                    "frozen_finals_id": fitted["frozen_finals_id"],
                    "optimizer_updates": 0,
                    "checkpoint_promoted": False,
                    "playing_strength_improvement_claimed_automatically": False,
                },
                sources,
            )
        except Pause:
            progress = {
                "status": "clean_session_boundary",
                "phase": "evaluate",
                "new_units": new,
                "withheld_fights_recorded": len(held),
                "summary": summary(cfg["plan"]["evaluation_seeds"], rows, bootstrap=False),
                "automatic_follow_up": False,
            }
            atomic_json(store.workspace / "progress.json", progress)
            return progress
