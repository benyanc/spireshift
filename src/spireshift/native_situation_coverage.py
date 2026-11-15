"""Coverage-first sampling of the frozen public candidate pool; no outcome labels."""

from __future__ import annotations

from collections import Counter
from typing import Any

from spireshift.native_situation_features import rank
from spireshift.native_situation_selection import LIMITS

POLICY = "public_family_act_floor_encounter_health_opportunity_coverage_then_balance_v2"


def strata(row: dict[str, Any]) -> set[str]:
    d = row["description"]
    result = {f"family_stage/{d['family']}/{d['act']}/{d['floor_band']}", f"health/{d['hp_band']}"}
    if d["family"] == "combat_turn" and d["encounter_type"] is not None:
        result.add(f"combat_encounter/{d['encounter_type']}")
    result.update(f"opportunity/{tag}" for tag in d["tags"])
    return result


def select(
    rows: list[dict[str, Any]], splits: dict[str, str]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    canonical: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row["world"] not in splits:
            raise ValueError("Reject an undeclared source world")
        prior = canonical.get(row["public_input_id"])
        if prior is None or rank([row["source_ref"], row["decision_index"]]) < rank(
            [prior["source_ref"], prior["decision_index"]]
        ):
            canonical[row["public_input_id"]] = row
    selected: list[dict[str, Any]] = []
    coverage = {}
    for split, maximum in LIMITS["split_sizes"].items():
        chosen, detail = _select_split(canonical, splits, split, maximum)
        selected.extend(chosen)
        coverage[split] = detail
    return selected, {
        "policy": POLICY,
        "candidate_references": len(rows),
        "exact_unique_public_states": len(canonical),
        "exact_duplicate_references_removed": len(rows) - len(canonical),
        "selected_situations": len(selected),
        "requested_split_sizes": LIMITS["split_sizes"],
        "selected_split_sizes": dict(Counter(r["split"] for r in selected)),
        "coverage_by_split": coverage,
        "source_world_splits_reused_unchanged": True,
        "selection_uses_saved_actions_or_final_outcomes": False,
        "shortages_are_not_filled_with_duplicates_or_synthetic_states": True,
    }


def _select_split(
    canonical: dict[str, dict[str, Any]], splits: dict[str, str], split: str, maximum: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    pool = {k: r for k, r in canonical.items() if splits[r["world"]] == split}
    row_strata = {k: strata(r) for k, r in pool.items()}
    support = {
        s: {r["world"] for k, r in pool.items() if s in row_strata[k]}
        for s in set().union(*row_strata.values())
    }
    available, covered = set(support), set()
    worlds: Counter[str] = Counter()
    families: Counter[str] = Counter()
    world_family: Counter[tuple[str, str]] = Counter()
    buckets: Counter[str] = Counter()
    inventories: Counter[tuple[str, str]] = Counter()
    inventory_buckets: Counter[tuple[str, str]] = Counter()
    used = 0

    def eligible(row: dict[str, Any]) -> bool:
        d, world = row["description"], row["world"]
        family, bucket, inv = d["family"], rank(d["bucket"]), d["inventory_signature"]
        return (
            used < maximum
            and worlds[world] < LIMITS["per_world"]
            and families[family] < LIMITS["per_split_family"]
            and world_family[world, family] < LIMITS["per_world_family"]
            and inventory_buckets[bucket, inv] < LIMITS["per_split_inventory_bucket"]
        )

    def accept(row: dict[str, Any]) -> None:
        nonlocal used
        d, world = row["description"], row["world"]
        family, bucket, inv = d["family"], rank(d["bucket"]), d["inventory_signature"]
        selected.append({**row, "split": split})
        covered.update(row_strata[row["public_input_id"]])
        del pool[row["public_input_id"]]
        worlds[world] += 1
        families[family] += 1
        world_family[world, family] += 1
        buckets[bucket] += 1
        inventories[family, inv] += 1
        inventory_buckets[bucket, inv] += 1
        used += 1

    # Reserve rare PUBLIC strata first, counting supporting worlds, not repeats.
    for stratum in sorted(available, key=lambda s: (len(support[s]), rank(s))):
        if stratum in covered:
            continue
        candidates = [r for k, r in pool.items() if stratum in row_strata[k] and eligible(r)]
        if candidates:
            accept(
                min(
                    candidates,
                    key=lambda r: (
                        -len(row_strata[r["public_input_id"]] - covered),
                        families[r["description"]["family"]],
                        worlds[r["world"]],
                        rank(r["public_input_id"]),
                    ),
                )
            )
    family_names = sorted({r["description"]["family"] for r in canonical.values()})
    while used < maximum:
        progress = False
        for family in family_names:
            candidates = [
                r for r in pool.values() if r["description"]["family"] == family and eligible(r)
            ]
            if not candidates:
                continue
            accept(
                min(
                    candidates,
                    key=lambda r: (
                        buckets[rank(r["description"]["bucket"])],
                        inventories[family, r["description"]["inventory_signature"]],
                        worlds[r["world"]],
                        rank(r["public_input_id"]),
                    ),
                )
            )
            progress = True
        if not progress:
            break
    summary = {
        "available_strata": sorted(available),
        "covered_strata": sorted(covered),
        "uncovered_available_strata": sorted(available - covered),
        "all_available_strata_covered": available == covered,
        "supporting_native_worlds": {s: len(support[s]) for s in sorted(support)},
    }
    return selected, summary
