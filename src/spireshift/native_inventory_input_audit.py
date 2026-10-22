"""Audit saved TRAIN actor distinctions and trace the native combat-counter omission."""

from __future__ import annotations

import argparse
import gzip
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_context_reuse import check_sources
from spireshift.native_inventory_credit_data import verify_binding
from spireshift.native_inventory_credit_features import inventory
from spireshift.native_inventory_credit_study import prepare
from spireshift.native_inventory_input_probes import changes, probe, visible_player
from spireshift.native_shop_policy import ShopNavigation
from spireshift.native_structured_inputs import load
from spireshift.native_structured_model import encode, extend
from spireshift.native_value_credit import public_value_features

REQUIRED = {
    "deck_definition",
    "deck_upgrade",
    "deck_displayed_cost",
    "deck_cost_ownership",
    "deck_upgrade_ownership",
    "relic_definition",
    "relic_counter_value",
    "relic_counter_zero_vs_unavailable",
    "relic_counter_ownership",
    "current_hand_and_subject_cost",
}


def native_counter_example(path: Path, deadline: float) -> dict[str, Any] | None:
    """Read a DEBUG journal; return only the already-public relic ID and counter.

    Raw operands, RNG, private future state and the rest of the response are never
    returned, encoded, fitted or used as an action/return label.
    """
    with gzip.open(path, "rt") as handle:
        for line in handle:
            if time.monotonic() >= deadline:
                raise TimeoutError("Saved native counter scan reached its wall cap")
            row = json.loads(line)
            state = row.get("response", {})
            if state.get("decision") == "combat_play":
                for relic in state.get("player", {}).get("relics", []):
                    if type(relic.get("counter")) in (int, float):
                        return {"definition_id": relic["id"], "counter": relic["counter"]}
    return None


def audit(root: Path, cfg: dict[str, Any], deadline: float) -> dict[str, Any]:
    context = prepare(root, root / cfg["credit_recipe"])
    diagnosis = identified(root / cfg["credit_report"]["path"])
    if (
        diagnosis["report_id"] != cfg["credit_report"]["id"]
        or diagnosis["status"] != "native_inventory_credit_diagnosis_complete"
    ):
        raise ValueError("Require the completed saved inventory-credit diagnosis")
    check_sources(root, diagnosis["sources"])
    source, done, score = context["source"], context["done"], context["score"]
    parents = load(root, root / context["source_report"]["recipe_path"])
    original = parents["models"][2]
    models = {
        a: extend(original, parents["adams"][2], tuple(parents["layout"]["columns"]), a)[0]
        for a in ("unchanged", "hashed", "named")
    }
    # Player 3 has the same encoding contract, not necessarily the same weights.
    second = parents["models"][3]
    if (original.mode, original.actor.dimension, original.actor.input_normalization) != (
        second.mode,
        second.actor.dimension,
        second.actor.input_normalization,
    ):
        models["original-player-3"] = second
    covered: Counter[str] = Counter()
    families: Counter[str] = Counter()
    checks, gaps = [], []
    natural: list[dict[str, Any]] = []
    representatives: dict[tuple[float, ...], tuple[int, str, dict[str, Any]]] = {}
    worlds: set[int] = set()
    games = rows_seen = combat_rows = combat_with_counters = 0
    for task in context["tasks"].values():
        if task["arm"] != "unchanged":
            continue  # Both fixed players and both rounds; no duplicated input-arm traces.
        model_id = done[task["state"]]["model_id"]
        expected = {s["id"]: s["seed"] for s in task["seeds"]}
        for name in (p for c in task["collections"] for p in done[c]["paths"]):
            if time.monotonic() >= deadline:
                raise TimeoutError("Saved input audit reached its wall cap")
            path = root / name
            binding = json.loads(path.read_text())["binding"]
            verify_binding(binding, source, model_id, expected)
            case = read_native_episode(path, binding)
            if case["status"] != "terminal" or not case["ordinary_PPO_eligible"]:
                raise ValueError("Only sealed clean TRAIN inputs enter the distinction audit")
            navigation = ShopNavigation()
            missing = False
            for row in case["decisions"]:
                public, indices, forced = navigation.view(row["public_input"])
                choice = row["choice"]
                if (
                    choice["effective_input_id"] != manifest_identifier(public)
                    or choice["action_index"] not in indices
                ):
                    raise ValueError("Saved effective public menu changed")
                navigation.advance(row["public_input"], choice["action_index"])
                if forced:
                    continue
                family = public["context"]["interaction"]["kind"]
                families[family] += 1
                rows_seen += 1
                if family == "combat_turn":
                    combat_rows += 1
                    available = "relics" in visible_player(public)
                    combat_with_counters += available
                    missing |= not available
                if any(covered[k] < 8 for k in REQUIRED):
                    for kind, before, after in changes(public):
                        if covered[kind] < 8:
                            checks.append(
                                {
                                    "world": binding["seed_id"],
                                    "family": family,
                                    **probe(kind, before, after, models, score),
                                }
                            )
                            covered[kind] += 1
                if len(natural) < 16:
                    coarse, _ = public_value_features(public, score)
                    signature = inventory(public)["inventory_signature"]
                    prior = representatives.get(coarse)
                    if (
                        prior is not None
                        and prior[0] != binding["seed_id"]
                        and prior[1] != signature
                    ):
                        a, _ = encode(prior[2], original, score)
                        b, _ = encode(public, original, score)
                        natural.append(
                            {
                                "worlds": [prior[0], binding["seed_id"]],
                                "actual_actor_inputs_distinct": a != b,
                                "inventory_causal_effect_isolated": False,
                            }
                        )
                        del representatives[coarse]
                    elif prior is None and len(representatives) < 512:
                        representatives[coarse] = (binding["seed_id"], signature, public)
            if missing:
                example = native_counter_example(
                    path.parent / "worker/private-transcript.jsonl.gz", deadline
                )
                if example is not None:
                    gaps.append(
                        {
                            "episode_path": name,
                            "world": binding["seed_id"],
                            "legacy_combat_counter_view_absent": True,
                            **example,
                        }
                    )
            worlds.add(binding["seed_id"])
            games += 1
            del case
    if games != 128 or len(worlds) != 64 or not covered.keys() >= REQUIRED or not natural:
        raise ValueError("Saved input audit did not meet its predeclared coverage")
    if any(not row["actual_actor_inputs_distinct"] for row in natural):
        raise ValueError("A checked natural inventory pair has identical actor inputs")
    sources = {**context["sources"], **diagnosis["sources"], **parents["sources"]}
    sources[cfg["credit_report"]["path"]] = _sha_file(root / cfg["credit_report"]["path"])
    check_sources(root, sources)
    return {
        "source_games": games,
        "distinct_worlds": len(worlds),
        "learning_rows": rows_seen,
        "decision_families": dict(families),
        "probe_counts": dict(covered),
        "checks": checks,
        "natural_pairs": natural,
        "counter_omission_examples": gaps,
        "combat_rows": combat_rows,
        "combat_rows_with_relic_counter_view": combat_with_counters,
        "actor_encoding_distinctions_passed": True,
        "projection_repair_required": bool(gaps),
        "larger_training_allowed": not gaps,
        "syntactic_probes_are_native_game_states": False,
        "native_journal_used_only_for_public_counter_omission_evidence": True,
        "different_action_probabilities_required": False,
        "sources": sources,
    }


def run(root: Path, path: Path) -> dict[str, Any]:
    started = time.monotonic()
    cfg = json.loads(path.read_text())
    if cfg["schema_version"] != "native-inventory-input-audit-config-v1" or cfg[
        "implementation_sha256"
    ] != {
        n: _sha_file(root / "src/spireshift" / n)
        for n in ("native_inventory_input_probes.py", "native_inventory_input_audit.py")
    }:
        raise ValueError("Preserve the finite saved input audit and source identities")
    journal = ChunkJournal(root, cfg)
    with journal.lock():
        final = journal.workspace / "report.json"
        if final.exists():
            cached = identified(final)
            if cached["config_id"] != journal.config_id:
                raise ValueError("Saved input audit belongs to another recipe")
            check_sources(root, cached["sources"])
            return cached
        request = {"credit_report": cfg["credit_report"], "source_games": 128, "probes_per_kind": 8}
        folder = journal.begin("saved-input-checks", request)
        result = audit(root, cfg, started + 225)
        sources = result.pop("sources")
        sources[str(path.relative_to(root))] = _sha_file(path)
        sources.update({f"src/spireshift/{n}": s for n, s in cfg["implementation_sha256"].items()})
        body = {
            "schema_version": "native-inventory-input-audit-v1",
            "config_id": journal.config_id,
            "status": "actor_distinctions_pass_projection_repair_required"
            if result["projection_repair_required"]
            else "inventory_input_audit_pass",
            **result,
            "sources": sources,
            "games_launched": 0,
            "optimizer_steps": 0,
            "original_full_states_and_Adam_unchanged": True,
            "wall_seconds": time.monotonic() - started,
        }
        report = {**body, "report_id": manifest_identifier(body)}
        atomic_json(folder / "result.json", report)
        journal.commit("saved-input-checks", request, {"report_id": report["report_id"]})
        atomic_json(final, report)
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    try:
        result = run(root, root / args.recipe)
        print(
            json.dumps(
                {k: v for k, v in result.items() if k not in {"sources", "checks"}}, indent=2
            )
        )
        return 0
    except (OSError, ValueError, KeyError, TimeoutError) as error:
        print(json.dumps({"status": "stopped_preserving_input_audit", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
