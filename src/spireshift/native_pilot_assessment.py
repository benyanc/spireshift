"""Saved-only assessment of a finished native A8 pilot, independent of its runner.

Never starts workers, changes weights, selects a different checkpoint, or reads a
live pilot's partial episodes. Historical inputs are checked against source-at-
launch bytes instead of demanding that the current learner still has old hashes.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import random
import time
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_native import _private_path
from spireshift.engine_neural import NativeActorCritic
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.training_objective import load_training_score_spec

SCHEMA = "native-pilot-assessment-v1"
POLICY = "wins_primary_failed_runs_zero_progress_paired_seed_v1"


class SavedFiles:
    def __init__(self, root: Path, maximum_seconds: float) -> None:
        self.root = root
        self.deadline = time.monotonic() + maximum_seconds
        self.files: dict[str, dict[str, Any]] = {}

    def check_time(self) -> None:
        if time.monotonic() > self.deadline:
            raise TimeoutError("Saved assessment wall cap; no source experiment was changed")

    def path(self, relative: str) -> Path:
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise ValueError("Saved input must stay under the project root")
        result = self.root / path
        if any(p.is_symlink() for p in (result, *result.parents)):
            raise ValueError("Saved assessment inputs cannot traverse symlinks")
        return result

    def pin(self, path: Path) -> str:
        self.check_time()
        relative = str(path.relative_to(self.root))
        path = self.path(relative)
        stat = path.stat()
        if relative in self.files:
            if (stat.st_size, stat.st_mtime_ns) != self.files[relative]["stat"]:
                raise ValueError("Saved pilot source changed during assessment")
            return str(self.files[relative]["sha256"])
        digest = _sha_file(path)
        after = path.stat()
        if (stat.st_size, stat.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("Saved pilot source changed while hashing")
        self.files[relative] = {"sha256": digest, "stat": (stat.st_size, stat.st_mtime_ns)}
        return digest

    def read(self, path: Path, key: str | None = None) -> dict[str, Any]:
        self.pin(path)
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError("Expected a saved object")
        if key and value.get(key) != manifest_identifier(
            {k: v for k, v in value.items() if k != key}
        ):
            raise ValueError(f"Saved evidence identity changed: {path.name}")
        return dict(value)

    def sources(self) -> list[dict[str, str]]:
        for relative in self.files:
            self.pin(self.root / relative)
        return [{"path": p, "sha256": self.files[p]["sha256"]} for p in sorted(self.files)]


def binomial_interval(successes: int, total: int, confidence: float = 0.95) -> list[float]:
    """Two-sided Clopper-Pearson bounds, including nonzero uncertainty at zero wins."""
    if type(successes) is not int or type(total) is not int or not 0 <= successes <= total:
        raise ValueError("Invalid binomial counts")
    if not 0 < confidence < 1 or total < 1 or total > 1000:
        raise ValueError("Binomial interval needs 1–1000 independent run seeds")
    tail = (1 - confidence) / 2

    def probability(p: float, lower: int, upper: int) -> float:
        return math.fsum(
            math.comb(total, k) * p**k * (1 - p) ** (total - k) for k in range(lower, upper + 1)
        )

    low = 0.0
    if successes:
        left, right = 0.0, 1.0
        for _ in range(60):
            mid = (left + right) / 2
            if probability(mid, successes, total) < tail:
                left = mid
            else:
                right = mid
        low = (left + right) / 2
    high = 1.0
    if successes != total:
        left, right = 0.0, 1.0
        for _ in range(60):
            mid = (left + right) / 2
            if probability(mid, 0, successes) > tail:
                left = mid
            else:
                right = mid
        high = (left + right) / 2
    return [low, high]


def paired_comparison(
    initial: list[dict[str, Any]], selected: list[dict[str, Any]], *, replicates: int, salt: int
) -> dict[str, Any]:
    if not initial or len(initial) != len(selected):
        raise ValueError("Paired comparison requires every planned independent seed")
    if [c["seed_id"] for c in initial] != [c["seed_id"] for c in selected]:
        raise ValueError("Development seeds are not paired")
    if len({c["seed_id"] for c in initial}) != len(initial):
        raise ValueError("Comparison requires independent seed pairs, not repeated decisions")
    if type(replicates) is not int or not 100 <= replicates <= 10000 or type(salt) is not int:
        raise ValueError("Bootstrap requires 100–10000 replicates and a fixed integer seed")
    n = len(initial)
    initial_wins, selected_wins = sum(c["win"] for c in initial), sum(c["win"] for c in selected)
    # Bonferroni-combined 97.5% marginal exact bounds cover their difference
    # simultaneously with at least 95% confidence, even under within-seed dependence.
    a, b = binomial_interval(initial_wins, n, 0.975), binomial_interval(selected_wins, n, 0.975)
    win_bounds = [b[0] - a[1], b[1] - a[0]]
    differences = [
        b["floor_zero"] - a["floor_zero"] for a, b in zip(initial, selected, strict=True)
    ]
    rng = random.Random(salt)
    draws = sorted(
        math.fsum(rng.choice(differences) for _ in range(n)) / n for _ in range(replicates)
    )

    def quantile(p: float) -> float:
        index = (len(draws) - 1) * p
        lower = int(index)
        return draws[lower] + (draws[min(lower + 1, len(draws) - 1)] - draws[lower]) * (
            index - lower
        )

    floor_bounds = [quantile(0.025), quantile(0.975)]
    return {
        "independent_unit": "complete_run_seed",
        "pairs": n,
        "victory_rate_difference": (selected_wins - initial_wins) / n,
        "victory_difference_95_interval": win_bounds,
        "victory_interval_method": "bonferroni_combined_exact_binomial_marginals",
        "initial_win_rate_95_interval": binomial_interval(initial_wins, n),
        "selected_win_rate_95_interval": binomial_interval(selected_wins, n),
        "selected_only_wins": sum(
            b["win"] and not a["win"] for a, b in zip(initial, selected, strict=True)
        ),
        "initial_only_wins": sum(
            a["win"] and not b["win"] for a, b in zip(initial, selected, strict=True)
        ),
        "mean_floor_difference_failures_zero": math.fsum(differences) / n,
        "floor_difference_95_interval": floor_bounds,
        "floor_interval_method": "paired_seed_percentile_bootstrap_exploratory",
        "bootstrap_replicates": replicates,
        "bootstrap_seed": salt,
        "victory_improvement_supported": win_bounds[0] > 0,
        "auxiliary_progress_supported": floor_bounds[0] > 0,
        "base_readiness_passed": False,
    }


def panel_plan(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    learning = cfg["learning"]
    plan = [
        {
            "name": "initial-confirmation",
            "partition": "confirmation",
            "ids": learning["confirmation_seeds"],
            "round": 0,
        }
    ]
    for index, seeds in enumerate(learning["rollout_panels"], 1):
        plan.append(
            {
                "name": f"round-{index:03}-sampled",
                "partition": "train",
                "ids": seeds,
                "round": index - 1,
            }
        )
        if index % learning["confirmation_every"] == 0:
            plan.append(
                {
                    "name": f"round-{index:03}-confirmation",
                    "partition": "confirmation",
                    "ids": learning["confirmation_seeds"],
                    "round": index,
                }
            )
    for name in ("initial", "selected"):
        plan.append(
            {
                "name": f"development-{name}",
                "partition": "development",
                "ids": learning["development_seeds"],
                "round": name,
            }
        )
    owners: dict[int, str] = {}
    for panel in plan:
        if len(panel["ids"]) != len(set(panel["ids"])) or not panel["ids"]:
            raise ValueError("Pilot plan has missing/duplicate run seeds")
        for seed in panel["ids"]:
            if seed in owners and (
                owners[seed] != panel["partition"] or panel["partition"] == "train"
            ):
                raise ValueError("Complete-run seed ownership overlaps or training repeats")
            owners[seed] = panel["partition"]
    return plan


def _model(files: SavedFiles, path: Path, environment_id: str) -> NativeActorCritic:
    model = NativeActorCritic.from_mapping(files.read(path))
    if model.actor.environment_id != environment_id:
        raise ValueError("Checkpoint belongs to another game/input environment")
    return model


def _case(
    files: SavedFiles,
    path: Path,
    cfg: dict[str, Any],
    panel: dict[str, Any],
    seed: dict[str, Any],
    model_id: str,
    cpu_budget: float,
) -> dict[str, Any]:
    doc = files.read(path)
    if doc.get("schema_version") != "actual-engine-on-policy-experience-v1" or doc.get(
        "case_id"
    ) != manifest_identifier(
        {k: v for k, v in doc.items() if k not in {"case_id", "trace_file_sha256"}}
    ):
        raise ValueError("Saved episode identity changed")
    binding, episode = doc["binding"], doc["episode"]
    training = panel["partition"] == "train"
    evaluation = cfg.get("evaluation_policy", {"behavior": "greedy"})
    sampled = training or evaluation["behavior"] == "sampled_softmax"
    source = (
        f"{evaluation['sampling_seed']}|frozen-policy-evaluation|{seed['id']}"
        if not training and sampled
        else f"{cfg['learning']['sampling_seed']}|{panel['name']}|{seed['id']}"
    )
    expected_seed = int.from_bytes(hashlib.sha256(source.encode()).digest()[:8], "big")
    expected = {
        "environment_id": cfg["environment_manifest"]["id"],
        "config_id": manifest_identifier(cfg),
        "seed_manifest_id": cfg["seed_manifest"]["id"],
        "seed_id": seed["id"],
        "native_seed": seed["seed"],
        "partition": panel["partition"],
        "panel": panel["name"],
        "model_id": model_id,
        "training_spec_id": cfg["training_spec"]["id"],
        "sampling_seed": expected_seed,
        "behavior": "sampled_softmax" if sampled else "greedy",
    }
    if any(binding.get(k) != value for k, value in expected.items()):
        raise ValueError("Saved episode crosses seed, policy, behavior or model ownership")
    if "evaluation_policy" in cfg and binding.get("panel_purpose") != (
        "training" if training else "frozen_policy_evaluation"
    ):
        raise ValueError("Saved decision purpose differs from its panel")
    trace = path.with_suffix(".jsonl.gz")
    if files.pin(trace) != doc["trace_file_sha256"]:
        raise ValueError("Saved episode trace changed")
    if (
        episode.get("seed") != seed["seed"]
        or episode.get("privileged_fixture") is not False
        or episode.get("recovered") is not False
    ):
        raise ValueError(
            "Privileged/recovered or mismatched episode cannot be assessed as native play"
        )
    if episode["status"] not in {"terminal", "failed"}:
        raise ValueError("Unsupported saved episode status")
    terminal = episode["status"] == "terminal"
    if terminal:
        end = episode.get("private_final_identity", {})
        win = episode["victory"]
        agrees = (
            end.get("native_game_over") and end.get("native_victory_room")
            if win
            else (
                (end.get("native_game_over") and not end.get("native_victory_room"))
                or end.get("native_player_dead")
            )
        )
        if (
            any(
                type(end.get(k)) is not bool
                for k in ("native_game_over", "native_victory_room", "native_player_dead")
            )
            or episode.get("native_ending_evidence_agrees") is not True
            or not agrees
            or not isinstance(win, bool)
        ):
            raise ValueError("Terminal label has no matching native ending evidence")
    else:
        win = False
        if episode.get("victory"):
            raise ValueError("A failed game cannot supply a victory")
    count = 0
    families: Counter[str] = Counter()
    verbs: Counter[str] = Counter()
    repeated: Counter[str] = Counter()
    last_family = None
    with gzip.open(trace, "rt") as stream:
        for line in stream:
            if count % 128 == 0:
                files.check_time()
            row = json.loads(line)
            choice, public = row["choice"], row["public_input"]
            action = choice["action_index"]
            if type(action) is not int or not 0 <= action < len(public["candidates"]):
                raise ValueError("Saved choice is outside its recorded public menu")
            temperature = (
                cfg["learning"]["ppo"]["temperature"]
                if training
                else evaluation.get("temperature", cfg["learning"]["ppo"]["temperature"])
            )
            if (
                choice.get("model_id") != model_id
                or choice.get("behavior") != expected["behavior"]
                or choice.get("temperature") != temperature
                or choice.get("public_input_id") != manifest_identifier(public)
            ):
                raise ValueError("Saved decision behavior differs from its episode")
            last_family = public["context"]["interaction"]["kind"]
            families[last_family] += 1
            verbs[public["candidates"][action]["verb"]] += 1
            repeated[row["public_key"]] += 1
            count += 1
    if count != doc["decision_count"]:
        raise ValueError("Saved decision count differs from its sealed episode")
    cpu = episode["cpu_seconds"]
    if type(cpu) not in {int, float} or not math.isfinite(cpu) or cpu < 0:
        raise ValueError("Saved native CPU measurement is invalid")
    if terminal and cpu > cpu_budget:
        raise ValueError("Completed game exceeded the frozen whole-run CPU budget")
    floor = episode["maximum_floor"]
    if type(floor) is not int or floor < 0:
        raise ValueError("Saved reached floor is invalid")
    return {
        "seed_id": seed["id"],
        "terminal": terminal,
        "win": win,
        "floor_zero": floor if terminal else 0,
        "floor_reached": floor,
        "completed_acts": episode["completed_acts"] if terminal else 0,
        "decisions": count,
        "cpu_seconds": cpu,
        "families": dict(families),
        "verbs": dict(verbs),
        "maximum_identical_public_state_visits": max(repeated.values(), default=0),
        "last_decision_family": last_family,
        "error": episode.get("error"),
        "worker_workspace": episode["worker_workspace"],
    }


def panel_metrics(rows: list[dict[str, Any]], denominator: int) -> dict[str, Any]:
    if denominator < len(rows) or denominator < 1:
        raise ValueError("Panel denominator changed")
    terminal = [r for r in rows if r["terminal"]]
    return {
        "planned_games": denominator,
        "recorded_games": len(rows),
        "completed_games": len(terminal),
        "failed_games": len(rows) - len(terminal),
        "not_attempted_games": denominator - len(rows),
        "wins": sum(r["win"] for r in rows),
        "win_rate": sum(r["win"] for r in rows) / denominator,
        "mean_floor_failures_zero": sum(r["floor_zero"] for r in rows) / denominator,
        "mean_floor_reached_diagnostic": sum(r["floor_reached"] for r in rows) / denominator,
        "mean_floor_completed_only_diagnostic": sum(r["floor_reached"] for r in terminal)
        / len(terminal)
        if terminal
        else None,
        "best_floor_completed": max((r["floor_reached"] for r in terminal), default=0),
        "best_completed_acts": max((r["completed_acts"] for r in terminal), default=0),
        "recorded_selections": sum(r["decisions"] for r in rows),
        "terminal_delivered_selections": sum(r["decisions"] for r in terminal),
        "cpu_seconds": math.fsum(r["cpu_seconds"] for r in rows),
    }


def _worker_audits(
    files: SavedFiles, pilot: Path, cfg: dict[str, Any], rows: list[dict[str, Any]]
) -> None:
    for relative in sorted({r["worker_workspace"] for r in rows}):
        worker = files.path(str((pilot / relative).relative_to(files.root)))
        owned = [r for r in rows if r["worker_workspace"] == relative]
        audit = files.read(worker / "experience-audit.json", "report_id")
        if (
            audit.get("valid") is not True
            or audit["games"] != sum(r["terminal"] for r in owned)
            or audit["excluded_failed_games"] != sum(not r["terminal"] for r in owned)
            or audit["decisions"] != sum(r["decisions"] for r in owned if r["terminal"])
        ):
            raise ValueError("Saved worker delivery audit does not cover its recorded episodes")
        for name, digest in audit["source_sha256"].items():
            if files.pin(worker / name) != digest:
                raise ValueError("Saved worker delivery evidence changed")
        for name, digest in cfg["helpers_sha256"].items():
            if files.pin(worker / "source-at-launch" / name) != digest:
                raise ValueError("Saved worker helper source changed")


def assess_completed_pilot(
    root: Path,
    config_path: Path,
    *,
    replicates: int = 2000,
    bootstrap_seed: int = 20261016,
    maximum_seconds: float = 180,
) -> dict[str, Any]:
    if (
        type(maximum_seconds) not in {int, float}
        or not math.isfinite(maximum_seconds)
        or not 1 <= maximum_seconds <= 180
    ):
        raise ValueError("Saved assessment requires a 1–180 second wall cap")
    files = SavedFiles(root, maximum_seconds)
    cfg = files.read(config_path)
    pilot = _private_path(root, cfg["workspace"])
    # The completion marker is checked BEFORE any episode, checkpoint or live log.
    if not (pilot / "summary.json").is_file():
        return {"status": "awaiting_completed_pilot", "games_launched": 0, "optimizer_steps": 0}
    summary = files.read(pilot / "summary.json", "report_id")
    if (
        cfg.get("stage") != "bounded_policy_only_pilot"
        or summary.get("schema_version") != "actual-engine-neural-experiment-report-v1"
        or summary["config_id"] != manifest_identifier(cfg)
        or files.read(pilot / "config.json") != cfg
        or summary["environment_id"] != cfg["environment_manifest"]["id"]
        or summary["training_spec_id"] != cfg["training_spec"]["id"]
        or summary["seed_manifest_id"] != cfg["seed_manifest"]["id"]
        or summary["implementation_sha256"] != cfg["implementation_sha256"]
    ):
        raise ValueError("Saved native pilot does not match its frozen recipe")
    if summary.get("status") not in {
        "bounded_pilot_complete",
        "bounded_pilot_complete_with_failures",
        "stopped_incomplete",
    }:
        raise ValueError("Expected a final native pilot result")
    if "evaluation_policy" in cfg and (
        summary.get("evaluation_policy") != cfg["evaluation_policy"]
        or cfg["evaluation_policy"].get("coupling") != "same_run_seed_across_checkpoints"
    ):
        raise ValueError("Frozen evaluation policy/RNG coupling changed")
    environment = files.read(files.path(cfg["environment_manifest"]["path"]), "manifest_id")
    seeds = files.read(files.path(cfg["seed_manifest"]["path"]), "manifest_id")
    score_path = files.path(cfg["training_spec"]["path"])
    files.pin(score_path)
    score = load_training_score_spec(score_path)
    if (
        environment["manifest_id"] != cfg["environment_manifest"]["id"]
        or environment["character"] != "Ironclad"
        or environment["ascension"] != 8
        or environment["version"] != "v0.111.0"
        or seeds["manifest_id"] != cfg["seed_manifest"]["id"]
        or seeds["environment_id"] != environment["manifest_id"]
        or score.spec_id != cfg["training_spec"]["id"]
        or score.scope.ruleset_manifest_id != environment["manifest_id"]
        or score.scope.character != "ironclad"
        or score.scope.ascension != 8
    ):
        raise ValueError("Saved game/difficulty/input/score/seed lineage changed")
    for name, digest in cfg["implementation_sha256"].items():
        if files.pin(pilot / "source-at-launch" / name) != digest:
            raise ValueError("Saved learner source differs from source at launch")
    if summary["status"] == "stopped_incomplete":
        return {
            "schema_version": SCHEMA,
            "assessment_policy": POLICY,
            "status": "pilot_stopped_before_complete_assessment",
            "source_report_id": summary["report_id"],
            "planned_games": summary["planned_games"],
            "completed_games": summary["completed_games"],
            "failed_games": summary["failed_games"],
            "not_attempted_games": summary["not_attempted_games"],
            "error": summary["error"],
            "comparison": None,
            "source_episode_audit_completed": False,
            "claim_scope": "sealed_stopped_pilot_metadata_only_no_quality_comparison",
            "games_launched": 0,
            "optimizer_steps": 0,
            "source_files": files.sources(),
            "checkpoint_promoted": False,
            "base_readiness_passed": False,
        }
    if (
        summary.get("error") is not None
        or set(summary["checks"])
        != {
            "account_profile_unchanged",
            "candidate_unchanged",
            "frozen_archive_unchanged",
            "runtime_unchanged",
            "sdk_unchanged",
        }
        or any(value is not True for value in summary["checks"].values())
        or summary["worker_failures"]
    ):
        raise ValueError("Completed pilot has unverified source/isolation failures")
    models: dict[int | str, str] = {
        0: _model(files, pilot / "initial-checkpoint.json", environment["manifest_id"]).model_id
    }
    updates = []
    for index, update in enumerate(summary["rounds"], 1):
        model = _model(
            files, pilot / f"round-{index:03}-checkpoint.json", environment["manifest_id"]
        )
        if (
            files.read(pilot / f"round-{index:03}-update.json") != update
            or update["round"] != index
            or update["behavior_model_id"] != models[index - 1]
            or update["updated_model_id"] != model.model_id
        ):
            raise ValueError("Saved update/checkpoint lineage changed")
        models[index] = model.model_id
        updates.append(
            {
                "round": index,
                "optimizer_steps": update["diagnostics"]["optimizer_steps"],
                "actor_change": update["actor_l2_change"],
                "critic_change": update["critic_l2_change"],
                "diagnostics": update["diagnostics"],
            }
        )
    models["initial"] = models[0]
    models["selected"] = _model(
        files, pilot / "selected-checkpoint.json", environment["manifest_id"]
    ).model_id
    freeze = files.read(pilot / "selection-freeze.json")
    if (
        models[0] != summary["initial_model_id"]
        or models["selected"] != summary["selected_model_id"]
        or freeze
        != {
            "model_id": models["selected"],
            "selection_partition": "confirmation",
            "development_opened": False,
        }
    ):
        raise ValueError("Checkpoint selection was not frozen before development evaluation")
    seed_map = {row["id"]: row for row in seeds["seeds"]}
    if len(seed_map) != len(seeds["seeds"]):
        raise ValueError("Duplicate seed ownership in saved manifest")
    if len({row["seed"] for row in seeds["seeds"]}) != len(seed_map):
        raise ValueError("Different seed IDs refer to the same native game seed")
    panels, all_rows, by_panel = [], [], {}
    plan = panel_plan(cfg)
    if len(summary["rounds"]) != len(cfg["learning"]["rollout_panels"]) or [
        p["panel"] for p in summary["panels"]
    ] != [p["name"] for p in plan]:
        raise ValueError("Completed pilot omitted a planned training/evaluation panel")
    selected_rank, selected_id = None, models[0]
    for panel, saved in zip(plan, summary["panels"], strict=True):
        folder = pilot / panel["name"]
        expected = {f"case-{seed}.json" for seed in panel["ids"]}
        if {p.name for p in folder.glob("case-*.json")} != expected or files.read(
            folder / "summary.json"
        ) != saved:
            raise ValueError("Saved panel has missing/extra episodes or changed metrics")
        rows = []
        for seed_id in panel["ids"]:
            seed = seed_map[seed_id]
            if seed["partition"] != panel["partition"]:
                raise ValueError("Episode crosses complete-run seed partitions")
            rows.append(
                _case(
                    files,
                    folder / f"case-{seed_id}.json",
                    cfg,
                    panel,
                    seed,
                    models[panel["round"]],
                    score.evaluation_objective.whole_run_budget,
                )
            )
        metrics = panel_metrics(rows, len(panel["ids"]))
        for key in (
            "planned_games",
            "completed_games",
            "failed_games",
            "not_attempted_games",
            "wins",
        ):
            if saved[key] != metrics[key]:
                raise ValueError("Saved summary outcome denominator differs from episodes")
        if (
            not math.isclose(
                saved["mean_floor"], metrics["mean_floor_reached_diagnostic"], abs_tol=1e-10
            )
            or saved["decisions"] != metrics["recorded_selections"]
            or saved["model_id"] != models[panel["round"]]
        ):
            raise ValueError("Saved panel progress, decisions or model disagrees with episodes")
        _worker_audits(files, pilot, cfg, rows)
        if panel["partition"] == "train":
            update = summary["rounds"][panel["round"]]
            if (
                update["completed_training_games"] != metrics["completed_games"]
                or update["excluded_failed_training_games"] != metrics["failed_games"]
                or update["diagnostics"]["sampled_decisions"]
                != metrics["terminal_delivered_selections"]
            ):
                raise ValueError("Training update counts disagree with clean saved episodes")
        if panel["partition"] == "confirmation":
            rank = (
                metrics["win_rate"],
                metrics["mean_floor_reached_diagnostic"],
                metrics["completed_games"] / metrics["planned_games"],
            )
            if selected_rank is None or rank > selected_rank:
                selected_rank, selected_id = rank, saved["model_id"]
        panels.append({"panel": panel["name"], "partition": panel["partition"], **metrics})
        by_panel[panel["name"]] = rows
        all_rows.extend(rows)
    if selected_id != models["selected"]:
        raise ValueError("Selected checkpoint differs from the frozen confirmation-only rule")
    total = panel_metrics(all_rows, sum(len(p["ids"]) for p in plan))
    if (
        any(
            total[k] != summary[k]
            for k in ("planned_games", "completed_games", "failed_games", "not_attempted_games")
        )
        or summary["recorded_games"] != len(all_rows)
        or summary["optimizer_steps"] != sum(u["optimizer_steps"] for u in updates)
        or summary["sampled_decisions_verified"]
        != sum(p["terminal_delivered_selections"] for p in panels if p["partition"] == "train")
    ):
        raise ValueError("Whole-pilot accounting disagrees with sealed cases/updates")
    comparison = paired_comparison(
        by_panel["development-initial"],
        by_panel["development-selected"],
        replicates=replicates,
        salt=bootstrap_seed,
    )
    verdict = (
        "victory_improvement_supported"
        if comparison["victory_improvement_supported"]
        else (
            "auxiliary_progress_only"
            if comparison["auxiliary_progress_supported"]
            else "no_clear_improvement"
        )
    )
    return {
        "schema_version": SCHEMA,
        "status": "completed_saved_assessment",
        "assessment_policy": POLICY,
        "source_report_id": summary["report_id"],
        "experiment_config_id": manifest_identifier(cfg),
        "environment_id": environment["manifest_id"],
        "evaluation_objective": score.evaluation_objective.as_dict(),
        "evaluation_policy": cfg.get("evaluation_policy", {"behavior": "greedy"}),
        "initial_model_id": models[0],
        "selected_model_id": models["selected"],
        "selection_rule": (
            "confirmation_wins_then_recorded_reached_floor_then_completion_strict_improvement"
        ),
        "verdict": verdict,
        "accounting": total,
        "panels": panels,
        "updates": updates,
        "comparison": comparison,
        "failures": [
            {
                k: row[k]
                for k in (
                    "seed_id",
                    "error",
                    "floor_reached",
                    "last_decision_family",
                    "maximum_identical_public_state_visits",
                    "decisions",
                    "worker_workspace",
                )
            }
            for row in all_rows
            if not row["terminal"]
        ],
        "terminal_action_families": dict(
            sum((Counter(r["families"]) for r in all_rows if r["terminal"]), Counter())
        ),
        "terminal_action_verbs": dict(
            sum((Counter(r["verbs"]) for r in all_rows if r["terminal"]), Counter())
        ),
        "source_files": files.sources(),
        "source_episode_audit_completed": True,
        "games_launched": 0,
        "optimizer_steps": 0,
        "checkpoint_promoted": False,
        "base_readiness_passed": False,
        "adaptive_controller_allowed": False,
        "claim_scope": (
            "saved_finished_native_pilot_seed_paired_assessment_no_new_play_or_selection"
        ),
        "limitations": [
            "small_development_panel",
            "one_evaluation_rng_stream_per_seed",
            "progress_is_auxiliary_not_victory_probability",
            "saved_delivery_audits_and_trace_hashes_verified_not_engine_replayed",
            "no_gradient_or_behavior_probability_recomputation",
        ],
    }


def render_assessment(report: dict[str, Any]) -> str:
    if report["status"] != "completed_saved_assessment":
        return f"# Native A8 pilot assessment\n\n{report['status']}: {report.get('error', '')}\n"
    comparison, total = report["comparison"], report["accounting"]
    labels = {
        "victory_improvement_supported": "The reserved panel supports a higher win rate.",
        "auxiliary_progress_only": (
            "The reserved panel supports more floor progress, with no clear win-rate improvement."
        ),
        "no_clear_improvement": "The reserved panel does not establish improved play.",
    }
    text = [
        "# Native A8 pilot assessment",
        "",
        labels[report["verdict"]],
        "",
        f"Recorded {total['recorded_games']}/{total['planned_games']} attempts; "
        f"{total['completed_games']} normal endings, {total['failed_games']} failures. "
        "No new games or updates ran.",
        "",
        "| Panel | Wins / planned | Failures | Average floor (failures zero) |",
        "| --- | ---: | ---: | ---: |",
    ]
    for p in report["panels"]:
        text.append(
            f"| {p['panel']} | {p['wins']}/{p['planned_games']} | {p['failed_games']} "
            f"| {p['mean_floor_failures_zero']:.3f} |"
        )
    low, high = comparison["floor_difference_95_interval"]
    initial = report["panels"][-2]
    selected = report["panels"][-1]
    a_low, a_high = comparison["initial_win_rate_95_interval"]
    b_low, b_high = comparison["selected_win_rate_95_interval"]
    win_low, win_high = comparison["victory_difference_95_interval"]
    text += [
        "",
        f"Reserved wins: initial {initial['wins']}/{initial['planned_games']} "
        f"(95% interval {a_low:.1%}–{a_high:.1%}); selected "
        f"{selected['wins']}/{selected['planned_games']} "
        f"({b_low:.1%}–{b_high:.1%}). The conservative 95% difference interval is "
        f"[{100 * win_low:+.1f}, {100 * win_high:+.1f}] percentage points.",
        "",
        f"Reserved comparison: {comparison['pairs']} paired seeds. Trained minus initial "
        f"average floor: {comparison['mean_floor_difference_failures_zero']:+.3f}; "
        f"exploratory 95% paired-bootstrap interval [{low:+.3f}, {high:+.3f}].",
        "",
        "Win-rate uncertainty uses exact binomial bounds. Zero observed wins still leaves "
        "nonzero uncertainty. Floors and training-round results do not establish full-game wins.",
        "",
        "These intervals use the independent development seeds only. Repeated confirmation "
        "checks do not add independent seeds. A small panel and one fixed evaluation RNG stream "
        "per seed limit the conclusions.",
        "",
        "Checkpoint selection remains the original confirmation-only selection. Development "
        "results did not choose a replacement checkpoint. Failures retain their original "
        "denominators; completed-only and reached-before-failure means are separate diagnostics "
        "in report.json.",
        "",
        "This assessment does not promote a checkpoint, establish base readiness "
        "or allow adaptive thinking.",
        "",
    ]
    if report["failures"]:
        text += ["## Recorded failures", ""]
        for failure in report["failures"]:
            text.append(
                f"- Seed {failure['seed_id']}, {failure['worker_workspace']}: "
                f"{failure['error']}. Reached floor {failure['floor_reached']} before failure; "
                f"last decision family {failure['last_decision_family']} "
                f"({failure['decisions']} recorded selections)."
            )
        text.append("")
    return "\n".join(text)


def run_assessment(root: Path, recipe_path: Path) -> dict[str, Any]:
    recipe = json.loads(recipe_path.read_text())
    if (
        recipe.get("schema_version") != "native-pilot-assessment-config-v1"
        or recipe.get("assessment_policy") != POLICY
        or recipe.get("implementation_sha256") != _sha_file(Path(__file__))
    ):
        raise ValueError("Saved assessment recipe/source identity changed")
    maximum_seconds = recipe["resource_limits"]["wall_seconds"]
    if (
        type(maximum_seconds) not in {int, float}
        or not math.isfinite(maximum_seconds)
        or not 1 <= maximum_seconds <= 180
        or type(recipe["bootstrap_replicates"]) is not int
        or not 100 <= recipe["bootstrap_replicates"] <= 10000
        or type(recipe["bootstrap_seed"]) is not int
    ):
        raise ValueError("Assessment needs bounded wall time and fixed bootstrap settings")
    output = _private_path(root, recipe["workspace"])
    experiment_path = SavedFiles(root, maximum_seconds).path(recipe["experiment_config"])
    cfg = json.loads(experiment_path.read_text())
    pilot = _private_path(root, cfg["workspace"])
    if output == pilot or pilot in output.parents or output in pilot.parents:
        raise ValueError("Assessment output cannot alter the source pilot")
    if manifest_identifier(cfg) != recipe["experiment_config_id"]:
        raise ValueError("Assessment experiment identity changed")
    if (output / "report.json").is_file():
        saved = SavedFiles(root, maximum_seconds)
        report = saved.read(output / "report.json", "report_id")
        if report["assessment_config_id"] != manifest_identifier(recipe) or report[
            "markdown_sha256"
        ] != _sha_file(output / "report.md"):
            raise ValueError("Saved assessment report/recipe changed")
        for ref in report["source_files"]:
            if saved.pin(saved.path(ref["path"])) != ref["sha256"]:
                raise ValueError("Assessed pilot sources changed")
        return {
            "status": "saved_assessment_verified",
            "report_id": report["report_id"],
            "verdict": report.get("verdict"),
            "games_launched": 0,
            "optimizer_steps": 0,
        }
    if output.exists():
        raise FileExistsError("Preserve the interrupted assessment output for inspection")
    report = assess_completed_pilot(
        root,
        experiment_path,
        replicates=recipe["bootstrap_replicates"],
        bootstrap_seed=recipe["bootstrap_seed"],
        maximum_seconds=maximum_seconds,
    )
    if report["status"] == "awaiting_completed_pilot":
        return report
    output.mkdir(parents=True, exist_ok=False)
    text = render_assessment(report)
    (output / "report.md").write_text(text)
    report.update(
        assessment_config_id=manifest_identifier(recipe),
        markdown_sha256=_sha_file(output / "report.md"),
    )
    report["report_id"] = manifest_identifier(report)
    atomic_json(output / "report.json", report)
    return {
        "status": report["status"],
        "report_id": report["report_id"],
        "verdict": report.get("verdict"),
        "report": str(output / "report.md"),
        "games_launched": 0,
        "optimizer_steps": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Assess a finished saved native pilot; no new games"
    )
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    try:
        result = run_assessment(Path(__file__).resolve().parents[2], args.config.resolve())
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({"status": "assessment_error", "error": str(error), "games_launched": 0}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
