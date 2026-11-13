"""Collect matched native opening outcomes for action-ranking admission."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from functools import partial
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_turn_rescue_session as prior
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_coverage_session import Collection
from spireshift.native_a8_coverage_session import journal as coverage_journal
from spireshift.native_a8_feedback_session import LIMITS, SHORT_LIMITS
from spireshift.native_a8_mix_audit import source
from spireshift.native_a8_opening_contrast import (
    DistinctContinuation,
    roots_from_source,
    select,
    summarize,
)
from spireshift.native_a8_own_training import FAILURES
from spireshift.native_a8_sampling_roots import resolve
from spireshift.native_a8_sampling_session import RECIPE as SAMPLING_RECIPE
from spireshift.native_a8_sampling_session import Study, journal
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_a8_turn_rescue_audit import STATUS as AUDITED
from spireshift.native_a8_turn_rescue_session import play as play_probe
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

AREA = "artifacts/native-a8-opening-contrast"
AUDIT = f"{prior.AREA}/assessment-v1-1794269728053855000/report.json"
RECIPE = "configs/native-learning/sts2-v0.111.0-a8-opening-contrast-v1.json"
WRAPPER = "scripts/collect-a8-opening-contrasts-v1.sh"
MODULE = "spireshift.native_a8_opening_contrast_session"
SCHEMA = "native-a8-opening-contrast-v1"
READY = "opening_contrast_controls_verified"
COMPLETE = "opening_contrast_collection_complete"
DIAGNOSTIC_WORLDS = {"SP1RESH1FTA8CV1T013", "SP1RESH1FTA8CV1T020"}


def schedule(roots: list[dict[str, Any]], control: bool) -> list[dict[str, Any]]:
    return [
        {
            "key": f"{spec['id']}-draw-{draw}",
            "seed": spec["source_task"]["seed"],
            "player": spec["source_task"]["player"],
            "partition": "opening_control" if control else "opening_training_only",
            "root": spec["id"],
            "arm": "standard",
            "draw": draw,
        }
        for spec in roots
        if spec["control"] is control
        for draw in range(2)
    ]


def inputs(root: Path, *, planning: bool = False) -> Study:
    earlier = prior.inputs(root)
    coverage, owner = earlier.coverage, earlier.owner
    base = coverage.temporal.base
    bank = coverage_journal(coverage, False)
    audit_path = _private_path(root, AUDIT)
    audit = identified(audit_path)
    if (
        audit["status"] != AUDITED
        or audit["config_id"] != journal(earlier, False).config_id
        or audit["environment_id"] != coverage.cfg["environment_id"]
        or audit["frozen_checks"] != frozen(root, base.ctx)
        or audit["summary"]["resolved_room_outcomes"] != len(earlier.cfg["study"])
        or audit["summary"]["candidate_for_separate_preference_admission"] is not False
        or audit["summary"]["reward_successes"] != 0
    ):
        raise ValueError("Require the saved audit of the completed losing-turn study")
    sampling = json.loads((root / SAMPLING_RECIPE).read_text())
    check_sources(root, sampling["implementation"])
    previous_menus = {s["root_input_id"] for s in [*earlier.cfg["roots"], *sampling["roots"]]}
    saved = None if planning else json.loads((root / RECIPE).read_text())
    roots = {}
    with (bank.workspace / "session.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        specs = (
            select(coverage, owner, previous_menus, DIAGNOSTIC_WORLDS)
            if saved is None
            else saved["roots"]
        )
        for spec in specs:
            if (
                spec["root_input_id"] in previous_menus
                or spec["source_task"]["seed"] in DIAGNOSTIC_WORLDS
                or source_spec(spec) not in roots_from_source(coverage, owner, spec["source_task"])
            ):
                raise ValueError("The declared early opening or native reference outcome changed")
            roots[spec["id"]] = resolve(coverage, owner, spec)
    control, study = schedule(specs, True), schedule(specs, False)
    if len(control) != 4 or len(study) != 32 or len(roots) != 18:
        raise ValueError("Require two disjoint controls and sixteen training roots")
    if len({s["source_task"]["seed"] for s in specs}) != len(roots):
        raise ValueError("Every opening needs a distinct training world")
    paths = (
        WRAPPER,
        "src/spireshift/native_a8_opening_contrast.py",
        "src/spireshift/native_a8_opening_contrast_session.py",
        "src/spireshift/native_a8_turn_rescue_audit.py",
    )
    cfg = {
        **earlier.cfg,
        "schema_version": SCHEMA,
        "workspace": f"{AREA}/collection-v1",
        "control_workspace": f"{AREA}/control-v1",
        "control_resource": f"{AREA}/control-v1-resources.json",
        "turn_audit": source(root, audit_path),
        "diagnostic_worlds_excluded": sorted(DIAGNOSTIC_WORLDS),
        "implementation": {
            **earlier.cfg["implementation"],
            **{name: _sha_file(root / name) for name in paths},
        },
        "root_probe_contract": "two_distinct_legal_alternatives_at_combat_opening_v1",
        "roots": specs,
        "control": control,
        "study": study,
    }
    if saved is not None and saved != cfg:
        raise ValueError("The declared opening contrast recipe changed")
    return Study(coverage, owner, cfg, roots)


def source_spec(spec: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in spec.items() if k not in {"id", "control"}}


def play(
    study: Study, store: ChunkJournal, task: dict[str, Any], deadline: float
) -> dict[str, Any]:
    with patch.object(
        prior, "RescueContinuation", partial(DistinctContinuation, draw=task["draw"])
    ):
        return play_probe(study, store, task, deadline)


@contextmanager
def execution(study: Study) -> Iterator[None]:
    def confirmed_source(
        coverage: Collection, owner: dict[str, Any], task: dict[str, Any]
    ) -> dict[str, Any] | None:
        spec = next(root.spec for root in study.roots.values() if root.spec["source_task"] == task)
        expected = source_spec(spec)
        return expected if expected in roots_from_source(coverage, owner, task) else None

    # Reuse the pinned collector and its checkpoint, receipt, and resume checks.
    # These bindings apply only within this new versioned entry point.
    with patch.multiple(
        prior,
        RECIPE=RECIPE,
        SCHEMA=SCHEMA,
        MODULE=MODULE,
        READY=READY,
        COMPLETE=COMPLETE,
        play=play,
        source_root=confirmed_source,
        summarize=partial(summarize, roots=study.roots),
    ):
        yield


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
        with execution(study):
            if args.control or args.collect is not None:
                if not args.control:
                    prior.require_short(study)
                limits = SHORT_LIMITS if args.control else LIMITS
                result = prior.execute(
                    study,
                    args.collect or 0,
                    started + limits["wall_seconds"] - 18,
                    control=args.control,
                )
                print(json.dumps({k: v for k, v in result.items() if k not in {"games", "seals"}}))
                return 0 if result["status"] in {READY, COMPLETE} else 2
            proof = None if args.check else prior.require_short(study)
            if args.preflight:
                assert proof is not None
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

        store = journal(study, args.check)
        if args.check:
            resource = _private_path(root, study.cfg["control_resource"])
            mode, limits = ["--control"], SHORT_LIMITS
        else:
            attempt = time.time_ns()
            resource = store.workspace.with_name(f"{store.workspace.name}-{attempt}-resources.json")
            mode, limits = ["--collect", str(attempt)], LIMITS
            print(
                "Close STS2. Collect 32 training-only alternatives at earlier combat menus. "
                "Allow about 8–15 minutes. Zero optimizer updates.",
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
