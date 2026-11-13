"""Reconstruct the sealed temporal-credit comparison without playing games."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import time
from collections import Counter
from pathlib import Path
from statistics import fmean
from typing import Any

from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path, _shared_snapshot
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_feedback_session import LIMITS
from spireshift.native_a8_mix_audit import source
from spireshift.native_a8_mix_session import unchanged
from spireshift.native_a8_own_training import SCOPE
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_paired_report import summarize
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_a8_temporal_credit import FULL, SHORT
from spireshift.native_a8_temporal_credit_session import (
    AREA,
    ARMS,
    COMPLETE,
    MODULE,
    WORLDS,
    inputs,
    require_prepared,
)
from spireshift.native_a8_world_credit_audit import replay
from spireshift.native_a8_world_credit_session import tally
from spireshift.native_combat_behavior_data import intervals
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS, execution_runtime
from spireshift.native_win4_game import write

STATUS = "temporal_credit_saved_verified"


def outcomes(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "games": len(rows),
        "wins": sum(row["outcome"] == "win" for row in rows),
        "act1_clears": sum(row["completed_acts"] >= 1 for row in rows),
        "act1_bosses_reached": sum(
            any(boss["act"] == 1 for boss in row["bosses_reached"]) for row in rows
        ),
        "mean_maximum_floor": fmean(row["maximum_floor"] for row in rows),
    }


def assess(root: Path, attempt: int, deadline: float) -> dict[str, Any]:
    session = inputs(root)
    preparation, states = require_prepared(session)
    base, cfg = session.base, session.cfg
    before = frozen(root, base.ctx)
    profile_path = Path.home() / SHARED_PROFILE
    profile = _shared_snapshot(profile_path)
    store = ChunkJournal(root, cfg)
    owner_path = store.workspace / f"attempt-{attempt}.json"
    resources_path = store.workspace.with_name(f"{store.workspace.name}-{attempt}-resources.json")
    owner, resources = identified(owner_path), identified(resources_path)
    plan = cfg["study"]
    keys = {task["key"] for task in plan}
    if (
        owner["status"] != COMPLETE
        or owner["stop"] is not None
        or owner["config_id"] != store.config_id
        or owner["preparation_id"] != preparation["report_id"]
        or owner["screen_id"] != session.screen["report_id"]
        or owner["frozen_checks"] != before
        or any(
            owner[field] != 0
            for field in (
                "original_optimizer_updates",
                "optimizer_updates_on_copies",
                "forced_action_probes_used",
            )
        )
        or any(owner[field] is not expected for field, expected in SCOPE.items())
        or set(owner["games"]) != keys
        or set(owner["seals"]) != keys
        or resources["status"] != "completed"
        or resources["exit_code"] != 0
        or resources["cap"] is not None
        or resources["limits"] != LIMITS
        or resources["artifacts"]["roots"] != [str(store.workspace)]
        or resources["command"]
        != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--evaluate", str(attempt)]
    ):
        raise ValueError("Require the exact completed temporal-credit comparison")

    out = _private_path(root, f"{AREA}/assessment-v1-{attempt}")
    out.mkdir()
    rows: dict[str, dict[str, Any]] = {}
    initials: dict[str, str] = {}
    counts: Counter[str] = Counter()
    terminal_owners: dict[str, Counter[str]] = {arm: Counter() for arm in ARMS}
    with (store.workspace / "session.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        if json.loads((store.workspace / "config-at-launch.json").read_text()) != cfg:
            raise ValueError("Saved launch recipe differs")
        for i, task in enumerate(plan, 1):
            key, arm = task["key"], task["arm"]
            state = states[task["player"], arm]
            seal = store.completed(key, {"task": task, "state_id": state[2]})
            if seal is None or seal["report_id"] != owner["seals"][key]:
                raise ValueError(f"Missing exact game seal for {key}")
            row = seal["result"]
            if (
                row != owner["games"][key]
                or row["task"] != task
                or row["model_id"] != state[0].model_id
                or row["outcome"] not in {"win", "loss"}
                or initials.setdefault(task["seed"], row["initial_public_input_id"])
                != row["initial_public_input_id"]
            ):
                raise ValueError(f"Saved start, checkpoint or outcome differs for {key}")
            actual, local, _, last_owner = replay(
                base, store.path(key), out / key, row, state, deadline
            )
            counts.update(
                sealed_files=len(seal["sources"]), native_deliveries=actual, local_factors=local
            )
            if row["outcome"] == "loss":
                terminal_owners[arm][last_owner] += 1
            rows[key] = row
            if i % 16 == 0:
                print(f"Reconstructed {i}/{len(plan)} saved games.", flush=True)

        unchanged(base, before, deadline)
        after, exact_states = require_prepared(inputs(root))
        if (
            after != preparation
            or {key: state[2] for key, state in exact_states.items()}
            != {key: state[2] for key, state in states.items()}
            or execution_runtime(base.ctx["node"]) != base.runtime
            or _shared_snapshot(profile_path) != profile
        ):
            raise ValueError("The frozen states, runtime or shared profile differ")

    if tally(plan, rows, None) != owner["outcomes"]:
        raise ValueError("Saved game denominator differs")
    games = {(t["seed"], t["player"], t["arm"]): rows[t["key"]] for t in plan}
    arms: dict[str, Any] = {}
    for arm in ARMS:
        by_player = {p: [games[w, p, arm] for w in WORLDS] for p in PLAYERS}
        arms[arm] = {
            **outcomes([row for batch in by_player.values() for row in batch]),
            "by_initializer": {str(p): outcomes(batch) for p, batch in by_player.items()},
            "losses_by_terminal_encounter": dict(terminal_owners[arm]),
        }
    comparisons = {}
    for arm in ("original", "within_world", FULL):
        pair = f"{SHORT}_minus_{arm}"
        summary = summarize(
            WORLDS,
            {
                (w, p, "original" if a == arm else "fitted"): row
                for (w, p, a), row in games.items()
                if a in (arm, SHORT)
            },
        )
        if owner["development"][pair] != {"reference_arm": arm, "candidate_arm": SHORT, **summary}:
            raise ValueError("Saved paired outcome comparison differs")
        deltas = [
            [
                games[w, p, SHORT]["maximum_floor"] - games[w, p, arm]["maximum_floor"]
                for p in PLAYERS
            ]
            for w in WORLDS
        ]
        flat = [d for world in deltas for d in world]
        comparisons[pair] = {
            "mean_floor_delta": fmean(flat),
            "floor_delta_interval_95_descriptive": intervals(
                [[*world, fmean(world), 0.0] for world in deltas]
            )[2],
            "higher": sum(d > 0 for d in flat),
            "tied": flat.count(0),
            "lower": sum(d < 0 for d in flat),
        }
    return write(
        out / "report.json",
        {
            "schema_version": "native-a8-temporal-credit-saved-audit-v1",
            "status": STATUS,
            "owner": source(root, owner_path),
            "resources": source(root, resources_path),
            "config_id": store.config_id,
            "environment_id": cfg["environment_id"],
            "preparation_id": preparation["report_id"],
            "outcomes": owner["outcomes"],
            "audit_counts": dict(counts),
            "arms": arms,
            "paired_floors": comparisons,
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
    report = assess(Path.cwd(), args.attempt, time.monotonic() + 270)
    print(json.dumps({k: report[k] for k in ("status", "outcomes", "audit_counts", "report_id")}))
