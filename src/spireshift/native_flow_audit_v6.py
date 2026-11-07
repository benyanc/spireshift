"""Bounded recorded-input preservation and frozen inference checks; no game launch."""

from __future__ import annotations

import argparse
import gzip
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_inputs_v6 import load, prepare
from spireshift.native_live_policy import LivePolicy
from spireshift.native_shared_transport import JsonLines


def audit(root: Path, recipe: Path) -> dict[str, Any]:
    started = time.monotonic()
    ctx = load(root, recipe)
    cfg = ctx["config"]
    if cfg["stage"] != "saved_only_checks":
        raise ValueError("The layout audit cannot launch games")
    workspace = root / cfg["workspace"]
    if workspace.exists():
        if not (workspace / "completed.json").exists():
            raise ValueError("Preserve the incomplete saved-layout audit")
        report = identified(workspace / "report.json")
        if report["config_id"] != manifest_identifier(cfg):
            raise ValueError("Saved layout result has different settings")
        check_sources(root, report["sources"])
        check_sources(root, report["evidence"])
        return report
    protected = json.loads(verified(root, cfg["protection_receipt"]).read_text())
    check_sources(root, protected)
    workspace.mkdir(parents=True)
    atomic_json(workspace / "active.json", {"config_id": manifest_identifier(cfg)})
    for name in cfg["sources"]:
        destination = workspace / "source-at-launch" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((root / name).read_bytes())
    atomic_json(workspace / "source-at-launch/recipe.json", cfg)
    imported = prepare(root, ctx)
    before = {
        p: (manifest_identifier(m.as_dict()), manifest_identifier(a.as_dict()))
        for p, (m, a, _) in imported.items()
    }
    service = JsonLines(
        root,
        [cfg["node"], str(root / "scripts/audit-selection-flows-v4.mjs")],
        workspace / "audit-stderr.log",
    )
    sequence = 0

    def request(body: dict[str, Any]) -> dict[str, Any]:
        nonlocal sequence
        sequence += 1
        service.send({"request_id": sequence, **body})
        response = service.receive(started + 210)
        if response.get("request_id") != sequence:
            raise ValueError("Saved-layout service lost frame ownership")
        return response

    counts: Counter[str] = Counter()
    rules: Counter[str] = Counter()
    problems: list[dict[str, Any]] = []
    total = converted = roundtrips = bindings = probes = 0

    def check_frame(response: dict[str, Any], key: str) -> None:
        nonlocal converted, roundtrips, bindings, probes
        if response.get("ok") is not True:
            problems.append({"key": key, "error": response.get("error")})
            return
        frame = response["frame"]
        converted += 1
        roundtrips += response["exact_round_trip"]
        bindings += response["bindings_preserved"] and response["complete_menu"]
        rules.update(frame["layout_evidence"]["rules"])
        if frame["terminal"]:
            return
        for player, (model, _, _) in imported.items():
            try:
                choice = LivePolicy(model, ctx["score"], "SAVEDLAYOUTAUDIT").choose(frame)
                if not 0 <= choice["action_index"] < len(frame["actions"]):
                    raise ValueError("Frozen choice escaped the complete menu")
                probes += 1
            except (ValueError, KeyError, TypeError) as error:
                problems.append({"key": key, "player": player, "error": str(error)})

    try:
        with gzip.open(workspace / "frames.jsonl.gz", "wt") as output:
            for capture in cfg["captures"]:
                path = verified(root, capture)
                ordinal = 0
                with gzip.open(path, "rt") as source:
                    for line in source:
                        if len(line) > 16_000_000 or time.monotonic() > started + 205:
                            raise ValueError("Saved-layout stream/whole-job cap")
                        row = json.loads(line)
                        if (
                            "snapshot" not in row
                            or "reads" not in row
                            or capture["record_kind"] is not None
                            and row.get("kind") != capture["record_kind"]
                        ):
                            continue
                        total += 1
                        if total > cfg["expected_saved_frames"] or total > 6000:
                            raise ValueError("Finite saved-layout frame limit exceeded")
                        group = f"{capture['host']}/{row['snapshot']['interaction']['kind']}"
                        counts[group] += 1
                        result = request({"snapshot": row["snapshot"], "reads": row["reads"]})
                        key = f"{capture['path']}#{ordinal}"
                        check_frame(result, key)
                        output.write(
                            json.dumps(
                                {
                                    "key": key,
                                    "converted": result.get("ok") is True,
                                    "input_id": result.get("frame", {}).get("input_digest"),
                                    "error": result.get("error"),
                                }
                            )
                            + "\n"
                        )
                        ordinal += 1
                if ordinal != capture["expected_frames"]:
                    problems.append(
                        {
                            "code": "record_selection_count_mismatch",
                            "capture": capture["path"],
                            "expected": capture["expected_frames"],
                            "actual": ordinal,
                        }
                    )
        if total != cfg["expected_saved_frames"]:
            problems.append(
                {
                    "code": "whole_bank_count_mismatch",
                    "expected": cfg["expected_saved_frames"],
                    "actual": total,
                }
            )
        bank = request({"command": "case_bank"})
        if bank.get("ok") is not True:
            raise ValueError("Generated layout envelopes failed")
        for case in bank["cases"]:
            check_frame(
                {
                    "ok": True,
                    "frame": case["frame"],
                    "exact_round_trip": case["exact_round_trip"],
                    "bindings_preserved": case["bindings_preserved"],
                    "complete_menu": case["complete_menu"],
                },
                case["key"],
            )
        service.close()
    finally:
        service.stop()
    after = {
        p: (manifest_identifier(m.as_dict()), manifest_identifier(a.as_dict()))
        for p, (m, a, _) in imported.items()
    }
    if before != after:
        raise ValueError("Frozen audit modified a player or Adam state")
    check_sources(root, protected)
    check_sources(root, ctx["sources"])
    expected = total + len(bank["cases"])
    report = {
        "schema_version": "native-input-layout-audit-v1",
        "status": "saved_input_layout_pass"
        if not problems and converted == roundtrips == bindings == expected
        else "saved_input_layout_blocked",
        "config_id": manifest_identifier(cfg),
        "environment_id": ctx["environment"]["manifest_id"],
        "implementation_id": manifest_identifier(cfg["implementation_sha256"]),
        "helpers_id": manifest_identifier(cfg["helpers_sha256"]),
        "saved_frames": total,
        "artificial_envelopes": len(bank["cases"]),
        "converted_frames_and_envelopes": converted,
        "exact_round_trips": roundtrips,
        "complete_raw_action_bindings_preserved": bindings,
        "frozen_policy_input_probes": probes,
        "families": dict(counts),
        "rules": dict(rules),
        "issues": problems,
        "protected_prior_files": len(protected),
        "original_full_weights_and_all_Adam_unchanged": True,
        "games_launched": 0,
        "optimizer_updates": 0,
        "game_apps_created": 0,
        "training_allowed": False,
        "full_input_equivalence_granted": False,
        "live_compatibility_granted": False,
        "old_missing_event_metadata_not_synthesized": True,
        "later_divergent_states_used_as_matched_pairs": False,
        "full_run_objective": ctx["score"].evaluation_objective.as_dict(),
        "sources": ctx["sources"],
        "evidence": {
            **{c["path"]: c["sha256"] for c in cfg["captures"]},
            cfg["protection_receipt"]["path"]: _sha_file(root / cfg["protection_receipt"]["path"]),
            str((workspace / "frames.jsonl.gz").relative_to(root)): _sha_file(
                workspace / "frames.jsonl.gz"
            ),
        },
        "wall_seconds": time.monotonic() - started,
    }
    report["report_id"] = manifest_identifier(report)
    atomic_json(workspace / "report.json", report)
    (workspace / "active.json").rename(workspace / "completed.json")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    args = parser.parse_args()
    try:
        report = audit(Path.cwd(), args.recipe.resolve())
        print(
            json.dumps(
                {
                    k: v
                    for k, v in report.items()
                    if k not in {"sources", "evidence", "families", "rules"}
                },
                indent=2,
            )
        )
        return 0 if report["status"] == "saved_input_layout_pass" else 2
    except (ValueError, OSError) as error:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
