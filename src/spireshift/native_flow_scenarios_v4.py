"""Bounded public starting-menu discovery; no action is submitted and no fitting occurs."""

from __future__ import annotations

import argparse
import gzip
import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_flow_worker import RelicWorker
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_inputs import load, prepare
from spireshift.native_live_policy import LivePolicy
from spireshift.native_shared_transport import JsonLines


def discover(root: Path, recipe: Path, output: Path) -> dict[str, Any]:
    ctx = load(root, recipe)
    if ctx["config"]["stage"] != "saved_only_checks":
        raise ValueError("Use the saved, qualified source tuple for observation only")
    if output.exists() or not output.resolve().is_relative_to(
        root / "artifacts/native-selection-flows"
    ):
        raise ValueError("Use a new isolated scenario-observation directory")
    output.mkdir(parents=True)
    atomic_json(output / "active.json", {"action_submissions": 0, "training_allowed": False})
    imported = prepare(root, ctx)
    started = time.monotonic()
    rows: list[dict[str, Any]] = []
    for number in range(335, 351):
        if time.monotonic() - started > 90:
            break
        seed = f"SP1RESH1FTFL0W{number}"
        worker = RelicWorker(
            ctx["qualification"],
            ctx["native"],
            output / seed,
            Path(ctx["config"]["node"]),
            ctx["native_helpers"],
        )
        converter = JsonLines(
            root,
            [ctx["config"]["node"], str(root / "scripts/engine-shared-input-v10.mjs")],
            output / f"{seed}.log",
        )
        try:
            current = worker.request("mount", seed=seed, timeout=25)
            frame = converter.project(current["snapshot"], current["reads"], None, started + 110)
            choice = LivePolicy(imported[2][0], ctx["score"], seed).choose(frame)
            candidate = frame["public_input"]["candidates"][choice["action_index"]]
            shutdown = worker.close()
            converter.close()
            # A root is only observed: no step/submit/acknowledge is ever invoked.
            row = {
                "seed": seed,
                "player": 2,
                "selected_label": candidate["label"],
                "input_digest": frame["input_digest"],
                "action_submissions": 0,
                "shutdown": shutdown,
                "snapshot": current,
                "choice": choice,
            }
            atomic_json(output / f"{seed}.json", row)
            rows.append({k: v for k, v in row.items() if k not in {"snapshot", "choice"}})
            print(
                f"Observed starting menu {len(rows)}/16: {candidate['label']}; "
                "no action submitted.",
                flush=True,
            )
            if candidate["label"] == "Scroll Boxes":
                break
        finally:
            worker.stop()
            converter.stop()
    for row in rows:
        receipt_path = output / row["seed"] / "public-receipts.jsonl.gz"
        if not receipt_path.exists():
            continue  # The journal is created on the first actual delivery.
        with gzip.open(receipt_path, "rt") as receipts:
            if any(line.strip() for line in receipts):
                raise ValueError("A starting-menu observation unexpectedly submitted an action")
    check_sources(root, ctx["sources"])
    body = {
        "schema_version": "native-selection-start-observation-v1",
        "status": "public_start_observations_complete",
        "seeds": [r["seed"] for r in rows],
        "cases": rows,
        "sources": {
            **ctx["sources"],
            str(Path(__file__).relative_to(root)): _sha_file(Path(__file__)),
        },
        "evidence": {
            str(p.relative_to(root)): _sha_file(p)
            for p in output.rglob("*")
            if p.is_file() and p.name != "active.json"
        },
        "selected_seed": next(
            (r["seed"] for r in rows if r["selected_label"] == "Scroll Boxes"), None
        ),
        "native_helpers": ctx["native_helpers"],
        "candidate_sha256": ctx["native"]["build"]["artifact_sha256"],
        "action_submissions": 0,
        "optimizer_updates": 0,
        "game_apps_created": 0,
        "original_weights_and_all_Adam_unchanged": True,
        "fresh_strength_evidence": False,
        "wall_seconds": time.monotonic() - started,
    }
    body["report_id"] = manifest_identifier(body)
    atomic_json(output / "report.json", body)
    (output / "active.json").rename(output / "complete.json")
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = discover(Path.cwd(), args.recipe.resolve(), args.output.resolve())
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in {"sources", "evidence", "cases"}}, indent=2
        )
    )
    return 0 if report["selected_seed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
