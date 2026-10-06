from __future__ import annotations

import copy
import json
import os
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.cli import main
from spireshift.combat_features import ENCODER_ID, CombatLayout, bind_public_combat
from spireshift.combat_foundation import (
    CONFIG_SCHEMA,
    CombatFoundationConfig,
    _decision,
    _pair_evidence,
    analyze_combat_foundation,
    load_combat_foundation_config,
    load_combat_foundation_report,
    run_combat_foundation_audit,
)
from spireshift.core.manifest import manifest_identifier
from spireshift.core.objective import load_objective
from spireshift.core.types import DecisionType, LegalAction, Observation
from spireshift.production_models import ProductionTrainingConfig, _Outcome, _ProductionExample
from spireshift.representations import CompositionalModelInput, build_model_input
from spireshift.resource_tracking import EXPERIMENT_METRICS_ENV
from spireshift.splits import SplitName, load_split_manifest

CONFIG_PATH = Path("configs/combat-foundation/sts2-v0.107.1-base-v2-audit-v1.json")
MOCK_RULESET = MockSpireEnvironment.ruleset
LAYOUT = CombatLayout(MOCK_RULESET.patch_id, MOCK_RULESET.manifest_id)


def _public() -> dict[str, Any]:
    v = [0] * 682
    v[:8] = [20, 40, 2, 3, 3, 8, 2, 0]
    v[8:16] = [17, 0, 0, 0, 45, 1, 2, 3]
    v[48:50] = [47, 1]
    v[60:64] = [0, 4, 5, -1]  # Zero is a real Strength identity.
    v[80:87] = [10, 20, 1, 0, 6, 0, 3]
    v[95:100] = [30, 30, 0, 4, 1]
    return {
        "observation_vector": v,
        "player_hp": 20,
        "player_max_hp": 40,
        "enemy_def_ids": [7, 8],
        "potions": [47, 0, 0, 0, 0, 0],
        "act": "underdocks",
        "floor": 2,
        "terminal": False,
        "victory": False,
    }


def _action(index: int, target: int | None = None, name: str | None = None) -> LegalAction:
    payload: dict[str, Any] = {"phase": "combat", "action_index": index}
    if target is not None:
        payload["target_index"] = target
    return LegalAction(name or f"card-{index}-{target}", "evangambit_combat", payload)


def _rep(
    public: dict[str, Any] | None = None,
    actions: tuple[LegalAction, ...] | None = None,
) -> CompositionalModelInput:
    state = _public() if public is None else public
    obs = Observation(
        "observation-v1",
        MOCK_RULESET.patch_id,
        DecisionType.COMBAT,
        state,
        manifest_identifier(state)[7:],
    )
    return build_model_input(
        MOCK_RULESET, obs, actions or (_action(0, 0), _action(1), _action(2), _action(3, 1))
    )


def _identified(d: dict[str, Any], key: str = "config_id") -> dict[str, Any]:
    return {**d, key: manifest_identifier({k: v for k, v in d.items() if k != key})}


def _config() -> CombatFoundationConfig:
    d = copy.deepcopy(load_combat_foundation_config(CONFIG_PATH).document)
    d["layout"] = LAYOUT.as_dict()
    d["complete_run_subfolds"] = {"fit": [1, 2], "selection": [3, 4]}
    d["analysis"].update(
        minimum_fit_signal_runs=1,
        minimum_selection_signal_runs=1,
        minimum_fit_card_ids=2,
        minimum_fit_floor_bins=1,
    )
    return CombatFoundationConfig.from_mapping(_identified(d))


def _example(seed: int, index: int = 0) -> _ProductionExample:
    rep = _rep()
    outcomes = tuple(
        tuple(_Outcome(floor, True, False, True, 20) for _ in range(16)) for floor in (2, 6, 2, 5)
    )
    return _ProductionExample(
        f"seed-{seed}-combat-{index}",
        seed,
        "combat",
        rep,
        ({0: 1.0}, {1: 1.0}, {2: 1.0}, {3: 1.0}),
        ((0.5, 0.1, 0.5, 0.1), (0.9, 0.5, 0.9, 0.9), (0.5, 0.1, 0.5, 0.1), (0.9, 0.1, 0.9, 0.5)),
        (0.1, 0.5, 0.1, 0.3),
        1.0,
        1.0,
        1,
        (0.1, 0.2, 0.1, 0.18),
        outcomes,
    )


def _report() -> dict[str, Any]:
    body = analyze_combat_foundation(
        examples=tuple(_example(s) for s in range(1, 5)), config=_config(), parent_weights={}
    )
    return _identified(body, "report_id")


def test_cards_targets_potions_end_turn_and_zero_id_strength_bind() -> None:
    value = bind_public_combat(_rep(), LAYOUT)
    assert value is not None
    assert [b["kind"] for b in value.bindings] == [
        "play_card",
        "play_card",
        "end_turn",
        "use_potion",
    ]
    assert value.bindings[0]["card"]["card_id"] == 17
    assert value.bindings[0]["target"]["hp"] == 10
    assert value.bindings[3]["target"]["enemy_id"] == 8
    assert value.context["player"]["statuses"][0] == {"status_id": 0, "amount": 4}
    assert value.bindings[0]["target"]["statuses"] == [{"status_id": 0, "amount": 3}]
    assert any("card_id=17" in t for t in value.tokens[0])
    assert any("public_position=0" in t for t in value.tokens[0])
    assert ENCODER_ID == "evangambit-public-card-target-v1"


def test_hand_reordering_and_opaque_action_renaming_preserve_features() -> None:
    original = bind_public_combat(_rep(), LAYOUT)
    state = _public()
    state["observation_vector"][8:16] = (
        state["observation_vector"][12:16] + state["observation_vector"][8:12]
    )
    moved = bind_public_combat(
        _rep(
            state,
            (
                _action(1, 0, "renamed-A"),
                _action(0, name="renamed-B"),
                _action(2, name="renamed-end"),
                _action(3, 1, "renamed-potion"),
            ),
        ),
        LAYOUT,
    )
    assert original is not None and moved is not None
    assert original.tokens == moved.tokens
    assert original.vectors(8192) == moved.vectors(8192)
    assert original.source_action_ids != moved.source_action_ids
    assert not any(
        "action_index" in t or "renamed" in t or "state_hash" in t
        for tokens in moved.tokens
        for t in tokens
    )


def test_candidate_order_is_aligned_and_enemy_position_is_preserved() -> None:
    actions = (_action(0, 0), _action(0, 1), _action(2))
    a = bind_public_combat(_rep(actions=actions), LAYOUT)
    b = bind_public_combat(_rep(actions=tuple(reversed(actions))), LAYOUT)
    assert a is not None and b is not None
    assert tuple(reversed(a.tokens)) == b.tokens
    assert a.tokens[0] != a.tokens[1]
    assert a.bindings[0]["target"]["public_position"] == 0


@pytest.mark.parametrize(
    "broken", ["layout", "hp", "potion", "hand_hole", "upgrade", "selection", "dead_target"]
)
def test_bad_public_bindings_fail_closed(broken: str) -> None:
    state = _public()
    if broken == "layout":
        state["observation_vector"].pop()
    if broken == "hp":
        state["player_hp"] = 19
    if broken == "potion":
        state["potions"][0] = 13
    if broken == "hand_hole":
        state["observation_vector"][8:12] = [0, 0, 0, 0]
    if broken == "upgrade":
        state["observation_vector"][9] = 2
    if broken == "selection":
        state["observation_vector"][183] = 1
    if broken == "dead_target":
        state["observation_vector"][80] = 0
    with pytest.raises(ValueError):
        bind_public_combat(_rep(state), LAYOUT)


@pytest.mark.parametrize(
    "actions",
    [
        (_action(0),),
        (_action(0), _action(2, 0)),
        (_action(0), _action(2), _action(4)),
        (_action(0), _action(0, name="duplicate"), _action(2)),
    ],
)
def test_illegal_action_binding_and_missing_end_turn_rejected(
    actions: tuple[LegalAction, ...],
) -> None:
    with pytest.raises(ValueError):
        bind_public_combat(_rep(actions=actions), LAYOUT)


def test_noncombat_parent_path_and_hidden_input_guard() -> None:
    rep = _rep()
    assert bind_public_combat(replace(rep, decision_type="path"), LAYOUT) is None
    with pytest.raises(ValueError, match="patch or ruleset"):
        bind_public_combat(replace(rep, patch_id="other"), LAYOUT)
    state = _public()
    state["rng_state"] = 8
    with pytest.raises(ValueError):
        _rep(state)


def test_terminal_victory_dominates_floor_and_censored_outcomes_cannot_qualify() -> None:
    ex = _example(1)
    winning = tuple(_Outcome(1, True, True, False, 20) for _ in range(16))
    losing = tuple(_Outcome(100, True, False, True, 20) for _ in range(16))
    ex = replace(ex, outcomes=(winning, losing, *ex.outcomes[2:]))
    pair = _pair_evidence(ex, 0, 1, _config().document["analysis"])
    assert pair["left_preference_probability"] == 1 and pair["reliable_advancement"]
    censored = (replace(winning[0], terminal=False), *winning[1:])
    ex = replace(ex, outcomes=(censored, losing, *ex.outcomes[2:]))
    assert not _pair_evidence(ex, 0, 1, _config().document["analysis"])["reliable_advancement"]


def test_half_split_disagreement_and_ties_are_retained() -> None:
    ex = _example(1)
    x = tuple(_Outcome(f, True, False, True, 20) for f in [6] * 8 + [2] * 8)
    y = tuple(_Outcome(4, True, False, True, 20) for _ in range(16))
    pair = _pair_evidence(
        replace(ex, outcomes=(x, y, *ex.outcomes[2:])), 0, 1, _config().document["analysis"]
    )
    assert pair["left_preference_probability"] == 0.5
    assert pair["half_split_direction_sums"] == [8, -8]
    assert not pair["reliable_advancement"]


def test_audit_deterministic_whole_run_counts_no_training_and_failure_denominator() -> None:
    report = _report()
    assert report == _report()
    assert report["summary"]["combat_states"] == 4
    assert report["summary"]["by_subfold"]["fit"]["signal_runs"] == 2
    assert report["decision"]["pilot_data_sufficient"]
    assert not report["decision"]["foundation_ready"]
    assert report["optimizer_steps"] == report["games_replayed"] == 0
    assert report["summary"]["terminal_victories_in_saved_combat_outcomes"] == 0
    ex = _example(4)
    ex = replace(ex, representation=replace(ex.representation, patch_id="wrong"))
    bad = analyze_combat_foundation(
        examples=(*(_example(s) for s in range(1, 4)), ex), config=_config(), parent_weights={}
    )
    assert bad["summary"]["combat_states"] == 4
    assert bad["summary"]["binding_failures"] == 1
    assert not bad["decision"]["pilot_data_sufficient"]
    assert bad["rows"][-1]["binding_status"] == "failed"


def test_correlated_many_states_do_not_inflate_independent_run_coverage() -> None:
    examples = tuple(_example(s, i) for s in range(1, 5) for i in range(4))
    report = analyze_combat_foundation(examples=examples, config=_config(), parent_weights={})
    assert report["summary"]["by_subfold"]["fit"]["signal_runs"] == 2
    assert report["summary"]["by_subfold"]["fit"]["signal_states"] == 8
    plan = {**_config().document["analysis"], "minimum_fit_signal_runs": 3}
    assert not _decision(report["summary"], plan)["pilot_data_sufficient"]
    with pytest.raises(ValueError, match="Duplicate"):
        analyze_combat_foundation(
            examples=(*examples, examples[0]), config=_config(), parent_weights={}
        )


def test_complete_run_ownership_config_and_frozen_layout() -> None:
    d = copy.deepcopy(_config().document)
    d["complete_run_subfolds"]["selection"] = [1, 3]
    with pytest.raises(ValueError, match="share complete"):
        CombatFoundationConfig.from_mapping(_identified(d))
    d = copy.deepcopy(_config().document)
    d["layout"]["hand_offset"] += 1
    with pytest.raises(ValueError, match="layout differs"):
        CombatFoundationConfig.from_mapping(_identified(d))
    d = copy.deepcopy(_config().document)
    d["curriculum_path"] = "../outside"
    with pytest.raises(ValueError, match="inside"):
        CombatFoundationConfig.from_mapping(_identified(d))


def test_no_reading_or_replay_before_owner_provenance_checks(tmp_path: Path) -> None:
    config = _config()
    with pytest.raises(ValueError, match="ruleset/split"):
        run_combat_foundation_audit(
            config=config,
            project_root=tmp_path,
            upstream_root=tmp_path,
            split_manifest=load_split_manifest(
                Path("manifests/splits/mock-v1-seeds-000000-000999-v1.json")
            ),
            ruleset=MOCK_RULESET,
            objective=load_objective(Path("configs/default.toml")),
        )


def test_cached_cli_refuses_overwrite_and_never_runs_source_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import spireshift.combat_foundation as module

    def fail(**kwargs: Any) -> dict[str, Any]:
        raise AssertionError("Source audit must not run")

    monkeypatch.setattr(module, "run_combat_foundation_audit", fail)
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps(_config().document))
    path = tmp_path / "audit.json"
    path.write_text(json.dumps(_report()))
    assert main(["model", "show-combat-foundation", str(path), "--config", str(cfg)]) == 0
    assert '"source_inputs_reaudited": false' in capsys.readouterr().out
    assert (
        main(
            [
                "model",
                "audit-combat-foundation",
                str(cfg),
                "--split-manifest",
                "missing",
                "--manifest",
                "missing",
                "--upstream-root",
                "missing",
                "--output",
                str(path),
            ]
        )
        == 1
    )
    assert "Completed combat data audit" in capsys.readouterr().out
    original = path.read_bytes()
    d = _report()
    d["decision"]["pilot_data_sufficient"] = False
    path.write_text(json.dumps(_identified(d, "report_id")))
    with pytest.raises(ValueError, match="decision differs"):
        load_combat_foundation_report(path, _config())
    assert original != path.read_bytes()
    d = _report()
    d["summary"]["by_subfold"]["fit"]["signal_runs"] += 1
    path.write_text(json.dumps(_identified(d, "report_id")))
    with pytest.raises(ValueError, match="summary differs"):
        load_combat_foundation_report(path, _config())


def test_source_verified_owner_pipeline_and_pinned_source_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hashlib

    import spireshift.combat_foundation as module

    split = load_split_manifest(Path("manifests/splits/mock-v1-seeds-000000-000999-v1.json"))
    objective = load_objective(Path("configs/default.toml"))
    seeds = split.seeds(SplitName.TRAIN)[:4]
    d = copy.deepcopy(_config().document)
    d["split_manifest_id"] = split.manifest_id
    d["complete_run_subfolds"] = {"fit": sorted(seeds[:2]), "selection": sorted(seeds[2:])}
    source = tmp_path / "layout.txt"
    source.write_text("toy pinned public layout and actions")
    d["layout_sources"] = [
        {"path": "layout.txt", "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    ]
    cfg = CombatFoundationConfig.from_mapping(_identified(d))
    checkpoint = {
        "model_id": d["model_id"],
        "ruleset_manifest_id": MOCK_RULESET.manifest_id,
        "split_manifest_id": split.manifest_id,
        "objective_id": objective.objective_id,
        "training_config": ProductionTrainingConfig().as_dict(),
    }
    parent_report = {
        "report_id": d["training_report_id"],
        "held_out_metrics": {"policy": {"auxiliary_policy_gate": {"passed": True}}},
    }
    monkeypatch.setattr(module, "load_production_model_checkpoint", lambda path: checkpoint)
    monkeypatch.setattr(
        module, "load_production_training_report", lambda path, **kwargs: parent_report
    )
    monkeypatch.setattr(
        module, "production_model_from_checkpoint", lambda doc: SimpleNamespace(policy_weights={})
    )
    monkeypatch.setattr(module, "load_starting_repeatability_config", lambda path: None)
    monkeypatch.setattr(
        module,
        "load_starting_repeatability_report",
        lambda path, config: {
            "report_id": d["starting_study"]["report_id"],
            "decision": {
                "next_step": "stop_starting_choice_experiment_return_to_combat_run_level_foundation"
            },
        },
    )
    calls = []

    def loader(path: Path, **kwargs: Any) -> Any:
        calls.append(path)
        return (
            {"dataset_id": d["dataset_id"], "objective": objective.as_dict()},
            SimpleNamespace(
                partition="train",
                ruleset_manifest_id=MOCK_RULESET.manifest_id,
                objective_id=objective.objective_id,
            ),
            tuple(_example(s) for s in seeds),
        )

    monkeypatch.setattr(module, "_load_curriculum_examples", loader)
    report = run_combat_foundation_audit(
        config=cfg,
        project_root=tmp_path,
        upstream_root=tmp_path,
        split_manifest=split,
        ruleset=MOCK_RULESET,
        objective=objective,
    )
    assert len(calls) == 1 and report["source_integrity_verified"]
    assert report["summary"]["combat_states"] == 4
    out = tmp_path / "audit.json"
    out.write_text(json.dumps(report))
    assert load_combat_foundation_report(out, cfg) == report
    source.write_text("changed layout")
    with pytest.raises(ValueError, match="source hash differs"):
        run_combat_foundation_audit(
            config=cfg,
            project_root=tmp_path,
            upstream_root=tmp_path,
            split_manifest=split,
            ruleset=MOCK_RULESET,
            objective=objective,
        )
    assert len(calls) == 1  # Fails before a second saved-case audit.


def test_cli_publishes_atomically_and_records_zero_new_game_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import spireshift.combat_foundation as module

    report = _report()
    monkeypatch.setattr(module, "run_combat_foundation_audit", lambda **kwargs: report)
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps(_config().document))
    metrics = tmp_path / "metrics.json"
    monkeypatch.setenv(EXPERIMENT_METRICS_ENV, str(metrics))
    path = tmp_path / "output/audit.json"
    assert (
        main(
            [
                "model",
                "audit-combat-foundation",
                str(cfg),
                "--split-manifest",
                "manifests/splits/mock-v1-seeds-000000-000999-v1.json",
                "--manifest",
                "manifests/patches/mock-v1.json",
                "--upstream-root",
                "unused",
                "--output",
                str(path),
            ]
        )
        == 0
    )
    assert json.loads(path.read_text()) == report
    assert json.loads(metrics.read_text())["trajectories"] == 0


def test_frozen_production_cohort_and_json_schemas() -> None:
    cfg = load_combat_foundation_config(CONFIG_PATH)
    split = load_split_manifest(
        Path("manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json")
    )
    runs = cfg.document["complete_run_subfolds"]
    assert len(runs["fit"]) == 84 and len(runs["selection"]) == 28
    assert set(runs["fit"] + runs["selection"]) <= set(split.seeds(SplitName.TRAIN))
    assert len(cfg.document["layout_sources"]) == 4
    for path, doc in (
        ("schemas/combat-foundation-audit-config-v1.json", cfg.document),
        ("schemas/combat-foundation-audit-v1.json", _report()),
    ):
        schema = json.loads(Path(path).read_text())
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(doc)
    assert cfg.document["schema_version"] == CONFIG_SCHEMA


def test_owner_script_attempt_rotation_and_completed_cached_display(tmp_path: Path) -> None:
    script = Path("scripts/audit-combat-foundation-v1.sh").read_text()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "bin").mkdir()
    (tmp_path / "scripts/audit.sh").write_text(script)
    log = tmp_path / "calls"
    uv = tmp_path / "bin/uv"
    uv.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "$SPIRESHIFT_TEST_CALLS"\n')
    uv.chmod(0o755)
    env = {
        **os.environ,
        "PATH": str(tmp_path / "bin") + os.pathsep + os.environ["PATH"],
        "SPIRESHIFT_TEST_CALLS": str(log),
    }
    resources = tmp_path / "artifacts/resources"
    resources.mkdir(parents=True)
    (resources / "combat-foundation-base-v2-audit-v1-attempt-1.json").write_text("{}")
    subprocess.run(
        ["bash", str(tmp_path / "scripts/audit.sh")], env=env, check=True, capture_output=True
    )
    calls = log.read_text()
    assert "attempt-2.json" in calls and "--max-wall-seconds 600" in calls
    assert "--kind other" in calls and "train-curriculum" not in calls
    out = tmp_path / "artifacts/combat-foundation/sts2-v0.107.1-base-v2-audit-v1"
    out.mkdir(parents=True)
    (out / "combat-foundation-audit.json").write_text("{}")
    log.write_text("")
    subprocess.run(
        ["bash", str(tmp_path / "scripts/audit.sh")], env=env, check=True, capture_output=True
    )
    assert "show-combat-foundation" in log.read_text() and "resources run" not in log.read_text()
