from __future__ import annotations

import copy
import json
import os
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Self, cast

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.agents.learned import ProductionCheckpointPolicy, ProductionPolicyDecision
from spireshift.cli import main
from spireshift.combat_confirmation import CombatConfirmationConfig, load_combat_confirmation_config
from spireshift.combat_features import TRANSFORM_LAYOUT_SCHEMA, CombatLayout
from spireshift.combat_replay_diagnostic import (
    KINDS,
    CombatReplayConfig,
    CombatReplayInputs,
    load_combat_replay_config,
    load_combat_replay_report,
    prepare_combat_replay,
    run_combat_replay,
)
from spireshift.core.manifest import manifest_identifier
from spireshift.core.objective import ObjectiveSpec
from spireshift.core.protocols import EnvironmentAdapter
from spireshift.core.types import DecisionType, LegalAction, Observation, Transition
from spireshift.production_evaluation import run_production_policy_evaluation
from spireshift.resource_tracking import EXPERIMENT_METRICS_ENV
from spireshift.splits import SplitName, load_split_manifest

CONFIG = Path("configs/combat-replay-diagnostic/sts2-v0.107.1-base-v10-confirmation-v1.json")
CONFIRMATION = Path("configs/combat-confirmation/sts2-v0.107.1-base-v10-fresh-train-v1.json")
SPLIT = load_split_manifest(Path("manifests/splits/mock-v1-seeds-000000-000999-v1.json"))
RULESET = MockSpireEnvironment.ruleset


def identified(d: dict[str, Any], field: str) -> dict[str, Any]:
    return {**d, field: manifest_identifier({k: v for k, v in d.items() if k != field})}


class TinyCombat:
    ruleset = RULESET
    patch_id = RULESET.patch_id

    def __init__(self, *, changed: bool = False, fail_step: bool = False) -> None:
        self.phase = 0
        self.changed, self.fail_step = changed, fail_step

    def observation(self) -> Observation:
        v = [0] * 682
        hp = 0 if self.phase == 2 else 20
        v[:8] = [hp, 40, 0, 3 if self.phase == 0 else 0, 3, 8, 2, 0]
        v[8:16] = [17, 0, 0, 0, 45, 1, 2, 3]
        v[80:87] = [10, 20, 0, 0, 6, 0, 3]
        state = {
            "observation_vector": v,
            "player_hp": hp,
            "player_max_hp": 40,
            "enemy_def_ids": [7],
            "potions": [0] * 6,
            "act": "underdocks",
            "floor": 3 if self.changed else 2,
            "terminal": self.phase == 2,
            "victory": False,
        }
        return Observation(
            "observation-v1",
            RULESET.patch_id,
            DecisionType.TERMINAL if self.phase == 2 else DecisionType.COMBAT,
            state,
            manifest_identifier(state)[7:],
        )

    def reset(self, seed: int) -> Observation:
        self.phase = 0
        return self.observation()

    def legal_actions(self) -> tuple[LegalAction, ...]:
        if self.phase == 2:
            return ()
        indices = (0, 1, 2) if self.phase == 0 else (2,)
        return tuple(
            LegalAction(
                f"action-{i}",
                "evangambit_combat",
                {
                    "phase": "combat",
                    "action_index": i,
                    **({"target_index": 0} if i == 0 else {}),
                },
            )
            for i in indices
        )

    def step(self, action: LegalAction) -> Transition:
        before = self.observation()
        if self.fail_step:
            raise RuntimeError("Synthetic step failure")
        self.phase = 2 if action.payload["action_index"] == 2 else 1
        return Transition(before, action, self.observation(), 0, self.phase == 2, False)

    def clone(self, *, resample_hidden: bool, seed: int | None = None) -> Self:
        pytest.fail("Diagnosis must not clone or resample an engine")

    def close(self) -> None:
        pass


@dataclass
class ToyPolicy:
    model_id: str
    candidate: bool
    fail_shadow: bool = False
    split_manifest_id: str = SPLIT.manifest_id
    ruleset: Any = RULESET
    policy_id: str = field(init=False)

    def __post_init__(self) -> None:
        self.policy_id = "production-checkpoint-policy-v1:" + self.model_id

    def predict(self, obs: Observation, actions: Sequence[LegalAction]) -> ProductionPolicyDecision:
        # Failure is installed only after generating a valid source comparison.
        if self.fail_shadow:
            raise ValueError("Synthetic unsupported shadow")
        index = 0 if self.candidate else len(actions) - 1
        values = (
            (1.0,)
            if len(actions) == 1
            else tuple(0.8 if i == index else 0.2 / (len(actions) - 1) for i in range(len(actions)))
        )
        return ProductionPolicyDecision(
            "",
            tuple(a.action_id for a in actions),
            index,
            actions[index],
            values,
            None,
            (),
            {},
            0,
        )

    def choose_action(self, obs: Observation, actions: Sequence[LegalAction]) -> LegalAction:
        return self.predict(obs, actions).selected_action


def inputs(
    tmp_path: Path, environment_factory: Callable[[], EnvironmentAdapter] = TinyCombat
) -> CombatReplayInputs:
    confirmation = copy.deepcopy(load_combat_confirmation_config(CONFIRMATION).document)
    confirmation.update(
        patch_id=RULESET.patch_id,
        ruleset_manifest_id=RULESET.manifest_id,
        split_manifest_id=SPLIT.manifest_id,
        seeds=list(SPLIT.seeds(SplitName.TRAIN)[:2]),
        run_offset=0,
        prior_train_prefix_stop=0,
        maximum_decisions_per_run=8,
    )
    frozen = CombatConfirmationConfig.from_mapping(identified(confirmation, "config_id"))
    candidate = cast(
        ProductionCheckpointPolicy, ToyPolicy(frozen.document["candidate"]["model_id"], True)
    )
    reference = cast(
        ProductionCheckpointPolicy, ToyPolicy(frozen.document["reference"]["model_id"], False)
    )
    source = run_production_policy_evaluation(
        environment_factory=environment_factory,
        ruleset=RULESET,
        learned_policy=candidate,
        reference_policy=reference,
        split_manifest=SPLIT,
        training_report_id=frozen.document["candidate"]["report_id"],
        reference_training_report_id=frozen.document["reference"]["report_id"],
        seeds=frozen.document["seeds"],
        workers=1,
        maximum_decisions_per_run=8,
        output_directory=tmp_path / "comparison",
        partition=SplitName.TRAIN,
        confirmation=frozen,
    )
    config = copy.deepcopy(load_combat_replay_config(CONFIG).document)
    config.update(
        confirmation_config_id=frozen.document["config_id"],
        comparison_report_id=source.report["report_id"],
    )
    cases = {}
    for entry in source.report["cases"]:
        case = json.loads((source.report_path.parent / entry["path"]).read_text())
        cases[entry["seed"], entry["policy_kind"]] = case
    return CombatReplayInputs(
        CombatReplayConfig.from_mapping(identified(config, "config_id")),
        frozen,
        RULESET,
        candidate,
        reference,
        source.report,
        cases,
        {
            "foundation_report_id": "sha256:" + "a" * 64,
            "fitting_card_ids": [17],
            "signal_card_ids": [17],
        },
        CombatLayout(RULESET.patch_id, RULESET.manifest_id, TRANSFORM_LAYOUT_SCHEMA),
    )


def run(data: CombatReplayInputs, output: Path, **kwargs: Any) -> dict[str, Any]:
    args: dict[str, Any] = dict(
        inputs=data, environment_factory=TinyCombat, output_directory=output
    )
    args.update(kwargs)
    return run_combat_replay(**args)


def test_public_replay_matches_source_and_records_choices_before_death(tmp_path: Path) -> None:
    data = inputs(tmp_path)
    activity: list[tuple[int, int]] = []
    progress: list[tuple[int, int]] = []
    report = run(
        data,
        tmp_path / "diagnosis",
        activity=lambda a, b: activity.append((a, b)),
        progress=lambda a, b: progress.append((a, b)),
    )
    assert activity == [(1, 2), (2, 3), (3, 5), (4, 6)]
    assert progress == [(1, 4), (2, 4), (3, 4), (4, 4)]
    assert report["summary"]["verified_replays"] == 4
    assert report["summary"]["case_denominator"] == 4
    assert report["summary"]["analysis_integrity_pass"]
    arms = report["summary"]["arms"]
    assert arms[KINDS[0]]["end_turn_with_legal_card_or_potion_states"] == 0
    assert arms[KINDS[1]]["end_turn_with_legal_card_or_potion_states"] == 2
    assert arms[KINDS[0]]["states_with_cards_absent_from_fit"] == 2
    assert arms[KINDS[1]]["terminal_defeats_after_end_turn"] == 2
    for pair in report["summary"]["pairs"]:
        assert pair["first_difference"]["kind"] == "aligned_policy_action_difference"
        assert pair["first_difference"]["decision_index"] == 0
        assert pair["reference_death_evidence"]["last_transition_hp_change"] == -20
        assert pair["candidate_death_evidence"]["last_combat_decision_indices"] == [0, 1]
    assert report["decision"]["checkpoint_promoted"] is False
    assert report["decision"]["adaptive_controller_allowed"] is False
    for path in (tmp_path / "diagnosis/cases").glob("*.json"):
        assert len(path.read_text().splitlines()) == 1
    assert load_combat_replay_report(tmp_path / "diagnosis/diagnostic.json", data) == report


@pytest.mark.parametrize("where", ["policy", "transition"])
def test_cpu_capped_replays_retain_partial_work_without_counting_a_win(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, where: str
) -> None:
    data = inputs(tmp_path)
    clock = [0.0]
    monkeypatch.setattr("spireshift.production_evaluation.time.process_time", lambda: clock[0])
    if where == "policy":
        predict = data.candidate.predict

        def timed(obs: Observation, actions: Sequence[LegalAction]) -> ProductionPolicyDecision:
            clock[0] += 200
            return predict(obs, actions)

        monkeypatch.setattr(data.candidate, "predict", timed)

    class TimedCombat(TinyCombat):
        def step(self, action: LegalAction) -> Transition:
            clock[0] += 200
            return super().step(action)

    activity: list[tuple[int, int]] = []
    report = run(
        data,
        tmp_path / "diagnosis",
        environment_factory=TinyCombat if where == "policy" else TimedCombat,
        activity=lambda a, b: activity.append((a, b)),
    )
    assert activity[-1] == (4, 0 if where == "policy" else 4)
    assert report["summary"]["case_denominator"] == report["summary"]["mismatched_replays"] == 4
    assert report["summary"]["failed_replays"] == 0
    assert not report["summary"]["analysis_integrity_pass"]
    for path in (tmp_path / "diagnosis/cases").glob("*.json"):
        case = json.loads(path.read_text())
        assert case["replay_result"]["compute"]["budget_exhausted"]
        assert case["replay_result"]["truncated"] and not case["replay_result"]["victory"]
        assert len(case["rows"]) == 1
        assert (case["rows"][0]["transition"] is None) == (where == "policy")
    assert load_combat_replay_report(tmp_path / "diagnosis/diagnostic.json", data) == report


def test_noncombat_changes_cannot_pass_a_combat_only_diagnosis(tmp_path: Path) -> None:
    class PathPrelude(TinyCombat):
        def reset(self, seed: int) -> Observation:
            self.phase = -1
            return self.observation()

        def observation(self) -> Observation:
            if self.phase != -1:
                return super().observation()
            state = {"floor": 1, "act": "underdocks", "terminal": False, "victory": False}
            return Observation(
                "observation-v1",
                RULESET.patch_id,
                DecisionType.PATH,
                state,
                manifest_identifier(state)[7:],
            )

        def legal_actions(self) -> tuple[LegalAction, ...]:
            if self.phase != -1:
                return super().legal_actions()
            return tuple(
                LegalAction(f"path-{i}", "evangambit_path", {"phase": "path", "action_index": i})
                for i in range(2)
            )

        def step(self, action: LegalAction) -> Transition:
            if self.phase != -1:
                return super().step(action)
            before = self.observation()
            self.phase = 0
            return Transition(before, action, self.observation(), 0, False, False)

    data = inputs(tmp_path, PathPrelude)
    report = run(data, tmp_path / "diagnosis", environment_factory=PathPrelude)
    assert report["summary"]["verified_replays"] == 4
    assert not report["summary"]["analysis_integrity_pass"]
    assert all(a["noncombat_score_drift_states"] == 2 for a in report["summary"]["arms"].values())


@pytest.mark.parametrize("bad", [None, "resource_failed", "wrong_work", "wrong_coverage"])
def test_saved_input_preflight_requires_exact_completed_comparison_and_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad: str | None
) -> None:
    data = inputs(tmp_path)
    config = copy.deepcopy(data.config.document)
    config.update(
        confirmation_config_path="confirmation.json",
        comparison_path="comparison/production-policy-evaluation.json",
    )
    frozen = CombatReplayConfig.from_mapping(identified(config, "config_id"))
    (tmp_path / "confirmation.json").write_text(json.dumps(data.confirmation.document))
    resource = {
        "report_id": config["comparison_resource_report_id"],
        "status": "completed",
        "exit_code": 0,
        "cap": None,
        "experiment_kind": "rollout",
        "usage": {"trajectories": 4, "simulations": 0, "transitions": 6},
    }
    if bad == "resource_failed":
        resource["status"] = "failed"
    elif bad == "wrong_work":
        resource["usage"]["trajectories"] = 3
    monkeypatch.setattr(
        "spireshift.combat_replay_diagnostic.load_resource_report", lambda p: resource
    )
    monkeypatch.setattr(
        "spireshift.combat_replay_diagnostic.load_confirmation_policies",
        lambda **kw: (data.candidate, data.reference),
    )
    recipe = SimpleNamespace(
        document={
            "foundation_report_path": "audit.json",
            "foundation_report_id": data.coverage["foundation_report_id"],
            "residual_layout": data.layout.as_dict(),
        },
        foundation=object(),
    )
    audit = {
        "report_id": "sha256:" + "b" * 64
        if bad == "wrong_coverage"
        else data.coverage["foundation_report_id"],
        "summary": {"by_subfold": {"fit": {"card_ids": [17], "signal_card_ids": [17]}}},
    }
    monkeypatch.setattr(
        "spireshift.combat_replay_diagnostic.load_combat_policy_config", lambda p: recipe
    )
    monkeypatch.setattr(
        "spireshift.combat_replay_diagnostic.load_combat_foundation_report", lambda *args: audit
    )
    kwargs: dict[str, Any] = dict(
        config=frozen,
        project_root=tmp_path,
        split=SPLIT,
        ruleset=RULESET,
        objective=ObjectiveSpec.from_mapping(config["objective"]),
    )
    if bad is None:
        prepared = prepare_combat_replay(**kwargs)
        assert prepared.cases == data.cases and prepared.coverage == data.coverage
    else:
        with pytest.raises(ValueError):
            prepare_combat_replay(**kwargs)


@pytest.mark.parametrize("fault", ["changed_environment", "failed_step", "failed_driver"])
def test_replay_mismatches_and_errors_remain_in_original_denominator(
    tmp_path: Path, fault: str
) -> None:
    data = inputs(tmp_path)
    kwargs: dict[str, Any] = {}
    if fault == "changed_environment":
        kwargs["environment_factory"] = lambda: TinyCombat(changed=True)
    elif fault == "failed_step":
        kwargs["environment_factory"] = lambda: TinyCombat(fail_step=True)
    else:
        cast(ToyPolicy, data.candidate).fail_shadow = True
    report = run(data, tmp_path / "diagnosis", **kwargs)
    assert report["summary"]["case_denominator"] == 4
    assert not report["summary"]["analysis_integrity_pass"]
    assert report["summary"]["mismatched_replays"] == (2 if fault == "failed_driver" else 4)
    assert report["summary"]["failed_replays"] == (
        0 if fault == "changed_environment" else 2 if fault == "failed_driver" else 4
    )
    if fault == "failed_driver":
        arm = report["summary"]["arms"][KINDS[1]]
        assert arm["shadow_failures"] == 2 and arm["verified_replays"] == 2
        assert arm["end_turn_with_legal_card_or_potion_states"] == 2
    assert load_combat_replay_report(tmp_path / "diagnosis/diagnostic.json", data) == report


@pytest.mark.parametrize("change", ["plan", "source_case", "model", "coverage", "confirmation"])
def test_mutated_inputs_stop_before_any_game(tmp_path: Path, change: str) -> None:
    data = inputs(tmp_path)
    if change == "plan":
        data.config.document["objective"]["whole_run_budget"] += 1
    elif change == "source_case":
        data.cases[next(iter(data.cases))]["seed"] += 1
    elif change == "model":
        data = replace(data, candidate=data.reference)
    elif change == "coverage":
        data.coverage["fitting_card_ids"] = [45, 17]
    else:
        data.confirmation.document["seeds"].append(99)

    def forbidden() -> None:
        pytest.fail("Mutated inputs must not create an engine")

    with pytest.raises(ValueError):
        run(data, tmp_path / "diagnosis", environment_factory=forbidden)


def test_safe_resume_only_replays_missing_cases_and_retains_original_bytes(tmp_path: Path) -> None:
    data = inputs(tmp_path)
    output = tmp_path / "diagnosis"

    def interrupt(done: int, total: int) -> None:
        if done == 1:
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run(data, output, progress=interrupt)
    first = next((output / "cases").glob("*.json"))
    saved = first.read_bytes()
    activity: list[tuple[int, int]] = []
    report = run(data, output, resume=True, activity=lambda a, b: activity.append((a, b)))
    assert activity[-1] == (3, 4) and first.read_bytes() == saved
    assert report["summary"]["verified_replays"] == 4
    assert load_combat_replay_report(output / "diagnostic.json", data) == report
    with pytest.raises(FileExistsError):
        run(data, output, resume=True)


def test_saved_failed_replays_are_never_replaced_on_resume(tmp_path: Path) -> None:
    data = inputs(tmp_path)
    output = tmp_path / "diagnosis"
    report = run(data, output, environment_factory=lambda: TinyCombat(fail_step=True))
    saved = {p: p.read_bytes() for p in (output / "cases").glob("*.json")}
    (output / "diagnostic.json").unlink()

    def forbidden() -> None:
        pytest.fail("Resuming failed cases must not replay them")

    activity: list[tuple[int, int]] = []
    resumed = run(
        data,
        output,
        environment_factory=forbidden,
        resume=True,
        activity=lambda a, b: activity.append((a, b)),
    )
    assert activity == [] and resumed == report
    assert all(p.read_bytes() == content for p, content in saved.items())


def test_privileged_observation_is_rejected_before_either_model_predicts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = inputs(tmp_path)

    class PrivateCombat(TinyCombat):
        def observation(self) -> Observation:
            obs = super().observation()
            public = {**obs.public_state, "hidden_rng": [123]}
            return replace(obs, public_state=public, state_hash=manifest_identifier(public)[7:])

    def forbidden(*args: Any) -> None:
        pytest.fail("A model cannot receive privileged state")

    monkeypatch.setattr(data.candidate, "predict", forbidden)
    monkeypatch.setattr(data.reference, "predict", forbidden)
    report = run(data, tmp_path / "diagnosis", environment_factory=PrivateCombat)
    assert report["summary"]["failed_replays"] == report["summary"]["case_denominator"] == 4
    for path in (tmp_path / "diagnosis/cases").glob("*.json"):
        case = json.loads(path.read_text())
        assert case["rows"] == [] and "observation_vector" not in path.read_text()


def test_cli_preflight_failure_records_zero_work_without_loading_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def bad_inputs(**kwargs: Any) -> None:
        raise ValueError("Synthetic changed comparison")

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("An invalid comparison cannot initialize a backend")

    monkeypatch.setattr("spireshift.combat_replay_diagnostic.prepare_combat_replay", bad_inputs)
    monkeypatch.setattr("spireshift.cli.load_evangambit_backend", forbidden)
    metrics = tmp_path / "metrics.json"
    monkeypatch.setenv(EXPERIMENT_METRICS_ENV, str(metrics))
    assert (
        main(
            [
                "model",
                "diagnose-combat-confirmation",
                str(CONFIG),
                "--split-manifest",
                "manifests/splits/mock-v1-seeds-000000-000999-v1.json",
                "--manifest",
                "manifests/patches/mock-v1.json",
                "--upstream-root",
                str(tmp_path / "unused"),
                "--output-dir",
                str(tmp_path / "diagnosis"),
            ]
        )
        == 1
    )
    saved = json.loads(metrics.read_text())
    assert saved["trajectories"] == saved["simulations"] == saved["transitions"] == 0


@pytest.mark.parametrize(
    "tamper",
    ["choice", "score", "binding", "transition", "private", "summary", "promotion", "count"],
)
def test_rehashed_forgery_cannot_change_public_choices_or_result(
    tmp_path: Path, tamper: str
) -> None:
    data = inputs(tmp_path)
    output = tmp_path / "diagnosis"
    report = run(data, output)
    ref = report["cases"][0]
    path = output / ref["path"]
    case = json.loads(path.read_text())
    row = case["rows"][0]
    if tamper == "choice":
        row["executed_action_id"] = "action-2"
    elif tamper == "score":
        row["predictions"][KINDS[0]]["selected_index"] = 2
    elif tamper == "binding":
        row["combat"]["bindings"][0]["card"]["card_id"] = 99
    elif tamper == "transition":
        row["transition"]["action"] = row["legal_actions"][-1]
    elif tamper == "private":
        row["observation"]["public_state"]["hidden_rng"] = [123]
        row["observation"]["state_hash"] = manifest_identifier(row["observation"]["public_state"])[
            7:
        ]
    elif tamper == "count":
        case["replay_result"]["activity"]["completed_transitions"] += 1
        case["replay_result"] = identified(case["replay_result"], "case_id")
    elif tamper == "summary":
        report["summary"]["verified_replays"] = 0
    else:
        report["decision"]["checkpoint_promoted"] = True
    case = identified(case, "case_id")
    path.write_text(json.dumps(case))
    ref["case_id"] = case["case_id"]
    (output / "diagnostic.json").write_text(json.dumps(identified(report, "report_id")))
    with pytest.raises(ValueError):
        load_combat_replay_report(output / "diagnostic.json", data)


@pytest.mark.parametrize("cached", [False, True])
def test_cli_counts_only_new_replay_work_and_cached_display_never_loads_backend(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    cached: bool,
) -> None:
    data = inputs(tmp_path)
    output = tmp_path / "diagnosis"
    if cached:
        run(data, output)

        def forbidden(*args: Any, **kwargs: Any) -> None:
            pytest.fail(
                "Cached display cannot initialize a backend or ask either policy to predict"
            )

        monkeypatch.setattr("spireshift.cli.load_evangambit_backend", forbidden)
        monkeypatch.setattr(data.candidate, "predict", forbidden)
        monkeypatch.setattr(data.reference, "predict", forbidden)
    else:
        monkeypatch.setattr(
            "spireshift.cli.load_evangambit_backend",
            lambda *a, **kw: SimpleNamespace(factory=TinyCombat),
        )
    monkeypatch.setattr(
        "spireshift.combat_replay_diagnostic.prepare_combat_replay", lambda **kw: data
    )
    metrics = tmp_path / "metrics.json"
    monkeypatch.setenv(EXPERIMENT_METRICS_ENV, str(metrics))
    args = [
        "model",
        "show-combat-confirmation-diagnosis" if cached else "diagnose-combat-confirmation",
        str(CONFIG),
        "--split-manifest",
        "manifests/splits/mock-v1-seeds-000000-000999-v1.json",
        "--manifest",
        "manifests/patches/mock-v1.json",
        "--output-dir",
        str(output),
    ]
    if not cached:
        args += ["--upstream-root", str(tmp_path / "unused")]
    assert main(args) == 0
    assert f'"games_this_command": {0 if cached else 4}' in capsys.readouterr().out
    if cached:
        assert not metrics.exists()
    else:
        assert json.loads(metrics.read_text())["trajectories"] == 4
        assert json.loads(metrics.read_text())["transitions"] == 6


def test_owner_script_rotates_attempts_and_shows_cache_without_games(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "bin").mkdir()
    script = tmp_path / "scripts/test.sh"
    script.write_text(Path("scripts/diagnose-combat-confirmation-v1.sh").read_text())
    log = tmp_path / "calls"
    uv = tmp_path / "bin/uv"
    uv.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "$SPIRESHIFT_TEST_CALLS"\n')
    uv.chmod(0o755)
    env = {
        **os.environ,
        "PATH": str(uv.parent) + os.pathsep + os.environ["PATH"],
        "SPIRESHIFT_TEST_CALLS": str(log),
    }
    resources = tmp_path / "artifacts/resources"
    resources.mkdir(parents=True)
    (resources / "combat-confirmation-base-v10-diagnostic-v1-attempt-1-metrics.json").write_text(
        "{}"
    )
    subprocess.run(["bash", str(script)], env=env, capture_output=True, check=True)
    calls = log.read_text()
    assert (
        "attempt-2.json" in calls and "--workers 1" in calls and "--max-wall-seconds 600" in calls
    )
    assert "--max-storage-bytes 250000000" in calls and "--resume" in calls
    assert "diagnose-combat-confirmation" in calls and "train-combat" not in calls
    output = tmp_path / "artifacts/diagnostics/sts2-v0.107.1-base-v10-combat-confirmation-v1"
    output.mkdir(parents=True)
    (output / "diagnostic.json").write_text("{}")
    log.write_text("")
    subprocess.run(["bash", str(script)], env=env, capture_output=True, check=True)
    assert (
        "show-combat-confirmation-diagnosis" in log.read_text()
        and "resources run" not in log.read_text()
    )


def test_strict_schemas_accept_plan_and_synthetic_public_diagnosis(tmp_path: Path) -> None:
    registry: Registry[Any] = Registry().with_resources(
        [
            (
                f"https://spireshift.dev/schemas/{p.name}",
                Resource.from_contents(json.loads(p.read_text())),
            )
            for p in Path("schemas").glob("*.json")
        ]
    )
    data = inputs(tmp_path)
    output = tmp_path / "diagnosis"
    report = run(data, output)
    documents = [
        ("combat-policy-replay-diagnostic-config-v1", load_combat_replay_config(CONFIG).document),
        ("combat-policy-replay-diagnostic-config-v1", data.config.document),
        ("combat-policy-replay-diagnostic-v1", report),
        *[
            ("combat-policy-replay-diagnostic-case-v1", json.loads(p.read_text()))
            for p in (output / "cases").glob("*.json")
        ],
    ]
    for name, document in documents:
        schema = json.loads((Path("schemas") / f"{name}.json").read_text())
        validator = Draft202012Validator(schema, registry=registry)
        assert list(validator.iter_errors(document)) == []
        assert list(validator.iter_errors({**document, "unexpected": True}))
