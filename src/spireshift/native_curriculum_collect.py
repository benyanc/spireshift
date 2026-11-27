"""Prospective original-player games, fitting-only branch search and a quality stop."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, cast

from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_worker_qualification import immutable_checks
from spireshift.full_run_experience import atomic_json
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_curriculum_data import bank, choose_reference_or_teacher, roots
from spireshift.native_curriculum_native import branch, collect_game
from spireshift.native_curriculum_store import (
    Pause,
    admit_result,
    final,
    finish,
    journal,
    reserve,
    snapshot,
)
from spireshift.native_flow_verification_v12 import same
from spireshift.native_learner_guard import require_scope
from spireshift.native_natural_data import mutations


def collect(
    context: dict[str, Any], *, max_units: int | None = None, deadline: float | None = None
) -> dict[str, Any]:
    saved = final(context, "collection")
    if saved is not None:
        return saved
    root, cfg = context["qualification"].root, context["config"]
    require_scope(context["guard_receipt"], context["guard_binding"], "collect_original_curriculum")
    started = time.monotonic()
    deadline = deadline or started + cfg["session_limits"]["wall_seconds"] - 15
    store = journal(context, "collection")
    sources, new, source_games, root_rows, cells = dict(context["sources"]), 0, [], [], []
    control = cfg["stage"] == "short_control"

    def unit(key: str, request: dict[str, Any], seconds: float, run: Any) -> dict[str, Any]:
        nonlocal new
        request = {"guard_id": context["guard_receipt"]["report_id"], **request}
        receipt = store.completed(key, request)
        if receipt is None:
            reserve(deadline, seconds, new, max_units)
            check_sources(root, cfg["implementation"])
            if _running_games():
                raise ValueError("Close STS2 before an isolated curriculum unit")
            target = store.begin(key, request)
            account = Path.home() / "Library/Application Support/SlayTheSpire2"
            before = _shared_snapshot(account)
            atomic_json(target / "profile-before.json", before)
            value = run(target)
            checks = immutable_checks(context["qualification"], context["native"])
            after = _shared_snapshot(account)
            atomic_json(target / "profile-after.json", after)
            checks["personal_profile_unchanged"] = before == after
            atomic_json(target / "immutable-checks.json", checks)
            if not all(checks.values()):
                raise ValueError("A curriculum unit changed frozen inputs or the personal profile")
            value["checks"] = checks
            store.commit(key, request, value, context["sources"])
            receipt = store.completed(key, request)
            assert receipt is not None
            new += 1
            print(f"Curriculum: {key}: {value.get('status', 'sealed')}", flush=True)
        admit_result(root, sources, store, key, receipt)
        return cast(dict[str, Any], receipt["result"])

    with store.lock():
        sources.update(snapshot(context, store))
        try:
            for case in cfg["plan"]["worlds"]:

                def source_unit(target: Path, case: dict[str, Any] = case) -> dict[str, Any]:
                    value = collect_game(context, case, target, deadline)
                    selected = (
                        roots(context, case, root / value["directory"])
                        if value["status"] == "native_natural_ending_pass"
                        else []
                    )
                    atomic_json(target / "roots.json", {"roots": selected})
                    value.update(
                        roots_path=str((target / "roots.json").relative_to(root)),
                        root_ids=[r["root_id"] for r in selected],
                    )
                    return value

                value = unit(
                    "source-" + case["key"],
                    {"kind": "natural_source", "case": case},
                    150,
                    source_unit,
                )
                source_games.append(value)
                root_rows.extend(json.loads((root / value["roots_path"]).read_text())["roots"])
            for index, r in enumerate(root_rows):
                if r["partition"] == "heldout":
                    continue
                proposals = mutations(r["reference"], cfg["plan"]["candidate_paths_per_root"])
                candidates = []
                for number in range(1, cfg["plan"]["candidate_paths_per_root"] + 1):
                    proposal = proposals[number - 1] if number <= len(proposals) else None

                    def candidate_unit(
                        target: Path,
                        proposal: Any = proposal,
                        number: int = number,
                        r: dict[str, Any] = r,
                    ) -> dict[str, Any]:
                        if proposal is None:
                            return {
                                "kind": "proposal_unavailable",
                                "status": "unavailable",
                                "candidate": number,
                                "native_attempts": 0,
                            }
                        forced = [
                            {
                                "public_input_id": s["public_input_id"],
                                "action_index": s["action_index"],
                            }
                            for s in r["reference"]["steps"][: proposal["decision"] + 1]
                        ]
                        forced[-1]["action_index"] = proposal["action"]
                        result = branch(
                            context, r, target, deadline, proposal=forced, candidate=number
                        )
                        return {
                            "kind": "teacher_branch",
                            "status": result["status"],
                            "candidate": number,
                            "branch_path": str((target / "branch.json").relative_to(root)),
                            "branch_id": result["report_id"],
                            "native_attempts": 1,
                        }

                    value = unit(
                        f"root-{index:02d}-candidate-{number:02d}",
                        {
                            "kind": "teacher_branch",
                            "root_id": r["root_id"],
                            "proposal": proposal,
                            "number": number,
                        },
                        85,
                        candidate_unit,
                    )
                    if "branch_path" in value:
                        candidates.append(identified(root / value["branch_path"]))
                selected = choose_reference_or_teacher(r["reference"], candidates)
                confirmed = selected is r["reference"]
                if not confirmed:
                    forced = [
                        {"public_input_id": s["public_input_id"], "action_index": s["action_index"]}
                        for s in selected["steps"]
                    ]

                    def confirm_unit(
                        target: Path,
                        r: dict[str, Any] = r,
                        forced: list[dict[str, Any]] = forced,
                        selected: dict[str, Any] = selected,
                    ) -> dict[str, Any]:
                        result = branch(
                            context,
                            r,
                            target,
                            deadline,
                            proposal=forced,
                            candidate=selected["candidate"],
                        )
                        if (
                            result["status"] != "complete"
                            or not same(result["steps"], selected["steps"])
                            or result["outcome"] != selected["outcome"]
                            or not same(result["resources"], selected["resources"])
                        ):
                            raise ValueError(
                                "Selected teacher plan did not reproduce its complete public path"
                            )
                        return {
                            "kind": "teacher_confirmation",
                            "status": "verified",
                            "native_attempts": 1,
                            "branch_path": str((target / "branch.json").relative_to(root)),
                        }

                    unit(
                        f"root-{index:02d}-confirm",
                        {
                            "kind": "confirmation",
                            "root_id": r["root_id"],
                            "selected_id": selected["report_id"],
                        },
                        85,
                        confirm_unit,
                    )
                    confirmed = True
                cells.append(
                    {
                        "root_id": r["root_id"],
                        "selected": selected,
                        "confirmation_verified": confirmed,
                    }
                )
            curriculum = bank(root_rows, cells, cfg["plan"]["quality"], control=control)
            all_sources_clean = all(
                g["status"] == "native_natural_ending_pass" for g in source_games
            )
            withheld_available = control or {
                r["world"] for r in root_rows if r["partition"] == "heldout"
            } == {c["seed"] for c in cfg["plan"]["worlds"] if c["partition"] == "heldout"}
            passed = all_sources_clean and withheld_available and curriculum["quality"]["passed"]
            atomic_json(store.workspace / "bank.json", curriculum)
            atomic_json(store.workspace / "roots.json", {"roots": root_rows})
            compact_cells = [
                {
                    "root_id": c["root_id"],
                    "selected_candidate": c["selected"]["candidate"],
                    "selected_status": c["selected"]["status"],
                    "selected_outcome": c["selected"]["outcome"],
                    "confirmation_verified": c["confirmation_verified"],
                }
                for c in cells
            ]
            return finish(
                context,
                store,
                {
                    "schema_version": "native-varied-curriculum-collection-v1",
                    "status": "curriculum_qualified" if passed else "curriculum_quality_blocked",
                    "quality": curriculum["quality"],
                    "all_natural_sources_clean": all_sources_clean,
                    "all_prospective_withheld_worlds_have_public_roots": withheld_available,
                    "source_world_denominator": len(cfg["plan"]["worlds"]),
                    "source_games": [
                        {k: g[k] for k in ["case", "status", "deliveries", "root_ids"]}
                        for g in source_games
                    ],
                    "cells": compact_cells,
                    "bank_id": curriculum["bank_id"],
                    "bank_path": str((store.workspace / "bank.json").relative_to(root)),
                    "roots_path": str((store.workspace / "roots.json").relative_to(root)),
                    "independent_fitting_unit": "world_not_root_branch_or_source_player",
                    "teacher_outcomes_are_privileged": True,
                    "ordinary_PPO_eligible": False,
                    "fitting_started": False,
                    "optimizer_updates": 0,
                    "wall_seconds": time.monotonic() - started,
                },
                sources,
            )
        except Pause:
            progress = {
                "status": "clean_session_boundary",
                "phase": "collect",
                "new_units": new,
                "source_worlds_sealed": len(source_games),
                "optimizer_updates": 0,
                "automatic_follow_up": False,
            }
            atomic_json(store.workspace / "progress.json", progress)
            return progress
