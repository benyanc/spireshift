"""Execution-only pins for the fresh normal-start Act 1 curriculum."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.core.objective import ObjectiveSpec
from spireshift.engine_learning import identified
from spireshift.engine_localization import verify_native_localization
from spireshift.engine_native import _private_path
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.engine_startup import _script_closure
from spireshift.engine_worker_qualification import immutable_checks
from spireshift.native_a8_paired_inputs import FITTING_EVIDENCE, PLAYERS
from spireshift.native_a8_rescue_policy import CONTRACT
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_curriculum_config import execution_runtime
from spireshift.native_structured_state import load as load_state
from spireshift.native_win4_plan import PLAN
from spireshift.native_win4_worker import SCRIPT
from spireshift.native_win_inputs import restore_paths
from spireshift.training_objective import TrainingScoreSpec

RECIPE = "configs/native-curriculum/sts2-v0.111.0-a8-act1-rescue-v1.json"
AREA = "artifacts/native-a8-act1-rescue"
CONVERTER = "engine-shared-input-v16.mjs"
ORDERED_PROOF = "engine-ordered-plan-verify-v1.mjs"
WRAPPER = "scripts/collect-act1-rescues-v1.sh"
MODULE = "spireshift.native_a8_rescue_session"
CONTROL_RESOURCE = "artifacts/resources/a8-act1-rescue-control-v1.json"
GAME_LIMITS = {
    "episode_cpu_seconds": 128,
    "episode_wall_seconds": 90,
    "maximum_decisions": 2048,
    "maximum_rounds_per_fight": 30,
}
SESSION_LIMITS = {
    "wall_seconds": 5400,
    "cpu_seconds": 14400,
    "resident_memory_bytes": 4000000000,
    "storage_bytes": 4000000000,
}
CONTROL_LIMITS = {**SESSION_LIMITS, "wall_seconds": 285, "cpu_seconds": 300}
GATES: dict[str, dict[str, Any]] = {
    "qualify": {"minimum_rescues": 2, "required_players": [2, 3]},
    "collect": {
        "minimum_rescues": 3,
        "required_players": [2, 3],
        "required_reasons": ["hp_spend", "potion", "rest"],
    },
}
CONTROL = {"key": "control-001", "seed": "SP1RESH1FTA8RC001", "player": 2, "phase": "control"}
CONTROL_DELIVERIES = 18


def cases() -> dict[str, list[dict[str, Any]]]:
    return {
        phase: [
            {
                "key": f"{phase}-{i:03d}",
                "seed": f"SP1RESH1FTA8R{code}{i:03d}",
                "player": PLAYERS[(i - 1) % 2],
                "phase": phase,
            }
            for i in range(1, count + 1)
        ]
        for phase, code, count in (("qualify", "Q", 8), ("collect", "F", 12))
    }


def implementation(root: Path) -> dict[str, str]:
    src = root / "src"
    pending = sorted((src / "spireshift").glob("native_a8_rescue_*.py"))
    paths = {WRAPPER, "pyproject.toml", "uv.lock", "src/spireshift/__init__.py"}
    paths.update(
        "scripts/" + name
        for name in _script_closure(root / "scripts", {SCRIPT, CONVERTER, ORDERED_PROOF})
    )
    while pending:
        path = pending.pop()
        name = path.relative_to(root).as_posix()
        if name in paths:
            continue
        paths.add(name)
        for node in ast.walk(ast.parse(path.read_text())):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                modules = [node.module, *(node.module + "." + alias.name for alias in node.names)]
            for module in modules:
                if module.startswith("spireshift."):
                    base = src.joinpath(*module.split("."))
                    for dependency in (base.with_suffix(".py"), base / "__init__.py"):
                        if dependency.is_file():
                            pending.append(dependency)
    return {name: _sha_file(root / name) for name in sorted(paths)}


def declaration(root: Path) -> dict[str, Any]:
    cfg = json.loads((root / RECIPE).read_text())
    if (
        cfg["schema_version"] != "native-a8-act1-rescue-curriculum-v1"
        or cfg["workspace"] != f"{AREA}/study-v1"
        or cfg["control_workspace"] != f"{AREA}/control-v1"
        or cfg["control_resource"] != CONTROL_RESOURCE
        or cfg["worlds"] != cases()
        or cfg["control"] != CONTROL
        or cfg["control_limits"] != CONTROL_LIMITS
        or cfg["teacher"] != CONTRACT
        or cfg["game_limits"] != GAME_LIMITS
        or cfg["session_limits"] != SESSION_LIMITS
        or cfg["gates"] != GATES
        or cfg["implementation"] != implementation(root)
    ):
        raise ValueError("Use the exact declared Act 1 recipe and execution sources")
    return dict(cfg)


def short_check(
    root: Path, cfg: dict[str, Any], environment_id: str | None = None
) -> dict[str, str] | None:
    workspace = root / cfg["control_workspace"]
    resource = root / cfg["control_resource"]
    if not workspace.exists() and not resource.exists():
        return None
    path = workspace / "report.json"
    if not path.is_file() or not resource.is_file():
        raise ValueError("Preserve the incomplete short control for inspection")
    proof, receipt = identified(path), identified(resource)
    if (
        proof["status"] != "act1_rescue_short_checks_verified"
        or proof["config_id"] != manifest_identifier(cfg)
        or (environment_id is not None and proof["environment_id"] != environment_id)
        or proof["control_world"] != CONTROL["seed"]
        or proof["native_prefixes"] != 3
        or proof["native_deliveries"] != 3 * CONTROL_DELIVERIES
        or proof["optimizer_updates"] != 0
        or proof["qualification_games"] != 0
        or receipt["status"] != "completed"
        or receipt["exit_code"] != 0
        or receipt["cap"] is not None
        or receipt["limits"] != cfg["control_limits"]
        or receipt["command"] != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--control"]
        or receipt["artifacts"]["roots"] != [str(workspace)]
    ):
        raise ValueError("Require the exact passing saved and native prefix control")
    check_sources(root, proof["evidence"])
    return {str(p.relative_to(root)): _sha_file(p) for p in (path, resource)}


def freeze(root: Path, context: dict[str, Any]) -> dict[str, bool]:
    cfg, native, qualification = context["config"], context["native"], context["qualification"]
    if json.loads((root / RECIPE).read_text()) != cfg:
        raise ValueError("The execution declaration changed")
    check_sources(root, cfg["implementation"])
    check_sources(root, context["short_check_receipts"])
    for ref in context["states"].values():
        verified(root, {"path": ref["path"], "sha256": ref["sha256"]})
    checks = immutable_checks(qualification, native)
    if (
        not all(checks.values())
        or verify_native_localization(qualification, native["inputs"]["native_localization"])
        != native["localization"]
    ):
        raise ValueError("Frozen native game, runtime or localization changed")
    return {**checks, "localization_exact": True, "all_four_full_states_and_Adam_exact": True}


def load(root: Path, cfg: dict[str, Any], *, control: bool) -> dict[str, Any]:
    parent = json.loads(verified(root, cfg["parent_recipe"]).read_text())
    baseline = identified(verified(root, parent["baseline"]))
    support = identified(verified(root, cfg["support"]))
    paired = identified(verified(root, cfg["paired_evidence"]))
    panel = identified(verified(root, paired["saved_recovery"]))
    diagnosis = identified(verified(root, cfg["diagnosis"]))
    fitting = identified(verified(root, cfg["fitting_evidence"]))
    if cfg["fitting_evidence"]["path"] != FITTING_EVIDENCE:
        raise ValueError("Use the exact assessed update-200 checkpoints")
    if (
        support["schema_version"] != "native-headless-soul-nexus-build-v60"
        or support["status"] != "soul_nexus_bridge_built"
        or panel["status"] != "saved_paired_development_comparison_verified"
        or diagnosis["status"] != "act1_loss_comparison_verified"
        or diagnosis["source_panel_id"] != panel["report_id"]
        or fitting["status"] != "both_frozen_candidates_independently_verified"
        or fitting["report_id"] != panel["fitting_evidence_id"]
        or fitting["environment_id"] != panel["environment_id"]
        or execution_runtime(parent["node"]) != parent["execution_runtime"]
    ):
        raise ValueError("Require the previously verified paired environment and numerical runtime")
    objective = ObjectiveSpec.from_mapping(cfg["objective"])
    score = TrainingScoreSpec.from_mapping(baseline["training_score"])
    native = restore_paths(root, baseline["native"])
    build = support["builds"][0]
    execution = {
        "schema_version": "native-curriculum-support-execution-v60",
        "parent_environment_id": support["parent_environment_id"],
        "support_build_id": support["report_id"],
        "ordered_answer_contract": PLAN,
        "official_qualification": False,
    }
    environment_id = manifest_identifier(execution)
    if (
        objective.as_dict() != native["objective"]
        or objective != score.evaluation_objective
        or objective.whole_run_budget != GAME_LIMITS["episode_cpu_seconds"]
        or any(parent["plan"][k] != v for k, v in GAME_LIMITS.items())
        or environment_id != panel["environment_id"]
        or build["runtime_sts2_sha256"] != native["build"]["runtime_sts2_sha256"]
    ):
        raise ValueError("Frozen objective, native support build or game changed")
    native.update(
        candidate=_private_path(root, build["candidate"]),
        candidate_before=support["candidate_inventory"],
        build={**native["build"], **build},
        recipe={**native["recipe"], "input_config_id": environment_id},
    )
    check_sources(root, support["sources"])
    check_sources(root, support["evidence"])
    history = json.loads(verified(root, parent["seed_history"]).read_text())
    used = set(history["canonical_prior_seeds"]) | set(panel["worlds"])
    used.update(parent["plan"]["reserved_evaluation_seeds"])
    used.update(s for p in ("fit", "heldout") for c in parent["plan"][p] for s in c["seed_pool"])
    seeds = [CONTROL["seed"], *(c["seed"] for phase in cases().values() for c in phase)]
    if len(set(seeds)) != len(seeds) or used.intersection(seeds):
        raise ValueError("Use fresh disjoint qualification, collection and control worlds")

    models, states = {}, {}
    for player in PLAYERS:
        original = baseline["originals"][str(player)]
        final = fitting["candidates"][str(player)]
        if (
            final["initial_state_id"] != original["imported_state_id"]
            or final["initial_optimizer_steps"] != original["optimizer_steps"]
            or final["optimizer_steps"] != original["optimizer_steps"] + 200
        ):
            raise ValueError("The fitted full state does not descend from the exact original")
        for variant, ref in (
            (
                "original",
                {
                    "path": original["imported_path"],
                    "sha256": original["imported_sha256"],
                    "state_id": original["imported_state_id"],
                    "model_id": original["imported_model_id"],
                    "optimizer_id": original["optimizer_id"],
                    "optimizer_steps": original["optimizer_steps"],
                },
            ),
            ("fitted", {**final, "path": final["state_path"], "sha256": final["state_sha256"]}),
        ):
            model, adam, state_id = load_state(verified(root, ref))
            if (
                state_id != ref["state_id"]
                or model.model_id != ref["model_id"]
                or manifest_identifier(adam.as_dict()) != ref["optimizer_id"]
                or adam.steps != ref["optimizer_steps"]
            ):
                raise ValueError("Full checkpoint or Adam identity differs")
            models[player, variant] = model
            states[f"p{player}-{variant}"] = {
                k: ref[k]
                for k in (
                    "path",
                    "sha256",
                    "state_id",
                    "model_id",
                    "optimizer_id",
                    "optimizer_steps",
                )
            }
    receipts = None if control else short_check(root, cfg, environment_id)
    if not control and receipts is None:
        raise ValueError("A passing native prefix control is required")
    return {
        "config": cfg,
        "config_id": manifest_identifier(cfg),
        "environment_id": environment_id,
        "qualification": EngineQualificationConfig(baseline["qualification_document"], root),
        "native": native,
        "node": parent["node"],
        "score": score,
        "models": models,
        "states": states,
        "diagnosis": diagnosis,
        "paired_panel": panel,
        "short_check_receipts": receipts or {},
    }
