"""Exercise native Test Subject revivals and Intangible with actual card actions."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_flow_live_v12 import append
from spireshift.native_flow_verification_v12 import records
from spireshift.native_shared_transport import JsonLines
from spireshift.native_win3_control import scripted_verification
from spireshift.native_win4_game import check_start, prepare, terminal, worker, write
from spireshift.native_win4_inputs import RECIPE, frozen_checks, load
from spireshift.native_win5_build import WORKSPACE
from spireshift.native_win5_inputs import support_context

CONTROL = "artifacts/native-win-curriculum/revival-control-v1"


def fixture_case(generation: int) -> dict[str, Any]:
    deck = ["BARRICADE", "ENTRENCH", "ENTRENCH", "BODY_SLAM", "BODY_SLAM"]
    return {
        "key": "test-subject-revival-control",
        "partition": "control_fit",
        "player": 2,
        "entry": "boss",
        "act": 3,
        "act_definition": "GLORY",
        "boss": "TEST_SUBJECT_BOSS",
        "seed_pool": [f"SP1RESH1FTW5REV{generation}P{i:02d}" for i in range(1, 9)],
        "profile": {
            "deck": deck,
            "hp": 80,
            "max_hp": 80,
            "gold": 0,
            "relics": ["BURNING_BLOOD", "ANCHOR", "PHILOSOPHERS_STONE", "LANTERN"],
            "potions": ["BLOCK_POTION", "BLOCK_POTION"],
            "upgrades": len(deck),
            "upgrade_priority": deck,
        },
    }


def fight(ctx: dict[str, Any], start: dict[str, Any], out: Path, deadline: float) -> dict[str, Any]:
    root = ctx["qualification"].root
    native = worker(ctx, out / "worker")
    converter = JsonLines(
        root,
        [ctx["node"], str(root / "scripts/engine-shared-input-v16.mjs")],
        out / "converter.log",
    )
    trace = out / "scripted-public.jsonl.gz"
    forms: list[int] = []
    rounds: list[int] = []
    intangible_seen = False
    intangible_expired = False
    form_three_turn = False
    try:
        current = native.request(
            "load",
            seed=start["seed"],
            save_json=(root / start["save_path"]).read_text(),
            timeout=25,
        )
        for index in range(75):
            frame = converter.project(current["snapshot"], current["reads"], None, deadline)
            if index == 0:
                check_start(frame, start)
            ended, success = terminal(frame, start)
            public = frame["public_input"]
            interaction = public["context"]["interaction"]
            if ended:
                if not success or interaction["kind"] != "reward_claim":
                    raise ValueError("The diagnostic boss fight did not reach native rewards")
                append(trace, {"kind": "final_observation", "frame": frame})
                break
            combat = interaction["content"]["context"]
            if interaction["kind"] != "combat_turn":
                raise ValueError("Unexpected interaction during the Test Subject control")
            enemies = combat["enemies"]
            subject = next(
                (enemy for enemy in enemies if enemy["definition_id"] == "TEST_SUBJECT"), None
            )
            hp = subject["max_hp"] if subject else None
            powers = (
                {power["definition_id"]: power["amount"] for power in subject["statuses"]}
                if subject
                else {}
            )
            round_number = combat["round"]
            if subject is not None and hp is not None and (not forms or hp != forms[-1]):
                forms.append(hp)
                rounds.append(round_number)
                if subject["hp"] != hp:
                    raise ValueError("The native revived form should begin at full health")
            intangible = powers.get("INTANGIBLE_POWER", 0)
            if hp == 313:
                if intangible == 1:
                    intangible_seen = True
                elif intangible_seen and intangible == 0:
                    intangible_expired = True
            # Give the third form an actual turn before finishing with Body Slam.
            if hp == 313 and round_number > rounds[-1]:
                form_three_turn = True
            preferences = ["BLOCK_POTION", "BARRICADE"]
            if combat["player"]["block"] < 500:
                preferences.append("ENTRENCH")
            if subject is not None and not intangible and (hp != 313 or form_three_turn):
                preferences.append("BODY_SLAM")
            ranked = []
            for i, candidate in enumerate(public["candidates"]):
                ident = ((candidate.get("subject") or {}).get("properties") or {}).get(
                    "definition_id"
                )
                if candidate["verb"] in {"play", "use"} and ident in preferences:
                    ranked.append((preferences.index(ident), i))
                elif candidate["verb"] == "end_turn":
                    ranked.append((len(preferences), i))
            if not ranked:
                raise ValueError("No legal diagnostic combat action")
            selected = min(ranked)[1]
            binding = frame["actions"][selected]
            choice = {
                "action_index": selected,
                "binding_id": frame["binding_id"],
                "bound_action_id": binding["bound_action_id"],
            }
            append(trace, {"kind": "policy_input", "frame": frame})
            successor = native.request(
                "step",
                snapshot_id=current["snapshot"]["snapshot_id"],
                action_index=binding["raw_index"],
                timeout=18,
            )
            if successor["delivery_domain"] != "native":
                raise ValueError("A diagnostic choice must complete on the native host")
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
            raise ValueError("The Test Subject control exceeded its action bound")
        shutdown = native.close()
        converter.close()
    finally:
        converter.stop()
        native.stop()
    domains = records(out / "worker/answer-plan-deliveries.jsonl.gz")
    if any(row["delivery_domain"] != "native" for row in domains):
        raise ValueError("The diagnostic ledger contains a non-native delivery")
    count = scripted_verification(ctx, out, deadline)
    checks = {
        "both_native_revivals": forms == [111, 212, 313] and rounds == sorted(set(rounds)),
        "intangible_applied_then_removed_in_third_form": intangible_seen and intangible_expired,
        "third_form_enemy_turn_completed": form_three_turn,
        "native_completed_boss_reward_owner": True,
        "clean_shutdown": shutdown["clean_exit"] and not shutdown["runtime_errors"],
        "independent_public_action_receipt_reconstruction": count == index,
    }
    if not all(checks.values()):
        raise ValueError(f"Test Subject control failed: {checks}, observed forms {forms}")
    return {
        "checks": checks,
        "native_form_hp": forms,
        "revival_rounds": rounds,
        "actual_deliveries": count,
    }


def control(root: Path, out: Path, generation: int) -> dict[str, Any]:
    deadline = time.monotonic() + 265
    parent = load(root, root / RECIPE)
    build_path = root / WORKSPACE / "report.json"
    report = identified(build_path)
    ctx = support_context(root, parent, report)
    before = frozen_checks(ctx)
    out.mkdir(parents=True, exist_ok=False)
    start = prepare(ctx, fixture_case(generation), out, deadline)
    if start["status"] != "ready":
        raise ValueError("Fresh diagnostic setup unavailable")
    result = fight(ctx, start, out, deadline)
    after = frozen_checks(ctx)
    if not all(before.values()) or not all(after.values()):
        raise ValueError("Frozen environment changed during control")
    return write(
        out / "report.json",
        {
            "schema_version": "native-curriculum-test-subject-revival-control-v1",
            "status": "test_subject_revivals_verified",
            "support_build_id": report["report_id"],
            "environment_id": ctx["environment"]["manifest_id"],
            "generation": generation,
            **result,
            "checks_before": before,
            "checks_after": after,
            "diagnostic_only": True,
            "training_labels_allowed": False,
            "optimizer_updates": 0,
            "sources": {
                **parent["sources"],
                str(build_path.relative_to(root)): _sha_file(build_path),
                "src/spireshift/native_win5_control.py": _sha_file(
                    root / "src/spireshift/native_win5_control.py"
                ),
                "src/spireshift/native_win5_inputs.py": _sha_file(
                    root / "src/spireshift/native_win5_inputs.py"
                ),
            },
            "evidence": {
                str(path.relative_to(root)): _sha_file(path)
                for path in out.rglob("*")
                if path.is_file()
            },
        },
    )


if __name__ == "__main__":
    import sys

    root = Path.cwd()
    out = root / (sys.argv[1] if len(sys.argv) > 1 else CONTROL)
    result = control(root, out, int(sys.argv[2]) if len(sys.argv) > 2 else 1)
    print(
        json.dumps(
            {
                key: result[key]
                for key in ["status", "checks", "native_form_hp", "actual_deliveries", "report_id"]
            }
        )
    )
