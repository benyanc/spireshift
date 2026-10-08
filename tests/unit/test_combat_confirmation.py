from __future__ import annotations

import copy
import json
import os
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Self, cast

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.agents.learned import ProductionCheckpointPolicy
from spireshift.cli import main
from spireshift.combat_confirmation import (
    CombatConfirmationConfig,
    load_combat_confirmation_config,
    load_confirmation_policies,
)
from spireshift.core.manifest import manifest_identifier
from spireshift.core.objective import ObjectiveSpec
from spireshift.core.types import DecisionType, LegalAction, Observation, Transition
from spireshift.production_evaluation import (
    _evaluate_case,
    load_production_policy_evaluation,
    run_production_policy_evaluation,
)
from spireshift.resource_tracking import EXPERIMENT_METRICS_ENV
from spireshift.splits import SplitName, load_split_manifest

CONFIG = Path("configs/combat-confirmation/sts2-v0.107.1-base-v10-fresh-train-v1.json")
SPLIT = load_split_manifest(Path("manifests/splits/mock-v1-seeds-000000-000999-v1.json"))
RULESET = MockSpireEnvironment.ruleset


def identified(d: dict[str, Any], field: str) -> dict[str, Any]:
    return {**d, field: manifest_identifier({k: v for k, v in d.items() if k != field})}


def recipe(*, budget: int = 128) -> CombatConfirmationConfig:
    d = copy.deepcopy(load_combat_confirmation_config(CONFIG).document)
    d.update(
        patch_id=RULESET.patch_id,
        ruleset_manifest_id=RULESET.manifest_id,
        split_manifest_id=SPLIT.manifest_id,
        seeds=list(SPLIT.seeds(SplitName.TRAIN)[:2]),
        run_offset=0,
        prior_train_prefix_stop=0,
        maximum_decisions_per_run=8,
    )
    d["objective"]["whole_run_budget"] = budget
    return CombatConfirmationConfig.from_mapping(identified(d, "config_id"))


class TinyEnvironment:
    ruleset = RULESET
    patch_id = RULESET.patch_id

    def __init__(self) -> None:
        self.phase = 0

    def observation(self) -> Observation:
        state = {
            "act": "hive" if self.phase == 2 else "underdocks",
            "floor": 17 if self.phase == 1 else 1,
            "terminal": self.phase == 2,
            "victory": self.phase == 2,
        }
        return Observation(
            "observation-v1",
            RULESET.patch_id,
            DecisionType.COMBAT if self.phase == 1 else DecisionType.PATH,
            state,
            manifest_identifier(state)[7:],
        )

    def reset(self, seed: int) -> Observation:
        self.phase = 0
        return self.observation()

    def legal_actions(self) -> tuple[LegalAction, ...]:
        return () if self.phase == 2 else (LegalAction("advance", "advance", {}),)

    def step(self, action: LegalAction) -> Transition:
        before = self.observation()
        self.phase += 1
        return Transition(
            before,
            action,
            self.observation(),
            float(self.phase == 2),
            self.phase == 2,
            self.phase == 2,
        )

    def clone(self, *, resample_hidden: bool, seed: int | None = None) -> Self:
        return copy.deepcopy(self)

    def close(self) -> None:
        pass


@dataclass
class ToyPolicy:
    model_id: str
    split_manifest_id: str = SPLIT.manifest_id
    ruleset: Any = RULESET
    fail_combat: bool = False
    policy_id: str = field(init=False)

    def __post_init__(self) -> None:
        self.policy_id = "production-checkpoint-policy-v1:" + self.model_id

    def choose_action(
        self, observation: Observation, legal_actions: Sequence[LegalAction]
    ) -> LegalAction:
        if self.fail_combat and observation.decision_type is DecisionType.COMBAT:
            raise ValueError("Unsupported public combat selection kind 99")
        return legal_actions[0]


def policies(
    config: CombatConfirmationConfig,
) -> tuple[ProductionCheckpointPolicy, ProductionCheckpointPolicy]:
    return (
        cast(ProductionCheckpointPolicy, ToyPolicy(config.document["candidate"]["model_id"])),
        cast(ProductionCheckpointPolicy, ToyPolicy(config.document["reference"]["model_id"])),
    )


def run(config: CombatConfirmationConfig, output: Path, **kwargs: Any) -> Any:
    candidate, reference = policies(config)
    args = dict(
        environment_factory=TinyEnvironment,
        ruleset=RULESET,
        learned_policy=candidate,
        split_manifest=SPLIT,
        training_report_id=config.document["candidate"]["report_id"],
        reference_policy=reference,
        reference_training_report_id=config.document["reference"]["report_id"],
        seeds=config.document["seeds"],
        workers=1,
        maximum_decisions_per_run=8,
        partition=SplitName.TRAIN,
        output_directory=output,
        confirmation=config,
    )
    args.update(kwargs)
    return run_production_policy_evaluation(**args)


def verify(config: CombatConfirmationConfig, path: Path) -> dict[str, Any]:
    return load_production_policy_evaluation(
        path,
        model_id=config.document["candidate"]["model_id"],
        training_report_id=config.document["candidate"]["report_id"],
        split_manifest=SPLIT,
        reference_model_id=config.document["reference"]["model_id"],
        reference_training_report_id=config.document["reference"]["report_id"],
    )


def test_fresh_pairing_preserves_frozen_plan_and_all_outcome_denominators(tmp_path: Path) -> None:
    config = recipe()
    progress: list[tuple[int, int]] = []
    result = run(config, tmp_path / "comparison", progress=lambda a, b: progress.append((a, b)))
    assert result.new_runs == 4 and result.new_transitions == 8
    assert progress == [(1, 4), (2, 4), (3, 4), (4, 4)]
    assert (
        result.report["partition"] == "train"
        and "fresh_train_development" in result.report["claim_scope"]
    )
    assert verify(config, result.report_path) == result.report
    assert result.report["summary"]["candidate"]["victories"] == 2
    assert result.report["summary"]["candidate"]["act1_boss_reaches"] == 2
    assert result.report["summary"]["candidate"]["act1_clears"] == 2
    assert result.report["summary"]["paired"]["benchmark_denominator"] == 2
    assert result.report["decision"]["checkpoint_promoted"] is False


@pytest.mark.parametrize(
    "wrong",
    ["unfrozen_train", "worker_overlap", "different_seeds", "validation_scope", "mutated_plan"],
)
def test_unfrozen_or_changed_confirmation_stops_before_any_game(tmp_path: Path, wrong: str) -> None:
    def forbidden() -> None:
        pytest.fail("A changed confirmation may not initialize a game")

    config = recipe()
    override: dict[str, Any] = {"environment_factory": forbidden}
    if wrong == "unfrozen_train":
        override["confirmation"] = None
    elif wrong == "worker_overlap":
        override["workers"] = 2
    elif wrong == "different_seeds":
        override["seeds"] = SPLIT.seeds(SplitName.TRAIN)[2:4]
    elif wrong == "validation_scope":
        override["partition"] = SplitName.VALIDATION
    else:
        config.document["seeds"][0] += 1
    with pytest.raises(ValueError):
        run(config, tmp_path / "invalid", **override)


def test_unsupported_combat_is_counted_and_partial_work_is_retained(tmp_path: Path) -> None:
    config = recipe()
    candidate, _ = policies(config)
    cast(Any, candidate).fail_combat = True
    result = run(config, tmp_path / "failed", learned_policy=candidate)
    arm = result.report["summary"]["candidate"]
    assert not result.successful and arm["benchmark_denominator"] == 2
    assert arm["failed_runs"] == arm["unsupported_public_combat_runs"] == 2
    assert arm["completed_transitions"] == 2 and arm["attempted_decisions"] == 4
    assert result.new_transitions == 6
    assert result.report["summary"]["paired"]["all_seed_reference_only_victories"] == 2
    assert (
        arm["victory_rate_interval_95"][1] > 0
    )  # All losses do not imply certain zero probability.
    assert verify(config, result.report_path) == result.report


@pytest.mark.parametrize("where", ["policy", "terminal_transition"])
def test_cpu_cap_stops_actions_and_cannot_count_a_late_terminal_win(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    where: str,
) -> None:
    config = recipe(budget=10)
    clock = [0.0]
    monkeypatch.setattr("spireshift.production_evaluation.time.process_time", lambda: clock[0])

    class TimedEnvironment(TinyEnvironment):
        def reset(self, seed: int) -> Observation:
            clock[0] += 100  # Mandatory startup is recorded separately.
            return super().reset(seed)

        def step(self, action: LegalAction) -> Transition:
            if where == "terminal_transition":
                clock[0] += 7
            return super().step(action)

    class TimedPolicy(ToyPolicy):
        def choose_action(
            self, observation: Observation, legal_actions: Sequence[LegalAction]
        ) -> LegalAction:
            if where == "policy":
                clock[0] += 20
            return super().choose_action(observation, legal_actions)

    case = _evaluate_case(
        environment_factory=TimedEnvironment,
        ruleset=RULESET,
        seed=config.document["seeds"][0],
        policy_kind="production_checkpoint",
        policy=TimedPolicy(config.document["candidate"]["model_id"]),
        model_id=config.document["candidate"]["model_id"],
        maximum_decisions=8,
        partition=SplitName.TRAIN,
        cycle_repetition_threshold=8,
        liveness_tail_length=16,
        no_op_fallback_threshold=2,
        schema_version="production-policy-evaluation-case-v5",
        confirmation=config,
    )
    assert case["truncated"] and not case["victory"] and not case["terminal"]
    assert case["termination_reason"] == "cpu_budget"
    assert case["compute"]["initialization_cpu_seconds"] == 100
    assert case["compute"]["budget_exhausted"] is True
    assert case["activity"]["completed_transitions"] == (0 if where == "policy" else 2)
    assert case["compute"]["observed_victory"] is (where == "terminal_transition")
    from spireshift.production_evaluation import _validate_fresh_case

    _validate_fresh_case(case, config)


def test_resume_preserves_saved_failures_and_never_replays_completed_cases(tmp_path: Path) -> None:
    config = recipe()
    candidate, _ = policies(config)
    cast(Any, candidate).fail_combat = True
    result = run(config, tmp_path / "resume", learned_policy=candidate)
    saved_cases = {p: p.read_bytes() for p in (result.report_path.parent / "cases").glob("*.json")}
    # Simulate interruption after all cases but before final report publication.
    result.report_path.unlink()

    def forbidden() -> None:
        pytest.fail("Resuming saved cases must not run another game")

    resumed = run(config, result.report_path.parent, environment_factory=forbidden, resume=True)
    assert resumed.new_runs == resumed.new_transitions == 0
    assert all(p.read_bytes() == original for p, original in saved_cases.items())
    assert verify(config, resumed.report_path) == resumed.report
    assert resumed.report["summary"]["candidate"]["failed_runs"] == 2


def test_interrupted_job_records_completed_work_and_resumes_only_missing_pairs(
    tmp_path: Path,
) -> None:
    config = recipe()
    activity: list[tuple[int, int]] = []

    def stop_after_first_saved_case(completed: int, total: int) -> None:
        raise KeyboardInterrupt

    output = tmp_path / "partial"
    with pytest.raises(KeyboardInterrupt):
        run(
            config,
            output,
            record_activity=lambda a, b: activity.append((a, b)),
            progress=stop_after_first_saved_case,
        )
    assert activity == [(1, 2)] and not (output / "production-policy-evaluation.json").exists()
    original = next((output / "cases").glob("*.json"))
    original_bytes = original.read_bytes()
    activity.clear()
    resumed = run(config, output, resume=True, record_activity=lambda a, b: activity.append((a, b)))
    assert resumed.new_runs == 3 and resumed.new_transitions == 6
    assert activity == [(1, 2), (2, 4), (3, 6)]
    assert original.read_bytes() == original_bytes
    assert verify(config, resumed.report_path) == resumed.report


@pytest.mark.parametrize("wrong", [None, "eligibility", "resource_cap", "freshness", "parent"])
def test_saved_training_and_freshness_preflight_blocks_bad_inputs_without_games(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    wrong: str | None,
) -> None:
    import spireshift.combat_confirmation as module

    config = recipe()
    d = config.document
    foundation = {
        "model_id": d["reference"]["model_id"],
        "training_report_id": d["reference"]["report_id"],
        "parent_checkpoint": d["reference"]["checkpoint_path"],
        "parent_report": d["reference"]["report_path"],
        "objective": d["objective"],
    }
    training = {
        "config_id": d["training_config_id"],
        "fresh_confirmation": {
            "seeds": d["seeds"],
            "run_offset": 0,
            "prior_train_prefix_stop": 0,
            "max_decisions_per_run": 8,
        },
    }
    inventory = {
        "kind": "saved",
        "path": "prior.json",
        "source_id": "sha256:" + "0" * 64,
        "complete_run_seeds": [999],
    }
    report = {
        "report_id": d["candidate"]["report_id"],
        "config": training,
        "candidate_eligible": wrong != "eligibility",
        "status": "requires_fresh_confirmation",
        "seed_verification": {
            "disjoint": True,
            "fresh_seeds": d["seeds"],
            "prior_inventories": [inventory],
        },
    }
    resource = {
        "report_id": d["candidate"]["resource_report_id"],
        "status": "completed",
        "exit_code": 0,
        "cap": None if wrong != "resource_cap" else "wall_seconds",
        "experiment_kind": "training",
        "usage": {"trajectories": 0, "simulations": 0, "transitions": 0},
    }
    if wrong == "parent":
        foundation["model_id"] = "sha256:" + "0" * 64
    monkeypatch.setattr(
        module,
        "load_combat_policy_config",
        lambda _: SimpleNamespace(
            document=training, foundation=SimpleNamespace(document=foundation)
        ),
    )
    monkeypatch.setattr(
        module,
        "load_production_model_checkpoint",
        lambda path: {
            "model_id": d["candidate" if "base-v10" in str(path) else "reference"]["model_id"]
        },
    )
    monkeypatch.setattr(
        module,
        "load_production_training_report",
        lambda path, **kw: (
            report if "base-v10" in str(path) else {"report_id": d["reference"]["report_id"]}
        ),
    )
    monkeypatch.setattr(module, "load_resource_report", lambda _: resource)
    monkeypatch.setattr(
        module,
        "_prior_inventory",
        lambda *args: {
            **inventory,
            "complete_run_seeds": d["seeds"] if wrong == "freshness" else [999],
        },
    )
    monkeypatch.setattr(
        module,
        "ProductionCheckpointPolicy",
        lambda checkpoint, **kw: ToyPolicy(checkpoint["model_id"]),
    )
    args: dict[str, Any] = dict(
        config=config,
        project_root=tmp_path,
        split=SPLIT,
        ruleset=RULESET,
        objective=ObjectiveSpec.from_mapping(d["objective"]),
    )
    if wrong is None:
        assert load_confirmation_policies(**args)[0].model_id == d["candidate"]["model_id"]
    else:
        with pytest.raises(ValueError):
            load_confirmation_policies(**args)


@pytest.mark.parametrize("wrong", ["cap", "missing_case", "changed_summary", "promotion"])
def test_reidentified_artifact_tampering_is_rejected(tmp_path: Path, wrong: str) -> None:
    config = recipe()
    result = run(config, tmp_path / "tampered")
    report = copy.deepcopy(result.report)
    if wrong == "cap":
        reference = report["cases"][0]
        path = result.report_path.parent / reference["path"]
        case = json.loads(path.read_text())
        case["compute"]["cpu_budget_seconds"] += 1
        case = identified(case, "case_id")
        path.write_text(json.dumps(case))
        reference["case_id"] = case["case_id"]
    elif wrong == "missing_case":
        report["cases"].pop()
    elif wrong == "changed_summary":
        report["summary"]["candidate"]["victories"] += 1
    else:
        report["decision"]["checkpoint_promoted"] = True
    result.report_path.write_text(json.dumps(identified(report, "report_id")))
    with pytest.raises(ValueError):
        verify(config, result.report_path)


def test_cached_cli_never_loads_backend_or_launches_training(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = recipe()
    result = run(config, tmp_path / "cached")
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config.document))
    monkeypatch.setattr(
        "spireshift.combat_confirmation.load_confirmation_policies", lambda **kw: policies(config)
    )

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Displaying a saved comparison must not initialize a backend or train")

    monkeypatch.setattr("spireshift.cli.load_evangambit_backend", forbidden)
    assert (
        main(
            [
                "model",
                "show-combat-confirmation",
                str(path),
                "--split-manifest",
                "manifests/splits/mock-v1-seeds-000000-000999-v1.json",
                "--manifest",
                "manifests/patches/mock-v1.json",
                "--output-dir",
                str(result.report_path.parent),
            ]
        )
        == 0
    )
    assert '"games_this_command": 0' in capsys.readouterr().out


@pytest.mark.parametrize("bad_preflight", [False, True])
def test_owner_cli_records_only_actual_new_game_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bad_preflight: bool,
) -> None:
    config = recipe()
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config.document))
    metrics = tmp_path / "metrics.json"
    monkeypatch.setenv(EXPERIMENT_METRICS_ENV, str(metrics))
    backend_loads: list[bool] = []

    def saved_policies(
        **kwargs: Any,
    ) -> tuple[ProductionCheckpointPolicy, ProductionCheckpointPolicy]:
        if bad_preflight:
            raise ValueError("Candidate is not eligible")
        return policies(config)

    def tiny_backend(*args: Any, **kwargs: Any) -> SimpleNamespace:
        backend_loads.append(True)
        return SimpleNamespace(factory=TinyEnvironment)

    monkeypatch.setattr("spireshift.combat_confirmation.load_confirmation_policies", saved_policies)
    monkeypatch.setattr("spireshift.cli.load_evangambit_backend", tiny_backend)
    exit_code = main(
        [
            "model",
            "confirm-combat-policy",
            str(path),
            "--split-manifest",
            "manifests/splits/mock-v1-seeds-000000-000999-v1.json",
            "--manifest",
            "manifests/patches/mock-v1.json",
            "--upstream-root",
            str(tmp_path / "unused_backend"),
            "--output-dir",
            str(tmp_path / "owner"),
        ]
    )
    saved = json.loads(metrics.read_text())
    assert exit_code == int(bad_preflight)
    assert saved["trajectories"] == (0 if bad_preflight else 4)
    assert saved["transitions"] == (0 if bad_preflight else 8)
    assert saved["simulations"] == 0
    assert backend_loads == ([] if bad_preflight else [True])


def test_owner_script_rotates_resource_attempts_and_displays_saved_result_only(
    tmp_path: Path,
) -> None:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "bin").mkdir()
    script = tmp_path / "scripts/test.sh"
    script.write_text(Path("scripts/confirm-combat-policy-v1.sh").read_text())
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
    (resources / "combat-policy-base-v10-confirmation-v1-attempt-1.json").write_text("{}")
    subprocess.run(["bash", str(script)], env=env, capture_output=True, check=True)
    calls = log.read_text()
    assert (
        "attempt-2.json" in calls and "--workers 1" in calls and "--max-wall-seconds 1800" in calls
    )
    assert "confirm-combat-policy" in calls and "--resume" in calls and "train-combat" not in calls
    output = tmp_path / "artifacts/evaluations/sts2-v0.107.1-base-v10-fresh-train-v1"
    output.mkdir(parents=True)
    (output / "production-policy-evaluation.json").write_text("{}")
    log.write_text("")
    subprocess.run(["bash", str(script)], env=env, capture_output=True, check=True)
    assert "show-combat-confirmation" in log.read_text() and "resources run" not in log.read_text()


def test_strict_confirmation_schemas_accept_frozen_plan_and_mock_evidence(tmp_path: Path) -> None:
    registry: Registry[Any] = Registry().with_resources(
        [
            (
                f"https://spireshift.dev/schemas/{p.name}",
                Resource.from_contents(json.loads(p.read_text())),
            )
            for p in Path("schemas").glob("*.json")
        ]
    )
    config = recipe()
    result = run(config, tmp_path / "schema")
    documents = [
        ("combat-policy-confirmation-config-v1", config.document),
        ("combat-policy-confirmation-config-v1", load_combat_confirmation_config(CONFIG).document),
        ("production-policy-evaluation-v5", result.report),
    ]
    documents += [
        ("production-policy-evaluation-case-v5", json.loads(p.read_text()))
        for p in (result.report_path.parent / "cases").glob("*.json")
    ]
    for name, value in documents:
        Draft202012Validator(
            json.loads(Path(f"schemas/{name}.json").read_text()), registry=registry
        ).validate(value)
