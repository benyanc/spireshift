"""Read only an audited, completed historical TRAIN collection, never a live workspace."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_context_reuse import check_sources
from spireshift.native_situation_selection import LIMITS
from spireshift.native_structured_plan import plan, request
from spireshift.training_objective import load_training_score_spec

SOURCES = (
    "native_situation_sources.py",
    "native_situation_features.py",
    "native_situation_selection.py",
    "native_situation_bank.py",
    "native_situation_resolve.py",
    "native_inventory_credit_features.py",
)
ENTRIES = ("build-native-situation-bank-v1.py", "build-native-situation-bank-v1.sh")
COHORTS = tuple(
    f"fit-p{p}-{arm}-r{r:02d}"
    for r in (1, 2)
    for p in (2, 3)
    for arm in ("unchanged", "hashed", "named")
)


def protected_sources(root: Path, ref: dict[str, str]) -> dict[str, str]:
    """Protect pinned code/configs without reading or following current run outputs."""
    path = root / ref["path"]
    if _sha_file(path) != ref["sha256"]:
        raise ValueError("The protected running recipe changed")
    cfg = json.loads(path.read_text())
    result = {ref["path"]: ref["sha256"]}
    for key, directory in (
        ("implementation_sha256", "src/spireshift"),
        ("entry_sha256", "scripts"),
        ("helpers_sha256", "scripts"),
    ):
        result.update({f"{directory}/{name}": sha for name, sha in cfg[key].items()})
    check_sources(root, result)
    return result


def prepare(root: Path, path: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    if (
        cfg.get("schema_version") != "native-situation-bank-config-v1"
        or cfg.get("stage") not in {"short_control", "completed_train_bank"}
        or cfg.get("cohorts") != list(COHORTS[:1] if cfg["stage"] == "short_control" else COHORTS)
        or cfg.get("sampling_limits") != LIMITS
        or not str(cfg.get("workspace", "")).startswith("artifacts/native-situation-bank/")
        or cfg.get("session_limits")
        != {
            "wall_seconds": 240,
            "cpu_seconds": 240,
            "resident_memory_bytes": 1000000000,
            "storage_bytes": 250000000,
        }
        or cfg.get("implementation_sha256")
        != {name: _sha_file(root / "src/spireshift" / name) for name in SOURCES}
        or cfg.get("entry_sha256") != {name: _sha_file(root / "scripts" / name) for name in ENTRIES}
    ):
        raise ValueError("Freeze the finite saved-only bank, quotas and implementation")
    sources = protected_sources(root, cfg["protected_run_recipe"])
    report = identified(root / cfg["source_report"]["path"])
    audit = identified(root / cfg["source_audit"]["path"])
    guard = identified(root / cfg["protection_report"]["path"])
    if (
        report["report_id"] != cfg["source_report"]["id"]
        or report["status"] != "native_structured_comparison_complete"
        or report["games_recorded"] != 640
        or report["failed_games"] != 0
        or audit["report_id"] != cfg["source_audit"]["id"]
        or audit["source_report_id"] != report["report_id"]
        or audit["games_verified"] != 640
        or audit["original_full_states_and_Adam_unchanged"] is not True
        or guard["report_id"] != cfg["protection_report"]["id"]
        or guard["status"] != "native_experience_control_complete"
    ):
        raise ValueError("Require the completed audited source and sealed protection evidence")
    for document in (report, audit, guard):
        for name, sha in document["sources"].items():
            if name in sources and sources[name] != sha:
                raise ValueError("Conflicting source seals")
            sources[name] = sha
    for key in ("source_report", "source_audit", "protection_report"):
        sources[cfg[key]["path"]] = _sha_file(root / cfg[key]["path"])
    source_path = root / report["recipe_path"]
    source = json.loads(source_path.read_text())
    if manifest_identifier(source) != report["config_id"]:
        raise ValueError("Historical source recipe differs")
    seed_ref = source["seed_manifest"]
    manifest = identified(root / seed_ref["path"], "manifest_id")
    if manifest["manifest_id"] != seed_ref["id"]:
        raise ValueError("The sealed training seed manifest differs")
    score = load_training_score_spec(root / source["training_spec"]["path"])
    if (
        score.spec_id != source["training_spec"]["id"]
        or score.scope.character != "ironclad"
        or score.scope.ascension != 8
        or score.evaluation_objective.primary != "terminal_victory"
        or score.evaluation_objective.whole_run_budget != 128
    ):
        raise ValueError("Preserve the actual A8 full-run objective and budget")
    done: dict[str, dict[str, Any]] = {}
    games, found = [], set()
    for task in plan(source, manifest["seeds"]):
        if task["kind"] == "evaluate":
            break  # Never open an evaluation episode or a live experiment unit.
        rel = f"{source['workspace']}/chunks/{task['key']}/done.json"
        if rel not in sources:
            raise ValueError("Historical TRAIN unit lacks a source audit seal")
        unit = identified(root / rel)
        if unit["config_id"] != report["config_id"] or unit["request_id"] != manifest_identifier(
            request(task, done)
        ):
            raise ValueError("Saved TRAIN predecessor or request changed")
        done[task["key"]] = unit["result"]
        if task["key"] not in cfg["cohorts"]:
            continue
        found.add(task["key"])
        paths = [p for key in task["collections"] for p in done[key]["paths"]]
        by_seed = {}
        for name in paths:
            if name not in sources or str(Path(name).with_suffix(".jsonl.gz")) not in sources:
                raise ValueError("A source episode or trace lacks a sealed audit")
            header = json.loads((root / name).read_text())
            seed = header["binding"]["seed_id"]
            if seed in by_seed:
                raise ValueError("Duplicate episode in a planned source cohort")
            by_seed[seed] = name
        if set(by_seed) != {s["id"] for s in task["seeds"]}:
            raise ValueError("Retain every planned source game, not selected successes")
        for seed in task["seeds"]:
            games.append(
                {
                    "key": f"{task['key']}-g{seed['id']}",
                    "cohort": task["key"],
                    "source_ref": by_seed[seed["id"]],
                    "world": seed["seed"],
                    "seed_id": seed["id"],
                    "model_id": done[task["state"]]["model_id"],
                    "player": task["player"],
                    "arm": task["arm"],
                    "round": task["round"],
                }
            )
    if found != set(cfg["cohorts"]):
        raise ValueError("Missing predeclared TRAIN cohorts")
    own = {f"src/spireshift/{n}": s for n, s in cfg["implementation_sha256"].items()}
    own.update({f"scripts/{n}": s for n, s in cfg["entry_sha256"].items()})
    sources.update(own)
    sources[str(path.relative_to(root))] = _sha_file(path)
    check_sources(root, sources)
    return {"config": cfg, "source": source, "score": score, "games": games, "sources": sources}
