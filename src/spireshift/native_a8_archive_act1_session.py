"""Qualify independent normal-start A8 Act 1 demonstrations without fitting."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift import native_a8_replay_probe as replay
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_archive_act1_game import CLEAR, play, verify_no_delivery
from spireshift.native_a8_archive_act1_source import ActOne, matching, read
from spireshift.native_a8_archive_batch import AREA, known_seeds
from spireshift.native_a8_archive_batch import SCHEMA as ARCHIVE_SCHEMA
from spireshift.native_a8_archive_fit_inputs import ArchiveFit, archive_fit
from spireshift.native_a8_archive_fit_session import ERRORS, check_inputs
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_own_training import SCOPE
from spireshift.native_a8_tactical_session import boundary
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

MODULE = "spireshift.native_a8_archive_act1_session"
SCHEMA = "native-a8-archive-act1-admission-v2"
RECIPE = "configs/native-curriculum/sts2-v0.111.0-a8-archive-act1-v2.json"
WRAPPER = "scripts/qualify-a8-archive-act1-v2.sh"
WORKSPACE = f"{AREA}/act1-qualification-v2"
CONTROL = "archive_act1_control_verified"
CANDIDATE = "archive_act1_bank_candidate"
LIMITS = {
    "wall_seconds": 960,
    "cpu_seconds": 1440,
    "storage_bytes": 1_000_000_000,
    "resident_memory_bytes": 4_000_000_000,
}
SHORT_LIMITS = {**LIMITS, "wall_seconds": 220, "cpu_seconds": 330}


def implementation(root: Path) -> dict[str, str]:
    files = {
        WRAPPER,
        "src/spireshift/native_a8_reward_exit.py",
        "src/spireshift/native_a8_archive_act1_game.py",
        "src/spireshift/native_a8_archive_act1_source.py",
        "src/spireshift/native_a8_archive_act1_session.py",
    }
    return {name: _sha_file(root / name) for name in sorted(files)}


def load(root: Path) -> tuple[ArchiveFit, dict[str, Any], dict[str, ActOne]]:
    study = archive_fit(root)
    cfg = json.loads((root / RECIPE).read_text())
    assessment = identified(verified(root, cfg["archive_fit_assessment"]))
    intake = identified(verified(root, cfg["source_screening"]))
    if cfg["implementation"] != implementation(root):
        # The completed pilot predates type-checking corrections. Read its
        # original sealed inputs from the execution snapshot.
        if any(not (root / WORKSPACE / name).is_file() for name in ("control.json", "result.json")):
            raise ValueError("Require the exact source version for any native replay")
        check_sources(root / f"{AREA}/act1-qualification-v2-source", cfg["implementation"])
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["workspace"] != WORKSPACE
        or cfg["environment_id"] != study.base.ctx["environment_id"]
        or cfg["objective"] != study.cfg["objective"]
        or cfg["game_limits"] != study.base.cfg["game_limits"]
        or assessment["archive_bank_id"] != study.bank["report_id"]
        or assessment["games_verified"] != 48
        or assessment["frozen_checks"] != study.frozen_checks
    ):
        raise ValueError("Require the frozen archive, objective and saved comparison assessment")
    ids = [case["run_id"] for case in cfg["cases"]]
    seeds = [case["seed"] for case in cfg["cases"]]
    if (
        len(ids) != 9
        or len(set(ids)) != len(ids)
        or len(set(seeds)) != len(seeds)
        or any(not re.fullmatch(r"[0-9a-f]{16}", run_id) for run_id in ids)
        or not set(cfg["controls"]) <= set(ids)
        or len(set(cfg["controls"])) != 2
        or Counter(c["partition"] for c in cfg["cases"]) != {"train": 6, "holdout": 3}
        or any(c["partition"] != "train" for c in cfg["cases"] if c["run_id"] in cfg["controls"])
    ):
        raise ValueError("Require nine distinct sources with fixed training and holdout ownership")
    bank_cfg = json.loads(verified(root, study.cfg["archive_config"]).read_text())
    reserved = (
        known_seeds(study.base)
        | {case["seed"] for case in bank_cfg["cases"]}
        | set(study.cfg["development"] + study.cfg["final_test"])
        | {study.cfg["control"]["prefix_world"], study.cfg["control"]["ending_world"]}
    )
    if reserved.intersection(seeds):
        raise ValueError("A demonstration overlaps a used or reserved world")
    archives = {}
    for case in cfg["cases"]:
        key = case["run_id"]
        recorded = intake["sources"][key]
        if (
            recorded["status"] != "source_rejected"
            or recorded["source"] != case["source"]
            or recorded["seed"] != case["seed"]
            or key in study.bank["worlds"]
        ):
            raise ValueError("An Act 1 candidate must be a distinct screened source")
        archive = read(verified(root, case["source"]))
        if archive.journal.seed != case["seed"]:
            raise ValueError("The source seed differs from its declaration")
        archives[key] = archive
    return study, cfg, archives


def previous_stops(
    study: ArchiveFit, cfg: dict[str, Any], archives: dict[str, ActOne], deadline: float
) -> dict[str, dict[str, Any]]:
    root = study.base.root
    path = verified(root, cfg["previous_control"])
    proof = identified(path)
    old_cfg = json.loads((path.parent / "config-at-launch.json").read_text())
    store = ChunkJournal(root, old_cfg)
    cases = {case["run_id"]: case for case in cfg["cases"]}
    clean, unsealed = old_cfg["controls"]
    if (
        store.workspace != path.parent
        or store.config_id != proof["config_id"]
        or old_cfg["cases"] != cfg["cases"]
        or set(old_cfg["controls"]) & set(cfg["controls"])
        or proof["status"] != "stopped_preserving_evidence"
        or proof["frozen_checks"] != study.frozen_checks
        or proof["stop"]["run_id"] != unsealed
        or "public-receipts.jsonl.gz" not in proof["stop"]["error"]
        or proof["cases"][clean]["status"] != "diverged"
        or proof["cases"][unsealed]["status"] != "failed"
    ):
        raise ValueError("Require the exact two preserved source stops")
    seal = store.completed(clean, cases[clean])
    if (
        seal is None
        or seal["result"] != proof["cases"][clean]
        or seal["report_id"] != proof["seals"][clean]
    ):
        raise ValueError("The preserved clean stop seal differs")
    target = store.path(unsealed)
    if {str(p.relative_to(root)) for p in target.rglob("*") if p.is_file()} != set(
        cfg["previous_unsealed_files"]
    ):
        raise ValueError("The unsealed evidence inventory changed")
    check_sources(root, cfg["previous_unsealed_files"])
    frame = identified(target / "last-frame.json")
    frame.pop("report_id")
    closed = json.loads((target / "worker/closed.json").read_text())
    journal = archives[unsealed].journal
    replay.start(frame, journal)
    if closed["clean_exit"] is not True or closed["episodes"] != 1 or closed["runtime_errors"]:
        raise ValueError("The previous stop did not shut down cleanly")
    with tempfile.TemporaryDirectory(prefix="spireshift-archive-act1-stop-") as temporary:
        verify_no_delivery(study.base.ctx, target, frame, Path(temporary) / "verify.log", deadline)
    try:
        with matching():
            replay.next_choice(frame, journal, 0, len(journal.intents))
    except replay.Divergence as exc:
        return {
            clean: {**seal["result"], "previous_seal_id": seal["report_id"]},
            unsealed: {
                **cases[unsealed],
                "status": "diverged",
                "verified_deliveries": 0,
                "mismatch": exc.facts,
                "previous_control_id": proof["report_id"],
                "labels": None,
            },
        }
    raise ValueError("The preserved zero-delivery stop does not reconstruct")


def summarize(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    clear = [row for row in rows.values() if row["status"] == CLEAR]
    train = [row for row in clear if row["partition"] == "train"]
    bosses = sorted({row["act1_boss"] for row in train})
    counts = Counter(row["partition"] for row in clear)
    checks = {
        "all_attempts_resolved": all(row["status"] in {CLEAR, "diverged"} for row in rows.values()),
        "four_new_training_worlds": counts["train"] >= 4,
        "two_held_out_demonstrations": counts["holdout"] >= 2,
        "three_training_bosses": len(bosses) >= 3,
    }
    return {
        "outcomes": dict(Counter(row["status"] for row in rows.values())),
        "clear_worlds_by_partition": dict(counts),
        "training_bosses": bosses,
        "checks": checks,
        "candidate_for_separate_fitting_admission": all(checks.values()),
    }


def run(
    study: ArchiveFit,
    cfg: dict[str, Any],
    archives: dict[str, ActOne],
    control: bool,
    deadline: float,
) -> dict[str, Any]:
    base, root = study.base, study.base.root
    store = ChunkJournal(root, cfg)
    scope = ChunkJournal(root, {"workspace": f"{AREA}/execution", "schema_version": ARCHIVE_SCHEMA})
    before = study.frozen_checks
    profile = _shared_snapshot(Path.home() / SHARED_PROFILE)
    cases = {case["run_id"]: case for case in cfg["cases"]}
    keys = cfg["controls"] if control else list(cases)
    result_path = store.workspace / ("control.json" if control else "result.json")
    rows = {key: {"status": "unattempted", **cases[key]} for key in keys}
    historical = previous_stops(study, cfg, archives, deadline)
    if not control:
        rows.update(historical)
    seals = {}
    stop = None
    with scope.lock(), store.lock():
        if not control:
            proof = identified(store.workspace / "control.json")
            if proof["status"] != CONTROL or proof["config_id"] != store.config_id:
                raise ValueError("Require the native Act 1 replay control")
            for key in cfg["controls"]:
                seal = store.completed(key, cases[key])
                if seal is None or proof["seals"].get(key) != seal["report_id"]:
                    raise ValueError("The short control seal changed")
        if result_path.exists():
            saved = identified(result_path)
            if saved["config_id"] != store.config_id or saved["frozen_checks"] != before:
                raise ValueError("The saved admission result belongs to another frozen recipe")
            if not control and any(saved["cases"].get(k) != row for k, row in historical.items()):
                raise ValueError("The saved admission has different historical stops")
            for key, seal_id in saved["seals"].items():
                seal = store.completed(key, cases[key])
                if (
                    seal is None
                    or seal["report_id"] != seal_id
                    or seal["result"] != saved["cases"][key]
                ):
                    raise ValueError("The saved Act 1 replay seal changed")
            return saved
        check_sources(root, cfg["implementation"])
        for key in keys:
            if key in historical:
                continue
            case = cases[key]
            try:
                seal = store.completed(key, case)
                if seal is None:
                    if time.monotonic() >= deadline - 90:
                        raise TimeoutError("Preserve the remaining unstarted sources")
                    boundary(root, base.ctx, before, profile)
                    seed_key = f"seed-{case['seed'].lower()}"
                    if any((scope.workspace / "chunks").glob(f"*{seed_key}")):
                        raise ValueError("Preserve the previous native archive attempt")
                    scope.begin(seed_key, {"batch": store.config_id, **case})
                    target = store.begin(key, case)
                    report = play(
                        base,
                        archives[key],
                        target,
                        store.config_id,
                        min(
                            deadline, time.monotonic() + cfg["game_limits"]["episode_wall_seconds"]
                        ),
                    )
                    boundary(root, base.ctx, before, profile)
                    source_path = verified(root, case["source"])
                    label_path = target / "public-answers.jsonl.gz"
                    row = {
                        **case,
                        "status": report["status"],
                        "act1_boss": report["act1_boss"],
                        "opening": report["opening"],
                        "native_report_id": report["report_id"],
                        "verified_deliveries": report["verified_deliveries"],
                        "labels": (
                            {
                                "path": str(label_path.relative_to(root)),
                                "sha256": _sha_file(label_path),
                            }
                            if report["status"] == CLEAR
                            else None
                        ),
                    }
                    seal = store.commit(
                        key,
                        case,
                        row,
                        {str(source_path.relative_to(root)): case["source"]["sha256"]},
                    )
                    print(f"{key} {row['status']}", flush=True)
                rows[key], seals[key] = seal["result"], seal["report_id"]
            except ERRORS as exc:
                stop = {"run_id": key, "error": f"{type(exc).__name__}: {exc}"}
                if store.path(key).exists():
                    rows[key]["status"] = "failed"
                break

        check_sources(root, cfg["implementation"])
        check_inputs(study)
        boundary(root, base.ctx, before, profile)
        coverage = summarize(rows)
        short_pass = control and coverage["checks"]["all_attempts_resolved"]
        status = "archive_act1_admission_blocked"
        if stop is not None:
            status = "stopped_preserving_evidence"
        elif short_pass:
            status = CONTROL
        elif not control and coverage["candidate_for_separate_fitting_admission"]:
            status = CANDIDATE
        return write(
            result_path,
            {
                "schema_version": SCHEMA,
                "config_id": store.config_id,
                "status": status,
                "cases": rows,
                "seals": seals,
                "coverage": coverage,
                "stop": stop,
                "frozen_checks": before,
                "shared_profile_unchanged": True,
                "training_admission_granted": False,
                "full_game_playing_strength_evaluated": False,
                "optimizer_updates": 0,
                **SCOPE,
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--control", action="store_true")
    mode.add_argument("--execute", choices=("control", "study"), help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = Path.cwd()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the launcher with its fixed numerical settings")
        study, cfg, archives = load(root)
        control = args.control or args.execute == "control"
        limits = SHORT_LIMITS if control else LIMITS
        if args.preflight:
            previous_stops(study, cfg, archives, time.monotonic() + 30)
            print(json.dumps({"status": "archive_act1_sources_ready", "sources": len(archives)}))
            return 0
        store = ChunkJournal(root, cfg)
        result_path = store.workspace / ("control.json" if control else "result.json")
        if args.execute or result_path.exists():
            result = run(
                study, cfg, archives, control, time.monotonic() + limits["wall_seconds"] - 15
            )
            print(json.dumps(result), flush=True)
            return 0 if result["status"] in {CONTROL, CANDIDATE} else 2
        if _running_games():
            raise ValueError("Close STS2 and wait for any other native worker")
        tracked = run_tracked_command(
            command=[
                "uv",
                "run",
                "--no-sync",
                "python",
                "-m",
                MODULE,
                "--execute",
                "control" if control else "study",
            ],
            experiment_kind=ExperimentKind.OTHER,
            report_path=store.workspace.with_name(
                f"{store.workspace.name}-{'control' if control else 'study'}-resources.json"
            ),
            artifact_roots=[store.workspace],
            working_directory=root,
            limits=ResourceLimits(**limits),
        )
        print(json.dumps(tracked.report), flush=True)
        return 2 if tracked.exit_code is None else tracked.exit_code
    except ERRORS as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc)}), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
