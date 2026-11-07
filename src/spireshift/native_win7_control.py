"""Exercise the repaired Soul Nexus kill and the separate Soul Fysh preparation."""

from __future__ import annotations

import argparse
import json
import time
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games
from spireshift.engine_qualification import _sha_file
from spireshift.native_flow_live_v12 import append
from spireshift.native_flow_verification_v12 import records
from spireshift.native_shared_transport import JsonLines
from spireshift.native_win3_control import scripted_verification
from spireshift.native_win4_game import episode, prepare, worker, write
from spireshift.native_win6_inputs import frozen_checks, load
from spireshift.native_win7_build import WORKSPACE
from spireshift.native_win7_inputs import soul_fysh_case, support_context
from spireshift.native_win7_recovery import CONVERTER


def action_index(frame: dict[str, Any], hp: int, block: int) -> int:
    """Keep the last hit on the exact weapon that faulted in the owner run."""
    priorities = ["BLOCK_POTION", "BARRICADE"]
    if hp <= 32:
        priorities.append("BLUDGEON")
    if block < 150:
        priorities.append("ENTRENCH")
    if block < hp:
        priorities.append("BODY_SLAM")
    if hp > 32:
        priorities.append("BLUDGEON")
    priorities.append("end_turn")
    ranked = []
    for index, action in enumerate(frame["public_input"]["candidates"]):
        definition = ((action["subject"] or {}).get("properties") or {}).get("definition_id")
        intent = action["verb"] if action["verb"] == "end_turn" else definition
        if action["verb"] not in {"play", "use", "end_turn"} or intent not in priorities:
            continue
        ranked.append((priorities.index(intent), index))
    if not ranked:
        raise ValueError("No native action for the Soul Nexus diagnostic")
    return min(ranked)[1]


def nexus(ctx: dict[str, Any], out: Path, seed: str, deadline: float) -> dict[str, Any]:
    root = ctx["qualification"].root
    out.mkdir()
    trace = out / "scripted-public.jsonl.gz"
    last_card = None
    with ExitStack() as cleanup:
        native = worker(ctx, out / "worker")
        cleanup.callback(native.stop)
        converter = JsonLines(root, [ctx["node"], str(root / CONVERTER)], out / "converter.log")
        cleanup.callback(converter.stop)
        current = native.request(
            "diagnostic_combat",
            seed=seed,
            diagnostic_only=True,
            encounter="SOUL_NEXUS_ELITE",
            deck=["BARRICADE", "ENTRENCH", "ENTRENCH", "BODY_SLAM", "BLUDGEON"],
            relics=["ANCHOR", "PHILOSOPHERS_STONE", "LANTERN"],
            potions=["BLOCK_POTION", "BLOCK_POTION"],
            timeout=25,
        )
        for delivered in range(60):
            frame = converter.project(current["snapshot"], current["reads"], None, deadline)
            interaction = frame["public_input"]["context"]["interaction"]
            if interaction["kind"] == "reward_claim":
                rewards = interaction["content"]["surface"]["rewards"]
                if (
                    delivered == 0
                    or last_card != "BLUDGEON"
                    or not any(row["kind"] == "relic" for row in rewards)
                ):
                    raise ValueError(
                        "Nexus did not settle into native elite rewards after Bludgeon"
                    )
                append(trace, {"kind": "final_observation", "frame": frame})
                break
            combat = interaction["content"]["context"]
            enemies = combat.get("enemies", [])
            if (
                interaction["kind"] != "combat_turn"
                or combat.get("encounter_type") != "elite"
                or [enemy["definition_id"] for enemy in enemies] != ["SOUL_NEXUS"]
                or (delivered == 0 and (enemies[0]["hp"], enemies[0]["max_hp"]) != (254, 254))
            ):
                raise ValueError("Expected the genuine A8 Soul Nexus elite owner")
            index = action_index(frame, enemies[0]["hp"], combat["player"]["block"])
            binding = frame["actions"][index]
            candidate = frame["public_input"]["candidates"][index]
            last_card = ((candidate["subject"] or {}).get("properties") or {}).get("definition_id")
            if last_card == "BLUDGEON" and [
                arg["entity"]["properties"]["definition_id"]
                for arg in candidate["arguments"]
                if arg["role"] == "target"
            ] != ["SOUL_NEXUS"]:
                raise ValueError("Bludgeon must target the actual Soul Nexus")
            choice = {
                "action_index": index,
                "binding_id": frame["binding_id"],
                "bound_action_id": binding["bound_action_id"],
            }
            append(trace, {"kind": "policy_input", "frame": frame})
            successor = native.request(
                "step",
                snapshot_id=frame["observation"]["snapshot_id"],
                action_index=binding["raw_index"],
                timeout=18,
            )
            if successor["delivery_domain"] != "native":
                raise ValueError("Nexus control requires actual native gameplay")
            receipt = {
                "binding_id": frame["binding_id"],
                "delivery": "delivered",
                "delivery_domain": "native",
                "bound_action_id": binding["bound_action_id"],
                "runtime_instance_id": frame["observation"]["runtime_instance_id"],
                "before_snapshot_id": frame["observation"]["snapshot_id"],
                "successor_snapshot_id": successor["snapshot"]["snapshot_id"],
            }
            converter.commit(choice, receipt, deadline)
            append(trace, {"kind": "policy_choice", "choice": choice, "receipt": receipt})
            current = successor
        else:
            raise ValueError("Nexus control exceeded its action bound")
        shutdown = native.close()
        converter.close()
    domain = list(records(out / "worker/answer-plan-deliveries.jsonl.gz"))
    if (
        not shutdown["clean_exit"]
        or shutdown["runtime_errors"]
        or scripted_verification(ctx, out, deadline) != delivered
        or len(domain) != delivered
        or any(row["delivery_domain"] != "native" for row in domain)
    ):
        raise ValueError("Nexus control did not reconstruct the clean native deliveries")
    return {
        "seed": seed,
        "lethal_card": last_card,
        "initial_nexus_hp": 254,
        "native_elite_rewards": True,
        "native_deliveries": delivered,
        "clean_shutdown": True,
    }


def control(root: Path, out: Path, generation: int) -> dict[str, Any]:
    if _running_games():
        raise ValueError("Close STS2 before the isolated combat controls")
    deadline = time.monotonic() + 265
    build = identified(root / WORKSPACE / "report.json")
    ctx = support_context(root, load(root), build)
    before = frozen_checks(ctx)
    out.mkdir(parents=True, exist_ok=False)
    seed = f"SP1RESH1FTW7NXCHK{generation}P01"
    elite = nexus(ctx, out / "nexus", seed, deadline)
    print(
        f"Soul Nexus verified through elite rewards after {elite['native_deliveries']} actions",
        flush=True,
    )

    # Same declared preparation and teacher as the proposed supplement, on a
    # separate diagnostic seed pool which can never enter fitting or evaluation.
    seeds = [f"SP1RESH1FTW7SFCHK{generation}P{i:02d}" for i in range(1, 9)]
    case = {
        **soul_fysh_case(ctx["config"]),
        "key": "soul-fysh-diagnostic",
        "partition": "control_fit",
        "seed_pool": seeds,
    }
    setup = out / "soul-fysh-setup"
    setup.mkdir()
    start = prepare(ctx, case, setup, deadline)
    if start["status"] != "ready":
        raise ValueError("Soul Fysh diagnostic setup unavailable")
    fight = out / "soul-fysh-fight"
    fight.mkdir()
    result = episode(ctx, start, "defensive", fight, deadline)
    if (
        result["status"] != "complete"
        or not result["curriculum_success"]
        or not result["actual_boss_combat_observed"]
        or result["native_terminal"]
        or result["full_run_win"]
        or result["optimizer_updates"] != 0
    ):
        raise ValueError("The proposed teaching setup did not complete the native Soul Fysh act")
    after = frozen_checks(ctx)
    if not all(before.values()) or not all(after.values()):
        raise ValueError("Frozen inputs changed during controls")
    return write(
        out / "report.json",
        {
            "schema_version": "native-curriculum-nexus-fysh-control-v1",
            "status": "nexus_death_and_soul_fysh_setup_verified",
            "support_build_id": build["report_id"],
            "environment_id": ctx["environment"]["manifest_id"],
            "nexus": elite,
            "soul_fysh": result,
            "diagnostic_seed_pools": [seed, *seeds],
            "checks": {
                "nexus_native_lethal_hit_and_elite_rewards": True,
                "soul_fysh_native_boss_and_next_act": True,
                "independent_public_reconstruction_and_shutdown": True,
            },
            "checks_before": before,
            "checks_after": after,
            "sources": {
                **ctx["sources"],
                **{
                    name: _sha_file(root / name)
                    for name in [
                        "src/spireshift/native_win7_control.py",
                        "src/spireshift/native_win7_inputs.py",
                    ]
                },
            },
            "evidence": {
                str(path.relative_to(root)): _sha_file(path)
                for path in out.rglob("*")
                if path.is_file()
            },
            "training_labels_allowed": False,
            "optimizer_updates": 0,
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--generation", type=int, required=True)
    args = parser.parse_args()
    result = control(Path.cwd(), args.output.resolve(), args.generation)
    print(json.dumps({k: result[k] for k in ("status", "report_id", "checks")}))
