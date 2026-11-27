"""Source-derived inventory, all-frame diagnostics and concrete producer comparisons."""

from __future__ import annotations

import argparse
import gzip
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_compatibility_contract import difference_paths, verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_interface_audit import inventory
from spireshift.native_live_inputs import prepare
from spireshift.native_live_policy import LivePolicy
from spireshift.native_shared_transport import JsonLines
from spireshift.native_systematic_inputs_v1 import load


def coverage_ledger(
    kinds: list[str], observed: dict[str, int], paired: dict[str, int]
) -> list[dict[str, Any]]:
    return [
        {
            "surface": kind,
            "inventoried": True,
            "saved_frames": observed.get(kind, 0),
            "actual_producer_pairs": paired.get(kind, 0),
            "live_effects_qualified": False,
            "remaining": ["live transition/effect comparison"]
            + ([] if observed.get(kind, 0) else ["actual saved runtime observation"])
            + ([] if paired.get(kind, 0) else ["concrete paired producer case"]),
        }
        for kind in kinds
    ]


def audit(root: Path, recipe: Path) -> dict[str, Any]:
    started = time.monotonic()
    ctx = load(root, recipe)
    cfg = ctx["config"]
    if cfg["stage"] != "short_checks":
        raise ValueError("Use the separate short saved comparison recipe")
    output = root / cfg["audit_workspace"]
    if not output.resolve().is_relative_to(root / "artifacts/native-systematic-comparison"):
        raise ValueError("Keep the saved audit in its separate evidence workspace")
    final = output / "report.json"
    if final.exists():
        saved = identified(final)
        if saved["config_id"] != manifest_identifier(cfg):
            raise ValueError("Preserve a different systematic audit")
        check_sources(root, saved["sources"])
        check_sources(root, saved["evidence"])
        return saved
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "active.json", {"config_id": manifest_identifier(cfg)})
    check_sources(root, json.loads(verified(root, cfg["protection"]).read_text()))
    source_inventory = inventory([verified(root, item) for item in cfg["inventory_sources"]])
    compiled = json.loads(verified(root, cfg["compiled_records"]).read_text())
    if (
        source_inventory != cfg["expected_source_inventory"]
        or compiled != cfg["expected_compiled_records"]
    ):
        raise ValueError("Source schema changed: regenerate and review the coverage contract")
    atomic_json(output / "source-inventory.json", source_inventory)
    atomic_json(output / "compiled-record-properties.json", compiled)
    imported = prepare(root, ctx)
    original_states = {
        key: (model.as_dict(), adam.as_dict()) for key, (model, adam, _) in imported.items()
    }
    actor_probes = 0
    probed: set[str] = set()
    service = JsonLines(
        root,
        [cfg["node"], str(root / "scripts/engine-systematic-comparison-v1.mjs")],
        output / "comparison-stderr.log",
    )
    problems: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    fields: dict[str, set[str]] = defaultdict(set)
    sequence = frames = 0

    def request(body: dict[str, Any]) -> dict[str, Any]:
        nonlocal sequence
        sequence += 1
        service.send({"request_id": sequence, **body})
        result = service.receive(started + 225)
        if result.get("request_id") != sequence:
            raise ValueError("Comparison response lost ownership")
        return result

    try:
        generated = request(
            {
                "command": "generated",
                "vectors": json.loads(verified(root, cfg["producer_vectors"]).read_text()),
            }
        )
        if generated.get("ok") is not True:
            raise ValueError(str(generated))
        problems.extend(row for row in generated["checks"] if not row["passed"])
        atomic_json(output / "generated-checks.json", generated)
        with gzip.open(output / "frame-checks.jsonl.gz", "wt") as journal:
            for capture in cfg["captures"]:
                count = 0
                with gzip.open(verified(root, capture), "rt") as stream:
                    for line in stream:
                        if len(line) > 16_000_000 or time.monotonic() > started + 220:
                            raise TimeoutError("Finite saved comparison cap")
                        row = json.loads(line)
                        if (
                            "snapshot" not in row
                            or "reads" not in row
                            or (
                                capture["record_kind"] is not None
                                and row.get("kind") != capture["record_kind"]
                            )
                        ):
                            continue
                        kind = row["snapshot"]["interaction"]["kind"]
                        result = request({"snapshot": row["snapshot"], "reads": row["reads"]})
                        key = f"{capture['path']}#{count}"
                        count += 1
                        frames += 1
                        counts[kind] += 1
                        if result.get("ok") is not True:
                            problems.append({"key": key, "error": result.get("error")})
                        else:
                            fields[kind].update(result["fields"])
                            if kind not in probed and not result["frame"]["terminal"]:
                                for model, _, _ in imported.values():
                                    LivePolicy(model, ctx["score"], "SAVEDCOMPAR1S0N").choose(
                                        result["frame"]
                                    )
                                    actor_probes += 1
                                probed.add(kind)
                        journal.write(
                            json.dumps(
                                {
                                    "key": key,
                                    "surface": kind,
                                    "ok": result["ok"],
                                    "error": result.get("error"),
                                }
                            )
                            + "\n"
                        )
                if count != capture["expected_frames"]:
                    problems.append(
                        {"key": capture["path"], "error": "capture denominator changed"}
                    )
        # Matched historical states only. Never align later states after a difference.
        pairs = []
        for item in cfg["matched_rest_states"]:
            values = []
            for side in ("native", "official"):
                ref = item[side]
                with gzip.open(verified(root, ref), "rt") as stream:
                    candidates = (json.loads(line) for line in stream)
                    candidates = (
                        row
                        for row in candidates
                        if "snapshot" in row
                        and "reads" in row
                        and (ref["record_kind"] is None or row.get("kind") == ref["record_kind"])
                    )
                    raw = next(
                        row for index, row in enumerate(candidates) if index == ref["ordinal"]
                    )
                projected = request({"snapshot": raw["snapshot"], "reads": raw["reads"]})
                if projected.get("ok") is not True:
                    raise ValueError(f"Saved rest witness cannot convert: {projected}")
                values.append(projected["frame"])
            differences = difference_paths(values[0]["public_input"], values[1]["public_input"])
            keys_equal = [a["key"] for a in values[0]["actions"]] == [
                a["key"] for a in values[1]["actions"]
            ]
            pairs.append(
                {
                    "key": item["key"],
                    "input_differences": differences,
                    "menu_keys_equal": keys_equal,
                }
            )
            if differences or not keys_equal:
                problems.append(
                    {
                        "key": item["key"],
                        "error": "matched rest witness differs",
                        "paths": differences,
                    }
                )
        service.close()
    finally:
        service.stop()
    atomic_json(output / "matched-rest-states.json", pairs)
    ledger = coverage_ledger(
        source_inventory["official_surface_kinds"], dict(counts), {"rest_site": 7}
    )
    atomic_json(output / "coverage-ledger.json", ledger)
    atomic_json(output / "observed-field-types.json", {k: sorted(v) for k, v in fields.items()})
    atomic_json(output / "all-gaps.json", problems)
    check_sources(root, json.loads(verified(root, cfg["protection"]).read_text()))
    if original_states != {
        key: (model.as_dict(), adam.as_dict()) for key, (model, adam, _) in imported.items()
    }:
        raise ValueError("Read-only actor probes changed model or optimizer")
    report = {
        "schema_version": "native-systematic-comparison-audit-v1",
        "config_id": manifest_identifier(cfg),
        "status": "short_comparison_checks_pass" if not problems else "comparison_gaps_found",
        "saved_frames": frames,
        "generated_checks": len(generated["checks"]),
        "frozen_actor_probes": actor_probes,
        "matched_rest_states": len(pairs),
        "compiled_records": len(compiled),
        "compiled_properties": sum(len(row["properties"]) for row in compiled),
        "inventoried_surfaces": len(ledger),
        "problems": len(problems),
        "live_effects_qualified": False,
        "all_possible_interactions_proved": False,
        "sources": ctx["sources"],
        "evidence": {},
        "optimizer_updates": 0,
        "new_games": 0,
        "training_allowed": False,
        "checkpoint_promoted": False,
        "original_weights_and_all_Adam_unchanged": True,
        "wall_seconds": time.monotonic() - started,
    }
    report["evidence"] = {
        str(p.relative_to(root)): _sha_file(p)
        for p in output.rglob("*")
        if p.is_file() and p.name != "active.json"
    }
    report["report_id"] = manifest_identifier(report)
    atomic_json(final, report)
    (output / "active.json").rename(output / "complete.json")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    args = parser.parse_args()
    result = audit(Path.cwd(), args.recipe.resolve())
    print(
        json.dumps({k: v for k, v in result.items() if k not in {"sources", "evidence"}}, indent=2)
    )
    return 0 if result["problems"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
