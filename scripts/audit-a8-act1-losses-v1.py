"""Compare Act 1 decisions from the sealed normal-start A8 panel."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from statistics import fmean
from typing import Any

from spireshift.engine_learning import identified
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.engine_worker_qualification import immutable_checks
from spireshift.native_a8_paired_inputs import FITTING_EVIDENCE
from spireshift.native_compatibility_contract import verified
from spireshift.native_flow_verification_v12 import records
from spireshift.native_win4_game import write
from spireshift.native_win_inputs import restore_paths

EVIDENCE = "docs/evidence/native-a8-paired-finals-result-v1.json"
STUDY = "artifacts/native-a8-paired/study-v1/chunks"
OUTPUT = "artifacts/native-a8-paired/act1-loss-audit-v1/report.json"
RECIPE = "configs/native-curriculum/sts2-v0.111.0-a8-win-curriculum-{}.json"


def frozen(root: Path, panel: dict[str, Any]) -> dict[str, bool]:
    initial = json.loads((root / RECIPE.format("v1")).read_text())
    current = json.loads((root / RECIPE.format("v7")).read_text())
    baseline = identified(verified(root, initial["baseline"]))
    support = identified(verified(root, current["support"]["report"]))
    native = restore_paths(root, baseline["native"])
    native.update(
        candidate=root / support["builds"][0]["candidate"],
        candidate_before=support["candidate_inventory"],
    )
    checks = immutable_checks(
        EngineQualificationConfig(baseline["qualification_document"], root), native
    )
    fitting = identified(root / FITTING_EVIDENCE)
    if fitting["report_id"] != panel["fitting_evidence_id"] or not all(checks.values()):
        raise ValueError("The saved panel requires its frozen game, host and checkpoints")
    for ref in baseline["originals"].values():
        verified(root, {"path": ref["imported_path"], "sha256": ref["imported_sha256"]})
    for ref in fitting["candidates"].values():
        verified(root, {"path": ref["state_path"], "sha256": ref["state_sha256"]})
    return {**checks, "all_four_full_states_and_Adam_exact": True}


def transitions(path: Path) -> Iterator[tuple[int, dict[str, Any], int, dict[str, Any]]]:
    before, choice = None, None
    first_line = 0
    for line, row in enumerate(records(path), 1):
        kind = row["kind"]
        if kind == "policy_choice" and before is not None and choice is None:
            choice = row
            continue
        if kind not in {"policy_input", "final_observation"}:
            raise ValueError("Unexpected order in the sealed public journal")
        after = row["frame"]
        if before is not None:
            if choice is None or before["terminal"]:
                raise ValueError("Expected a choice between saved observations")
            index = choice["choice"]["action_index"]
            receipt = choice["receipt"]
            if (
                receipt["delivery"] != "delivered"
                or receipt["bound_action_id"] != before["actions"][index]["bound_action_id"]
                or receipt["binding_id"] != before["binding_id"]
                or receipt["before_snapshot_id"] != before["observation"]["snapshot_id"]
                or receipt["successor_snapshot_id"] != after["observation"]["snapshot_id"]
            ):
                raise ValueError("The saved transition has a mismatched delivery")
            if receipt["delivery_domain"] == "native":
                yield first_line, before, index, after
            elif receipt["delivery_domain"] != "local_answer_factor":
                raise ValueError("Unknown delivery domain")
        before, choice, first_line = after, None, line
    if before is None or not before["terminal"] or before["ending"]["victory"] or choice:
        raise ValueError("The saved game must end in the sealed terminal loss")


def state(frame: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    ctx = frame["public_input"]["context"]
    return (
        ctx["persistent"]["run"],
        ctx["persistent"]["player"],
        ctx["interaction"]["content"].get("context", {}),
    )


def subject(action: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    item = action.get("subject") or {}
    return item.get("role"), item.get("properties", {})


def belt(player: dict[str, Any]) -> list[str]:
    return [item["definition_id"] for item in player["potions"] if item]


def audit_cell(root: Path, saved: dict[str, Any], seal_id: str) -> dict[str, Any]:
    path = root / STUDY / saved["key"]
    seal = identified(path / "done.json")
    if seal["report_id"] != seal_id or seal["result"] != saved:
        raise ValueError("The cell differs from the verified paired result")
    name = f"{STUDY}/{saved['key']}/shared-public.jsonl.gz"
    trace = verified(root, {"path": name, "sha256": seal["sources"][name]})
    counts: Counter[str] = Counter()
    fights: dict[int, dict[str, Any]] = {}
    choices = []
    resources = []
    terminal = None
    previous_buy = None
    delivered = 0
    for line, before, index, after in transitions(trace):
        delivered += 1
        run, p, context = state(before)
        if run["act"] != 1:
            continue
        run_after, successor, _ = state(after)
        floor, family = run["floor"], before["source_family"]
        menu = before["public_input"]["candidates"]
        action = menu[index]
        role, properties = subject(action)
        label, verb = action["label"], action["verb"]
        hp, next_hp = p["hp"], successor["hp"]
        counts["native_deliveries"] += 1
        anchor = {
            "line": line,
            "floor": floor,
            "family": family,
            "label": label,
            "hp": hp,
            "next_hp": next_hp,
        }
        choices.append({**anchor, "input_digest": before["input_digest"], "index": index})

        combat = context.get("encounter_type") if context.get("kind") == "combat" else None
        if combat:
            fight = fights.setdefault(
                floor,
                {
                    "floor": floor,
                    "type": combat,
                    "entry_hp": hp,
                    "exit_hp": hp,
                    "enemies": [e["definition_id"] for e in context["enemies"]],
                    "lethal": False,
                    "potion_use_offered": False,
                },
            )
            fight["exit_hp"] = next_hp
            fight["lethal"] |= after["terminal"]
            fight["potion_use_offered"] |= any(
                a["verb"] == "use" and subject(a)[0] == "potion" for a in menu
            )
            if role == "potion" and verb == "use":
                counts["combat_potion_uses"] += 1

        held, next_held = belt(p), belt(successor)
        discarded = (
            role == "potion" and label.startswith("Discard ") and len(next_held) == len(held) - 1
        )
        if discarded:
            counts["potion_discards"] += 1
            if not next_held:
                counts["discarded_last_potion"] += 1
            if previous_buy and previous_buy[:2] == (floor, held) and not next_held:
                counts["bought_then_immediately_discarded_only_potion"] += 1
                resources.append(
                    {
                        **anchor,
                        "kind": "immediate_purchase_discard",
                        "purchase_line": previous_buy[2],
                    }
                )
        previous_buy = None
        if family == "shop_inventory" and properties.get("can_purchase") is True:
            if role == "potion":
                counts["potion_purchases"] += 1
                if not held and len(next_held) == 1:
                    previous_buy = floor, next_held, line
            if role == "card":
                counts["card_purchases"] += 1
        if family == "rest_site" and label in {"Rest", "Smith"}:
            counts[f"camp_{label.lower()}"] += 1
            if hp * 2 <= p["max_hp"] and any(a["label"] == "Rest" for a in menu):
                counts["low_hp_camp_with_rest"] += 1
                if label == "Smith":
                    counts["low_hp_smith_with_rest"] += 1
            resources.append({**anchor, "kind": "camp", "max_hp": p["max_hp"]})

        if after["terminal"]:
            view = properties.get("public_card_views", {}).get(
                "interaction:/context/player/hand/*", {}
            )
            hp_cost = (view.get("stats") or {}).get("hploss", 0)
            lethal_spend = verb == "play" and hp_cost >= hp > 0 and next_hp == 0
            terminal = {
                **anchor,
                "kind": "lethal_hp_spend" if lethal_spend else verb,
                "encounter": combat,
                "card_hp_cost": hp_cost if lethal_spend else None,
                "defend_offered": any(a["label"] in {"Play Defend", "Play Defend+"} for a in menu),
            }
        if run_after["act"] != 1:
            counts["act1_clears"] += 1

    if delivered != saved["verified_native_deliveries"] or bool(terminal) == bool(
        saved["completed_acts"]
    ):
        raise ValueError("Act 1 outcome or delivery count differs from the sealed cell")
    return {
        **{k: saved[k] for k in ("key", "world", "player", "arm")},
        "counts": dict(counts),
        "fights": list(fights.values()),
        "terminal": terminal,
        "resources": resources,
        "choices": choices,
    }


def arm_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = sum((Counter(row["counts"]) for row in rows), Counter())
    fights = [fight for row in rows for fight in row["fights"]]
    stages = {}
    for kind in ("normal", "elite", "boss"):
        subset = [f for f in fights if f["type"] == kind]
        stages[kind] = {
            "started": len(subset),
            "fatal": sum(f["lethal"] for f in subset),
            "mean_entry_hp": fmean(f["entry_hp"] for f in subset),
        }
    deaths = [row["terminal"] for row in rows if row["terminal"]]
    return {
        "games": len(rows),
        "counts": dict(counts),
        "death_room_counts": dict(Counter(d["encounter"] or d["family"] for d in deaths)),
        "fatal_action_counts": dict(Counter(d["kind"] for d in deaths)),
        "mean_first_fight_exit_hp": fmean(row["fights"][0]["exit_hp"] for row in rows),
        "fights_with_potion_use_offered": sum(f["potion_use_offered"] for f in fights),
        "combat_by_room_type": stages,
    }


def audit(root: Path) -> dict[str, Any]:
    evidence = identified(root / EVIDENCE)
    panel = identified(verified(root, evidence["saved_recovery"]))
    if (
        panel["report_id"] != evidence["saved_recovery"]["report_id"]
        or panel["status"] != "saved_paired_development_comparison_verified"
        or len(panel["seals"]) != len(panel["cells"])
        or len(panel["cells"]) != 48
    ):
        raise ValueError("Expected the exact saved 48-game comparison")
    before = frozen(root, panel)
    games = {}
    for saved in panel["cells"]:
        row = audit_cell(root, saved, panel["seals"][saved["key"]])
        games[row["world"], row["player"], row["arm"]] = row
    pairs = []
    for world in panel["worlds"]:
        for player in (2, 3):
            original, fitted = (games[world, player, arm] for arm in ("original", "fitted"))
            divergent = next(
                (a, b)
                for a, b in zip(original.pop("choices"), fitted.pop("choices"), strict=False)
                if (a["input_digest"], a["index"]) != (b["input_digest"], b["index"])
            )
            first, second = divergent
            if first["input_digest"] != second["input_digest"]:
                raise ValueError("This panel requires an exact shared menu at the first difference")
            pairs.append(
                {
                    "world": world,
                    "player": player,
                    "original": first,
                    "fitted": second,
                    "same_displayed_label": first["label"] == second["label"],
                }
            )
    after = frozen(root, panel)
    if before != after:
        raise ValueError("The frozen inputs changed during the saved audit")
    arms = {
        arm: arm_summary([row for (_, _, name), row in games.items() if name == arm])
        for arm in ("original", "fitted")
    }
    return write(
        root / OUTPUT,
        {
            "schema_version": "native-a8-act1-saved-loss-audit-v1",
            "status": "act1_loss_comparison_verified",
            "source_panel_id": panel["report_id"],
            "frozen_checks": after,
            "arms": arms,
            "first_difference_counts": dict(
                Counter(
                    "same_displayed_label" if p["same_displayed_label"] else p["original"]["family"]
                    for p in pairs
                )
            ),
            "pairs": pairs,
            "cells": list(games.values()),
            "new_game_launches": 0,
            "optimizer_updates": 0,
            "panel_worlds_are_development_only": True,
            "audit_source_sha256": _sha_file(Path(__file__)),
        },
    )


if __name__ == "__main__":
    result = audit(Path.cwd().resolve())
    print(
        json.dumps(
            {k: result[k] for k in ("status", "arms", "first_difference_counts", "report_id")},
            indent=2,
        )
    )
