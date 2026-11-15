"""Rebuild the outcome gate from sealed native opening probes."""

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
from spireshift import native_a8_turn_rescue_session as prior
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_coverage_session import request
from spireshift.native_a8_feedback_session import LIMITS
from spireshift.native_a8_mix_audit import source
from spireshift.native_a8_mix_session import unchanged
from spireshift.native_a8_opening_contrast import summarize
from spireshift.native_a8_opening_contrast_session import (
    AREA,
    COMPLETE,
    MODULE,
    RECIPE,
    execution,
    inputs,
    play,
)
from spireshift.native_a8_own_training import SCOPE
from spireshift.native_a8_sampling_audit import saved_game
from spireshift.native_a8_sampling_session import journal
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_a8_world_credit_session import tally
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_curriculum_config import THREADS, execution_runtime
from spireshift.native_win4_game import write

STATUS = "opening_contrast_saved_verified"
PARTS = (1, 2)


def assess(root: Path, attempt: int, deadline: float, part: int | None) -> dict[str, Any]:
    study = inputs(root)
    with execution(study):
        control = prior.require_short(study)
    base, cfg = study.coverage.temporal.base, study.cfg
    before, profile = frozen(root, base.ctx), _shared_snapshot(Path.home() / SHARED_PROFILE)
    store = journal(study, False)
    owner_path = store.workspace / f"attempt-{attempt}.json"
    resource_path = store.workspace.with_name(f"{store.workspace.name}-{attempt}-resources.json")
    owner, resource = (identified(path) for path in (owner_path, resource_path))
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
        raise ValueError("Require the exact completed owner opening collection")
    output = _private_path(root, f"{AREA}/assessment-v2-{attempt}")
    evidence = {
        "config_id": store.config_id,
        "environment_id": cfg["environment_id"],
        "owner": source(root, owner_path),
        "resources": source(root, resource_path),
        "control_id": control["report_id"],
        "audit_source_sha256": _sha_file(Path(__file__)),
        "frozen_checks": before,
    }
    rows: dict[str, Any] = {}
    counts: Counter[str] = Counter()
    sources = []
    with (store.workspace / "session.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        if json.loads((store.workspace / "config-at-launch.json").read_text()) != store.recipe:
            raise ValueError("The saved launch recipe changed")
        if part is not None:
            directory = output / f"part-{part}"
            directory.mkdir(parents=True)
            tasks = plan[part - 1 :: len(PARTS)]
            with patch.object(
                native_a8_sampling_session, "game", partial(saved_game, output=directory)
            ):
                for i, task in enumerate(tasks, 1):
                    key = task["key"]
                    seal = store.completed(key, request(study.coverage, task))
                    if seal is None or seal["report_id"] != owner["seals"][key]:
                        raise ValueError(f"Missing saved opening probe for {key}")
                    row = play(study, store, task, deadline)
                    if row != seal["result"] or row != owner["games"][key]:
                        raise ValueError(f"Saved opening probe differs for {key}")
                    rows[key] = row
                    counts.update(sealed_files=len(seal["sources"]))
                    if i % 8 == 0:
                        print(f"Reconstructed {i}/{len(tasks)} probes in part {part}.", flush=True)
        else:
            for i in PARTS:
                path = output / f"part-{i}/report.json"
                saved = identified(path)
                tasks = plan[i - 1 :: len(PARTS)]
                expected = {t["key"]: owner["games"][t["key"]] for t in tasks}
                if (
                    saved["part"] != i
                    or saved["status"] != "opening_contrast_part_verified"
                    or saved["games"] != expected
                    or any(saved[key] != value for key, value in evidence.items())
                ):
                    raise ValueError("Reconstructed part does not match the owner collection")
                rows.update(saved["games"])
                counts.update(sealed_files=saved["sealed_files"])
                sources.append(source(root, path))
        unchanged(base, before, deadline)
        check_sources(root, cfg["implementation"])
        if (
            execution_runtime(base.ctx["node"]) != base.runtime
            or _shared_snapshot(Path.home() / SHARED_PROFILE) != profile
            or json.loads((root / RECIPE).read_text()) != cfg
            or _sha_file(Path(__file__)) != evidence["audit_source_sha256"]
        ):
            raise ValueError("Frozen runtime, shared profile or opening recipe changed")
    if part is not None:
        return write(
            output / f"part-{part}/report.json",
            {
                **evidence,
                "status": "opening_contrast_part_verified",
                "part": part,
                "games": rows,
                "sealed_files": counts["sealed_files"],
            },
        )
    summary, outcomes = summarize(plan, rows, study.roots), tally(plan, rows, None)
    if summary != owner["summary"] or outcomes != owner["outcomes"]:
        raise ValueError("The reconstructed opening outcome gate differs")
    rooms: dict[str, Counter[str]] = defaultdict(Counter)
    contrasts: dict[str, list[str]] = defaultdict(list)
    for task in plan:
        key = task["key"]
        row, spec = rows[key], study.roots[task["root"]].spec
        room = row["observed_room_outcome"]
        rooms[spec["encounter"]][room] += 1
        if room != spec["reference_room_outcome"]:
            contrasts[task["root"]].append(key)
        counts.update(
            native_deliveries=row["native_decisions"],
            prefix_deliveries=row["prefix_deliveries"],
            suffix_deliveries=row["suffix_deliveries"],
            local_factors=row["local_answer_factors"],
            act1_clears=row["completed_acts"] >= 1,
        )
    return write(
        output / "report.json",
        {
            **evidence,
            "schema_version": "native-a8-opening-contrast-audit-v1",
            "status": STATUS,
            "verified_parts": sources,
            "summary": summary,
            "outcomes": outcomes,
            "room_outcomes": rooms,
            "contrast_probes_by_root": contrasts,
            "audit_counts": dict(counts),
            "native_game_launches": 0,
            "optimizer_updates": 0,
            "training_admission_granted": False,
            **SCOPE,
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt", type=int)
    parser.add_argument("--part", type=int, choices=PARTS)
    args = parser.parse_args()
    if any(os.environ.get(name) != "1" for name in THREADS):
        raise SystemExit("Use the pinned numerical environment")
    report = assess(Path.cwd(), args.attempt, time.monotonic() + 275, args.part)
    print(json.dumps({key: value for key, value in report.items() if key != "games"}))
