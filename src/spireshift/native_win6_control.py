"""Exercise Trial's native presentation boundary and verdict effects on fresh fixtures."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from spireshift.engine_choice_fixture_worker_v4 import SCRIPT, FixtureWorker
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games
from spireshift.engine_qualification import _sha_file
from spireshift.engine_worker import worker_helpers
from spireshift.native_flow_live_v12 import append
from spireshift.native_shared_transport import JsonLines
from spireshift.native_win3_control import scripted_verification
from spireshift.native_win4_game import write
from spireshift.native_win5_inputs import frozen_checks, load
from spireshift.native_win6_build import WORKSPACE
from spireshift.native_win6_inputs import support_context

ENTRANTS = {"2 random Relics": "merchant", "Heal 10 HP": "noble", "2 card rewards": "nondescript"}
VERDICTS = {"guilty": "DECIDE: Guilty", "innocent": "DECIDE: Innocent"}
CURSES = {
    ("merchant", "guilty"): "REGRET",
    ("merchant", "innocent"): "SHAME",
    ("noble", "innocent"): "REGRET",
    ("nondescript", "guilty"): "DOUBT",
    ("nondescript", "innocent"): "DOUBT",
}
CONVERTER = "scripts/engine-shared-input-v16.mjs"


def card_key(card: dict[str, Any]) -> tuple[str, bool]:
    return str(card["definition_id"]), bool(card["is_upgraded"])


def player_facts(frame: dict[str, Any]) -> dict[str, Any]:
    context = frame["public_input"]["context"]
    player = context["persistent"]["player"]
    return {
        "hp": player["hp"],
        "gold": player["gold"],
        "max_hp": player["max_hp"],
        "relics": Counter(row["definition_id"] for row in player["relics"]),
        "deck": Counter(
            card_key(card)
            for read in context["reads"]
            if read["kind"] == "run_deck"
            for card in read["content"]["cards"]
        ),
    }


def check_effect(
    entrant: str,
    verdict: str,
    before: dict[str, Any],
    after: dict[str, Any],
    selected: list[tuple[str, bool]],
    rewards: list[tuple[str, bool]],
) -> None:
    expected = before["deck"].copy()
    curse = CURSES.get((entrant, verdict))
    if curse:
        expected[curse, False] += 1
    if entrant == "merchant" and verdict == "guilty":
        if (
            sum((after["relics"] - before["relics"]).values()) != 2
            or before["relics"] - after["relics"]
        ):
            raise ValueError("Trial did not award two additional relics")
    elif entrant == "merchant" and verdict == "innocent":
        if len(selected) != 2 or any(upgraded for _, upgraded in selected):
            raise ValueError("Trial did not complete the required two-card upgrade selection")
        expected.subtract(selected)
        expected.update((definition, True) for definition, _ in selected)
    elif entrant == "noble":
        hp_gain, gold_gain = (10, 0) if verdict == "guilty" else (0, 300)
        if (after["hp"], after["gold"]) != (before["hp"] + hp_gain, before["gold"] + gold_gain):
            raise ValueError("Trial did not apply the native healing or gold effect")
    elif verdict == "guilty":
        if len(rewards) != 2:
            raise ValueError("Trial did not deliver two claimed card rewards")
        expected.update(rewards)
    else:
        if len(selected) != 2 or expected - after["deck"] != Counter(selected):
            raise ValueError("Trial did not remove both selected cards for transformation")
        expected.subtract(selected)
        replacements = after["deck"] - expected
        if sum(replacements.values()) != 2:
            raise ValueError("Trial did not add two transformed cards")
        expected.update(replacements)
    if +expected != after["deck"]:
        raise ValueError("Trial deck effects differ from the native verdict")


def fixture(
    ctx: dict[str, Any],
    out: Path,
    seed: str,
    reject_first: bool,
    covered: set[str],
    deadline: float,
) -> dict[str, Any]:
    root = ctx["qualification"].root
    out.mkdir()
    native = FixtureWorker(
        ctx["qualification"],
        ctx["native"],
        out / "worker",
        Path(ctx["node"]),
        worker_helpers(root, SCRIPT),
    )
    converter = JsonLines(root, [ctx["node"], str(root / CONVERTER)], out / "converter.log")
    trace = out / "scripted-public.jsonl.gz"
    frame: dict[str, Any] = {}
    delivered = 0

    def take(match: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
        nonlocal frame, delivered
        candidates = frame["public_input"]["candidates"]
        index = next((i for i, candidate in enumerate(candidates) if match(candidate)), None)
        if index is None:
            raise ValueError("Required Trial action missing from the public menu")
        action = frame["actions"][index]
        choice = {
            "action_index": index,
            "binding_id": frame["binding_id"],
            "bound_action_id": action["bound_action_id"],
        }
        append(trace, {"kind": "policy_input", "frame": frame})
        successor = native.request(
            "step",
            snapshot_id=frame["observation"]["snapshot_id"],
            action_index=action["raw_index"],
            timeout=min(20, max(0.1, deadline - time.monotonic())),
        )
        receipt = {
            "binding_id": frame["binding_id"],
            "delivery": "delivered",
            "bound_action_id": action["bound_action_id"],
            "runtime_instance_id": frame["observation"]["runtime_instance_id"],
            "before_snapshot_id": frame["observation"]["snapshot_id"],
            "successor_snapshot_id": successor["snapshot"]["snapshot_id"],
        }
        converter.commit(choice, receipt, deadline)
        append(trace, {"kind": "policy_choice", "choice": choice, "receipt": receipt})
        delivered += 1
        frame = converter.project(successor["snapshot"], successor["reads"], None, deadline)
        return dict(candidates[index])

    def interaction() -> dict[str, Any]:
        return dict(frame["public_input"]["context"]["interaction"])

    def options(*titles: str) -> list[dict[str, Any]]:
        current = interaction()
        event = current["content"]
        rows = event["surface"].get("options", [])
        if (
            current["kind"] != "event_option"
            or event["context"]["event_id"] != "TRIAL"
            or [row["title"] for row in rows] != list(titles)
            or not all(row["is_enabled"] and not row["is_locked"] for row in rows)
        ):
            raise ValueError("Unexpected native Trial event menu")
        return list(rows)

    def activate(title: str) -> None:
        take(lambda candidate: candidate["verb"] == "activate" and candidate["label"] == title)

    try:
        native.request("mount", seed=seed)
        state = native.request("potion_fixture", room="event", event="TRIAL", potions=[])
        frame = converter.project(state["snapshot"], state["reads"], None, deadline)
        options("Accept", "Reject")
        before = player_facts(frame)
        if reject_first:
            activate("Reject")
            if options("Accept", "Double Down")[1]["will_kill_player"] is not True:
                raise ValueError("Trial Reject must retain the advertised lethal option")
        activate("Accept")
        choices = options(*VERDICTS.values())
        entrants = [
            name for marker, name in ENTRANTS.items() if marker in choices[0]["description"]
        ]
        if len(entrants) != 1 or player_facts(frame) != before:
            raise ValueError("Trial Accept did not settle at the native verdict menu")
        entrant = entrants[0]
        verdict = "guilty" if f"{entrant}/guilty" not in covered else "innocent"
        activate(VERDICTS[verdict])

        selected: list[tuple[str, bool]] = []
        rewards: list[tuple[str, bool]] = []
        claims = 0
        for _ in range(7):
            kind = interaction()["kind"]
            if kind == "event_option":
                break
            if kind == "card_selection" and not selected and verdict == "innocent":
                surface = interaction()["content"]["surface"]
                if (surface["min_select"], surface["max_select"]) != (2, 2):
                    raise ValueError("Trial must ask for exactly two cards")
                action = take(
                    lambda candidate: (
                        candidate["verb"] == "confirm" and len(candidate["arguments"]) == 2
                    )
                )
                selected = [
                    card_key(argument["entity"]["properties"]) for argument in action["arguments"]
                ]
            elif entrant == "nondescript" and verdict == "guilty":
                if kind == "reward_claim" and claims < 2:
                    take(
                        lambda candidate: (
                            candidate["verb"] == "activate"
                            and (candidate["subject"] or {}).get("role") == "reward"
                        )
                    )
                    claims += 1
                elif kind == "card_reward_selection" and len(rewards) < 2:
                    action = take(
                        lambda candidate: (
                            candidate["verb"] == "select"
                            and (candidate["subject"] or {}).get("role") == "card"
                        )
                    )
                    rewards.append(card_key(action["subject"]["properties"]))
                elif kind in {"reward_claim", "reward_completion"} and len(rewards) == claims == 2:
                    activate("Continue from rewards")
                else:
                    raise ValueError("Unexpected Trial reward owner")
            else:
                raise ValueError(f"Unexpected Trial verdict successor {kind}")
        else:
            raise ValueError("Trial verdict exceeded the diagnostic action bound")
        if options("Proceed")[0]["is_proceed"] is not True:
            raise ValueError("Trial verdict did not reach native event completion")
        after = player_facts(frame)
        check_effect(entrant, verdict, before, after, selected, rewards)
        activate("Proceed")
        if interaction()["kind"] != "map_navigation" or player_facts(frame) != after:
            raise ValueError("Trial Proceed must preserve verdict effects and reach the map")
        append(trace, {"kind": "final_observation", "frame": frame})
        shutdown = native.close()
        converter.close()
    finally:
        converter.stop()
        native.stop()
    if (
        not shutdown["clean_exit"]
        or shutdown["runtime_errors"]
        or scripted_verification(ctx, out, deadline) != delivered
    ):
        raise ValueError("Trial public receipts or clean shutdown failed verification")
    return {
        "seed": seed,
        "entrant": entrant,
        "verdict": verdict,
        "reject_first": reject_first,
        "delivered_actions": delivered,
        "chosen_cards": selected,
        "claimed_reward_cards": rewards,
        "native_effect_verified": True,
        "native_proceed_to_map_verified": True,
    }


def control(root: Path, out: Path, generation: int) -> dict[str, Any]:
    if _running_games():
        raise ValueError("Close STS2 before running the isolated Trial controls")
    deadline = time.monotonic() + 265
    build = identified(root / WORKSPACE / "report.json")
    ctx = support_context(root, load(root), build)
    before = frozen_checks(ctx)
    out.mkdir(parents=True, exist_ok=False)
    wanted = {f"{entrant}/{verdict}" for entrant in ENTRANTS.values() for verdict in VERDICTS}
    covered: set[str] = set()
    rows = []
    for index in range(1, 25):
        seed = f"SP1RESH1FTW6TRIALG{generation}P{index:02d}"
        row = fixture(ctx, out / f"case-{index:02d}", seed, index == 1, covered, deadline)
        rows.append(row)
        covered.add(f"{row['entrant']}/{row['verdict']}")
        print(f"Trial control {index}: {row['entrant']}/{row['verdict']} verified", flush=True)
        if covered == wanted:
            break
    after = frozen_checks(ctx)
    if covered != wanted or not all(before.values()) or not all(after.values()):
        raise ValueError("Trial control did not verify every verdict against the frozen inputs")
    sources = [
        "src/spireshift/native_win6_control.py",
        "src/spireshift/native_win6_inputs.py",
        "src/spireshift/engine_choice_fixture_worker_v4.py",
        "src/spireshift/native_win3_control.py",
        CONVERTER,
        *(f"scripts/{name}" for name in worker_helpers(root, SCRIPT)),
    ]
    return write(
        out / "report.json",
        {
            "schema_version": "native-trial-verdict-control-v1",
            "status": "trial_accept_and_verdicts_verified",
            "support_build_id": build["report_id"],
            "environment_id": ctx["environment"]["manifest_id"],
            "verified_verdicts": sorted(covered),
            "cases": rows,
            "checks": {
                "reject_then_accept": rows[0]["reject_first"],
                "native_effects_and_proceed": all(
                    row["native_proceed_to_map_verified"] for row in rows
                ),
                "public_inputs_and_deliveries_reconstructed": True,
                "clean_shutdown": True,
            },
            "checks_before": before,
            "checks_after": after,
            "sources": {name: _sha_file(root / name) for name in sources},
            "evidence": {
                str(path.relative_to(root)): _sha_file(path)
                for path in out.rglob("*")
                if path.is_file()
            },
            "optimizer_updates": 0,
            "training_labels_allowed": False,
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--generation", type=int, required=True)
    args = parser.parse_args()
    result = control(Path.cwd(), args.output.resolve(), args.generation)
    print(json.dumps({k: result[k] for k in ("status", "report_id", "verified_verdicts")}))
