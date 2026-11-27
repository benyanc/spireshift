from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
from collections.abc import Sequence
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
from spireshift.splits import SplitName, load_split_manifest
from spireshift.starting_evidence import (
    CONFIG_SCHEMA,
    FILENAME,
    StartingEvidenceConfig,
    collect_starting_option_evidence,
    load_starting_evidence_config,
    verify_starting_option_evidence,
)
from spireshift.trajectory_policy import _folds
from spireshift.trajectory_search import (
    Act1Milestones,
    PublicFrontierRanking,
    TrajectorySearchConfig,
)


class _StartingEnvironment:
    ruleset = MockSpireEnvironment.ruleset
    patch_id = MockSpireEnvironment.patch_id
    victory_option: int | None = None

    def __init__(self) -> None:
        self.seed = 0
        self.choice: int | None = None
        self.terminal = False

    def reset(self, seed: int) -> Observation:
        self.seed, self.choice, self.terminal = seed, None, False
        return self.observe()

    def observe(self) -> Observation:
        public: dict[str, Any] = {
            "floor": 1 if self.choice is None else (5, 18, 7)[self.choice],
            "act": "hive" if self.choice == 1 else "overgrowth",
            "player_hp": 80,
            "player_max_hp": 80,
            "gold": 99,
            "deck": [{"card_id": 3, "upgraded": False}],
            "relic_slots": [{"relic_id": 11, "used_up": False}],
            "neow_options": [11, 22, 33],
            "terminal": self.terminal,
            "victory": self.terminal and self.choice == self.victory_option,
        }
        return Observation(
            "observation-v1",
            self.patch_id,
            DecisionType.TERMINAL
            if self.terminal
            else DecisionType.EVENT
            if self.choice is None
            else DecisionType.PATH,
            public,
            hashlib.sha256(
                json.dumps(public, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        )

    def legal_actions(self) -> tuple[LegalAction, ...]:
        if self.terminal:
            return ()
        phase = "ancient" if self.choice is None else "path"
        return tuple(
            LegalAction(
                f"evangambit:{phase}:{i}",
                f"evangambit_{phase}",
                {"action_index": i, "phase": phase},
            )
            for i in range(3 if self.choice is None else 1)
        )

    def step(self, action: LegalAction) -> Transition:
        source = self.observe()
        assert action in self.legal_actions()
        if self.choice is None:
            self.choice = int(action.payload["action_index"])
        else:
            self.terminal = True
        victory = self.terminal and self.choice == self.victory_option
        return Transition(source, action, self.observe(), float(victory), self.terminal, victory)

    def clone(self, *, resample_hidden: bool, seed: int | None = None) -> Self:
        raise AssertionError("Starting collection must never clone or resample hidden state")

    def close(self) -> None:
        pass


class _Policy:
    ruleset = _StartingEnvironment.ruleset
    model_id = manifest_identifier({"model": "starting"})
    policy_id = f"production-checkpoint-policy-v1:{model_id}"

    def __init__(self, split_id: str) -> None:
        self.split_manifest_id = split_id

    def predict(
        self, observation: Observation, legal_actions: Sequence[LegalAction]
    ) -> ProductionPolicyDecision:
        actions = tuple(legal_actions)
        index = 1 if len(actions) == 3 else 0
        return ProductionPolicyDecision(
            manifest_identifier(observation.as_dict()),
            tuple(a.action_id for a in actions),
            index,
            actions[index],
            (0.2, 0.6, 0.2) if len(actions) == 3 else (1.0,),
            None,
            tuple(0.0 for _ in actions),
            {},
            0.0,
        )


@pytest.fixture
def package() -> dict[str, Any]:
    split = load_split_manifest(Path("manifests/splits/mock-v1-seeds-000000-000999-v1.json"))
    policy = _Policy(split.manifest_id)
    runner = TrajectorySearchConfig(
        split_manifest_id=split.manifest_id,
        ruleset_manifest_id=policy.ruleset.manifest_id,
        model_id=policy.model_id,
        training_report_id=manifest_identifier({"report": "starting"}),
        run_offset=0,
        run_count=4,
        generations=1,
        beam_width=3,
        mutations_per_parent=2,
        workers=2,
        maximum_decisions_per_run=8,
        cycle_repetition_threshold=3,
        liveness_tail_length=4,
        no_op_fallback_threshold=2,
        mutation_salt="starting-test",
        milestones=Act1Milestones(("overgrowth", "underdocks"), "hive", 17),
        frontier_ranking=PublicFrontierRanking(
            strategy="public_frontier_v1",
            enemy_hp_offset=80,
            enemy_slot_size=15,
            maximum_enemy_slots=6,
            enemy_snapshot_rule="last_actionable_on_deepest_floor_v2",
        ),
    )
    seeds = set(split.seeds(SplitName.TRAIN)[:4])
    body = {
        "schema_version": CONFIG_SCHEMA,
        "encoder_id": "starting-ancient-public-option-v1",
        "trajectory_config": runner.as_dict(),
        "selection_fraction": 0.25,
        "selection_salt": "trajectory-policy-selection-v1",
        "complete_run_subfolds": _folds(
            seeds, {"selection_fraction": 0.25, "selection_salt": "trajectory-policy-selection-v1"}
        ),
        "minimum_runs": {"fit": 1, "selection": 1, "strong_selection": 1},
    }
    body["config_id"] = manifest_identifier(body)
    return {"split": split, "policy": policy, "config": StartingEvidenceConfig.from_mapping(body)}


def _collect(directory: Path, package: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    return collect_starting_option_evidence(
        environment_factory=kwargs.pop("factory", _StartingEnvironment),
        ruleset=_StartingEnvironment.ruleset,
        policy=cast(ProductionCheckpointPolicy, package["policy"]),
        split_manifest=package["split"],
        training_report_id=package["config"].runner.training_report_id,
        config=package["config"],
        objective=load_objective(Path("configs/default.toml")),
        output_directory=directory,
        **kwargs,
    )


def _verify(directory: Path, package: dict[str, Any]) -> dict[str, Any]:
    return verify_starting_option_evidence(
        directory / FILENAME,
        config=package["config"],
        split_manifest=package["split"],
        ruleset=_StartingEnvironment.ruleset,
    )


def _case(directory: Path, report: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((directory / report["cases"][0]["path"]).read_text()))


def test_exhaustive_pairs_fixed_continuation_and_saved_verification(
    tmp_path: Path,
    package: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _collect(tmp_path / "evidence", package)
    summary = report["summary"]
    assert summary["benchmark_denominator"] == 4
    assert summary["candidate_denominator"] == 12
    assert summary["completed_branches"] == 12
    assert summary["evidence_sufficient"] is True
    assert summary["terminal_victories"] == 0
    case = _case(tmp_path / "evidence", report)
    assert [b["action_id"] for b in case["branches"]] == [
        f"evangambit:ancient:{i}" for i in range(3)
    ]
    assert len(case["comparisons"]) == 3
    assert case["comparisons"][0]["preferred_action_id"] == "evangambit:ancient:1"
    assert case["comparisons"][2]["preferred_action_id"] == "evangambit:ancient:1"
    assert all(
        b["trajectory"]["decisions"][1]["selection_source"] == "base_policy"
        for b in case["branches"]
    )
    monkeypatch.setattr(
        _StartingEnvironment, "reset", lambda *args: pytest.fail("Verifier replayed")
    )
    assert _verify(tmp_path / "evidence", package)["games_replayed"] == 0
    assert report["training_started"] is False and report["checkpoint_promoted"] is False


def test_victory_outranks_longer_losing_run(tmp_path: Path, package: dict[str, Any]) -> None:
    class Winning(_StartingEnvironment):
        victory_option = 2

    report = _collect(tmp_path / "evidence", package, factory=Winning)
    case = _case(tmp_path / "evidence", report)
    pair = case["comparisons"][2]
    assert pair["preferred_action_id"] == "evangambit:ancient:2"
    assert pair["deciding_rank_component"] == "victory"
    assert pair["terminal_victory_difference"] is True
    assert report["summary"]["terminal_victories"] == 4


def test_ties_are_retained_and_fail_sufficiency(tmp_path: Path, package: dict[str, Any]) -> None:
    class Tied(_StartingEnvironment):
        def observe(self) -> Observation:
            observed = super().observe()
            public = {
                **observed.public_state,
                "floor": 1 if self.choice is None else 5,
                "act": "overgrowth",
            }
            return Observation(
                observed.schema_version,
                observed.patch_id,
                observed.decision_type,
                public,
                manifest_identifier(public).removeprefix("sha256:"),
            )

    report = _collect(tmp_path / "evidence", package, factory=Tied)
    assert all(p["label"] == "tied" for p in _case(tmp_path / "evidence", report)["comparisons"])
    assert report["summary"]["complete_run_subfolds"]["fit"]["tied_pairs"] == 9
    assert report["summary"]["evidence_sufficient"] is False
    assert _verify(tmp_path / "evidence", package)["valid"] is True


@pytest.mark.parametrize("baseline_failed", [False, True])
def test_branch_errors_keep_every_run_and_candidate_in_denominator(
    tmp_path: Path,
    package: dict[str, Any],
    baseline_failed: bool,
) -> None:
    class Failed(_StartingEnvironment):
        def step(self, action: LegalAction) -> Transition:
            if self.choice is None and action.payload["action_index"] == (
                1 if baseline_failed else 0
            ):
                raise RuntimeError("deliberate failure")
            return super().step(action)

    report = _collect(tmp_path / "evidence", package, factory=Failed)
    summary = report["summary"]
    assert summary["failed_runs"] == 4 and summary["candidate_denominator"] == 12
    assert summary["failed_or_missing_branches"] == (12 if baseline_failed else 4)
    assert summary["evidence_sufficient"] is False
    assert _case(tmp_path / "evidence", report)["comparisons"] == []
    assert _verify(tmp_path / "evidence", package)["valid"] is True


def test_changed_reset_menu_is_rejected(tmp_path: Path, package: dict[str, Any]) -> None:
    calls = 0

    class Changed(_StartingEnvironment):
        def reset(self, seed: int) -> Observation:
            observed = super().reset(seed)
            public = {**observed.public_state, "gold": 88}
            return Observation(
                observed.schema_version,
                observed.patch_id,
                observed.decision_type,
                public,
                manifest_identifier(public).removeprefix("sha256:"),
            )

    def factory() -> _StartingEnvironment:
        nonlocal calls
        calls += 1
        return _StartingEnvironment() if calls == 1 else Changed()

    # One worker fixes factory ordering for this deliberately unstable reset fixture.
    document = copy.deepcopy(package["config"].document)
    runner = document["trajectory_config"]
    runner["workers"] = 1
    runner["config_id"] = manifest_identifier({k: v for k, v in runner.items() if k != "config_id"})
    document["config_id"] = manifest_identifier(
        {k: v for k, v in document.items() if k != "config_id"}
    )
    package["config"] = StartingEvidenceConfig.from_mapping(document)
    report = _collect(tmp_path / "evidence", package, factory=factory)
    case = _case(tmp_path / "evidence", report)
    assert case["status"] == "failed"
    assert "changed public observation" in case["branches"][1]["error"]


def test_truncated_runs_are_retained_without_labels(
    tmp_path: Path, package: dict[str, Any]
) -> None:
    document = copy.deepcopy(package["config"].document)
    runner = document["trajectory_config"]
    runner["maximum_decisions_per_run"] = 1
    runner["config_id"] = manifest_identifier({k: v for k, v in runner.items() if k != "config_id"})
    document["config_id"] = manifest_identifier(
        {k: v for k, v in document.items() if k != "config_id"}
    )
    package["config"] = StartingEvidenceConfig.from_mapping(document)
    report = _collect(tmp_path / "evidence", package)
    assert report["summary"]["truncated_trajectories"] == 12
    assert report["summary"]["failed_runs"] == 4
    assert _case(tmp_path / "evidence", report)["comparisons"] == []
    assert _verify(tmp_path / "evidence", package)["valid"] is True


def test_preflight_cleanup_error_stays_in_denominator(
    tmp_path: Path, package: dict[str, Any]
) -> None:
    class CleanupFailure(_StartingEnvironment):
        def close(self) -> None:
            raise RuntimeError("cleanup error")

    report = _collect(tmp_path / "evidence", package, factory=CleanupFailure)
    assert report["summary"]["failed_runs"] == 4
    assert "cleanup" in _case(tmp_path / "evidence", report)["error"]
    assert _verify(tmp_path / "evidence", package)["valid"] is True


def test_privileged_source_is_not_saved_as_training_input(
    tmp_path: Path, package: dict[str, Any]
) -> None:
    class Private(_StartingEnvironment):
        def observe(self) -> Observation:
            observed = super().observe()
            public = {**observed.public_state, "rng_state": "secret"}
            return Observation(
                observed.schema_version,
                observed.patch_id,
                observed.decision_type,
                public,
                manifest_identifier(public).removeprefix("sha256:"),
            )

    report = _collect(tmp_path / "evidence", package, factory=Private)
    case = _case(tmp_path / "evidence", report)
    assert case["source_model_input"] is None
    assert "secret" not in json.dumps(case)
    assert report["summary"]["failed_or_missing_branches"] == 12


def test_interrupted_collection_resumes_only_missing_seeds(
    tmp_path: Path, package: dict[str, Any]
) -> None:
    def interrupted(done: int, total: int) -> None:
        raise RuntimeError("owner interruption")

    with pytest.raises(RuntimeError, match="owner interruption"):
        _collect(tmp_path / "evidence", package, progress=interrupted)
    saved = list((tmp_path / "evidence/cases").glob("seed-*.json"))
    assert len(saved) == 1 and not (tmp_path / "evidence" / FILENAME).exists()
    original = saved[0].read_bytes()
    resets = []

    class Resumed(_StartingEnvironment):
        def reset(self, seed: int) -> Observation:
            resets.append(seed)
            return super().reset(seed)

    report = _collect(tmp_path / "evidence", package, factory=Resumed, resume=True)
    saved_seed = json.loads(original)["run_seed"]
    assert saved_seed not in resets and len(resets) == 12
    assert saved[0].read_bytes() == original
    assert report["summary"]["completed_runs"] == 4
    with pytest.raises(FileExistsError):
        _collect(tmp_path / "evidence", package, resume=True)


@pytest.mark.parametrize(
    "field", ["comparisons", "source_model_input", "later_action", "missing_branch"]
)
def test_recomputed_outer_hash_cannot_hide_changed_evidence(
    tmp_path: Path,
    package: dict[str, Any],
    field: str,
) -> None:
    directory = tmp_path / "evidence"
    report = _collect(directory, package)
    case = _case(directory, report)
    if field == "comparisons":
        case["comparisons"][0]["eligible_policy_preference"] = False
    elif field == "source_model_input":
        case["option_ids"][0] = 999
    elif field == "missing_branch":
        case["branches"].pop()
    else:
        trajectory = case["branches"][0]["trajectory"]
        trajectory["decisions"][1]["selection_source"] = "mutation"
        trajectory["trajectory_id"] = manifest_identifier(
            {k: v for k, v in trajectory.items() if k != "trajectory_id"}
        )
    case["case_id"] = manifest_identifier({k: v for k, v in case.items() if k != "case_id"})
    (directory / report["cases"][0]["path"]).write_text(json.dumps(case))
    with pytest.raises(ValueError):
        _verify(directory, package)


def test_config_owner_folds_and_production_window_are_frozen(package: dict[str, Any]) -> None:
    config = load_starting_evidence_config(
        Path("configs/starting-option-evidence/sts2-v0.107.1-base-v2-train-v1.json")
    )
    assert len(config.document["complete_run_subfolds"]["fit"]) == 48
    assert len(config.document["complete_run_subfolds"]["selection"]) == 16
    assert config.document["minimum_runs"] == {"fit": 16, "selection": 8, "strong_selection": 4}
    broken = copy.deepcopy(package["config"].document)
    broken["complete_run_subfolds"]["selection"] = broken["complete_run_subfolds"]["fit"][:1]
    broken["config_id"] = manifest_identifier({k: v for k, v in broken.items() if k != "config_id"})
    with pytest.raises(ValueError, match="overlapping|missing"):
        StartingEvidenceConfig.from_mapping(broken)


def test_cli_saved_verification_uses_no_backend(
    tmp_path: Path,
    package: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    directory = tmp_path / "evidence"
    _collect(directory, package)
    config = tmp_path / "config.json"
    config.write_text(json.dumps(package["config"].document))
    monkeypatch.setattr(
        "spireshift.cli.load_patch_manifest",
        lambda _: SimpleNamespace(ruleset_identity=lambda: _StartingEnvironment.ruleset),
    )
    monkeypatch.setattr(
        "spireshift.cli.load_evangambit_backend", lambda *a, **kw: pytest.fail("Backend loaded")
    )
    assert (
        main(
            [
                "model",
                "verify-starting-option-evidence",
                str(directory / FILENAME),
                str(config),
                "--split-manifest",
                "manifests/splits/mock-v1-seeds-000000-000999-v1.json",
                "--manifest",
                "not-needed.json",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["valid"] is True


def test_cli_completed_collection_refuses_before_loading_backend(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / FILENAME).write_text("{}")
    monkeypatch.setattr(
        "spireshift.cli.load_evangambit_backend", lambda *a, **kw: pytest.fail("Backend loaded")
    )
    assert (
        main(
            [
                "model",
                "collect-starting-option-evidence",
                "unused-config",
                "unused-checkpoint",
                "--report",
                "unused-report",
                "--split-manifest",
                "unused-split",
                "--upstream-root",
                "unused-root",
                "--manifest",
                "unused-manifest",
                "--output-dir",
                str(tmp_path),
                "--resume",
            ]
        )
        == 1
    )
    assert "already exists" in json.loads(capsys.readouterr().out)["error"]


def test_owner_script_completed_rerun_verifies_and_partial_attempt_uses_new_report(
    tmp_path: Path,
) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    script = scripts / "collect-starting-option-evidence-v1.sh"
    script.write_text(Path("scripts/collect-starting-option-evidence-v1.sh").read_text())
    binary = tmp_path / "bin"
    binary.mkdir()
    uv = binary / "uv"
    uv.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@"\n')
    uv.chmod(0o755)
    environment = {**os.environ, "PATH": str(binary) + os.pathsep + os.environ["PATH"]}
    resources = tmp_path / "artifacts/resources"
    resources.mkdir(parents=True)
    (resources / "starting-option-evidence-base-v2-train-v1-attempt-1.json").write_text("{}")
    first = subprocess.run(
        ["bash", str(script)], capture_output=True, text=True, env=environment, check=True
    )
    assert "attempt-2.json" in first.stdout and "collect-starting-option-evidence" in first.stdout
    output = tmp_path / "artifacts/starting-options/sts2-v0.107.1-base-v2-train-v1"
    output.mkdir(parents=True)
    (output / FILENAME).write_text("{}")
    second = subprocess.run(
        ["bash", str(script)], capture_output=True, text=True, env=environment, check=True
    )
    assert "verify-starting-option-evidence" in second.stdout
    assert "resources" not in second.stdout and "--resume" not in second.stdout


def test_json_schemas_cover_frozen_config_and_collected_evidence(
    tmp_path: Path, package: dict[str, Any]
) -> None:
    schema_documents = [json.loads(p.read_text()) for p in Path("schemas").glob("*.json")]
    registry: Registry[Any] = Registry().with_resources(
        (d["$id"], Resource.from_contents(d)) for d in schema_documents
    )
    directory = tmp_path / "evidence"
    report = _collect(directory, package)
    for filename, value in [
        ("starting-option-evidence-config-v1.json", package["config"].document),
        ("starting-option-evidence-case-v1.json", _case(directory, report)),
        ("starting-option-evidence-report-v1.json", report),
    ]:
        schema = json.loads((Path("schemas") / filename).read_text())
        Draft202012Validator(schema, registry=registry).validate(value)
