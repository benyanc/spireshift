"""Fresh native Reattach effects and fail-fast support controls; no learning."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _sha_file
from spireshift.native_e2e_contract import difference_paths
from spireshift.native_flow_live_v12 import append
from spireshift.native_flow_verification_v12 import records
from spireshift.native_shared_transport import JsonLines
from spireshift.native_win3_game import episode, prepare, worker, write
from spireshift.native_win3_inputs import RECIPE, binding, frozen_checks, load
from spireshift.native_win_plan import start_cases


def project(
    ctx: dict[str, Any], converter: JsonLines, current: dict[str, Any], deadline: float
) -> dict[str, Any]:
    return converter.project(current["snapshot"], current["reads"], None, deadline)


def scripted_verification(ctx: dict[str, Any], folder: Path, deadline: float) -> int:
    root = ctx["qualification"].root
    converter = JsonLines(
        root,
        [ctx["node"], str(root / "scripts/engine-shared-input-v16.mjs")],
        folder / "verify-converter.log",
    )
    observations = iter(records(folder / "worker/public-observations.jsonl.gz"))
    receipts = iter(records(folder / "worker/public-receipts.jsonl.gz"))
    total = 0
    frame = None
    try:
        for row in records(folder / "scripted-public.jsonl.gz"):
            if row["kind"] in {"policy_input", "final_observation"}:
                raw = next(observations)
                # The explicit fixture setup mounts one native lobby before
                # replacing it with the diagnostic combat. It submits no action.
                if (
                    frame is None
                    and raw["snapshot"]["snapshot_id"] != row["frame"]["observation"]["snapshot_id"]
                ):
                    if raw["snapshot"]["sequence"] != 1:
                        raise ValueError("Unexpected diagnostic setup observations")
                    raw = next(observations)
                frame = converter.project(raw["snapshot"], raw["reads"], None, deadline)
                if difference_paths(frame, row["frame"]):
                    raise ValueError("Diagnostic native public projection changed")
            else:
                if frame is None:
                    raise ValueError("Diagnostic choice has no current menu")
                choice, receipt = row["choice"], row["receipt"]
                raw = next(receipts)
                if (
                    raw["delivery"] != "delivered"
                    or raw["action"]["bound_action_id"] != choice["bound_action_id"]
                    or raw["snapshot_id"] != frame["observation"]["snapshot_id"]
                    or raw["successor_snapshot_id"] != receipt["successor_snapshot_id"]
                ):
                    raise ValueError("Diagnostic native delivery differs")
                converter.commit(choice, receipt, deadline)
                total += 1
        if next(observations, None) is not None or next(receipts, None) is not None:
            raise ValueError("Extra diagnostic evidence")
        converter.close()
    finally:
        converter.stop()
    return total


def fixture(ctx: dict[str, Any], target: Path, revival: bool, deadline: float) -> dict[str, Any]:
    root = ctx["qualification"].root
    target.mkdir()
    native = worker(ctx, target / "worker")
    converter = JsonLines(
        root,
        [ctx["node"], str(root / "scripts/engine-shared-input-v16.mjs")],
        target / "converter.log",
    )
    frame: dict[str, Any] = {}
    delivered = 0

    def take(predicate: Any) -> None:
        nonlocal frame, delivered
        matches = [i for i, a in enumerate(frame["public_input"]["candidates"]) if predicate(a)]
        if not matches:
            raise ValueError("No actual current diagnostic action")
        index = matches[0]
        bind = frame["actions"][index]
        append(target / "scripted-public.jsonl.gz", {"kind": "policy_input", "frame": frame})
        choice = {
            "action_index": index,
            "binding_id": frame["binding_id"],
            "bound_action_id": bind["bound_action_id"],
        }
        successor = native.request(
            "step",
            snapshot_id=frame["observation"]["snapshot_id"],
            action_index=bind["raw_index"],
            timeout=20,
        )
        receipt = {
            "binding_id": frame["binding_id"],
            "delivery": "delivered",
            "bound_action_id": bind["bound_action_id"],
            "runtime_instance_id": frame["observation"]["runtime_instance_id"],
            "before_snapshot_id": frame["observation"]["snapshot_id"],
            "successor_snapshot_id": successor["snapshot"]["snapshot_id"],
        }
        converter.commit(choice, receipt, deadline)
        append(
            target / "scripted-public.jsonl.gz",
            {"kind": "policy_choice", "choice": choice, "receipt": receipt},
        )
        delivered += 1
        frame = project(ctx, converter, successor, deadline)

    try:
        current = native.request(
            "diagnostic_combat",
            diagnostic_only=True,
            seed=f"SP1RESH1FTWG57REV{ctx['config']['support_control_generation']}"
            if revival
            else f"SP1RESH1FTWG57ALL{ctx['config']['support_control_generation']}",
            deck=["BLUDGEON" if revival else "WHIRLWIND"] * 5,
            relics=["BURNING_BLOOD", "ANCHOR", "PHILOSOPHERS_STONE"]
            + ([] if revival else ["VELVET_CHOKER", "VAJRA"]),
            potions=["FIRE_POTION" if revival else "ENERGY_POTION"] * 2,
            timeout=30,
        )
        frame = project(ctx, converter, current, deadline)

        def combat() -> dict[str, Any]:
            return dict(
                frame["public_input"]["context"]["interaction"]["content"].get("context", {})
            )

        enemies = combat()["enemies"]
        if len(enemies) != 3 or not all(e["hp"] > 0 for e in enemies):
            raise ValueError("Missing actual native segment encounter")
        target_id = enemies[0]["definition_id"]

        def at_target(a: dict[str, Any]) -> bool:
            return any(
                x.get("entity", {}).get("properties", {}).get("definition_id") == target_id
                for x in a.get("arguments", [])
            )

        for _ in range(2):
            take(
                lambda a: (
                    a["verb"] == "use"
                    and (a.get("subject") or {}).get("properties", {}).get("definition_id")
                    == ("FIRE_POTION" if revival else "ENERGY_POTION")
                    and (not revival or at_target(a))
                )
            )
        energy_before = combat()["player"]["energy"]
        take(
            lambda a: (
                a["verb"] == "play"
                and (a.get("subject") or {}).get("properties", {}).get("definition_id")
                == ("BLUDGEON" if revival else "WHIRLWIND")
                and (not revival or at_target(a))
            )
        )
        if revival:
            first = next((e for e in combat()["enemies"] if e["definition_id"] == target_id), None)
            if (first is not None and first["hp"] != 0) or not any(
                e["hp"] > 0 for e in combat()["enemies"]
            ):
                raise ValueError("Individual segment death was not exercised")
            for _ in range(3):
                take(lambda a: a["verb"] == "end_turn")
                first = next(
                    (e for e in combat()["enemies"] if e["definition_id"] == target_id), None
                )
                if first is not None and first["hp"] > 0:
                    break
            if first is None or first["hp"] != 25:
                raise ValueError("Native segment regeneration changed")
            if not any(
                a["verb"] == "play" and at_target(a) for a in frame["public_input"]["candidates"]
            ):
                raise ValueError("Revived segment remains un-hittable")
            result = {
                "one_segment_death_then_native_25_HP_reattach": True,
                "revived_segment_targetable": True,
            }
        else:
            if frame["source_family"] != "reward_claim":
                raise ValueError("All-segment death did not finish the native combat")
            result = {
                "all_three_segments_defeated": True,
                "native_reward_owner_reached": True,
                "native_energy_before_whirlwind": energy_before,
            }
        append(target / "scripted-public.jsonl.gz", {"kind": "final_observation", "frame": frame})
        shutdown = native.close()
        converter.close()
    finally:
        converter.stop()
        native.stop()
    if not shutdown["clean_exit"] or shutdown["runtime_errors"]:
        raise ValueError("Diagnostic runtime errors remain")
    count = scripted_verification(ctx, target, deadline)
    if count != delivered:
        raise ValueError("Diagnostic delivery count differs")
    return write(
        target / "report.json",
        {
            "schema_version": "native-reattach-effect-control-v1",
            **result,
            "actual_deliveries_verified": count,
            "shutdown": shutdown,
            "diagnostic_only": True,
            "labels_allowed": False,
            "optimizer_updates": 0,
        },
    )


def main() -> int:
    root = Path.cwd()
    began = time.monotonic()
    ctx = load(root, root / RECIPE, require_control=False)
    cfg = ctx["config"]
    target = (
        root
        / f"artifacts/native-win-curriculum/reattach-control-v{cfg['support_control_generation']}"
    )
    target.mkdir(parents=True, exist_ok=False)
    before = frozen_checks(ctx)
    one = fixture(ctx, target / "regeneration", True, began + 270)
    print("Reattach control: native regeneration and renewed targetability verified", flush=True)
    all_dead = fixture(ctx, target / "all-segments", False, began + 270)
    print(
        "Reattach control: all segments defeated, reward owner and clean shutdown verified",
        flush=True,
    )
    short = {**ctx, "config": {**cfg, "plan": {**cfg["plan"], "maximum_decisions": 2}}}
    cases = [
        start_cases(10)[9],
        {
            "key": "support-natural",
            "partition": "control_fit",
            "player": 3,
            "entry": "natural",
            "act": 1,
            "act_definition": "ANY",
            "boss": None,
            "profile": None,
            "seed_pool": ["SP1RESH1FTWG57NAT1"],
        },
    ]
    runs = []
    for case in cases:
        where = target / case["key"]
        where.mkdir()
        start = prepare(ctx, case, where, began + 270)
        if start["status"] != "ready":
            raise ValueError("Fresh support control start unavailable")
        output = where / "delivery"
        output.mkdir()
        runs.append(episode(short, start, "reference", output, began + 270))
    after = frozen_checks(ctx)
    checks = {
        "native_regeneration_and_targeting_preserved": one[
            "one_segment_death_then_native_25_HP_reattach"
        ]
        and one["revived_segment_targetable"],
        "all_segment_death_visual_path_completes_cleanly": all_dead["native_reward_owner_reached"],
        "new_native_mount_and_load_deliveries": all(r["policy_decisions"] == 2 for r in runs),
        "originals_and_game_frozen": all(before.values()) and all(after.values()),
        "no_optimizer_updates": True,
        "no_runtime_error_whitelist": True,
    }
    if not all(checks.values()):
        raise ValueError("Support control failed")
    refs = [cfg["continuation_parent"], cfg["support_build"], cfg["protection"]] + [
        x[2] for x in cfg["saved_audits"]
    ]
    report = write(
        target / "report.json",
        {
            "schema_version": "native-curriculum-reattach-support-control-v1",
            "status": "reattach_support_and_continuation_verified",
            "implementation_id": manifest_identifier(cfg["implementation"]),
            "launch_binding_id": binding(cfg),
            "checks": checks,
            "actual_deliveries_verified": one["actual_deliveries_verified"]
            + all_dead["actual_deliveries_verified"]
            + sum(r["policy_decisions"] for r in runs),
            "optimizer_updates": 0,
            "main_started": False,
            "checks_before": before,
            "checks_after": after,
            "sources": {**cfg["implementation"], **{r["path"]: r["sha256"] for r in refs}},
            "evidence": {
                str(p.relative_to(root)): _sha_file(p) for p in target.rglob("*") if p.is_file()
            },
        },
    )
    print(json.dumps({k: v for k, v in report.items() if k not in {"sources", "evidence"}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
