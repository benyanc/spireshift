"""Reconstruct saved A8 combat contrasts and their admission gate."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import time
from collections import Counter, defaultdict
from functools import partial
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_sampling_session
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path, _shared_snapshot
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_coverage_session import request
from spireshift.native_a8_feedback_session import LIMITS
from spireshift.native_a8_mix_audit import source
from spireshift.native_a8_mix_session import unchanged
from spireshift.native_a8_own_training import SCOPE
from spireshift.native_a8_sampling_audit import saved_game
from spireshift.native_a8_sampling_session import journal
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_a8_turn_rescue import summarize
from spireshift.native_a8_turn_rescue_session import (
    AREA,
    COMPLETE,
    MODULE,
    RECIPE,
    inputs,
    play,
    require_short,
)
from spireshift.native_a8_world_credit_session import tally
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_curriculum_config import THREADS, execution_runtime
from spireshift.native_win4_game import write

STATUS = "turn_rescue_saved_verified"


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
        != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--collect", str(attempt)]
    ):
        raise ValueError("Require the exact completed owner collection")
    output = _private_path(root, f"{AREA}/assessment-v1-{attempt}")
    output.mkdir()
    rows: dict[str, Any] = {}
    alternatives: dict[str, set[int]] = defaultdict(set)
    counts: Counter[str] = Counter()
    by_encounter: dict[str, Counter[str]] = defaultdict(Counter)
    with (store.workspace / "session.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        if json.loads((store.workspace / "config-at-launch.json").read_text()) != store.recipe:
            raise ValueError("The saved launch recipe changed")
        with patch.object(native_a8_sampling_session, "game", partial(saved_game, output=output)):
            for i, task in enumerate(plan, 1):
                key = task["key"]
                seal = store.completed(key, request(study.coverage, task))
                if seal is None or seal["report_id"] != owner["seals"][key]:
                    raise ValueError(f"Missing saved combat contrast for {key}")
                row = play(study, store, task, deadline)
                if row != seal["result"] or row != owner["games"][key]:
                    raise ValueError(f"Saved combat contrast differs for {key}")
                rows[key] = row
                if row["alternative_action_index"] is not None:
                    alternatives[task["root"]].add(row["alternative_action_index"])
                by_encounter[row["encounter"]][row["observed_room_outcome"]] += 1
                counts.update(
                    sealed_files=len(seal["sources"]),
                    native_deliveries=row["native_decisions"],
                    prefix_deliveries=row["prefix_deliveries"],
                    suffix_deliveries=row["suffix_deliveries"],
                    local_factors=row["local_answer_factors"],
                )
                if i % 6 == 0:
                    print(f"Reconstructed {i}/{len(plan)} saved combat contrasts.", flush=True)
        unchanged(base, before, deadline)
        check_sources(root, cfg["implementation"])
        if (
            execution_runtime(base.ctx["node"]) != base.runtime
            or _shared_snapshot(Path.home() / SHARED_PROFILE) != profile
            or json.loads((root / RECIPE).read_text()) != cfg
        ):
            raise ValueError("Frozen runtime, shared profile or declared recipe changed")
    summary, outcomes = summarize(plan, rows), tally(plan, rows, None)
    if summary != owner["summary"] or outcomes != owner["outcomes"]:
        raise ValueError("Reconstructed outcome gate differs from the owner report")
    roots = {task["root"]: study.roots[task["root"]].spec for task in plan}
    return write(
        output / "report.json",
        {
            "schema_version": "native-a8-turn-rescue-audit-v1",
            "status": STATUS,
            "config_id": store.config_id,
            "environment_id": cfg["environment_id"],
            "owner": source(root, owner_path),
            "resources": source(root, resources_path),
            "control_id": control["report_id"],
            "summary": summary,
            "outcomes": outcomes,
            "room_outcomes": by_encounter,
            "audit_counts": dict(counts),
            "root_diagnostics": {
                "distinct_roots": len(roots),
                "below_half_health": sum(2 * s["hp"] < s["max_hp"] for s in roots.values()),
                "minimum_hp": min(s["hp"] for s in roots.values()),
                "maximum_hp": max(s["hp"] for s in roots.values()),
                "same_first_alternative_in_both_draws": sum(
                    len(indices) == 1 for indices in alternatives.values()
                ),
            },
            "frozen_checks": before,
            "native_game_launches": 0,
            "optimizer_updates": 0,
            "training_admission_granted": False,
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
    print(json.dumps(report))
