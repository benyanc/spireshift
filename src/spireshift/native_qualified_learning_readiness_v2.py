"""Verify both saved checker cases, then run two fresh normal-start controls without learning."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_combat_intent_model import load as load_state
from spireshift.native_combat_intent_model import using_intent_encoder
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_flow_verification_v12 import records
from spireshift.native_qualified_learning_inputs_v2 import RECIPE as ORIGINAL
from spireshift.native_qualified_learning_inputs_v3 import RECIPE as PARENT
from spireshift.native_qualified_learning_inputs_v3 import assessment as original_assessment
from spireshift.native_qualified_learning_inputs_v3 import context
from spireshift.native_qualified_learning_inputs_v3 import load as load_parent
from spireshift.native_qualified_learning_verification_v3 import verify_episode
from spireshift.native_qualified_learning_worker_v3 import play
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

RECIPE = "configs/native-learning/sts2-v0.111.0-a8-qualified-model-only-readiness-v2.json"
MODULE = "spireshift.native_qualified_learning_readiness_v2"
SCHEMA = "native-qualified-learning-readiness-v2"
EXCLUDED = ("train-0571-p3-learner", "train-0572-p3-learner")
LIMITS = {
    "wall_seconds": 275,
    "cpu_seconds": 600,
    "storage_bytes": 1_000_000_000,
    "resident_memory_bytes": 4_000_000_000,
}


def cases() -> list[dict[str, Any]]:
    return [
        {
            "key": f"verifier-control-p{p}",
            "seed": f"SP1RESH1FTA8Q2C00{i}P{p}",
            "seed_id": i,
            "player": p,
            "round": 0,
            "partition": "verifier-control",
            "arm": "shared",
        }
        for i, p in enumerate((2, 3), 1)
    ]


def implementation(root: Path) -> dict[str, str]:
    parent = json.loads((root / PARENT).read_text())
    names = {
        *parent["implementation"],
        PARENT,
        "scripts/engine-card-answer-verify-v3.mjs",
        "scripts/engine-card-answer-verify-v3.test.mjs",
        "src/spireshift/native_qualified_learning_verification_v3.py",
        "src/spireshift/native_qualified_learning_worker_v3.py",
        "src/spireshift/native_qualified_learning_readiness_v2.py",
        "tests/unit/test_native_qualified_learning_readiness_v2.py",
    }
    return {name: _sha_file(root / name) for name in sorted(names)}


def load(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    parent = load_parent(root)
    cfg: dict[str, Any] = json.loads((root / RECIPE).read_text())
    if (
        cfg["schema_version"] != SCHEMA
        or verified(root, cfg["parent_recipe"]) != root / PARENT
        or cfg["workspace"] != "artifacts/native-qualified-learning/readiness-v2"
        or cfg["implementation"] != implementation(root)
        or cfg["cases"] != cases()
        or cfg["limits"] != LIMITS
        or cfg["objective"] != parent["objective"]
        or cfg["game_limits"] != parent["game_limits"]
    ):
        raise ValueError("The no-update verifier control scope changed")
    check_sources(root, cfg["implementation"])
    before = original_assessment(root, parent)
    verified(root, cfg["source_resources"])
    for p in (2, 3):
        _, state_id = load_state(verified(root, cfg["states"][str(p)]))
        if state_id != before["current_states"][str(p)]:
            raise ValueError("The saved full checkpoint/Adam for the control changed")
    stop = identified(verified(root, cfg["source_stop"]))
    check_sources(root, stop["sources"])
    if (
        stop["status"] != "stopped_preserving_evidence"
        or stop["config_id"] != manifest_identifier(parent)
        or stop["chunk_seals"] != before["inherited_units"]
        or stop["optimizer_updates_on_copies"] != 3813
        or stop["stop"]["unit"] != EXCLUDED[1]
        or "selection-cursor.jsonl.gz" not in stop["stop"]["error"]
        or "ENOENT" not in stop["stop"]["error"]
        or not all(stop["frozen_checks"].values())
    ):
        raise ValueError("Require the exact preserved absent-unused-ledger stop")
    chunks = root / parent["workspace"] / "chunks"
    if {p.name for p in chunks.iterdir()} != {EXCLUDED[1]}:
        raise ValueError("The stopped continuation has missing or newly started worlds")
    return cfg, parent, before


def audit(
    root: Path,
    cfg: dict[str, Any],
    parent: dict[str, Any],
    before: dict[str, Any],
    output: Path,
    deadline: float,
) -> dict[str, Any]:
    path = output / "assessment.json"
    if path.exists():
        result = identified(path)
        check_sources(root, result["sources"])
        return result
    ctx = context(root, parent)
    original = json.loads((root / ORIGINAL).read_text())
    sources = {RECIPE: _sha_file(root / RECIPE)}
    sources.update(
        {
            ref["path"]: ref["sha256"]
            for ref in (cfg["source_stop"], cfg["source_resources"], parent["source_assessment"])
        }
    )
    diagnostics: dict[str, Any] = {}
    requests: dict[str, Any] = {}
    for key, workspace in zip(EXCLUDED, (original["workspace"], parent["workspace"]), strict=True):
        folder = root / workspace / "chunks" / key
        active = json.loads((folder / "active.json").read_text())
        request = active["request"]
        if (folder / "done.json").exists() or request["task"]["key"] != key:
            raise ValueError("The original failed cell or marker changed")
        state, state_id = load_state(verified(root, cfg["states"]["3"]))
        if request["behavior_state_id"] != state_id:
            raise ValueError("Failed cell used a different behavior checkpoint/full Adam")
        target = output / f"saved-{key}"
        target.mkdir()
        with using_intent_encoder():
            count = verify_episode(
                ctx,
                identified(folder / "start.json"),
                "own_policy",
                folder,
                target,
                deadline,
                model=state.model,
            )
        proof = identified(target / "ordered-answer-raw-verification.json")
        final = None
        for row in records(folder / "shared-public.jsonl.gz"):
            if row["kind"] == "final_observation":
                if final is not None:
                    raise ValueError("Extra final saved observation")
                final = row["frame"]
        identity = None
        for row in records(folder / "worker/private-transcript.jsonl.gz"):
            if row["request"]["cmd"] == "run_identity" and row["response"].get("active"):
                identity = row["response"]
        closed = json.loads((folder / "worker/closed.json").read_text())
        if (
            final is None
            or final["terminal"] is not True
            or final["ending"]["victory"] is not False
            or identity is None
            or identity["seed"] != request["task"]["seed"]
            or identity["native_player_dead"] is not True
            or identity["native_game_over"] is not True
            or identity["action_executor_running"]
            or identity["pending_host_operation"]
            or closed["clean_exit"] is not True
            or closed["runtime_errors"]
        ):
            raise ValueError("The diagnostic cell lacks a clean native loss and exact seed")
        diagnostics[key] = {
            "native_deliveries": count,
            "local_factors": proof["local_factors"],
            "selection_cursor_present": proof["selection_cursor_present"],
            "exact_choices_probabilities_and_native_loss_verified": True,
            "training_admitted": False,
        }
        requests[key] = request
        for source in (*folder.rglob("*"), *target.rglob("*")):
            if source.is_file():
                sources[str(source.relative_to(root))] = _sha_file(source)
    if [diagnostics[key]["selection_cursor_present"] for key in EXCLUDED] != [True, False]:
        raise ValueError("Both present-used and absent-unused saved ledger cases are required")
    return write(
        path,
        {
            "schema_version": SCHEMA,
            "status": "saved_present_and_absent_cursor_cases_verified",
            "parent_config_id": manifest_identifier(parent),
            "base_assessment_id": before["report_id"],
            "inherited_units": before["inherited_units"],
            "inherited_optimizer_updates": 3813,
            "by_initializer": before["by_initializer"],
            "sealed_training_games": 1146,
            "excluded_training_requests": requests,
            "diagnostic_cells": diagnostics,
            "preserved_failed_training_games": 2,
            "unstarted_training_games": 900,
            "planned_training_games": 2048,
            "planned_development_games": 128,
            "development_games_started": 0,
            "games_launched": 0,
            "optimizer_updates": 0,
            "sources": sources,
        },
    )


def execute(
    root: Path, cfg: dict[str, Any], parent: dict[str, Any], before: dict[str, Any]
) -> dict[str, Any]:
    ctx = context(root, parent)
    protected = frozen(root, ctx)
    profile = _shared_snapshot(Path.home() / SHARED_PROFILE)
    store = ChunkJournal(root, cfg)
    deadline = time.monotonic() + LIMITS["wall_seconds"] - 10
    with store.lock():
        final = store.workspace / "report.json"
        if final.exists():
            result = identified(final)
            check_sources(root, result["sources"])
            return result
        saved = audit(root, cfg, parent, before, store.workspace, deadline)
        controls = []
        for case in cases():
            state, state_id = load_state(verified(root, cfg["states"][str(case["player"])]))
            request = {"task": case, "behavior_state_id": state_id}
            seal = store.completed(case["key"], request)
            if seal is None:
                if _running_games() or time.monotonic() + 110 >= deadline:
                    raise ValueError(
                        "Cannot start the next short control safely within its declaration"
                    )
                target = store.begin(case["key"], request)
                row = play(
                    {
                        **ctx,
                        "config": {"plan": cfg["game_limits"]},
                        "execution_id": store.config_id,
                    },
                    case,
                    target,
                    state,
                    deadline - 5,
                )
                seal = store.commit(case["key"], request, row)
            row = seal["result"]
            proof = identified(
                store.path(case["key"]) / "verification/ordered-answer-raw-verification.json"
            )
            if (
                row["outcome"] not in {"win", "loss"}
                or row["model_id"] != state.model.model_id
                or row["task"] != case
                or row["native_decisions"] != proof["native_deliveries"]
                or row["local_answer_factors"] != proof["local_factors"]
                or proof["native_deliveries"] <= 0
            ):
                raise ValueError("The normal-start verifier control did not finish exactly")
            controls.append(
                {
                    "key": case["key"],
                    "seal_id": seal["report_id"],
                    "outcome": row["outcome"],
                    "native_deliveries": proof["native_deliveries"],
                    "local_factors": proof["local_factors"],
                    "selection_cursor_present": proof["selection_cursor_present"],
                }
            )
        if not any(not row["selection_cursor_present"] for row in controls):
            raise ValueError("The fresh controls did not cover an actually absent cursor journal")
        if (
            frozen(root, ctx) != protected
            or _shared_snapshot(Path.home() / SHARED_PROFILE) != profile
        ):
            raise ValueError("The frozen build, checkpoints/full Adam or shared profile changed")
        sources = {RECIPE: _sha_file(root / RECIPE)}
        sources.update(
            {
                str(p.relative_to(root)): _sha_file(p)
                for p in store.workspace.rglob("*")
                if p.is_file() and p != final
            }
        )
        return write(
            final,
            {
                "schema_version": SCHEMA,
                "status": "saved_and_fresh_normal_start_verifier_controls_passed",
                "config_id": store.config_id,
                "saved_assessment_id": saved["report_id"],
                "controls": controls,
                "native_games_launched": len(controls),
                "optimizer_updates": 0,
                "training_admission_granted": False,
                "frozen_checks": protected,
                "shared_profile_unchanged": True,
                "sources": sources,
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = Path.cwd()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Require the pinned numerical runtime")
        cfg, parent, before = load(root)
        if args.execute is None:
            area = root / cfg["workspace"]
            area.mkdir(parents=True, exist_ok=True)
            attempt = time.time_ns()
            tracked = run_tracked_command(
                command=[
                    "uv",
                    "run",
                    "--no-sync",
                    "python",
                    "-B",
                    "-m",
                    MODULE,
                    "--execute",
                    str(attempt),
                ],
                working_directory=root,
                experiment_kind=ExperimentKind.OTHER,
                report_path=area / f"resources-{attempt}.json",
                artifact_roots=[area],
                limits=ResourceLimits(**LIMITS),
            )
            print(json.dumps(tracked.report))
            return 0 if tracked.exit_code == 0 and tracked.report["cap"] is None else 2
        if _running_games():
            raise ValueError("Close STS2 and wait for other native workers")
        with ChunkJournal(root, parent).lock():
            result = execute(root, cfg, parent, before)
        print(json.dumps({k: v for k, v in result.items() if k != "sources"}))
        return 0
    except (ValueError, OSError, KeyError, TimeoutError) as exc:
        print(
            json.dumps(
                {"status": "stopped_preserving_evidence", "error": str(exc), "optimizer_updates": 0}
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
