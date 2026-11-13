"""Continue the unstarted A8 practice worlds without reusing an interrupted run."""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_practice_session as previous
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.engine_worker import worker_helpers
from spireshift.native_a8_feedback_session import LIMITS as FEEDBACK_LIMITS
from spireshift.native_a8_own_training import FAILURES, SCOPE, State
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_practice_potion import REGRESSION, SCRIPT, PracticeWorker
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_flow_inputs_v12 import canonical_seed
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

MODULE = "spireshift.native_a8_practice_recovery"
RECIPE = "configs/native-learning/sts2-v0.111.0-a8-practice-continuation-v1.json"
WRAPPER = "scripts/continue-a8-practice-mix-v1.sh"
LIMITS = {**FEEDBACK_LIMITS, "wall_seconds": 270, "cpu_seconds": 480}
SCHEMA = "native-a8-practice-continuation-v1"
INTERRUPTED = "m-030-p3"
ORIGINAL_PENDING = ("m-031", "m-032")
SUPPLEMENT = "glory-lean-supplement"


def implementation(root: Path) -> dict[str, str]:
    paths = {WRAPPER, REGRESSION}
    paths.update(f"scripts/{name}" for name in worker_helpers(root, SCRIPT))
    paths.update(f"src/spireshift/native_a8_practice_{name}.py" for name in ("potion", "recovery"))
    return {name: _sha_file(root / name) for name in sorted(paths)}


def plan(original: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cases = {c["key"]: c for c in original}
    interrupted = cases["m-030"]
    if interrupted["act_definition"] != "GLORY" or interrupted["tier"] != "lean":
        raise ValueError("The declared supplement must match the interrupted training stratum")
    replacement = {
        **interrupted,
        "key": SUPPLEMENT,
        "seed_pool": [canonical_seed(f"SP1RESH1FTA8PM2S001P{i:02}") for i in range(1, 17)],
    }
    used = {s for case in original for s in case["seed_pool"]}
    if used.intersection(replacement["seed_pool"]):
        raise ValueError("The paired supplement needs a fresh practice world")
    return [*(cases[name] for name in ORIGINAL_PENDING), replacement]


def verify_control(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    path = verified(root, cfg["selector_control"])
    proof = identified(path)
    recipe = json.loads((path.parent / "config-at-launch.json").read_text())
    store = ChunkJournal(root, recipe)
    if (
        proof["status"] != "combat_selector_belt_controls_verified"
        or proof["config_id"] != store.config_id
        or proof["sources"] != recipe["sources"]
        or proof["saved_selector"]["supported_menu"] is not True
        or set(proof["live_controls"]) != {"belt-use", "belt-discard"}
        or not all(proof["frozen_checks"].values())
        or proof["shared_profile_unchanged"] is not True
    ):
        raise ValueError("Require the saved selector and both fresh native effect checks")
    check_sources(root, recipe["sources"])
    proofs = {
        "saved": proof["saved_selector"],
        **proof["live_controls"],
    }
    for key, row in proofs.items():
        request = json.loads((store.path(key) / "active.json").read_text())["request"]
        seal = store.completed(key, request)
        if seal is None or row != {**seal["result"], "seal_id": seal["report_id"]}:
            raise ValueError("The native selector control seal differs")
    return proof


def original_rows(
    root: Path,
    old: dict[str, Any],
    cfg: dict[str, Any],
    cases: list[dict[str, Any]],
    states: dict[int, State],
    prep_id: str,
) -> dict[str, Any]:
    audit = identified(verified(root, cfg["source_assessment"]))
    result = identified(verified(root, audit["original_attempt"]))
    verified(root, audit["resources"])
    store = previous.journal(root, old, False)
    if (
        audit["status"] != "stopped_practice_collection_verified"
        or audit["config_id"] != store.config_id
        or audit["preparation_id"] != prep_id
        or result["config_id"] != store.config_id
        or result["status"] != "stopped_preserving_evidence"
        or result["stop"]["unit"] != INTERRUPTED
        or audit["sealed_segments"] != 59
        or audit["affected_menus_in_sealed_segments"] != 0
        or audit["unstarted_worlds"] != list(ORIGINAL_PENDING)
    ):
        raise ValueError("Require the exact independently checked practice interruption")
    check_sources(root, audit["interrupted_files"])
    if (store.path(INTERRUPTED) / "done.json").exists():
        raise ValueError("The interrupted segment must retain its failure marker")
    rows = {}
    for case in cases:
        key = case["key"]
        if key in ORIGINAL_PENDING:
            if any(store.path(f"{key}-{suffix}").exists() for suffix in ("start", "p2", "p3")):
                raise ValueError("Only previously unstarted practice worlds may continue")
            continue
        setup = store.completed(f"{key}-start", {"case": case})
        if setup is None or setup["report_id"] != audit["verified_setup_seals"][key]:
            raise ValueError("Verified native practice start differs")
        for player in PLAYERS:
            unit = f"{key}-p{player}"
            if unit == INTERRUPTED:
                rows[unit] = {"outcome": "failed"}
                continue
            seal = store.completed(
                unit,
                {
                    "start_seal": setup["report_id"],
                    "state_id": states[player][2],
                    "player": player,
                    "preparation_id": prep_id,
                },
            )
            if seal is None or seal["report_id"] != audit["verified_segment_seals"][unit]:
                raise ValueError("Verified native practice segment differs")
            rows[unit] = {**seal["result"], "seal_id": seal["report_id"]}
    if rows != result["segments"]:
        raise ValueError("Preserved practice denominator differs")
    return rows


def summarize(
    original: list[dict[str, Any]],
    supplement: dict[str, Any],
    rows: dict[str, Any],
    new_rows: dict[str, Any],
    stop: Any,
) -> dict[str, Any]:
    prior = {**rows, **{key: v for key, v in new_rows.items() if not key.startswith(SUPPLEMENT)}}
    remaining = {key: v for key, v in new_rows.items() if key.startswith(SUPPLEMENT)}
    matched_cases = [c for c in original if c["key"] != "m-030"] + [supplement]
    available = {**prior, **remaining}
    paired = {
        f"{c['key']}-p{p}": row
        for c in matched_cases
        for p in PLAYERS
        if (row := available.get(f"{c['key']}-p{p}")) is not None
    }
    coverage = previous.status(matched_cases, paired, control=False)
    counts = Counter(
        prior.get(f"{c['key']}-p{p}", {}).get("outcome", "unattempted")
        for c in original
        for p in PLAYERS
    )
    return {
        "original_panel": {
            "planned_segments": len(original) * len(PLAYERS),
            "outcomes": dict(counts),
            "coverage": previous.status(original, prior, control=False),
            "preserved_failure": INTERRUPTED,
        },
        "paired_supplement": {
            "case": SUPPLEMENT,
            "outcomes": {
                str(p): remaining.get(f"{SUPPLEMENT}-p{p}", {}).get("outcome", "unattempted")
                for p in PLAYERS
            },
        },
        "matched_candidate": {
            "planned_worlds": len(matched_cases),
            "planned_segments": len(matched_cases) * len(PLAYERS),
            "excluded_incomplete_pair": "m-030",
            "coverage": coverage,
            "ready_for_separate_admission": stop is None and coverage["room_coverage_candidate"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--execute", type=int)
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the launcher with its fixed numerical settings")
        old, ctx, runtime, states, prep_id = previous.load_inputs(root)
        previous.require_control(root, old, prep_id)
        cfg = json.loads((root / RECIPE).read_text())
        original = ctx["practice_cases"]["collection"]
        cases = plan(original)
        if (
            cfg["schema_version"] != SCHEMA
            or cfg["objective"] != old["objective"]
            or cfg["game_limits"] != old["game_limits"]
            or cfg["environment_id"] != old["environment_id"]
            or cfg["implementation"] != implementation(root)
            or cfg["case_inventory_id"] != manifest_identifier(cases)
        ):
            raise ValueError("Continuation recipe or frozen inputs changed")
        control = verify_control(root, cfg)
        rows = original_rows(root, old, cfg, original, states, prep_id)
        store = ChunkJournal(root, cfg)
        before = frozen(root, ctx)
        if args.preflight:
            print(
                json.dumps(
                    {
                        "status": "practice_continuation_ready",
                        "preserved_segments": 59,
                        "new_segments": 6,
                        "control_id": control["report_id"],
                        "frozen_checks": before,
                    }
                )
            )
            return 0
        if args.execute is not None:
            ctx = {**ctx, "practice_cases": {"collection": cases}}
            with patch.multiple(previous, RECIPE=RECIPE, PracticeWorker=PracticeWorker):
                result = previous.collect(
                    root,
                    cfg,
                    ctx,
                    runtime,
                    states,
                    prep_id,
                    control=False,
                    attempt=args.execute,
                    deadline=started + LIMITS["wall_seconds"] - 15,
                )
            if (
                original_rows(root, old, cfg, original, states, prep_id) != rows
                or frozen(root, ctx) != before
            ):
                raise ValueError("Historical segments or frozen inputs changed")
            summary = summarize(original, cases[-1], rows, result["segments"], result["stop"])
            ready = summary["matched_candidate"]["ready_for_separate_admission"]
            output = write(
                store.workspace / f"summary-{args.execute}.json",
                {
                    "schema_version": SCHEMA,
                    "status": "matched_practice_candidate_complete"
                    if ready
                    else "practice_continuation_incomplete",
                    "continuation_report_id": result["report_id"],
                    "selector_control_id": control["report_id"],
                    "stop": result["stop"],
                    "new_segments": result["segments"],
                    **summary,
                    "optimizer_updates": 0,
                    "training_admission_granted": False,
                    "frozen_checks": before,
                    **SCOPE,
                },
            )
            print(json.dumps(output), flush=True)
            return 0 if ready else 2
        attempt = time.time_ns()
        tracked = run_tracked_command(
            command=["uv", "run", "--no-sync", "python", "-m", MODULE, "--execute", str(attempt)],
            experiment_kind=ExperimentKind.OTHER,
            report_path=store.workspace.with_name(
                f"{store.workspace.name}-{attempt}-resources.json"
            ),
            artifact_roots=[store.workspace],
            working_directory=root,
            limits=ResourceLimits(**LIMITS),
        )
        print(json.dumps(tracked.report, indent=2))
        return 0 if tracked.exit_code == 0 and tracked.status == "completed" else 2
    except FAILURES as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
