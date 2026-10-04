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
from spireshift.trajectory_policy import (
    FROZEN_HEADS,
    TrajectoryPolicyConfig,
    _features,
    _gradient,
    _Preference,
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


@pytest.fixture
def package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
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
        "collection": collection,
        "root": tmp_path,
        "recipe": base_recipe,
    }


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


def test_cli_rejects_existing_output_before_starting_training(
    package: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def forbidden(**kwargs: Any) -> Any:
        raise AssertionError("Training must not start")

    monkeypatch.setattr("spireshift.cli.train_trajectory_policy", forbidden)
    path = package["kwargs"]["parent_checkpoint_path"]
    rc = main(
        [
            "model",
            "finetune-trajectory-policy",
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
