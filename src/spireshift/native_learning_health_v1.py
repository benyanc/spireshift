"""Audit saved training credit, representations and disposable optimizer steps."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_head_policy import OwnedDecision
from spireshift.native_a8_head_training import training_examples
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_capacity_inputs_v1 import METHODS
from spireshift.native_capacity_inputs_v1 import load as load_original
from spireshift.native_capacity_inputs_v2 import RECIPE as PARENT
from spireshift.native_capacity_inputs_v2 import assessment, context
from spireshift.native_capacity_inputs_v2 import load as load_parent
from spireshift.native_capacity_result_v1 import DEEP_STATUS
from spireshift.native_capacity_result_v1 import STATUS as SOURCE_STATUS
from spireshift.native_capacity_result_v1 import audit as audit_source
from spireshift.native_capacity_session_v2 import ContinuationJournal
from spireshift.native_combat_intent_model import load as load_state
from spireshift.native_combat_intent_model import using_intent_encoder
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_learning_health_math_v1 import (
    explained_variance,
    geometry,
    kernel_probe,
    optimizer_probes,
)
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

RECIPE = "configs/native-learning/sts2-v0.111.0-a8-learning-health-v1.json"
MODULE = "spireshift.native_learning_health_v1"
SHORT = "saved_learner_diagnostic_short_controls_passed"
COMPLETE = "saved_training_credit_and_optimizer_diagnostics_complete"
LIMITS = dict(
    wall_seconds=10800,
    cpu_seconds=10800,
    storage_bytes=2_000_000_000,
    resident_memory_bytes=4_000_000_000,
)
SHORT_LIMITS = {**LIMITS, "wall_seconds": 275, "cpu_seconds": 600}


def plan() -> dict[str, Any]:
    return {
        "rounds": [1, 16, 32, 64],
        "initializers": [2, 3],
        "methods": list(METHODS),
        "games_per_cohort": 16,
        "short_cohort": [2, "standard", 1],
        "short_games": 2,
        "probe_decisions_per_world": 8,
        "gradient_probe_count": 4,
        "sampling_seed": 20261125,
        "source_partition": "train",
        "development_labels_allowed": False,
        "new_games_allowed": False,
        "checkpoints_saved": False,
        "promotion_allowed": False,
    }


def implementation(root: Path) -> dict[str, str]:
    names = {
        PARENT,
        "src/spireshift/native_capacity_result_v1.py",
        "src/spireshift/native_learning_health_v1.py",
        "src/spireshift/native_learning_health_math_v1.py",
        "tests/unit/test_native_learning_health_v1.py",
        "tests/unit/test_native_capacity_result_v1.py",
        "scripts/audit-a8-learning-signal-v1.sh",
    }
    return {name: _sha_file(root / name) for name in sorted(names)}


def load(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    parent = load_parent(root)
    cfg: dict[str, Any] = json.loads((root / RECIPE).read_text())
    if (
        set(cfg)
        != {
            "schema_version",
            "workspace",
            "short_workspace",
            "parent_recipe",
            "source_assessment",
            "implementation",
            "plan",
            "limits",
            "short_limits",
        }
        or cfg["schema_version"] != "native-a8-saved-learning-health-v1"
        or cfg["workspace"] != "artifacts/native-learning-health/v1/full"
        or cfg["short_workspace"] != "artifacts/native-learning-health/v1/short"
        or verified(root, cfg["parent_recipe"]) != root / PARENT
        or cfg["implementation"] != implementation(root)
        or cfg["plan"] != plan()
        or cfg["limits"] != LIMITS
        or cfg["short_limits"] != SHORT_LIMITS
    ):
        raise ValueError("The saved-training-only diagnostic declaration changed")
    check_sources(root, cfg["implementation"])
    source = identified(verified(root, cfg["source_assessment"]))
    check_sources(root, source["sources"])
    if (
        source["status"] != SOURCE_STATUS
        or source["verified_units"] != 5120
        or source["full_model_and_Adam_fits_reloaded"] != 256
        or source["development_games_verified"] != 768
        or source["optimizer_updates_on_copies"] != 16517
        or not all(source["frozen_checks"].values())
    ):
        raise ValueError("Require the independently verified complete capacity experiment")
    return cfg, parent


def selected_examples(
    examples: list[OwnedDecision], games: list[tuple[Path, dict[str, Any]]], count: int
) -> list[OwnedDecision]:
    """Equal bounded world ownership; no outcome-dependent selection or new labels."""
    result: list[OwnedDecision] = []
    offset = 0
    for _, game in games:
        n = game["native_decisions"]
        candidates = examples[offset : offset + n]
        offset += n
        indices = [
            i
            for i, row in enumerate(candidates)
            if any(len(f.rows) > 1 for f in row.decision.factors)
        ]
        seed = game["task"]["seed"]
        indices.sort(
            key=lambda i: hashlib.sha256(
                f"learning-health-v1|20261125|{seed}|{i}".encode()
            ).digest()
        )
        result.extend(candidates[i] for i in indices[:count])
    if offset != len(examples) or not result:
        raise ValueError("Diagnostic examples lost their delivered-world ownership")
    return result


def cohort(
    root: Path, cfg: dict[str, Any], parent: dict[str, Any], spec: tuple[int, str, int], short: bool
) -> dict[str, Any]:
    p, method, r = spec
    store = ContinuationJournal(root, parent, load_original(root), assessment(root, parent))
    completed = identified(root / parent["workspace"] / "report.json")

    def sealed(key: str) -> dict[str, Any]:
        request = json.loads((store.path(key) / "active.json").read_text())["request"]
        seal = store.completed(key, request)
        if seal is None or seal["report_id"] != completed["chunk_seals"].get(key):
            raise ValueError("A source diagnostic unit changed")
        return {"seal_id": seal["report_id"], **seal["result"]}

    prior = "source-copies" if r == 1 else f"fit-p{p}-{method}-r{r - 1:03d}"
    sealed(prior)
    path = store.path(prior) / (f"p{p}-{method}.json" if r == 1 else "shared.json")
    source_sha = _sha_file(path)
    state, state_id = load_state(path)
    before = manifest_identifier(state.document())
    fitted_key = f"fit-p{p}-{method}-r{r:03d}"
    source_fit = sealed(fitted_key)
    fit_request = json.loads((store.path(fitted_key) / "active.json").read_text())["request"]
    if fit_request["prior_state_id"] != state_id:
        raise ValueError("The source cohort was collected from a different full behavior state")
    games: list[tuple[Path, dict[str, Any]]] = []
    source_seals = []
    outcomes: Counter[str] = Counter()
    for i in range((r - 1) * 16 + 1, r * 16 + 1):
        key = f"train-{i:04d}-p{p}-{method}"
        game = sealed(key)
        source_seals.append(game["seal_id"])
        if (
            game["task"]["partition"] != "train"
            or game["task"]["round"] != r
            or game["model_id"] != state.model.model_id
        ):
            raise ValueError("Reject development, foreign-model or foreign-round labels")
        outcomes[game["outcome"]] += 1
        if game["outcome"] in {"win", "loss"} and (
            not short or len(games) < cfg["plan"]["short_games"]
        ):
            games.append((store.path(key), game))
    if fit_request["game_seals"] != source_seals:
        raise ValueError("The exact fitting cohort or its source lineage changed")
    ctx = context(root, parent)
    with using_intent_encoder():
        examples, evidence = training_examples(games, state, ctx["score"], parent["credit"], r)
    advantages = [row.decision.advantage for row in examples]
    mean = math.fsum(advantages) / len(advantages)
    std = math.sqrt(math.fsum((a - mean) ** 2 for a in advantages) / len(advantages))
    if not short and not math.isclose(
        std, source_fit["work"]["raw_advantage_std"], rel_tol=0, abs_tol=1e-10
    ):
        raise ValueError("Reconstructed credit differs from the actual committed PPO fit")
    prepared = [
        replace(
            row,
            decision=replace(
                row.decision, advantage=(row.decision.advantage - mean) / max(std, 1e-8)
            ),
        )
        for row in examples
    ]
    batch = selected_examples(prepared, games, cfg["plan"]["probe_decisions_per_world"])
    kernels = [
        kernel_probe(state, row, parent["settings"])
        for row in batch[: cfg["plan"]["gradient_probe_count"]]
    ]
    targets = [row.decision.target for row in examples]
    estimates = [state.model.value(row.decision.state) for row in examples]
    baseline = [target - adv for target, adv in zip(targets, advantages, strict=True)]
    result = {
        "source_fit_id": source_fit["seal_id"],
        "behavior_state_id": state_id,
        "player": p,
        "method": method,
        "round": r,
        "source_partition": "train",
        "declared_worlds": 16,
        "source_outcomes": dict(outcomes),
        "reconstructed_games": len(games),
        "candidate_decisions": len(examples),
        "single_choice_native_decisions": sum(
            all(len(f.rows) == 1 for f in row.decision.factors) for row in examples
        ),
        "compound_decisions": evidence["compound_decisions"],
        "native_families": evidence["native_families"],
        "distinct_episode_returns": len(set(targets)),
        "native_victory_targets": sum(game["outcome"] == "win" for _, game in games),
        "raw_advantage_mean": mean,
        "raw_advantage_std": std,
        "positive_raw_advantage_fraction": sum(a > 0 for a in advantages) / len(advantages),
        "critic_explained_variance": explained_variance(targets, estimates),
        "cross_fitted_baseline_explained_variance": explained_variance(targets, baseline),
        "geometry": geometry(state, batch, parent["settings"]["temperature"]),
        "kernel_probes": kernels,
        "optimizer_probes": optimizer_probes(state, batch, parent["settings"]),
        "source_states_and_Adam_unchanged": manifest_identifier(state.document()) == before,
        "source_state_sha256": source_sha,
        "disposable_copy_updates": 2,
        "source_optimizer_updates": 0,
        "new_games": 0,
        "checkpoints_saved": 0,
        "teacher_labels_created": False,
        "strength_improvement_established": False,
    }
    if not result["source_states_and_Adam_unchanged"] or _sha_file(path) != source_sha:
        raise ValueError("The diagnostic changed a source checkpoint or full Adam")
    if not any(probe["responsive"] for probe in kernels):
        raise ValueError("No sampled legal alternative produced a responsive policy gradient")
    for probe in kernels:
        if probe["responsive"] and (
            probe["maximum_relative_directional_error"] > 1e-5
            or not all(v["correct_direction"] for v in probe["advantage_signs"].values())
        ):
            raise ValueError("A finite-difference or policy-gradient direction check failed")
    return result


def execute(
    root: Path, cfg: dict[str, Any], parent: dict[str, Any], short: bool, deadline: float
) -> dict[str, Any]:
    effective = {**cfg, "workspace": cfg["short_workspace"]} if short else cfg
    store = ChunkJournal(root, effective)
    ctx = context(root, parent)
    before = frozen(root, ctx)
    with store.lock():
        final = store.workspace / "report.json"
        if final.exists():
            result = identified(final)
            check_sources(root, result["sources"])
            if result["config_id"] != store.config_id:
                raise ValueError("The completed diagnostic declaration changed")
            return result
        specs = (
            [(2, "standard", 1)]
            if short
            else [(p, m, r) for r in cfg["plan"]["rounds"] for p in (2, 3) for m in METHODS]
        )
        rows = []
        for p, m, r in specs:
            key = f"p{p}-{m}-r{r:03d}"
            request = {
                "player": p,
                "method": m,
                "round": r,
                "short": short,
                "source_assessment": cfg["source_assessment"],
            }
            sealed = store.completed(key, request)
            if sealed is None:
                if time.monotonic() + 90 >= deadline:
                    raise TimeoutError(
                        "Stopped before a new diagnostic cohort; preserve clean seals"
                    )
                store.begin(key, request)
                value = cohort(root, cfg, parent, (p, m, r), short)
                sealed = store.commit(key, request, value)
            rows.append(sealed["result"])
            print(
                f"Diagnostic {key}: {rows[-1]['candidate_decisions']} decisions; "
                "credit reconstructed",
                flush=True,
            )
        if frozen(root, ctx) != before:
            raise ValueError("Frozen build or original full states/Adam changed")
        return write(
            final,
            {
                "status": SHORT if short else COMPLETE,
                "config_id": store.config_id,
                "cohorts": rows,
                "source_optimizer_updates": 0,
                "new_games": 0,
                "checkpoints_saved": 0,
                "disposable_copy_updates": sum(row["disposable_copy_updates"] for row in rows),
                "training_labels_created": False,
                "frozen_checks": before,
                "promotion_allowed": False,
                "automatic_follow_up": False,
                "final_test_worlds_used": False,
                "sources": {
                    str(p.relative_to(root)): _sha_file(p)
                    for p in store.workspace.rglob("*")
                    if p.is_file() and p != final
                },
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("short", "saved", "full"), nargs="?", default="full")
    parser.add_argument("--execute", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = Path.cwd()
    if any(os.environ.get(k) != "1" for k in THREADS):
        raise ValueError("Require the pinned numerical runtime")
    cfg, parent = load(root)
    if args.mode != "short":
        result = identified(root / cfg["short_workspace"] / "report.json")
        check_sources(root, result["sources"])
        if result["status"] != SHORT or result["config_id"] != manifest_identifier(
            {**cfg, "workspace": cfg["short_workspace"]}
        ):
            raise ValueError("Require passing short saved-data learner controls")
        if args.mode == "saved":
            print(
                json.dumps(
                    {
                        "status": SHORT,
                        "report_id": result["report_id"],
                        "new_games": 0,
                        "source_optimizer_updates": 0,
                    }
                )
            )
            return 0
    short = args.mode == "short"
    limits = cfg["short_limits"] if short else cfg["limits"]
    area = root / (cfg["short_workspace"] if short else cfg["workspace"])
    area.mkdir(parents=True, exist_ok=True)
    if args.execute is None:
        attempt = time.time_ns()
        if not short:
            print(
                "Saved-training learner diagnostic: 16 cohorts / 256 games "
                "across both policy widths and initializers. "
                "No new games, source updates or saved checkpoints. "
                "Allow about 20–60 minutes; three-hour cap.",
                flush=True,
            )
        tracked = run_tracked_command(
            command=[
                "uv",
                "run",
                "--no-sync",
                "python",
                "-B",
                "-m",
                MODULE,
                args.mode,
                "--execute",
                str(attempt),
            ],
            working_directory=root,
            experiment_kind=ExperimentKind.OTHER,
            report_path=area / f"resources-{attempt}.json",
            artifact_roots=[area],
            limits=ResourceLimits(**limits),
        )
        print(json.dumps(tracked.report))
        return 0 if tracked.exit_code == 0 and tracked.report["cap"] is None else 2
    deadline = time.monotonic() + limits["wall_seconds"] - 10
    if not short:
        deep = audit_source(root, deadline - 600, recount_public=True)
        if deep["status"] != DEEP_STATUS:
            raise ValueError(
                "Require the complete raw-public outcome recount before the full diagnostic"
            )
    result = execute(root, cfg, parent, short, deadline)
    print(json.dumps({k: v for k, v in result.items() if k not in {"sources", "cohorts"}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
