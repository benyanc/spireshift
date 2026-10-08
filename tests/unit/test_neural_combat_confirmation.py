from __future__ import annotations

import copy
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from test_combat_confirmation import RULESET, SPLIT, TinyEnvironment, ToyPolicy, identified, recipe
from test_combat_policy import _example
from test_neural_combat import _setup

from spireshift.agents.learned import ProductionCheckpointPolicy
from spireshift.cli import main
from spireshift.combat_confirmation import (
    CombatConfirmationConfig,
    load_combat_confirmation_config,
    load_confirmation_policies,
)
from spireshift.core.manifest import manifest_identifier
from spireshift.core.objective import ObjectiveSpec
from spireshift.core.types import DecisionType, LegalAction, Observation
from spireshift.neural_combat import NeuralCombatHead, train_neural_combat_inputs
from spireshift.production_evaluation import (
    load_production_policy_evaluation,
    run_production_policy_evaluation,
)
from spireshift.resource_tracking import EXPERIMENT_METRICS_ENV
from spireshift.splits import SplitName, load_split_manifest

CONFIG = Path("configs/combat-confirmation/sts2-v0.107.1-base-v11-neural-fresh-train-v1.json")


def _preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Exercise cross-artifact bindings; source/model validators have separate tests."""
    import spireshift.combat_confirmation as module

    d = copy.deepcopy(load_combat_confirmation_config(CONFIG).document)
    train = list(SPLIT.seeds(SplitName.TRAIN))
    d.update(
        patch_id=RULESET.patch_id,
        ruleset_manifest_id=RULESET.manifest_id,
        split_manifest_id=SPLIT.manifest_id,
        seeds=train[4:6],
        run_offset=4,
        prior_train_prefix_stop=4,
        maximum_decisions_per_run=8,
    )
    config = CombatConfirmationConfig.from_mapping(identified(d, "config_id"))
    fresh = {
        "seeds": d["seeds"],
        "run_offset": 4,
        "prior_train_prefix_stop": 4,
        "run_count": 2,
    }
    # Deliberately different: the reused linear recipe's historical reservation must
    # not substitute for the neural recipe's new cohort or its complete-run ownership.
    data = {
        "fresh_confirmation": {
            "seeds": train[2:4],
            "run_offset": 2,
            "prior_train_prefix_stop": 2,
            "max_decisions_per_run": 8,
        }
    }
    diagnosis = identified(
        {"summary": {"analysis_integrity_pass": True}, "cases": [{"seed": s} for s in train[:2]]},
        "report_id",
    )
    (tmp_path / "diagnosis.json").write_text(json.dumps(diagnosis))
    neural = {
        "config_id": d["training_config_id"],
        "data_config": data,
        "fresh_confirmation": fresh,
        "diagnosis": {
            "path": "diagnosis.json",
            "report_id": diagnosis["report_id"],
            "inspected_seeds": train[:2],
        },
    }
    foundation = {
        "model_id": d["reference"]["model_id"],
        "training_report_id": d["reference"]["report_id"],
        "parent_checkpoint": d["reference"]["checkpoint_path"],
        "parent_report": d["reference"]["report_path"],
        "objective": d["objective"],
    }
    report = {
        "schema_version": "production-model-training-report-v10",
        "report_id": d["candidate"]["report_id"],
        "neural_config": copy.deepcopy(neural),
        "config": copy.deepcopy(data),
        "candidate_eligible": True,
        "status": "requires_fresh_confirmation",
        "seed_verification": {
            "disjoint": True,
            "fresh_seeds": d["seeds"],
            "prior_inventories": [],
        },
    }
    resource = {
        "report_id": d["candidate"]["resource_report_id"],
        "status": "completed",
        "exit_code": 0,
        "cap": None,
        "experiment_kind": "training",
        "usage": {"trajectories": 0, "simulations": 0, "transitions": 0},
    }
    monkeypatch.setattr(
        "spireshift.neural_combat.load_neural_combat_config",
        lambda _: SimpleNamespace(
            document=neural,
            data=SimpleNamespace(document=data, foundation=SimpleNamespace(document=foundation)),
        ),
    )
    monkeypatch.setattr(
        module,
        "load_production_model_checkpoint",
        lambda path: {
            "model_id": d["candidate" if "base-v11" in str(path) else "reference"]["model_id"]
        },
    )
    monkeypatch.setattr(
        module,
        "load_production_training_report",
        lambda path, **kw: (
            report if "base-v11" in str(path) else {"report_id": d["reference"]["report_id"]}
        ),
    )
    monkeypatch.setattr(module, "load_resource_report", lambda _: resource)
    monkeypatch.setattr(
        module,
        "ProductionCheckpointPolicy",
        lambda checkpoint, **kw: ToyPolicy(checkpoint["model_id"]),
    )

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("Neural confirmation may not load the old linear recipe or refit sources")

    monkeypatch.setattr(module, "load_combat_policy_config", forbidden)
    monkeypatch.setattr("spireshift.neural_combat.load_neural_combat_inputs", forbidden)
    monkeypatch.setattr("spireshift.neural_combat.train_neural_combat_inputs", forbidden)
    monkeypatch.setattr("spireshift.cli.load_evangambit_backend", forbidden)
    return (
        {
            "config": config,
            "project_root": tmp_path,
            "split": SPLIT,
            "ruleset": RULESET,
            "objective": ObjectiveSpec.from_mapping(d["objective"]),
        },
        report,
        neural,
        resource,
    )


@pytest.mark.parametrize(
    "wrong",
    [
        None,
        "recipe",
        "data",
        "cap",
        "work",
        "rejected",
        "diagnosis",
        "overlap",
        "old_cohort",
        "limit",
    ],
)
def test_neural_preflight_uses_new_reservation_and_blocks_invalid_saved_bindings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wrong: str | None
) -> None:
    args, report, neural, resource = _preflight(tmp_path, monkeypatch)
    d = copy.deepcopy(args["config"].document)
    if wrong == "recipe":
        report["neural_config"]["config_id"] = "sha256:" + "0" * 64
    elif wrong == "data":
        report["config"]["fresh_confirmation"]["max_decisions_per_run"] += 1
    elif wrong == "cap":
        resource["cap"] = "wall_seconds"
    elif wrong == "work":
        resource["usage"]["simulations"] = 1
    elif wrong == "rejected":
        report["candidate_eligible"] = False
    elif wrong == "diagnosis":
        path = tmp_path / "diagnosis.json"
        broken = json.loads(path.read_text())
        broken["summary"]["analysis_integrity_pass"] = False
        path.write_text(json.dumps(identified(broken, "report_id")))
    elif wrong == "overlap":
        d.update(
            seeds=neural["diagnosis"]["inspected_seeds"], run_offset=0, prior_train_prefix_stop=0
        )
    elif wrong == "old_cohort":
        old = neural["data_config"]["fresh_confirmation"]
        d.update(seeds=old["seeds"], run_offset=2, prior_train_prefix_stop=2)
    elif wrong == "limit":
        d["maximum_decisions_per_run"] += 1
    args["config"] = CombatConfirmationConfig.from_mapping(identified(d, "config_id"))
    if wrong is None:
        candidate, reference = load_confirmation_policies(**args)
        assert candidate.model_id == d["candidate"]["model_id"]
        assert reference.model_id == d["reference"]["model_id"]
    else:
        with pytest.raises(ValueError):
            load_confirmation_policies(**args)


def test_frozen_neural_comparison_matches_pretraining_reservation_and_strict_schema() -> None:
    from spireshift.neural_combat import load_neural_combat_config

    plan = load_combat_confirmation_config(CONFIG).document
    training = load_neural_combat_config(Path(plan["training_config_path"]))
    fresh = training.document["fresh_confirmation"]
    split = load_split_manifest(
        Path("manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json")
    )
    assert plan["training_config_id"] == training.document["config_id"]
    assert len(plan["seeds"]) == 32
    assert plan["seeds"] == fresh["seeds"] == list(split.seeds(SplitName.TRAIN)[536:568])
    assert plan["run_offset"] == plan["prior_train_prefix_stop"] == fresh["run_offset"] == 536
    assert not set(plan["seeds"]) & set(training.document["diagnosis"]["inspected_seeds"])
    assert plan["maximum_decisions_per_run"] == 4096
    assert plan["objective"]["whole_run_budget"] == 128
    assert plan["reference"]["model_id"] == training.data.foundation.document["model_id"]
    registry: Registry[Any] = Registry().with_resources(
        [
            (
                f"https://spireshift.dev/schemas/{p.name}",
                Resource.from_contents(json.loads(p.read_text())),
            )
            for p in Path("schemas").glob("*.json")
        ]
    )
    Draft202012Validator(
        json.loads(Path("schemas/combat-policy-confirmation-config-v1.json").read_text()),
        registry=registry,
    ).validate(plan)


@pytest.mark.parametrize("bad_binding", [False, True])
def test_neural_cli_checks_inputs_before_backend_and_cached_display_never_plays(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    bad_binding: bool,
) -> None:
    args, report, _, _ = _preflight(tmp_path, monkeypatch)
    if bad_binding:
        report["neural_config"]["config_id"] = "sha256:" + "0" * 64
    config = tmp_path / "plan.json"
    config.write_text(json.dumps(args["config"].document))
    metrics = tmp_path / "work.json"
    monkeypatch.setenv(EXPERIMENT_METRICS_ENV, str(metrics))
    loads: list[bool] = []

    def tiny_backend(*args: Any, **kwargs: Any) -> SimpleNamespace:
        loads.append(True)
        return SimpleNamespace(factory=TinyEnvironment)

    monkeypatch.setattr("spireshift.cli.load_evangambit_backend", tiny_backend)
    common = [
        str(config),
        "--project-root",
        str(tmp_path),
        "--split-manifest",
        "manifests/splits/mock-v1-seeds-000000-000999-v1.json",
        "--manifest",
        "manifests/patches/mock-v1.json",
        "--output-dir",
        str(tmp_path / "comparison"),
    ]
    code = main(
        [
            "model",
            "confirm-combat-policy",
            *common,
            "--upstream-root",
            str(tmp_path / "unused_backend"),
        ]
    )
    work = json.loads(metrics.read_text())
    assert code == int(bad_binding)
    assert loads == ([] if bad_binding else [True])
    assert work["trajectories"] == (0 if bad_binding else 4)
    assert work["transitions"] == (0 if bad_binding else 8)
    assert work["simulations"] == 0
    capsys.readouterr()
    if not bad_binding:

        def forbidden(*args: Any, **kwargs: Any) -> Any:
            pytest.fail("Displaying a saved neural comparison must not play or predict")

        monkeypatch.setattr("spireshift.cli.load_evangambit_backend", forbidden)
        monkeypatch.setattr(ToyPolicy, "choose_action", forbidden)
        before = metrics.read_bytes()
        assert main(["model", "show-combat-confirmation", *common]) == 0
        assert '"games_this_command": 0' in capsys.readouterr().out
        assert metrics.read_bytes() == before


@dataclass
class NeuralToyPolicy(ToyPolicy):
    # A small real neural scorer inside the synthetic evaluation cohort. Source/model
    # identity preflight is exercised separately above; this test needs no game engine.
    neural: ProductionCheckpointPolicy | None = None

    def choose_action(self, observation: Observation, legal_actions: Any) -> LegalAction:
        assert self.neural is not None
        return self.neural.choose_action(observation, legal_actions)


class PublicCombatEnvironment(TinyEnvironment):
    def observation(self) -> Observation:
        if self.phase != 1:
            return super().observation()
        fields = _example(5).representation
        slots = {
            f.indices[0]: int(cast(float, f.numeric_value))
            for f in fields.global_features + fields.persistent_resources
            if f.path == ("observation_vector",)
        }
        vector = [slots[i] for i in range(682)]
        state = {
            "observation_vector": vector,
            "player_hp": vector[0],
            "player_max_hp": vector[1],
            "enemy_def_ids": [7],
            "potions": [47, 0, 0, 0, 0, 0],
            "act": "underdocks",
            "floor": 17,
            "terminal": False,
            "victory": False,
        }
        return Observation(
            "observation-v1",
            RULESET.patch_id,
            DecisionType.COMBAT,
            state,
            manifest_identifier(state)[7:],
        )

    def legal_actions(self) -> tuple[LegalAction, ...]:
        if self.phase != 1:
            return super().legal_actions()
        return tuple(
            LegalAction(
                f"action-{i}",
                "evangambit_combat",
                {
                    "phase": "combat",
                    "action_index": i,
                    **({"target_index": 0} if i in (0, 3) else {}),
                },
            )
            for i in range(4)
        )


def test_real_neural_inference_runs_in_paired_loop_and_saved_cases_resume_without_predictions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    training, inputs, catalog = _setup()
    learned = train_neural_combat_inputs(inputs=inputs, config=training, catalog=catalog)
    neural = ProductionCheckpointPolicy(
        checkpoint=learned.checkpoint, training_report=learned.report, ruleset=RULESET
    )
    d = copy.deepcopy(recipe().document)
    d["candidate"].update(model_id=neural.model_id, report_id=learned.report["report_id"])
    d["reference"].update(
        model_id=inputs.parent_checkpoint["model_id"], report_id=inputs.parent_report["report_id"]
    )
    config = CombatConfirmationConfig.from_mapping(identified(d, "config_id"))
    calls: list[int] = []
    original = NeuralCombatHead.scores

    def scores(self: NeuralCombatHead, representation: Any) -> tuple[float, ...]:
        if representation.decision_type == "combat":
            calls.append(len(representation.candidates))
        return original(self, representation)

    monkeypatch.setattr(NeuralCombatHead, "scores", scores)
    arguments = {
        "environment_factory": PublicCombatEnvironment,
        "ruleset": RULESET,
        "learned_policy": cast(
            ProductionCheckpointPolicy, NeuralToyPolicy(neural.model_id, neural=neural)
        ),
        "split_manifest": SPLIT,
        "training_report_id": learned.report["report_id"],
        "reference_policy": cast(ProductionCheckpointPolicy, ToyPolicy(d["reference"]["model_id"])),
        "reference_training_report_id": d["reference"]["report_id"],
        "seeds": d["seeds"],
        "workers": 1,
        "maximum_decisions_per_run": 8,
        "partition": SplitName.TRAIN,
        "output_directory": tmp_path / "comparison",
        "confirmation": config,
    }
    result = run_production_policy_evaluation(**arguments)
    assert calls == [4, 4]
    assert result.successful and result.new_runs == 4 and result.new_transitions == 8
    assert result.report["decision"]["checkpoint_promoted"] is False
    result.report_path.unlink()  # Interrupted after cases, before final summary.

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("All saved neural cases must resume without another game or prediction")

    arguments["environment_factory"] = forbidden
    monkeypatch.setattr(NeuralCombatHead, "scores", forbidden)
    resumed = run_production_policy_evaluation(**arguments, resume=True)
    assert resumed.new_runs == resumed.new_transitions == 0
    assert (
        load_production_policy_evaluation(
            resumed.report_path,
            model_id=neural.model_id,
            training_report_id=learned.report["report_id"],
            split_manifest=SPLIT,
            reference_model_id=d["reference"]["model_id"],
            reference_training_report_id=d["reference"]["report_id"],
        )
        == resumed.report
    )


@pytest.mark.parametrize("repair", [False, True])
def test_neural_owner_script_has_caps_single_threads_immutable_attempts_and_cached_display(
    tmp_path: Path,
    repair: bool,
) -> None:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "bin").mkdir()
    script = tmp_path / "scripts/test.sh"
    script_name = (
        "confirm-neural-selection-repair-v2.sh" if repair else "confirm-neural-combat-policy-v1.sh"
    )
    script.write_text(Path("scripts", script_name).read_text())
    resource_prefix = (
        "neural-combat-base-v11-selection-repair-v2"
        if repair
        else "neural-combat-base-v11-confirmation-v1"
    )
    output_name = (
        "sts2-v0.107.1-base-v11-neural-selection-repair-v2"
        if repair
        else "sts2-v0.107.1-base-v11-neural-fresh-train-v1"
    )
    log = tmp_path / "calls"
    uv = tmp_path / "bin/uv"
    uv.write_text(
        '#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "$SPIRESHIFT_TEST_CALLS"\n'
        'printf "threads=%s,%s,%s,%s\\n" "$OMP_NUM_THREADS" "$OPENBLAS_NUM_THREADS" '
        '"$MKL_NUM_THREADS" "$VECLIB_MAXIMUM_THREADS" >> "$SPIRESHIFT_TEST_THREADS"\n'
    )
    uv.chmod(0o755)
    env = {
        **os.environ,
        "PATH": str(uv.parent) + os.pathsep + os.environ["PATH"],
        "SPIRESHIFT_TEST_CALLS": str(log),
        "SPIRESHIFT_TEST_THREADS": str(tmp_path / "threads"),
        "OMP_NUM_THREADS": "9",
        "OPENBLAS_NUM_THREADS": "9",
        "MKL_NUM_THREADS": "9",
        "VECLIB_MAXIMUM_THREADS": "9",
    }
    resources = tmp_path / "artifacts/resources"
    resources.mkdir(parents=True)
    (resources / f"{resource_prefix}-attempt-1.json").write_text("{}")
    (resources / f"{resource_prefix}-attempt-2-metrics.json").write_text("{}")
    subprocess.run(["bash", str(script)], env=env, capture_output=True, check=True)
    command = log.read_text()
    assert len(command.splitlines()) == 1
    for argument in (
        "attempt-3.json",
        "--workers 1",
        "--max-wall-seconds 1800",
        "--max-cpu-seconds 10000",
        "--max-memory-bytes 8000000000",
        "--max-storage-bytes 1000000000",
        "--resume",
        "confirm-combat-policy",
        output_name,
    ):
        assert argument in command
    assert "train-neural-combat-policy" not in command and "discover-states" not in command
    assert (tmp_path / "threads").read_text() == "threads=1,1,1,1\n"
    output = tmp_path / "artifacts/evaluations" / output_name
    output.mkdir(parents=True)
    final = output / "production-policy-evaluation.json"
    final.write_text("{}")
    log.write_text("")
    subprocess.run(["bash", str(script)], env=env, capture_output=True, check=True)
    assert "show-combat-confirmation" in log.read_text() and "resources run" not in log.read_text()
    final.unlink()
    final.symlink_to(tmp_path / "missing-result")
    log.write_text("")
    stopped = subprocess.run(["bash", str(script)], env=env, capture_output=True, check=False)
    assert stopped.returncode != 0 and log.read_text() == ""
