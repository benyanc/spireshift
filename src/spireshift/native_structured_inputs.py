"""Bind the finished controls, frozen TRAIN layout, original states and fresh worlds."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_context_reuse import check_sources
from spireshift.native_policy_trial_inputs import load as prior_load
from spireshift.native_structured_model import ARMS, vocabulary_id

SOURCES = (
    "native_structured_model.py",
    "native_structured_vocabulary.py",
    "native_structured_state.py",
    "native_structured_policy.py",
    "native_structured_game.py",
    "native_structured_training.py",
    "native_structured_plan.py",
    "native_structured_inputs.py",
    "native_structured_checks.py",
    "native_structured_execute.py",
    "native_structured_comparison.py",
)
ENTRIES = ("compare-native-structured-inputs-v1.sh", "compare-native-structured-inputs-v1.py")
SHARED = (
    "parent_recipe",
    "tactical_result",
    "vocabulary",
    "arms",
    "learning",
    "credit",
    "implementation_sha256",
    "entry_sha256",
)
RUNTIME = (
    "qualification",
    "qualification_id",
    "native_inputs",
    "helpers_sha256",
    "node",
    "players",
    "environment_manifest",
    "training_spec",
    "maximum_decisions",
    "episode_wall_seconds",
)


def validate(cfg: dict[str, Any]) -> None:
    control = cfg["stage"] == "short_control"
    if (
        cfg["schema_version"] != "native-structured-input-comparison-config-v1"
        or cfg["stage"] not in {"short_control", "bounded_representation_comparison"}
        or cfg["arms"] != list(ARMS)
        or cfg["rounds"] != (1 if control else 2)
        or cfg["batch_games"] != (2 if control else 32)
        or cfg["chunk_games"] != (2 if control else 8)
        or cfg["evaluation_worlds"] != (1 if control else 32)
        or cfg["session_limits"]
        != {
            "wall_seconds": 240 if control else 900,
            "cpu_seconds": 480 if control else 1800,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 1000000000 if control else 4000000000,
        }
    ):
        raise ValueError("Preserve the finite three-arm representation comparison")


def validate_worlds(
    cfg: dict[str, Any], manifest: dict[str, Any], environment: str
) -> list[dict[str, Any]]:
    seeds = manifest["seeds"]
    if (
        manifest["schema_version"] != "native-structured-comparison-seeds-v1"
        or manifest["environment_id"] != environment
        or len(seeds) != cfg["rounds"] * cfg["batch_games"] + cfg["evaluation_worlds"]
        or sum(s["partition"] == "train" for s in seeds) != cfg["rounds"] * cfg["batch_games"]
        or sum(s["partition"] == "development" for s in seeds) != cfg["evaluation_worlds"]
        or len({s["id"] for s in seeds}) != len(seeds)
        or len({s["seed"] for s in seeds}) != len(seeds)
        or any(
            set(s) != {"id", "seed", "partition"}
            or type(s["id"]) is not int
            or not isinstance(s["seed"], str)
            or not re.fullmatch(r"[A-HJ-NP-Z0-9]+", s["seed"])
            for s in seeds
        )
    ):
        raise ValueError("Use finite disjoint canonical training/development worlds")
    return cast(list[dict[str, Any]], seeds)


def exclude_worlds(seeds: list[dict[str, Any]], previous: list[dict[str, Any]]) -> None:
    names = {s["seed"].upper().replace("I", "1").replace("O", "0") for s in previous}
    if {s["seed"] for s in seeds} & names or {s["id"] for s in seeds} & {s["id"] for s in previous}:
        raise ValueError("Do not reuse old training, development, tactical or control worlds")


def load(root: Path, path: Path, *, require_control: bool = True) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    validate(cfg)
    if cfg["implementation_sha256"] != {
        n: _sha_file(root / "src/spireshift" / n) for n in SOURCES
    } or cfg["entry_sha256"] != {n: _sha_file(root / "scripts" / n) for n in ENTRIES}:
        raise ValueError("Preserve the exact structured-input implementation and launchers")
    prior = prior_load(root, root / cfg["parent_recipe"])
    base = prior["config"]
    if (
        cfg["learning"] != base["learning"]
        or cfg["credit"] != base["credit"]
        or any(cfg[k] != base[k] for k in RUNTIME)
    ):
        raise ValueError("Do not change PPO, rewards or the value baseline during input comparison")
    tactical = identified(root / cfg["tactical_result"]["path"])
    if (
        tactical["report_id"] != cfg["tactical_result"]["id"]
        or tactical["status"] != "tactical_diagnostic_complete"
        or not all(
            m["criterion_passed"] for p in tactical["learning"] for m in p["methods"].values()
        )
    ):
        raise ValueError("Assess the completed native learning controls before this intervention")
    check_sources(root, tactical["sources"])
    layout = identified(root / cfg["vocabulary"]["path"])
    if (
        layout["report_id"] != cfg["vocabulary"]["id"]
        or layout["size"] != 1024
        or layout["source_games"] != 128
        or layout["builder_sha256"]
        != cfg["implementation_sha256"]["native_structured_vocabulary.py"]
        or vocabulary_id(tuple(layout["columns"])) != layout["vocabulary_id"]
    ):
        raise ValueError("Use the frozen varied TRAIN-only layout")
    check_sources(root, layout["sources"])
    ref = cfg["seed_manifest"]
    manifest = identified(root / ref["path"], "manifest_id")
    if manifest["manifest_id"] != ref["id"]:
        raise ValueError("Fresh seed manifest identity changed")
    seeds = validate_worlds(cfg, manifest, base["environment_manifest"]["id"])
    sources = {**prior["sources"], **layout["sources"], **tactical["sources"]}
    for excluded in cfg["freshness_exclusions"]:
        p = root / excluded["path"]
        if _sha_file(p) != excluded["sha256"]:
            raise ValueError("A historical seed exclusion changed")
        rows = json.loads(p.read_text())["seeds"]
        exclude_worlds(seeds, rows)
        sources[excluded["path"]] = excluded["sha256"]
    for name in (
        str(path.relative_to(root)),
        cfg["parent_recipe"],
        cfg["vocabulary"]["path"],
        cfg["tactical_result"]["path"],
        cfg["seed_manifest"]["path"],
    ):
        sources[name] = _sha_file(root / name)
    sources.update({f"src/spireshift/{n}": v for n, v in cfg["implementation_sha256"].items()})
    sources.update({f"scripts/{n}": v for n, v in cfg["entry_sha256"].items()})
    if cfg["stage"] != "short_control" and require_control:
        control_cfg = json.loads((root / cfg["control_recipe"]).read_text())
        control = identified(root / control_cfg["workspace"] / "report.json")
        if (
            any(cfg[k] != control_cfg[k] for k in (*SHARED, *RUNTIME))
            or control["config_id"] != manifest_identifier(control_cfg)
            or control["status"] != "native_structured_control_complete"
            or control["failed_games"] != 0
            or control["games_recorded"] != 20
            or control["input_checks"]["passed"] is not True
            or not control["original_full_states_and_Adam_unchanged"]
        ):
            raise ValueError("Complete the matching clean twenty-game native control first")
        check_sources(root, control["sources"])
        if not any(
            r["path"] == control_cfg["seed_manifest"]["path"] for r in cfg["freshness_exclusions"]
        ):
            raise ValueError("The main stage must exclude its short-control worlds")
        sources.update(control["sources"])
        sources[str((root / control_cfg["workspace"] / "report.json").relative_to(root))] = (
            _sha_file(root / control_cfg["workspace"] / "report.json")
        )
    required_exclusions = {r["path"] for r in base["freshness_exclusions"]} | {
        base["seed_manifest"]["path"]
    }
    if not required_exclusions <= {r["path"] for r in cfg["freshness_exclusions"]}:
        raise ValueError("Preserve every historical full-game seed exclusion")
    return {**prior, "config": cfg, "seeds": seeds, "sources": sources, "layout": layout}
