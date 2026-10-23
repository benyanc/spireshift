"""Sealed natural multi-turn proposals, confirmation and explicitly local lessons."""

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
from spireshift.native_natural_branch import branch
from spireshift.native_natural_data import CONTRACT, admit, improves, mutations, select
from spireshift.native_natural_inputs import snapshot


def fight(root: Path, row: dict[str, Any]) -> dict[str, Any]:
    value = identified(root / row["fight_path"], "fight_id")
    if value["fight_id"] != row["fight_id"]:
        raise ValueError("A sealed natural fight changed")
    return value


def collect(
    root: Path,
    context: dict[str, Any],
    native: Any,
    *,
    max_units: int | None = None,
    launch_deadline: float | None = None,
) -> dict[str, Any]:
    cfg = context["config"]
    store = ChunkJournal(root, {**cfg, "workspace": cfg["workspace"] + "/teacher"})
    final = store.workspace / "report.json"
    if final.exists():
        result = identified(final)
        check_sources(root, result["sources"])
        return result
    started = time.monotonic()
    deadline = launch_deadline or started + cfg["session_limits"]["wall_seconds"] - 15
    sources = dict(context["sources"])
    done: dict[str, Any] = {}
    summaries: list[dict[str, Any]] = []
    new = 0
    q, inputs = native
    with store.lock():
        sources.update(snapshot(root, cfg, store.workspace))
        for index, r in enumerate(context["roots"]):
            rows: list[dict[str, Any]] = []
            reference = None
            proposals: list[dict[str, Any]] = []
            selected = 0
            blocked = False
            for phase in ("reference", "mutations", "confirm_reference", "confirm_selected"):
                if phase == "mutations":
                    assert reference is not None
                    proposals = mutations(reference, cfg["maximum_mutations"])
                schedule: list[dict[str, Any]] = (
                    [{"candidate": i + 1, "mutation": m} for i, m in enumerate(proposals)]
                    if phase == "mutations"
                    else [{"candidate": 0}]
                )
                if phase == "confirm_selected":
                    selected = select(rows)
                    schedule = [{"candidate": selected, "replay": True}]
                elif phase == "confirm_reference":
                    schedule = [{"candidate": 0, "replay": True}]
                for ordinal, details in enumerate(schedule):
                    key = f"root-{index:02d}-{phase.replace('_', '-')}-{ordinal:02d}"
                    task = {"key": key, "root_id": r["root_id"], "phase": phase, **details}
                    request = {
                        "contract": CONTRACT,
                        "task": task,
                        "reference_id": reference["fight_id"] if reference else None,
                    }
                    if phase == "confirm_selected":
                        request["chosen_id"] = rows[selected]["fight_id"]
                    receipt = store.completed(key, request)
                    if receipt is None:
                        if (
                            deadline - time.monotonic() < 85
                            or max_units is not None
                            and new >= max_units
                        ):
                            return finish(
                                root, context, store, done, summaries, sources, new, started, False
                            )
                        if _running_games():
                            raise ValueError(
                                "Close STS2 before another isolated natural combat branch"
                            )
                        target = store.begin(key, request)
                        account = Path.home() / "Library/Application Support/SlayTheSpire2"
                        before = _shared_snapshot(account)
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
                            rows[selected] if phase == "confirm_selected" else reference,
                        )
                        checks = immutable_checks(q, inputs)
                        checks["account_profile_unchanged"] = before == _shared_snapshot(account)
                        if not all(checks.values()):
                            raise ValueError(
                                "Natural teacher changed a frozen input or real profile"
                            )
                        result = {
                            "kind": "fight",
                            "fight_path": str((target / "fight.json").relative_to(root)),
                            "fight_id": value["fight_id"],
                            "status": value["status"],
                            "checks": checks,
                        }
                        store.commit(key, request, result)
                        receipt = store.completed(key, request)
                        assert receipt is not None
                        new += 1
                        print(
                            f"Natural fight {index + 1}/{len(context['roots'])}, {phase}: "
                            f"{value['outcome'] or value['status']}; no optimizer updates.",
                            flush=True,
                        )
                    done[key] = receipt["result"]
                    sources.update(receipt["sources"])
                    sources[str((store.path(key) / "done.json").relative_to(root))] = _sha_file(
                        store.path(key) / "done.json"
                    )
                    value = fight(root, receipt["result"])
                    if phase == "reference":
                        reference = value
                        rows.append(value)
                    elif phase == "mutations":
                        rows.append(value)
                    elif value["status"] == "complete":
                        expected = rows[details["candidate"]]
                        if (
                            value["steps"] != expected["steps"]
                            or value["resources"] != expected["resources"]
                        ):
                            raise ValueError("Repeated selected/reference encounter did not match")
                    if sum(v["status"] == "failed" for v in done.values()) > 2:
                        raise ValueError(
                            "Natural teacher exceeded its finite technical failure allowance"
                        )
                    if value["status"] != "complete":
                        blocked = True
                        break  # Retain this root as unavailable; never retry a failed/capped path.
                if blocked:
                    break
            assert reference is not None
            chosen = rows[selected]
            relevant = [v for k, v in done.items() if k.startswith(f"root-{index:02d}-")]
            verified = all(v["status"] == "complete" for v in relevant)
            summaries.append(
                {
                    "root_id": r["root_id"],
                    "partition": r["partition"],
                    "verified": verified,
                    "selected_candidate": selected,
                    "selected_fight_id": chosen["fight_id"],
                    "reference_fight_id": reference["fight_id"],
                    "selected_outcome": chosen["outcome"],
                    "reference_outcome": reference["outcome"],
                    "public_rounds": chosen["public_rounds"],
                    "choice_decisions": chosen["choice_decisions"],
                    "strict_local_improvement": improves(chosen, reference),
                    "candidate_count": len(rows),
                }
            )
            print(
                f"Natural root {index + 1} complete: {chosen['outcome']}; "
                f"local improvement {summaries[-1]['strict_local_improvement']}; "
                f"{chosen['public_rounds']} public rounds.",
                flush=True,
            )
        return finish(root, context, store, done, summaries, sources, new, started, True)


def finish(
    root: Path,
    context: dict[str, Any],
    store: ChunkJournal,
    done: dict[str, Any],
    summaries: list[dict[str, Any]],
    sources: dict[str, str],
    new: int,
    started: float,
    complete: bool,
) -> dict[str, Any]:
    check_sources(root, sources)
    body = {
        "schema_version": "natural-native-teacher-v1",
        "config_id": store.config_id,
        "status": "natural_teacher_complete" if complete else "natural_teacher_clean_pause",
        "completed_units": len(done),
        "new_units_this_session": new,
        "sources": sources,
        "summaries": summaries,
        "fights": done,
        "gate": admit(context["roots"], summaries),
        "native_attempts": len(done),
        "failed_branches": sum(v["status"] == "failed" for v in done.values()),
        "optimizer_steps": 0,
        "ordinary_PPO_eligible": False,
        "planned_root_denominator": len(context["roots"]),
        "root_gaps": sum(not s["verified"] for s in summaries),
        "full_run_objective": context["score"].evaluation_objective.as_dict(),
        "training_spec_id": context["score"].spec_id,
        "privileged_fixed_world_teacher": True,
        "full_run_utility_established": False,
        "original_weights_and_Adam_unchanged": True,
        "game_apps_created": 0,
        "automatic_training_follows": False,
        "checkpoint_promoted": False,
        "wall_seconds": time.monotonic() - started,
    }
    report = {**body, "report_id": manifest_identifier(body)}
    index = len(list((store.workspace / "sessions").glob("session-*.json"))) + 1
    atomic_json(store.workspace / f"sessions/session-{index:03d}.json", report)
    if complete:
        atomic_json(store.workspace / "report.json", report)
    return report
