from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, cast

from spireshift.combat_features import (
    LAYOUT_SCHEMA,
    SELECTION_LAYOUT_SCHEMA,
    CombatLayout,
    bind_public_combat,
)
from spireshift.core.manifest import RulesetIdentity, manifest_identifier
from spireshift.core.objective import ObjectiveSpec
from spireshift.models import _dot, _exact_keys, _integer, _mapping, _quantize_artifact
from spireshift.production_models import (
    ProductionTrainingConfig,
    _load_curriculum_examples,
    _ProductionExample,
    _safe_child,
    load_production_model_checkpoint,
    load_production_training_report,
    production_model_from_checkpoint,
)
from spireshift.splits import SplitManifest, SplitName
from spireshift.starting_repeatability import (
    load_starting_repeatability_config,
    load_starting_repeatability_report,
)

CONFIG_SCHEMA = "combat-foundation-audit-config-v1"
REPORT_SCHEMA = "combat-foundation-audit-v1"
FILENAME = "combat-foundation-audit.json"
CLAIM = "verified_train_only_public_combat_binding_and_label_coverage"


def _identified(doc: dict[str, Any], field: str) -> None:
    if doc.get(field) != manifest_identifier({k: v for k, v in doc.items() if k != field}):
        raise ValueError(f"Combat foundation {field} mismatch")


@dataclass(frozen=True, slots=True)
class CombatFoundationConfig:
    document: dict[str, Any]

    @classmethod
    def from_mapping(cls, value: object) -> CombatFoundationConfig:
        d = copy.deepcopy(_mapping(value, "combat foundation config"))
        _exact_keys(
            d,
            {
                "schema_version",
                "config_id",
                "objective",
                "parent_checkpoint",
                "parent_report",
                "model_id",
                "training_report_id",
                "curriculum_path",
                "dataset_id",
                "split_manifest_id",
                "layout",
                "layout_sources",
                "starting_study",
                "complete_run_subfolds",
                "analysis",
                "resource_limits",
            },
            "combat foundation config",
        )
        _identified(d, "config_id")
        if d["schema_version"] != CONFIG_SCHEMA:
            raise ValueError("Unsupported combat foundation audit config")
        ObjectiveSpec.from_mapping(_mapping(d["objective"], "objective"))
        layout = CombatLayout.from_mapping(d["layout"])
        if layout.schema_version not in {LAYOUT_SCHEMA, SELECTION_LAYOUT_SCHEMA}:
            raise ValueError("Archived combat audit supports only its original v1/v2 layouts")
        for key in ("model_id", "training_report_id", "dataset_id", "split_manifest_id"):
            v = d[key]
            if not isinstance(v, str) or len(v) != 71 or not v.startswith("sha256:"):
                raise ValueError(f"Missing combat foundation identity: {key}")
            if any(c not in "0123456789abcdef" for c in v[7:]):
                raise ValueError(f"Invalid combat foundation identity: {key}")
        for key in ("parent_checkpoint", "parent_report", "curriculum_path"):
            _relative_path(d[key])
        if not isinstance(d["layout_sources"], list) or not d["layout_sources"]:
            raise ValueError("Combat layout needs pinned source evidence")
        seen_sources = set()
        for source in d["layout_sources"]:
            _exact_keys(source, {"path", "sha256"}, "layout source")
            _relative_path(source["path"])
            if source["path"] in seen_sources:
                raise ValueError("Duplicate combat layout source")
            seen_sources.add(source["path"])
            if (
                not isinstance(source["sha256"], str)
                or len(source["sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in source["sha256"])
            ):
                raise ValueError("Invalid combat layout source hash")
        s = _mapping(d["starting_study"], "starting study")
        _exact_keys(s, {"config_path", "report_path", "report_id"}, "starting study")
        _relative_path(s["config_path"])
        _relative_path(s["report_path"])
        if not isinstance(s["report_id"], str) or not s["report_id"].startswith("sha256:"):
            raise ValueError("Starting study identity is missing")
        runs = _mapping(d["complete_run_subfolds"], "complete run subfolds")
        _exact_keys(runs, {"fit", "selection"}, "complete run subfolds")
        for name in runs:
            seeds = runs[name]
            if (
                not isinstance(seeds, list)
                or not seeds
                or any(
                    not isinstance(seed, int) or isinstance(seed, bool) or seed < 0
                    for seed in seeds
                )
                or seeds != sorted(set(seeds))
            ):
                raise ValueError("Invalid complete-run combat subfold")
        if set(runs["fit"]) & set(runs["selection"]):
            raise ValueError("Combat subfolds share complete runs")
        a = _mapping(d["analysis"], "combat analysis")
        _exact_keys(
            a,
            {
                "encoder_id",
                "vector_dimension",
                "pairwise_noise_floor",
                "minimum_samples",
                "minimum_fit_signal_runs",
                "minimum_selection_signal_runs",
                "minimum_fit_card_ids",
                "minimum_fit_floor_bins",
                "half_split_rule",
                "outcome_rank",
                "stop_rule",
            },
            "combat analysis",
        )
        if (
            a["encoder_id"] != layout.encoder_id
            or a["half_split_rule"] != "both_strict_same_direction"
            or a["outcome_rank"] != ["terminal_victory", "maximum_floor"]
            or a["stop_rule"] != "report_only_no_automatic_training_or_collection"
        ):
            raise ValueError("Unsupported combat foundation analysis plan")
        for key in (
            "minimum_samples",
            "minimum_fit_signal_runs",
            "minimum_selection_signal_runs",
            "minimum_fit_card_ids",
            "minimum_fit_floor_bins",
        ):
            if _integer(a[key], key) < 1:
                raise ValueError("Combat coverage limits must be positive")
        if a["minimum_samples"] < 4:
            raise ValueError("Paired combat evidence needs at least four samples")
        if not 64 <= _integer(a["vector_dimension"], "vector dimension") <= 65536:
            raise ValueError("Invalid combat vector dimension")
        noise = a["pairwise_noise_floor"]
        if isinstance(noise, bool) or not isinstance(noise, (int, float)) or not 0 < noise < 1:
            raise ValueError("Combat pairwise noise floor must be in (0, 1)")
        limits = _mapping(d["resource_limits"], "combat audit limits")
        _exact_keys(
            limits, {"wall_seconds", "cpu_seconds", "memory_bytes", "storage_bytes"}, "limits"
        )
        if any(_integer(value, name) <= 0 for name, value in limits.items()):
            raise ValueError("Combat resource caps must be positive")
        return cls(d)


def _relative_path(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or Path(value).is_absolute()
        or ".." in Path(value).parts
    ):
        raise ValueError("Combat source path must remain inside its project root")
    return value


def load_combat_foundation_config(path: Path) -> CombatFoundationConfig:
    return CombatFoundationConfig.from_mapping(json.loads(path.read_text()))


def _pair_evidence(
    item: _ProductionExample, left: int, right: int, plan: dict[str, Any]
) -> dict[str, Any]:
    x, y = item.outcomes[left], item.outcomes[right]
    if len(x) != len(y):
        raise ValueError("Combat candidate paired-sample counts differ")
    completed = all(o.terminal for o in x + y)
    signs = []
    for a, b in zip(x, y, strict=True):
        ar, br = (a.terminal_victory, a.maximum_floor), (b.terminal_victory, b.maximum_floor)
        signs.append(int(ar > br) - int(ar < br))
    p = (sum(signs) / len(signs) + 1) / 2 if signs else 0.5
    mid = len(signs) // 2
    halves = [sum(signs[:mid]), sum(signs[mid:])]
    stable = halves[0] * halves[1] > 0
    eligible = (
        completed
        and len(signs) >= plan["minimum_samples"]
        and stable
        and abs(2 * p - 1) > plan["pairwise_noise_floor"]
    )
    return {
        "samples": len(signs),
        "completed": completed,
        "left_preference_probability": p,
        "half_split_direction_sums": halves,
        "half_split_stable": stable,
        "reliable_advancement": eligible,
        "paired_terminal_victory_variation": any(
            a.terminal_victory != b.terminal_victory for a, b in zip(x, y, strict=True)
        ),
        "paired_maximum_floor_variation": any(
            a.maximum_floor != b.maximum_floor for a, b in zip(x, y, strict=True)
        ),
    }


def _decision(summary: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    fit, selection = summary["by_subfold"]["fit"], summary["by_subfold"]["selection"]
    checks = {
        "every_combat_state_bound": summary["binding_failures"] == 0
        and summary["combat_states"] > 0,
        "fitting_run_signal": fit["signal_runs"] >= plan["minimum_fit_signal_runs"],
        "selection_run_signal": selection["signal_runs"] >= plan["minimum_selection_signal_runs"],
        "fitting_card_coverage": len(fit["signal_card_ids"]) >= plan["minimum_fit_card_ids"],
        "fitting_floor_coverage": len(fit["signal_floor_bins"]) >= plan["minimum_fit_floor_bins"],
    }
    sufficient = all(checks.values())
    return {
        "coverage_checks": checks,
        "pilot_data_sufficient": sufficient,
        "next_step": "freeze_combat_residual_training_and_fresh_run_confirmation"
        if sufficient
        else "repair_binding_failures_before_training"
        if not checks["every_combat_state_bound"]
        else "design_bounded_combat_teacher_collection_before_training",
        "automatic_training_allowed": False,
        "automatic_collection_allowed": False,
        "foundation_ready": False,
        "adaptive_controller_allowed": False,
    }


def _summarize_rows(
    rows: list[dict[str, Any]], roles: dict[int, str], source_states: int
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "source_states": source_states,
        "source_runs": len(roles),
        "combat_states": len(rows),
        "bound_combat_states": sum(r["binding_status"] == "completed" for r in rows),
        "binding_failures": sum(r["binding_status"] == "failed" for r in rows),
        "terminal_victories_in_saved_combat_outcomes": sum(
            r["terminal_victories_in_saved_outcomes"] for r in rows
        ),
        "by_subfold": {},
    }
    for role in ("fit", "selection"):
        group = [row for row in rows if row["subfold"] == role]
        signal = [row for row in group if any(p["learnable_advancement"] for p in row["pairs"])]
        pairs = [pair for row in group for pair in row["pairs"]]
        by_run = {}
        for seed in sorted({row["run_seed"] for row in group}):
            seed_rows = [row for row in group if row["run_seed"] == seed]
            by_run[str(seed)] = {
                "combat_states": len(seed_rows),
                "mean_parent_auxiliary_regret": sum(
                    row["parent_auxiliary_regret"] for row in seed_rows
                )
                / len(seed_rows),
                "signal_states": sum(
                    any(p["learnable_advancement"] for p in row["pairs"]) for row in seed_rows
                ),
            }
        summary["by_subfold"][role] = {
            "complete_runs": sum(v == role for v in roles.values()),
            "combat_runs": len(by_run),
            "combat_states": len(group),
            "binding_failures": sum(row["binding_status"] == "failed" for row in group),
            "candidate_pairs": len(pairs),
            "reliable_advancement_pairs": sum(p["reliable_advancement"] for p in pairs),
            "learnable_advancement_pairs": sum(p["learnable_advancement"] for p in pairs),
            "hash_alias_pairs": sum(p["hash_alias"] for p in pairs),
            "semantically_identical_reliable_pairs": sum(
                p["reliable_advancement"] and p["semantic_features_equal"] for p in pairs
            ),
            "signal_states": len(signal),
            "signal_runs": len({row["run_seed"] for row in signal}),
            "signal_floor_bins": sorted({row["source_floor"] for row in signal}),
            "card_ids": sorted(
                {
                    binding["card"]["card_id"]
                    for row in group
                    for binding in row["bindings"]
                    if binding["card"] is not None
                }
            ),
            "signal_card_ids": sorted(
                {
                    row["bindings"][index]["card"]["card_id"]
                    for row in group
                    for pair in row["pairs"]
                    if pair["learnable_advancement"]
                    for index in (pair["left"], pair["right"])
                    if row["bindings"][index]["card"] is not None
                }
            ),
            "learnable_pair_kinds": dict(
                sorted(
                    Counter(
                        " vs ".join(
                            sorted(
                                row["bindings"][index]["kind"]
                                for index in (pair["left"], pair["right"])
                            )
                        )
                        for row in group
                        for pair in row["pairs"]
                        if pair["learnable_advancement"]
                    ).items()
                )
            ),
            "action_kinds": dict(
                sorted(
                    Counter(binding["kind"] for row in group for binding in row["bindings"]).items()
                )
            ),
            "mean_run_parent_auxiliary_regret": sum(
                v["mean_parent_auxiliary_regret"] for v in by_run.values()
            )
            / len(by_run)
            if by_run
            else None,
            "by_run": by_run,
        }
    return summary


def analyze_combat_foundation(
    *,
    examples: tuple[_ProductionExample, ...],
    config: CombatFoundationConfig,
    parent_weights: dict[int, float],
) -> dict[str, Any]:
    """Analyze source-verified train examples, with no fitting or engine calls."""
    d = config.document
    layout = CombatLayout.from_mapping(d["layout"])
    roles = {seed: role for role, seeds in d["complete_run_subfolds"].items() for seed in seeds}
    if {item.run_seed for item in examples} != set(roles):
        raise ValueError("Combat source complete runs differ from the frozen subfolds")
    if len({item.state_id for item in examples}) != len(examples):
        raise ValueError("Duplicate combat source state ID")
    rows = []
    for item in examples:
        if item.decision_type != "combat":
            continue
        rep = item.representation
        if rep.decision_type != item.decision_type:
            raise ValueError("Combat record and public representation phases differ")
        scores = [_dot(parent_weights, f) for f in item.candidate_features]
        selected = max(range(len(scores)), key=lambda i: (scores[i], -i))
        row: dict[str, Any] = {
            "state_id": item.state_id,
            "run_seed": item.run_seed,
            "subfold": roles[item.run_seed],
            "representation_hash": rep.representation_hash,
            "source_state_hash": rep.source_state_hash,
            "candidate_action_ids": [c.source_action_id for c in rep.candidates],
            "parent_selected_candidate": selected,
            "parent_auxiliary_regret": max(item.mean_progress_utilities)
            - item.mean_progress_utilities[selected],
            "terminal_victories_in_saved_outcomes": sum(
                o.terminal_victory for outcomes in item.outcomes for o in outcomes
            ),
            "binding_status": "failed",
            "binding_error": None,
            "bindings": [],
            "feature_digests": [],
            "source_floor": None,
            "pairs": [],
        }
        try:
            bound = bind_public_combat(rep, layout)
            assert bound is not None
            vectors = bound.vectors(d["analysis"]["vector_dimension"])
            row.update(
                binding_status="completed",
                bindings=list(bound.bindings),
                feature_digests=list(bound.feature_digests()),
                source_floor=bound.context["floor"],
            )
            for left, right in combinations(range(len(bound.bindings)), 2):
                evidence = _pair_evidence(item, left, right, d["analysis"])
                tokens_equal = bound.tokens[left] == bound.tokens[right]
                vector_equal = vectors[left] == vectors[right]
                evidence.update(
                    left=left,
                    right=right,
                    semantic_features_equal=tokens_equal,
                    hashed_vectors_equal=vector_equal,
                    hash_alias=vector_equal and not tokens_equal,
                    learnable_advancement=evidence["reliable_advancement"] and not vector_equal,
                )
                row["pairs"].append(evidence)
        except ValueError as error:
            row["binding_status"] = "failed"
            row["binding_error"] = str(error)
        rows.append(row)
    rows = cast(list[dict[str, Any]], _quantize_artifact(rows))
    summary = _summarize_rows(rows, roles, len(examples))
    return cast(
        dict[str, Any],
        _quantize_artifact(
            {
                "schema_version": REPORT_SCHEMA,
                "config_id": d["config_id"],
                "objective": d["objective"],
                "sources": {
                    "dataset_id": d["dataset_id"],
                    "model_id": d["model_id"],
                    "training_report_id": d["training_report_id"],
                    "split_manifest_id": d["split_manifest_id"],
                    "ruleset_manifest_id": layout.ruleset_manifest_id,
                    "starting_study_report_id": d["starting_study"]["report_id"],
                },
                "complete_run_subfolds": d["complete_run_subfolds"],
                "encoder_id": layout.encoder_id,
                "summary": summary,
                "rows": rows,
                "decision": _decision(summary, d["analysis"]),
                "claim_scope": CLAIM,
                "source_integrity_verified": True,
                "optimizer_steps": 0,
                "games_replayed": 0,
                "simulations": 0,
                "checkpoint_promoted": False,
                "limitations": [
                    "Coverage is a pilot prerequisite, not evidence of gameplay improvement.",
                    "Reused train/development seeds include some previously seen by the parent.",
                    "Candidate comparisons share runs; independent coverage counts whole seeds.",
                    "Floor and regret are auxiliary; full-run terminal victory stays primary.",
                    "No card cost/damage or hidden future is inferred from an opaque identifier.",
                    "Public encoding does not certify all mechanics or cross-patch equivalence.",
                    "Residual training and fresh run confirmation need a separate experiment.",
                ],
            }
        ),
    )


@dataclass(frozen=True, slots=True)
class CombatFoundationInputs:
    audit: dict[str, Any]
    parent_checkpoint: dict[str, Any]
    parent_report: dict[str, Any]
    examples: tuple[_ProductionExample, ...]


def load_combat_foundation_inputs(
    *,
    config: CombatFoundationConfig,
    project_root: Path,
    upstream_root: Path,
    split_manifest: SplitManifest,
    ruleset: RulesetIdentity,
    objective: ObjectiveSpec,
) -> CombatFoundationInputs:
    config = CombatFoundationConfig.from_mapping(config.document)
    d = config.document
    if (
        objective.as_dict() != d["objective"]
        or split_manifest.objective_id != objective.objective_id
    ):
        raise ValueError("Combat audit objective differs from the frozen whole-run objective")
    layout = CombatLayout.from_mapping(d["layout"])
    if (
        ruleset.manifest_id != layout.ruleset_manifest_id
        or ruleset.patch_id != layout.patch_id
        or split_manifest.manifest_id != d["split_manifest_id"]
    ):
        raise ValueError("Combat audit ruleset/split binding differs")
    all_seeds = {s for seeds in d["complete_run_subfolds"].values() for s in seeds}
    if not all_seeds <= set(split_manifest.seeds(SplitName.TRAIN)):
        raise ValueError("Combat audit may only consume complete train runs")
    for source in d["layout_sources"]:
        if (
            hashlib.sha256(
                _safe_child(upstream_root.resolve(), source["path"]).read_bytes()
            ).hexdigest()
            != source["sha256"]
        ):
            raise ValueError("Pinned combat observation/action source hash differs")
    root = project_root.resolve()
    s = d["starting_study"]
    study = load_starting_repeatability_report(
        _safe_child(root, s["report_path"]),
        load_starting_repeatability_config(_safe_child(root, s["config_path"])),
    )
    if (
        study["report_id"] != s["report_id"]
        or study["decision"]["next_step"]
        != "stop_starting_choice_experiment_return_to_combat_run_level_foundation"
    ):
        raise ValueError("Combat follow-up requires the completed starting-study stop decision")
    checkpoint = load_production_model_checkpoint(_safe_child(root, d["parent_checkpoint"]))
    parent_report = load_production_training_report(
        _safe_child(root, d["parent_report"]), checkpoint=checkpoint
    )
    if (
        checkpoint["model_id"] != d["model_id"]
        or parent_report["report_id"] != d["training_report_id"]
    ):
        raise ValueError("Combat audit parent artifact identity differs")
    for field, expected in (
        ("ruleset_manifest_id", ruleset.manifest_id),
        ("split_manifest_id", split_manifest.manifest_id),
        ("objective_id", objective.objective_id),
    ):
        if checkpoint[field] != expected:
            raise ValueError("Combat parent provenance differs")
    if not parent_report["held_out_metrics"]["policy"]["auxiliary_policy_gate"]["passed"]:
        raise ValueError("Combat audit requires the accepted parent policy")
    training_config = ProductionTrainingConfig.from_mapping(checkpoint["training_config"])
    report, state_set, examples = _load_curriculum_examples(
        _safe_child(root, d["curriculum_path"]),
        split_manifest=split_manifest,
        config=training_config,
    )
    if (
        report["dataset_id"] != d["dataset_id"]
        or state_set.partition != "train"
        or state_set.ruleset_manifest_id != ruleset.manifest_id
        or state_set.objective_id != objective.objective_id
        or report["objective"] != objective.as_dict()
    ):
        raise ValueError("Combat audit curriculum ownership/identity/objective differs")
    model = production_model_from_checkpoint(checkpoint)
    body = analyze_combat_foundation(
        examples=examples, config=config, parent_weights=model.policy_weights
    )
    return CombatFoundationInputs(
        {**body, "report_id": manifest_identifier(body)}, checkpoint, parent_report, examples
    )


def run_combat_foundation_audit(
    *,
    config: CombatFoundationConfig,
    project_root: Path,
    upstream_root: Path,
    split_manifest: SplitManifest,
    ruleset: RulesetIdentity,
    objective: ObjectiveSpec,
) -> dict[str, Any]:
    return load_combat_foundation_inputs(
        config=config,
        project_root=project_root,
        upstream_root=upstream_root,
        split_manifest=split_manifest,
        ruleset=ruleset,
        objective=objective,
    ).audit


def load_combat_foundation_report(path: Path, config: CombatFoundationConfig) -> dict[str, Any]:
    doc = _mapping(json.loads(path.read_text()), "combat foundation report")
    _exact_keys(
        doc,
        {
            "schema_version",
            "report_id",
            "config_id",
            "objective",
            "sources",
            "complete_run_subfolds",
            "encoder_id",
            "summary",
            "rows",
            "decision",
            "claim_scope",
            "source_integrity_verified",
            "optimizer_steps",
            "games_replayed",
            "simulations",
            "checkpoint_promoted",
            "limitations",
        },
        "combat foundation report",
    )
    _identified(doc, "report_id")
    if (
        doc.get("schema_version") != REPORT_SCHEMA
        or doc.get("config_id") != config.document["config_id"]
        or doc.get("claim_scope") != CLAIM
        or doc.get("objective") != config.document["objective"]
        or doc.get("complete_run_subfolds") != config.document["complete_run_subfolds"]
    ):
        raise ValueError("Cached combat audit binding differs")
    d = config.document
    expected_sources = {
        "dataset_id": d["dataset_id"],
        "model_id": d["model_id"],
        "training_report_id": d["training_report_id"],
        "split_manifest_id": d["split_manifest_id"],
        "ruleset_manifest_id": d["layout"]["ruleset_manifest_id"],
        "starting_study_report_id": d["starting_study"]["report_id"],
    }
    if (
        doc.get("sources") != expected_sources
        or doc.get("encoder_id") != CombatLayout.from_mapping(d["layout"]).encoder_id
    ):
        raise ValueError("Cached combat audit source binding differs")
    for field in ("optimizer_steps", "games_replayed", "simulations"):
        if type(doc.get(field)) is not int or doc[field] != 0:
            raise ValueError("Combat audit may not perform training or simulation")
    if (
        doc.get("checkpoint_promoted") is not False
        or doc.get("source_integrity_verified") is not True
    ):
        raise ValueError("Cached combat audit scope differs")
    roles = {seed: role for role, seeds in d["complete_run_subfolds"].items() for seed in seeds}
    rows = doc["rows"]
    if not isinstance(rows, list) or len({row["state_id"] for row in rows}) != len(rows):
        raise ValueError("Cached combat audit repeats state coordinates")
    for row in rows:
        count = len(row["candidate_action_ids"])
        if (
            roles.get(row["run_seed"]) != row["subfold"]
            or not 0 <= row["parent_selected_candidate"] < count
            or count != len(set(row["candidate_action_ids"]))
            or row["binding_status"] not in {"completed", "failed"}
        ):
            raise ValueError("Cached combat audit candidate/complete-run alignment differs")
        if row["binding_status"] == "completed" and (
            len(row["bindings"]) != count
            or len(row["feature_digests"]) != count
            or len(row["pairs"]) != count * (count - 1) // 2
        ):
            raise ValueError("Cached combat audit paired denominator differs")
    if (
        _quantize_artifact(_summarize_rows(rows, roles, doc["summary"]["source_states"]))
        != doc["summary"]
    ):
        raise ValueError("Cached combat audit summary differs from its rows")
    if doc.get("decision") != _decision(doc["summary"], d["analysis"]):
        raise ValueError("Cached combat audit decision differs from frozen coverage checks")
    return doc


def summarize_combat_foundation(doc: dict[str, Any]) -> dict[str, Any]:
    summary = doc["summary"]
    return {
        "report_id": doc["report_id"],
        **{
            key: summary[key]
            for key in (
                "source_states",
                "source_runs",
                "combat_states",
                "bound_combat_states",
                "binding_failures",
                "terminal_victories_in_saved_combat_outcomes",
            )
        },
        "coverage": {
            role: {k: v for k, v in stats.items() if k != "by_run"}
            for role, stats in summary["by_subfold"].items()
        },
        "decision": doc["decision"],
        "optimizer_steps": 0,
        "games_replayed": 0,
        "checkpoint_promoted": False,
        "claim_scope": CLAIM,
    }
