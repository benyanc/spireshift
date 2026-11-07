"""Versioned coverage correction using only sealed v1 candidates; preserve the first bank."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_context_reuse import check_sources
from spireshift.native_situation_bank import coverage
from spireshift.native_situation_coverage import POLICY, select
from spireshift.native_situation_selection import LIMITS

SOURCES = ("native_situation_coverage.py", "native_situation_reselection.py")
ENTRIES = ("build-native-situation-bank-v2.py", "build-native-situation-bank-v2.sh")


def run(root: Path, path: Path) -> dict[str, Any]:
    started = time.monotonic()
    cfg = json.loads(path.read_text())
    if (
        cfg.get("schema_version") != "native-situation-bank-coverage-config-v2"
        or cfg.get("sampling_limits") != LIMITS
        or cfg.get("selection_policy") != POLICY
        or cfg.get("workspace")
        != "artifacts/native-situation-bank/sts2-v0.111.0-a8-completed-train-v2"
        or cfg.get("implementation_sha256")
        != {n: _sha_file(root / "src/spireshift" / n) for n in SOURCES}
        or cfg.get("entry_sha256") != {n: _sha_file(root / "scripts" / n) for n in ENTRIES}
        or cfg.get("session_limits")
        != {
            "wall_seconds": 240,
            "cpu_seconds": 240,
            "resident_memory_bytes": 1000000000,
            "storage_bytes": 25000000,
        }
    ):
        raise ValueError("Freeze the saved-only coverage correction and original caps")
    parent_path = root / cfg["parent_report"]["path"]
    parent = identified(parent_path)
    if (
        parent["status"] != "native_situation_bank_complete"
        or parent["report_id"] != cfg["parent_report"]["id"]
    ):
        raise ValueError("Require the completed frozen candidate bank")
    sources = dict(parent["sources"])
    sources[cfg["parent_report"]["path"]] = _sha_file(parent_path)
    sources[str(path.relative_to(root))] = _sha_file(path)
    sources.update({f"src/spireshift/{n}": s for n, s in cfg["implementation_sha256"].items()})
    sources.update({f"scripts/{n}": s for n, s in cfg["entry_sha256"].items()})
    check_sources(root, sources)
    parent_bank = identified(parent_path.parent / "bank.json", "bank_id")
    if parent_bank["bank_id"] != parent["summary"]["bank_id"]:
        raise ValueError("The frozen parent bank identity differs")
    store = ChunkJournal(root, cfg)
    with store.lock():
        if (store.workspace / "report.json").exists():
            report = identified(store.workspace / "report.json")
            if report["config_id"] != store.config_id:
                raise ValueError("Completed bank uses another selection recipe")
            check_sources(root, report["sources"])
            return report
        candidates = []
        for name in sorted(sources):
            if name.startswith(
                str(parent_path.parent.relative_to(root)) + "/chunks/"
            ) and name.endswith("/rows.json"):
                candidates.extend(json.loads((root / name).read_text()))
        if len(candidates) != parent["summary"]["sampling"]["candidate_references"]:
            raise ValueError(
                "Preserve every pre-thinned candidate, not just the first bank's winners"
            )
        chosen, sampling = select(candidates, parent_bank["world_splits"])
        bank = {
            k: v for k, v in parent_bank.items() if k not in {"bank_id", "config_id", "situations"}
        }
        bank.update(
            schema_version="native-training-situation-bank-v2",
            config_id=store.config_id,
            selection_policy=POLICY,
            parent_bank_id=parent_bank["bank_id"],
            situations=[dict(r, situation_id=manifest_identifier(r)) for r in chosen],
        )
        bank["bank_id"] = manifest_identifier(bank)
        bank_path = store.workspace / "bank.json"
        if bank_path.exists():
            raise FileExistsError("Preserve an uncommitted corrected bank for inspection")
        atomic_json(bank_path, bank)
        sources[str(bank_path.relative_to(root))] = _sha_file(bank_path)
        check_sources(root, sources)
        summary = {
            **{
                k: parent["summary"][k]
                for k in ("source_attempts", "source_native_worlds", "counts")
            },
            "sampling": sampling,
            "selected": coverage(chosen),
            "selected_by_split": {
                s: coverage([r for r in chosen if r["split"] == s]) for s in ("fit", "validation")
            },
            "bank_id": bank["bank_id"],
        }
        body = {
            "schema_version": "native-training-situation-bank-report-v2",
            "config_id": store.config_id,
            "recipe_path": str(path.relative_to(root)),
            "status": "native_situation_bank_complete",
            "summary": summary,
            "sources": sources,
            "parent_report_id": parent["report_id"],
            "parent_bank_preserved": True,
            "source_world_splits_reused_unchanged": True,
            "protected_files_unchanged": True,
            "original_full_states_and_Adam_unchanged": True,
            "evaluation_episodes_decoded": 0,
            "running_experiment_units_read": 0,
            "games_launched": 0,
            "optimizer_updates": 0,
            "automatic_followup": False,
            "checkpoint_promoted": False,
            "adaptive_controller_allowed": False,
            "wall_seconds": time.monotonic() - started,
        }
        report = {**body, "report_id": manifest_identifier(body)}
        atomic_json(store.workspace / "report.json", report)
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe")
    args = parser.parse_args()
    try:
        report = run(Path.cwd(), Path.cwd() / args.recipe)
        print(json.dumps({k: v for k, v in report.items() if k != "sources"}, indent=2))
        return 0
    except (ValueError, KeyError, FileExistsError) as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
