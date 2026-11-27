from __future__ import annotations

import copy
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spireshift.bootstrap_teacher import load_bootstrap_state_set_document
from spireshift.core.manifest import RulesetIdentity, manifest_identifier
from spireshift.core.objective import ObjectiveSpec
from spireshift.models import _exact_keys, _integer, _list, _mapping
from spireshift.representations import model_input_from_mapping
from spireshift.splits import SplitManifest, SplitName
from spireshift.starting_evidence import (
    StartingEvidenceConfig,
    _identified,
    _identity,
    _validate_seed_window,
    load_verified_starting_option_evidence,
)
from spireshift.starting_options import starting_option_feature_tokens, starting_option_ids
from spireshift.trajectory_search import TRAJECTORY_SELECTION_RANK_ORDER

CONFIG_SCHEMA = "starting-repeatability-config-v1"
REPORT_SCHEMA = "starting-repeatability-report-v1"
FILENAME = "starting-repeatability.json"
CLAIM = "train_only_fixed_policy_starting_preference_repeatability"
LEVELS = ("encoded_context", "full_menu", "exact_public_state")
TARGETS = ("strong", "all_eligible")
REPORT_FIELDS = {
    "schema_version",
    "report_id",
    "configuration",
    "objective_id",
    "ruleset_manifest_id",
    "model_id",
    "training_report_id",
    "split_manifest_id",
    "sources",
    "complete_run_roles",
    "historical_fitting_inventory",
    "collection_summary",
    "comparisons",
    "strata",
    "confirmation",
    "decision",
    "terminal_victories",
    "independent_unit",
    "futures_per_option",
    "hidden_state_resampling",
    "optimizer_steps",
    "games_replayed_by_analysis",
    "training_started",
    "checkpoint_promoted",
    "claim_scope",
    "limitations",
}


@dataclass(frozen=True, slots=True)
class StartingRepeatabilityConfig:
    document: dict[str, Any]

    @classmethod
    def from_mapping(cls, value: object) -> StartingRepeatabilityConfig:
        doc = copy.deepcopy(_mapping(value, "starting repeatability config"))
        _exact_keys(
            doc,
            {
                "schema_version",
                "config_id",
                "objective_id",
                "historical_evidence_path",
                "historical_report_id",
                "historical_config",
                "collection_config",
                "prior_train_prefix_stop",
                "prior_seed_sources",
                "analysis",
                "resource_limits",
            },
            "starting repeatability config",
        )
        _identity(doc, "config_id")
        if doc["schema_version"] != CONFIG_SCHEMA or doc["objective_id"] != "terminal-victory-v1":
            raise ValueError("Repeatability must preserve terminal victory")
        historical = StartingEvidenceConfig.from_mapping(doc["historical_config"])
        fresh = StartingEvidenceConfig.from_mapping(doc["collection_config"])
        for key in (
            "model_id",
            "training_report_id",
            "ruleset_manifest_id",
            "split_manifest_id",
            "objective_id",
            "milestones",
            "frontier_ranking",
            "maximum_decisions_per_run",
        ):
            if (
                historical.document["trajectory_config"][key]
                != fresh.document["trajectory_config"][key]
            ):
                raise ValueError(f"Repeatability changes fixed continuation semantics: {key}")
        prefix = _integer(doc["prior_train_prefix_stop"], "prior train prefix")
        if (
            prefix < 0
            or fresh.runner.run_offset < prefix
            or set(historical.seeds) & set(fresh.seeds)
        ):
            raise ValueError("Repeatability fresh cohort overlaps prior training")
        _relative_path(doc["historical_evidence_path"])
        sources = _list(doc["prior_seed_sources"], "prior seed sources")
        if not sources or len({s["path"] for s in sources}) != len(sources):
            raise ValueError("Repeatability requires unique prior source inventories")
        for source in sources:
            _exact_keys(source, {"path", "kind", "source_id"}, "prior seed source")
            _relative_path(source["path"])
            if source["kind"] not in {"bootstrap_dataset", "trajectory_preference_collection"}:
                raise ValueError("Unsupported prior seed inventory kind")
        plan = _mapping(doc["analysis"], "repeatability analysis")
        _exact_keys(
            plan,
            {
                "matching_levels",
                "minimum_discovery_strict_runs",
                "minimum_discovery_majority",
                "minimum_confirmed_groups",
                "minimum_confirmation_runs",
                "minimum_strong_confirmation_runs",
                "alpha",
                "uncertainty_method",
                "primary_level",
                "primary_target",
                "stop_rule",
            },
            "repeatability analysis",
        )
        if (
            plan["matching_levels"] != list(LEVELS)
            or plan["uncertainty_method"] != "independent_run_hoeffding_v1"
            or plan["primary_level"] != "encoded_context"
            or plan["primary_target"] != "strong"
            or plan["stop_rule"] != "one_cohort_no_automatic_extension"
        ):
            raise ValueError("Unsupported repeatability analysis or stop rule")
        for key in (
            "minimum_discovery_strict_runs",
            "minimum_confirmed_groups",
            "minimum_confirmation_runs",
            "minimum_strong_confirmation_runs",
        ):
            if _integer(plan[key], key) < 1:
                raise ValueError("Repeatability coverage must be positive")
        if (
            isinstance(plan["alpha"], bool)
            or not 0 < plan["alpha"] < 1
            or isinstance(plan["minimum_discovery_majority"], bool)
            or not 0.5 < plan["minimum_discovery_majority"] <= 1
        ):
            raise ValueError("Invalid repeatability confidence or majority")
        limits = _mapping(doc["resource_limits"], "repeatability limits")
        _exact_keys(
            limits, {"wall_seconds", "cpu_seconds", "storage_bytes", "memory_bytes"}, "limits"
        )
        if any(_integer(v, k) < 1 for k, v in limits.items()):
            raise ValueError("Repeatability resource limits must be positive")
        return cls(doc)

    @property
    def historical(self) -> StartingEvidenceConfig:
        return StartingEvidenceConfig.from_mapping(self.document["historical_config"])

    @property
    def collection(self) -> StartingEvidenceConfig:
        return StartingEvidenceConfig.from_mapping(self.document["collection_config"])


def load_starting_repeatability_config(path: Path) -> StartingRepeatabilityConfig:
    return StartingRepeatabilityConfig.from_mapping(json.loads(path.read_text()))


def _relative_path(value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("Repeatability source path is missing")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Repeatability source path must be relative to the project")
    return path


def _source_path(root: Path, relative: str) -> Path:
    root = root.resolve()
    path = (root / _relative_path(relative)).resolve()
    if root not in path.parents:
        raise ValueError("Repeatability source escapes project directory")
    return path


def _prior_inventory(
    source: dict[str, Any],
    root: Path,
    split: SplitManifest,
    ruleset: RulesetIdentity,
) -> dict[str, Any]:
    doc = _mapping(json.loads(_source_path(root, source["path"]).read_text()), "prior seed source")
    field = "dataset_id" if source["kind"] == "bootstrap_dataset" else "collection_id"
    _identity(doc, field)
    if doc[field] != source["source_id"]:
        raise ValueError("Repeatability prior seed source identity differs")
    if source["kind"] == "bootstrap_dataset":
        state_set = load_bootstrap_state_set_document(doc["state_set"])
        provenance = doc["state_set"]
        seeds = sorted({c.run_seed for c in state_set.cases})
    else:
        provenance = doc
        seeds = sorted({_integer(c["run_seed"], "prior run seed") for c in doc["cases"]})
    if (
        provenance["split_manifest_id"] != split.manifest_id
        or provenance["ruleset_manifest_id"] != ruleset.manifest_id
        or provenance["objective_id"] != split.objective_id
        or any(split.split_for_seed(s).value != provenance["partition"] for s in seeds)
    ):
        raise ValueError("Repeatability prior inventory ownership or environment differs")
    return {
        **source,
        "complete_run_seeds": seeds,
        "verification_scope": "content_addressed_seed_metadata_no_case_replay",
    }


@dataclass(frozen=True, slots=True)
class RepeatabilityInputs:
    config: StartingRepeatabilityConfig
    historical_report: dict[str, Any]
    historical_cases: list[dict[str, Any]]
    prior_inventories: list[dict[str, Any]]
    split_manifest: SplitManifest
    ruleset: RulesetIdentity
    objective: ObjectiveSpec


def prepare_starting_repeatability(
    *,
    config: StartingRepeatabilityConfig,
    project_root: Path,
    split_manifest: SplitManifest,
    ruleset: RulesetIdentity,
    objective: ObjectiveSpec,
) -> RepeatabilityInputs:
    if objective.objective_id != config.document["objective_id"]:
        raise ValueError("Repeatability objective differs")
    _validate_seed_window(config.collection, split_manifest)
    _validate_seed_window(config.historical, split_manifest)
    prior = [
        _prior_inventory(s, project_root, split_manifest, ruleset)
        for s in config.document["prior_seed_sources"]
    ]
    excluded = set(
        split_manifest.seeds(SplitName.TRAIN)[: config.document["prior_train_prefix_stop"]]
    )
    excluded.update(config.historical.seeds)
    excluded.update(s for inventory in prior for s in inventory["complete_run_seeds"])
    if excluded & set(config.collection.seeds):
        raise ValueError("Repeatability fresh cohort overlaps previous fitted or inspected seeds")
    historical_report, historical_cases = load_verified_starting_option_evidence(
        _source_path(project_root, config.document["historical_evidence_path"]),
        config=config.historical,
        split_manifest=split_manifest,
        ruleset=ruleset,
    )
    if historical_report["report_id"] != config.document["historical_report_id"]:
        raise ValueError("Repeatability historical evidence identity differs")
    return RepeatabilityInputs(
        config, historical_report, historical_cases, prior, split_manifest, ruleset, objective
    )


def _sign(value: float) -> int:
    return int(value > 0) - int(value < 0)


def _pair_rows(cases: list[dict[str, Any]], roles: dict[int, str]) -> list[dict[str, Any]]:
    rows = []
    for case in cases:
        seed = case["run_seed"]
        if seed not in roles or case["status"] != "completed":
            continue
        rep = model_input_from_mapping(case["source_model_input"])
        options = starting_option_ids(rep)
        if options is None or len(set(options)) != 3:
            raise ValueError("Repeatability requires three distinct public options")
        context = {
            json.loads(token)[-1]: value
            for token, value in starting_option_feature_tokens(rep, tuple(sorted(options)))[
                0
            ].items()
        }
        context_id = manifest_identifier(context)
        exact_id = manifest_identifier(
            {
                "observation": {
                    k: v for k, v in case["source_observation"].items() if k != "state_hash"
                },
                "legal_actions": case["source_legal_actions"],
            }
        )
        by_action = dict(zip((c.source_action_id for c in rep.candidates), options, strict=True))
        for comparison in case["comparisons"]:
            left, right = (by_action[comparison[k]] for k in ("left_action_id", "right_action_id"))
            a, b = comparison["left_rank"], comparison["right_rank"]
            if left > right:
                left, right, a, b = right, left, b, a
            component = comparison["deciding_rank_component"]
            rows.append(
                {
                    "run_seed": seed,
                    "role": roles[seed],
                    "case_id": case["case_id"],
                    "comparison_id": comparison["comparison_id"],
                    "option_pair": [left, right],
                    "ordered_menu": list(options),
                    "encoded_context_id": context_id,
                    "full_menu_id": manifest_identifier(
                        {"context_id": context_id, "menu": sorted(options)}
                    ),
                    "exact_public_state_id": exact_id,
                    "deciding_rank_component": component,
                    "label": comparison["label"],
                    "eligible_policy_preference": comparison["eligible_policy_preference"],
                    "all_eligible_sign": _sign(int(tuple(a) > tuple(b)) - int(tuple(a) < tuple(b)))
                    if comparison["eligible_policy_preference"]
                    else 0,
                    "strong_sign": int(tuple(a[:4]) > tuple(b[:4]))
                    - int(tuple(a[:4]) < tuple(b[:4])),
                    "floor_sign": _sign(a[3] - b[3]),
                    "paired_rank_differences": dict(
                        zip(
                            TRAJECTORY_SELECTION_RANK_ORDER,
                            (x - y for x, y in zip(a, b, strict=True)),
                            strict=True,
                        )
                    ),
                }
            )
    keys = [(r["run_seed"], tuple(r["option_pair"])) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Repeatability contains duplicate correlated run/pair evidence")
    return sorted(rows, key=lambda r: (r["run_seed"], r["option_pair"]))


def _group_key(row: dict[str, Any], level: str) -> str:
    return manifest_identifier({"option_pair": row["option_pair"], "context": row[f"{level}_id"]})


def _direction(rows: list[dict[str, Any]], target: str, plan: dict[str, Any]) -> dict[str, Any]:
    counts = Counter(r[f"{target}_sign"] for r in rows)
    strict = counts[1] + counts[-1]
    majority = max(counts[1], counts[-1]) / strict if strict else 0.0
    eligible = (
        strict >= plan["minimum_discovery_strict_runs"]
        and majority >= plan["minimum_discovery_majority"]
    )
    return {
        "positive_runs": counts[1],
        "negative_runs": counts[-1],
        "tied_or_ineligible_runs": counts[0],
        "strict_runs": strict,
        "majority_fraction": majority,
        "direction": _sign(counts[1] - counts[-1]) if eligible else None,
    }


def _counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "independent_runs": sorted({r["run_seed"] for r in rows}),
        "pairs": len(rows),
        "components": dict(
            sorted(Counter(str(r["deciding_rank_component"]) for r in rows).items())
        ),
        "floor_positive_runs": sum(r["floor_sign"] == 1 for r in rows),
        "floor_negative_runs": sum(r["floor_sign"] == -1 for r in rows),
        "floor_tied_runs": sum(r["floor_sign"] == 0 for r in rows),
    }


def _strata(rows: list[dict[str, Any]], level: str, plan: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_group_key(row, level)].append(row)
    result = []
    for key, members in sorted(grouped.items()):
        discovery = [r for r in members if r["role"] != "confirmation"]
        confirmation = [r for r in members if r["role"] == "confirmation"]
        result.append(
            {
                "group_id": key,
                "option_pair": members[0]["option_pair"],
                "matching_context_id": members[0][f"{level}_id"],
                "ordered_menus": sorted({tuple(r["ordered_menu"]) for r in members}),
                "exact_public_states": len({r["exact_public_state_id"] for r in members}),
                "discovery": _counts(discovery),
                "confirmation": _counts(confirmation),
                "discovery_targets": {
                    target: _direction(discovery, target, plan) for target in TARGETS
                },
                "floor_direction_disagreement_in_discovery": any(
                    r["floor_sign"] == 1 for r in discovery
                )
                and any(r["floor_sign"] == -1 for r in discovery),
                "floor_direction_disagreement_in_confirmation": any(
                    r["floor_sign"] == 1 for r in confirmation
                )
                and any(r["floor_sign"] == -1 for r in confirmation),
                "paired_difference_means_by_role": {
                    name: {
                        k: sum(r["paired_rank_differences"][k] for r in subset) / len(subset)
                        for k in TRAJECTORY_SELECTION_RANK_ORDER
                    }
                    if subset
                    else None
                    for name, subset in (("discovery", discovery), ("confirmation", confirmation))
                },
            }
        )
    return result


def _run_interval(scores: dict[int, list[float]], alpha: float) -> dict[str, Any]:
    # Reduce all correlated pairs from each complete seed before computing uncertainty.
    run_scores = {str(seed): sum(values) / len(values) for seed, values in sorted(scores.items())}
    n = len(run_scores)
    mean = sum(run_scores.values()) / n if n else None
    radius = math.sqrt(math.log(2 / alpha) / (2 * n)) if n else None
    return {
        "independent_runs": n,
        "mean_agreement": mean,
        "interval": [max(0.0, mean - radius), min(1.0, mean + radius)]
        if mean is not None and radius is not None
        else None,
        "run_scores": run_scores,
        "alpha": alpha,
        "method": "independent_run_hoeffding_v1",
    }


def _confirmation(
    rows: list[dict[str, Any]],
    groups: list[dict[str, Any]],
    level: str,
    target: str,
    plan: dict[str, Any],
) -> dict[str, Any]:
    directions = {
        g["group_id"]: g["discovery_targets"][target]["direction"]
        for g in groups
        if g["discovery_targets"][target]["direction"] is not None
    }
    scores: dict[int, list[float]] = defaultdict(list)
    strong_runs = set()
    confirmed = set()
    directions_by_run = []
    for row in rows:
        key = _group_key(row, level)
        if row["role"] != "confirmation" or key not in directions:
            continue
        sign = row[f"{target}_sign"]
        score = 0.5 if sign == 0 else float(sign == directions[key])
        scores[row["run_seed"]].append(score)
        if row["strong_sign"]:
            strong_runs.add(row["run_seed"])
        confirmed.add(key)
        directions_by_run.append(
            {
                "run_seed": row["run_seed"],
                "comparison_id": row["comparison_id"],
                "group_id": key,
                "discovery_direction": directions[key],
                "observed_direction": sign,
                "agreement_score": score,
            }
        )
    return {
        "qualified_discovery_groups": len(directions),
        "confirmed_groups": len(confirmed),
        "covered_strong_runs": len(strong_runs),
        "paired_observations": len(directions_by_run),
        "tie_score": 0.5,
        "interval": _run_interval(dict(scores), plan["alpha"]),
        "observations": directions_by_run,
    }


def _quantize(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 12)
    if isinstance(value, dict):
        return {k: _quantize(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_quantize(v) for v in value]
    return value


def _decision(
    primary: dict[str, Any], summary: dict[str, Any], plan: dict[str, Any]
) -> dict[str, Any]:
    checks = {
        "all_fresh_runs_terminal_and_complete": summary["failed_runs"] == 0,
        "replicated_pair_coverage": primary["confirmed_groups"] >= plan["minimum_confirmed_groups"],
        "independent_confirmation_coverage": primary["interval"]["independent_runs"]
        >= plan["minimum_confirmation_runs"],
        "strong_confirmation_coverage": primary["covered_strong_runs"]
        >= plan["minimum_strong_confirmation_runs"],
    }
    bound = _quantize(primary["interval"]["interval"])
    status = "inconclusive"
    if all(checks.values()) and bound is not None:
        if bound[0] > 0.5:
            status = "supported"
        elif bound[1] < 0.5:
            status = "unsupported"
    return {
        "status": status,
        "scope": "auxiliary_strong_preference_pooling_on_matched_public_strata",
        "coverage_checks": checks,
        "primary_level": plan["primary_level"],
        "primary_target": plan["primary_target"],
        "chance_reference": 0.5,
        "next_step": "propose_separately_frozen_training_and_fresh_confirmation"
        if status == "supported"
        else "stop_starting_choice_experiment_return_to_combat_run_level_foundation",
        "automatic_extension_allowed": False,
        "automatic_training_allowed": False,
    }


def analyze_starting_repeatability(
    inputs: RepeatabilityInputs,
    fresh_report: dict[str, Any],
    fresh_cases: list[dict[str, Any]],
) -> dict[str, Any]:
    """Analyze source-verified cases, preserving all configured seed denominators."""
    config = inputs.config
    _identity(fresh_report, "report_id")
    if (
        fresh_report["configuration"] != config.collection.document
        or [c["run_seed"] for c in fresh_cases] != list(config.collection.seeds)
        or [c["case_id"] for c in fresh_cases] != [r["case_id"] for r in fresh_report["cases"]]
    ):
        raise ValueError("Repeatability analysis fresh source bindings or coverage differ")
    historical_roles = {
        s: "historical_fit" for s in config.historical.document["complete_run_subfolds"]["fit"]
    }
    new_roles = {
        s: "discovery"
        if s in config.collection.document["complete_run_subfolds"]["fit"]
        else "confirmation"
        for s in config.collection.seeds
    }
    rows = _pair_rows(inputs.historical_cases, historical_roles) + _pair_rows(
        fresh_cases, new_roles
    )
    rows.sort(key=lambda r: (r["run_seed"], r["option_pair"]))
    plan = config.document["analysis"]
    strata = {level: _strata(rows, level, plan) for level in LEVELS}
    confirmation = {
        level: {
            target: _confirmation(rows, strata[level], level, target, plan) for target in TARGETS
        }
        for level in LEVELS
    }
    primary = confirmation[plan["primary_level"]][plan["primary_target"]]
    historical_rows = [r for r in rows if r["role"] == "historical_fit"]
    historical_groups = {level: _strata(historical_rows, level, plan) for level in LEVELS}
    body = {
        "schema_version": REPORT_SCHEMA,
        "configuration": config.document,
        "objective_id": inputs.objective.objective_id,
        "ruleset_manifest_id": inputs.ruleset.manifest_id,
        "model_id": config.collection.runner.model_id,
        "training_report_id": config.collection.runner.training_report_id,
        "split_manifest_id": inputs.split_manifest.manifest_id,
        "sources": {
            "historical_report_id": inputs.historical_report["report_id"],
            "fresh_report_id": fresh_report["report_id"],
            "prior_seed_inventories": inputs.prior_inventories,
            "source_verification": "saved_case_contracts_no_engine_replay",
        },
        "complete_run_roles": {
            "historical_fit": sorted(historical_roles),
            "excluded_historical_selection": config.historical.document["complete_run_subfolds"][
                "selection"
            ],
            "discovery": config.collection.document["complete_run_subfolds"]["fit"],
            "confirmation": config.collection.document["complete_run_subfolds"]["selection"],
        },
        "historical_fitting_inventory": {
            "cases": len(historical_roles),
            "comparisons": len(historical_rows),
            "groups": {level: len(groups) for level, groups in historical_groups.items()},
            "floor_disagreement_groups": {
                level: sum(g["floor_direction_disagreement_in_discovery"] for g in groups)
                for level, groups in historical_groups.items()
            },
            "option_ids": sorted({i for r in historical_rows for i in r["ordered_menu"]}),
        },
        "collection_summary": fresh_report["summary"],
        "comparisons": rows,
        "strata": strata,
        "confirmation": confirmation,
        "decision": _decision(primary, fresh_report["summary"], plan),
        "terminal_victories": fresh_report["summary"]["terminal_victories"],
        "independent_unit": "complete_run_seed",
        "futures_per_option": 1,
        "hidden_state_resampling": False,
        "optimizer_steps": 0,
        "games_replayed_by_analysis": 0,
        "training_started": False,
        "checkpoint_promoted": False,
        "claim_scope": CLAIM,
        "limitations": [
            "Fresh seeds vary naturally occurring public contexts and deterministic futures; "
            "they are not repeated stochastic draws from identical states.",
            "Directions use historical fitting and fresh discovery only. Confirmation never "
            "chooses the strata, directions or thresholds.",
            "Only the prespecified encoded-context strong comparison drives the decision. "
            "Other matching levels and all-eligible scores are descriptive.",
            "Hoeffding bounds assume independent complete-run seeds and bounded run-mean "
            "agreement, conditional on discovery and matched public strata.",
            "Three pairs from one seed and overlapping strata are correlated; each seed "
            "contributes one mean score to its interval.",
            "Unmatched confirmation seeds remain in cohort denominators but not the "
            "conditional matched-stratum interval. Failures block a supported conclusion.",
            "Floor directions ignore higher-priority rank components and are diagnostic only; "
            "strong directions preserve victory, Act 1 clear, boss reach, then floor.",
            "Saved verification checks logged source/continuation contracts, not independent "
            "emulator replay or real-game equivalence.",
            "Repeatability does not prove better gameplay, terminal-value readiness or "
            "adaptive-controller readiness. Inspected confirmation cannot become an untouched "
            "later test.",
        ],
    }
    quantized = _quantize(body)
    # Frozen configuration identities use their original numbers, including 2/3 majority.
    quantized["configuration"] = config.document
    return _identified(quantized, "report_id")


def summarize_starting_repeatability(report: dict[str, Any]) -> dict[str, Any]:
    primary = report["confirmation"]["encoded_context"]["strong"]
    return {
        "report_id": report["report_id"],
        "completed_runs": report["collection_summary"]["completed_runs"],
        "failed_runs": report["collection_summary"]["failed_runs"],
        "historical_fitting_inventory": report["historical_fitting_inventory"],
        "confirmed_strong_groups": primary["confirmed_groups"],
        "confirmation_runs": primary["interval"]["independent_runs"],
        "strong_confirmation_runs": primary["covered_strong_runs"],
        "mean_agreement": primary["interval"]["mean_agreement"],
        "agreement_interval": primary["interval"]["interval"],
        "decision": report["decision"],
        "terminal_victories": report["terminal_victories"],
        "training_started": False,
        "checkpoint_promoted": False,
        "claim_scope": CLAIM,
    }


def load_starting_repeatability_report(
    path: Path, config: StartingRepeatabilityConfig
) -> dict[str, Any]:
    """Check cached identity and frozen bindings only; do not reload or replay source cases."""
    report = _mapping(json.loads(path.read_text()), "repeatability report")
    _exact_keys(report, REPORT_FIELDS, "repeatability report")
    _identity(report, "report_id")
    runner = config.collection.runner
    expected = {
        "schema_version": REPORT_SCHEMA,
        "configuration": config.document,
        "objective_id": runner.objective_id,
        "model_id": runner.model_id,
        "training_report_id": runner.training_report_id,
        "ruleset_manifest_id": runner.ruleset_manifest_id,
        "split_manifest_id": runner.split_manifest_id,
        "claim_scope": CLAIM,
        "independent_unit": "complete_run_seed",
        "futures_per_option": 1,
        "training_started": False,
        "checkpoint_promoted": False,
        "optimizer_steps": 0,
        "games_replayed_by_analysis": 0,
        "hidden_state_resampling": False,
    }
    if any(report[k] != v for k, v in expected.items()):
        raise ValueError("Repeatability cached bindings or claim differ")
    if report["sources"]["historical_report_id"] != config.document["historical_report_id"]:
        raise ValueError("Repeatability cached historical binding differs")
    primary = report["confirmation"]["encoded_context"]["strong"]
    if report["decision"] != _decision(
        primary, report["collection_summary"], config.document["analysis"]
    ):
        raise ValueError("Repeatability cached decision differs from frozen checks")
    return report
