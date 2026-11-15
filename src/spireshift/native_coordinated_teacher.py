"""Resumable equal-slot search at paired earlier/later natural combat roots."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.engine_worker_qualification import immutable_checks
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_context_reuse import check_sources
from spireshift.native_coordinated_branch import branch
from spireshift.native_coordinated_data import ARMS, CONTRACT, ENTRIES, candidates, cell, later_root
from spireshift.native_coordinated_inputs import snapshot
from spireshift.native_natural_data import select


class Pause(Exception):
    """Every completed native unit is already sealed; nothing remains running."""


def read_fight(root: Path, row: dict[str, Any]) -> dict[str, Any]:
    value = identified(root / row["fight_path"], "fight_id")
    if value["fight_id"] != row["fight_id"]:
        raise ValueError("A sealed coordinated fight changed")
    return value


def summarize(
    cfg: dict[str, Any], roots: list[dict[str, Any]], cells: list[dict[str, Any]]
) -> dict[str, Any]:
    panels = {}
    for partition in (
        ("control",) if cfg["stage"] == "qualification_control" else ("fit", "heldout")
    ):
        denominator = sum(r["partition"] == partition for r in roots)
        for entry in ENTRIES:
            for arm in ARMS:
                rows = [
                    c
                    for c in cells
                    if (c["partition"], c["entry"], c["arm"]) == (partition, entry, arm)
                ]
                good = [c for c in rows if c.get("verified")]
                panels[f"{partition}/{entry}/{arm}"] = {
                    "world_denominator": denominator,
                    "recorded_worlds": len(rows),
                    "verified_worlds": len(good),
                    "selected_fight_wins": sum(c["selected_outcome"] == "win" for c in good),
                    "strictly_improved_worlds": sum(c["strict_local_improvement"] for c in good),
                    "rescued_worlds": sum(
                        c["reference_outcome"] == "loss" and c["selected_outcome"] == "win"
                        for c in good
                    ),
                    "HP_gain_sum_on_verified_both_win": sum(
                        c["selected_hp"] - c["reference_hp"]
                        for c in good
                        if c["selected_outcome"] == c["reference_outcome"] == "win"
                    ),
                    "candidate_paths": sum(c.get("candidate_paths", 0) for c in rows),
                }
    comparisons = []
    for r in roots:
        by = {(c["entry"], c["arm"]): c for c in cells if c["world"] == r["world"]}
        if len(by) == 4 and all(c.get("verified") for c in by.values()):
            row: dict[str, Any] = {
                "world": r["world"],
                "player": r["player"],
                "partition": r["partition"],
            }
            for entry in ENTRIES:
                a, b = (by[entry, arm] for arm in ARMS)
                row[entry + "_coordinated_minus_single"] = {
                    "fight_win": int(b["selected_outcome"] == "win")
                    - int(a["selected_outcome"] == "win"),
                    "HP_difference_if_both_win": b["selected_hp"] - a["selected_hp"]
                    if a["selected_outcome"] == b["selected_outcome"] == "win"
                    else None,
                }
            for arm in ARMS:
                a, b = by["early", arm], by["later", arm]
                row[arm + "_early_minus_later"] = {
                    "fight_win": int(a["selected_outcome"] == "win")
                    - int(b["selected_outcome"] == "win"),
                    "HP_difference_if_both_win": a["selected_hp"] - b["selected_hp"]
                    if a["selected_outcome"] == b["selected_outcome"] == "win"
                    else None,
                }
            comparisons.append(row)
    return {
        "panels": panels,
        "paired_worlds": comparisons,
        "independent_unit": "native_world_not_branch_or_entry",
        "equal_candidate_slots_not_equal_CPU": True,
        "local_outcomes_are_full_run_utility": False,
    }


def collect(
    root: Path,
    context: dict[str, Any],
    native: Any,
    *,
    max_units: int | None = None,
    launch_deadline: float | None = None,
) -> dict[str, Any]:
    cfg = context["config"]
    store = ChunkJournal(root, cfg)
    if (store.workspace / "report.json").exists():
        saved = identified(store.workspace / "report.json")
        check_sources(root, saved["sources"])
        return saved
    started = time.monotonic()
    deadline = launch_deadline or started + cfg["session_limits"]["wall_seconds"] - 15
    sources = dict(context["sources"])
    done: dict[str, dict[str, Any]] = {}
    cells: list[dict[str, Any]] = []
    new, complete = 0, False
    q, inputs = native

    def unit(
        key: str, r: dict[str, Any], task: dict[str, Any], replay: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        nonlocal new
        request = {
            "contract": CONTRACT,
            "root_id": r["root_id"],
            "task": task,
            "replay_id": replay["fight_id"] if replay else None,
        }
        receipt = store.completed(key, request)
        if receipt is None:
            if deadline - time.monotonic() < 150 or max_units is not None and new >= max_units:
                raise Pause
            if not task.get("unavailable") and _running_games():
                raise ValueError("Close STS2 before another isolated coordinated branch")
            target = store.begin(key, request)
            if task.get("unavailable"):
                result = {
                    "kind": "proposal_unavailable",
                    "status": "unavailable",
                    "native_attempts": 0,
                }
            else:
                account = Path.home() / "Library/Application Support/SlayTheSpire2"
                before = _shared_snapshot(account)
                atomic_json(target / "root.json", r)
                value = branch(
                    q,
                    inputs,
                    cfg,
                    r,
                    task,
                    context["models"][r["player"]],
                    context["score"],
                    target,
                    deadline,
                    replay,
                )
                checks = immutable_checks(q, inputs)
                checks["account_profile_unchanged"] = before == _shared_snapshot(account)
                if not all(checks.values()):
                    raise ValueError(
                        "Coordinated comparison changed a frozen input or real profile"
                    )
                result = {
                    "kind": "fight",
                    "status": value["status"],
                    "checks": checks,
                    "fight_path": str((target / "fight.json").relative_to(root)),
                    "fight_id": value["fight_id"],
                }
            store.commit(key, request, result)
            receipt = store.completed(key, request)
            assert receipt is not None
            new += 1
            if new % 8 == 0 or task["phase"] == "reference":
                print(
                    f"Coordinated teacher: {new} new units saved; {key}: {result['status']}.",
                    flush=True,
                )
        done[key] = receipt["result"]
        sources.update(receipt["sources"])
        sources[str((store.path(key) / "done.json").relative_to(root))] = _sha_file(
            store.path(key) / "done.json"
        )
        if sum(v["status"] == "failed" for v in done.values()) > 2:
            raise ValueError("Coordinated teacher exceeded its finite technical failure allowance")
        returned: dict[str, Any] = receipt["result"]
        return returned

    with store.lock():
        sources.update(snapshot(root, cfg, store.workspace))
        try:
            for i, early in enumerate(context["roots"]):
                early_reference = None
                blocked = False
                for entry in ENTRIES:
                    r = (
                        early
                        if entry == "early"
                        else later_root(early, early_reference)
                        if early_reference
                        else None
                    )
                    if r is None or blocked:
                        cells.extend(
                            {
                                "world": early["world"],
                                "player": early["player"],
                                "partition": early["partition"],
                                "entry": entry,
                                "arm": arm,
                                "verified": False,
                                "available": False,
                                "reason": "blocked_root" if blocked else "no_second_turn",
                            }
                            for arm in ARMS
                        )
                        continue
                    prefix = f"root-{i:02d}-{entry}"
                    result = unit(prefix + "-reference", r, {"phase": "reference"})
                    reference = read_fight(root, result)
                    if reference["status"] != "complete":
                        blocked = True
                    if entry == "early":
                        early_reference = reference
                    elif reference["status"] == "complete":
                        assert early_reference is not None
                        if (
                            reference["steps"] != early_reference["steps"][r["reference_offset"] :]
                            or reference["outcome"] != early_reference["outcome"]
                            or reference["resources"] != early_reference["resources"]
                        ):
                            raise ValueError(
                                "Late reference differs from the original greedy first-turn suffix"
                            )
                    rows_by_arm: dict[str, list[dict[str, Any]]] = {arm: [] for arm in ARMS}
                    for arm in ARMS if i % 2 == 0 else tuple(reversed(ARMS)):
                        if blocked:
                            break
                        for slot in range(cfg["lineages"] * 4):
                            plan = candidates(
                                arm, slot, cfg["lineages"], reference, rows_by_arm[arm]
                            )
                            task = {
                                "phase": "proposal",
                                "arm": arm,
                                "candidate": slot + 1,
                                "plan": plan,
                                "unavailable": plan is None,
                            }
                            value = unit(
                                prefix + f"-{arm.replace('_', '-')}-{slot + 1:02d}", r, task
                            )
                            if value["kind"] == "proposal_unavailable":
                                continue
                            path = read_fight(root, value)
                            rows_by_arm[arm].append(path)
                            if path["status"] != "complete":
                                blocked = True
                                break
                    if not blocked:
                        confirm = read_fight(
                            root,
                            unit(
                                prefix + "-confirm-reference",
                                r,
                                {"phase": "confirmation"},
                                reference,
                            ),
                        )
                        if confirm["resources"] != reference["resources"]:
                            raise ValueError("Coordinated reference confirmation resources differ")
                        for arm in ARMS:
                            rows = [reference, *rows_by_arm[arm]]
                            chosen = select(rows)
                            selected = next(v for v in rows if v["candidate"] == chosen)
                            confirm = read_fight(
                                root,
                                unit(
                                    prefix + "-confirm-" + arm.replace("_", "-"),
                                    r,
                                    {"phase": "confirmation", "arm": arm, "candidate": chosen},
                                    selected,
                                ),
                            )
                            if confirm["resources"] != selected["resources"]:
                                raise ValueError(
                                    "Coordinated selected confirmation resources differ"
                                )
                    for arm in ARMS:
                        measured = (
                            cell(reference, rows_by_arm[arm], not blocked)
                            if reference["status"] == "complete"
                            else {"verified": False}
                        )
                        cells.append(
                            {
                                "world": early["world"],
                                "player": early["player"],
                                "partition": early["partition"],
                                "entry": entry,
                                "arm": arm,
                                "root_id": r["root_id"],
                                "available": True,
                                **measured,
                            }
                        )
                        if measured.get("verified"):
                            print(
                                f"World {i + 1}/{len(context['roots'])} {entry} {arm}: "
                                f"best {measured['selected_outcome']}, "
                                f"HP {measured['selected_hp']:g} "
                                f"(reference {measured['reference_hp']:g}); "
                                f"{measured['selected_edits']} changes, "
                                f"{measured['candidate_paths']} candidate paths.",
                                flush=True,
                            )
            complete = True
        except Pause:
            pass
        check_sources(root, sources)
        checks = {
            "all_cells_verified": len(cells) == len(context["roots"]) * 4
            and all(c.get("verified") for c in cells),
            "both_parents_execute_joint_edits": all(
                any(
                    c["player"] == p
                    and c["arm"] == "coordinated"
                    and c.get("maximum_executed_edits", 0) >= 2
                    for c in cells
                )
                for p in (2, 3)
            ),
            "three_edits_exercised": any(c.get("maximum_executed_edits", 0) >= 3 for c in cells),
            "cross_round_edits_exercised": any(
                c.get("maximum_edited_rounds", 0) >= 2 for c in cells
            ),
        }
        fit = [
            c
            for c in cells
            if c["partition"] == "fit"
            and c["entry"] == "early"
            and c["arm"] == "coordinated"
            and c.get("strict_local_improvement")
        ]
        body = {
            "schema_version": "coordinated-native-teacher-comparison-v1",
            "config_id": store.config_id,
            "sources": sources,
            "status": "coordinated_teacher_complete"
            if complete
            else "coordinated_teacher_clean_pause",
            "completed_units": len(done),
            "new_units_this_session": new,
            "native_attempts": sum(v["kind"] == "fight" for v in done.values()),
            "failed_branches": sum(v["status"] == "failed" for v in done.values()),
            "capped_branches": sum(v["status"] == "capped" for v in done.values()),
            "unavailable_proposals": sum(
                v["kind"] == "proposal_unavailable" for v in done.values()
            ),
            "planned_worlds": len(context["roots"]),
            "cells": cells,
            "fights": done,
            "comparison": summarize(cfg, context["roots"], cells),
            "control_checks": checks,
            "control_checks_passed": cfg["stage"] == "qualification_control"
            and all(checks.values()),
            "preliminary_signal": {
                "improved_fitting_worlds": len(fit),
                "short_winning_plans_excluded": False,
                "heldout_used_for_fitting": False,
                "automatic_student_training_allowed": False,
            },
            "original_weights_and_all_Adam_unchanged": True,
            "optimizer_steps": 0,
            "ordinary_PPO_eligible": False,
            "privileged_fixed_world_teacher": True,
            "student_inputs_public_only": True,
            "game_apps_created": 0,
            "checkpoint_promoted": False,
            "adaptive_controller_allowed": False,
            "automatic_training_follows": False,
            "full_run_objective": context["score"].evaluation_objective.as_dict(),
            "training_spec_id": context["score"].spec_id,
            "wall_seconds": time.monotonic() - started,
        }
        report = {**body, "report_id": manifest_identifier(body)}
        n = len(list((store.workspace / "sessions").glob("session-*.json"))) + 1
        atomic_json(store.workspace / f"sessions/session-{n:03d}.json", report)
        if complete:
            atomic_json(store.workspace / "report.json", report)
        return report
