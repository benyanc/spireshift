"""Verify model-owned coverage and compare terminal signal within each training root."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_win4_game
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path, _shared_snapshot
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_coverage_policy import Continuation
from spireshift.native_a8_coverage_session import (
    AREA,
    BRANCH,
    COMPLETE,
    MODULE,
    Collection,
    journal,
    load,
    request,
    require_control,
)
from spireshift.native_a8_feedback_session import LIMITS
from spireshift.native_a8_mix_audit import source
from spireshift.native_a8_mix_session import unchanged
from spireshift.native_a8_own_experience import groups, policy
from spireshift.native_a8_own_training import SCOPE
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_paired_report import diagnostics
from spireshift.native_a8_rescue_game import TRACE
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_a8_world_credit import run_return
from spireshift.native_a8_world_credit_session import tally
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_curriculum_config import THREADS, execution_runtime

STATUS = "model_owned_coverage_saved_verified"


def replay(
    collection: Collection, row: dict[str, Any], directory: Path, out: Path, deadline: float
) -> dict[str, Any]:
    task = row["task"]
    base = collection.temporal.base
    model = base.originals[task["player"]][0]
    start, episode = (identified(directory / name) for name in ("start.json", "report.json"))
    ending = episode["native_ending"]
    identity = ending["private_final_identity"]
    won = row["outcome"] == "win"
    if (
        task["partition"] not in {"train", BRANCH}
        or start["scenario"] != task
        or start["seed"] != task["seed"]
        or start["kind"] != "natural_training"
        or start["save_path"] is not None
        or start["evaluation_eligible"] is not False
        or episode["start_id"] != start["report_id"]
        or episode["report_id"] != row["episode_report_id"]
        or episode["model_id"] != model.model_id
        or episode["initial_public_input_id"] != row["initial_public_input_id"]
        or episode["status"] != "complete"
        or episode["optimizer_updates"] != 0
        or episode["native_terminal"] is not True
        or episode["full_run_win"] is not won
        or episode["shutdown"]["clean_exit"] is not True
        or episode["shutdown"]["runtime_errors"]
        or ending["native_ending_evidence_agrees"] is not True
        or identity["seed"] != task["seed"]
        or identity["ascension"] != 8
        or identity["native_victory_room"] is not won
        or not (identity["native_game_over"] or (not won and identity["native_player_dead"]))
        or ending["usage"]["native_cpu_seconds"] != row["native_cpu_seconds"]
        or row["native_cpu_seconds"] > base.ctx["score"].evaluation_objective.whole_run_budget
        or any(row[k] != v for k, v in diagnostics(directory / TRACE, won).items())
    ):
        raise ValueError(f"Saved start, terminal or shutdown differs for {task['key']}")

    root = collection.roots[task["root"]] if task["partition"] == BRANCH else None
    prefix = root.spec["prefix_native_deliveries"] if root else 0

    def chooser(
        ctx: dict[str, Any], start: dict[str, Any], variant: str, model: CachedContextModel
    ) -> Any:
        if root is None:
            return policy(ctx, start, variant, model)
        draw = f"{task['seed']}/a8-coverage-v1/{task['partition']}/{task['key']}"
        return Continuation(model, ctx["score"], root, draw)

    out.mkdir()
    with patch.object(native_win4_game, "policy", chooser):
        deliveries = native_win4_game.verify_episode(
            base.ctx, start, "own_policy", directory, out, deadline, model=model
        )
    total = local = 0
    first = None
    choices: Counter[int] = Counter()
    families: Counter[str] = Counter()
    for i, group in enumerate(groups(directory, model.model_id)):
        frame, choice = group[0]
        if i == prefix:
            first = choice["draw_key"]
        if i >= prefix and any(len(f["actions"]) > 1 for f, _ in group):
            act = frame["public_input"]["context"]["persistent"]["run"]["act"]
            choices[act] += 1
            families[frame["source_family"]] += 1
        total += 1
        local += len(group) - 1
    if (
        total != deliveries
        or total != row["native_decisions"]
        or total != episode["actual_deliveries_independently_verified"]
        or local != row["local_answer_factors"]
        or local != episode["local_answer_factors"]
        or total <= prefix
        or not first
        or (
            root is not None
            and row["continuation"]
            != {
                "root_input_id": root.spec["root_input_id"],
                "reconstructed_prefix_deliveries": prefix,
                "suffix_deliveries": total - prefix,
                "first_suffix_draw_key": first,
                "prefix_is_training_data": False,
            }
        )
    ):
        raise ValueError(f"Saved suffix or native delivery count differs for {task['key']}")
    return {
        "native_deliveries": total,
        "local_factors": local,
        "prefix_deliveries": prefix,
        "verified_training_choices": total - prefix,
        "first_draw": first,
        "multi_choice_decisions_by_act": dict(choices),
        "multi_choice_families": dict(families),
        "training_return": run_return(row, base.ctx["score"]),
    }


def assess(root: Path, attempt: int, deadline: float) -> dict[str, Any]:
    collection = load(root)
    ready = require_control(collection)
    base, cfg = collection.temporal.base, collection.cfg
    before = frozen(root, base.ctx)
    profile = _shared_snapshot(Path.home() / SHARED_PROFILE)
    store = journal(collection, False)
    owner_path = store.workspace / f"attempt-{attempt}.json"
    resources_path = store.workspace.with_name(f"{store.workspace.name}-{attempt}-resources.json")
    owner, resource = (identified(path) for path in (owner_path, resources_path))
    plan = cfg["study"]
    keys = {task["key"] for task in plan}
    if (
        owner["status"] != COMPLETE
        or owner["config_id"] != store.config_id
        or owner["stop"] is not None
        or owner["frozen_checks"] != before
        or owner["optimizer_updates"] != 0
        or owner["training_admission_granted"] is not False
        or any(owner[k] is not v for k, v in SCOPE.items())
        or set(owner["games"]) != keys
        or set(owner["seals"]) != keys
        or resource["status"] != "completed"
        or resource["exit_code"] != 0
        or resource["cap"] is not None
        or resource["limits"] != LIMITS
        or resource["artifacts"]["roots"] != [str(store.workspace)]
        or resource["command"]
        != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--collect", str(attempt)]
    ):
        raise ValueError("Require the exact completed owner coverage collection")
    output = _private_path(root, f"{AREA}/assessment-v1-{attempt}")
    output.mkdir()
    verified: dict[str, dict[str, Any]] = {}
    counts: Counter[str] = Counter()
    with (store.workspace / "session.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        if json.loads((store.workspace / "config-at-launch.json").read_text()) != store.recipe:
            raise ValueError("The owner launch recipe changed")
        for i, task in enumerate(plan, 1):
            key = task["key"]
            seal = store.completed(key, request(collection, task))
            if seal is None or seal["report_id"] != owner["seals"][key]:
                raise ValueError(f"Missing exact episode seal for {key}")
            row = seal["result"]
            if (
                row != owner["games"][key]
                or row["task"] != task
                or row["outcome"] not in {"win", "loss"}
            ):
                raise ValueError(f"Require a genuine matched terminal game for {key}")
            evidence = replay(collection, row, store.path(key), output / key, deadline)
            verified[key] = {**row, **evidence}
            counts["sealed_files"] += len(seal["sources"])
            for label in ("native_deliveries", "local_factors", "prefix_deliveries"):
                counts[label] += evidence[label]
            if i % 12 == 0:
                print(f"Reconstructed {i}/{len(plan)} saved coverage games.", flush=True)
        unchanged(base, before, deadline)
        check_sources(root, cfg["implementation"])
        if (
            execution_runtime(base.ctx["node"]) != base.runtime
            or _shared_snapshot(Path.home() / SHARED_PROFILE) != profile
        ):
            raise ValueError("Frozen runtime or shared profile changed")
    if tally(plan, verified, None) != owner["outcomes"]:
        raise ValueError("The saved outcome denominator differs")

    by_partition: dict[str, Any] = {}
    root_rows = {}
    for name in ("train", BRANCH):
        by_partition[name] = {}
        for p in PLAYERS:
            batch = [
                row
                for row in verified.values()
                if (row["task"]["partition"], row["task"]["player"]) == (name, p)
            ]
            acts: Counter[int] = Counter()
            families: Counter[str] = Counter()
            for row in batch:
                acts.update(row["multi_choice_decisions_by_act"])
                families.update(row["multi_choice_families"])
            by_partition[name][str(p)] = {
                "games": len(batch),
                "distinct_worlds": len({row["task"]["seed"] for row in batch}),
                "wins": sum(row["outcome"] == "win" for row in batch),
                "act1_clears": sum(row["completed_acts"] >= 1 for row in batch),
                "act1_bosses_reached": sum(
                    any(b["act"] == 1 for b in row["bosses_reached"]) for row in batch
                ),
                "distinct_training_returns": len({row["training_return"] for row in batch}),
                "verified_training_choices": sum(row["verified_training_choices"] for row in batch),
                "multi_choice_decisions_by_act": {str(a): count for a, count in acts.items()},
                "multi_choice_families": dict(families),
            }
    for root_id, spec in collection.roots.items():
        runs = [row for row in verified.values() if row["task"].get("root") == root_id]
        if len(runs) != 3 or len({row["first_draw"] for row in runs}) != 3:
            raise ValueError("Require three distinct model draws per verified root")
        root_rows[root_id] = {
            "initializer": spec.spec["source_task"]["player"],
            "floor": spec.spec["floor"],
            "terminal_floors": [row["maximum_floor"] for row in runs],
            "terminal_returns": [row["training_return"] for row in runs],
            "suffix_deliveries": [row["verified_training_choices"] for row in runs],
            "act1_clears": sum(row["completed_acts"] >= 1 for row in runs),
        }
    varied = {
        str(p): sum(
            row["initializer"] == p and len(set(row["terminal_returns"])) > 1
            for row in root_rows.values()
        )
        for p in PLAYERS
    }
    return native_win4_game.write(
        output / "report.json",
        {
            "schema_version": "native-a8-model-owned-coverage-audit-v1",
            "status": STATUS,
            "config_id": store.config_id,
            "environment_id": cfg["environment_id"],
            "control_id": ready["report_id"],
            "owner": source(root, owner_path),
            "resources": source(root, resources_path),
            "outcomes": owner["outcomes"],
            "audit_counts": dict(counts),
            "by_partition": by_partition,
            "roots": root_rows,
            "varied_roots_by_initializer": varied,
            "frozen_checks": before,
            "native_game_launches": 0,
            "optimizer_updates": 0,
            **SCOPE,
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt", type=int)
    args = parser.parse_args()
    if any(os.environ.get(name) != "1" for name in THREADS):
        raise SystemExit("Use the pinned numerical environment")
    report = assess(Path.cwd(), args.attempt, time.monotonic() + 280)
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "status",
                    "outcomes",
                    "audit_counts",
                    "varied_roots_by_initializer",
                    "report_id",
                )
            }
        )
    )
