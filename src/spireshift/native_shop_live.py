"""Small paired state-machine diagnostics on one frozen game; never training."""

from __future__ import annotations

import argparse
import gzip
import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_native import _running_games
from spireshift.engine_qualification import _sha_file
from spireshift.engine_shop_fixture_worker import SCRIPT, ShopFixtureWorker
from spireshift.engine_worker import worker_helpers
from spireshift.engine_working_app import preflight_working_app
from spireshift.full_run_experience import atomic_json
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_e2e_contract import difference_paths
from spireshift.native_live_policy import LivePolicy
from spireshift.native_shared_transport import JsonLines
from spireshift.native_shop_inputs import load
from spireshift.native_shop_session import official_prefix


def append(path: Path, row: dict[str, Any]) -> None:
    with gzip.open(path, "at") as stream:
        stream.write(json.dumps(row, allow_nan=False) + "\n")


def select_action(frame: dict[str, Any], instruction: str) -> int:
    family = frame["source_family"]
    candidates = frame["public_input"]["candidates"]
    if instruction == "open_inventory" and family == "shop_room":
        matches = [i for i, c in enumerate(candidates) if c["label"] == "Open inventory"]
    elif instruction == "remove_card" and family == "shop_inventory":
        matches = [
            i
            for i, c in enumerate(candidates)
            if c["verb"] == "open" and c["label"].startswith("Choose a card to remove for ")
        ]
    elif instruction == "confirm_first_card" and family == "card_selection":
        matches = [i for i, c in enumerate(candidates) if c["verb"] == "confirm"]
        if matches:
            return matches[0]  # Declared first legal candidate in the complete public menu.
    elif instruction == "cancel_removal" and family == "card_selection":
        matches = [i for i, c in enumerate(candidates) if c["verb"] == "cancel"]
    else:
        raise ValueError("Unexpected native owner in the declared shop script")
    if len(matches) != 1:
        raise ValueError("No unique declared current shop or child-selection control")
    return matches[0]


class ScriptedPolicy(LivePolicy):
    """Existing session protocol, with a declared script and no model or optimizer."""

    def __init__(self, instructions: list[str]) -> None:
        self.instructions = instructions
        self.decisions = 0
        self.done = False
        self.frames: list[dict[str, Any]] = []
        self._fixture_pending: tuple[dict[str, Any], dict[str, Any]] | None = None

    def choose(self, frame: dict[str, Any]) -> dict[str, Any]:
        if (
            self.done
            or self._fixture_pending is not None
            or self.decisions >= len(self.instructions)
        ):
            raise ValueError("No diagnostic retry or undeclared follow-up")
        index = select_action(frame, self.instructions[self.decisions])
        choice = {
            "binding_id": frame["binding_id"],
            "action_index": index,
            "bound_action_id": frame["actions"][index]["bound_action_id"],
            "optimizer_updates": 0,
            "privileged_fixture": True,
        }
        self._fixture_pending = frame, choice
        self.frames.append(frame)
        return choice

    def acknowledge(self, receipt: dict[str, Any]) -> None:
        if self._fixture_pending is None:
            raise ValueError("No pending diagnostic delivery")
        frame, choice = self._fixture_pending
        if (
            receipt.get("delivery") != "delivered"
            or receipt.get("binding_id") != frame["binding_id"]
            or receipt.get("bound_action_id") != choice["bound_action_id"]
            or receipt.get("runtime_instance_id") != frame["observation"]["runtime_instance_id"]
            or receipt.get("before_snapshot_id") != frame["observation"]["snapshot_id"]
            or not receipt.get("successor_snapshot_id")
        ):
            raise ValueError("Rejected or uncertain diagnostic delivery; no retry")
        self.done = self.decisions + 1 == len(self.instructions)
        self._fixture_pending = None
        self.decisions += 1

    def observe_successor(self, frame: dict[str, Any]) -> None:
        if self._fixture_pending is not None or not self.done:
            raise ValueError("Unowned final diagnostic successor")
        self.frames.append(frame)


def prepare_fixture(
    root: Path, ctx: dict[str, Any], case: dict[str, Any], output: Path
) -> dict[str, str]:
    worker = ShopFixtureWorker(
        ctx["qualification"],
        ctx["native"],
        output / "setup-worker",
        Path(ctx["config"]["node"]),
        worker_helpers(root, SCRIPT),
    )
    try:
        result = worker.request(
            "prepare", seed=case["seed"], room=case["room"], relics=case["relics"], timeout=40
        )
        original = Path(result["save"]["path"])
        save = output / "diagnostic-current-run.save"
        save.write_bytes(original.read_bytes())
        shutdown = worker.close()
        if not shutdown["clean_exit"] or shutdown["runtime_errors"]:
            raise ValueError("Diagnostic fixture setup did not shut down cleanly")
        atomic_json(
            output / "fixture-provenance.json",
            {
                "seed": case["seed"],
                "source_save_sha256": _sha_file(original),
                "save_sha256": _sha_file(save),
                "game_assembly_sha256": ctx["environment"]["game_assembly_sha256"],
                "setup": {
                    "room": case["room"],
                    "obtain_relics": case["relics"],
                    "hp": 48,
                    "gold": 1000,
                    "deck": ["STRIKE_IRONCLAD", "DEFEND_IRONCLAD", "BASH"],
                    "max_hp": 80,
                    "native_map_start_type": "shop",
                },
                "privileged_fixture": True,
                "training_allowed": False,
                "shutdown": shutdown,
            },
        )
        return {"path": str(save.relative_to(root)), "sha256": _sha_file(save)}
    finally:
        worker.stop()


def native_case(
    root: Path,
    ctx: dict[str, Any],
    case: dict[str, Any],
    output: Path,
    policy: ScriptedPolicy,
    deadline: float,
) -> dict[str, Any]:
    output.mkdir()
    worker = ShopFixtureWorker(
        ctx["qualification"],
        ctx["native"],
        output / "worker",
        Path(ctx["config"]["node"]),
        worker_helpers(root, SCRIPT),
    )
    converter = JsonLines(
        root,
        [ctx["config"]["node"], str(root / "scripts/engine-shared-input-v16.mjs")],
        output / "converter-stderr.log",
    )
    try:
        current = worker.request(
            "load",
            seed=case["seed"],
            save_json=(root / case["fixture_save"]["path"]).read_text(),
            timeout=25,
        )
        for _ in case["instructions"]:
            frame = converter.project(current["snapshot"], current["reads"], None, deadline)
            choice = policy.choose(frame)
            binding = frame["actions"][choice["action_index"]]
            successor = worker.request(
                "step",
                snapshot_id=current["snapshot"]["snapshot_id"],
                action_index=binding["raw_index"],
                timeout=20,
            )
            receipt = {
                "binding_id": frame["binding_id"],
                "delivery": "delivered",
                "bound_action_id": binding["bound_action_id"],
                "runtime_instance_id": frame["observation"]["runtime_instance_id"],
                "before_snapshot_id": frame["observation"]["snapshot_id"],
                "successor_snapshot_id": successor["snapshot"]["snapshot_id"],
            }
            append(output / "shared-public.jsonl.gz", {"kind": "policy_input", "frame": frame})
            append(
                output / "shared-public.jsonl.gz",
                {"kind": "policy_choice", "choice": choice, "receipt": receipt},
            )
            policy.acknowledge(receipt)
            converter.commit(choice, receipt, deadline)
            current = successor
            if policy.done:
                break
        final = converter.project(current["snapshot"], current["reads"], None, deadline)
        policy.observe_successor(final)
        append(output / "shared-public.jsonl.gz", {"kind": "diagnostic_successor", "frame": final})
        shutdown = worker.close()
        converter.close()
        result = {
            "shutdown": shutdown,
            "policy_decisions": policy.decisions,
            "clean": shutdown["clean_exit"] and not shutdown["runtime_errors"],
        }
        result["report_id"] = manifest_identifier(result)
        atomic_json(output / "report.json", result)
        return result
    finally:
        worker.stop()
        converter.stop()


def compare_frames(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> dict[str, Any]:
    matches = 0
    first = None
    for index, (native, official) in enumerate(zip(left, right, strict=False)):
        paths = difference_paths(native["public_input"], official["public_input"])
        menus = [a["key"] for a in native["actions"]] == [a["key"] for a in official["actions"]]
        if paths or not menus:
            first = {"index": index, "all_difference_paths": paths, "menu_keys_equal": menus}
            break
        matches += 1
    return {
        "matching_states": matches,
        "native_states": len(left),
        "official_states": len(right),
        "first_difference": first,
        "later_divergent_states_realigned": False,
        "equal": first is None and len(left) == len(right),
    }


def effects(case: dict[str, Any], frames: list[dict[str, Any]]) -> dict[str, Any]:
    if len(frames) != len(case["instructions"]) + 1:
        raise ValueError("Missing declared shop-task final successor")
    before, after = frames[1]["public_input"]["context"], frames[-1]["public_input"]["context"]
    if (
        before["interaction"]["kind"] != "shop_inventory"
        or after["interaction"]["kind"] != "shop_inventory"
    ):
        raise ValueError("The native shop must regain ownership after its child finishes")
    a, b = before["persistent"]["player"], after["persistent"]["player"]

    def deck(c: dict[str, Any]) -> list[dict[str, Any]]:
        return next(r["content"]["cards"] for r in c["reads"] if r["kind"] == "run_deck")

    removed = case["instructions"][-1] == "confirm_first_card"
    if a["gold"] != 1000 or b["gold"] != (900 if removed else 1000):
        raise ValueError("Native removal completion has unexpected gold effect")
    if len(deck(before)) != 3 or len(deck(after)) != (2 if removed else 3):
        raise ValueError("Native removal completion has unexpected deck effect")
    if a["hp"] != 48 or b["hp"] != 48:
        raise ValueError("Undeclared fixture health change")
    catalog = next(r["content"] for r in after["reads"] if r["kind"] == "shop_catalog")
    if catalog["card_removal"]["stocked"] is not (not removed):
        raise ValueError("Native removal service stock does not match completion")
    return {
        "gold_before": a["gold"],
        "gold_after": b["gold"],
        "deck_before": 3,
        "deck_after": len(deck(after)),
        "removed": removed,
        "native_child_completed": True,
    }


def run_case(root: Path, ctx: dict[str, Any], case: dict[str, Any], output: Path) -> dict[str, Any]:
    if _running_games():
        raise ValueError("Close STS2 before diagnostic comparison")
    preflight_working_app(ctx["working_app"])
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "active.json", {"case": case, "training_allowed": False})
    for name in ctx["config"]["implementation"]:
        destination = output / "source-at-launch" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((root / name).read_bytes())
    atomic_json(output / "source-at-launch/recipe.json", ctx["config"])
    started = time.monotonic()
    case = {**case, "fixture_save": prepare_fixture(root, ctx, case, output)}
    policies = [ScriptedPolicy(case["instructions"]), ScriptedPolicy(case["instructions"])]
    local_ctx = {**ctx, "config": {**ctx["config"], "maximum_decisions": len(case["instructions"])}}
    native = native_case(root, local_ctx, case, output / "native", policies[0], started + 150)
    if not native["clean"]:
        raise ValueError("Native shutdown unverified; no official control may start")
    official = official_prefix(local_ctx, case, output / "official", policies[1], started + 150)
    from spireshift.native_shop_control_verification import verify_host

    verified_deliveries = {}
    verification_errors = {}
    for host in ("native", "official"):
        try:
            verified_deliveries[host] = verify_host(
                root, local_ctx, case, host, output / host, output, started + 180
            )
        except (ValueError, KeyError, StopIteration) as error:
            verification_errors[host] = str(error)
    comparison = compare_frames(policies[0].frames, policies[1].frames)
    checks: dict[str, Any] = {}
    effect_errors = {}
    for name, policy in zip(("native", "official"), policies, strict=True):
        try:
            checks[name] = effects(case, policy.frames)
        except (ValueError, KeyError) as error:
            effect_errors[name] = str(error)
    clean = native["clean"] and all(official["checks"].values())
    passed = (
        clean
        and not verification_errors
        and not effect_errors
        and comparison["equal"]
        and checks["native"] == checks["official"]
    )
    result = {
        "schema_version": "native-shop-task-case-v1",
        "case": case,
        "status": "transition_comparison_pass" if passed else "transition_comparison_blocked",
        "native": native,
        "official": official,
        "comparison": comparison,
        "effects": checks,
        "independently_reconstructed_deliveries": verified_deliveries,
        "verification_errors": verification_errors,
        "effect_errors": effect_errors,
        "clean_reset": clean,
        "environment_id": ctx["environment"]["manifest_id"],
        "sources": ctx["sources"],
        "privileged_fixture": True,
        "training_allowed": False,
        "optimizer_updates": 0,
        "full_game_evaluation": False,
        "game_apps_created": 0,
        "wall_seconds": time.monotonic() - started,
    }
    result["evidence"] = {
        str(p.relative_to(root)): _sha_file(p)
        for p in output.rglob("*")
        if p.is_file() and p.name != "active.json"
    }
    result["report_id"] = manifest_identifier(result)
    atomic_json(output / "report.json", result)
    (output / "active.json").rename(output / "complete.json")
    check_sources(root, ctx["sources"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--case", required=True)
    args = parser.parse_args()
    root = Path.cwd()
    ctx = load(root, args.recipe.resolve())
    case = next(row for row in ctx["config"]["cases"] if row["key"] == args.case)
    result = run_case(root, ctx, case, root / ctx["config"]["workspace"] / case["key"])
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in {"sources", "evidence", "official"}},
            indent=2,
        )
    )
    return 0 if result["status"] == "transition_comparison_pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
