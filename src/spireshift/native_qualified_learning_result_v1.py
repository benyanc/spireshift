"""Independently audit the completed fixed A8 study and bounded saved-state model diagnostics."""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import math
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_policy import dense_features, score_features
from spireshift.full_run_ppo_math import log_softmax
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_paired_report import diagnostics
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_combat_intent_model import encode
from spireshift.native_combat_intent_model import load as load_state
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_flow_verification_v12 import records
from spireshift.native_qualified_learning_inputs_v2 import RECIPE as ORIGINAL
from spireshift.native_qualified_learning_inputs_v4 import RECIPE, assessment, context, load
from spireshift.native_qualified_learning_readiness_v2 import EXCLUDED
from spireshift.native_qualified_learning_recovery_v1 import task
from spireshift.native_qualified_learning_session_v1 import COMPLETE, development_report
from spireshift.native_qualified_learning_session_v4 import ContinuationJournal
from spireshift.native_win4_game import write
from spireshift.neural_combat import _numpy
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

MODULE = "spireshift.native_qualified_learning_result_v1"
WORKSPACE = "artifacts/native-qualified-learning/assessment-v1"
STATUS = "completed_a8_training_and_fresh_comparison_independently_verified"
LIMITS = {
    "wall_seconds": 275,
    "cpu_seconds": 600,
    "storage_bytes": 1_000_000_000,
    "resident_memory_bytes": 4_000_000_000,
}


def architecture_diagnostics(
    samples: dict[int, list[tuple[int, str, dict[str, Any]]]],
    states: dict[str, Any],
    score: Any,
) -> dict[str, Any]:
    np = _numpy()
    result: dict[str, Any] = {}
    for p in (2, 3):
        if not samples[p]:
            raise ValueError("Require bounded saved combat states for both initializers")
        for label in ("start", "final"):
            model = states[label][p][0].model
            saturated = units = 0
            entropy: list[float] = []
            hidden_ranges: list[float] = []
            end_prob: list[float] = []
            for _, _, public in samples[p]:
                rows, _ = encode(public, model, score)
                w, b, _, _ = model.actor.unpack()
                hidden = np.tanh(dense_features(rows, model.actor.dimension) @ w.T + b)
                saturated += int(np.sum(np.abs(hidden) > 0.95))
                units += int(hidden.size)
                hidden_ranges.append(float(np.mean(np.ptp(hidden, axis=0))))
                logs = log_softmax(score_features(cast(Any, model.actor), rows), 0.8)
                h = -math.fsum(math.exp(x) * x for x in logs)
                entropy.append(h / math.log(len(logs)) if len(logs) > 1 else 0.0)
                end_prob.append(
                    math.fsum(
                        math.exp(logs[i])
                        for i, c in enumerate(public["candidates"])
                        if c["verb"] == "end_turn"
                    )
                )
            result[f"p{p}-{label}"] = {
                "sampled_choice_states": len(samples[p]),
                "dimension": model.actor.dimension,
                "hidden_units": model.actor.hidden_units,
                "actor_parameters": model.actor.parameter_count,
                "critic_parameters": len(model.value_weights),
                "hidden_activation_fraction_above_abs_0_95": saturated / units,
                "mean_hidden_range_across_legal_actions": math.fsum(hidden_ranges)
                / len(hidden_ranges),
                "mean_entropy_fraction_of_uniform": math.fsum(entropy) / len(entropy),
                "mean_end_turn_probability": math.fsum(end_prob) / len(end_prob),
            }
    return {
        "sampling": "four_hash_selected_combat_states_per_every_fourth_development_cell_v1",
        "training_labels_created": 0,
        "measurements": result,
    }


def audit(root: Path) -> dict[str, Any]:
    cfg = load(root)
    ctx = context(root, cfg)
    protected = frozen(root, ctx)
    profile = _shared_snapshot(Path.home() / SHARED_PROFILE)
    output = root / WORKSPACE
    output.mkdir(parents=True, exist_ok=True)
    final = output / "report.json"
    if final.exists():
        result = identified(final)
        check_sources(root, result["sources"])
        return result
    proof = assessment(root, cfg)
    report_path = root / cfg["workspace"] / "report.json"
    report = identified(report_path)
    if (
        report["status"] != COMPLETE
        or report["config_id"] != manifest_identifier(cfg)
        or report["stop"] is not None
        or report["optimizer_updates_on_copies"] != 7101
        or report["excluded_training_units"] != list(EXCLUDED)
    ):
        raise ValueError("Require the exact completed fixed-round A8 training and comparison")
    check_sources(root, report["sources"])
    original = json.loads((root / ORIGINAL).read_text())
    store = ContinuationJournal(root, cfg, original, proof)
    states = {p: load_state(verified(root, cfg["starting_states"][str(p)])) for p in (2, 3)}
    starting = states.copy()
    seals: dict[str, str] = {}
    counts: dict[str, Counter[str]] = {str(p): Counter() for p in (2, 3)}
    training: list[dict[str, Any]] = []
    sources = {
        RECIPE: _sha_file(root / RECIPE),
        str(report_path.relative_to(root)): _sha_file(report_path),
        "src/spireshift/native_qualified_learning_result_v1.py": _sha_file(Path(__file__)),
    }

    def require(key: str, request: dict[str, Any]) -> dict[str, Any]:
        seal = store.completed(key, request)
        if seal is None or report["chunk_seals"].get(key) != seal["report_id"]:
            raise ValueError("A complete declared unit is missing or changed")
        seals[key] = seal["report_id"]
        sources[str((store.path(key) / "done.json").relative_to(root))] = _sha_file(
            store.path(key) / "done.json"
        )
        return {"seal_id": seal["report_id"], **seal["result"]}

    with ChunkJournal(root, original).lock(), ChunkJournal(root, cfg).lock():
        for r in range(1, 65):
            for p in (2, 3):
                rows = []
                for i in range((r - 1) * 16 + 1, r * 16 + 1):
                    game_task = task(cfg["plan"]["training"][i - 1], i, p, r)
                    request = {"task": game_task, "behavior_state_id": states[p][1]}
                    key = game_task["key"]
                    if key in EXCLUDED:
                        if request != proof["excluded_training_requests"][key]:
                            raise ValueError("A failed cell's world or behavior changed")
                        row = {"outcome": "failed", "seal_id": proof["report_id"]}
                    else:
                        row = require(key, request)
                        if (
                            row["task"] != game_task
                            or row["model_id"] != states[p][0].model.model_id
                        ):
                            raise ValueError(
                                "Training was not sampled from its declared behavior state"
                            )
                    counts[str(p)][row["outcome"]] += 1
                    rows.append(row)
                key = f"fit-p{p}-r{r:03d}"
                fitted = require(
                    key,
                    {
                        "player": p,
                        "round": r,
                        "prior_state_id": states[p][1],
                        "game_seals": [row["seal_id"] for row in rows],
                    },
                )
                after, state_id = load_state(store.path(key) / "shared.json")
                updates = fitted["work"]["optimizer_updates"]
                if (
                    state_id != fitted["state_id"]
                    or after.model.model_id != fitted["model_id"]
                    or after.actor_adam.steps - states[p][0].actor_adam.steps != updates
                    or after.value_adam.steps - states[p][0].value_adam.steps != updates
                    or after.actor_adam.steps != fitted["actor_steps"]
                    or after.value_adam.steps != fitted["value_steps"]
                ):
                    raise ValueError("A full actor/critic/Adam restore or update increment changed")
                states[p] = after, state_id
                training.append(fitted)
        if (
            training != report["training"]
            or {str(p): states[p][1] for p in (2, 3)} != report["final_states"]
        ):
            raise ValueError("The fixed-round training lineage or final selection changed")
        games: dict[tuple[str, int, str], dict[str, Any]] = {}
        samples: dict[int, list[tuple[int, str, dict[str, Any]]]] = {2: [], 3: []}
        for i, seed in enumerate(cfg["plan"]["development"], 1):
            for p in (2, 3):
                for arm, state in (("original", starting[p]), ("fitted", states[p])):
                    key = f"development-{i:04d}-p{p}-{arm}"
                    game_task = {
                        "key": key,
                        "seed": seed,
                        "seed_id": i,
                        "player": p,
                        "round": 64,
                        "partition": "development",
                        "arm": "shared",
                    }
                    row = require(key, {"task": game_task, "behavior_state_id": state[1]})
                    if (
                        row["task"] != game_task
                        or row["model_id"] != state[0].model.model_id
                        or row["outcome"] not in {"win", "loss"}
                    ):
                        raise ValueError("Development is not a genuine frozen normal-start game")
                    folder = store.path(key)
                    episode = identified(folder / "report.json")
                    identity = episode["native_ending"]["private_final_identity"]
                    if (
                        episode["report_id"] != row["episode_report_id"]
                        or episode["native_ending"]["native_ending_evidence_agrees"] is not True
                        or identity["seed"] != seed
                        or identity["ascension"] != 8
                        or episode["status"] != "complete"
                        or not episode["native_terminal"]
                        or episode["shutdown"]["clean_exit"] is not True
                        or episode["shutdown"]["runtime_errors"]
                        or episode["actual_deliveries_independently_verified"]
                        != row["native_decisions"]
                    ):
                        raise ValueError(
                            "Development lacks exact ending, native deliveries or clean shutdown"
                        )
                    rebuilt = diagnostics(
                        folder / "shared-public.jsonl.gz", row["outcome"] == "win"
                    )
                    if any(row[k] != v for k, v in rebuilt.items()):
                        raise ValueError(
                            "Act/floor diagnostics differ from their actual public journals"
                        )
                    games[seed, p, arm] = row
                    if i % 4 == 1:
                        picked: list[tuple[int, str, dict[str, Any]]] = []
                        for index, raw in enumerate(records(folder / "shared-public.jsonl.gz")):
                            if (
                                raw["kind"] != "policy_input"
                                or raw["frame"]["source_family"] != "combat_turn"
                            ):
                                continue
                            public = raw["frame"]["public_input"]
                            rank = int.from_bytes(
                                hashlib.sha256(f"model-health-v1|{key}|{index}".encode()).digest()[
                                    :8
                                ],
                                "big",
                            )
                            entry = (-rank, f"{key}:{index}", public)
                            if len(picked) < 4:
                                heapq.heappush(picked, entry)
                            elif entry[0] > picked[0][0]:
                                heapq.heapreplace(picked, entry)
                        samples[p].extend(picked)
        rebuilt_development = development_report(cfg["plan"]["development"], games)
        if rebuilt_development != report["development"] or seals != report["chunk_seals"]:
            raise ValueError("The paired comparison or declared unit denominator changed")
        models = architecture_diagnostics(
            samples, {"start": starting, "final": states}, ctx["score"]
        )
        if (
            frozen(root, ctx) != protected
            or _shared_snapshot(Path.home() / SHARED_PROFILE) != profile
        ):
            raise ValueError(
                "The frozen build, source checkpoints/full Adam or shared profile changed"
            )
        return write(
            final,
            {
                "schema_version": "native-qualified-learning-saved-result-v1",
                "status": STATUS,
                "source_report_id": report["report_id"],
                "source_config_id": report["config_id"],
                "completed_training_games": 2046,
                "failed_training_cells": 2,
                "unattempted_training_games": 0,
                "planned_training_games": 2048,
                "training_counts": {p: dict(v) for p, v in counts.items()},
                "training_act1_clears": sum(r["act1_clears"] for r in training),
                "training_act2_clears": sum(r["act2_clears"] for r in training),
                "optimizer_updates_on_copies": sum(
                    r["work"]["optimizer_updates"] for r in training
                ),
                "full_model_and_Adam_fits_reloaded": len(training),
                "development": rebuilt_development,
                "development_games_verified": len(games),
                "final_states": report["final_states"],
                "architecture_diagnostics": models,
                "scope": "two_fixed_initializers_32_fresh_worlds_native_only_no_competence_claim",
                "frozen_checks": protected,
                "shared_profile_unchanged": True,
                "games_launched": 0,
                "optimizer_updates": 0,
                "original_optimizer_updates": 0,
                "promotion_allowed": False,
                "official_live_qualification_granted": False,
                "final_test_worlds_used": False,
                "sources": sources,
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = Path.cwd()
    if any(os.environ.get(name) != "1" for name in THREADS):
        raise ValueError("Require the pinned numerical runtime")
    if args.execute is None:
        area = root / WORKSPACE
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
    result = audit(root)
    print(json.dumps({k: v for k, v in result.items() if k not in {"sources", "development"}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
