"""Reconstruct the paired sampling result from sealed native evidence."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import time
from collections import Counter
from collections.abc import Iterator
from functools import partial
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_own_experience, native_a8_sampling_session, native_win4_game
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path, _shared_snapshot
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_coverage_session import request
from spireshift.native_a8_feedback_session import LIMITS
from spireshift.native_a8_mix_audit import first_difference, source
from spireshift.native_a8_mix_data import room_evidence
from spireshift.native_a8_mix_session import Study, unchanged
from spireshift.native_a8_own_policy import CONTRACT
from spireshift.native_a8_own_training import SCOPE, State
from spireshift.native_a8_paired_report import diagnostics
from spireshift.native_a8_rescue_game import TRACE, decisions
from spireshift.native_a8_sampling_session import (
    AREA,
    COMPLETE,
    MODULE,
    inputs,
    journal,
    require_short,
    summarize,
)
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_a8_world_credit_session import tally
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS, execution_runtime

STATUS = "act1_sampling_saved_verified"


def saved_game(
    base: Study,
    store: ChunkJournal,
    task: dict[str, Any],
    state: State,
    deadline: float,
    *,
    output: Path,
) -> dict[str, Any]:
    """Supply the sampling runner with a verified saved episode instead of a game."""
    model = state[0]
    directory = store.path(task["key"])
    start, episode = (identified(directory / name) for name in ("start.json", "report.json"))
    native = episode["native_ending"]
    identity = native["private_final_identity"]
    won, cpu = episode["full_run_win"], native["usage"]["native_cpu_seconds"]
    if (
        start["scenario"] != task
        or start["kind"] != "natural_training"
        or start["evaluation_eligible"] is not False
        or episode["start_id"] != start["report_id"]
        or episode["model_id"] != model.model_id
        or episode["status"] != "complete"
        or episode["optimizer_updates"] != 0
        or episode["native_terminal"] is not True
        or episode["shutdown"]["clean_exit"] is not True
        or episode["shutdown"]["runtime_errors"]
        or native["native_ending_evidence_agrees"] is not True
        or identity["seed"] != task["seed"]
        or identity["ascension"] != 8
        or identity["native_victory_room"] is not won
        or not (identity["native_game_over"] or (not won and identity["native_player_dead"]))
        or cpu > base.ctx["score"].evaluation_objective.whole_run_budget
    ):
        raise ValueError(f"Invalid saved native start, ending or reset for {task['key']}")
    out = output / task["key"]
    out.mkdir()
    with patch.object(native_win4_game, "policy", native_a8_own_experience.policy):
        actual = native_win4_game.verify_episode(
            base.ctx, start, "own_policy", directory, out, deadline, model=model
        )
    if actual != episode["actual_deliveries_independently_verified"]:
        raise ValueError("Saved native delivery count differs")
    return {
        "task": task,
        "policy_contract": CONTRACT,
        "outcome": "win" if won else "loss",
        "model_id": model.model_id,
        "episode_report_id": episode["report_id"],
        "initial_public_input_id": episode["initial_public_input_id"],
        "native_cpu_seconds": cpu,
        "native_decisions": actual,
        "local_answer_factors": episode["local_answer_factors"],
        **diagnostics(directory / TRACE, won),
    }


def opening_result(directory: Path, row: dict[str, Any], floor: int) -> tuple[str, bool] | None:
    ending: dict[str, Any] | None = None

    def observations() -> Iterator[dict[str, Any]]:
        nonlocal ending
        for _, frame, delivered in decisions(directory / TRACE):
            if delivered is None:
                ending = frame
            elif delivered["receipt"]["delivery_domain"] == "native":
                yield frame["public_input"]

    # The last saved frame establishes a native loss for the active room.
    # Keep only the public frames needed by this one episode's room classifier.
    public = list(observations())
    if ending is None:
        raise ValueError("Missing final public frame")
    return room_evidence(public, ending, row["native_decisions"]).outcomes.get((1, floor))


def assess(root: Path, attempt: int, deadline: float) -> dict[str, Any]:
    study = inputs(root)
    control = require_short(study)
    base, cfg = study.coverage.temporal.base, study.cfg
    before, profile = frozen(root, base.ctx), _shared_snapshot(Path.home() / SHARED_PROFILE)
    store = journal(study, False)
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
        != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--compare", str(attempt)]
    ):
        raise ValueError("Require the exact completed owner sampling comparison")
    out = _private_path(root, f"{AREA}/assessment-v1-{attempt}")
    out.mkdir()
    rows: dict[str, Any] = {}
    openings: dict[str, tuple[str, bool] | None] = {}
    counts: Counter[str] = Counter()
    with (store.workspace / "session.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        if json.loads((store.workspace / "config-at-launch.json").read_text()) != store.recipe:
            raise ValueError("The saved launch recipe changed")
        with patch.object(native_a8_sampling_session, "game", partial(saved_game, output=out)):
            for i, task in enumerate(plan, 1):
                key = task["key"]
                seal = store.completed(key, request(study.coverage, task))
                if seal is None or seal["report_id"] != owner["seals"][key]:
                    raise ValueError(f"Missing episode seal for {key}")
                row = native_a8_sampling_session.play(study, store, task, deadline)
                if row != seal["result"] or row != owner["games"][key]:
                    raise ValueError(f"Saved sampling result differs for {key}")
                rows[key] = row
                spec = study.roots[task["root"]].spec
                opening = openings[key] = opening_result(store.path(key), row, spec["floor"])
                if opening is not None and opening[0] != spec["encounter"]:
                    raise ValueError("Opening encounter differs from the declared root")
                counts.update(
                    sealed_files=len(seal["sources"]),
                    native_deliveries=row["native_decisions"],
                    prefix_deliveries=row["prefix_deliveries"],
                    suffix_deliveries=row["suffix_deliveries"],
                    local_factors=row["local_answer_factors"],
                )
                if i % 8 == 0:
                    print(f"Reconstructed {i}/{len(plan)} saved sampling games.", flush=True)
        unchanged(base, before, deadline)
        check_sources(root, cfg["implementation"])
        if (
            execution_runtime(base.ctx["node"]) != base.runtime
            or _shared_snapshot(Path.home() / SHARED_PROFILE) != profile
        ):
            raise ValueError("Frozen numerical runtime or shared profile changed")

    result = summarize(plan, rows)
    if result != owner["summary"] or tally(plan, rows, None) != owner["outcomes"]:
        raise ValueError("Saved outcome denominator or clear gate differs")
    pair_stats: Counter[str] = Counter()
    for task in plan:
        if task["arm"] != "standard":
            continue
        old_key, new_key = task["key"], task["key"].removesuffix("standard") + "sharp"
        old, new = rows[old_key], rows[new_key]
        change = first_difference(store.path(old_key) / TRACE, store.path(new_key) / TRACE)
        delta = new["maximum_floor"] - old["maximum_floor"]
        pair_stats["different_choices"] += change is not None
        pair_stats[
            "higher_floor" if delta > 0 else "lower_floor" if delta < 0 else "same_floor"
        ] += 1
        a, b = openings[old_key], openings[new_key]
        pair_stats["opposite_opening_outcomes"] += a is not None and b is not None and a[1] != b[1]
    arms: dict[str, Any] = {}
    for arm in result["act1_clears"]:
        games = [row for row in rows.values() if row["task"]["arm"] == arm]
        room_results = [openings[row["task"]["key"]] for row in games]
        arms[arm] = {
            "games": len(games),
            "act1_clears": result["act1_clears"][arm],
            "bosses_reached": sum(bool(row["bosses_reached"]) for row in games),
            "opening_rewards_reached": sum(room[1] for room in room_results if room is not None),
        }
    return native_win4_game.write(
        out / "report.json",
        {
            "schema_version": "native-a8-act1-sampling-audit-v1",
            "status": STATUS,
            "config_id": store.config_id,
            "environment_id": cfg["environment_id"],
            "owner": source(root, owner_path),
            "resources": source(root, resources_path),
            "control_id": control["report_id"],
            "outcomes": owner["outcomes"],
            "gate": result,
            "arms": arms,
            "pairs": dict(pair_stats),
            "audit_counts": dict(counts),
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
    report = assess(Path.cwd(), args.attempt, time.monotonic() + 275)
    print(
        json.dumps({k: report[k] for k in ("status", "gate", "pairs", "audit_counts", "report_id")})
    )
