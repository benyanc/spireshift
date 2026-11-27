"""Saved-only replay and combat diagnostics for the completed v2 panel."""

from __future__ import annotations

import fcntl
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.native_a8_boss2_game import verify
from spireshift.native_a8_boss2_inputs import AREA, declaration, freeze, load, short_check
from spireshift.native_a8_boss_checks import compare_teachers
from spireshift.native_a8_boss_game import ARMS
from spireshift.native_a8_boss_session import qualify
from spireshift.native_a8_rescue_game import TRACE, decisions, public_state
from spireshift.native_a8_rescue_policy import subject
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_win4_game import write
from spireshift.native_win_teacher import card_stats

ATTEMPT = 1794069727755831000
ANCHORS = {
    "boss-v2-002": {471, 479, 485},
    "boss-v2-003": {515, 557, 561, 569, 577},
    "boss-v2-005": {435, 443, 447},
    "boss-v2-006": {261, 263, 265, 267},
}


def combat_sample(
    line: int,
    frame: dict[str, Any],
    action: dict[str, Any],
    floor: int,
    player: dict[str, Any],
    combat: dict[str, Any],
) -> dict[str, Any]:
    offers = []
    for item in frame["public_input"]["candidates"]:
        if item["verb"] not in {"play", "use", "end_turn"}:
            continue
        _, props = subject(item)
        offers.append(
            {
                "label": item["label"],
                "slot": (props.get("entity_id") or {}).get("public_slot"),
                "cost": props.get("cost"),
                "stats": card_stats(props),
            }
        )
    return {
        "line": line,
        "input_digest": frame["input_digest"],
        "floor": floor,
        "round": combat["round"],
        "player_hp": player["hp"],
        "block": combat["player"]["block"],
        "energy": combat["player"]["energy"],
        "enemies": [
            {k: enemy[k] for k in ("definition_id", "hp", "max_hp", "block", "intents", "statuses")}
            for enemy in combat["enemies"]
        ],
        "encounter": combat["encounter_type"],
        "held_potions": len(player["potions"]),
        "action": action["label"],
        "legal_moves": offers,
    }


def summary(path: Path, anchors: set[int]) -> dict[str, Any]:
    entry = last = route = None
    samples = []
    reopen_count = 0
    for line, frame, delivered in decisions(path):
        run, player, interaction = public_state(frame)
        if delivered is None:
            if (
                frame["ending"]["victory"] is not False
                or not frame["terminal"]
                or player["hp"] != 0
            ):
                raise ValueError("Require a genuine terminal Act 1 loss")
            if {sample["line"] for sample in samples} != anchors or last is None:
                raise ValueError("Missing a saved diagnostic combat menu")
            return {
                "final_floor": run["floor"],
                "boss_entry": entry,
                "last_combat": last,
                "last_map_choice": route,
                "reopened_declined_card_rewards": reopen_count,
                "diagnostic_menus": samples,
            }
        menu = frame["public_input"]["candidates"]
        action = menu[delivered["choice"]["action_index"]]
        if action["history"]["card_reward_declined"]:
            reopen_count += 1
        if interaction["kind"] == "map_navigation" and subject(action)[1].get("point_type"):
            route = {
                "floor": run["floor"],
                "hp": player["hp"],
                "chosen": subject(action)[1]["point_type"],
                "offered": [
                    subject(item)[1].get("point_type")
                    for item in menu
                    if subject(item)[1].get("point_type")
                ],
            }
        combat = interaction["content"].get("context", {})
        if interaction["kind"] != "combat_turn":
            continue
        last = {
            "floor": run["floor"],
            "round": combat["round"],
            "encounter": combat["encounter_type"],
            "hp": player["hp"],
            "block": combat["player"]["block"],
            "action": action["label"],
            "enemies": [
                {"definition_id": e["definition_id"], "hp": e["hp"], "max_hp": e["max_hp"]}
                for e in combat["enemies"]
            ],
        }
        if entry is None and combat["encounter_type"] == "boss":
            entry = {
                "hp": player["hp"],
                "enemies": last["enemies"],
                "potions": len(player["potions"]),
            }
        if line in anchors:
            samples.append(combat_sample(line, frame, action, run["floor"], player, combat))
    raise ValueError("Missing a final observation")


def audit(root: Path, ctx: dict[str, Any], out: Path, deadline: float) -> dict[str, Any]:
    cfg = ctx["reward_config"]
    store = ChunkJournal(root, cfg)
    attempt = identified(store.workspace / f"attempt-{ATTEMPT}.json")
    launch = identified(store.workspace / f"launch-{ATTEMPT}.json")
    resource = identified(root / f"artifacts/resources/a8-act1-boss-v2-{ATTEMPT}.json")
    checks = freeze(root, ctx)
    if (
        attempt["launch_id"] != launch["report_id"]
        or attempt["config_id"] != ctx["reward_config_id"]
        or attempt["execution_id"] != ctx["execution_id"]
        or attempt["status"] != "act1_boss_teacher_qualification_blocked"
        or attempt["stop"] is not None
        or attempt["optimizer_updates"] != 0
        or attempt["lessons_admitted"] != 0
        or not attempt["shared_profile_unchanged"]
        or attempt["frozen_checks"] != checks
        or launch["frozen_checks"] != checks
        or resource["exit_code"] != 2
        or resource["cap"] is not None
    ):
        raise ValueError("Expected the exact completed qualification and frozen inputs")

    rows, seals, games = [], {}, {}
    deliveries = 0
    for case in cfg["worlds"]:
        key = case["key"]
        seal = store.completed(key, case)
        if seal is None:
            raise ValueError("Missing a sealed world in the completed panel")
        row = seal["result"]
        world = store.path(key)
        rows.append(row)
        seals[key] = seal["report_id"]
        games[key] = {}
        if set(row["episodes"]) != set(ARMS) or row[
            "first_different_teacher_action"
        ] != compare_teachers(world):
            raise ValueError("Matched arms or first same-menu teacher change differs")
        for arm, episode in row["episodes"].items():
            old = world / arm
            target = out / "replay" / key / arm
            target.mkdir(parents=True)
            (target / TRACE).symlink_to(old / TRACE)
            (target / "worker").symlink_to(old / "worker", target_is_directory=True)
            raw = verify(ctx, case, arm, target, deadline)
            if (
                any(episode.get(k) != value for k, value in raw.items())
                or episode["outcome"] != "act1_loss"
                or episode["cap"]
                or not episode["native_ending"]["native_ending_evidence_agrees"]
                or not episode["shutdown"]["clean_exit"]
            ):
                raise ValueError("Saved loss, receipts or shutdown differ from the seal")
            deliveries += raw["verified_native_deliveries"]
            samples = ANCHORS.get(key, set()) if arm == "boss" else set()
            games[key][arm] = summary(old / TRACE, samples)

    result = qualify(len(cfg["worlds"]), cfg["gate"], rows)
    if (
        result != attempt["qualification"]
        or {path.name for path in (store.workspace / "chunks").iterdir()} != set(seals)
        or freeze(root, ctx) != checks
    ):
        raise ValueError("Matched results or frozen inputs changed")
    boss = [world["boss"] for world in games.values()]
    return write(
        out / "report.json",
        {
            "schema_version": "native-a8-act1-boss-v2-saved-audit-v1",
            "status": "complete_boss_qualification_losses_verified",
            "owner_attempt_id": attempt["report_id"],
            "owner_resource_id": resource["report_id"],
            "config_id": ctx["reward_config_id"],
            "execution_id": ctx["execution_id"],
            "frozen_checks": checks,
            "seals": seals,
            "qualification": result,
            "verified_episodes": sum(len(arms) for arms in games.values()),
            "verified_native_deliveries": deliveries,
            "boss_teacher_fatal_encounters": dict(
                Counter(g["last_combat"]["encounter"] for g in boss)
            ),
            "boss_teacher_reopened_declined_rewards": sum(
                g["reopened_declined_card_rewards"] for g in boss
            ),
            "games": games,
            "new_games": 0,
            "optimizer_updates": 0,
            "lessons_admitted": 0,
            "automatic_follow_up": False,
        },
    )


if __name__ == "__main__":
    root = Path.cwd()
    cfg = declaration(root)
    context = load(root, cfg)
    receipts = short_check(root, context)
    if receipts is None:
        raise ValueError("Missing the exact saved short check")
    context["reward_short_receipts"] = receipts
    out = root / AREA / "study-v2-saved-audit-v1"
    with (root / cfg["workspace"] / "session.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        out.mkdir(parents=True, exist_ok=False)
        report = audit(root, context, out, time.monotonic() + 230)
    print(
        json.dumps(
            {
                k: report[k]
                for k in ("status", "verified_episodes", "verified_native_deliveries", "report_id")
            }
        )
    )
