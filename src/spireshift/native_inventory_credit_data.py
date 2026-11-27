"""Decode one saved TRAIN episode at a time into a compact inventory-credit cache."""

from __future__ import annotations

import json
import math
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode, score_episode
from spireshift.native_inventory_credit_features import ENCODER, inventory
from spireshift.native_shop_policy import ShopNavigation
from spireshift.native_structured_policy import CONTRACT
from spireshift.native_value_credit import public_value_features
from spireshift.neural_combat import _numpy
from spireshift.training_objective import TrainingScoreSpec


def verify_binding(
    binding: dict[str, Any], source: dict[str, Any], model_id: str, expected: dict[int, str]
) -> None:
    if (
        binding.get("config_id") != manifest_identifier(source)
        or binding.get("partition") != "train"
        or binding.get("panel_purpose") != "training"
        or binding.get("model_id") != model_id
        or binding.get("seed_manifest_id") != source["seed_manifest"]["id"]
        or binding.get("environment_id") != source["environment_manifest"]["id"]
        or binding.get("training_spec_id") != source["training_spec"]["id"]
        or binding.get("policy_contract") != CONTRACT
        or binding.get("seed_id") not in expected
        or binding.get("native_seed") != expected[binding["seed_id"]]
    ):
        raise ValueError("Reject evaluation, foreign-policy, stale or unplanned saved data")


def effective_rows(
    case: dict[str, Any], model_id: str, score: TrainingScoreSpec
) -> list[dict[str, Any]]:
    """Rebuild navigation and effective IDs; reuse sealed policy-probability audits."""
    if (
        case.get("status") != "terminal"
        or case.get("ordinary_PPO_eligible") is not True
        or case.get("recovered") is not False
        or case.get("privileged_fixture") is not False
        or case.get("privileged_fixed_world_teacher") is not False
        or case.get("native_ending_evidence_agrees") is not True
        or case.get("policy_contract") != CONTRACT
    ):
        raise ValueError("Only clean unprivileged own-policy training games enter diagnosis")
    navigation = ShopNavigation()
    result = []
    for decision in case["decisions"]:
        public, saved = decision["public_input"], decision["choice"]
        effective, indices, forced = navigation.view(public)
        action = saved["action_index"]
        if (
            type(action) is not int
            or action not in indices
            or saved.get("model_id") != model_id
            or saved.get("training") is not True
            or saved.get("policy_contract") != CONTRACT
            or saved.get("navigation_only") is not forced
            or saved.get("effective_action_index") != indices.index(action)
            or saved.get("effective_input_id") != manifest_identifier(effective)
            or saved.get("behavior")
            != ("deterministic_navigation" if forced else "sampled_softmax")
            or saved.get("temperature") != 0.8
            or type(saved.get("log_probability")) is not float
            or not math.isfinite(saved["log_probability"])
            or saved["log_probability"] > 1e-12
        ):
            raise ValueError("Saved effective TRAIN menu, navigation or behavior differs")
        navigation.advance(public, action)
        if not forced:
            coarse, potential = public_value_features(effective, score)
            result.append(
                {
                    "coarse": coarse,
                    "potential": potential,
                    "behavior_value": saved["value"],
                    "choices": len(effective["candidates"]),
                    "log_probability": saved["log_probability"],
                    "family": effective["context"]["interaction"]["kind"],
                    **inventory(effective),
                }
            )
    return result


def extract(
    root: Path,
    task: dict[str, Any],
    source: dict[str, Any],
    model_id: str,
    paths: list[str],
    score: TrainingScoreSpec,
    directory: Path,
    deadline: float,
) -> tuple[dict[str, Any], list[str], dict[str, Any]]:
    np = _numpy()
    expected = {s["id"]: s["seed"] for s in task["seeds"]}
    observed: set[int] = set()
    records, outcomes = [], []
    for name in paths:
        if time.monotonic() >= deadline:
            raise TimeoutError("Inventory extraction reached its finite saved-data cap")
        path = root / name
        binding = json.loads(path.read_text())["binding"]
        verify_binding(binding, source, model_id, expected)
        seed = binding["seed_id"]
        if seed in observed:
            raise ValueError("Duplicate whole training game")
        observed.add(seed)
        case = read_native_episode(path, binding)
        scored = score_episode(case, seed, score)
        if not scored["completed"]:
            raise ValueError("Do not fit incomplete or over-budget games")
        rows = effective_rows(case, model_id, score)
        for row in rows:
            row.update(world=seed, target=scored["training_return"])
        records.extend(rows)
        outcomes.append(
            {
                "world": seed,
                "target": scored["training_return"],
                "maximum_floor": case["maximum_floor"],
                "completed_acts": case["completed_acts"],
                "victory": case["victory"],
                "strategic_rows": len(rows),
                "native_decisions": len(case["decisions"]),
            }
        )
        del case, rows
        if len(records) > 100000:
            raise ValueError("Stop rather than exceed the compact cohort row cap")
    if observed != set(expected):
        raise ValueError("Whole saved TRAIN denominator differs")
    records.sort(key=lambda r: r["world"])
    names = sorted({name for row in records for name in row["values"]})
    if not records or len(names) > 4096:
        raise ValueError("Missing compact states or oversized inventory schema")
    index = {name: i for i, name in enumerate(names)}
    values = np.zeros((len(records), len(names)))
    present = np.zeros((len(records), len(names)), dtype=bool)
    for i, row in enumerate(records):
        for name, value in row["values"].items():
            values[i, index[name]] = value
            present[i, index[name]] = True
    data = {
        key: np.asarray([r[key] for r in records])
        for key in (
            "world",
            "target",
            "coarse",
            "potential",
            "behavior_value",
            "choices",
            "log_probability",
            "family",
            "deck_signature",
            "relic_signature",
            "inventory_signature",
        )
    }
    data["inventory"] = values
    data["inventory_present"] = present
    with (directory / "extracted.npz").open("xb") as handle:
        np.savez_compressed(handle, **data)
    metadata = {
        "encoder": ENCODER,
        "names": names,
        "outcomes": outcomes,
        "decisions": len(records),
        "choice_decisions": sum(r["choices"] > 1 for r in records),
        "distinct_owned_card_definitions": len(
            {name for row in records for name in row["deck_definitions"]}
        ),
        "distinct_owned_relic_definitions": len(
            {name for row in records for name in row["relic_definitions"]}
        ),
        "rows_with_public_relic_counter_view": sum(r["relic_counters_available"] for r in records),
        "maximum_raw_episode_histories_retained": 1,
        "native_policy_inference_replayed": False,
        "sealed_native_probability_audits_reused": True,
        "effective_input_ids_and_navigation_reconstructed": True,
        "held_only_cache_names_never_fitted_or_normalized": True,
    }
    return data, names, metadata


def alias_diagnostics(data: dict[str, Any]) -> dict[str, Any]:
    groups: dict[bytes, list[int]] = defaultdict(list)
    for i, row in enumerate(data["coarse"]):
        groups[row.tobytes()].append(i)
    counts = dict.fromkeys(
        (
            "coarse_groups",
            "groups_with_distinct_decks",
            "groups_with_distinct_relics",
            "cross_world_inventory_alias_groups",
            "rows_in_cross_world_inventory_alias_groups",
        ),
        0,
    )
    counts["coarse_groups"] = len(groups)
    for indices in groups.values():
        decks = {str(data["deck_signature"][i]) for i in indices}
        relics = {str(data["relic_signature"][i]) for i in indices}
        counts["groups_with_distinct_decks"] += len(decks) > 1
        counts["groups_with_distinct_relics"] += len(relics) > 1
        if len({int(data["world"][i]) for i in indices}) > 1 and (
            len(decks) > 1 or len(relics) > 1
        ):
            counts["cross_world_inventory_alias_groups"] += 1
            counts["rows_in_cross_world_inventory_alias_groups"] += len(indices)
    return {
        **counts,
        "exact_coarse_feature_equality_no_rounding": True,
        "same_coarse_information_not_necessarily_same_cross_fitted_weights": True,
        "different_true_state_values_or_causal_effects_proven": False,
    }
