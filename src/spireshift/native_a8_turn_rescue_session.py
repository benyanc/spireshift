"""Collect combat outcome contrasts for action-score training, with zero updates."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_sampling_session
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_coverage_session import Collection, load, request, require_control
from spireshift.native_a8_coverage_session import journal as coverage_journal
from spireshift.native_a8_feedback_session import LIMITS, SHORT_LIMITS
from spireshift.native_a8_mix_audit import source
from spireshift.native_a8_mix_session import unchanged
from spireshift.native_a8_own_experience import groups
from spireshift.native_a8_own_training import FAILURES, SCOPE
from spireshift.native_a8_sampling_audit import STATUS as AUDITED
from spireshift.native_a8_sampling_audit import opening_result
from spireshift.native_a8_sampling_roots import resolve
from spireshift.native_a8_sampling_session import AREA as SAMPLING_AREA
from spireshift.native_a8_sampling_session import ASSESSMENT as COVERAGE_AUDIT
from spireshift.native_a8_sampling_session import RECIPE as SAMPLING_RECIPE
from spireshift.native_a8_sampling_session import Study, journal
from spireshift.native_a8_tactical_session import boundary, frozen
from spireshift.native_a8_turn_rescue import (
    PROBE,
    RescueContinuation,
    select,
    source_root,
    summarize,
)
from spireshift.native_a8_world_credit_session import tally
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS, execution_runtime
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

AREA = "artifacts/native-a8-turn-rescue"
ASSESSMENT = f"{SAMPLING_AREA}/assessment-v1-1794256498012401000/report.json"
RECIPE = "configs/native-learning/sts2-v0.111.0-a8-turn-rescue-v1.json"
WRAPPER = "scripts/collect-a8-turn-rescues-v1.sh"
MODULE = "spireshift.native_a8_turn_rescue_session"
SCHEMA = "native-a8-turn-rescue-v1"
READY = "turn_rescue_controls_verified"
COMPLETE = "turn_rescue_collection_complete"
TERMINAL = {"win", "loss"}


def schedule(roots: list[dict[str, Any]], control: bool) -> list[dict[str, Any]]:
    return [
        {
            "key": f"{spec['id']}-draw-{draw}",
            "seed": spec["source_task"]["seed"],
            "player": spec["source_task"]["player"],
            "partition": "turn_control" if control else "turn_training_only",
            "root": spec["id"],
            "arm": "standard",
            "draw": draw,
        }
        for spec in roots
        if spec["control"] is control
        for draw in range(1 if control else 2)
    ]


def expected(
    coverage: Collection, roots: list[dict[str, Any]] | None
) -> tuple[dict[str, Any], dict[str, Any]]:
    base = coverage.temporal.base
    audit_path, bank_path = (_private_path(base.root, n) for n in (ASSESSMENT, COVERAGE_AUDIT))
    audit, bank = identified(audit_path), identified(bank_path)
    owner = identified(verified(base.root, bank["owner"]))
    prior = json.loads((base.root / SAMPLING_RECIPE).read_text())
    check_sources(base.root, prior["implementation"])
    before = frozen(base.root, base.ctx)
    if (
        audit["status"] != AUDITED
        or audit["gate"]["candidate_for_further_training_collection"] is not False
        or any(audit["gate"]["act1_clears"].values())
        or audit["gate"]["terminal_pairs"] != 16
        or bank["config_id"] != coverage_journal(coverage, False).config_id
        or audit["frozen_checks"] != before
        or bank["frozen_checks"] != before
        or audit["environment_id"] != coverage.cfg["environment_id"]
    ):
        raise ValueError("Require the verified sampling result and native training bank")
    if roots is None:
        roots = select(coverage, owner)
    control, study = schedule(roots, True), schedule(roots, False)
    if (
        len(control) != 2
        or len(study) != 24
        or len({r["source_task"]["seed"] for r in roots}) != 14
    ):
        raise ValueError("The declared training and control roots must be distinct worlds")
    paths = (
        WRAPPER,
        "src/spireshift/native_a8_sampling_audit.py",
        "src/spireshift/native_a8_turn_rescue.py",
        "src/spireshift/native_a8_turn_rescue_session.py",
    )
    return owner, {
        "schema_version": SCHEMA,
        "environment_id": coverage.cfg["environment_id"],
        "objective": coverage.cfg["objective"],
        "game_limits": coverage.cfg["game_limits"],
        "original_full_state_ids": coverage.cfg["original_full_state_ids"],
        "workspace": f"{AREA}/collection-v1",
        "control_workspace": f"{AREA}/control-v1",
        "control_resource": f"{AREA}/control-v1-resources.json",
        "sampling_audit": source(base.root, audit_path),
        "coverage_audit": source(base.root, bank_path),
        "implementation": {name: _sha_file(base.root / name) for name in paths},
        "root_probe_contract": PROBE,
        "roots": roots,
        "control": control,
        "study": study,
    }


def inputs(root: Path, *, planning: bool = False) -> Study:
    coverage = load(root)
    require_control(coverage)
    saved = None if planning else json.loads((root / RECIPE).read_text())
    bank = coverage_journal(coverage, False)
    with (bank.workspace / "session.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        owner, cfg = expected(coverage, None if saved is None else saved["roots"])
        if saved is not None and saved != cfg:
            raise ValueError("The declared turn rescue recipe changed")
        roots = {}
        for spec in cfg["roots"]:
            expected_root = {k: v for k, v in spec.items() if k not in {"id", "control"}}
            if source_root(coverage, owner, spec["source_task"]) != expected_root:
                raise ValueError("The source combat turn or reference action changed")
            roots[spec["id"]] = resolve(coverage, owner, spec)
    return Study(coverage, owner, cfg, roots)


def play(
    study: Study, store: ChunkJournal, task: dict[str, Any], deadline: float
) -> dict[str, Any]:
    spec = study.roots[task["root"]].spec
    with patch.object(native_a8_sampling_session, "SamplingContinuation", RescueContinuation):
        row = native_a8_sampling_session.play(study, store, task, deadline)
    directory = store.path(task["key"])
    endpoint = "unresolved"
    alternative_index = None
    if row["outcome"] in TERMINAL:
        root_index = spec["prefix_native_deliveries"]
        for i, group in enumerate(groups(directory, row["model_id"])):
            for frame, choice in group:
                probe = choice.get("turn_rescue_probe")
                if i != root_index:
                    if probe is not None:
                        raise ValueError("Alternative sampling escaped the single declared root")
                    continue
                public = frame["public_input"]["candidates"]
                reference, alternative_index = (
                    spec["reference_action_index"],
                    choice["action_index"],
                )
                if (
                    probe != {"contract": PROBE, "reference_action_index": reference}
                    or len(group) != 1
                    or public[reference]["label"] == public[alternative_index]["label"]
                ):
                    raise ValueError(
                        "The root did not deliver a different model-ranked legal choice"
                    )
        if alternative_index is None:
            raise ValueError("Missing delivered alternative")
        room = opening_result(directory, row, spec["floor"])
        if room is not None:
            if room[0] != spec["encounter"]:
                raise ValueError("Recorded reward must come from the same native encounter")
            endpoint = "reward" if room[1] else "loss"
    return {
        **row,
        "observed_room_outcome": endpoint,
        "encounter": spec["encounter"],
        "reference_action_index": spec["reference_action_index"],
        "alternative_action_index": alternative_index,
        "ordinary_PPO_eligible": False,
    }


def execute(study: Study, attempt: int, deadline: float, *, control: bool) -> dict[str, Any]:
    base, cfg = study.coverage.temporal.base, study.cfg
    store = journal(study, control)
    before, profile = frozen(base.root, base.ctx), _shared_snapshot(Path.home() / SHARED_PROFILE)
    plan = cfg["control" if control else "study"]
    rows: dict[str, Any] = {}
    seals: dict[str, str] = {}
    key, stop = "preflight", None

    def check() -> None:
        unchanged(base, before, deadline)
        if json.loads((base.root / RECIPE).read_text()) != cfg:
            raise ValueError("Turn rescue recipe changed after launch")
        check_sources(base.root, cfg["implementation"])
        boundary(base.root, base.ctx, before, profile)

    with store.lock():
        try:
            check()
            for task in plan:
                key = task["key"]
                expected = request(study.coverage, task)
                seal = store.completed(key, expected)
                if seal is None:
                    check()
                    if deadline - time.monotonic() < 18:
                        raise TimeoutError("Too little time to start a clean native probe")
                    store.begin(key, expected)
                    row = play(study, store, task, deadline)
                    check()
                    seal = store.commit(key, expected, row)
                    print(f"{key} {row['observed_room_outcome']}", flush=True)
                rows[key], seals[key] = seal["result"], seal["report_id"]
            key = "final_verification"
            check()
            if execution_runtime(base.ctx["node"]) != base.runtime:
                raise ValueError("Frozen numerical runtime changed")
            for root in study.roots.values():
                source = {k: v for k, v in root.spec.items() if k not in {"id", "control"}}
                if source_root(study.coverage, study.owner, root.spec["source_task"]) != source:
                    raise ValueError("The verified reference turn changed")
            if control and any(
                row["observed_room_outcome"] == "unresolved" for row in rows.values()
            ):
                raise ValueError("Short controls require a genuine native room outcome")
        except FAILURES as exc:
            stop = {"unit": key, "error": f"{type(exc).__name__}: {exc}"}
        planned = {task["key"] for task in plan}
        failed = key if stop and key in planned and store.path(key).exists() else None
        return write(
            store.workspace / ("report.json" if control else f"attempt-{attempt}.json"),
            {
                "schema_version": SCHEMA,
                "status": "stopped_preserving_evidence" if stop else READY if control else COMPLETE,
                "config_id": store.config_id,
                "outcomes": tally(plan, rows, failed),
                "summary": summarize(plan, rows),
                "games": rows,
                "seals": seals,
                "stop": stop,
                "frozen_checks": before if not stop else None,
                "optimizer_updates": 0,
                "training_admission_granted": False,
                "full_game_playing_strength_evaluated": False,
                **SCOPE,
            },
        )


def require_short(study: Study) -> dict[str, Any]:
    base, cfg = study.coverage.temporal.base, study.cfg
    store = journal(study, True)
    proof = identified(store.workspace / "report.json")
    resource = identified(_private_path(base.root, cfg["control_resource"]))
    if (
        proof["status"] != READY
        or proof["config_id"] != store.config_id
        or proof["stop"] is not None
        or proof["optimizer_updates"] != 0
        or proof["frozen_checks"] != frozen(base.root, base.ctx)
        or proof["summary"] != summarize(cfg["control"], proof["games"])
        or resource["status"] != "completed"
        or resource["cap"] is not None
        or resource["exit_code"] != 0
        or resource["limits"] != SHORT_LIMITS
        or resource["artifacts"]["roots"] != [str(store.workspace)]
        or resource["command"] != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--control"]
    ):
        raise ValueError("Require exact short native turn rescue checks")
    for task in cfg["control"]:
        key = task["key"]
        seal = store.completed(key, request(study.coverage, task))
        if (
            seal is None
            or seal["report_id"] != proof["seals"][key]
            or seal["result"] != proof["games"][key]
        ):
            raise ValueError("The verified short control changed")
    return proof


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--plan", action="store_true")
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--control", action="store_true")
    modes.add_argument("--collect", type=int)
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the launcher with its fixed numerical settings")
        study = inputs(root, planning=args.plan)
        if args.plan:
            with (root / RECIPE).open("x") as output:
                json.dump(study.cfg, output, indent=2, sort_keys=True)
                output.write("\n")
            return 0
        if args.control or args.collect is not None:
            if not args.control:
                require_short(study)
            limits = SHORT_LIMITS if args.control else LIMITS
            result = execute(
                study,
                args.collect or 0,
                started + limits["wall_seconds"] - 18,
                control=args.control,
            )
            print(json.dumps({k: v for k, v in result.items() if k not in {"games", "seals"}}))
            return 0 if result["status"] in {READY, COMPLETE} else 2
        store = journal(study, args.check)
        if args.check:
            resource = _private_path(root, study.cfg["control_resource"])
            mode, limits = ["--control"], SHORT_LIMITS
        else:
            proof = require_short(study)
            if args.preflight:
                print(
                    json.dumps(
                        {
                            "status": READY,
                            "control_id": proof["report_id"],
                            "planned_probes": len(study.cfg["study"]),
                        }
                    )
                )
                return 0
            attempt = time.time_ns()
            resource = store.workspace.with_name(f"{store.workspace.name}-{attempt}-resources.json")
            mode, limits = ["--collect", str(attempt)], LIMITS
            print(
                "Close STS2. Collect 24 training-only turn rescue probes. "
                "Allow about 6–12 minutes. Zero updates.",
                flush=True,
            )
        if resource.exists():
            raise FileExistsError("Preserve the prior resource receipt")
        tracked = run_tracked_command(
            command=["uv", "run", "--no-sync", "python", "-m", MODULE, *mode],
            experiment_kind=ExperimentKind.OTHER,
            report_path=resource,
            artifact_roots=[store.workspace],
            working_directory=root,
            limits=ResourceLimits(**limits),
        )
        print(json.dumps(tracked.report, indent=2))
        return 0 if tracked.exit_code == 0 and tracked.status == "completed" else 2
    except FAILURES as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
