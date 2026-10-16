"""Finite outside-combat belt/merchant controls on the exact native engine.

Privileged fixtures never become experience. The existing game model owns every
potion effect. Each independent case owns a fresh mutable profile, not an app.
"""

from __future__ import annotations

import gzip
import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_coverage import _read_sealed, _sealed
from spireshift.engine_native import _private_path, _require_native_launch_support, _running_games
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.engine_run import _run_inputs, _verify_saved_observation
from spireshift.engine_worker import EngineWorker, worker_helpers
from spireshift.engine_worker_qualification import immutable_checks
from spireshift.full_run_experience import atomic_json

SCRIPT = "engine-mechanics-worker-v3.mjs"
ANYTIME = {"AMBERGRIS", "BLOOD_POTION", "ENTROPIC_BREW", "FOUL_POTION", "FRUIT_JUICE"}
IMPLEMENTATION = ("engine_potion_checks.py", "engine_worker.py", "engine_run.py")


def potion_implementation(root: Path) -> dict[str, str]:
    return {name: _sha_file(root / "src/spireshift" / name) for name in IMPLEMENTATION}


def potion_cases() -> list[dict[str, Any]]:
    cases = [
        {"id": f"{potion.lower()}-{room}", "potion": potion, "room": room, "mode": "use"}
        for potion in sorted(ANYTIME - {"FOUL_POTION"})
        for room in ("rest", "map", "reward", "shop")
    ]
    cases += [
        {"id": "foul-real-merchant", "potion": "FOUL_POTION", "room": "shop", "mode": "use"},
        {
            "id": "foul-inventory-roundtrip",
            "potion": "FOUL_POTION",
            "room": "shop",
            "mode": "roundtrip",
        },
        {
            "id": "foul-fake-merchant",
            "potion": "FOUL_POTION",
            "room": "event",
            "event": "FAKE_MERCHANT",
            "mode": "use",
        },
        {
            "id": "foul-fake-inventory-roundtrip",
            "potion": "FOUL_POTION",
            "room": "event",
            "event": "FAKE_MERCHANT",
            "mode": "roundtrip",
        },
        {
            "id": "foul-unavailable-rest",
            "potion": "FOUL_POTION",
            "room": "rest",
            "mode": "disabled",
        },
        {
            "id": "combat-only-unavailable",
            "potion": "FORTIFIER",
            "room": "rest",
            "mode": "disabled",
        },
        {
            "id": "same-slot-stale-copy",
            "potion": "FOUL_POTION",
            "room": "shop",
            "mode": "stale_potion",
        },
        {"id": "stale-merchant", "potion": "FOUL_POTION", "room": "shop", "mode": "stale_target"},
        {"id": "stale-room", "potion": "FOUL_POTION", "room": "shop", "mode": "stale_room"},
    ]
    return cases


def player(observation: dict[str, Any]) -> dict[str, Any]:
    return dict(observation["snapshot"]["persistent"]["content"]["player"])


def check_effect(spec: dict[str, Any], before: dict[str, Any], after: dict[str, Any]) -> None:
    """Assertions qualify effects; they never implement them or supply learning labels."""
    first, last = player(before), player(after)
    potion = spec["potion"]
    if potion != "ENTROPIC_BREW" and any(row["definition_id"] == potion for row in last["potions"]):
        raise ValueError("Used native potion remains in belt")
    if potion in {"AMBERGRIS", "BLOOD_POTION"}:
        healed = first["max_hp"] * (0.5 if potion == "AMBERGRIS" else 0.2)
        if last["hp"] != min(first["max_hp"], first["hp"] + healed):
            raise ValueError("Native healing effect differs")
    elif potion == "FRUIT_JUICE":
        if (last["hp"], last["max_hp"]) != (first["hp"] + 5, first["max_hp"] + 5):
            raise ValueError("Native maximum HP effect differs")
    elif potion == "ENTROPIC_BREW":
        if len(last["potions"]) != last["max_potion_slots"]:
            raise ValueError("Native Entropic Brew did not refill belt")
    elif spec.get("event") == "FAKE_MERCHANT":
        if (
            after["snapshot"]["interaction"]["kind"] != "combat_turn"
            or last["gold"] != first["gold"]
        ):
            raise ValueError("Fake merchant must start native combat instead of award shop gold")
    elif last["gold"] != first["gold"] + 100:
        raise ValueError("Real merchant native Foul Potion gold differs")


def load_potion_config(
    q: EngineQualificationConfig, path: Path, *, saved: bool = False
) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    if (
        cfg.get("schema_version") != "native-potion-checks-config-v1"
        or cfg.get("qualification_config_id") != q.config_id
        or cfg.get("cases") != potion_cases()
        or (not saved and cfg.get("implementation_sha256") != potion_implementation(q.root))
        or (not saved and cfg.get("helpers_sha256") != worker_helpers(q.root, SCRIPT))
        or cfg.get("privileged_fixture") is not True
        or cfg.get("training_allowed") is not False
        or cfg.get("maximum_wall_seconds") != 180
    ):
        raise ValueError("Expected a frozen finite native potion check recipe")
    _private_path(q.root, cfg["workspace"])
    return dict(cfg)


def run_potion_checks(q: EngineQualificationConfig, path: Path, *, node: Path) -> dict[str, Any]:
    cfg = load_potion_config(q, path)
    _require_native_launch_support()
    if _running_games() or not node.is_file():
        raise ValueError("Close the game and use the local Node runtime")
    inputs = _run_inputs(q, q.root / cfg["run_config"])
    if manifest_identifier(inputs["recipe"]) != cfg["run_config_id"]:
        raise ValueError("Native potion run input changed")
    output = _private_path(q.root, cfg["workspace"])
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "recipe.json", cfg)
    source = output / "matching-python-source"
    source.mkdir()
    for name in IMPLEMENTATION:
        (source / name).write_bytes((q.root / "src/spireshift" / name).read_bytes())
    started = time.monotonic()
    rows: list[dict[str, Any]] = []
    error = None
    catalog_ids: list[str] = []
    try:
        for index, spec in enumerate(cfg["cases"]):
            if time.monotonic() - started > cfg["maximum_wall_seconds"] - 20:
                raise TimeoutError("Finite potion batch wall cap")
            worker = EngineWorker(
                q, inputs, output / spec["id"], node, cfg["helpers_sha256"], script=SCRIPT
            )
            observations: list[dict[str, Any]] = []
            try:
                if not rows:
                    catalog = worker.request("catalog")
                    catalog_ids = sorted(
                        m["id"]
                        for m in catalog["models"]
                        if m.get("usage") == "AnyTime" and not m["is_mock"]
                    )
                    if {value.removeprefix("POTION.") for value in catalog_ids} != ANYTIME:
                        raise ValueError("Native AnyTime potion inventory changed")
                else:
                    worker.request("mount", seed=f"SP1RESH1FTP0T10N{index + 100:03}")
                current = worker.request(
                    "potion_fixture",
                    potions=[spec["potion"]],
                    room=spec["room"],
                    event=spec.get("event"),
                )

                def step_label(
                    label: str,
                    worker: EngineWorker = worker,
                    observations: list[dict[str, Any]] = observations,
                ) -> dict[str, Any]:
                    nonlocal current
                    actions = current["snapshot"]["bound_actions"]["actions"]
                    chosen = next(i for i, a in enumerate(actions) if a["label"] == label)
                    observations.append(current)
                    current = worker.request(
                        "step", snapshot_id=current["snapshot"]["snapshot_id"], action_index=chosen
                    )
                    return current

                if spec["mode"] == "roundtrip":
                    step_label("Open inventory")
                    if any(
                        a["verb"] == "use" for a in current["snapshot"]["bound_actions"]["actions"]
                    ):
                        raise ValueError("Foul Potion target must disappear inside inventory")
                    step_label("Close inventory")
                actions = current["snapshot"]["bound_actions"]["actions"]
                if spec["mode"] == "disabled":
                    if any(a["verb"] == "use" for a in actions):
                        raise ValueError("Natively unavailable potion was advertised")
                    step_label(
                        next(a["label"] for a in actions if a["label"].startswith("Discard "))
                    )
                    if player(current)["potions"]:
                        raise ValueError("Native discard did not remove current belt copy")
                elif spec["mode"].startswith("stale_"):
                    before = current
                    # Extract only the exact private native operands from the private journal.
                    with gzip.open(
                        worker.workspace / "private-transcript.jsonl.gz", "rt"
                    ) as stream:
                        native_rows = [json.loads(line) for line in stream]
                    state = next(
                        row["response"]
                        for row in reversed(native_rows)
                        if row["response"].get("decision") == "merchant_approach"
                    )
                    potion = state["player"]["potions"][0]
                    args = {
                        "potion_slot": potion["slot"],
                        "potion_ref": potion["native_ref"],
                        "room_ref": state["room_ref"],
                        "target_ref": state["merchant_ref"],
                    }
                    field = {
                        "stale_potion": "potion_ref",
                        "stale_target": "target_ref",
                        "stale_room": "room_ref",
                    }[spec["mode"]]
                    args[field] = "KNOWN_STALE_DIAGNOSTIC_OPERAND"
                    rejected = worker.request(
                        "reject_potion_action",
                        payload={"cmd": "action", "action": "use_potion", "args": args},
                        expected_error="no longer",
                    )
                    if rejected.get("rejected") is not True:
                        raise ValueError("Stale potion operand was not rejected")
                    retirement = worker.retire(
                        "expected precommit malformed-operand negative control"
                    )
                    observations.append(before)
                    atomic_json(
                        worker.workspace / "negative-control.json",
                        {"rejection": rejected, "retirement": retirement},
                    )
                else:
                    before = current
                    step_label(next(a["label"] for a in actions if a["verb"] == "use"))
                    check_effect(spec, before, current)
                observations.append(current)
                for observation in observations:
                    _verify_saved_observation(
                        observation, observation["snapshot"]["session"]["runtime_instance_id"]
                    )
                if not worker.closed:
                    worker.close()
                evidence = [
                    {"path": str(p.relative_to(worker.workspace)), "sha256": _sha_file(p)}
                    for p in sorted(worker.workspace.rglob("*"))
                    if p.is_file()
                ]
                row = _sealed(
                    {
                        "spec": spec,
                        "status": "native_potion_case_pass",
                        "evidence_files": evidence,
                        "public_observations": len(observations),
                        "privileged_fixture": True,
                        "training_allowed": False,
                    }
                )
                atomic_json(worker.workspace / "result.json", row)
                rows.append(row)
            finally:
                worker.stop()
        checks = immutable_checks(q, inputs)
        if not all(checks.values()):
            raise ValueError("Potion diagnostics changed immutable shared inputs")
    except (ValueError, TimeoutError, OSError, StopIteration) as exc:
        error = f"{type(exc).__name__}: {exc}"
        checks = {"incomplete": False}
    report = _sealed(
        {
            "schema_version": "native-potion-checks-v1",
            "config_id": manifest_identifier(cfg),
            "input_config_id": inputs["recipe"]["input_config_id"],
            "build_report_id": inputs["inputs"]["build_report_id"],
            "status": "native_potion_checks_pass"
            if error is None
            else "native_potion_checks_incomplete",
            "planned_cases": len(cfg["cases"]),
            "completed_cases": len(rows),
            "not_attempted_cases": len(cfg["cases"]) - len(rows),
            "case_reports": [r["report_id"] for r in rows],
            "native_anytime_potion_ids": catalog_ids,
            "checks": checks,
            "privileged_fixture": True,
            "full_run_attempts": 0,
            "optimizer_steps": 0,
            "training_allowed": False,
            "game_apps_created": 0,
            "wall_seconds": time.monotonic() - started,
            "error": error,
            "claim_scope": (
                "finite_native_outside_combat_potion_effects_current_belt_"
                "and_real_and_fake_merchant_targets_only"
            ),
        }
    )
    atomic_json(output / "summary.json", report)
    return report


def verify_potion_checks(q: EngineQualificationConfig, path: Path) -> dict[str, Any]:
    cfg = load_potion_config(q, path, saved=True)
    output = _private_path(q.root, cfg["workspace"])
    report = _read_sealed(output / "summary.json")
    for name, digest in cfg["implementation_sha256"].items():
        if _sha_file(output / "matching-python-source" / name) != digest:
            raise ValueError("Frozen potion checker Python source changed")
    if (
        report["config_id"] != manifest_identifier(cfg)
        or report["status"] != "native_potion_checks_pass"
        or report["completed_cases"] != len(cfg["cases"])
        or report["not_attempted_cases"]
        or not all(report["checks"].values())
    ):
        raise ValueError("Native potion diagnostics did not pass every planned case")
    ids = []
    for spec in cfg["cases"]:
        workspace = output / spec["id"]
        case = _read_sealed(workspace / "result.json")
        if case["spec"] != spec or case["status"] != "native_potion_case_pass":
            raise ValueError("Potion saved-case identity changed")
        for ref in case["evidence_files"]:
            if _sha_file(workspace / ref["path"]) != ref["sha256"]:
                raise ValueError("Potion diagnostic source/trace evidence changed")
        ids.append(case["report_id"])
    if ids != report["case_reports"]:
        raise ValueError("Potion evidence denominator changed")
    return {
        "valid": True,
        "report_id": report["report_id"],
        "verified_cases": len(ids),
        "games_launched": 0,
        "training_allowed": False,
    }
