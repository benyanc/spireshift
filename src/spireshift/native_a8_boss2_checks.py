"""Reconstruct the saved reward loops and verify real decline-to-map transitions."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_boss2_game import play
from spireshift.native_a8_boss2_inputs import CONTROL_DELIVERIES, CONTROL_WORLDS, freeze
from spireshift.native_a8_boss2_policy import CONTINUE, DIAGNOSTIC_DECLINE, declined, intervention
from spireshift.native_a8_boss_checks import SHARED_PROFILE, saved_checks
from spireshift.native_a8_boss_policy import intervention as previous_intervention
from spireshift.native_a8_boss_session import qualify
from spireshift.native_a8_rescue_game import TRACE, decisions, public_state
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_win4_game import write


def saved_reward_loops(root: Path, ctx: dict[str, Any]) -> dict[str, Any]:
    previous = ctx["boss_config"]
    store = ChunkJournal(root, previous)
    rows, loops = [], []
    for case in previous["worlds"]:
        key = case["key"]
        seal = store.completed(key, case)
        if seal is None:
            raise ValueError("Missing sealed v1 qualification world")
        row = seal["result"]
        rows.append(row)
        if row["outcomes"]["boss"] != "capped":
            continue
        count: Counter[str] = Counter()
        first = None
        after_reopen = False
        for line, frame, delivered in decisions(store.path(key) / "boss" / TRACE):
            if delivered is None:
                if after_reopen:
                    raise ValueError("Saved reward cycle lacks its Skip delivery")
                break
            public = frame["public_input"]
            menu = public["candidates"]
            choice = delivered["choice"]
            index = choice["action_index"]
            if after_reopen and (
                frame["source_family"] != "card_reward_selection" or menu[index]["label"] != "Skip"
            ):
                raise ValueError("The saved repeat no longer returns to the same decline cycle")
            after_reopen = frame["source_family"] == "reward_claim" and declined(menu[index])
            if not after_reopen:
                continue
            count["teacher_override" if choice.get("intervention") else "inherited"] += 1
            if first is not None:
                continue
            exit_index = next(i for i, action in enumerate(menu) if action["label"] in CONTINUE)
            indices = list(range(len(menu)))
            if (
                previous_intervention(public, indices, exit_index)[0] != index
                or previous_intervention(public, indices, index)[0] != index
                or intervention(public, indices, exit_index)[0] != exit_index
                or intervention(public, indices, index)[0] != exit_index
            ):
                raise ValueError("Both saved ways to reopen the declined offer must be repaired")
            first = {"line": line, "menu": frame["input_digest"], "delivered": menu[index]["label"]}
        if first is None:
            raise ValueError("The capped v1 episode lacks its saved decline loop")
        loops.append(
            {
                "world": key,
                "seal_id": seal["report_id"],
                "cap": row["episodes"]["boss"]["cap"],
                "floor": row["episodes"]["boss"]["final_floor"],
                "first": first,
                "reopens": dict(count),
            }
        )
    if (
        len(loops) != 7
        or qualify(len(rows), previous["gate"], rows) != ctx["failed_boss_attempt"]["qualification"]
    ):
        raise ValueError("The v1 qualification denominator differs")
    return {
        "capped_reward_loops": len(loops),
        "cap_counts": dict(Counter(reason for loop in loops for reason in loop["cap"])),
        "reopen_actions": sum(sum(loop["reopens"].values()) for loop in loops),
        "loops": loops,
        **saved_checks(root, ctx),
    }


def decline_exit(trace: Path) -> dict[str, Any]:
    skip = None
    declined_menu = None
    leave = None
    for line, frame, delivered in decisions(trace):
        run, _, interaction = public_state(frame)
        public = frame["public_input"]
        family = interaction["kind"]
        if skip is not None and declined_menu is None:
            if family != "reward_claim" or not any(
                declined(action) for action in public["candidates"]
            ):
                raise ValueError("The actual Skip must expose the same declined reward")
            declined_menu = frame["input_digest"]
        if leave is not None:
            if family != "map_navigation":
                raise ValueError("The delivered reward exit must open the actual native map")
            return {
                "skip": skip,
                "declined_menu": declined_menu,
                "exit": leave,
                "native_map": frame["input_digest"],
            }
        if delivered is None:
            break
        choice = delivered["choice"]
        action = public["candidates"][choice["action_index"]]
        if choice.get("intervention") == DIAGNOSTIC_DECLINE:
            if skip is not None or family != "card_reward_selection" or action["label"] != "Skip":
                raise ValueError("Only the first legal card reward Skip is scripted")
            skip = {
                "line": line,
                "floor": run["floor"],
                "receipt": delivered["receipt"]["delivery"],
            }
        if declined_menu is not None and declined(action):
            raise ValueError("The live control reopened its declined reward")
        if declined_menu is not None and family == "reward_claim" and action["label"] in CONTINUE:
            leave = {"line": line, "label": action["label"], "floor": run["floor"]}
    raise ValueError("The short native prefix did not verify an actual decline-to-map lifecycle")


def control(root: Path, ctx: dict[str, Any], deadline: float) -> dict[str, Any]:
    out = root / ctx["reward_config"]["control_workspace"]
    out.mkdir(parents=True, exist_ok=False)
    shared = Path.home() / SHARED_PROFILE
    before, profile = freeze(root, ctx), _shared_snapshot(shared)
    saved = saved_reward_loops(root, ctx)
    episodes, exits = {}, {}
    for case in CONTROL_WORLDS:
        key = case["key"]
        target = out / key
        episode = play(ctx, case, "decline_probe", target, deadline, choices=CONTROL_DELIVERIES)
        if (
            episode["cap"] not in ([], ["choices"])
            or episode["native_interventions"].get(DIAGNOSTIC_DECLINE) != 1
            or not episode["shutdown"]["clean_exit"]
        ):
            raise ValueError("The diagnostic normal start did not finish a clean short prefix")
        episodes[key] = episode
        exits[key] = decline_exit(target / TRACE)
    if freeze(root, ctx) != before or _shared_snapshot(shared) != profile or _running_games():
        raise ValueError("Frozen inputs, worker exit or shared profile differs after the control")
    return write(
        out / "report.json",
        {
            "schema_version": "native-a8-act1-boss-reward-lifecycle-short-check-v1",
            "status": "act1_boss_reward_lifecycle_short_check_verified",
            "config_id": ctx["reward_config_id"],
            "execution_id": ctx["execution_id"],
            "controls": CONTROL_WORLDS,
            "saved": saved,
            "episodes": episodes,
            "decline_exit_transitions": exits,
            "verified_decline_exits": len(exits),
            "verified_deliveries": sum(
                row["verified_native_deliveries"] for row in episodes.values()
            ),
            "frozen_checks": before,
            "shared_profile_unchanged": True,
            "qualification_games": 0,
            "optimizer_updates": 0,
            "evidence": {
                str(file.relative_to(root)): _sha_file(file)
                for file in sorted(out.rglob("*"))
                if file.is_file() and not file.is_symlink()
            },
        },
    )
