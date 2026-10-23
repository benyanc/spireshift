"""Exact copied parents, a sealed public lesson bank and disjoint fresh game panels."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.engine_relic_worker import SCRIPT
from spireshift.engine_worker import worker_helpers
from spireshift.native_context_journal import load_state
from spireshift.native_context_reuse import check_sources
from spireshift.native_coordinated_inputs import snapshot
from spireshift.native_experience_inputs import migrate
from spireshift.native_structured_inputs import exclude_worlds
from spireshift.native_teaching_data import ARMS, BANK, CONTRACT, LEARNING
from spireshift.training_objective import load_training_score_spec

SOURCES = (
    "native_teaching_data.py",
    "native_teaching_learning.py",
    "native_teaching_plan.py",
    "native_teaching_inputs.py",
    "native_teaching_execute.py",
    "native_teaching_study.py",
)
ENTRIES = ("test-native-plan-teaching-v1.py", "test-native-plan-teaching-v1.sh")


def validate(cfg: dict[str, Any]) -> None:
    control = cfg.get("stage") == "short_control"
    if (
        cfg.get("schema_version") != "native-plan-teaching-config-v1"
        or cfg.get("stage") not in {"short_control", "bounded_teaching_test"}
        or cfg.get("contract") != CONTRACT
        or cfg.get("arms") != list(ARMS)
        or cfg.get("learning") != {**LEARNING, "epochs": 1 if control else 16}
        or cfg.get("maximum_decisions") != 4096
        or cfg.get("episode_wall_seconds") != 120
        or cfg.get("technical_failure_allowance") != 2
        or cfg.get("workspace")
        != "artifacts/native-teaching/sts2-v0.111.0-a8-"
        + ("control-v1" if control else "comparison-v1")
        or cfg.get("session_limits")
        != {
            "wall_seconds": 240 if control else 900,
            "cpu_seconds": 480 if control else 1800,
            "resident_memory_bytes": 2000000000,
            "storage_bytes": 1000000000 if control else 3000000000,
        }
    ):
        raise ValueError("Preserve the fixed, separately declared three-way teaching comparison")


def worlds(root: Path, cfg: dict[str, Any], bank: dict[str, Any]) -> dict[str, str]:
    ref = cfg["seed_manifest"]
    manifest = identified(root / ref["path"], "manifest_id")
    seeds = manifest["seeds"]
    if (
        manifest["schema_version"] != "native-plan-teaching-seeds-v1"
        or manifest["manifest_id"] != ref["id"]
        or manifest["environment_id"] != bank["runtime"]["environment_manifest"]["id"]
        or seeds != cfg["evaluation_seeds"]
        or len(seeds) != (1 if cfg["stage"] == "short_control" else 32)
        or len({s["id"] for s in seeds}) != len(seeds)
        or len({s["seed"] for s in seeds}) != len(seeds)
        or any(
            set(s) != {"id", "seed", "partition"}
            or type(s["id"]) is not int
            or s["partition"] != "development"
            or not isinstance(s["seed"], str)
            or not re.fullmatch(r"[A-HJ-NP-Z0-9]+", s["seed"])
            for s in seeds
        )
    ):
        raise ValueError("Use a bounded fresh canonical whole-game panel, never fitting worlds")
    sources = {ref["path"]: _sha_file(root / ref["path"])}
    for old in cfg["freshness_exclusions"]:
        if _sha_file(root / old["path"]) != old["sha256"]:
            raise ValueError("Preserve the prior-world exclusion inventory")
        previous = json.loads((root / old["path"]).read_text())["seeds"]
        previous = [
            s
            for s in previous
            if isinstance(s, dict) and isinstance(s.get("seed"), str) and "id" in s
        ]
        exclude_worlds(seeds, previous)
        sources[old["path"]] = old["sha256"]
    required = {r["path"] for r in bank["runtime"]["freshness_exclusions"]} | {
        bank["runtime"]["seed_manifest"]["path"]
    }
    if not required <= sources.keys():
        raise ValueError("Fresh games must exclude every inherited training/development panel")
    exclude_worlds(seeds, [{"id": r["seed_id"], "seed": r["world"]} for r in bank["roots"]])
    return sources


def load(root: Path, recipe: Path, *, require_control: bool = True) -> dict[str, Any]:
    cfg = json.loads(recipe.read_text())
    validate(cfg)
    if (
        cfg["implementation_sha256"] != {n: _sha_file(root / "src/spireshift" / n) for n in SOURCES}
        or cfg["entry_sha256"] != {n: _sha_file(root / "scripts" / n) for n in ENTRIES}
        or cfg["helpers_sha256"] != worker_helpers(root, SCRIPT)
        or cfg["lesson_bank"]["path"] != BANK
    ):
        raise ValueError("Bind exact teaching, evaluation and native-worker implementations")
    bank = identified(root / BANK, "bank_id")
    if (
        bank["bank_id"] != cfg["lesson_bank"]["id"]
        or bank["contract"] != CONTRACT
        or bank["heldout_used_for_fitting"]
        or len(bank["lessons"]) != 2
        or any(r["partition"] != "fit" for r in bank["lessons"])
        or cfg["node"] != bank["runtime"]["node"]
    ):
        raise ValueError("Only the sealed two-world fitting bank may supply labels")
    sources = dict(bank["sources"])
    sources.update(worlds(root, cfg, bank))
    source = bank["runtime"]
    models, adams = {}, {}
    for player in source["players"]:
        if _sha_file(root / player["path"]) != player["sha256"]:
            raise ValueError("An original full model/Adam state changed")
        model, adam, sid = load_state(root / player["path"])
        if (
            sid != player["state_id"]
            or model.model_id != player["model_id"]
            or adam.steps != player["optimizer_steps"]
        ):
            raise ValueError("Preserve both numerical parents and all warm Adam moments/counters")
        p = player["numerical_seed"]
        models[p], adams[p] = migrate(model, source["environment_manifest"]["id"]), adam
    score = load_training_score_spec(root / source["training_spec"]["path"])
    if (
        score.spec_id != source["training_spec"]["id"]
        or score.evaluation_objective.primary != "terminal_victory"
    ):
        raise ValueError("Categorical teaching never replaces the full-run ObjectiveSpec")
    if cfg["stage"] != "short_control" and require_control:
        path = root / cfg["control_recipe"]
        c = json.loads(path.read_text())
        if any(
            c[k] != cfg[k]
            for k in (
                "lesson_bank",
                "implementation_sha256",
                "entry_sha256",
                "helpers_sha256",
                "node",
            )
        ):
            raise ValueError("The short control must qualify this exact bank and implementation")
        exclude_worlds(cfg["evaluation_seeds"], c["evaluation_seeds"])
        name = c["workspace"] + "/report.json"
        report = identified(root / name)
        if (
            report["status"] != "native_teaching_complete"
            or not report["control_checks_passed"]
            or report["config_id"] != manifest_identifier(c)
        ):
            raise ValueError("Complete the bounded teaching/native integration control first")
        sources.update(report["sources"])
        sources[name] = _sha_file(root / name)
    sources[BANK] = _sha_file(root / BANK)
    sources[str(recipe.relative_to(root))] = _sha_file(recipe)
    sources.update({f"src/spireshift/{n}": h for n, h in cfg["implementation_sha256"].items()})
    sources.update(
        {f"scripts/{n}": h for n, h in {**cfg["helpers_sha256"], **cfg["entry_sha256"]}.items()}
    )
    check_sources(root, sources)
    return {
        "config": cfg,
        "bank": bank,
        "source": source,
        "models": models,
        "adams": adams,
        "score": score,
        "sources": sources,
    }


__all__ = ["ENTRIES", "SOURCES", "load", "snapshot", "validate", "worlds"]
