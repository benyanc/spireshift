"""Read-only descriptive combat audit of sealed, complete TRAIN games.

Counts describe choices, never prove the value of an alternative. No held-out
decisions, simulator calls, model fitting or extra health rewards are used.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_reuse import check_sources
from spireshift.native_shop_policy import CONTRACT


def combat(public: dict[str, Any], index: int) -> dict[str, Any] | None:
    interaction = public["context"]["interaction"]
    if interaction["kind"] != "combat_turn":
        return None
    content = interaction["content"]["context"]
    player = public["context"]["persistent"]["player"]
    run = public["context"]["persistent"]["run"]
    candidates = public["candidates"]
    chosen = candidates[index]
    can_play = any(c["verb"] == "play" for c in candidates)
    can_block = any(
        c["verb"] == "play"
        and ((c.get("subject") or {}).get("properties", {}).get("stats") or {}).get("block", 0) > 0
        for c in candidates
    )
    can_use = any(c["verb"] == "use" for c in candidates)
    return {
        "act": run["act"],
        "floor": run["floor"],
        "encounter_type": content["encounter_type"],
        "enemies": sorted(e["definition_id"] for e in content["enemies"]),
        "round": content["round"],
        "hp": player["hp"],
        "max_hp": player["max_hp"],
        "block": content["player"]["block"],
        "energy": content["player"]["energy"],
        "belt_count": len(player["potions"]),
        "action": chosen["label"],
        "verb": chosen["verb"],
        "play_available": can_play,
        "block_card_available": can_block,
        "potion_available": can_use,
        "end_with_play_available": chosen["verb"] == "end_turn" and can_play,
        "end_with_potion_available": chosen["verb"] == "end_turn" and can_use,
        "end_low_health_with_block_available": chosen["verb"] == "end_turn"
        and can_block
        and player["hp"] <= player["max_hp"] / 4,
    }


def inspect_case(case: dict[str, Any]) -> dict[str, Any]:
    if (
        case["status"] != "terminal"
        or case.get("native_ending_evidence_agrees") is not True
        or case.get("privileged_fixture") is not False
        or case.get("recovered") is not False
    ):
        raise ValueError("Combat-loss audit requires clean, unrecovered terminal games")
    counts: Counter[str] = Counter()
    families: Counter[str] = Counter()
    last = None
    entries: dict[tuple[int, int], dict[str, Any]] = {}
    for row in case["decisions"]:
        public, choice = row["public_input"], row["choice"]
        if choice.get("policy_contract") != CONTRACT:
            raise ValueError("Audit cannot reinterpret another policy behavior contract")
        if choice.get("public_input_id") != manifest_identifier(public):
            raise ValueError("Saved public input no longer matches the chosen action")
        families[public["context"]["interaction"]["kind"]] += 1
        point = combat(public, choice["action_index"])
        if point is None:
            continue
        last = point
        entries.setdefault((point["act"], point["floor"]), point)
        counts["combat_decisions"] += 1
        counts["end_turns"] += point["verb"] == "end_turn"
        counts["card_plays"] += point["verb"] == "play"
        counts["potion_uses"] += point["verb"] == "use"
        counts["potion_opportunities"] += point["potion_available"]
        for name in (
            "end_with_play_available",
            "end_with_potion_available",
            "end_low_health_with_block_available",
        ):
            counts[name] += point[name]
    terminal_combat = last is not None and (last["act"], last["floor"]) == (
        case["maximum_act"],
        case["maximum_floor"],
    )
    entry = entries[(last["act"], last["floor"])] if terminal_combat and last else None
    return {
        "victory": case["victory"],
        "maximum_floor": case["maximum_floor"],
        "completed_acts": case["completed_acts"],
        "counts": dict(counts),
        "families": dict(families),
        "terminal_combat_observed": terminal_combat,
        "last_combat_entry": entry,
        "last_combat_decision": last,
        "last_combat_is_death_cause_proven": False,
    }


def audit(root: Path, path: Path) -> dict[str, Any]:
    started = time.monotonic()
    path = root / path
    initial_sources = {
        str(path.relative_to(root)): _sha_file(path),
        "src/spireshift/native_combat_loss_audit.py": _sha_file(Path(__file__)),
    }
    cfg = json.loads(path.read_text())
    report_path = root / cfg["source_report"]["path"]
    report = identified(report_path)
    if report["report_id"] != cfg["source_report"]["id"] or report["status"] != (
        "native_shop_continuation_complete"
    ):
        raise ValueError("Audit requires the completed, sealed shop continuation")
    check_sources(root, report["sources"])
    workspace = root / cfg["workspace"]
    final = workspace / "report.json"
    if final.exists():
        saved = identified(final)
        if saved["config_id"] != manifest_identifier(cfg):
            raise ValueError("Saved loss audit belongs to another recipe")
        check_sources(root, saved["sources"])
        return saved
    cases = []
    excluded = []
    counts: Counter[str] = Counter()
    deaths: Counter[str] = Counter()
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[int] = set()
    for done in sorted((report_path.parent / "chunks").glob("*/done.json")):
        receipt = identified(done)
        task = json.loads(done.with_name("active.json").read_text())["request"]
        if receipt["request_id"] != manifest_identifier(task):
            raise ValueError("Saved collection request changed")
        if task["kind"] != "collect":
            continue
        if task.get("training") is not True:
            continue  # No evaluation decision histories are opened.
        for relative in receipt["result"]["paths"]:
            source = root / relative
            header = json.loads(source.read_text())
            binding = header["binding"]
            if (
                binding["partition"] != "train"
                or binding["panel_purpose"] != "training"
                or binding["config_id"] != report["config_id"]
                or binding["seed_id"] in seen
            ):
                raise ValueError("Audit input is not distinct TRAIN-only experience")
            seen.add(binding["seed_id"])
            case = read_native_episode(source, binding)
            if case["status"] != "terminal":
                excluded.append({"seed_id": binding["seed_id"], "status": case["status"]})
                continue
            result = inspect_case(case)
            result.update(path=relative, seed_id=binding["seed_id"], player=task["numerical_seed"])
            cases.append(result)
            counts.update(result["counts"])
            last = result["last_combat_decision"]
            if result["terminal_combat_observed"] and not result["victory"]:
                deaths[last["encounter_type"] + ":" + "+".join(last["enemies"])] += 1
            stage = "early" if task["round"] <= 39 else "late" if task["round"] >= 45 else "middle"
            groups[f"player-{task['numerical_seed']}-{stage}"].append(result)
            del case
    source_files = {
        **initial_sources,
        str(report_path.relative_to(root)): _sha_file(report_path),
    }
    body = {
        "schema_version": "native-combat-loss-audit-v1",
        "config_id": manifest_identifier(cfg),
        "source_report_id": report["report_id"],
        "train_attempts": len(seen),
        "clean_terminal_games": len(cases),
        "excluded_failures": excluded,
        "counts": dict(counts),
        "terminal_combat_encounters": dict(deaths.most_common()),
        "groups": {
            name: {
                "games": len(rows),
                "wins": sum(r["victory"] for r in rows),
                "mean_floor": sum(r["maximum_floor"] for r in rows) / len(rows),
                "counts": dict(sum((Counter(r["counts"]) for r in rows), Counter())),
            }
            for name, rows in groups.items()
        },
        "cases": cases,
        "sources": source_files,
        "maximum_raw_game_histories_retained": 1,
        "evaluation_histories_opened": 0,
        "games_launched": 0,
        "optimizer_steps": 0,
        "automatic_training_follows": False,
        "claim_scope": "descriptive_TRAIN_behavior_not_counterfactual_action_quality",
        "wall_seconds": time.monotonic() - started,
    }
    check_sources(root, report["sources"])
    check_sources(root, initial_sources)
    result = {**body, "report_id": manifest_identifier(body)}
    atomic_json(final, result)
    return result


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("config", type=Path)
    a = p.parse_args()
    result = audit(Path.cwd(), a.config)
    print(json.dumps({k: v for k, v in result.items() if k not in {"sources", "cases"}}, indent=2))


if __name__ == "__main__":
    main()
