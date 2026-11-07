from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from typing import Any

from spireshift.core.manifest import RulesetIdentity, manifest_identifier
from spireshift.models import _exact_keys, _integer, _list, _mapping, _weights_as_list
from spireshift.production_models import _ProductionExample
from spireshift.representations import CompositionalModelInput
from spireshift.starting_options import (
    StartingOptionConfig,
    StartingOptionHead,
    option_coverage,
    starting_option_ids,
)
from spireshift.trajectory_policy import (
    TrajectoryPolicyInputs,
    _id,
    _preference_representation,
)


@dataclass(slots=True)
class StartingOptionSpace:
    config: StartingOptionConfig
    head: StartingOptionHead
    offset: int
    parent_schema: str
    parent_type: str
    coverage: dict[str, Any]

    def checkpoint_binding(self, weights: dict[int, float]) -> dict[str, Any]:
        head = StartingOptionHead(
            self.head.dimension,
            self.head.known_option_ids,
            {
                index - self.offset: value
                for index, value in weights.items()
                if index >= self.offset
            },
        )
        return {
            "config": self.config.document,
            "parent_schema_version": self.parent_schema,
            "parent_model_type": self.parent_type,
            "head": head.as_dict(),
        }

    def report_binding(self, weights: dict[int, float]) -> dict[str, Any]:
        return {
            "config": self.config.document,
            "known_option_ids": list(self.head.known_option_ids),
            "residual_head_id": manifest_identifier(self.checkpoint_binding(weights)["head"]),
            "coverage": self.coverage,
            "parent_checkpoint_unchanged": True,
            "coverage_source": "verified_saved_public_inputs_no_engine",
        }


def prepare_starting_option_space(
    inputs: TrajectoryPolicyInputs, ruleset: RulesetIdentity, config: StartingOptionConfig
) -> tuple[TrajectoryPolicyInputs, StartingOptionSpace]:
    config = StartingOptionConfig.from_mapping(config.document)
    if inputs.parent_checkpoint["schema_version"] not in {
        "production-model-checkpoint-v1",
        "production-model-checkpoint-v2",
        "production-model-checkpoint-v3",
    }:
        raise ValueError("Starting option training requires an immutable original base parent")
    representations = tuple(
        _preference_representation(record, ruleset) for record in inputs.preference_records
    )
    fit_runs = set(inputs.runs["fit"])
    fit_rows = tuple(
        (item.run_seed, item.representation) for item in inputs.anchors if item.run_seed in fit_runs
    )
    fit_preference_rows = tuple(
        (item.run_seed, representation)
        for item, representation in zip(inputs.preferences, representations, strict=True)
        if item.weight > 0 and item.run_seed in fit_runs
    )
    known = tuple(
        sorted(
            {
                option
                for _, representation in fit_rows + fit_preference_rows
                for option in (starting_option_ids(representation) or ())
            }
        )
    )
    if not known or not any(starting_option_ids(r) for _, r in fit_preference_rows):
        raise ValueError("Starting option fitting data has no scoped preference evidence")
    head = StartingOptionHead(int(config.document["dimension"]), known)
    offset = inputs.training_config.vector_dimension + inputs.training_config.interaction_dimension

    def augment(
        features: tuple[dict[int, float], ...], representation: CompositionalModelInput
    ) -> tuple[dict[int, float], ...]:
        residual = head.features(representation)
        return tuple(
            {**old, **{offset + key: value for key, value in new.items()}}
            for old, new in zip(features, residual, strict=True)
        )

    def anchor(item: _ProductionExample) -> _ProductionExample:
        return replace(
            item, candidate_features=augment(item.candidate_features, item.representation)
        )

    preferences = []
    for item, record, representation in zip(
        inputs.preferences, inputs.preference_records, representations, strict=True
    ):
        features = augment(item.candidates, representation)
        ids = record["candidate_action_ids"]
        preferences.append(
            replace(
                item,
                candidates=features,
                preferred=features[ids.index(record["preferred_action_id"])],
                disfavored=features[ids.index(record["disfavored_action_id"])],
            )
        )
    selection_rows = tuple(
        (item.run_seed, item.representation)
        for item in inputs.anchors
        if item.run_seed not in fit_runs
    )
    selection_preferences = tuple(
        (item.run_seed, representation)
        for item, representation in zip(inputs.preferences, representations, strict=True)
        if item.weight > 0 and item.run_seed not in fit_runs
    )
    if not any(starting_option_ids(r) for _, r in selection_preferences):
        raise ValueError("Starting option selection data has no scoped preference evidence")
    groups = {
        "fit_anchors": fit_rows,
        "selection_anchors": selection_rows,
        "validation": tuple((item.run_seed, item.representation) for item in inputs.validation),
        "fit_preferences": fit_preference_rows,
        "selection_preferences": selection_preferences,
        "excluded_activity_preferences": tuple(
            (item.run_seed, representation)
            for item, representation in zip(inputs.preferences, representations, strict=True)
            if item.weight == 0
        ),
    }
    space = StartingOptionSpace(
        config,
        head,
        offset,
        inputs.parent_checkpoint["schema_version"],
        inputs.parent_checkpoint["model_type"],
        {key: option_coverage(rows, head) for key, rows in groups.items()},
    )
    return replace(
        inputs,
        anchors=tuple(anchor(item) for item in inputs.anchors),
        validation=tuple(anchor(item) for item in inputs.validation),
        preferences=tuple(preferences),
    ), space


def starting_option_parent(checkpoint: dict[str, Any]) -> dict[str, Any]:
    binding = _mapping(checkpoint.get("starting_option_residual"), "starting option binding")
    _exact_keys(
        binding,
        {"config", "parent_schema_version", "parent_model_type", "head"},
        "starting option binding",
    )
    config = StartingOptionConfig.from_mapping(binding["config"])
    if (checkpoint["schema_version"] == "production-model-checkpoint-v8") != (
        config.document["schema_version"] == "starting-option-policy-training-config-v2"
    ):
        raise ValueError("Starting option checkpoint version differs from its config")
    if config.recipe.document != checkpoint["trajectory_finetuning"]["recipe"]:
        raise ValueError("Starting option training recipe differs from the frozen binding")
    head = StartingOptionHead.from_mapping(binding["head"])
    if head.dimension != config.document["dimension"]:
        raise ValueError("Starting option residual dimension differs from its config")
    if binding["parent_schema_version"] not in {
        "production-model-checkpoint-v1",
        "production-model-checkpoint-v2",
        "production-model-checkpoint-v3",
    }:
        raise ValueError("Unsupported starting option parent schema")
    body = {
        key: copy.deepcopy(value)
        for key, value in checkpoint.items()
        if key not in {"model_id", "trajectory_finetuning", "starting_option_residual"}
    }
    body.update(
        schema_version=binding["parent_schema_version"], model_type=binding["parent_model_type"]
    )
    identifier = manifest_identifier(body)
    if identifier != config.recipe.document["inputs"]["parent_model_id"]:
        raise ValueError("Frozen starting option parent checkpoint changed")
    if checkpoint["trajectory_finetuning"]["selected_epoch"] == 0 and head.weights:
        raise ValueError("Unselected starting option residual must be zero initialized")
    return {**body, "model_id": identifier}


def starting_option_combined_weights(checkpoint: dict[str, Any]) -> list[dict[str, float | int]]:
    from spireshift.models import _weights_from_list
    from spireshift.production_models import ProductionTrainingConfig

    config = ProductionTrainingConfig.from_mapping(checkpoint["training_config"])
    offset = config.vector_dimension + config.interaction_dimension
    parent = _weights_from_list(
        checkpoint["heads"]["policy"]["weights"], offset, "parent policy weights"
    )
    head = StartingOptionHead.from_mapping(checkpoint["starting_option_residual"]["head"])
    return _weights_as_list(
        {**parent, **{offset + index: value for index, value in head.weights.items()}}
    )


def validate_starting_option_report(
    report: dict[str, Any], checkpoint: dict[str, Any] | None
) -> None:
    info = _mapping(report["starting_option_training"], "starting option training")
    _exact_keys(
        info,
        {
            "config",
            "known_option_ids",
            "residual_head_id",
            "coverage",
            "parent_checkpoint_unchanged",
            "coverage_source",
        },
        "starting option training",
    )
    config = StartingOptionConfig.from_mapping(info["config"])
    _id(info["residual_head_id"], "residual head ID")
    if config.recipe.document != report["trajectory_finetuning"]["recipe"]:
        raise ValueError("Starting option report recipe differs")
    if (
        info["parent_checkpoint_unchanged"] is not True
        or info["coverage_source"] != "verified_saved_public_inputs_no_engine"
    ):
        raise ValueError("Starting option report scope differs")
    known = info["known_option_ids"]
    # The head parser supplies the same strict vocabulary validation as checkpoint loading.
    StartingOptionHead.from_mapping(
        {
            "schema_version": "starting-option-policy-residual-v1",
            "encoder_id": config.document["encoder_id"],
            "dimension": config.document["dimension"],
            "known_option_ids": known,
            "weights": [],
        }
    )
    coverage = _mapping(info["coverage"], "starting option coverage")
    counts = {
        "fit_anchors": report["fit_anchor_records"],
        "selection_anchors": report["selection_anchor_records"],
        "validation": report["validation_records"],
        "fit_preferences": report["fit_preferences"],
        "selection_preferences": report["selection_preferences"],
        "excluded_activity_preferences": report["exclusions"].get(
            "distinct_public_states_on_floor", 0
        ),
    }
    _exact_keys(coverage, set(counts), "starting option coverage")
    for key, count in counts.items():
        row = _mapping(coverage[key], key)
        _exact_keys(
            row,
            {
                "records",
                "scoped_records",
                "scoped_complete_runs",
                "candidate_options",
                "unique_option_ids",
                "unknown_candidate_options",
                "unknown_option_ids",
            },
            key,
        )
        numbers = {
            label: _integer(row[label], label)
            for label in (
                "records",
                "scoped_records",
                "scoped_complete_runs",
                "candidate_options",
                "unknown_candidate_options",
            )
        }
        ids = [
            _integer(item, "option ID") for item in _list(row["unique_option_ids"], "option IDs")
        ]
        if ids != sorted(set(ids)) or any(item <= 0 for item in ids):
            raise ValueError("Starting option coverage IDs differ")
        if (
            numbers["records"] != count
            or min(numbers.values()) < 0
            or not numbers["scoped_complete_runs"] <= numbers["scoped_records"] <= count
            or numbers["unknown_candidate_options"] > numbers["candidate_options"]
            or numbers["candidate_options"] < 2 * numbers["scoped_records"]
            or len(ids) > numbers["candidate_options"]
            or row["unknown_option_ids"] != sorted(set(ids) - set(known))
            or numbers["unknown_candidate_options"] < len(row["unknown_option_ids"])
            or (not row["unknown_option_ids"] and numbers["unknown_candidate_options"] != 0)
        ):
            raise ValueError("Starting option coverage counts or unknown IDs differ")
    fitted_ids = sorted(
        set(coverage["fit_anchors"]["unique_option_ids"])
        | set(coverage["fit_preferences"]["unique_option_ids"])
    )
    if known != fitted_ids:
        raise ValueError("Starting option vocabulary must come only from fitting inputs")
    if checkpoint is not None:
        binding = checkpoint["starting_option_residual"]
        if (
            info["config"] != binding["config"]
            or known != binding["head"]["known_option_ids"]
            or info["residual_head_id"] != manifest_identifier(binding["head"])
        ):
            raise ValueError("Starting option report and residual differ")
