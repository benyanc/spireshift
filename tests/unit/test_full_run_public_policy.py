from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from spireshift.adapters.evangambit import EvanGambitBackendError, EvanGambitLayout
from spireshift.adapters.evangambit_public_choices import (
    ADAPTER_VERSION,
    PublicChoiceEnvironment,
    choice_view,
    load_public_choice_backend,
    public_choice_manifest,
)
from spireshift.core.manifest import load_patch_manifest, manifest_identifier
from spireshift.core.objective import load_objective
from spireshift.core.types import DecisionType, LegalAction, Observation
from spireshift.full_run_experience import CASE_SCHEMA, save_episode
from spireshift.full_run_features import PHASE_NAMES
from spireshift.full_run_policy import FullRunModel, initial_full_run_model
from spireshift.full_run_public_audit import (
    IntegrationRecipe,
    audit_replay_case,
    load_integration_recipe,
    run_integration_audit,
)
from spireshift.full_run_public_policy import (
    DIRECT_FEATURES,
    PublicFullRunModel,
    PublicFullRunPolicy,
    initial_public_full_run_model,
    public_full_run_input,
)
from spireshift.neural_combat_features import CARD_FLAGS
from spireshift.resource_tracking import EXPERIMENT_METRICS_ENV

SOURCE = Path("manifests/patches/sts2-v0.107.1-evangambit-full-run-repair-v1-pending.json")
CATALOG = {
    str(i): {
        "Cost": 1,
        "BaseDamage": 6 if i == 17 else 0,
        "BaseBlock": 5 if i == 45 else 0,
        "UpgradeDamage": 3,
        "UpgradeBlock": 3,
        "UpgradeCost": 0,
        "Type": "Attack" if i == 17 else "Skill",
        "Target": "AnyEnemy" if i == 17 else "Self",
        **dict.fromkeys(CARD_FLAGS, False),
    }
    for i in (17, 45)
}


class MenuRun:
    def __init__(self, *, phase: int = 0, count: int = 15) -> None:
        self.phase, self.count = phase, count
        self.selected = -1
        self.closed = False
        self.missing_mask = False

    def reset(self, *, seed: int) -> tuple[object, Mapping[str, object]]:
        return self.current()

    def current(self) -> tuple[object, Mapping[str, object]]:
        raw = [0] * 682
        raw[:8] = [60, 80, 0, 3, 3, 5, 0, 0]
        raw[8:16] = [17, 0, 0, 0, 45, 0, 0, 0]
        raw[80:85], raw[95:100] = [8, 8, 0, 0, 10], [8, 8, 0, 0, 10]
        raw[276] = self.phase
        if self.phase == 0 and self.count:
            raw[183:185] = [13, self.count]
            raw[185 : 185 + min(10, self.count) * 4] = [17, 1, 0, 0] * min(10, self.count)
        info = {
            "phase": self.phase,
            "floor": 1,
            "act": "overgrowth",
            "gold": 100,
            "player_hp": 60,
            "player_max_hp": 80,
            "deck_size": 2,
            "deck": [{"card_id": 17, "upgraded": False}, {"card_id": 45, "upgraded": False}],
            "enemy_def_ids": [11, 12, 0, 0, 0, 0],
            "potions": [47, 0],
            "bundle_offer": [17, 17, 17, 45, 45, 45],
            "player_won": False,
        }
        return raw, info

    def public_choice_lists(self) -> Mapping[int, tuple[int, ...]]:
        return {
            22: (1, 13, 0, 1, 1, 0, self.count, *([17, 1, 0, 0] * self.count))
            if self.phase == 0 and self.count
            else (),
            23: (1, self.selected, int(self.selected >= 0)) if self.phase == 12 else (),
            24: (1, 8, 0),
        }

    def action_masks(self) -> object:
        mask = [False] * 64
        if self.phase == 0:
            for i in range(self.count + 1 if self.count else 3):
                mask[i] = not (self.missing_mask and i == self.count)
        elif self.phase == 12:
            mask[0] = mask[1] = True
            mask[2] = self.selected >= 0
        else:
            mask[0] = True
        return mask

    def step(
        self, action: int, target: int = -1
    ) -> tuple[object, float, bool, bool, Mapping[str, object]]:
        if self.phase == 12:
            if action == 2:
                self.phase = 6
            else:
                self.selected = action
        else:
            assert target == -1
            self.phase = 12
        raw, info = self.current()
        return raw, 0.0, self.phase == 6, False, info

    def clone(self, *, resample_hidden: bool, seed: int | None) -> MenuRun:
        return copy.deepcopy(self)

    def map_graph(self) -> Mapping[str, object]:
        return {"nodes": {}, "edges": ()}

    def close(self) -> None:
        self.closed = True


def environment(run: MenuRun) -> PublicChoiceEnvironment:
    manifest = public_choice_manifest(load_patch_manifest(SOURCE))
    layout = EvanGambitLayout(
        6,
        2,
        PHASE_NAMES,
        {0: DecisionType.COMBAT, 12: DecisionType.CARD_SELECTION},
        682,
        64,
        6,
        80,
        15,
        10,
        8,
        4,
        frozenset({17}),
        frozenset({47}),
    )
    return PublicChoiceEnvironment(
        lambda: MenuRun(), manifest, layout, allow_pending=True, backend=run
    )


def changed(observation: Observation, state: dict[str, Any]) -> Observation:
    return replace(
        observation,
        public_state=state,
        state_hash=hashlib.sha256(
            json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    )


def test_adapter_keeps_all_menu_actions_without_hand_target_decorations() -> None:
    env = environment(MenuRun())
    obs = env.reset(1)
    actions = tuple(env.legal_actions())
    assert len(actions) == 16
    assert all(a.payload.get("target_index", -1) == -1 for a in actions)
    assert obs.public_state["adapter_version"] == ADAPTER_VERSION
    assert obs.public_state["phase"] == "combat"
    assert choice_view(obs).fixed_profile["source_declared_ascension_level"] == 8
    transition = env.step(actions[14])
    assert (
        transition.observation == obs
        and transition.next_observation.public_state["phase"] == "bundle_selection"
    )
    env.close()


def test_adapter_rejects_a_missing_legal_menu_action_and_preserves_normal_targeting() -> None:
    run = MenuRun()
    env = environment(run)
    env.reset(1)
    run.missing_mask = True
    with pytest.raises(ValueError, match="must be retained"):
        env.legal_actions()
    normal = environment(MenuRun(count=0))
    normal.reset(1)
    assert [a.payload.get("target_index", -1) for a in normal.legal_actions()] == [0, 1, -1, -1]


def test_clone_and_bundle_confirm_keep_the_new_projection_and_progress() -> None:
    env = environment(MenuRun(phase=12))
    env.reset(1)
    assert len(env.legal_actions()) == 2
    env.step(env.legal_actions()[1])
    assert len(env.legal_actions()) == 3
    clone = env.clone(resample_hidden=False)
    assert isinstance(clone, PublicChoiceEnvironment)
    assert clone._observation == env._observation
    result = clone.step(clone.legal_actions()[2])
    assert result.terminal and not result.victory and result.reward == 0
    assert env._observation is not None
    assert choice_view(env._observation).bundle_selection == {
        "selected_bundle": 1,
        "confirmation_enabled": True,
    }
    clone.close()
    env.close()


def test_pending_loader_stops_before_importing_or_opening_native_files(tmp_path: Path) -> None:
    manifest = public_choice_manifest(load_patch_manifest(SOURCE))
    path = tmp_path / "pending.json"
    path.write_text(json.dumps(manifest.as_dict()))
    with pytest.raises(EvanGambitBackendError, match="pending conformance"):
        load_public_choice_backend(tmp_path / "does-not-exist", path)


def test_player_scores_every_offered_card_and_skip_with_complete_context() -> None:
    env = environment(MenuRun())
    obs = env.reset(1)
    model = initial_public_full_run_model(env.ruleset, CATALOG, "a" * 64)
    decision = PublicFullRunPolicy(env.ruleset, model).predict(obs, env.legal_actions())
    assert len(decision.inputs.vectors) == len(decision.logits) == 16
    assert len(decision.inputs.context["combat"]["selection_cards"]) == 15
    assert decision.inputs.bindings[14]["card"]["upgraded"]
    assert decision.inputs.bindings[15]["kind"] == "skip_combat_selection"
    assert decision.selected_action in env.legal_actions()
    assert sum(decision.probabilities) == pytest.approx(1)
    reverse = PublicFullRunPolicy(env.ruleset, model).predict(
        obs, tuple(reversed(env.legal_actions()))
    )
    assert reverse.inputs.vectors == tuple(reversed(decision.inputs.vectors))


def test_new_model_roundtrips_mutates_all_weights_and_rejects_historical_schema() -> None:
    env = environment(MenuRun())
    old = initial_full_run_model(env.ruleset, CATALOG, "a" * 64)
    new = initial_public_full_run_model(env.ruleset, CATALOG, "a" * 64)
    assert new.parameter_count == old.parameter_count == 4384
    assert new.model_id != old.model_id
    assert PublicFullRunModel.from_mapping(new.as_dict()).as_dict() == new.as_dict()
    assert isinstance(new.with_genome([0] * new.parameter_count), PublicFullRunModel)
    with pytest.raises(ValueError):
        PublicFullRunModel.from_mapping(old.as_dict())
    with pytest.raises(ValueError):
        FullRunModel.from_mapping(new.as_dict())
    with pytest.raises(ValueError, match="Historical genomes"):
        PublicFullRunPolicy(env.ruleset, old)  # type: ignore[arg-type]


def test_bundle_confirmation_uses_contents_not_selected_index_and_is_learnable() -> None:
    env = environment(MenuRun(phase=12))
    env.reset(1)
    obs = env.step(env.legal_actions()[0]).next_observation
    model = initial_public_full_run_model(env.ruleset, CATALOG, "a" * 64)
    decision = PublicFullRunPolicy(env.ruleset, model).predict(obs, env.legal_actions())
    assert decision.selected_action.payload["action_index"] == 2
    swapped = copy.deepcopy(obs.public_state)
    swapped["bundle_offer"] = swapped["bundle_offer"][3:] + swapped["bundle_offer"][:3]
    swapped["public_choice_lists"]["bundle"][1] = 1
    permuted = (env.legal_actions()[1], env.legal_actions()[0], env.legal_actions()[2])
    other = public_full_run_input(env.ruleset, changed(obs, swapped), permuted, CATALOG, 256)
    assert other.vectors == decision.inputs.vectors
    genes = [0.0] * model.parameter_count
    genes[-model.dimension + DIRECT_FEATURES.index("select_bundle")] = 3.0
    learned = PublicFullRunPolicy(env.ruleset, model.with_genome(genes)).predict(
        obs, env.legal_actions()
    )
    assert learned.selected_action.payload["action_index"] == 0  # No fixed action restriction.


@pytest.mark.parametrize("kind", ["hidden", "inconsistent", "missing", "extra_action"])
def test_public_boundary_and_complete_binding_reject_invalid_inputs(kind: str) -> None:
    env = environment(MenuRun())
    obs = env.reset(1)
    state = copy.deepcopy(obs.public_state)
    actions = tuple(env.legal_actions())
    if kind == "hidden":
        state["rng_state"] = 12
    elif kind == "inconsistent":
        state["observation_vector"][185] = 45
    elif kind == "missing":
        state.pop("public_choice_lists")
    else:
        actions += (
            LegalAction("extra", "evangambit_combat", {"phase": "combat", "action_index": 16}),
        )
    with pytest.raises(ValueError):
        public_full_run_input(env.ruleset, changed(obs, state), actions, CATALOG, 256)


def saved_failure(
    tmp_path: Path, error: str | None, status: str = "unsupported"
) -> tuple[Path, dict[str, Any]]:
    path = tmp_path / "source.json"
    case = {
        "schema_version": CASE_SCHEMA,
        "binding": {"partition": "train", "seed": 1},
        "outcome": {"decisions": 0, "status": status},
        "trace_digest": manifest_identifier([]),
        "error": error,
    }
    case["case_id"] = manifest_identifier(case)
    save_episode(path, case, [])
    return path, {
        "case_id": case["case_id"],
        "run_seed": 1,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def test_compatibility_replay_binds_saved_overflow_and_releases_environment(tmp_path: Path) -> None:
    path, entry = saved_failure(
        tmp_path, "ValueError: Public combat selection exceeds visible cards"
    )
    run = MenuRun()
    env = environment(run)
    policy = PublicFullRunPolicy(
        env.ruleset, initial_public_full_run_model(env.ruleset, CATALOG, "a" * 64)
    )
    result = audit_replay_case(
        path, entry, lambda: env, policy, load_objective(Path("configs/default.toml"))
    )
    assert result["status"] == "passed" and run.closed
    assert result["game_prefixes_started"] == 1
    assert result["checks"]["overflow_endpoint_bound"] == 1
    assert result["transitions"] == 0


def test_compatibility_replay_confirm_exits_bundle_menu_without_training(tmp_path: Path) -> None:
    path, entry = saved_failure(tmp_path, None, "liveness_failure")
    run = MenuRun(phase=12)
    run.selected = 0
    env = environment(run)
    policy = PublicFullRunPolicy(
        env.ruleset, initial_public_full_run_model(env.ruleset, CATALOG, "a" * 64)
    )
    result = audit_replay_case(
        path, entry, lambda: env, policy, load_objective(Path("configs/default.toml"))
    )
    assert result["status"] == "passed" and result["transitions"] == 1 and run.closed
    assert result["checks"]["bundle_confirmation_progress"] == 1


@pytest.mark.parametrize("failure", ["changed_source", "not_reproduced", "uncovered_stall"])
def test_replay_keeps_corrupt_or_unresolved_source_failures_in_results(
    tmp_path: Path, failure: str
) -> None:
    path, entry = saved_failure(
        tmp_path,
        "ValueError: Public combat selection exceeds visible cards",
        "liveness_failure" if failure == "uncovered_stall" else "unsupported",
    )
    if failure == "changed_source":
        path.write_text(path.read_text() + " ")
    if failure == "uncovered_stall":
        path, entry = saved_failure(tmp_path / "stall", None, "liveness_failure")
    run = MenuRun(count=0)
    env = environment(run)
    policy = PublicFullRunPolicy(
        env.ruleset, initial_public_full_run_model(env.ruleset, CATALOG, "a" * 64)
    )
    result = audit_replay_case(
        path, entry, lambda: env, policy, load_objective(Path("configs/default.toml"))
    )
    assert result["status"] == "failed" and result["error"]
    if failure != "changed_source":
        assert run.closed


def test_batch_audit_needs_resource_wrapper_before_any_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(EXPERIMENT_METRICS_ENV, raising=False)
    manifest = public_choice_manifest(load_patch_manifest(SOURCE))
    recipe = IntegrationRecipe(
        {"output_dir": "audit"},
        tmp_path,
        manifest,
        load_objective(Path("configs/default.toml")),
        (),
    )
    with pytest.raises(ValueError, match="owner integration-audit script"):
        run_integration_audit(recipe)
    assert not recipe.output.exists()


@pytest.mark.parametrize("case_path", ["cases/train/source.json", "../escaped.json"])
def test_audit_resolves_episodes_from_declared_pilot_root_not_index_directory(
    tmp_path: Path, case_path: str
) -> None:
    config = json.loads(
        Path("configs/backend-repair/sts2-v0.107.1-public-integration-audit-v1.json").read_text()
    )
    for name in ("objective", "split_manifest"):
        original = Path(config[name]["path"])
        target = tmp_path / original
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(original.read_bytes())
    manifest = public_choice_manifest(load_patch_manifest(SOURCE))
    manifest_path = tmp_path / "pending.json"
    manifest_path.write_text(json.dumps(manifest.as_dict()))
    config["integration_manifest"] = {"path": "pending.json", "id": manifest.manifest_id}
    index: dict[str, Any] = {
        "partition": "train",
        "protocol": {"split_manifest_id": config["split_manifest"]["id"]},
        "cases": [
            {
                "case_id": "sha256:" + "a" * 64,
                "run_seed": 100116,
                "status": "unsupported",
                "trace_available": True,
                "path": case_path,
            }
        ],
    }
    index["index_id"] = manifest_identifier(index)
    pilot = tmp_path / "artifacts/pilot"
    index_path = pilot / "experience/train-index.json"
    index_path.parent.mkdir(parents=True)
    index_path.write_text(json.dumps(index))
    config["source_index"] = {
        "path": str(index_path.relative_to(tmp_path)),
        "case_root": str(pilot.relative_to(tmp_path)),
        "id": index["index_id"],
    }
    config["source_case_ids"] = [index["cases"][0]["case_id"]]
    config["config_id"] = manifest_identifier({k: v for k, v in config.items() if k != "config_id"})
    config_path = tmp_path / "recipe.json"
    config_path.write_text(json.dumps(config))
    if case_path.startswith("../"):
        with pytest.raises(ValueError, match="escapes the frozen training index"):
            load_integration_recipe(config_path, root=tmp_path)
    else:
        recipe = load_integration_recipe(config_path, root=tmp_path)
        assert recipe.source_root / case_path == pilot / "cases/train/source.json"
        assert recipe.source_root != index_path.parent
        assert not recipe.output.exists()  # Reading a recipe does not start a batch.
