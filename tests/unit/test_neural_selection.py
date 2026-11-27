from __future__ import annotations

import copy
import hashlib
import json
import runpy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from test_combat_confirmation import RULESET, SPLIT, identified, recipe
from test_neural_combat import _setup
from test_neural_combat_confirmation import PublicCombatEnvironment

from spireshift.agents.learned import ProductionCheckpointPolicy
from spireshift.combat_confirmation import REPAIRED_SCHEMA, CombatConfirmationConfig
from spireshift.combat_features import (
    DISCARD_LAYOUT_SCHEMA,
    TRANSFORM_LAYOUT_SCHEMA,
    CombatLayout,
    bind_public_combat,
)
from spireshift.core.manifest import manifest_identifier
from spireshift.core.types import LegalAction, Observation
from spireshift.neural_combat import train_neural_combat_inputs
from spireshift.neural_selection import (
    CAPTURE_CLAIM,
    ENGINE_FILES,
    REPAIRED_CLAIM,
    NeuralSelectionCompatibilityPolicy,
    prepare_selection_repair,
)
from spireshift.production_evaluation import (
    load_production_policy_evaluation,
    run_production_policy_evaluation,
)
from spireshift.representations import build_model_input
from spireshift.splits import SplitName

CONFIG = Path("configs/combat-confirmation/sts2-v0.107.1-base-v11-neural-selection-repair-v2.json")
OLD = CombatLayout(RULESET.patch_id, RULESET.manifest_id, TRANSFORM_LAYOUT_SCHEMA)
NEW = CombatLayout(RULESET.patch_id, RULESET.manifest_id, DISCARD_LAYOUT_SCHEMA)


def menu(kind: int, *, skip: bool = False) -> tuple[Observation, tuple[LegalAction, ...]]:
    env = PublicCombatEnvironment()
    env.phase = 1
    obs = env.observation()
    state = copy.deepcopy(obs.public_state)
    v = state["observation_vector"]
    # Offered discard cards are public, but need not be in hand. Include a target
    # decoration on one supplied action: the pinned selector consumes only its index.
    v[12:48] = [0] * 36
    v[183:193] = [kind, 2, 45, 1, 2, 3, 17, 0, 0, 0]
    obs = Observation(
        obs.schema_version, obs.patch_id, obs.decision_type, state, manifest_identifier(state)[7:]
    )
    actions = tuple(
        LegalAction(
            f"select-{i}",
            "evangambit_combat",
            {"phase": "combat", "action_index": i, **({"target_index": 0} if i == 1 else {})},
        )
        for i in range(2 + int(skip))
    )
    return obs, actions


@pytest.mark.parametrize("kind", [1, 13])
def test_discard_choices_bind_public_offers_without_confusing_hand_or_enemy_targets(
    kind: int,
) -> None:
    obs, actions = menu(kind, skip=kind == 13)
    representation = build_model_input(RULESET, obs, actions)
    with pytest.raises(ValueError, match="not a supported"):
        bind_public_combat(representation, OLD)
    bound = bind_public_combat(representation, NEW)
    assert bound is not None
    assert [b["card"]["card_id"] for b in bound.bindings[:2]] == [45, 17]
    assert all(b["target"] is None for b in bound.bindings)
    if kind == 13:
        assert bound.bindings[-1] == {
            "kind": "skip_discard_to_hand",
            "card": None,
            "potion_id": None,
            "target": None,
        }
    # The original decoder contract remains unchanged.
    assert CombatLayout.from_mapping(NEW.as_dict()) == NEW


@pytest.mark.parametrize("wrong", ["count", "missing", "outside", "skip_top", "unknown"])
def test_selection_binding_rejects_incomplete_or_uninterpretable_inputs(wrong: str) -> None:
    obs, actions = menu(13)
    state = copy.deepcopy(obs.public_state)
    if wrong == "count":
        state["observation_vector"][6] = 1
    elif wrong == "missing":
        actions = actions[:1]
    elif wrong == "outside":
        actions += (
            LegalAction("outside", "evangambit_combat", {"phase": "combat", "action_index": 3}),
        )
    elif wrong == "skip_top":
        obs, actions = menu(1, skip=True)
        state = obs.public_state
    else:
        state["observation_vector"][183] = 21
    obs = Observation(
        obs.schema_version, obs.patch_id, obs.decision_type, state, manifest_identifier(state)[7:]
    )
    with pytest.raises(ValueError):
        bind_public_combat(build_model_input(RULESET, obs, actions), NEW)


def test_skip_is_never_created_when_absent_from_the_supplied_menu() -> None:
    obs, actions = menu(13)
    bound = bind_public_combat(build_model_input(RULESET, obs, actions), NEW)
    assert bound is not None and len(bound.bindings) == 2
    assert all(b["kind"] == "select_discard_to_hand" for b in bound.bindings)


def test_failure_recorder_preserves_the_public_menu_without_claiming_an_action(
    neural_pair: Any,
) -> None:
    recorder_class = runpy.run_path("scripts/capture-neural-selection-failures-v1.py")[
        "PublicRecorder"
    ]
    recorder = recorder_class(neural_pair[0])
    obs, actions = menu(13, skip=True)
    with pytest.raises(ValueError, match="not a supported"):
        recorder.choose_action(obs, actions)
    assert recorder.rows == [
        {
            "observation": obs.as_dict(),
            "legal_actions": [a.as_dict() for a in actions],
            "selected_action_id": None,
        }
    ]
    state = copy.deepcopy(obs.public_state)
    state["rng_state"] = 1
    bad = Observation(
        obs.schema_version, obs.patch_id, obs.decision_type, state, manifest_identifier(state)[7:]
    )
    with pytest.raises(ValueError):
        recorder.choose_action(bad, actions)
    assert len(recorder.rows) == 1  # No privileged row was captured.


@pytest.fixture
def neural_pair() -> tuple[ProductionCheckpointPolicy, ProductionCheckpointPolicy]:
    config, inputs, catalog = _setup()
    learned = train_neural_combat_inputs(inputs=inputs, config=config, catalog=catalog)
    # This fixture isolates runtime binding; production saved-report validation has
    # separate tests and is exercised by the real saved-artifact preflight.
    parent_report = {
        "model_id": inputs.parent_checkpoint["model_id"],
        "held_out_metrics": {"policy": {"auxiliary_policy_gate": {"passed": True}}},
    }
    pair = (
        ProductionCheckpointPolicy(
            checkpoint=learned.checkpoint, training_report=learned.report, ruleset=RULESET
        ),
        ProductionCheckpointPolicy(
            checkpoint=inputs.parent_checkpoint,
            training_report=parent_report,
            ruleset=RULESET,
        ),
    )
    for policy in pair:
        policy.split_manifest_id = SPLIT.manifest_id
    return pair


def test_repair_preserves_all_weights_and_predictions_on_supported_inputs(neural_pair: Any) -> None:
    source, _ = neural_pair
    repaired = NeuralSelectionCompatibilityPolicy(source, NEW)
    assert repaired.model_id == source.model_id and repaired.policy_id != source.policy_id
    old_head = source._model.combat_policy_residual
    new_head = repaired._model.combat_policy_residual
    assert old_head is not None and new_head is not None
    assert old_head.layout == OLD and new_head.layout == NEW
    for key in ("input_weights", "hidden_bias", "output_weights", "catalog"):
        assert getattr(old_head, key) == getattr(new_head, key)
    env = PublicCombatEnvironment()
    for phase in (0, 1):
        env.phase = phase
        obs, actions = env.observation(), env.legal_actions()
        representation = build_model_input(RULESET, obs, actions)
        assert source._model.predict(representation) == repaired._model.predict(representation)
        if phase == 1:
            a, b = bind_public_combat(representation, OLD), bind_public_combat(representation, NEW)
            assert a is not None and b is not None
            assert a.vectors(64) == b.vectors(64)
    for kind in (1, 13):
        obs, actions = menu(kind, skip=kind == 13)
        with pytest.raises(ValueError):
            source.predict(obs, actions)
        decision = repaired.predict(obs, actions)
        assert decision.selected_action in actions
        assert decision.source_action_ids == tuple(a.action_id for a in actions)
        assert sum(decision.policy) == pytest.approx(1)


@pytest.mark.parametrize("kind", [15, 20])
def test_original_selection_predictions_and_coordinates_are_preserved(
    neural_pair: Any, kind: int
) -> None:
    source, _ = neural_pair
    repaired = NeuralSelectionCompatibilityPolicy(source, NEW)
    obs, actions = menu(kind)
    state = copy.deepcopy(obs.public_state)
    v = state["observation_vector"]
    v[186] = 0  # The upgrade menu offers only unupgraded cards.
    v[8:16] = v[185:193]
    obs = Observation(
        obs.schema_version, obs.patch_id, obs.decision_type, state, manifest_identifier(state)[7:]
    )
    representation = build_model_input(RULESET, obs, actions)
    old, new = bind_public_combat(representation, OLD), bind_public_combat(representation, NEW)
    assert old is not None and new is not None
    assert old.vectors(64) == new.vectors(64)
    assert source._model.predict(representation) == repaired._model.predict(representation)


class SelectionEnvironment(PublicCombatEnvironment):
    def reset(self, seed: int) -> Observation:
        self.selection_kind = 1 if seed == SPLIT.seeds(SplitName.TRAIN)[0] else 13
        return super().reset(seed)

    def observation(self) -> Observation:
        if self.phase == 1:
            return menu(self.selection_kind)[0]
        return super().observation()

    def legal_actions(self) -> tuple[LegalAction, ...]:
        if self.phase == 1:
            return menu(self.selection_kind)[1]
        return super().legal_actions()


def _repair_inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pair: Any) -> dict[str, Any]:
    candidate, reference = pair
    d = recipe().document
    d["candidate"].update(model_id=candidate.model_id)
    d["reference"].update(model_id=reference.model_id)
    source_config = CombatConfirmationConfig.from_mapping(identified(d, "config_id"))
    (tmp_path / "original.json").write_text(json.dumps(source_config.document))
    result = run_production_policy_evaluation(
        environment_factory=SelectionEnvironment,
        ruleset=RULESET,
        learned_policy=candidate,
        reference_policy=reference,
        training_report_id=d["candidate"]["report_id"],
        reference_training_report_id=d["reference"]["report_id"],
        split_manifest=SPLIT,
        seeds=d["seeds"],
        workers=1,
        maximum_decisions_per_run=8,
        output_directory=tmp_path / "comparison",
        partition=SplitName.TRAIN,
        confirmation=source_config,
    )
    resource = {
        "report_id": "sha256:" + "4" * 64,
        "status": "failed",
        "exit_code": 1,
        "cap": None,
        "experiment_kind": "rollout",
        "usage": {"trajectories": 4, "simulations": 0, "transitions": 6},
    }
    monkeypatch.setattr("spireshift.neural_selection.load_resource_report", lambda p: resource)
    entries = []
    for entry in result.report["cases"]:
        if entry["policy_kind"] != "production_checkpoint":
            continue
        case = json.loads((result.report_path.parent / entry["path"]).read_text())
        env = SelectionEnvironment()
        obs = env.reset(entry["seed"])
        actions = env.legal_actions()
        selected = candidate.choose_action(obs, actions)
        rows = [
            {
                "observation": obs.as_dict(),
                "legal_actions": [a.as_dict() for a in actions],
                "selected_action_id": selected.action_id,
            }
        ]
        obs = env.step(selected).next_observation
        actions = env.legal_actions()
        rows.append(
            {
                "observation": obs.as_dict(),
                "legal_actions": [a.as_dict() for a in actions],
                "selected_action_id": None,
            }
        )
        capture = identified(
            {
                "schema_version": "public-combat-menu-failure-capture-v1",
                "claim_scope": CAPTURE_CLAIM,
                "source_report_id": result.report["report_id"],
                "source_case_id": case["case_id"],
                "model_id": candidate.model_id,
                "ruleset_manifest_id": RULESET.manifest_id,
                "objective": d["objective"],
                "seed": entry["seed"],
                "public_rows": rows,
                "replay_result": case,
                "optimizer_steps": 0,
            },
            "capture_id",
        )
        name = f"capture-{entry['seed']}.json"
        (tmp_path / name).write_text(json.dumps(capture))
        entries.append(
            {
                "seed": entry["seed"],
                "path": name,
                "capture_id": capture["capture_id"],
                "selection_kind": env.selection_kind,
                "visible_choices": 2,
                "legal_action_count": 2,
                "source_case_reproduced": True,
            }
        )
    collection = identified(
        {
            "schema_version": "public-combat-menu-failure-capture-collection-v1",
            "claim_scope": CAPTURE_CLAIM,
            "source_report_id": result.report["report_id"],
            "cases": entries,
            "games": 2,
            "transitions": 2,
            "simulations": 0,
            "optimizer_steps": 0,
        },
        "report_id",
    )
    (tmp_path / "captures.json").write_text(json.dumps(collection))
    repair = copy.deepcopy(json.loads(CONFIG.read_text())["selection_repair"])
    repair.update(
        source_confirmation_path="original.json",
        source_confirmation_id=source_config.document["config_id"],
        source_comparison_path="comparison/production-policy-evaluation.json",
        source_comparison_report_id=result.report["report_id"],
        source_comparison_resource_path="resources.json",
        source_comparison_resource_report_id=resource["report_id"],
        capture_collection_path="captures.json",
        capture_collection_id=collection["report_id"],
        engine_source_root="engine",
        layout=NEW.as_dict(),
    )
    for name in ENGINE_FILES:
        path = tmp_path / "engine" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("frozen synthetic semantics")
        repair["engine_source_sha256"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
    d.update(schema_version=REPAIRED_SCHEMA, claim_scope=REPAIRED_CLAIM, selection_repair=repair)
    current = CombatConfirmationConfig.from_mapping(identified(d, "config_id"))
    return {
        "repair": repair,
        "confirmation_document": current.document,
        "candidate": candidate,
        "reference": reference,
        "project_root": tmp_path,
        "split": SPLIT,
    }


@pytest.mark.parametrize(
    "wrong", [None, "cohort", "capture", "resource", "semantics", "privileged"]
)
def test_repair_preflight_checks_original_failures_public_captures_and_source_bindings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, neural_pair: Any, wrong: str | None
) -> None:
    args = _repair_inputs(tmp_path, monkeypatch, neural_pair)
    if wrong == "cohort":
        args["confirmation_document"]["seeds"][0] += 1
    elif wrong == "capture":
        args["repair"]["capture_collection_id"] = "sha256:" + "3" * 64
    elif wrong == "resource":
        args["repair"]["source_comparison_resource_report_id"] = "sha256:" + "3" * 64
    elif wrong == "semantics":
        next((tmp_path / "engine").rglob("*.cs")).write_text("changed")
    elif wrong == "privileged":
        # A correctly hashed untrusted public input still cannot smuggle hidden fields.
        capture_path = next(tmp_path.glob("capture-*.json"))
        capture = json.loads(capture_path.read_text())
        capture["public_rows"][0]["observation"]["public_state"]["rng_state"] = 1
        state = capture["public_rows"][0]["observation"]["public_state"]
        capture["public_rows"][0]["observation"]["state_hash"] = manifest_identifier(state)[7:]
        capture = identified(capture, "capture_id")
        capture_path.write_text(json.dumps(capture))
        collection = json.loads((tmp_path / "captures.json").read_text())
        for entry in collection["cases"]:
            if entry["path"] == capture_path.name:
                entry["capture_id"] = capture["capture_id"]
        collection = identified(collection, "report_id")
        (tmp_path / "captures.json").write_text(json.dumps(collection))
        args["repair"]["capture_collection_id"] = collection["report_id"]

    def forbidden(*a: Any, **kw: Any) -> Any:
        pytest.fail("Saved compatibility preflight cannot predict or create a backend")

    monkeypatch.setattr(ProductionCheckpointPolicy, "predict", forbidden)
    monkeypatch.setattr("spireshift.cli.load_evangambit_backend", forbidden)
    if wrong is None:
        fixed = prepare_selection_repair(**args)
        assert (
            fixed.policy_id
            == CombatConfirmationConfig.from_mapping(
                args["confirmation_document"]
            ).candidate_policy_id()
        )
    else:
        with pytest.raises(ValueError):
            prepare_selection_repair(**args)


def test_repaired_comparison_is_versioned_and_cached_validation_keeps_all_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, neural_pair: Any
) -> None:
    args = _repair_inputs(tmp_path, monkeypatch, neural_pair)
    repaired = prepare_selection_repair(**args)
    config = CombatConfirmationConfig.from_mapping(args["confirmation_document"])
    result = run_production_policy_evaluation(
        environment_factory=SelectionEnvironment,
        ruleset=RULESET,
        learned_policy=repaired,
        reference_policy=args["reference"],
        training_report_id=config.document["candidate"]["report_id"],
        reference_training_report_id=config.document["reference"]["report_id"],
        split_manifest=SPLIT,
        seeds=config.document["seeds"],
        workers=1,
        maximum_decisions_per_run=8,
        output_directory=tmp_path / "corrected",
        partition=SplitName.TRAIN,
        confirmation=config,
    )
    assert result.report["claim_scope"] == REPAIRED_CLAIM
    assert result.report["configuration"]["paired_policies"][0] == repaired.policy_id
    assert result.report["summary"]["candidate"]["failed_runs"] == 0

    def forbidden(*a: Any, **kw: Any) -> Any:
        pytest.fail("Cached loading cannot predict or create a backend")

    monkeypatch.setattr(ProductionCheckpointPolicy, "predict", forbidden)
    loaded = load_production_policy_evaluation(
        result.report_path,
        model_id=repaired.model_id,
        training_report_id=config.document["candidate"]["report_id"],
        reference_model_id=args["reference"].model_id,
        reference_training_report_id=config.document["reference"]["report_id"],
        split_manifest=SPLIT,
    )
    assert loaded == result.report
    registry: Registry[Any] = Registry().with_resources(
        [
            (
                f"https://spireshift.dev/schemas/{p.name}",
                Resource.from_contents(json.loads(p.read_text())),
            )
            for p in Path("schemas").glob("*.json")
        ]
    )
    for name, document in [
        ("combat-policy-confirmation-config-v2", config.document),
        ("production-policy-evaluation-v5", loaded),
    ]:
        Draft202012Validator(
            json.loads(Path(f"schemas/{name}.json").read_text()), registry=registry
        ).validate(document)
    # Original failure report remains intact and verifies after classifier repair.
    original = json.loads((tmp_path / "comparison/production-policy-evaluation.json").read_text())
    assert original["summary"]["candidate"]["failed_runs"] == 2
    assert original["summary"]["candidate"]["unsupported_public_combat_runs"] == 2


def test_changed_runtime_policy_cannot_enter_a_corrective_comparison(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, neural_pair: Any
) -> None:
    args = _repair_inputs(tmp_path, monkeypatch, neural_pair)
    config = CombatConfirmationConfig.from_mapping(args["confirmation_document"])

    def forbidden() -> Any:
        pytest.fail("Unrepaired policy cannot initialize a corrective comparison")

    with pytest.raises(ValueError, match="runtime policy"):
        run_production_policy_evaluation(
            environment_factory=forbidden,
            ruleset=RULESET,
            learned_policy=args["candidate"],
            reference_policy=args["reference"],
            training_report_id=config.document["candidate"]["report_id"],
            reference_training_report_id=config.document["reference"]["report_id"],
            split_manifest=SPLIT,
            seeds=config.document["seeds"],
            workers=1,
            maximum_decisions_per_run=8,
            output_directory=tmp_path / "invalid",
            partition=SplitName.TRAIN,
            confirmation=config,
        )
