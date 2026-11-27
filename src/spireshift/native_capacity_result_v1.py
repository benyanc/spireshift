"""Independently verify the complete capacity experiment without games or updates."""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_paired_report import diagnostics
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_capacity_inputs_v1 import EVALUATION, METHODS
from spireshift.native_capacity_inputs_v1 import load as load_parent
from spireshift.native_capacity_inputs_v2 import RECIPE, assessment, context, load
from spireshift.native_capacity_recovery_v1 import FAILED, game_task
from spireshift.native_capacity_session_v1 import COMPLETE, comparison_report
from spireshift.native_capacity_session_v2 import ContinuationJournal
from spireshift.native_combat_intent_model import load as load_state
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_flow_verification_v12 import records
from spireshift.native_qualified_learning_result_v1 import architecture_diagnostics
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

MODULE = "spireshift.native_capacity_result_v1"
WORKSPACE = "artifacts/native-policy-capacity/assessment-v1"
STATUS = "capacity_seals_lineages_and_native_endings_verified"
DEEP_STATUS = "completed_capacity_study_independently_verified"
LIMITS = dict(
    wall_seconds=275,
    cpu_seconds=600,
    storage_bytes=1_000_000_000,
    resident_memory_bytes=4_000_000_000,
)


def episode(folder: Path, row: dict[str, Any]) -> None:
    saved = identified(folder / "report.json")
    terminal = row["outcome"] in {"win", "loss"}
    if (
        saved["report_id"] != row["episode_report_id"]
        or saved["status"] != ("complete" if terminal else "capped")
        or saved["native_terminal"] is not terminal
        or saved["shutdown"]["clean_exit"] is not True
        or saved["shutdown"]["runtime_errors"]
        or saved["actual_deliveries_independently_verified"] != row["native_decisions"]
        or saved["optimizer_updates"] != 0
    ):
        raise ValueError(
            "A game lacks its exact native outcome, verified deliveries or clean reset"
        )
    if terminal:
        native = saved["native_ending"]
        identity = native["private_final_identity"]
        if (
            native["native_ending_evidence_agrees"] is not True
            or identity["seed"] != row["task"]["seed"]
            or identity["ascension"] != 8
            or identity["native_game_over"] is not True
            or identity["native_player_dead"] is not (row["outcome"] == "loss")
        ):
            raise ValueError("A terminal result differs from the original native ending facts")


def audit(root: Path, deadline: float, *, recount_public: bool = False) -> dict[str, Any]:
    cfg = load(root)
    ctx = context(root, cfg)
    before = frozen(root, ctx)
    profile = _shared_snapshot(Path.home() / SHARED_PROFILE)
    out = root / (
        "artifacts/native-policy-capacity/assessment-public-recount-v1"
        if recount_public
        else WORKSPACE
    )
    out.mkdir(parents=True, exist_ok=True)
    final = out / "report.json"
    if final.exists():
        result = identified(final)
        check_sources(root, result["sources"])
        return result
    proof = assessment(root, cfg)
    parent = load_parent(root)
    result_path = root / cfg["workspace"] / "report.json"
    saved = identified(result_path)
    if (
        saved["status"] != COMPLETE
        or saved["config_id"] != manifest_identifier(cfg)
        or saved["stop"] is not None
        or saved["excluded_training_units"] != [FAILED]
        or saved["optimizer_updates_on_copies"] != 16517
    ):
        raise ValueError("Require the exact completed fixed-round capacity experiment")
    check_sources(root, saved["sources"])
    store = ContinuationJournal(root, cfg, parent, proof)
    seals: dict[str, str] = {}
    sources = {
        RECIPE: _sha_file(root / RECIPE),
        str(result_path.relative_to(root)): _sha_file(result_path),
        str(Path(__file__).relative_to(root)): _sha_file(Path(__file__)),
    }

    def require(key: str, request: dict[str, Any]) -> dict[str, Any]:
        if time.monotonic() >= deadline:
            raise TimeoutError("The read-only capacity audit reached its short-check boundary")
        seal = store.completed(key, request)
        if seal is None or saved["chunk_seals"].get(key) != seal["report_id"]:
            raise ValueError(f"A capacity unit is missing or changed: {key}")
        seals[key] = seal["report_id"]
        path = store.path(key) / "done.json"
        sources[str(path.relative_to(root))] = _sha_file(path)
        return {"seal_id": seal["report_id"], **seal["result"]}

    counts: dict[str, Counter[str]] = {}
    fits = []
    capped = []
    with ChunkJournal(root, parent).lock(), ChunkJournal(root, cfg).lock():
        require(
            "source-copies",
            {
                "source_states": {
                    str(p): load_state(verified(root, cfg["starting_states"][str(p)]))[1]
                    for p in (2, 3)
                },
                "initialization": cfg["initialization"],
            },
        )
        current = {
            m: {p: load_state(store.path("source-copies") / f"p{p}-{m}.json") for p in (2, 3)}
            for m in METHODS
        }
        reference = current["standard"].copy()
        for r in range(1, 65):
            for p in (2, 3):
                for method in METHODS if (r + p) % 2 else METHODS[::-1]:
                    rows = []
                    cohort = counts.setdefault(f"p{p}-{method}", Counter())
                    for i in range((r - 1) * 16 + 1, r * 16 + 1):
                        task = game_task(cfg["plan"]["training"][i - 1], i, p, r, method)
                        request = {"task": task, "behavior_state_id": current[method][p][1]}
                        if task["key"] == FAILED:
                            if request != proof["failed_request"]:
                                raise ValueError(
                                    "The failed-cell exclusion changed its behavior state"
                                )
                            row = {"outcome": "failed", "seal_id": proof["report_id"]}
                        else:
                            row = require(task["key"], request)
                            if (
                                row["task"] != task
                                or row["model_id"] != current[method][p][0].model.model_id
                            ):
                                raise ValueError(
                                    "A training game differs from its declared behavior policy"
                                )
                            episode(store.path(task["key"]), row)
                            if row["outcome"] == "capped":
                                capped.append(task["key"])
                            else:
                                cohort["act1_clears"] += row["completed_acts"] >= 1
                                cohort["act2_clears"] += row["completed_acts"] >= 2
                        cohort[row["outcome"]] += 1
                        rows.append(row)
                    key = f"fit-p{p}-{method}-r{r:03d}"
                    fitted = require(
                        key,
                        {
                            "player": p,
                            "method": method,
                            "round": r,
                            "prior_state_id": current[method][p][1],
                            "game_seals": [row["seal_id"] for row in rows],
                        },
                    )
                    state, state_id = load_state(store.path(key) / "shared.json")
                    updates = fitted["work"]["optimizer_updates"]
                    prior = current[method][p][0]
                    if (
                        state_id != fitted["state_id"]
                        or state.model.model_id != fitted["model_id"]
                        or state.actor_adam.steps - prior.actor_adam.steps != updates
                        or state.value_adam.steps - prior.value_adam.steps != updates
                        or state.actor_adam.steps != fitted["actor_steps"]
                        or state.value_adam.steps != fitted["value_steps"]
                        or fitted["eligible_terminal_worlds"]
                        != sum(row["outcome"] in {"win", "loss"} for row in rows)
                    ):
                        raise ValueError(
                            "A complete actor/critic/Adam lineage or admitted cohort changed"
                        )
                    current[method][p] = state, state_id
                    fits.append(fitted)
        if (
            fits != saved["training"]
            or {m: {str(p): current[m][p][1] for p in (2, 3)} for m in METHODS}
            != saved["final_states"]
        ):
            raise ValueError("The round-64 selection or full fitting history changed")
        games: dict[tuple[str, int, str], dict[str, Any]] = {}
        panels: dict[int, list[tuple[int, str, dict[str, Any]]]] = {2: [], 3: []}
        for i, seed in enumerate(cfg["plan"]["development"], 1):
            for p in (2, 3):
                for method in EVALUATION:
                    behavior = reference[p] if method == "reference" else current[method][p]
                    key = f"development-{i:04d}-p{p}-{method}"
                    task = dict(
                        key=key,
                        seed=seed,
                        seed_id=i,
                        player=p,
                        round=64,
                        partition="development",
                        arm="shared",
                    )
                    row = require(key, {"task": task, "behavior_state_id": behavior[1]})
                    if (
                        row["task"] != task
                        or row["model_id"] != behavior[0].model.model_id
                        or row["outcome"] not in {"win", "loss"}
                    ):
                        raise ValueError("A frozen evaluation policy, world or outcome changed")
                    folder = store.path(key)
                    episode(folder, row)
                    if recount_public:
                        rebuilt = diagnostics(
                            folder / "shared-public.jsonl.gz", row["outcome"] == "win"
                        )
                        if any(row[k] != v for k, v in rebuilt.items()):
                            raise ValueError(
                                "Evaluation diagnostics differ from the public journal"
                            )
                    games[seed, p, method] = row
                    sample = i % 8 == 1 if recount_public else i in {1, 65}
                    if method == "reference" and sample:
                        picked: list[tuple[int, str, dict[str, Any]]] = []
                        for j, event in enumerate(records(folder / "shared-public.jsonl.gz")):
                            if (
                                event["kind"] != "policy_input"
                                or event["frame"]["source_family"] != "combat_turn"
                            ):
                                continue
                            rank = int.from_bytes(
                                hashlib.sha256(f"capacity-health-v1|{key}|{j}".encode()).digest()[
                                    :8
                                ],
                                "big",
                            )
                            entry = (-rank, f"{key}:{j}", event["frame"]["public_input"])
                            if len(picked) < 4:
                                heapq.heappush(picked, entry)
                            elif entry[0] > picked[0][0]:
                                heapq.heapreplace(picked, entry)
                        panels[p].extend(picked)
        comparisons = comparison_report(cfg["plan"]["development"], games)
        if comparisons != saved["comparisons"] or seals != saved["chunk_seals"]:
            raise ValueError("The paired results or linked denominator differ")
        health = {
            m: architecture_diagnostics(
                panels, {"start": reference, "final": current[m]}, ctx["score"]
            )
            for m in METHODS
        }
        if frozen(root, ctx) != before or _shared_snapshot(Path.home() / SHARED_PROFILE) != profile:
            raise ValueError("Frozen build, checkpoints/full Adam or personal profile changed")
        return write(
            final,
            {
                "status": DEEP_STATUS if recount_public else STATUS,
                "source_report_id": saved["report_id"],
                "source_config_id": saved["config_id"],
                "source_workspace": cfg["workspace"],
                "verified_units": len(seals),
                "training_counts": {k: dict(v) for k, v in counts.items()},
                "capped_training_units": capped,
                "failed_training_units": [FAILED],
                "failed_prefix_training_admitted": False,
                "full_model_and_Adam_fits_reloaded": len(fits),
                "optimizer_updates_on_copies": sum(
                    row["work"]["optimizer_updates"] for row in fits
                ),
                "development_games_verified": len(games),
                "raw_public_diagnostics_recounted": recount_public,
                "comparisons": comparisons,
                "final_states": saved["final_states"],
                "architecture_diagnostics": health,
                "architecture_panel": (
                    "same_four_hash_selected_reference_combat_states_on_fixed_reference_worlds"
                ),
                "frozen_checks": before,
                "shared_profile_unchanged": True,
                "games_launched": 0,
                "optimizer_updates": 0,
                "promotion_allowed": False,
                "official_live_qualification_granted": False,
                "final_test_worlds_used": False,
                "scope": "128_worlds_two_fixed_initializers_native_only_no_competence_claim",
                "sources": sources,
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = Path.cwd()
    if any(os.environ.get(k) != "1" for k in THREADS):
        raise ValueError("Require the pinned numerical runtime")
    out = root / WORKSPACE
    out.mkdir(parents=True, exist_ok=True)
    if args.execute is None:
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
            report_path=out / f"resources-{attempt}.json",
            artifact_roots=[out],
            limits=ResourceLimits(**LIMITS),
        )
        print(json.dumps(tracked.report))
        return 0 if tracked.exit_code == 0 and tracked.report["cap"] is None else 2
    result = audit(root, time.monotonic() + LIMITS["wall_seconds"] - 10)
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in {"sources", "comparisons", "architecture_diagnostics"}
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
