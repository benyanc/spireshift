"""Prospective worlds, fixed work and separately gated phases on frozen tuple48."""

from __future__ import annotations

import ast
import json
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _sha_file
from spireshift.engine_startup import _script_closure
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_inputs_v12 import canonical_seed
from spireshift.native_learner_guard import qualify
from spireshift.neural_combat import _numpy

CONTRACT = "varied_native_teaching_and_separate_routing_interference_v1"
ARMS = ("reference", "teacher")
VARIANTS = ("original", "reference", "teacher", "teacher_original_noncombat")
PHASES = ("collect", "fit", "canary", "evaluate")
THREADS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "MKL_NUM_THREADS")
LEARNING = {
    "epochs": 16,
    "steps_per_epoch": 4,
    "batch_choices": 32,
    "actor_learning_rate": 0.001,
    "gradient_clip": 1.0,
    "temperature": 0.8,
}


def execution_runtime(node: str) -> dict[str, Any]:
    numpy = _numpy()
    package = Path(numpy.__file__).parent
    uv = shutil.which("uv")
    if uv is None:
        raise ValueError("The pinned uv executable is unavailable")
    return {
        "system": platform.system(),
        "release": platform.release(),
        "kernel": platform.version(),
        "machine": platform.machine(),
        "python_version": sys.version,
        "python_executable_sha256": _sha_file(Path(sys.executable).resolve()),
        "uv_executable_sha256": _sha_file(Path(uv).resolve()),
        "node_executable_sha256": _sha_file(Path(node).resolve()),
        "numpy_version": str(numpy.__version__),
        "numpy_implementation": {
            str(p.relative_to(package)): _sha_file(p)
            for p in sorted(package.rglob("*"))
            if p.is_file() and p.suffix in {".py", ".so", ".dylib"}
        },
        "numeric_threads": {n: os.environ.get(n) for n in THREADS},
    }


def plan(control: bool = False, generation: int = 1) -> dict[str, Any]:
    worlds = (
        [
            {
                "key": f"control-p{p}",
                "seed": f"SP1RESH1FTVTC{899 + p + 2 * (generation - 1)}",
                "player": p,
                "partition": "control",
            }
            for p in (2, 3)
        ]
        if control
        else [
            {
                "key": f"fit-{i:02d}",
                "seed": f"SP1RESH1FTVTF{i:03d}",
                "player": 2 + (i - 1) % 2,
                "partition": "fit",
            }
            for i in range(1, 9)
        ]
        + [
            {
                "key": f"held-{i:02d}",
                "seed": f"SP1RESH1FTVTH{i:03d}",
                "player": 2 + (i - 1) % 2,
                "partition": "heldout",
            }
            for i in range(1, 5)
        ]
    )
    return {
        "worlds": worlds,
        "roots_per_fit_world": 1 if control else 2,
        "candidate_paths_per_root": 1 if control else 4,
        "branch_maximum_decisions": 192,
        "branch_maximum_rounds": 12,
        "branch_wall_seconds": 60,
        "maximum_pair_wall_seconds": 600,
        "maximum_decisions": 384,
        "whole_run_cpu_seconds": 128,
        "maximum_technical_failures": 2,
        "learning": {**LEARNING, "epochs": 1 if control else 16},
        "arms": list(ARMS),
        "evaluation_variants": list(VARIANTS),
        "canary_cases": []
        if control
        else [
            {
                "key": f"canary-p{p}-{a.replace('_', '-')}",
                "player": p,
                "variant": a,
                "seed": f"SP1RESH1FTVTV{201 + i * 2 + p - 2}",
            }
            for i, a in enumerate(VARIANTS[1:])
            for p in (2, 3)
        ],
        "evaluation_seeds": [] if control else [f"SP1RESH1FTVTE{i:03d}" for i in range(1, 17)],
        "quality": {
            "independent_fitting_worlds": 1 if control else 4,
            "source_players": 1 if control else 2,
            "strictly_improved_worlds": 0 if control else 2,
            "enemy_compositions": 1 if control else 2,
            "deck_compositions": 1 if control else 3,
        },
        "teacher_selection": "confirmed_native_win_or_resource_preserving_strict_HP_gain_v1",
        "root_selection": "first_round2_fight_then_later_public_novelty_without_outcomes_v1",
        "interference": (
            "same_teacher_final_shared_vs_original_noncombat_public_ownership_routing_v1"
        ),
        "world_equal_sampling": True,
        "all_finals_before_evaluation": True,
        "heldout_fitting_or_selection": False,
        "ordinary_PPO": False,
        "automatic_follow_up": False,
    }


def validate(cfg: dict[str, Any]) -> None:
    control = cfg.get("stage") == "short_control"
    generation = cfg.get("control_generation", 1)
    if (
        cfg.get("schema_version") != "native-varied-teaching-config-v1"
        or cfg.get("contract") != CONTRACT
        or cfg.get("stage") not in {"short_control", "bounded_study"}
        or type(generation) is not int
        or not 1 <= generation <= 8
        or cfg.get("plan") != plan(control, generation)
        or cfg.get("workspace")
        != "artifacts/native-varied-teaching/"
        + (f"control-v{generation}" if control else "study-v1")
        or cfg.get("training_allowed") is not False
        or cfg.get("diagnostic_fitting_on_copies_only") is not True
        or cfg.get("automatic_follow_up") is not False
        or cfg.get("session_limits")
        != {
            "wall_seconds": 290 if control else 1800,
            "cpu_seconds": 900 if control else 3600,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 4000000000,
        }
    ):
        raise ValueError(
            "Preserve prospective splits, matched teaching work, ablation and fixed budgets"
        )


def implementation(root: Path) -> dict[str, str]:
    pending = [
        f"spireshift.{p.stem}" for p in (root / "src/spireshift").glob("native_curriculum_*.py")
    ]
    pending.append("spireshift.native_learner_guard")
    names, seen = set(), set()
    while pending:
        module = pending.pop()
        if module in seen or not module.startswith("spireshift"):
            continue
        seen.add(module)
        p = root / "src" / Path(*module.split("."))
        p = p.with_suffix(".py") if p.with_suffix(".py").is_file() else p / "__init__.py"
        if not p.is_file():
            continue
        names.add(str(p.relative_to(root)))
        for node in ast.walk(ast.parse(p.read_text())):
            if isinstance(node, ast.ImportFrom) and node.module:
                pending.append(node.module)
            elif isinstance(node, ast.Import):
                pending.extend(a.name for a in node.names)
    names.update(
        f"scripts/{n}"
        for n in _script_closure(
            root / "scripts",
            {
                "engine-shop-checkpoint-v1.mjs",
                "engine-shop-task-verify-v1.mjs",
                "engine-native-worker-v24.mjs",
            },
        )
    )
    names.update(
        {
            "scripts/prepare-varied-teaching-v1.sh",
            "scripts/varied-teaching-session-v1.py",
            "tests/unit/test_native_curriculum.py",
        }
    )
    return {n: _sha_file(root / n) for n in sorted(names)}


def validate_worlds(cfg: dict[str, Any], history: set[str]) -> None:
    p = cfg["plan"]
    seeds = (
        [r["seed"] for r in p["worlds"]]
        + p["evaluation_seeds"]
        + [r["seed"] for r in p["canary_cases"]]
    )
    if len(set(seeds)) != len(seeds) or any(canonical_seed(s) in history for s in seeds):
        raise ValueError(
            "Fitting, withheld, canary, final and historical worlds must stay disjoint"
        )


def load(root: Path, recipe: Path) -> dict[str, Any]:
    cfg = json.loads(recipe.read_text())
    validate(cfg)
    if cfg["execution_runtime"] != execution_runtime(cfg["node"]) or any(
        os.environ.get(n) != "1" for n in THREADS
    ):
        raise ValueError("Python, numeric library, Node, uv, host or thread settings changed")
    if cfg["implementation"] != implementation(root):
        raise ValueError("Study, guard, native delivery or policy implementation changed")
    history = json.loads(verified(root, cfg["seed_history"]).read_text())
    validate_worlds(cfg, set(history["canonical_prior_seeds"]))
    check_sources(root, cfg["implementation"])
    context = qualify(root, cfg)
    if cfg["stage"] == "bounded_study":
        ref = cfg["control_recipe"]
        control = json.loads(verified(root, ref).read_text())
        if control["implementation"] != cfg["implementation"]:
            raise ValueError("The control must exercise this exact source")
        validate_worlds(cfg, {r["seed"] for r in control["plan"]["worlds"]})
    # The newly minted guard receipt owns its source map. Binding the study
    # recipe must not mutate that sealed receipt through a shared dictionary.
    context["sources"] = {
        **context["sources"],
        str(recipe.relative_to(root)): _sha_file(recipe),
        **cfg["implementation"],
    }
    context.update(config=cfg, recipe=recipe, config_id=manifest_identifier(cfg))
    return context
