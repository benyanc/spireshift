from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from spireshift.adapters.evangambit import EvanGambitLayout
from spireshift.adapters.evangambit_public_choices import (
    PublicChoiceEnvironment,
    public_choice_manifest,
)
from spireshift.core.manifest import load_patch_manifest, manifest_identifier
from spireshift.core.objective import load_objective
from spireshift.core.types import DecisionType
from spireshift.full_run_event_audit import (
    CAPS,
    EventIntegrationRecipe,
    audit_event_case,
    load_event_integration_recipe,
    run_event_integration,
)
from spireshift.full_run_experience import CASE_SCHEMA, save_episode
from spireshift.full_run_features import PHASE_NAMES
from spireshift.full_run_public_audit import IntegrationRecipe
from spireshift.full_run_public_policy import PublicFullRunPolicy, initial_public_full_run_model
from spireshift.neural_combat_features import CARD_FLAGS
from spireshift.resource_tracking import EXPERIMENT_METRICS_ENV

CATALOG = {
    "17": {
        "Cost": 1,
        "BaseDamage": 6,
        "BaseBlock": 0,
        "UpgradeDamage": 3,
        "UpgradeBlock": 0,
        "UpgradeCost": 0,
        "Type": "Attack",
        "Target": "AnyEnemy",
        **dict.fromkeys(CARD_FLAGS, False),
    }
}


class EventRun:
    def __init__(self, event_id: int = 12, *, allow_broken_action: bool = False) -> None:
        self.phase, self.page, self.event_id = 7, 0, event_id
        self.allow_broken_action, self.closed = allow_broken_action, False
        self.encounter_id = {12: 55, 23: 56}.get(event_id, 58)
        self.extra_action = False
        self.lose_hp = False

    def reset(self, *, seed: int) -> tuple[object, Mapping[str, object]]:
        return self.current()

    def current(self) -> tuple[object, Mapping[str, object]]:
        raw = [0] * 682
        raw[:8] = [60, 80, 0, 3, 3, 0, 0, 0]
        raw[80:85] = [8, 8, 0, 0, 10]
        raw[276] = self.phase
        return raw, {
            "phase": self.phase,
            "floor": 5,
            "act": "overgrowth",
            "event_id": self.event_id,
            "player_hp": 60 - int(self.lose_hp and self.phase == 0),
            "player_max_hp": 80,
            "gold": 100,
            "deck_size": 0,
            "deck": [],
            "enemy_def_ids": [11, 0, 0, 0, 0, 0],
            "encounter_id": self.encounter_id if self.phase == 0 else 3,
            "player_won": False,
        }

    def public_choice_lists(self) -> Mapping[int, tuple[int, ...]]:
        return {22: (), 23: (), 24: (1, 8, 0)}

    def action_masks(self) -> object:
        mask = [False] * 64
        mask[0] = True
        if self.phase == 7:
            mask[1] = self.page == 0 or self.extra_action
            mask[3] = self.page == 0 or self.allow_broken_action
        return mask

    def step(
        self, action: int, target: int = -1
    ) -> tuple[object, float, bool, bool, Mapping[str, object]]:
        assert target == -1
        if action == 1:
            self.page = 1
        elif action == 0 and self.page == 1:
            self.phase = 0
        raw, info = self.current()
        return raw, 0.0, False, False, info

    def clone(self, *, resample_hidden: bool, seed: int | None) -> EventRun:
        return copy.deepcopy(self)

    def map_graph(self) -> Mapping[str, object]:
        return {"nodes": {}, "edges": ()}

    def close(self) -> None:
        self.closed = True


def environment(run: EventRun) -> PublicChoiceEnvironment:
    manifest = public_choice_manifest(
        load_patch_manifest(
            Path("manifests/patches/sts2-v0.107.1-evangambit-full-run-repair-v1-pending.json")
        )
    )
    layout = EvanGambitLayout(
        6,
        2,
        PHASE_NAMES,
        {0: DecisionType.COMBAT, 7: DecisionType.EVENT},
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
        lambda: EventRun(), manifest, layout, allow_pending=True, backend=run
    )


def source_failure(
    tmp_path: Path, event_id: int = 12, *, changed_tail: bool = False
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    old = environment(EventRun(event_id, allow_broken_action=True))
    observation = old.reset(1)
    trace = []
    for index, selected in enumerate((1, 3, 3, 3)):
        actions = old.legal_actions()
        selected_index = next(
            i for i, a in enumerate(actions) if a.payload["action_index"] == selected
        )
        result = old.step(actions[selected_index])
        trace.append(
            {
                "decision_index": index,
                "observation": observation.as_dict(),
                "legal_candidates": [a.as_dict() for a in actions],
                "selected_index": selected_index,
                "next_state_hash": result.next_observation.state_hash,
                "environment_reward": result.reward,
                "terminal": result.terminal,
                "victory": result.victory,
            }
        )
        observation = result.next_observation
    old.close()
    if changed_tail:
        trace[-1]["next_state_hash"] = "a" * 64
    case = {
        "schema_version": CASE_SCHEMA,
        "binding": {"partition": "train", "seed": 1},
        "outcome": {"decisions": len(trace), "status": "liveness_failure"},
        "trace_digest": manifest_identifier(trace),
        "error": None,
    }
    case["case_id"] = manifest_identifier(case)
    path = tmp_path / "source.json"
    save_episode(path, case, trace)
    return (
        path,
        {
            "case_id": case["case_id"],
            "run_seed": 1,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        },
        {
            "source_case_id": case["case_id"],
            "event_id": event_id,
            "expected_encounter_id": {12: 55, 23: 56}.get(event_id, 58),
            "source_floor": 5,
            "first_invalid_decision": 1,
            "skipped_noop_actions": 3,
        },
    )


@pytest.mark.parametrize("event_id", [12, 23])
def test_event_replay_scores_all_actions_and_records_replaced_noop_suffix(
    tmp_path: Path, event_id: int
) -> None:
    source, entry, endpoint = source_failure(tmp_path, event_id)
    run = EventRun(event_id)
    env = environment(run)
    policy = PublicFullRunPolicy(
        env.ruleset, initial_public_full_run_model(env.ruleset, CATALOG, "a" * 64)
    )
    result = audit_event_case(
        source, entry, endpoint, lambda: env, policy, load_objective(Path("configs/default.toml"))
    )
    assert result["status"] == "passed", result["error"]
    assert result["transitions"] == 2 and result["scored_observations"] == 3
    assert result["skipped_historical_noop_actions"] == 3 and run.closed
    assert result["checks"] == {"event_continuation_progress": 1, "rejected_event_action_absent": 1}


@pytest.mark.parametrize(
    "failure",
    [
        "source_bytes",
        "tail_progress",
        "rejected_still_legal",
        "extra_action",
        "wrong_fight",
        "resource_loss",
        "wrong_scope",
    ],
)
def test_event_replay_keeps_corruption_and_unfixed_or_unrelated_endpoints_failed(
    tmp_path: Path, failure: str
) -> None:
    source, entry, endpoint = source_failure(tmp_path, changed_tail=failure == "tail_progress")
    if failure == "source_bytes":
        source.write_text(source.read_text() + " ")
    if failure == "wrong_scope":
        endpoint["source_case_id"] = "sha256:" + "b" * 64
    run = EventRun(allow_broken_action=failure == "rejected_still_legal")
    run.extra_action = failure == "extra_action"
    run.encounter_id = 56 if failure == "wrong_fight" else 55
    run.lose_hp = failure == "resource_loss"
    env = environment(run)
    policy = PublicFullRunPolicy(
        env.ruleset, initial_public_full_run_model(env.ruleset, CATALOG, "a" * 64)
    )
    result = audit_event_case(
        source, entry, endpoint, lambda: env, policy, load_objective(Path("configs/default.toml"))
    )
    assert result["status"] == "failed" and result["error"]
    assert result["skipped_historical_noop_actions"] == 0
    if result["game_prefixes_started"]:
        assert run.closed


def test_event_batch_requires_resource_caps_before_creating_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(EXPERIMENT_METRICS_ENV, raising=False)
    env = environment(EventRun())
    base = IntegrationRecipe(
        {}, tmp_path, env._manifest, load_objective(Path("configs/default.toml")), ()
    )
    recipe = EventIntegrationRecipe({"output_dir": "artifacts/new-audit"}, base, env._manifest)
    with pytest.raises(ValueError, match="resource caps"):
        run_event_integration(recipe)
    assert not recipe.output.exists()


def test_event_recipe_cannot_expand_short_job_budget(tmp_path: Path) -> None:
    recipe = json.loads(
        Path("configs/backend-repair/sts2-v0.107.1-event-integration-audit-v1.json").read_text()
    )
    assert recipe["resource_limits"] == CAPS
    recipe["resource_limits"]["wall_seconds"] = 600
    recipe["config_id"] = manifest_identifier({k: v for k, v in recipe.items() if k != "config_id"})
    path = tmp_path / "config.json"
    path.write_text(json.dumps(recipe))
    with pytest.raises(ValueError, match="four-minute"):
        load_event_integration_recipe(path, root=tmp_path)
