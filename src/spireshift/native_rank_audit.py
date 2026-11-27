"""Replay saved public menus through fixed models; never generate or fit labels."""

from __future__ import annotations

import gzip
import json
import math
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_policy import dense_features
from spireshift.full_run_ppo_math import log_softmax
from spireshift.native_action_context import encode
from spireshift.native_action_rankings import compare, scores, selected
from spireshift.native_combat_behavior_game import binding
from spireshift.native_combat_behavior_policy import Chooser
from spireshift.native_combat_teacher_data import trace_id
from spireshift.native_outcome_predictor import PlayerWithPredictions

ARMS = ("original", "return_only", "consequence")
CONTRASTS = (
    ("original", "return_only"),
    ("original", "consequence"),
    ("return_only", "consequence"),
)


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    fields = (
        "greedy_changed",
        "before_margin",
        "after_margin",
        "before_centered_RMS",
        "after_centered_RMS",
        "KL_before_to_after",
        "entropy_change",
        "same_draw_choice_changed",
    )
    for group in sorted({r["group"] for r in rows}):
        eligible = [r for r in rows if r["group"] == group and r["strategic_menu"]]
        cells = {}
        for before, after in CONTRASTS:
            values = [r["comparisons"][f"{before}_to_{after}"] for r in eligible]
            cells[f"{before}_to_{after}"] = {
                key: sum(v[key] for v in values if v[key] is not None)
                / sum(v[key] is not None for v in values)
                if any(v[key] is not None for v in values)
                else None
                for key in fields
            }
            cells[f"{before}_to_{after}"].update(
                strict_pair_inversions=sum(v["strict_pair_inversions"] for v in values),
                strict_pairs_compared=sum(v["strict_pairs_compared"] for v in values),
            )
        result[group] = {
            "strategic_menus": len(eligible),
            "all_menus": sum(r["group"] == group for r in rows),
            "contrasts": cells,
        }
    return result


def audit_case(
    context: dict[str, Any],
    task: dict[str, Any],
    players: dict[int, PlayerWithPredictions],
    root: Path,
    directory: Path,
    deadline: float,
) -> dict[str, Any]:
    started = time.monotonic()
    old, r, models, score = (context[k] for k in ("old", "report", "models", "score"))
    player, variant = task["numerical_seed"], task["variant"]
    path = root / old["workspace"] / "chunks" / task["key"] / "episode.json"
    case = read_native_episode(path, binding(old, task, models[player, variant], score))
    if len(case["decisions"]) > context["config"]["maximum_saved_decisions_per_case"]:
        raise ValueError("Saved case exceeds the frozen finite ranking bound; preserve it")
    if (
        case["status"] != "terminal"
        or case["recovered"]
        or case["privileged_fixture"]
        or not case["native_ending_evidence_agrees"]
    ):
        raise ValueError("Rank only sealed clean saved games; never drop a failed source")
    chooser = Chooser(models[player, variant], score, task["seed"]["seed"], "greedy")
    params = {arm: models[player, arm].actor.unpack() for arm in ARMS}
    output = []
    for index, decision in enumerate(case["decisions"]):
        if time.monotonic() >= deadline:
            raise TimeoutError("Saved-menu ranking reached its finite cap")
        public, saved = decision["public_input"], decision["choice"]
        effective, indices, forced = chooser.navigation.view(public)
        expected = chooser(public)
        if expected.keys() != saved.keys() or any(
            not math.isclose(saved[k], v, rel_tol=0, abs_tol=1e-10)
            if type(v) is float
            else type(saved[k]) is not type(v) or saved[k] != v
            for k, v in expected.items()
        ):
            raise ValueError("Saved behavior, ownership, randomness or inference does not replay")
        rows, state = encode(effective, models[player, "original"], score)
        x = dense_features(rows, models[player, "original"].actor.dimension)
        values = {arm: scores(x, params[arm]) for arm in ARMS}
        unchanged = players[player].action_policy(effective, score, 0.8)
        if (
            unchanged[0] != rows
            or unchanged[1] != state
            or unchanged[2] != log_softmax(values["original"], 0.8)
        ):
            raise ValueError("Independent prediction fitting changed a policy score/probability")
        use_draw = None if saved["combat_owned"] or forced else saved["draw"]
        source_logs = log_softmax(values[variant], 0.8)
        own_index = 0 if forced else selected(source_logs, use_draw)
        if indices[own_index] != saved["action_index"] or not math.isclose(
            source_logs[own_index], saved["policy_log_probability"], abs_tol=1e-10, rel_tol=0
        ):
            raise ValueError("Raw-score replay differs from the recorded delivered action")
        output.append(
            {
                "index": index,
                "input_id": saved["public_input_id"],
                "effective_input_id": saved["effective_input_id"],
                "family": public["context"]["interaction"]["kind"],
                "source_action_index": saved["action_index"],
                "effective_candidate_indices": indices,
                "group": "navigation"
                if forced
                else "combat"
                if saved["combat_owned"]
                else "noncombat",
                "strategic_menu": not forced and len(rows) > 1,
                "raw_scores": values,
                "comparisons": {
                    f"{a}_to_{b}": compare(values[a], values[b], draw=use_draw)
                    for a, b in CONTRASTS
                },
            }
        )
    with gzip.open(directory / "rankings.jsonl.gz", "xt", encoding="utf-8") as stream:
        for row in output:
            stream.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    body = {
        "schema_version": "native-saved-action-ranking-case-v1",
        "source_key": task["key"],
        "source_variant": variant,
        "numerical_seed": player,
        "seed_id": task["seed"]["id"],
        "decisions": len(output),
        "trace_id": trace_id(case),
        "groups": summarize_rows(output),
        "fitted_prediction_policy_logs_exactly_unchanged": True,
        "saved_source_choices_reconstructed": True,
        "fitting_targets_from_development": 0,
        "counterfactual_same_menu_not_counterfactual_game_outcomes": True,
        "wall_seconds": time.monotonic() - started,
    }
    # The historical whole-case trace is sealed independently by the chunk source hashes.
    if not all(r["checks"].values()):
        raise ValueError("Historical qualification checks are not complete")
    result = {**body, "report_id": manifest_identifier(body)}
    atomic_json(directory / "ranking-report.json", result)
    return result


def aggregate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    cells: dict[tuple[int, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        for group, summary in case["groups"].items():
            if not summary["strategic_menus"]:
                continue
            for contrast, value in summary["contrasts"].items():
                cells[case["numerical_seed"], case["source_variant"], group, contrast].append(value)
    output = []
    for (player, origin, group, contrast), rows in sorted(cells.items()):
        fields = {k for row in rows for k in row if not k.startswith("strict_")}
        output.append(
            {
                "numerical_seed": player,
                "source_policy": origin,
                "group": group,
                "contrast": contrast,
                "games_with_eligible_menus": len(rows),
                "equal_game_mean": {
                    k: sum(row[k] for row in rows if row[k] is not None)
                    / sum(row[k] is not None for row in rows)
                    if any(row[k] is not None for row in rows)
                    else None
                    for k in sorted(fields)
                },
            }
        )
    return {
        "cells": output,
        "episodes": len(cases),
        "decisions": sum(c["decisions"] for c in cases),
        "each_source_policy_stratified_not_pooled_as_independent_states": True,
        "equal_game_within_stratum_not_raw_menu_weighted": True,
        "no_action_quality_or_causal_outcome_claim": True,
    }
