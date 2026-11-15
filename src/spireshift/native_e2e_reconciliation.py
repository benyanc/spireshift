"""Reproject qualified historical prefixes with current inputs and unchanged numerical players."""

from __future__ import annotations

import argparse
import gzip
import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_e2e_contract import equivalent_replayed_choice
from spireshift.native_e2e_inputs import load
from spireshift.native_flow_inputs_v12 import load as historical_load
from spireshift.native_flow_verification_v12 import records, same, verify_host
from spireshift.native_live_inputs import prepare
from spireshift.native_live_policy import LivePolicy
from spireshift.native_shared_transport import JsonLines
from spireshift.native_structured_state import load as load_state


def replay_host(
    root: Path,
    ctx: dict[str, Any],
    unit: dict[str, Any],
    host: str,
    model: Any,
    adam: Any,
    output: Path,
    deadline: float,
) -> dict[str, Any]:
    old_cfg = json.loads(verified(root, unit["recipe"]).read_text())
    old_ctx = historical_load(root, root / unit["recipe"]["path"])
    report = identified(verified(root, unit["report"]))
    check_sources(root, report["sources"])
    check_sources(root, report["evidence"])
    witness = identified(verified(root, unit["verification"]))
    if (
        report["status"] != "live_checkpoint_delivery_control_pass"
        or witness.get("valid") is not True
        or witness.get("source_report_id") != report["report_id"]
        or witness.get("verifier_sha256")
        != _sha_file(root / "src/spireshift/native_flow_verification_v12.py")
        or not report["full_prefix_input_equivalence"]
    ):
        raise ValueError("Only completed passing prefixes may supply inherited evidence")
    case = report["cases"][0]
    directory = root / old_cfg["workspace"] / case["key"] / host
    # Actual old choices/receipts are independently verified under their original source.
    delivered = verify_host(root, old_ctx, case, host, directory, output, deadline)
    old_model, old_adam, _ = load_state(
        root / old_cfg["workspace"] / f"imports/player-{case['player']}.json"
    )
    if old_model.weights() != model.weights() or old_adam.as_dict() != adam.as_dict():
        raise ValueError("Historical and current numerical players/Adam differ")
    policy = LivePolicy(model, ctx["score"], case["seed"])
    converter = JsonLines(
        root,
        [ctx["config"]["node"], str(root / "scripts/engine-shared-input-v15.mjs")],
        output / f"{unit['kind']}-{host}-current.log",
    )
    raw = (
        iter(records(directory / "worker/public-observations.jsonl.gz"))
        if host == "native"
        else None
    )
    source = directory / ("shared-public.jsonl.gz" if host == "native" else "live-public.jsonl.gz")
    projection_file = output / f"{unit['kind']}-{host}-projections.jsonl.gz"
    frame = choice = None
    count = transient = 0
    families: set[str] = set()
    try:
        with gzip.open(projection_file, "wt") as projections:
            for row in records(source):
                if row["kind"] == "policy_input":
                    capture = next(raw) if raw is not None else row
                    frame = converter.project(capture["snapshot"], capture["reads"], None, deadline)
                    old_frame = row["frame"]
                    if (
                        frame["input_digest"] != old_frame["input_digest"]
                        or not same(frame["public_input"], old_frame["public_input"])
                        or not same(frame["actions"], old_frame["actions"])
                    ):
                        raise ValueError(
                            "Current projection changed a historical input or complete binding map"
                        )
                    families.add(frame["source_family"])
                    relics = frame["public_input"]["context"]["persistent"]["player"]["relics"]
                    transient += any(
                        r.get("definition_id") == "HAPPY_FLOWER" and r.get("counter") == 3
                        for r in relics
                    )
                    if frame["terminal"]:
                        raise ValueError(
                            "Declared passing-prefix bank unexpectedly contains an ending"
                        )
                    choice = policy.choose(frame)
                    projections.write(
                        json.dumps(
                            {
                                "input_digest": frame["input_digest"],
                                "menu_keys": [a["key"] for a in frame["actions"]],
                            }
                        )
                        + "\n"
                    )
                elif row["kind"] == "policy_choice":
                    saved = {k: v for k, v in row["choice"].items() if k != "command"}
                    if choice is None or not equivalent_replayed_choice(choice, saved):
                        raise ValueError(
                            "Frozen sampled action, RNG, log probability or value changed"
                        )
                    if (
                        saved["model_id"] != old_model.model_id
                        or choice["model_id"] != model.model_id
                    ):
                        raise ValueError("Wrong historical/current player identity")
                    if host == "native":
                        ack = {**row["receipt"], "binding_id": choice["binding_id"]}
                        policy.acknowledge(ack)
                        converter.commit(choice, ack, deadline)
                        choice = None
                        count += 1
                elif host == "official" and row["kind"] == "receipt" and choice is not None:
                    receipt = row["receipt"]
                    ack = {
                        "binding_id": choice["binding_id"],
                        "delivery": receipt["delivery"],
                        "bound_action_id": receipt["action"]["bound_action_id"],
                        "runtime_instance_id": receipt["attribution"]["runtime_instance_id"],
                        "before_snapshot_id": row["before_snapshot_id"],
                        "successor_snapshot_id": row.get("semantic_successor_snapshot_id")
                        or receipt.get("successor", {}).get("snapshot_id"),
                    }
                    policy.acknowledge(ack)
                    converter.commit(choice, ack, deadline)
                    choice = None
                    count += 1
        if count != delivered or policy.pending is not None or transient:
            raise ValueError(
                "Incomplete replay or a historical boundary affected by the new counter guard"
            )
        converter.close()
    finally:
        converter.stop()
    return {
        "host": host,
        "verified_historical_deliveries": delivered,
        "current_input_and_choice_replays": count,
        "observed_families": sorted(families),
        "HappyFlower_transient_policy_boundaries": transient,
        "versioned_binding_id_rebased_only_in_diagnostic_acknowledgements": True,
        "raw_receipts_modified": False,
        "current_connector_live_effects_claimed": False,
        "source_report_id": report["report_id"],
        "source_verifier_id": witness["report_id"],
    }


def reconcile(root: Path, recipe: Path) -> dict[str, Any]:
    started = time.monotonic()
    ctx = load(root, recipe)
    cfg = ctx["config"]
    if cfg["stage"] != "saved_reconciliation":
        raise ValueError("Saved reconciliation cannot launch a live plan")
    output = root / cfg["workspace"]
    if (output / "report.json").exists():
        saved = identified(output / "report.json")
        if saved["config_id"] != manifest_identifier(cfg):
            raise ValueError("Preserve another reconciliation")
        check_sources(root, saved["sources"])
        check_sources(root, saved["evidence"])
        return saved
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "active.json", {"config_id": manifest_identifier(cfg), "new_games": 0})
    imported = prepare(root, ctx)
    units = []
    for unit in cfg["historical_units"]:
        directory = output / unit["kind"]
        directory.mkdir()
        old_cfg = json.loads(verified(root, unit["recipe"]).read_text())
        player = old_cfg["cases"][0]["player"]
        model, adam, _ = imported[player]
        hosts = [
            replay_host(root, ctx, unit, host, model, adam, directory, started + 220)
            for host in ("native", "official")
        ]
        with (
            gzip.open(directory / f"{unit['kind']}-native-projections.jsonl.gz", "rt") as left,
            gzip.open(directory / f"{unit['kind']}-official-projections.jsonl.gz", "rt") as right,
        ):
            if list(left) != list(right):
                raise ValueError("Reprojected matched prefixes differ between hosts")
        units.append({"kind": unit["kind"], "player": player, "hosts": hosts})
        print(f"Reconciled saved control {len(units)}/4: {unit['kind']}; no games", flush=True)
    protected = json.loads(verified(root, cfg["protection"]).read_text())
    check_sources(root, protected)
    check_sources(root, ctx["sources"])
    report = {
        "schema_version": "native-e2e-saved-reconciliation-v1",
        "status": "saved_reconciliation_pass",
        "config_id": manifest_identifier(cfg),
        "environment_id": ctx["environment"]["manifest_id"],
        "units": units,
        "source_delta": cfg["expected_source_delta"],
        "verified_historical_deliveries": sum(
            h["verified_historical_deliveries"] for u in units for h in u["hosts"]
        ),
        "current_input_and_choice_replays": sum(
            h["current_input_and_choice_replays"] for u in units for h in u["hosts"]
        ),
        "current_connector_live_effects_claimed": False,
        "final_uncaptured_successor_qualified": False,
        "sources": ctx["sources"],
        "evidence": {
            str(p.relative_to(root)): _sha_file(p)
            for p in output.rglob("*")
            if p.is_file() and p.name != "active.json"
        },
        "new_games": 0,
        "optimizer_updates": 0,
        "original_weights_and_all_Adam_unchanged": True,
        "training_allowed": False,
        "automatic_follow_up": False,
        "wall_seconds": time.monotonic() - started,
    }
    report["report_id"] = manifest_identifier(report)
    atomic_json(output / "report.json", report)
    (output / "active.json").rename(output / "complete.json")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    args = parser.parse_args()
    report = reconcile(Path.cwd(), args.recipe.resolve())
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in {"sources", "evidence", "source_delta", "units"}
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
