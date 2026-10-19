"""Scoped native Crystal Sphere/Rolling Boulder repair and effect checks.

No game-rule replacement, historical replay, training or app copies. The old
mechanics evidence stays attached to its old host; a reviewed source delta and
new public effect checks are required before using the new host for learning.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import (
    EngineQualificationConfig,
    _sha_file,
    load_engine_qualification_config,
)
from spireshift.engine_run import _run_inputs
from spireshift.engine_worker import EngineWorker, worker_helpers
from spireshift.engine_worker_qualification import immutable_checks
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_reuse import check_sources

SCRIPT = "engine-mechanics-worker-v4.mjs"
CHANGED = {"src/GodotStubs/Core.cs", "src/GodotStubs/Math.cs", "src/Sts2Headless/RunSimulator.cs"}


def repair_inputs(q: EngineQualificationConfig, cfg: dict[str, Any]) -> dict[str, Any]:
    old = _run_inputs(q, q.root / cfg["old_run"]["path"])
    new = _run_inputs(q, q.root / cfg["new_run"]["path"])
    for key, inputs in (("old_run", old), ("new_run", new)):
        if manifest_identifier(inputs["recipe"]) != cfg[key]["id"]:
            raise ValueError("Runtime repair run recipe changed")
    if (
        old["build"]["runtime_sts2_sha256"] != new["build"]["runtime_sts2_sha256"]
        or old["projection"] != new["projection"]
        or old["objective"] != new["objective"]
        or old["archive"] != new["archive"]
        or old["runtime"] != new["runtime"]
        or old["localization"] != new["localization"]
    ):
        raise ValueError("A scoped host repair cannot change game rules, projection or objective")
    before = {
        str(p.relative_to(old["candidate"])): _sha_file(p)
        for p in (old["candidate"] / "src").rglob("*.cs")
        if not {"obj", "bin"} & set(p.parts)
    }
    after = {
        str(p.relative_to(new["candidate"])): _sha_file(p)
        for p in (new["candidate"] / "src").rglob("*.cs")
        if not {"obj", "bin"} & set(p.parts)
    }
    delta = {
        name: {"old": before.get(name), "new": after.get(name)}
        for name in before.keys() | after.keys()
        if before.get(name) != after.get(name)
    }
    if set(delta) != CHANGED or delta != cfg["native_source_delta"]:
        raise ValueError("Native repair differs from the reviewed three-file delta")
    return new


def player(o: dict[str, Any]) -> dict[str, Any]:
    return dict(o["model_input"]["context"]["persistent"]["player"])


def deck(o: dict[str, Any]) -> list[str]:
    return [
        c["definition_id"]
        for r in o["model_input"]["context"]["reads"]
        if r["kind"] == "run_deck"
        for c in r["content"]["cards"]
    ]


def step(w: EngineWorker, o: dict[str, Any], index: int) -> dict[str, Any]:
    return w.request("step", snapshot_id=o["snapshot"]["snapshot_id"], action_index=index)


def crystal(w: EngineWorker, option: int, large: bool) -> dict[str, Any]:
    o = w.request("potion_fixture", room="event", event="CRYSTAL_SPHERE", potions=[])
    before, old_deck = player(o), deck(o)
    o = step(w, o, option)
    entered, new_deck = player(o), deck(o)
    if (option == 0 and entered["gold"] >= before["gold"]) or (
        option == 1 and len(new_deck) != len(old_deck) + 1
    ):
        raise ValueError("Native Crystal Sphere payment/curse effect missing")
    moves = []
    for index in range(6 if option == 1 else 3):
        menu = o["model_input"]["candidates"]
        title = o["snapshot"]["interaction"]["content"]["surface"].get("title", "")
        if "grid" not in title or len(menu) != 242 or any("None at" in c["label"] for c in menu):
            raise ValueError("Crystal grid needs both public tools and every current coordinate")
        # Fixed public-only centers; never consult the private/native item layout.
        x, y = [(2, 2), (5, 2), (8, 2), (2, 5), (5, 5), (8, 5)][index]
        selected = (121 if large else 0) + x * 11 + y
        moves.append(menu[selected]["label"])
        o = step(w, o, selected)
    for _ in range(20):
        title = o["snapshot"]["interaction"]["content"]["surface"].get("title", "")
        if "grid" in title:
            raise ValueError("Last native divination did not finish the grid")
        if o["snapshot"]["interaction"]["kind"] == "event_option":
            if [c["label"] for c in o["model_input"]["candidates"]] != ["Proceed"]:
                raise ValueError("Native event has not reached its real finished page")
            break
        # Choose the first actual card when a revealed card reward opens.
        # The diagnostic default may repeatedly decline/reopen an unclaimed reward.
        chosen = (
            0
            if o["snapshot"]["interaction"]["kind"] == "card_reward_selection"
            else o["default_action_index"]
        )
        o = step(w, o, chosen)
    else:
        raise ValueError("Crystal Sphere reward collection did not settle")
    return {
        "payment_option": option,
        "large_tool": large,
        "moves": moves,
        "before": before,
        "after_payment": entered,
        "after": player(o),
        "added_cards": [c for c in deck(o) if c not in old_deck],
        "native_event_finished": True,
    }


def boulder(w: EngineWorker, upgrade: int) -> dict[str, Any]:
    o = w.request(
        "fixture",
        fixture={"card_id": "ROLLING_BOULDER", "upgrade": upgrade, "funded": True, "copies": 1},
    )
    i = next(i for i, c in enumerate(o["model_input"]["candidates"]) if c["verb"] == "play")
    o = step(w, o, i)
    readings = []
    for _ in range(3):
        content = o["model_input"]["context"]["interaction"]["content"]["context"]
        powers = content["player"]["statuses"]
        power = next(s for s in powers if s["definition_id"] == "ROLLING_BOULDER_POWER")
        readings.append({"round": content["round"], "power": power, "enemies": content["enemies"]})
        if len(readings) == 3:
            break
        i = next(i for i, c in enumerate(o["model_input"]["candidates"]) if c["verb"] == "end_turn")
        o = step(w, o, i)
    amounts = [r["power"]["amount"] for r in readings]
    health = [sum(e["hp"] for e in r["enemies"]) for r in readings]
    if not (amounts[0] < amounts[1] < amounts[2] and health[0] > health[1] > health[2]):
        raise ValueError("Rolling Boulder did not apply growing native damage on two turn starts")
    return {"upgrade": upgrade, "turns": readings, "native_damage_and_growth": True}


def run(q: EngineQualificationConfig, path: Path, node: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    sources = {
        str(path.relative_to(q.root)): _sha_file(path),
        "src/spireshift/engine_runtime_gaps.py": _sha_file(Path(__file__)),
    }
    inputs = repair_inputs(q, cfg)
    final = q.root / cfg["workspace"] / "report.json"
    if final.exists():
        result = identified(final)
        if result["config_id"] != manifest_identifier(cfg):
            raise ValueError("Saved runtime repair check belongs to another recipe")
        check_sources(q.root, result["sources"])
        return result
    if _running_games():
        raise ValueError("Close the game before the isolated repair check")
    snapshot = _shared_snapshot(Path.home() / "Library/Application Support/SlayTheSpire2")
    started = time.monotonic()
    results = []
    for index in range(6):
        if time.monotonic() - started > 120:
            raise TimeoutError("Finite repair check exceeded its short budget")
        workspace = final.parent / f"case-{index:02d}"
        w = EngineWorker(q, inputs, workspace, node, worker_helpers(q.root, SCRIPT), script=SCRIPT)
        try:
            w.request("mount", seed=f"SP1RESH1FTGAPCHECK{index + cfg['seed_offset']:03d}")
            result = crystal(w, index // 2, bool(index % 2)) if index < 4 else boulder(w, index - 4)
            w.close()
            atomic_json(workspace / "result.json", result)
            results.append(result)
        finally:
            w.stop()
        sources.update(
            {
                str(p.relative_to(q.root)): _sha_file(p)
                for p in workspace.rglob("*")
                if p.is_file() and not p.is_symlink()
            }
        )
    checks = immutable_checks(q, inputs)
    checks["account_profile_unchanged"] = snapshot == _shared_snapshot(
        Path.home() / "Library/Application Support/SlayTheSpire2"
    )
    if not all(checks.values()):
        raise ValueError("Immutable inputs/account changed in repair control")
    check_sources(q.root, sources)
    body = {
        "schema_version": "native-runtime-gap-effects-v1",
        "config_id": manifest_identifier(cfg),
        "status": "scoped_native_runtime_effects_pass",
        "cases": results,
        "checks": checks,
        "sources": sources,
        "build_report_id": inputs["inputs"]["build_report_id"],
        "full_run_attempts": 0,
        "optimizer_steps": 0,
        "privileged_fixture": True,
        "training_allowed": False,
        "shipped_cross_host_parity": False,
        "game_apps_created": 0,
        "wall_seconds": time.monotonic() - started,
        "claim_scope": "native_public_crystal_tools_payments_completion_and_two_boulder_turns_only",
    }
    result = {**body, "report_id": manifest_identifier(body)}
    atomic_json(final, result)
    return result


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("qualification", type=Path)
    p.add_argument("config", type=Path)
    p.add_argument("--node", type=Path, required=True)
    a = p.parse_args()
    q = load_engine_qualification_config(a.qualification)
    result = run(q, q.root / a.config, a.node)
    print(json.dumps({k: v for k, v in result.items() if k not in {"sources", "cases"}}, indent=2))


if __name__ == "__main__":
    main()
