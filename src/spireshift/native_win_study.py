"""Finite training-only collection with sealed units; no automatic base training."""

from __future__ import annotations

import time
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_win_bank import coverage, lesson, matching_confirmation, select, steps
from spireshift.native_win_game import episode, prepare, write


class CleanPause(Exception):
    """No uncommitted unit or live worker; owner may resume the same command."""


def unit(
    context: dict[str, Any],
    store: ChunkJournal,
    key: str,
    request: dict[str, Any],
    deadline: float,
    operation: Any,
) -> dict[str, Any]:
    existing = store.completed(key, request)
    if existing is not None:
        return dict(existing["result"])
    if time.monotonic() > deadline - 160:
        raise CleanPause
    target = store.begin(key, request)
    result = operation(target, min(deadline - 20, time.monotonic() + 135))
    receipt = store.commit(key, request, result, context["sources"])
    if store.completed(key, request) != receipt:
        raise ValueError("A new curriculum unit did not seal exactly")
    return dict(result)


def collect(context: dict[str, Any], deadline: float) -> dict[str, Any]:
    cfg, root = context["config"], context["qualification"].root
    store = ChunkJournal(root, cfg)
    final = store.workspace / "report.json"
    if final.exists():
        report = identified(final)
        check_sources(root, report["sources"])
        check_sources(root, report["evidence"])
        return report
    admitted, actual, heldout, cases, families = [], [], [], [], set()
    sources = dict(context["sources"])
    with store.lock():
        try:
            for partition in ("fit", "heldout"):
                for case in cfg["plan"][partition]:
                    key = case["key"]
                    start = unit(
                        context,
                        store,
                        key + "-start",
                        {"case": case, "stage": "setup"},
                        deadline,
                        lambda p, d, c=case: prepare(context, c, p, d),
                    )
                    if start["status"] != "ready":
                        cases.append(
                            {"case": case, "status": "unavailable", "start_id": start["report_id"]}
                        )
                        continue
                    variants = ["reference", *cfg["plan"]["teacher_variants"]]
                    results = []
                    for variant in variants:
                        request = {
                            "case": case,
                            "stage": "episode",
                            "start_id": start["report_id"],
                            "variant": variant,
                            "model_id": context["models"][case["player"]].model_id,
                        }
                        value = unit(
                            context,
                            store,
                            key + "-" + variant,
                            request,
                            deadline,
                            lambda p, d, s=start, v=variant: episode(context, s, v, p, d),
                        )
                        results.append(value)
                        actual.append(value)
                        print(
                            f"Curriculum: {key}/{variant}: {value['status']}; "
                            f"success={value['curriculum_success']}",
                            flush=True,
                        )
                    if partition == "heldout":
                        best = select(results[0], results[1:])
                        heldout.append(best if best is not None else results[1])
                        cases.append(
                            {
                                "case": case,
                                "status": "heldout_probe_only",
                                "results": results,
                                "teacher_selected_by_frozen_method": None
                                if best is None
                                else best["report_id"],
                                "fitting_labels_provided": False,
                            }
                        )
                        continue
                    chosen = select(results[0], results[1:])
                    if chosen is None:
                        cases.append(
                            {"case": case, "status": "no_successful_teacher", "results": results}
                        )
                        continue
                    confirmation = unit(
                        context,
                        store,
                        key + "-confirm",
                        {
                            "stage": "confirmation",
                            "chosen_id": chosen["report_id"],
                            "start_id": start["report_id"],
                        },
                        deadline,
                        lambda p, d, s=start, v=chosen["variant"]: episode(context, s, v, p, d),
                    )
                    actual.append(confirmation)
                    if not matching_confirmation(root, chosen, confirmation):
                        raise ValueError(
                            "Fresh teacher confirmation changed; preserve without retry"
                        )
                    value = lesson(case, start, results[0], chosen, confirmation)
                    labels = steps(root, value)
                    value["meaningful_choices"] = len(labels)
                    value["meaningful_families"] = sorted({s["family"] for s in labels})
                    # Re-identify after adding the verified label counts.
                    value.pop("lesson_id")
                    value["lesson_id"] = manifest_identifier(value)
                    admitted.append(value)
                    families.update(value["meaningful_families"])
                    cases.append(
                        {
                            "case": case,
                            "status": "confirmed_teacher",
                            "lesson_id": value["lesson_id"],
                            "results": results,
                        }
                    )
        except CleanPause:
            return {
                "status": "paused_at_clean_curriculum_boundary",
                "optimizer_updates": 0,
                "automatic_follow_up": False,
                "resume": "same_owner_command",
            }
        quality = coverage(admitted, families, heldout, cfg["plan"]["quality"])
        bank = {
            "schema_version": "native-win-curriculum-bank-v1",
            "config_id": context["config_id"],
            "lessons": admitted,
            "quality": quality,
            "heldout_labels_included": False,
            "ordinary_PPO_eligible": False,
            "training_start_wins_are_full_run_wins": False,
        }
        bank_path = store.workspace / "bank.json"
        bank = write(bank_path, bank, "bank_id")
        sources[str(bank_path.relative_to(root))] = _sha_file(bank_path)
        evidence = {
            str(p.relative_to(root)): _sha_file(p)
            for p in store.workspace.rglob("*")
            if p.is_file() and p.name not in {"session.lock", "report.json"}
        }
        return write(
            final,
            {
                "schema_version": "native-win-curriculum-result-v1",
                "status": "win_focused_curriculum_admitted"
                if quality["passed"]
                else "curriculum_quality_blocked",
                "config_id": context["config_id"],
                "environment_id": context["environment"]["manifest_id"],
                "planned_cases": len(cfg["plan"]["fit"]) + len(cfg["plan"]["heldout"]),
                "cases": cases,
                "bank_path": str(bank_path.relative_to(root)),
                "bank_id": bank["bank_id"],
                "quality": quality,
                "admitted_lessons": len(admitted),
                "actual_episodes": len(actual),
                "actual_deliveries_verified": sum(
                    r["actual_deliveries_independently_verified"] for r in actual
                ),
                "capped_episodes": sum(r["status"] == "capped" for r in actual),
                "natural_training_full_wins": sum(r["full_run_win"] for r in actual),
                "prepared_training_successes": sum(
                    r["kind"] == "prepared_training_only" and r["curriculum_success"]
                    for r in actual
                ),
                "optimizer_updates": 0,
                "training_allowed": False,
                "promotion_allowed": False,
                "official_live_qualification_granted": False,
                "full_game_playing_strength_evaluated": False,
                "automatic_follow_up": False,
                "sources": sources,
                "evidence": evidence,
            },
        )
