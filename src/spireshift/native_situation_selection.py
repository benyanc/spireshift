"""Deterministic diversity sampling with whole-world splits and explicit shortages."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, TypedDict

from spireshift.native_situation_features import rank


class SamplingLimits(TypedDict):
    per_episode_bucket: int
    per_world: int
    per_world_family: int
    per_split_family: int
    per_split_inventory_bucket: int
    split_sizes: dict[str, int]


LIMITS: SamplingLimits = {
    "per_episode_bucket": 2,
    "per_world": 12,
    "per_world_family": 2,
    "per_split_family": 32,
    "per_split_inventory_bucket": 2,
    "split_sizes": {"fit": 192, "validation": 64},
}


def split_worlds(worlds: list[str]) -> dict[str, str]:
    """Split native worlds before state selection; all policies/branches stay together."""
    if len(set(worlds)) != len(worlds) or len(worlds) < 4:
        raise ValueError("Require at least four distinct complete native worlds")
    ordered = sorted(worlds, key=rank)
    held = set(ordered[: (len(ordered) + 3) // 4])
    return {world: "validation" if world in held else "fit" for world in ordered}


def thin(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bound each episode's contribution using only current public state."""
    counts: Counter[str] = Counter()
    selected = []
    for row in sorted(rows, key=lambda r: (rank(r["public_input_id"]), r["decision_index"])):
        bucket = rank(row["description"]["bucket"])
        if counts[bucket] < LIMITS["per_episode_bucket"]:
            selected.append(row)
            counts[bucket] += 1
    return selected


def select(
    rows: list[dict[str, Any]], splits: dict[str, str]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Round-robin families, then favor rarer stage/health/encounter/inventory groups.

    Exact public-state duplicates get one canonical provenance before splitting.
    No final outcome, saved action, return, logit or teacher result enters a rank.
    The bank remains observational, not a representative performance sample.
    """
    canonical: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = row["public_input_id"]
        if row["world"] not in splits:
            raise ValueError("A situation belongs to an undeclared whole world")
        prior = canonical.get(key)
        if prior is None or rank([row["source_ref"], row["decision_index"]]) < rank(
            [prior["source_ref"], prior["decision_index"]]
        ):
            canonical[key] = row
    selected = []
    for split, maximum in LIMITS["split_sizes"].items():
        families: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in canonical.values():
            if splits[row["world"]] == split:
                families[row["description"]["family"]].append(row)
        world_counts: Counter[str] = Counter()
        family_counts: Counter[str] = Counter()
        world_family: Counter[tuple[str, str]] = Counter()
        buckets: Counter[str] = Counter()
        inventories: Counter[tuple[str, str]] = Counter()
        inventory_buckets: Counter[tuple[str, str]] = Counter()
        count = 0
        while count < maximum:
            progress = False
            for family in sorted(families):
                if count >= maximum:
                    break
                eligible = []
                for row in families[family]:
                    world, desc = row["world"], row["description"]
                    bucket, inv = rank(desc["bucket"]), desc["inventory_signature"]
                    if (
                        world_counts[world] < LIMITS["per_world"]
                        and world_family[world, family] < LIMITS["per_world_family"]
                        and family_counts[family] < LIMITS["per_split_family"]
                        and inventory_buckets[bucket, inv] < LIMITS["per_split_inventory_bucket"]
                    ):
                        eligible.append(row)
                if not eligible:
                    continue
                chosen = min(
                    eligible,
                    key=lambda r: (
                        buckets[rank(r["description"]["bucket"])],
                        inventories[family, r["description"]["inventory_signature"]],
                        world_counts[r["world"]],
                        rank(r["public_input_id"]),
                    ),
                )
                world, desc = chosen["world"], chosen["description"]
                bucket, inv = rank(desc["bucket"]), desc["inventory_signature"]
                selected.append({**chosen, "split": split})
                families[family].remove(chosen)
                world_counts[world] += 1
                family_counts[family] += 1
                world_family[world, family] += 1
                buckets[bucket] += 1
                inventories[family, inv] += 1
                inventory_buckets[bucket, inv] += 1
                count += 1
                progress = True
            if not progress:
                break
    return selected, {
        "candidate_references": len(rows),
        "exact_unique_public_states": len(canonical),
        "exact_duplicate_references_removed": len(rows) - len(canonical),
        "selected_situations": len(selected),
        "requested_split_sizes": LIMITS["split_sizes"],
        "selected_split_sizes": dict(Counter(r["split"] for r in selected)),
        "splits_have_no_exact_duplicate_public_states": True,
        "selection_uses_saved_actions_or_final_outcomes": False,
        "shortages_are_not_filled_with_duplicates_or_synthetic_states": True,
    }
