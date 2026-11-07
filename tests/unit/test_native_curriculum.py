from __future__ import annotations

import ast
import copy
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_native_action_context import model, score
from test_native_natural_curriculum import plan as fight_plan
from test_native_natural_curriculum import public
from test_native_turn_teacher_policy import selection

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _inventory, _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_ppo_math import Adam
from spireshift.native_context_cache import cached_model
from spireshift.native_curriculum_config import CONTRACT, plan, validate, validate_worlds
from spireshift.native_curriculum_data import bank
from spireshift.native_curriculum_evaluate import require_canaries, summary
from spireshift.native_curriculum_fit import examples, fit, schedule
from spireshift.native_curriculum_policy import ForcedPolicy, RoutedChooser, RoutedPolicy, policy
from spireshift.native_learner_guard import CONTRACT as GUARD
from spireshift.native_learner_guard import (
    OPERATIONS,
    bind_candidate_freeze,
    require_copy,
    require_scope,
)
from spireshift.native_structured_policy import Chooser
from spireshift.native_structured_state import load, save


def seal(body: dict[str, Any], key: str = "report_id") -> dict[str, Any]:
    return {**body, key: manifest_identifier(body)}


def guard(binding: dict[str, Any]) -> dict[str, Any]:
    return seal(
        {
            "schema_version": "native-learner-guard-receipt-v1",
            "contract": GUARD,
            "binding": binding,
            "environment_verified": True,
            "recorded_original_inputs_verified": True,
            "original_checkpoint_official_delivery_verified": True,
            "diagnostic_copies_only": True,
            "diagnostic_fitting_on_verified_copies_allowed": True,
            "ordinary_PPO_allowed": False,
            "allowed_operations": sorted(OPERATIONS),
            "training_allowed": False,
            "promotion_allowed": False,
            "adaptive_controller_allowed": False,
        }
    )


@pytest.mark.parametrize(
    "field",
    [
        "environment_verified",
        "recorded_original_inputs_verified",
        "original_checkpoint_official_delivery_verified",
        "diagnostic_copies_only",
    ],
)
def test_missing_actual_guard_scope_blocks_even_with_valid_digest(field: str) -> None:
    binding = {"original_state_id": "full-state-and-Adam"}
    receipt = guard(binding)
    require_scope(receipt, binding, "fit_diagnostic_copy")
    receipt[field] = False
    receipt = seal({k: v for k, v in receipt.items() if k != "report_id"})
    with pytest.raises(ValueError):
        require_scope(receipt, binding, "fit_diagnostic_copy")


@pytest.mark.parametrize(
    "operation", ["promote", "ordinary_PPO", "adaptive_controller", "evaluate_changed_checkpoint"]
)
def test_scoped_live_receipt_cannot_authorize_broader_work(operation: str) -> None:
    with pytest.raises(ValueError):
        require_scope(guard({"checkpoint": "one"}), {"checkpoint": "one"}, operation)


def test_changed_checkpoint_or_optimizer_cannot_borrow_original_guard() -> None:
    binding = {"checkpoint": "old"}
    with pytest.raises(ValueError):
        require_scope(guard(binding), {"checkpoint": "new"}, "fit_diagnostic_copy")
    m = cached_model(model())
    adam = Adam.zero(m.parameter_count)
    receipt = seal(
        {
            "schema_version": "native-learner-recorded-check-v1",
            "guard_binding_id": manifest_identifier(binding),
            "model_id": m.model_id,
            "optimizer_id": manifest_identifier(adam.as_dict()),
            "paired_inputs": 292,
            "all_inputs_features_distributions_equal": True,
            "current_checkpoint_live_delivery_qualified": False,
        }
    )
    context = {"guard_receipt": guard(binding), "guard_binding": binding}
    require_copy(context, m, adam, receipt)
    adam = replace(adam, steps=adam.steps + 1)
    with pytest.raises(ValueError):
        require_copy(context, m, adam, receipt)


def test_binding_study_recipe_does_not_mutate_sealed_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import spireshift.native_curriculum_config as module

    source = tmp_path / "source.py"
    source.write_text("pass\n")
    history = tmp_path / "history.json"
    history.write_text(json.dumps({"canonical_prior_seeds": []}))
    cfg = config()
    cfg.update(
        stage="short_control",
        plan=plan(True),
        workspace="artifacts/native-varied-teaching/control-v1",
        session_limits={
            "wall_seconds": 290,
            "cpu_seconds": 900,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 4000000000,
        },
        node="node",
        execution_runtime={"fixed": True},
        seed_history={"path": "history.json", "sha256": _sha_file(history)},
        implementation={"source.py": _sha_file(source)},
    )
    path = tmp_path / "recipe.json"
    path.write_text(json.dumps(cfg))
    binding = {"checkpoint": "original"}
    sources = {"source.py": _sha_file(source)}
    receipt = guard(binding)
    receipt["sources"] = sources
    receipt = seal({k: v for k, v in receipt.items() if k != "report_id"})
    context = {"guard_receipt": receipt, "guard_binding": binding, "sources": sources}
    monkeypatch.setattr(module, "qualify", lambda *_: context)
    monkeypatch.setattr(module, "implementation", lambda *_: cfg["implementation"])
    monkeypatch.setattr(module, "execution_runtime", lambda *_: cfg["execution_runtime"])
    for name in module.THREADS:
        monkeypatch.setenv(name, "1")
    loaded = module.load(tmp_path, path)
    require_scope(loaded["guard_receipt"], binding, "fit_diagnostic_copy")
    assert "recipe.json" in loaded["sources"]
    assert "recipe.json" not in loaded["guard_receipt"]["sources"]


def test_current_cli_inventory_replaces_stale_metadata_but_still_rejects_any_drift(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    binary = candidate / "host.dll"
    binary.write_bytes(b"qualified-current-CLI")
    frozen = seal(
        {
            "schema_version": "current-native-candidate-freeze-v1",
            "candidate": "candidate",
            "qualified_build_report_id": "current-build",
            "inventory": _inventory(candidate),
        }
    )
    snapshot = tmp_path / "freeze.json"
    atomic_json(snapshot, frozen)
    cfg = {"native_candidate_inventory": {"path": "freeze.json", "sha256": _sha_file(snapshot)}}
    native = {
        "candidate": candidate,
        "inputs": {"build_report_id": "current-build"},
        "candidate_before": [{"path": "older-unrelated-build"}],
    }
    assert bind_candidate_freeze(tmp_path, cfg, native) == frozen["report_id"]
    assert native["candidate_before"] == _inventory(candidate)
    binary.write_bytes(b"patched")
    with pytest.raises(ValueError):
        bind_candidate_freeze(tmp_path, cfg, native)


def test_policy_factory_rejects_checkpoint_swap_even_when_replacement_is_valid(
    tmp_path: Path,
) -> None:
    m = cached_model(model())
    adam = Adam.zero(m.parameter_count)
    checkpoint = save(tmp_path / "state.json", m, adam)
    entry = {
        "state_path": "state.json",
        "state_id": checkpoint["state_id"],
        "model_id": m.model_id,
        "optimizer_id": manifest_identifier(adam.as_dict()),
    }
    context = {"qualification": SimpleNamespace(root=tmp_path), "score": score()}
    assert (
        policy(context, 2, "teacher", "WORLD", {"p2-teacher": entry}).model.model_id == m.model_id
    )
    save(tmp_path / "other.json", cached_model(model(seed=4)), adam)
    entry["state_path"] = "other.json"
    with pytest.raises(ValueError):
        policy(context, 2, "teacher", "WORLD", {"p2-teacher": entry})


def config() -> dict[str, Any]:
    return {
        "schema_version": "native-varied-teaching-config-v1",
        "contract": CONTRACT,
        "stage": "bounded_study",
        "plan": plan(),
        "workspace": "artifacts/native-varied-teaching/study-v1",
        "training_allowed": False,
        "diagnostic_fitting_on_copies_only": True,
        "automatic_follow_up": False,
        "session_limits": {
            "wall_seconds": 1800,
            "cpu_seconds": 3600,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 4000000000,
        },
    }


def test_prospective_splits_and_whole_run_budget_cannot_silently_change() -> None:
    cfg = config()
    validate(cfg)
    validate_worlds(cfg, set())
    with pytest.raises(ValueError):
        validate_worlds(cfg, {cfg["plan"]["evaluation_seeds"][0]})
    cfg["plan"]["evaluation_seeds"][0] = cfg["plan"]["worlds"][0]["seed"]
    with pytest.raises(ValueError):
        validate_worlds(cfg, set())
    cfg = config()
    cfg["plan"]["whole_run_cpu_seconds"] = 129
    with pytest.raises(ValueError):
        validate(cfg)


def frame(p: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "shared-public-decision-v1",
        "contract": "official_cli_shared_public_graph_v1",
        "terminal": False,
        "public_input": p,
        "binding_id": "binding",
        "observation": {"runtime_instance_id": "runtime", "snapshot_id": "snapshot"},
        "actions": [
            {"bound_action_id": f"action-{i}", "key": f"key-{i}", "raw_index": i}
            for i in range(len(p["candidates"]))
        ],
    }


def noncombat(p: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(p)
    result["context"]["interaction"] = {
        "kind": "event_option",
        "content": {"context": {"kind": "event"}},
    }
    return result


def test_routing_retains_original_noncombat_and_taught_combat_including_nested_owner() -> None:
    original, taught = cached_model(model(seed=1)), cached_model(model(seed=3))
    p, spec = public(), score()
    route = RoutedChooser(taught, original, spec, "WORLD")
    current = route(p)
    assert current["routed_actor"] == "taught"
    assert current["action_index"] == Chooser(taught, spec, "WORLD", False)(p)["action_index"]
    assert route(selection(p))["routed_actor"] == "taught"
    after = noncombat(p)
    assert route(after)["routed_actor"] == "original"
    other = RoutedChooser(taught, original, spec, "WORLD")(after)
    expected = Chooser(original, spec, "WORLD", False)(after)
    assert all(
        other[k] == expected[k]
        for k in ["action_index", "draw_key", "policy_log_probability", "value"]
    )
    assert route.original is original and route.taught is taught


def test_route_memory_and_rng_commit_only_after_matching_actual_delivery() -> None:
    original, taught, spec = cached_model(model()), cached_model(model(seed=2)), score()
    policy = RoutedPolicy(taught, original, spec, "WORLD")
    p = frame(noncombat(public()))
    first = policy.choose(p)
    assert policy.chooser.visits == {}
    pending = policy.pending
    assert pending is not None
    trial = pending[2]
    assert isinstance(trial, RoutedChooser) and trial.original is original
    with pytest.raises(ValueError):
        policy.choose(p)
    policy.acknowledge(
        {
            "binding_id": "binding",
            "delivery": "delivered",
            "bound_action_id": first["bound_action_id"],
            "runtime_instance_id": "runtime",
            "before_snapshot_id": "snapshot",
            "successor_snapshot_id": "next",
        }
    )
    assert policy.decisions == 1 and policy.chooser.visits


def test_teacher_force_binds_exact_public_menu_and_rejects_unknown_action() -> None:
    p, spec = public(), score()
    forced = [{"public_input_id": manifest_identifier(p), "action_index": 1}]
    policy = ForcedPolicy(cached_model(model()), spec, "WORLD", forced)
    choice = policy.choose(frame(p))
    assert choice["action_index"] == 1 and choice["bound_action_id"] == "action-1"
    assert choice["ordinary_PPO_eligible"] is False and not policy.chooser.visits
    for changed in [
        {"public_input_id": "wrong", "action_index": 1},
        {"public_input_id": manifest_identifier(p), "action_index": 999},
    ]:
        with pytest.raises(ValueError):
            ForcedPolicy(cached_model(model()), spec, "WORLD", [changed]).choose(frame(p))


def lessons() -> list[dict[str, Any]]:
    steps = [
        {
            "public_input": public(),
            "public_input_id": manifest_identifier(public()),
            "action_index": 0,
        }
    ]
    return [
        {
            "world": f"WORLD{i}",
            "root_id": f"root-{i}-{j}",
            "partition": "control",
            "plans": {
                a: {
                    "root_id": f"root-{i}-{j}",
                    "world": f"WORLD{i}",
                    "steps": steps * (1 if a == "reference" else 5),
                }
                for a in ["reference", "teacher"]
            },
        }
        for i in range(2)
        for j in range(1 + i)
    ]


def test_same_world_work_despite_different_entries_and_plan_lengths() -> None:
    m = cached_model(model())
    banks = lessons()
    a = examples(m, banks, "reference", score(), 32, 0, "sample")
    b = examples(m, banks, "teacher", score(), 32, 0, "sample")
    assert a[2] == b[2] == {"WORLD0": 16, "WORLD1": 16}
    banks[0]["partition"] = "heldout"
    with pytest.raises(ValueError):
        examples(m, banks, "teacher", score(), 32, 0, "sample")


def test_quality_counts_worlds_not_branches_and_refuses_withheld_labels() -> None:
    roots = [
        {
            "root_id": f"root-{i}",
            "world": "ONEWORLD",
            "partition": "fit",
            "player": 2,
            "descriptor": {"enemy_definitions": ["beetle"], "deck_signature": "deck"},
            "reference": fight_plan(),
        }
        for i in range(8)
    ]
    cells = [
        {"root_id": r["root_id"], "selected": fight_plan(), "confirmation_verified": True}
        for r in roots
    ]
    result = bank(roots, cells, plan()["quality"], control=False)
    assert result["quality"]["fitting_worlds"] == 1 and result["quality"]["passed"] is False
    roots[0]["partition"] = "heldout"
    with pytest.raises(ValueError):
        bank(roots, cells, plan()["quality"], control=False)


def test_every_final_precedes_evaluation_and_fixed_work_is_matched() -> None:
    tasks = schedule(16)
    assert tasks[-1]["kind"] == "freeze"
    assert sum(t["kind"] == "fit" for t in tasks) == 64
    assert {t["epoch"] for t in tasks if t["kind"] == "fit"} == set(range(1, 17))
    assert all(t["kind"] not in {"canary", "heldout", "evaluate"} for t in tasks)


def test_changed_final_or_policy_mode_cannot_borrow_canary() -> None:
    expected = plan()["canary_cases"]
    report: dict[str, Any] = {
        "status": "trained_policy_canaries_verified",
        "config_id": "cfg",
        "frozen_finals_id": "finals",
        "cases": [{"case": c, "status": "matching_genuine_endings"} for c in expected],
        "all_current_policy_modes_live_qualified": True,
        "promotion_allowed": False,
    }
    require_canaries(report, "cfg", "finals", expected)
    with pytest.raises(ValueError):
        require_canaries(report, "cfg", "changed-final", expected)
    report["cases"].pop()
    with pytest.raises(ValueError):
        require_canaries(report, "cfg", "finals", expected)


def test_failures_and_unattempted_stay_in_primary_denominator() -> None:
    rows = [
        {
            "seed": "A",
            "player": 2,
            "variant": "teacher",
            "status": "failed_or_capped",
            "victory": False,
            "floor": 99,
        }
    ]
    result = summary(["A", "B"], rows, bootstrap=False)
    assert result["arms"]["teacher"] == {
        "denominator": 4,
        "recorded": 1,
        "not_attempted": 3,
        "failed_or_capped": 1,
        "wins": 0,
        "mean_floor_including_failures": 0,
    }
    with pytest.raises(ValueError):
        summary(["A", "B"], rows * 2, bootstrap=False)


def test_established_raw_receipt_and_summary_verification_not_weakened() -> None:
    root = Path(__file__).resolve().parents[2]
    before = ast.parse((root / "src/spireshift/native_chest_ending_verification.py").read_text())
    after = ast.parse((root / "src/spireshift/native_curriculum_verification.py").read_text())
    old = next(n for n in before.body if isinstance(n, ast.FunctionDef) and n.name == "verify_host")
    new = next(n for n in after.body if isinstance(n, ast.FunctionDef) and n.name == "verify_host")
    assert ast.dump(ast.Module(body=old.body[3:], type_ignores=[])) == ast.dump(
        ast.Module(body=new.body[2:], type_ignores=[])
    )


def test_real_gradient_warm_adam_resume_and_changed_state_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import spireshift.native_curriculum_fit as module

    cfg: dict[str, Any] = {
        "workspace": "artifacts/test",
        "stage": "short_control",
        "implementation": {},
        "plan": {
            "learning": {
                "epochs": 1,
                "steps_per_epoch": 1,
                "batch_choices": 4,
                "actor_learning_rate": 0.001,
                "temperature": 0.8,
                "gradient_clip": 1.0,
            }
        },
        "session_limits": {"wall_seconds": 240},
    }
    m = cached_model(model())
    # Nonzero moments detect accidental zero-state restoration.
    warm = Adam(
        7,
        (0.01, *(0.0 for _ in range(m.parameter_count - 1))),
        (0.02, *(0.0 for _ in range(m.parameter_count - 1))),
    )
    ids = {}
    for p in [2, 3]:
        ids[str(p)] = {
            "imported_state_id": save(tmp_path / f"artifacts/original-{p}.json", m, warm)[
                "state_id"
            ]
        }
    binding = {"players": ids}
    context = {
        "config": cfg,
        "config_id": "cfg",
        "qualification": SimpleNamespace(root=tmp_path),
        "models": {2: m, 3: m},
        "adams": {2: warm, 3: warm},
        "score": score(),
        "environment": {"manifest_id": m.actor.environment_id},
        "sources": {},
        "guard_binding": binding,
        "guard_receipt": guard(binding),
    }
    b = seal({"control_only": True, "lessons": lessons()}, "bank_id")
    directory = tmp_path / cfg["workspace"] / "collection"
    atomic_json(directory / "bank.json", b)
    atomic_json(
        directory / "report.json",
        seal(
            {
                "config_id": "cfg",
                "status": "curriculum_qualified",
                "bank_path": str((directory / "bank.json").relative_to(tmp_path)),
                "bank_id": b["bank_id"],
                "sources": {},
                "evidence": {},
            }
        ),
    )

    def regression(ctx: Any, model: Any, sid: str, oid: str) -> dict[str, Any]:
        return seal(
            {
                "schema_version": "native-learner-recorded-check-v1",
                "guard_binding_id": manifest_identifier(binding),
                "state_id": sid,
                "model_id": model.model_id,
                "optimizer_id": oid,
                "paired_inputs": 292,
                "all_inputs_features_distributions_equal": True,
                "current_checkpoint_live_delivery_qualified": False,
            }
        )

    monkeypatch.setattr(module, "recorded", regression)
    first = fit(context, max_units=3)
    assert first["status"] == "clean_session_boundary"
    saved = tmp_path / cfg["workspace"] / "fitting/chunks/fit-p2-reference-e01/state.json"
    frozen_bytes = saved.read_bytes()
    complete = fit(context)
    assert complete["optimizer_updates"] == 4 and saved.read_bytes() == frozen_bytes
    restored, adam, _ = load(saved)
    assert adam.steps == 8 and restored.value_weights == m.value_weights
    assert warm.steps == 7 and warm.first[0] == 0.01
    saved.write_bytes(frozen_bytes + b" ")
    with pytest.raises(ValueError):
        fit(context)
