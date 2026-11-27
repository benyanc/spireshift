"""Admission for fitting copies from the independently assessed v7 bank."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.core.objective import ObjectiveSpec
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_bank_fit import (
    ACTOR_RATE,
    GRADIENT_CLIP,
    TEMPERATURE,
    Worlds,
    encode_decision,
)
from spireshift.native_compatibility_contract import local, verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_win4_plan import PLAN, steps
from spireshift.native_win5_inputs import completed
from spireshift.native_win7_inputs import RECIPE as PARENT_RECIPE
from spireshift.native_win7_inputs import frozen_checks
from spireshift.native_win7_inputs import load as load_collection
from spireshift.native_win_bank import select

RECIPE = "configs/native-curriculum/sts2-v0.111.0-a8-world-balanced-fitting-v1.json"
ASSESSMENT = "docs/evidence/native-win-curriculum-result-v1.json"
CONTROL_RECIPE = "artifacts/native-win-fitting/preparation-v1/control-declaration-v2.json"
PLAYERS = (2, 3)
UPDATES = 200
CHUNK = 20
CONTROL_UPDATES = 4
CONTROL_CHUNK = 2
SCHEMA = "native-win-world-balanced-fitting-v1"
WORK = {
    "players": list(PLAYERS),
    "updates_per_copy": UPDATES,
    "updates_per_chunk": CHUNK,
    "draws_per_world_per_update": 1,
    "actor_rate": ACTOR_RATE,
    "value_rate": 0.0,
    "gradient_clip": GRADIENT_CLIP,
    "temperature": TEMPERATURE,
    "objective": "mean_joint_negative_log_probability_per_native_decision",
}
LIMITS = {
    "wall_seconds": 1800,
    "cpu_seconds": 3600,
    "storage_bytes": 4000000000,
    "resident_memory_bytes": 4000000000,
}
FILES = (
    "scripts/fit-win-curriculum-v1.sh",
    "src/spireshift/native_a8_bank_fit.py",
    "src/spireshift/native_a8_bank_fit_inputs.py",
    "src/spireshift/native_a8_bank_fit_session.py",
    "tests/unit/test_native_a8_bank_fit.py",
    "src/spireshift/native_context_journal.py",
    "src/spireshift/native_curriculum_store.py",
    "src/spireshift/native_win4_plan.py",
    "src/spireshift/native_shop_policy.py",
    "src/spireshift/native_structured_model.py",
    "src/spireshift/native_structured_state.py",
    "src/spireshift/full_run_policy.py",
    "src/spireshift/full_run_ppo_math.py",
)


def implementation(root: Path) -> dict[str, str]:
    return {name: _sha_file(root / name) for name in FILES}


def binding(recipe: dict[str, Any]) -> str:
    return manifest_identifier({k: v for k, v in recipe.items() if k != "short_check"})


def declaration(root: Path, path: str = RECIPE) -> dict[str, Any]:
    cfg = json.loads(local(root, path).read_text())
    if (
        cfg.get("schema_version") != SCHEMA
        or cfg.get("operation") != "fit_two_original_copies_then_stop"
        or cfg.get("work") != WORK
        or cfg.get("session_limits") != LIMITS
        or cfg.get("implementation") != implementation(root)
        or cfg.get("ordinary_PPO_allowed") is not False
        or cfg.get("promotion_allowed") is not False
        or cfg.get("automatic_follow_up") is not False
        or verified(root, cfg["collection_recipe"]) != root / PARENT_RECIPE
        or verified(root, cfg["assessment"]) != root / ASSESSMENT
    ):
        raise ValueError("Use the exact versioned fitting-only declaration")
    main, control = (_private_path(root, cfg[key]) for key in ("workspace", "control_workspace"))
    base = root / "artifacts/native-win-fitting"
    if main.parent != base or control.parent != base or main == control:
        raise ValueError("Use distinct private fitting and control workspaces")
    return dict(cfg)


def datasets(
    root: Path, ctx: dict[str, Any], collection: dict[str, Any], bank: dict[str, Any]
) -> tuple[Worlds, Worlds, dict[str, Any]]:
    plan = ctx["config"]["plan"]
    fit_cases = {case["key"]: case for case in plan["fit"]}
    dev_cases = {case["key"]: case for case in plan["heldout"]}
    cases = {row["case"]["key"]: row for row in collection["cases"]}
    forbidden = set(plan["reserved_evaluation_seeds"])
    forbidden.update(seed for case in dev_cases.values() for seed in case["seed_pool"])
    forbidden.update(
        seed for row in ctx["historical_failures"] for seed in row["case"]["seed_pool"]
    )
    model, other = (ctx["models"][player] for player in PLAYERS)
    if (
        type(model) is not CachedContextModel
        or type(other) is not CachedContextModel
        or (
            model.mode,
            model.feature_spec_id,
            model.actor.dimension,
            model.actor.input_normalization,
        )
        != (
            other.mode,
            other.feature_spec_id,
            other.actor.dimension,
            other.actor.input_normalization,
        )
    ):
        raise ValueError("Both copied actors must share the exact numerical input contract")

    fit: Worlds = {}
    dev: Worlds = {}
    stats: dict[str, Any] = {
        "fit_families": {},
        "fit_worlds": 0,
        "fit_decisions": 0,
        "fit_grouped_answers": 0,
        "development_cases": len(dev_cases),
        "development_probe_worlds": 0,
        "development_decisions": 0,
    }
    trace_pins: dict[str, str] = {}
    family_counts: Counter[str] = Counter()

    def from_saved(episode: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
        folder = local(root, episode["directory"])
        if (
            episode != identified(folder / "report.json")
            or episode["status"] != "complete"
            or not episode["curriculum_success"]
            or episode["optimizer_updates"] != 0
            or not episode["shutdown"]["clean_exit"]
            or episode["shutdown"]["runtime_errors"]
        ):
            raise ValueError("Only a sealed complete teacher continuation supplies labels")
        trace = folder / "shared-public.jsonl.gz"
        labels = steps(root, {"episode_directory": episode["directory"]})
        trace_pins[str(trace.relative_to(root))] = _sha_file(trace)
        return labels, episode["seed"]

    for lesson in bank["lessons"]:
        scenario = lesson["scenario"]
        key, world = scenario["key"], lesson["world"]
        case = cases[key]
        if (
            scenario != fit_cases.get(key)
            or lesson["partition"] != "fit"
            or world not in scenario["seed_pool"]
            or world in forbidden
            or world in fit
            or lesson["student_inputs_public_only"] is not True
            or lesson["ordinary_PPO_eligible"] is not False
            or case["status"] != "confirmed_teacher"
            or case["lesson_id"] != lesson["lesson_id"]
        ):
            raise ValueError("A withheld, historical or foreign lesson entered fitting")
        teacher = select(case["results"][0], case["results"][1:])
        if (
            teacher is None
            or teacher["report_id"] != lesson["episode_id"]
            or teacher["directory"] != lesson["episode_directory"]
            or teacher["partition"] != "fit"
        ):
            raise ValueError("Fitting lesson differs from the confirmed teacher")
        labels, seed = from_saved(teacher)
        if seed != world or len(labels) != lesson["meaningful_choices"]:
            raise ValueError("The admitted world or decision count changed")
        fit[world] = tuple(encode_decision(label, model, ctx["score"]) for label in labels)
        family_counts.update(label["family"] for label in labels)
        stats["fit_grouped_answers"] += sum("answer_factors" in label for label in labels)

    for key, case in dev_cases.items():
        row = cases[key]
        if (
            row["case"] != case
            or row["status"] != "heldout_probe_only"
            or row["fitting_labels_provided"] is not False
        ):
            raise ValueError("Development evidence changed its ownership")
        teacher = select(row["results"][0], row["results"][1:])
        if teacher is None:
            if row["teacher_selected_by_frozen_method"] is not None:
                raise ValueError("A failed teacher cannot supply a development probe")
            continue
        if (
            row["teacher_selected_by_frozen_method"] != teacher["report_id"]
            or teacher["partition"] != "heldout"
        ):
            raise ValueError("Wrong sealed development teacher")
        labels, seed = from_saved(teacher)
        if seed not in case["seed_pool"] or seed in fit or seed in dev:
            raise ValueError("A development probe overlaps another world")
        dev[seed] = tuple(encode_decision(label, model, ctx["score"]) for label in labels)

    stats.update(
        fit_worlds=len(fit),
        fit_decisions=sum(map(len, fit.values())),
        fit_families=dict(sorted(family_counts.items())),
        development_probe_worlds=len(dev),
        development_decisions=sum(map(len, dev.values())),
        source_traces=trace_pins,
    )
    return fit, dev, stats


def load(root: Path, *, require_control: bool = True) -> dict[str, Any]:
    declaration_path = RECIPE if require_control else CONTROL_RECIPE
    recipe = declaration(root, declaration_path)
    ctx = load_collection(root)
    assessment_summary = identified(verified(root, recipe["assessment"]))
    assessment = identified(verified(root, assessment_summary["assessment"]))
    collection = identified(verified(root, assessment_summary["collection"]))
    bank = identified(verified(root, assessment_summary["bank"]), "bank_id")
    completed(root, assessment_summary["owner_resource"])
    completed(root, assessment_summary["saved_assessment_resource"])
    if (
        assessment["status"] != "admitted_bank_independently_verified"
        or collection["status"] != "win_focused_curriculum_admitted"
        or assessment["collection_report_id"] != collection["report_id"]
        or recipe["bank_id"] != assessment["bank_id"]
        or bank["bank_id"] != assessment["bank_id"]
        or collection["bank_id"] != bank["bank_id"]
        or bank["config_id"] != ctx["config_id"]
        or collection["config_id"] != ctx["config_id"]
        or assessment["config_id"] != ctx["config_id"]
        or recipe["environment_id"] != ctx["environment"]["manifest_id"]
        or collection["environment_id"] != recipe["environment_id"]
        or assessment["environment_id"] != recipe["environment_id"]
        or bank["quality"] != collection["quality"]
        or bank["quality"] != assessment["quality"]
        or bank["quality"]["passed"] is not True
        or collection["optimizer_updates"] != 0
        or collection["training_allowed"] is not False
        or bank["schema_version"] != "native-win-curriculum-bank-v2"
        or bank["large_answer_contract"] != PLAN
        or bank["factor_labels_are_grouped_atomic_answers"] is not True
        or bank["heldout_labels_included"] is not False
        or bank["ordinary_PPO_eligible"] is not False
        or not all(assessment["checks_after"].values())
    ):
        raise ValueError("The separately assessed public fitting bank is required")
    check_sources(root, collection["sources"])
    check_sources(root, collection["evidence"])
    check_sources(root, assessment["sources"])
    objective = ObjectiveSpec.from_mapping(ctx["native"]["objective"])
    if objective != ctx["score"].evaluation_objective:
        raise ValueError("The terminal-victory objective changed")
    fit, dev, stats = datasets(root, ctx, collection, bank)
    if (
        stats["fit_worlds"] != assessment["admitted_lessons"]
        or stats["fit_decisions"] != assessment["meaningful_choices"]
        or stats["fit_grouped_answers"] != assessment["grouped_answers"]
        or stats["fit_families"] != assessment["label_families"]
        or stats["development_probe_worlds"] != assessment["quality"]["heldout_successes"]
        or max(map(len, fit.values())) != UPDATES
    ):
        raise ValueError("Reconstructed fitting coverage disagrees with the admitted bank")
    references = [recipe["assessment"], recipe["collection_recipe"]]
    references.extend(
        assessment_summary[key]
        for key in (
            "assessment",
            "collection",
            "bank",
            "owner_resource",
            "saved_assessment_resource",
        )
    )
    if require_control:
        control_refs = recipe["short_check"]
        control = identified(verified(root, control_refs["report"]))
        completed(root, control_refs["resource"])
        if (
            control["status"] != "world_balanced_copy_fitting_control_verified"
            or control["launch_binding_id"] != binding(recipe)
            or control["bank_id"] != bank["bank_id"]
            or control["dataset_id"] != manifest_identifier(stats)
            or control["copy_updates"] != len(PLAYERS) * CONTROL_UPDATES
            or control["main_fitting_started"] is not False
            or control["control_states_enter_main"] is not False
            or not control["checks"]
            or not all(control["checks"].values())
        ):
            raise ValueError("A current disposable-copy fitting and resume check is required")
        check_sources(root, control["evidence"])
        references.extend(control_refs.values())
    return {
        **ctx,
        "fitting_recipe": recipe,
        "fitting_sources": {
            **recipe["implementation"],
            declaration_path: _sha_file(root / declaration_path),
            **{ref["path"]: ref["sha256"] for ref in references},
        },
        "fit": fit,
        "development": dev,
        "dataset": stats,
        "dataset_id": manifest_identifier(stats),
        "objective": objective,
        "bank_id": bank["bank_id"],
    }


def verify_frozen(root: Path, ctx: dict[str, Any]) -> dict[str, bool]:
    check_sources(root, ctx["fitting_sources"])
    check_sources(root, ctx["dataset"]["source_traces"])
    return frozen_checks(ctx)
