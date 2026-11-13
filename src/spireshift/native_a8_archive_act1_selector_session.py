"""Qualify the recorded Act 1 rest-site cancellation on two clean replay stops."""

from __future__ import annotations

import argparse
import json
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from functools import partial
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_archive_act1_game as game
from spireshift import native_a8_archive_act1_selectors as selectors
from spireshift import native_a8_replay_probe as replay
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_archive_act1_session import load as previous_inputs
from spireshift.native_a8_archive_act1_source import ActOne
from spireshift.native_a8_archive_batch import AREA
from spireshift.native_a8_archive_batch import SCHEMA as ARCHIVE_SCHEMA
from spireshift.native_a8_archive_fit_inputs import ArchiveFit
from spireshift.native_a8_archive_fit_session import ERRORS, check_inputs
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_replay_source import Journal
from spireshift.native_a8_tactical_session import boundary
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_flow_verification_v12 import records
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

MODULE = "spireshift.native_a8_archive_act1_selector_session"
RECIPE = "configs/native-curriculum/sts2-v0.111.0-a8-archive-act1-selectors-v2.json"
WORKSPACE = f"{AREA}/act1-selector-qualification-v2"
SCHEMA = "native-a8-archive-act1-selector-qualification-v2"
LIMITS = {
    "wall_seconds": 270,
    "cpu_seconds": 420,
    "storage_bytes": 400_000_000,
    "resident_memory_bytes": 4_000_000_000,
}
Prefix = tuple[tuple[str, int, str], ...]


def prefix_check(study: ArchiveFit, archive: ActOne, directory: Path) -> tuple[Prefix, str]:
    locale = study.base.ctx["native"]["localization"] / "localization_eng"
    names = {
        (kind, key.removesuffix(".title")): label
        for kind in ("card", "potion", "relic")
        for key, label in json.loads((locale / f"{kind}s.json").read_text()).items()
        if key.endswith(".title")
    }
    journal = replace(archive.journal, reward_names=names)
    cursor = 0
    prefix = []
    with selectors.matching():
        for row in records(directory / replay.TRACE):
            frame = row["frame"]
            index, cursor, domain = replay.next_choice(frame, journal, cursor, len(journal.intents))
            if index is None:
                raise ValueError("Expected a bound action on the saved prefix")
            public = frame["public_input"]
            prefix.append((manifest_identifier(public), index, domain))
            if (index, domain) != (
                row["choice"]["action_index"],
                row["receipt"]["delivery_domain"],
            ):
                raise ValueError("Unexpected change before the recorded rest cancellation")
        frame = identified(directory / "last-frame.json")
        if journal.intents[cursor].kind != selectors.REST_CANCEL:
            raise ValueError("Expected the recorded cancellation at the saved stop")
        index, _, domain = replay.next_choice(frame, journal, cursor, len(journal.intents))
        public = frame["public_input"]
        if index is None or public["candidates"][index]["verb"] != "cancel":
            raise ValueError("The current selector must offer the recorded cancellation")
        prefix.append((manifest_identifier(public), index, domain))
        return tuple(prefix), public["candidates"][index]["label"]


@contextmanager
def matched_prefix(prefix: Prefix) -> Iterator[None]:
    with selectors.matching():
        choose = replay.next_choice
        delivered = 0

        def checked(
            frame: dict[str, Any], journal: Journal, cursor: int, end: int
        ) -> tuple[int | None, int, str]:
            nonlocal delivered
            index, following, domain = choose(frame, journal, cursor, end)
            if delivered < len(prefix):
                if (manifest_identifier(frame["public_input"]), index, domain) != prefix[delivered]:
                    raise ValueError("Native prefix or the first revised action differs")
                delivered += 1
            return index, following, domain

        with patch.object(replay, "next_choice", checked):
            yield


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the launcher with its fixed numerical settings")
        study, previous, _ = previous_inputs(root)
        cfg = json.loads((root / RECIPE).read_text())
        path = verified(root, cfg["previous_result"])
        prior_cfg = json.loads((path.parent / "config-at-launch.json").read_text())
        prior = ChunkJournal(root, prior_cfg)
        proof = identified(path)
        if (
            cfg["schema_version"] != SCHEMA
            or cfg["workspace"] != WORKSPACE
            or cfg["objective"] != study.cfg["objective"]
            or cfg["environment_id"] != study.base.ctx["environment_id"]
            or cfg["case_seconds"] != study.cfg["game_limits"]["episode_wall_seconds"]
            or path != prior.workspace / "result.json"
            or proof["config_id"] != prior.config_id
            or proof["frozen_checks"] != study.frozen_checks
            or proof["stop"] is not None
            or proof["schema_version"] != "native-a8-archive-act1-selector-qualification-v1"
            or len(cfg["cases"]) != 2
            or len(set(cfg["cases"])) != 2
        ):
            raise ValueError("Require the exact saved sources and frozen A8 inputs")
        check_sources(root, cfg["implementation"])
        candidates = {case["run_id"]: case for case in previous["cases"]}
        store = ChunkJournal(root, cfg)
        scope = ChunkJournal(
            root, {"workspace": f"{AREA}/execution", "schema_version": ARCHIVE_SCHEMA}
        )
        summary: dict[str, Any] = {}
        archives = {}
        for key in cfg["cases"]:
            case = candidates[key]
            previous_seal_id = proof["saved_regressions"][key]["previous_seal_id"]
            seal = prior.completed(key, {"case": case, "previous_seal_id": previous_seal_id})
            rep = identified(prior.path(key) / "report.json")
            if (
                seal is None
                or seal["report_id"] != proof["seals"][key]
                or seal["result"] != proof["cases"][key]
                or seal["result"]["status"] != "diverged"
                or seal["result"]["report_id"] != rep["report_id"]
                or rep["shutdown"]["clean_exit"] is not True
                or rep["shutdown"]["runtime_errors"]
                or rep["verified_deliveries"] < 1
                or rep["stop"]["mismatch"]["field"] != "unique legal action"
            ):
                raise ValueError("Replays require a clean and independently verified selector stop")
            archive = selectors.read(verified(root, case["source"]))
            prefix, next_label = prefix_check(study, archive, prior.path(key))
            archives[key] = (archive, prefix, seal["report_id"])
            summary[key] = {
                "unchanged_prefix_deliveries": len(prefix) - 1,
                "first_revised_action": next_label,
                "previous_seal_id": seal["report_id"],
            }
        if args.preflight:
            print(json.dumps({"status": "saved_selector_regressions_verified", "cases": summary}))
            return 0
        result_path = store.workspace / "result.json"
        if result_path.is_file():
            result = identified(result_path)
            if result["config_id"] != store.config_id or result["saved_regressions"] != summary:
                raise ValueError("Saved selector qualification differs")
            for key, seal_id in result["seals"].items():
                request = {"case": candidates[key], "previous_seal_id": archives[key][2]}
                seal = store.completed(key, request)
                if (
                    seal is None
                    or seal["report_id"] != seal_id
                    or seal["result"] != result["cases"][key]
                ):
                    raise ValueError("Saved selector result seal differs")
            print(json.dumps(result))
            return 0 if result["stop"] is None else 2
        if _running_games():
            raise ValueError("Close STS2 and wait for any other native worker")
        if not args.execute:
            tracked = run_tracked_command(
                command=["uv", "run", "--no-sync", "python", "-m", MODULE, "--execute"],
                experiment_kind=ExperimentKind.OTHER,
                report_path=store.workspace.with_name(
                    "act1-selector-qualification-v2-resources.json"
                ),
                artifact_roots=[store.workspace],
                working_directory=root,
                limits=ResourceLimits(**LIMITS),
            )
            print(json.dumps(tracked.report))
            return 2 if tracked.exit_code is None else tracked.exit_code

        before, profile = study.frozen_checks, _shared_snapshot(Path.home() / SHARED_PROFILE)
        deadline = started + LIMITS["wall_seconds"] - 12
        outcomes = {key: {"status": "unattempted"} for key in cfg["cases"]}
        seals = {}
        stop = None
        with scope.lock(), store.lock():
            for key in cfg["cases"]:
                case = candidates[key]
                archive, prefix, predecessor = archives[key]
                request = {"case": case, "previous_seal_id": predecessor}
                try:
                    seal = store.completed(key, request)
                    if seal is None:
                        if time.monotonic() >= deadline - 45:
                            raise TimeoutError("Preserve the unstarted selector cases")
                        boundary(root, study.base.ctx, before, profile)
                        scope.begin(f"selector-v2-seed-{case['seed'].lower()}", request)
                        target = store.begin(key, request)
                        with patch.object(game, "matching", partial(matched_prefix, prefix)):
                            result = game.play(
                                study.base,
                                archive,
                                target,
                                store.config_id,
                                min(deadline, time.monotonic() + cfg["case_seconds"]),
                            )
                        boundary(root, study.base.ctx, before, profile)
                        verified(root, case["source"])
                        labels = target / "public-answers.jsonl.gz"
                        row = {
                            **result,
                            "partition": case["partition"],
                            "labels": (
                                {"path": str(labels.relative_to(root)), "sha256": _sha_file(labels)}
                                if result["status"] == game.CLEAR
                                else None
                            ),
                        }
                        seal = store.commit(key, request, row)
                        print(f"{key} {row['status']}", flush=True)
                    outcomes[key], seals[key] = seal["result"], seal["report_id"]
                except ERRORS as exc:
                    stop = {"run_id": key, "error": f"{type(exc).__name__}: {exc}"}
                    if store.path(key).exists():
                        outcomes[key]["status"] = "failed"
                    break
            check_sources(root, cfg["implementation"])
            check_inputs(study)
            boundary(root, study.base.ctx, before, profile)
            report = write(
                result_path,
                {
                    "schema_version": SCHEMA,
                    "config_id": store.config_id,
                    "status": "stopped_preserving_evidence"
                    if stop
                    else "archive_selector_check_complete",
                    "saved_regressions": summary,
                    "cases": outcomes,
                    "seals": seals,
                    "stop": stop,
                    "frozen_checks": before,
                    "optimizer_updates": 0,
                    "training_admission_granted": False,
                    "full_game_playing_strength_evaluated": False,
                },
            )
        print(json.dumps(report))
        return 2 if stop else 0
    except ERRORS as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
