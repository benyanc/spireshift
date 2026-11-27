"""Freeze the repaired observation, exact warm states and finite experience-budget test."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_neural import NativeActorCritic
from spireshift.engine_qualification import _sha_file
from spireshift.engine_relic_worker import SCRIPT
from spireshift.engine_worker import worker_helpers
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_reuse import check_sources
from spireshift.native_policy_updates import SETTINGS
from spireshift.native_relic_observation import CONTRACT
from spireshift.native_structured_inputs import exclude_worlds
from spireshift.native_structured_inputs import load as previous_load

SOURCES = (
    "native_experience_inputs.py",
    "native_experience_plan.py",
    "native_experience_game.py",
    "native_experience_training.py",
    "native_experience_execute.py",
    "native_experience_comparison.py",
)
ENTRIES = ("compare-native-experience-v1.py", "compare-native-experience-v1.sh")
ARMS = ("batch32", "batch128")


def migrate(model: CachedContextModel, environment: str) -> CachedContextModel:
    actor = replace(model.actor, environment_id=environment)
    result = CachedContextModel(
        NativeActorCritic(actor, model.value_weights), model.mode, model.feature_spec_id
    )
    if result.weights() != model.weights() or result.actor.dimension != 512:
        raise ValueError("Observation metadata migration changed inherited numerical weights")
    return result


def load(root: Path, path: Path, *, require_control: bool = True) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    control = cfg.get("stage") == "short_control"
    if (
        cfg.get("schema_version") != "native-experience-budget-config-v1"
        or cfg.get("stage") not in {"short_control", "bounded_experience_comparison"}
        or cfg.get("arms") != list(ARMS)
        or cfg.get("batch_sizes") != dict(zip(ARMS, (2, 4) if control else (32, 128), strict=True))
        or cfg.get("rounds") != (1 if control else 2)
        or cfg.get("chunk_games") != (2 if control else 8)
        or cfg.get("evaluation_worlds") != (1 if control else 32)
        or cfg.get("learning") != SETTINGS
        or cfg.get("session_limits")
        != {
            "wall_seconds": 240 if control else 900,
            "cpu_seconds": 480 if control else 1800,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 1000000000 if control else 4000000000,
        }
        or cfg.get("implementation_sha256")
        != {n: _sha_file(root / "src/spireshift" / n) for n in SOURCES}
        or cfg.get("entry_sha256") != {n: _sha_file(root / "scripts" / n) for n in ENTRIES}
        or cfg.get("helpers_sha256") != worker_helpers(root, SCRIPT)
    ):
        raise ValueError("Preserve the finite two-arm experience-budget comparison")
    old = previous_load(root, root / cfg["parent_recipe"])
    previous = old["config"]
    for name in (
        "players",
        "credit",
        "learning",
        "qualification",
        "qualification_id",
        "native_inputs",
        "node",
        "maximum_decisions",
        "episode_wall_seconds",
        "training_spec",
    ):
        if cfg[name] != previous[name]:
            raise ValueError(f"Experience treatment must not silently change {name}")
    sources = dict(old["sources"])
    for name, status in (
        ("input_audit", "actor_distinctions_pass_projection_repair_required"),
        ("relic_qualification", "native_relic_observation_qualification_complete"),
    ):
        ref = cfg[name]
        report = identified(root / ref["path"])
        if report["report_id"] != ref["id"] or report["status"] != status:
            raise ValueError("Complete actor distinctions and the scoped counter repair first")
        check_sources(root, report["sources"])
        sources.update(report["sources"])
        sources[ref["path"]] = _sha_file(root / ref["path"])
    ref = cfg["environment_manifest"]
    environment = identified(root / ref["path"], "manifest_id")
    expected = identified(root / previous["environment_manifest"]["path"], "manifest_id")
    parent_id = expected.pop("manifest_id")
    expected.update(
        parent_environment_id=parent_id,
        worker_script=SCRIPT,
        helpers_sha256=cfg["helpers_sha256"],
        inventory_observation_contract=CONTRACT,
        initialization="explicit_exact_weight_and_Adam_import_v1",
    )
    if (
        environment != {**expected, "manifest_id": manifest_identifier(expected)}
        or environment["manifest_id"] != ref["id"]
    ):
        raise ValueError("Only the versioned public counter observation may change the environment")
    ref = cfg["seed_manifest"]
    manifest = identified(root / ref["path"], "manifest_id")
    seeds = manifest["seeds"]
    broad = cfg["batch_sizes"][ARMS[1]]
    if (
        manifest["manifest_id"] != ref["id"]
        or manifest["schema_version"] != "native-experience-budget-seeds-v1"
        or manifest["environment_id"] != environment["manifest_id"]
        or len(seeds) != cfg["rounds"] * broad + cfg["evaluation_worlds"]
    ):
        raise ValueError("Require a finite environment-bound seed manifest")
    if (
        len({s["id"] for s in seeds}) != len(seeds)
        or len({s["seed"] for s in seeds}) != len(seeds)
        or sum(s["partition"] == "train" for s in seeds) != cfg["rounds"] * broad
        or any(
            set(s) != {"id", "seed", "partition"}
            or type(s["id"]) is not int
            or s["id"] < 0
            or not isinstance(s["seed"], str)
            or not re.fullmatch(r"[A-HJ-NP-Z0-9]+", s["seed"])
            or s["partition"] not in {"train", "development"}
            for s in seeds
        )
    ):
        raise ValueError("Require disjoint distinct whole-game train and evaluation seeds")
    required = {r["path"] for r in previous["freshness_exclusions"]} | {
        previous["seed_manifest"]["path"]
    }
    if not required <= {r["path"] for r in cfg["freshness_exclusions"]}:
        raise ValueError("Preserve all historical seed exclusions")
    for excluded in cfg["freshness_exclusions"]:
        p = root / excluded["path"]
        if _sha_file(p) != excluded["sha256"]:
            raise ValueError("A historical seed exclusion changed")
        exclude_worlds(seeds, json.loads(p.read_text())["seeds"])
        sources[excluded["path"]] = excluded["sha256"]
    for name in (
        str(path.relative_to(root)),
        cfg["parent_recipe"],
        cfg["environment_manifest"]["path"],
        cfg["seed_manifest"]["path"],
    ):
        sources[name] = _sha_file(root / name)
    sources.update({f"src/spireshift/{n}": s for n, s in cfg["implementation_sha256"].items()})
    sources.update(
        {f"scripts/{n}": s for n, s in {**cfg["entry_sha256"], **cfg["helpers_sha256"]}.items()}
    )
    if not control and require_control:
        c = json.loads((root / cfg["control_recipe"]).read_text())
        report = identified(root / c["workspace"] / "report.json")
        shared = (
            "players",
            "credit",
            "learning",
            "environment_manifest",
            "implementation_sha256",
            "entry_sha256",
            "helpers_sha256",
            "input_audit",
            "relic_qualification",
            "parent_recipe",
        )
        if (
            any(cfg[k] != c[k] for k in shared)
            or report["config_id"] != manifest_identifier(c)
            or report["status"] != "native_experience_control_complete"
            or report["failed_games"] != 0
            or report["games_recorded"] != 18
        ):
            raise ValueError("Pass the clean matching eighteen-game native learning control first")
        if c["seed_manifest"]["path"] not in {r["path"] for r in cfg["freshness_exclusions"]}:
            raise ValueError("Exclude the short-control worlds")
        check_sources(root, report["sources"])
        sources.update(report["sources"])
        sources[str((root / c["workspace"] / "report.json").relative_to(root))] = _sha_file(
            root / c["workspace"] / "report.json"
        )
    check_sources(root, sources)
    return {
        **old,
        "config": cfg,
        "seeds": seeds,
        "sources": sources,
        "models": {p: migrate(m, environment["manifest_id"]) for p, m in old["models"].items()},
    }
