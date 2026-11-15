"""Read-only closure of the stopped continuation; no unit is committed or replayed."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode
from spireshift.engine_experience_stream import audit_worker_streaming
from spireshift.engine_learning import identified
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_journal import ChunkJournal, load_state
from spireshift.native_context_reuse import check_sources
from spireshift.native_continuation_plan import training_plan
from spireshift.native_policy_continuation import load_continuation, request, verify_state


def capture(q: EngineQualificationConfig, recipe: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        saved = identified(output)
        check_sources(q.root, saved["sources"])
        return saved
    started = time.monotonic()
    cfg, _, seeds, sources = load_continuation(q, recipe)
    store = ChunkJournal(q.root, cfg)
    completed: dict[str, dict[str, Any]] = {}
    last_fit: dict[int, dict[str, Any]] = {}
    unfitted: dict[int, list[str]] = {2: [], 3: []}
    unfinished: dict[str, Any] | None = None
    for task in training_plan(cfg, seeds):
        req = request(task, completed)
        try:
            receipt = store.completed(task["key"], req)
        except FileExistsError:
            if task["kind"] != "collect":
                raise ValueError(
                    "Only the known uncommitted collection may be closed diagnostically"
                ) from None
            target = store.path(task["key"])
            active = json.loads((target / "active.json").read_text())
            if active["config_id"] != manifest_identifier(cfg) or active[
                "request_id"
            ] != manifest_identifier(req):
                raise ValueError(
                    "Uncommitted request no longer matches its planned predecessor"
                ) from None
            summary = json.loads((target / "games/summary.json").read_text())
            paths = sorted((target / "games").glob("case-*.json"))
            if (
                summary["planned_games"] != 8
                or len(paths) != 8
                or summary["not_attempted_games"]
                or summary["worker_failures"]
            ):
                raise ValueError(
                    "Uncommitted collection has missing or unauditable attempts"
                ) from None
            headers = [json.loads(p.read_text()) for p in paths]
            if {h["binding"]["seed_id"] for h in headers} != {s["id"] for s in task["seeds"]}:
                raise ValueError("Uncommitted batch seeds changed") from None
            audits = []
            for worker in sorted((target / "games").glob("worker-*")):
                own = [
                    p
                    for p, h in zip(paths, headers, strict=True)
                    if h["episode"]["worker_workspace"] == worker.name
                ]
                if not worker.is_dir() or not own:
                    raise ValueError(
                        "Unexpected worker suffix; preserve it for inspection"
                    ) from None
                audits.append(audit_worker_streaming(worker, own, deadline=started + 220))
            for p, header in zip(paths, headers, strict=True):
                case = read_native_episode(p, header["binding"])
                if (
                    case["status"] != "terminal"
                    and case.get("error") != "Repeated public-state exploration cap"
                ):
                    raise ValueError("Unexpected unfinished game cause") from None
            unfinished = {
                "key": task["key"],
                "planned_attempts": len(paths),
                "terminal_games": summary["completed_games"],
                "failed_games": summary["failed_games"],
                "diagnostic_only": True,
                "ordinary_training_admitted": False,
                "worker_audit_ids": [a["report_id"] for a in audits],
            }
            unfitted[task["numerical_seed"]].append(task["key"])
            break
        if receipt is None:
            raise ValueError("Expected the recorded stopped batch, not a merely paused experiment")
        verify_state(q, task, receipt, completed)
        completed[task["key"]] = receipt
        sources.update(receipt["sources"])
        if task.get("training"):
            unfitted[task["numerical_seed"]].append(task["key"])
        if task["kind"] == "fit":
            n = task["numerical_seed"]
            state = receipt["result"]
            last_fit[n] = {
                "numerical_seed": n,
                "version": "trained",
                "path": state["state_path"],
                "state_id": state["state_id"],
                "model_id": state["model_id"],
                "sha256": _sha_file(q.root / state["state_path"]),
                "optimizer_steps": state["optimizer_steps"],
                "round": task["round"],
                "scheduled_training_games": task["milestone"],
            }
            unfitted[n] = []
    if (
        unfinished is None
        or len(completed) != 221
        or set(last_fit) != {2, 3}
        or any(p["round"] != 35 or p["scheduled_training_games"] != 1120 for p in last_fit.values())
        or len(unfitted[2]) != 4
        or unfitted[3]
    ):
        raise ValueError("Stopped continuation extent differs from the reviewed round-36 failure")
    counts: Counter[str] = Counter()
    failures: list[dict[str, Any]] = []
    for p in store.workspace.glob("chunks/*/games/summary.json"):
        s = json.loads(p.read_text())
        counts.update(
            {k: s[k] for k in ("planned_games", "completed_games", "failed_games", "wins")}
        )
        failures.extend({"chunk": p.parent.parent.name, **f} for f in s["failed_cases"])
    if counts != Counter(planned_games=1440, completed_games=1437, failed_games=3, wins=0):
        raise ValueError("Original attempt denominator differs")
    # Seal the entire stopped workspace, including all original markers and the
    # uncommitted suffix. No deletion, done.json synthesis, worker reset or replay.
    sources.update(
        {
            str(p.relative_to(q.root)): _sha_file(p)
            for p in store.workspace.rglob("*")
            if p.is_file()
        }
    )
    check_sources(q.root, sources)
    body: dict[str, Any] = {
        "schema_version": "native-shop-stopped-continuation-audit-v1",
        "status": "stopped_prefix_and_full_Adam_states_verified",
        "source_recipe": str(recipe.relative_to(q.root)),
        "source_config_id": manifest_identifier(cfg),
        "completed_units": len(completed),
        "attempts": dict(counts),
        "failed_cases": failures,
        "players": [last_fit[n] for n in (2, 3)],
        "unfinished_collection": unfinished,
        "excluded_unfitted_collections": unfitted,
        "excluded_unfitted_training_attempts": 32,
        "all_prior_reserved_seeds_excluded_from_replacement": True,
        "ordinary_training_admitted": False,
        "old_workspace_modified": False,
        "games_replayed": 0,
        "optimizer_steps": 0,
        "sources": sources,
        "wall_seconds": time.monotonic() - started,
        "claim_scope": "read_only_stopped_batch_diagnosis_and_latest_full_Adam_checkpoint_import",
    }
    for ref in body["players"]:
        m, optimizer, state_id = load_state(q.root / ref["path"])
        if (
            m.model_id != ref["model_id"]
            or state_id != ref["state_id"]
            or optimizer.steps != ref["optimizer_steps"]
        ):
            raise ValueError("Latest saved full optimizer state changed")
    result = {**body, "report_id": manifest_identifier(body)}
    atomic_json(output, result)
    return result


if __name__ == "__main__":
    from spireshift.engine_qualification import load_engine_qualification_config

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("qualification", type=Path)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    qualification = load_engine_qualification_config(args.qualification)
    result = capture(
        qualification, qualification.root / args.recipe, qualification.root / args.output
    )
    print(json.dumps({k: v for k, v in result.items() if k != "sources"}, indent=2))
