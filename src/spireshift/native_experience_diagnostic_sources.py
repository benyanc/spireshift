"""Bind only four already sealed first-round TRAIN updates; never follow live units."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_context_reuse import check_sources
from spireshift.native_experience_plan import plan, request
from spireshift.native_policy_updates import SETTINGS
from spireshift.training_objective import load_training_score_spec

COHORTS = tuple(f"fit-p{p}-{arm}-r01" for p in (2, 3) for arm in ("batch32", "batch128"))
SOURCES = (
    "native_experience_feedback.py",
    "native_experience_diagnostic_data.py",
    "native_experience_diagnostic_sources.py",
    "native_experience_diagnostics.py",
    "native_training_diagnostics.py",
    "native_optimizer_probe.py",
    "native_value_credit.py",
    "native_structured_policy.py",
    "native_structured_state.py",
    "native_compact_training.py",
    "native_inventory_credit_features.py",
)
ENTRIES = ("diagnose-native-experience-v1.py", "diagnose-native-experience-v1.sh")


def prepare(root: Path, path: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    if (
        cfg.get("schema_version") != "native-experience-diagnostic-config-v1"
        or cfg.get("stage") not in {"short_control", "sealed_first_round_diagnostic"}
        or cfg.get("cohorts") != list(COHORTS)
        or not str(cfg.get("workspace", "")).startswith("artifacts/native-experience-diagnostics/")
        or cfg.get("implementation_sha256")
        != {n: _sha_file(root / "src/spireshift" / n) for n in SOURCES}
        or cfg.get("entry_sha256") != {n: _sha_file(root / "scripts" / n) for n in ENTRIES}
        or cfg.get("session_limits")
        != {
            "wall_seconds": 240,
            "cpu_seconds": 240,
            "resident_memory_bytes": 2000000000,
            "storage_bytes": 100000000,
        }
    ):
        raise ValueError("Freeze the finite first-round saved-only diagnostic and sources")
    ref = cfg["source_recipe"]
    source_path = root / ref["path"]
    source = json.loads(source_path.read_text())
    if (
        manifest_identifier(source) != ref["id"]
        or source.get("schema_version") != "native-experience-budget-config-v1"
        or source["learning"] != SETTINGS
        or (source["stage"] == "short_control") != (cfg["stage"] == "short_control")
    ):
        raise ValueError("Diagnostic source must be the pinned matching experience recipe")
    guard = identified(root / cfg["protection_report"]["path"])
    if (
        guard["report_id"] != cfg["protection_report"]["id"]
        or guard["status"] != "native_experience_control_complete"
    ):
        raise ValueError("Preserve the qualified source and original complete player states")
    sources = dict(guard["sources"])
    sources[cfg["protection_report"]["path"]] = _sha_file(root / cfg["protection_report"]["path"])
    sources[ref["path"]] = _sha_file(source_path)
    for key, directory in (
        ("implementation_sha256", "src/spireshift"),
        ("entry_sha256", "scripts"),
        ("helpers_sha256", "scripts"),
    ):
        sources.update({f"{directory}/{n}": s for n, s in source[key].items()})
    seeds = identified(root / source["seed_manifest"]["path"], "manifest_id")
    environment = identified(root / source["environment_manifest"]["path"], "manifest_id")
    score = load_training_score_spec(root / source["training_spec"]["path"])
    if (
        seeds["manifest_id"] != source["seed_manifest"]["id"]
        or environment["manifest_id"] != source["environment_manifest"]["id"]
        or score.spec_id != source["training_spec"]["id"]
        or score.scope.character != "ironclad"
        or score.scope.ascension != 8
        or score.evaluation_objective.primary != "terminal_victory"
        or score.evaluation_objective.whole_run_budget != 128
    ):
        raise ValueError("Preserve the source TRAIN worlds, actual environment and A8 objective")
    for key in ("seed_manifest", "environment_manifest", "training_spec"):
        sources[source[key]["path"]] = _sha_file(root / source[key]["path"])
    journal = ChunkJournal(
        root, source
    )  # Read completed receipts without locking/writing the source.
    done: dict[str, dict[str, Any]] = {}
    tasks = {}
    for task in plan(source, seeds["seeds"]):
        if task["kind"] == "evaluate" or task.get("round", 1) > 1:
            raise ValueError("Stop before later training or evaluation units")
        req = request(task, done)
        receipt = journal.completed(task["key"], req)
        if receipt is None:
            raise ValueError(
                f"Required TRAIN unit is not sealed: {task['key']}; do not open active work"
            )
        done[task["key"]] = receipt["result"]
        sources.update(receipt["sources"])
        name = str((journal.path(task["key"]) / "done.json").relative_to(root))
        sources[name] = _sha_file(root / name)
        if task["key"] in COHORTS:
            tasks[task["key"]] = task
        if set(tasks) == set(COHORTS):
            break
    if set(tasks) != set(COHORTS):
        raise ValueError("All four prespecified first-round updates must be sealed")
    sources.update({f"src/spireshift/{n}": s for n, s in cfg["implementation_sha256"].items()})
    sources.update({f"scripts/{n}": s for n, s in cfg["entry_sha256"].items()})
    sources[str(path.relative_to(root))] = _sha_file(path)
    check_sources(root, sources)
    return {
        "config": cfg,
        "source": source,
        "sources": sources,
        "done": done,
        "tasks": tasks,
        "score": score,
    }
