from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Self, cast

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.agents.learned import ProductionCheckpointPolicy, ProductionPolicyDecision
from spireshift.cli import main
from spireshift.core.manifest import manifest_identifier
from spireshift.core.objective import load_objective
from spireshift.core.types import DecisionType, LegalAction, Observation, Transition
from spireshift.models import _candidate_features, _weights_as_list
from spireshift.production_models import (
    ProductionTrainingConfig,
    _Outcome,
    _ProductionExample,
    load_production_model_checkpoint,
    load_production_training_report,
)
from spireshift.representations import build_model_input, vectorize_model_input
from spireshift.splits import SplitName, load_split_manifest
from spireshift.trajectory_diagnostic import (
    _anchor_conflicts,
    _choice_rows,
    _contrast_key,
    _summary,
    diagnose_trajectory_policy,
)
from spireshift.trajectory_policy import (
    FROZEN_HEADS,
    TrajectoryPolicyConfig,
    _features,
    _gradient,
    _Preference,
    load_trajectory_policy_inputs,
    train_trajectory_policy,
    validate_trajectory_report,
)
from spireshift.trajectory_preferences import (
    freeze_trajectory_mutation_preference_collection,
    load_trajectory_preference_collection,
)
from spireshift.trajectory_search import (
    PUBLIC_FRONTIER_STRATEGY,
    Act1Milestones,
    PublicFrontierRanking,
    TrajectorySearchConfig,
    run_trajectory_search,
)


class _Environment:
    patch_id = MockSpireEnvironment.patch_id
    ruleset = MockSpireEnvironment.ruleset

    def __init__(self) -> None:
        self.seed = 0
        self.stage = 0
        self.terminal = False

    def reset(self, seed: int) -> Observation:
        self.seed, self.stage, self.terminal = seed, 0, False
        return self.observe()

    def observe(self) -> Observation:
        public = {
            "floor": 0 if self.stage == 0 else 17,
            "act": "hive" if self.stage == 2 else "overgrowth",
            "gold": self.seed,
            "terminal": self.terminal,
            "victory": False,
        }
        return Observation(
            "observation-v1",
            self.patch_id,
            DecisionType.TERMINAL if self.terminal else DecisionType.PATH,
            public,
            hashlib.sha256(
                json.dumps(public, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        )

    def legal_actions(self) -> tuple[LegalAction, ...]:
        if self.terminal:
            return ()
        return tuple(
            LegalAction(
                f"evangambit:path:{i}", "evangambit_path", {"action_index": i, "phase": "path"}
            )
            for i in range(2 if self.stage == 0 else 1)
        )

    def step(self, action: LegalAction) -> Transition:
        source = self.observe()
        if self.stage == 0 and action.action_id.endswith(":0"):
            self.terminal = True
        else:
            self.stage += 1
            self.terminal = self.stage == 2
        return Transition(source, action, self.observe(), 0.0, self.terminal, False)

    def clone(self, *, resample_hidden: bool, seed: int | None = None) -> Self:
        del resample_hidden, seed
        return copy.deepcopy(self)

    def close(self) -> None:
        pass


class _Policy:
    ruleset = _Environment.ruleset

    def __init__(self, model_id: str, split_id: str) -> None:
        self.model_id, self.split_manifest_id = model_id, split_id
        self.policy_id = f"production-checkpoint-policy-v1:{model_id}"

    def predict(
        self, observation: Observation, legal_actions: tuple[LegalAction, ...]
    ) -> ProductionPolicyDecision:
        return ProductionPolicyDecision(
            manifest_identifier(observation.as_dict()),
            tuple(a.action_id for a in legal_actions),
            0,
            legal_actions[0],
            (0.9, 0.1) if len(legal_actions) == 2 else (1.0,),
            None,
            tuple(0.0 for _ in legal_actions),
            {},
            0.0,
        )


def _write(path: Path, value: dict[str, Any], id_field: str | None = None) -> None:
    if id_field:
        value[id_field] = manifest_identifier({k: v for k, v in value.items() if k != id_field})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def _build_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    split = load_split_manifest(Path("manifests/splits/mock-v1-seeds-000000-000999-v1.json"))
    config = ProductionTrainingConfig(epochs=2, vector_dimension=128, interaction_dimension=256)
    environment = _Environment()
    observation = environment.reset(0)
    # A separate public combat context supplies the old policy's anchor examples.
    public = {**observation.public_state, "floor": 4, "hp": 70}
    observation = Observation(
        "observation-v1",
        environment.patch_id,
        DecisionType.COMBAT,
        public,
        hashlib.sha256(
            json.dumps(public, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    )
    actions = tuple(
        LegalAction(
            f"evangambit:combat:{i}", "evangambit_combat", {"action_index": i, "phase": "combat"}
        )
        for i in range(2)
    )
    representation = build_model_input(environment.ruleset, observation, actions)
    vector = vectorize_model_input(representation, dimension=config.vector_dimension)
    features = tuple(
        _candidate_features(
            vector.state, candidate, config.vector_dimension, config.interaction_dimension
        )
        for candidate in vector.candidates
    )
    weights = {
        index: 0.1 * (features[1].get(index, 0) - features[0].get(index, 0))
        for index in set(features[0]) | set(features[1])
    }
    dataset = manifest_identifier({"dataset": "anchor"})
    validation_dataset = manifest_identifier({"dataset": "validation"})
    parent: dict[str, Any] = {
        "schema_version": "production-model-checkpoint-v3",
        "model_type": "sparse-pairwise-curriculum-multihead-v3",
        "representation_encoder_id": "mechanics-compositional-v1",
        "vectorizer_id": "signed-sha256-feature-hash-v1",
        "ruleset_manifest_id": environment.ruleset.manifest_id,
        "objective_id": "terminal-victory-v1",
        "split_manifest_id": split.manifest_id,
        "train_dataset_id": dataset,
        "training_config": config.as_dict(),
        "heads": {
            "policy": {
                "target": "paired-preference-confidence-v1",
                "weights": _weights_as_list(weights),
            },
            "terminal_value": {
                "status": "blocked",
                "reason": "all_zero_terminal_victory_evidence",
                "weights": [],
            },
            "tactical_death_risk": {
                "target": "terminal_defeat_within_32_decisions",
                "bias": 0.125,
                "weights": [{"index": 1, "value": 0.3}],
            },
            "maximum_floor_distribution": {
                "target": "candidate-maximum-floor-survival-v1",
                "thresholds": [{"floor": 3, "bias": 0.5, "weights": [{"index": 2, "value": 0.2}]}],
            },
        },
    }
    parent_path = tmp_path / "parent.json"
    _write(parent_path, parent, "model_id")
    parent_report: dict[str, Any] = {
        "report_id": manifest_identifier({"report": "parent"}),
        "model_id": parent["model_id"],
        "validation_dataset_id": validation_dataset,
        "held_out_metrics": {
            "policy": {"soft_target_baseline": {"weighted_pairwise_cross_entropy": 10.0}},
            "terminal_value": {"status": "blocked"},
            "tactical_death_risk": {},
            "maximum_floor_distribution": {},
        },
        "terminal_value_status": {
            "promoted": False,
            "reason": "all_zero_terminal_victory_evidence",
        },
    }
    parent_report_path = tmp_path / "parent-report.json"
    _write(parent_report_path, parent_report)
    monkeypatch.setattr(
        "spireshift.trajectory_policy.load_production_training_report",
        lambda *a, **kw: copy.deepcopy(parent_report),
    )
    train_seeds = split.seeds(SplitName.TRAIN)[:8]
    validation_seeds = split.seeds(SplitName.VALIDATION)[:4]

    def example(seed: int) -> _ProductionExample:
        return _ProductionExample(
            str(seed),
            seed,
            "combat",
            representation,
            features,
            ((0.5, 0.0), (1.0, 0.5)),
            (0.1, 0.9),
            1.0,
            1.0,
            1,
            (0.0, 1.0),
            ((_Outcome(1, True, False, True, 2),), (_Outcome(4, True, False, True, 3),)),
        )

    train_path = tmp_path / "train.json"
    validation_path = tmp_path / "validation.json"

    def curriculum(path: Path, **kwargs: Any) -> tuple[Any, Any, Any]:
        partition = "train" if path == train_path else "validation"
        return (
            {
                "dataset_id": dataset if partition == "train" else validation_dataset,
                "signal_assessment": {"auxiliary_policy_signal_pass": True},
            },
            SimpleNamespace(partition=partition),
            tuple(
                example(seed)
                for seed in (train_seeds if partition == "train" else validation_seeds)
            ),
        )

    monkeypatch.setattr("spireshift.trajectory_policy._load_curriculum_examples", curriculum)
    policy = _Policy(parent["model_id"], split.manifest_id)
    search_config = TrajectorySearchConfig(
        split_manifest_id=split.manifest_id,
        ruleset_manifest_id=environment.ruleset.manifest_id,
        model_id=parent["model_id"],
        training_report_id=parent_report["report_id"],
        run_offset=0,
        run_count=8,
        generations=2,
        beam_width=2,
        mutations_per_parent=2,
        workers=1,
        maximum_decisions_per_run=8,
        cycle_repetition_threshold=3,
        liveness_tail_length=4,
        no_op_fallback_threshold=2,
        mutation_salt="trajectory-test",
        milestones=Act1Milestones(
            first_act_ids=("overgrowth", "underdocks"), next_act_id="hive", boss_floor=17
        ),
        frontier_ranking=PublicFrontierRanking(
            strategy=PUBLIC_FRONTIER_STRATEGY,
            enemy_hp_offset=80,
            enemy_slot_size=15,
            maximum_enemy_slots=6,
        ),
    )
    search = run_trajectory_search(
        environment_factory=_Environment,
        ruleset=environment.ruleset,
        policy=cast(ProductionCheckpointPolicy, policy),
        split_manifest=split,
        training_report_id=parent_report["report_id"],
        config=search_config,
        output_directory=tmp_path / "search",
    )
    collection = freeze_trajectory_mutation_preference_collection(
        search_report_path=search.report_path,
        search_config=search_config,
        output_directory=tmp_path / "collection",
        split_manifest=split,
        environment_factory=_Environment,
        ruleset=environment.ruleset,
        policy=cast(ProductionCheckpointPolicy, policy),
    )
    collection_path = tmp_path / "collection/trajectory-mutation-preference-collection.json"
    base_recipe = json.loads(
        Path(
            "configs/trajectory-policy/sts2-v0.107.1-base-v2-frontier-preferences-v1.json"
        ).read_text()
    )
    base_recipe["inputs"] = {
        "parent_model_id": parent["model_id"],
        "parent_training_report_id": parent_report["report_id"],
        "collection_id": collection["collection_id"],
        "search_report_id": collection["search_report_id"],
        "search_config_id": search_config.config_id,
        "train_dataset_id": dataset,
        "validation_dataset_id": validation_dataset,
        "split_manifest_id": split.manifest_id,
        "ruleset_manifest_id": environment.ruleset.manifest_id,
    }
    base_recipe.update(epochs=3, learning_rate=0.0001, selection_fraction=0.5)
    base_recipe["limits"]["minimum_preference_loss_improvement"] = 1e-7
    base_recipe["config_id"] = manifest_identifier(
        {k: v for k, v in base_recipe.items() if k != "config_id"}
    )
    kwargs = {
        "parent_checkpoint_path": parent_path,
        "parent_report_path": parent_report_path,
        "collection_path": collection_path,
        "search_report_path": search.report_path,
        "search_config": search_config,
        "train_report_path": train_path,
        "validation_report_path": validation_path,
        "split_manifest": split,
        "ruleset": environment.ruleset,
        "config": TrajectoryPolicyConfig.from_mapping(base_recipe),
        "objective": load_objective(Path("configs/default.toml")),
    }
    return {
        "kwargs": kwargs,
        "parent": parent,
        "parent_report": parent_report,
        "curriculum_loader": curriculum,
        "collection": collection,
        "root": tmp_path,
        "recipe": base_recipe,
    }


@pytest.fixture
def package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    return _build_package(tmp_path, monkeypatch)


@pytest.fixture
def starting_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    from spireshift.starting_options import StartingOptionConfig

    original_observe = _Environment.observe

    def observe(environment: _Environment) -> Observation:
        result = original_observe(environment)
        if environment.stage:
            return result
        public = {
            **result.public_state,
            "floor": 1,
            "player_hp": 64,
            "player_max_hp": 80,
            "neow_options": [5, 9, 12],
            "deck": [],
            "relic_slots": [],
        }
        return Observation(
            result.schema_version,
            result.patch_id,
            DecisionType.TERMINAL if environment.terminal else DecisionType.EVENT,
            public,
            hashlib.sha256(
                json.dumps(public, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        )

    original_actions = _Environment.legal_actions

    def actions(environment: _Environment) -> tuple[LegalAction, ...]:
        if environment.stage or environment.terminal:
            return original_actions(environment)
        return tuple(
            LegalAction(
                f"evangambit:ancient:{i}",
                "evangambit_ancient",
                {"phase": "ancient", "action_index": i},
            )
            for i in range(2)
        )

    monkeypatch.setattr(_Environment, "observe", observe)
    monkeypatch.setattr(_Environment, "legal_actions", actions)
    result = _build_package(tmp_path, monkeypatch)
    doc = {
        "schema_version": "starting-option-policy-training-config-v1",
        "encoder_id": "starting-ancient-public-option-v1",
        "dimension": 4096,
        "trajectory_recipe": result["recipe"],
    }
    doc["config_id"] = manifest_identifier(doc)
    result["kwargs"]["residual_config"] = StartingOptionConfig.from_mapping(doc)
    return result


def test_saved_collection_loads_without_engine_and_rejects_corruption(
    package: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    kwargs = package["kwargs"]

    def no_replay(**kwargs: Any) -> Any:
        raise AssertionError("Artifact loading must never replay a game")

    monkeypatch.setattr("spireshift.trajectory_preferences._run_trajectory", no_replay)
    evidence = load_trajectory_preference_collection(
        kwargs["collection_path"],
        search_report_path=kwargs["search_report_path"],
        search_config=kwargs["search_config"],
        split_manifest=kwargs["split_manifest"],
    )
    assert evidence.document["summary"]["unique_runs"] == 8
    component_path = kwargs["collection_path"].parent / package["collection"]["cases"][0]["path"]
    component = json.loads(component_path.read_text())
    component["preferences"][0]["candidate_action_ids"].reverse()
    _write(component_path, component, "preference_set_id")
    with pytest.raises(ValueError, match="differs"):
        load_trajectory_preference_collection(
            kwargs["collection_path"],
            search_report_path=kwargs["search_report_path"],
            search_config=kwargs["search_config"],
            split_manifest=kwargs["split_manifest"],
        )


def test_policy_only_update_preserves_heads_and_selects_by_complete_run(
    package: dict[str, Any],
) -> None:
    result = train_trajectory_policy(**package["kwargs"])
    for head in FROZEN_HEADS:
        assert result.checkpoint["heads"][head] == package["parent"]["heads"][head]
    assert (
        result.checkpoint["heads"]["policy"]["weights"]
        != package["parent"]["heads"]["policy"]["weights"]
    )
    assert result.report["candidate_eligible"] is True
    binding = result.checkpoint["trajectory_finetuning"]
    runs = binding["complete_run_subfolds"]
    assert not set(runs["fit"]) & set(runs["selection"])
    assert result.report["fit_preferences"] == 4 and result.report["selection_preferences"] == 4
    assert result.report["checkpoint_promoted"] is False
    assert result.report["terminal_victory_positive_labels"] == 0
    assert result.report["inference_diagnostics"]["candidate_alignment_pass"] is True
    checkpoint_path = package["root"] / "result.json"
    report_path = package["root"] / "report.json"
    _write(checkpoint_path, result.checkpoint)
    _write(report_path, result.report)
    assert load_production_model_checkpoint(checkpoint_path) == result.checkpoint
    assert (
        load_production_training_report(report_path, checkpoint=result.checkpoint) == result.report
    )
    registry = Registry().with_resources(
        [
            (schema["$id"], Resource.from_contents(schema))
            for path in Path("schemas").glob("*.json")
            for schema in [json.loads(path.read_text())]
        ]
    )
    for schema_name, document in [
        ("production-model-checkpoint-v6", result.checkpoint),
        ("production-model-training-report-v6", result.report),
    ]:
        Draft202012Validator(
            json.loads(Path("schemas", schema_name + ".json").read_text()), registry=registry
        ).validate(document)
    ProductionCheckpointPolicy(
        checkpoint=result.checkpoint,
        training_report=result.report,
        ruleset=package["kwargs"]["ruleset"],
    )
    tampered = copy.deepcopy(result.checkpoint)
    tampered["heads"]["tactical_death_risk"]["bias"] += 0.1
    _write(checkpoint_path, tampered, "model_id")
    with pytest.raises(ValueError, match="Frozen tactical"):
        load_production_model_checkpoint(checkpoint_path)
    bad_report = copy.deepcopy(result.report)
    bad_report["trajectory_finetuning"]["complete_run_subfolds"]["selection"].append(runs["fit"][0])
    bad_report["report_id"] = manifest_identifier(
        {k: v for k, v in bad_report.items() if k != "report_id"}
    )
    with pytest.raises(ValueError, match="overlap|sorted"):
        validate_trajectory_report(bad_report)


def test_nonadvancing_candidate_returns_parent_policy_and_is_not_deployable(
    package: dict[str, Any],
) -> None:
    recipe = copy.deepcopy(package["recipe"])
    recipe["limits"]["minimum_preference_loss_improvement"] = 10.0
    recipe["config_id"] = manifest_identifier({k: v for k, v in recipe.items() if k != "config_id"})
    kwargs = {**package["kwargs"], "config": TrajectoryPolicyConfig.from_mapping(recipe)}
    result = train_trajectory_policy(**kwargs)
    assert result.report["candidate_eligible"] is False
    assert result.checkpoint["heads"] == package["parent"]["heads"]
    assert result.checkpoint["trajectory_finetuning"]["selected_epoch"] == 0
    with pytest.raises(ValueError, match="advancement"):
        ProductionCheckpointPolicy(
            checkpoint=result.checkpoint, training_report=result.report, ruleset=kwargs["ruleset"]
        )


def test_recipe_and_public_state_fail_closed(package: dict[str, Any]) -> None:
    recipe = copy.deepcopy(package["recipe"])
    recipe["inputs"]["collection_id"] = manifest_identifier({"wrong": "collection"})
    recipe["config_id"] = manifest_identifier({k: v for k, v in recipe.items() if k != "config_id"})
    with pytest.raises(ValueError, match="identities"):
        train_trajectory_policy(
            **{**package["kwargs"], "config": TrajectoryPolicyConfig.from_mapping(recipe)}
        )
    recipe = copy.deepcopy(package["recipe"])
    recipe["rank_weights"]["distinct_public_states_on_floor"] = 1.0
    recipe["config_id"] = manifest_identifier({k: v for k, v in recipe.items() if k != "config_id"})
    with pytest.raises(ValueError, match="tie-breakers"):
        TrajectoryPolicyConfig.from_mapping(recipe)
    component_path = (
        package["kwargs"]["collection_path"].parent / package["collection"]["cases"][0]["path"]
    )
    record = json.loads(component_path.read_text())["preferences"][0]
    raw = record["source_observation"]
    raw["public_state"]["hidden_rng"] = 123
    raw["state_hash"] = hashlib.sha256(
        json.dumps(raw["public_state"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    with pytest.raises(ValueError, match="Privileged"):
        _features(
            record,
            package["kwargs"]["ruleset"],
            ProductionTrainingConfig.from_mapping(package["parent"]["training_config"]),
        )


@pytest.mark.parametrize("corruption", ["missing_case", "file_hash", "non_train_seed"])
def test_collection_rejects_incomplete_hash_or_owner_drift(
    package: dict[str, Any], corruption: str
) -> None:
    collection = copy.deepcopy(package["collection"])
    if corruption == "missing_case":
        collection["cases"].pop()
    elif corruption == "file_hash":
        collection["cases"][0]["sha256"] = "0" * 64
    else:
        collection["cases"][0]["run_seed"] = package["kwargs"]["split_manifest"].seeds(
            "validation"
        )[0]
    _write(package["kwargs"]["collection_path"], collection, "collection_id")
    kwargs = package["kwargs"]
    with pytest.raises(ValueError, match="missing|hash|ownership"):
        load_trajectory_preference_collection(
            kwargs["collection_path"],
            search_report_path=kwargs["search_report_path"],
            search_config=kwargs["search_config"],
            split_manifest=kwargs["split_manifest"],
        )


def test_longer_lineage_does_not_increase_total_gradient() -> None:
    recipe = {"anchor_strength": 2.0, "preference_strength": 1.0, "proximal_strength": 0.1}
    first = _Preference(1, "maximum_floor", "combat", 1.0, {1: 1.0}, {2: 1.0}, ({1: 1.0}, {2: 1.0}))
    second = replace(first, run_seed=2)
    assert _gradient({}, {}, (first, second), (), recipe) == _gradient(
        {}, {}, (first, first, first, second), (), recipe
    )


@pytest.mark.parametrize(
    "command", ["finetune-trajectory-policy", "finetune-starting-option-policy"]
)
def test_cli_rejects_existing_output_before_starting_training(
    package: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    def forbidden(**kwargs: Any) -> Any:
        raise AssertionError("Training must not start")

    monkeypatch.setattr("spireshift.cli.train_trajectory_policy", forbidden)
    path = package["kwargs"]["parent_checkpoint_path"]
    rc = main(
        [
            "model",
            command,
            str(path),
            str(path),
            str(path),
            "--parent-report",
            str(path),
            "--report",
            str(path),
            "--collection",
            str(path),
            "--search-report",
            str(path),
            "--search-config",
            str(path),
            "--train-report",
            str(path),
            "--validation-report",
            str(path),
            "--split-manifest",
            str(path),
            "--ruleset-manifest",
            str(path),
        ]
    )
    assert rc == 1 and "must not already exist" in capsys.readouterr().out


def _diagnostic_kwargs(package: dict[str, Any]) -> dict[str, Any]:
    result = train_trajectory_policy(**package["kwargs"])
    candidate_path = package["root"] / "candidate.json"
    report_path = package["root"] / "candidate-report.json"
    _write(candidate_path, result.checkpoint)
    _write(report_path, result.report)
    return {
        **package["kwargs"],
        "candidate_checkpoint_path": candidate_path,
        "candidate_report_path": report_path,
    }


def test_starting_option_update_freezes_the_entire_parent_and_round_trips(
    starting_package: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_replay(**kwargs: Any) -> Any:
        raise AssertionError("Owner training reads saved inputs; it cannot replay a game")

    monkeypatch.setattr("spireshift.trajectory_preferences._run_trajectory", no_replay)
    result = train_trajectory_policy(**starting_package["kwargs"])
    parent = starting_package["parent"]
    assert result.checkpoint["heads"] == parent["heads"]
    assert result.checkpoint["training_config"] == parent["training_config"]
    assert result.report["candidate_eligible"] is True
    head = result.checkpoint["starting_option_residual"]["head"]
    assert head["weights"] and head["known_option_ids"] == [5, 9]
    coverage = result.report["starting_option_training"]["coverage"]
    assert coverage["fit_preferences"]["records"] == 4
    assert coverage["selection_preferences"]["scoped_complete_runs"] == 4
    assert coverage["validation"]["records"] == result.report["validation_records"]
    assert coverage["validation"]["scoped_records"] == 0
    assert result.report["validation_drift"]["changed_actions"] == 0
    assert result.report["checkpoint_promoted"] is False
    checkpoint_path = starting_package["root"] / "starting-result.json"
    report_path = starting_package["root"] / "starting-report.json"
    _write(checkpoint_path, result.checkpoint)
    _write(report_path, result.report)
    assert load_production_model_checkpoint(checkpoint_path) == result.checkpoint
    assert (
        load_production_training_report(report_path, checkpoint=result.checkpoint) == result.report
    )
    ProductionCheckpointPolicy(
        checkpoint=result.checkpoint,
        training_report=result.report,
        ruleset=starting_package["kwargs"]["ruleset"],
    )
    registry = Registry().with_resources(
        [
            (schema["$id"], Resource.from_contents(schema))
            for p in Path("schemas").glob("*.json")
            for schema in [json.loads(p.read_text())]
        ]
    )
    for name, document in (
        ("production-model-checkpoint-v7", result.checkpoint),
        ("production-model-training-report-v7", result.report),
    ):
        Draft202012Validator(
            json.loads(Path("schemas", name + ".json").read_text()), registry=registry
        ).validate(document)
    tampered = copy.deepcopy(result.checkpoint)
    tampered["heads"]["policy"]["weights"][0]["value"] += 0.1
    _write(checkpoint_path, tampered, "model_id")
    with pytest.raises(ValueError, match="parent checkpoint changed"):
        load_production_model_checkpoint(checkpoint_path)
    bad_report = copy.deepcopy(result.report)
    bad_report["starting_option_training"]["coverage"]["validation"]["records"] += 1
    _write(report_path, bad_report, "report_id")
    with pytest.raises(ValueError, match="coverage counts"):
        load_production_training_report(report_path, checkpoint=result.checkpoint)


def test_nonadvancing_starting_option_update_keeps_a_zero_residual_and_is_rejected(
    starting_package: dict[str, Any],
) -> None:
    from spireshift.starting_options import StartingOptionConfig

    kwargs = dict(starting_package["kwargs"])
    recipe = copy.deepcopy(starting_package["recipe"])
    recipe["limits"]["minimum_preference_loss_improvement"] = 10.0
    recipe["config_id"] = manifest_identifier(
        {key: value for key, value in recipe.items() if key != "config_id"}
    )
    residual_doc = copy.deepcopy(kwargs["residual_config"].document)
    residual_doc["trajectory_recipe"] = recipe
    residual_doc["config_id"] = manifest_identifier(
        {key: value for key, value in residual_doc.items() if key != "config_id"}
    )
    kwargs.update(
        config=TrajectoryPolicyConfig.from_mapping(recipe),
        residual_config=StartingOptionConfig.from_mapping(residual_doc),
    )
    result = train_trajectory_policy(**kwargs)
    assert result.report["candidate_eligible"] is False
    assert result.report["trajectory_finetuning"]["selected_epoch"] == 0
    assert result.checkpoint["starting_option_residual"]["head"]["weights"] == []
    assert result.checkpoint["heads"] == starting_package["parent"]["heads"]
    with pytest.raises(ValueError, match="advancement"):
        ProductionCheckpointPolicy(
            checkpoint=result.checkpoint, training_report=result.report, ruleset=kwargs["ruleset"]
        )
    forged = copy.deepcopy(result.report)
    forged["candidate_eligible"] = True
    forged["report_id"] = manifest_identifier({k: v for k, v in forged.items() if k != "report_id"})
    with pytest.raises(ValueError, match="validation checks"):
        ProductionCheckpointPolicy(
            checkpoint=result.checkpoint, training_report=forged, ruleset=kwargs["ruleset"]
        )


def test_starting_option_wrapper_and_residual_cannot_change_the_frozen_recipe(
    starting_package: dict[str, Any],
) -> None:
    from spireshift.starting_options import StartingOptionConfig

    kwargs = dict(starting_package["kwargs"])
    doc = copy.deepcopy(kwargs["residual_config"].document)
    doc["trajectory_recipe"]["limits"]["maximum_regret_increase"] += 1.0
    recipe = doc["trajectory_recipe"]
    recipe["config_id"] = manifest_identifier({k: v for k, v in recipe.items() if k != "config_id"})
    doc["config_id"] = manifest_identifier({k: v for k, v in doc.items() if k != "config_id"})
    kwargs["residual_config"] = StartingOptionConfig.from_mapping(doc)
    with pytest.raises(ValueError, match="wrapper differs"):
        train_trajectory_policy(**kwargs)


def test_option_vocabulary_excludes_selection_and_validation_only_ids(
    starting_package: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from spireshift.starting_option_training import prepare_starting_option_space
    from spireshift.trajectory_policy import _preference_representation

    kwargs = starting_package["kwargs"]
    inputs = load_trajectory_policy_inputs(
        **{key: value for key, value in kwargs.items() if key != "residual_config"}
    )
    records = copy.deepcopy(inputs.preference_records)
    for record in records:
        if record["run_seed"] in inputs.runs["selection"]:
            public = record["source_observation"]["public_state"]
            public["neow_options"][1] = 999
            record["source_observation"]["state_hash"] = hashlib.sha256(
                json.dumps(public, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
    validation_record = copy.deepcopy(records[0])
    public = validation_record["source_observation"]["public_state"]
    public["neow_options"][1] = 1000
    validation_record["source_observation"]["state_hash"] = hashlib.sha256(
        json.dumps(public, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    validation_representation = _preference_representation(validation_record, kwargs["ruleset"])
    validation = tuple(
        replace(item, representation=validation_representation) for item in inputs.validation
    )
    injected = replace(inputs, preference_records=tuple(records), validation=validation)
    _, space = prepare_starting_option_space(injected, kwargs["ruleset"], kwargs["residual_config"])
    assert space.head.known_option_ids == (5, 9)
    assert space.coverage["selection_preferences"]["unknown_option_ids"] == [999]
    assert space.coverage["selection_preferences"]["unknown_candidate_options"] == 4
    assert space.coverage["validation"]["unknown_option_ids"] == [1000]


def test_diagnosis_reconciles_saved_choices_without_training_or_replay(
    package: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    kwargs = _diagnostic_kwargs(package)
    saved = json.loads(kwargs["candidate_report_path"].read_text())
    source_bytes = kwargs["candidate_checkpoint_path"].read_bytes()

    def forbidden(**kwargs: Any) -> Any:
        raise AssertionError("Diagnosis must not train or replay")

    monkeypatch.setattr("spireshift.trajectory_policy.train_trajectory_policy", forbidden)
    monkeypatch.setattr("spireshift.trajectory_preferences._run_trajectory", forbidden)
    report = diagnose_trajectory_policy(**kwargs)
    assert report == diagnose_trajectory_policy(**kwargs)
    assert kwargs["candidate_checkpoint_path"].read_bytes() == source_bytes
    assert report["report_id"] == manifest_identifier(
        {key: value for key, value in report.items() if key != "report_id"}
    )
    assert report["reconciliation_pass"] is True
    assert report["checkpoint_promoted"] is False
    assert report["terminal_victory_positive_labels"] == 0
    assert report["validation_summary"]["decisions"] == saved["validation_records"]
    assert (
        report["validation_summary"]["changed_actions"]
        == saved["validation_drift"]["changed_actions"]
    )
    assert (
        report["validation_summary"]["candidate_mean_regret"]
        == saved["held_out_metrics"]["policy"]["mean_progress_utility_regret"]
    )
    assert (
        len(report["preference_choices"]) == package["collection"]["summary"]["strict_improvements"]
    )
    assert (
        sum(values["decisions"] for values in report["validation_by_run"].values())
        == saved["validation_records"]
    )
    registry: Registry[Any] = Registry().with_resources(
        [
            (schema["$id"], Resource.from_contents(schema))
            for path in Path("schemas").glob("*.json")
            for schema in [json.loads(path.read_text())]
        ]
    )
    schema = json.loads(Path("schemas/trajectory-policy-diagnostic-v1.json").read_text())
    Draft202012Validator(schema, registry=registry).validate(report)


def test_choice_attribution_accounts_for_harm_benefit_and_utility_ties(
    package: dict[str, Any],
) -> None:
    source = load_trajectory_policy_inputs(**package["kwargs"]).validation[0]
    features = ({0: 1.0}, {1: 1.0})
    examples = tuple(
        replace(
            source,
            state_id=str(index),
            candidate_features=features,
            mean_progress_utilities=utilities,
        )
        for index, utilities in enumerate(((1.0, 0.0), (0.0, 0.5), (0.25, 0.25)))
    )
    parent, candidate = {0: 1.0}, {1: 1.0}
    rows = _choice_rows(examples, parent, candidate, 128, (), {})
    summary = _summary(rows)
    assert summary["changed_actions"] == 3
    assert summary["harmful_changes"] == 1
    assert summary["beneficial_changes"] == 1
    assert summary["tied_changes"] == 1
    assert summary["total_regret_change"] == 0.5
    assert summary["gross_harm"] == 1.0 and summary["gross_benefit"] == 0.5
    assert summary["mean_regret_change"] == pytest.approx(1 / 6)
    attribution = rows[0]["weight_attribution"]
    assert attribution["parent_new_over_old_margin"] == -1
    assert attribution["candidate_new_over_old_margin"] == 1
    assert attribution["weight_update_margin"] == 2
    assert attribution["action_coordinate_margin"] == 2
    assert attribution["state_action_coordinate_margin"] == 0


def test_exact_contrast_alias_preserves_direction_and_exposes_opposing_targets(
    package: dict[str, Any],
) -> None:
    inputs = load_trajectory_policy_inputs(**package["kwargs"])
    source = inputs.validation[0]
    features = ({0: 1.0}, {1: 1.0})
    anchor = replace(source, candidate_features=features, mean_progress_utilities=(1.0, 0.0))
    preference = _Preference(1, "maximum_floor", "combat", 1.0, features[1], features[0], features)
    record = {
        "preference_id": manifest_identifier({"preference": "opposing"}),
        "source_state_hash": "different-public-state",
    }
    diagnosis = _anchor_conflicts(
        replace(inputs, anchors=(anchor,)), ((preference, record),), {}, {}
    )
    assert diagnosis["exact_state_action_overlap"] == []
    assert diagnosis["opposing_aliases"] == 1
    assert diagnosis["exact_hashed_contrast_aliases"][0]["teacher_utility_gap"] == -1
    forward, sign = _contrast_key({0: 1.0, 1: -1.0})
    reverse, reversed_sign = _contrast_key({0: -1.0, 1: 1.0})
    assert forward == reverse and sign == -reversed_sign


def test_diagnosis_rejects_saved_report_counts_that_do_not_match_sources(
    package: dict[str, Any],
) -> None:
    kwargs = _diagnostic_kwargs(package)
    report = json.loads(kwargs["candidate_report_path"].read_text())
    report["validation_runs"] += 1
    _write(kwargs["candidate_report_path"], report, "report_id")
    with pytest.raises(ValueError, match="reconcile"):
        diagnose_trajectory_policy(**kwargs)


def test_diagnosis_rejects_candidate_parameter_tampering(package: dict[str, Any]) -> None:
    kwargs = _diagnostic_kwargs(package)
    checkpoint = json.loads(kwargs["candidate_checkpoint_path"].read_text())
    checkpoint["heads"]["policy"]["weights"][0]["value"] += 1
    _write(kwargs["candidate_checkpoint_path"], checkpoint, "model_id")
    with pytest.raises(ValueError):
        diagnose_trajectory_policy(**kwargs)


@pytest.mark.parametrize("corruption", ["action_order", "hidden_field"])
def test_diagnosis_rejects_changed_public_comparison_evidence(
    package: dict[str, Any], corruption: str
) -> None:
    kwargs = _diagnostic_kwargs(package)
    path = kwargs["collection_path"].parent / package["collection"]["cases"][0]["path"]
    component = json.loads(path.read_text())
    record = component["preferences"][0]
    if corruption == "action_order":
        record["candidate_action_ids"].reverse()
    else:
        record["source_observation"]["public_state"]["hidden_rng"] = 123
    _write(path, component, "preference_set_id")
    with pytest.raises(ValueError):
        diagnose_trajectory_policy(**kwargs)


def test_diagnostic_cli_preserves_source_files(
    package: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def forbidden(**kwargs: Any) -> Any:
        raise AssertionError("Diagnosis must not begin if its output would replace an input")

    monkeypatch.setattr("spireshift.cli.diagnose_trajectory_policy", forbidden)
    path = package["kwargs"]["parent_checkpoint_path"]
    arguments = ["model", "diagnose-trajectory-policy", str(path), str(path), str(path)]
    for flag in (
        "--parent-report",
        "--candidate-report",
        "--collection",
        "--search-report",
        "--search-config",
        "--train-report",
        "--validation-report",
        "--split-manifest",
        "--ruleset-manifest",
        "--output",
    ):
        arguments.extend((flag, str(path)))
    assert main(arguments) == 1
    assert "must differ from every source artifact" in capsys.readouterr().out
