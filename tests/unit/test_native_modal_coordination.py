from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _sha_file

VERIFIER = "src/spireshift/native_flow_verification_v12.py"


def coordinator() -> Any:
    path = Path(__file__).resolve().parents[2] / "scripts/modal-panel-session-v2.py"
    spec = importlib.util.spec_from_file_location("modal_coordinator_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_identified(path: Path, body: dict[str, Any]) -> dict[str, Any]:
    body = {k: v for k, v in body.items() if k != "report_id"}
    value = {**body, "report_id": manifest_identifier(body)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return value


def live_result(root: Path, context: dict[str, Any]) -> dict[str, Any]:
    cfg = context["config"]
    raw = root / cfg["workspace"] / "raw.txt"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text("saved public input and receipt")
    checks = dict.fromkeys(
        [
            "profile_path_logged",
            "Steam_disabled_observed",
            "personal_profile_unchanged",
            "working_app_unchanged",
            "frozen_archive_unchanged",
            "settings_template_unchanged",
            "natural_shutdown",
            "exact_delivery_count",
        ],
        True,
    )
    return write_identified(
        root / cfg["workspace"] / "report.json",
        {
            "schema_version": "native-live-checkpoint-adapter-result-v1",
            "config_id": manifest_identifier(cfg),
            "environment_id": context["environment"]["manifest_id"],
            "implementation_id": manifest_identifier(cfg["implementation_sha256"]),
            "helpers_id": manifest_identifier(cfg["helpers_sha256"]),
            "cases": [
                {
                    **cfg["cases"][0],
                    "native": {
                        "policy_decisions": cfg["maximum_decisions"],
                        "shutdown": {"clean_exit": True},
                    },
                    "official": {
                        "probe": {"policy_decisions": cfg["maximum_decisions"]},
                        "checks": checks,
                    },
                    "comparison": {"equal_input_prefix": cfg["maximum_decisions"]},
                }
            ],
            "checkpoint_delivery_exercised": True,
            "full_prefix_input_equivalence": True,
            "sources": {VERIFIER: _sha_file(root / VERIFIER)},
            "evidence": {str(raw.relative_to(root)): _sha_file(raw)},
        },
    )


def verification(
    root: Path, context: dict[str, Any], report: dict[str, Any], index: int
) -> dict[str, Any]:
    # This is the producer's real contract. It deliberately has no evidence map.
    witness = write_identified(
        root / context["config"]["workspace"] / "verification-v1/report.json",
        {
            "schema_version": "native-live-checkpoint-verification-v1",
            "valid": True,
            "source_report_id": report["report_id"],
            "verifier_sha256": _sha_file(root / VERIFIER),
            "cases": [
                {
                    "key": report["cases"][0]["key"],
                    "host": host,
                    "verified_decisions": context["config"]["maximum_decisions"],
                }
                for host in ["native", "official"]
            ],
            "games_launched": 0,
            "optimizer_updates": 0,
            "original_weights_and_all_Adam_unchanged": True,
            "source_inputs_reaudited": False,
        },
    )
    write_identified(
        root / f"artifacts/resources/map-settling-control-{index}-verify-v1.json",
        {"status": "completed", "exit_code": 0, "cap": None},
    )
    return witness


@pytest.fixture
def batch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    module = coordinator()
    verifier = tmp_path / VERIFIER
    verifier.parent.mkdir(parents=True)
    verifier.write_text("frozen verifier")
    parent = tmp_path / "parent.json"
    parent.write_text('{"original_finite_plan":true}')
    old_marker = tmp_path / "old/active.json"
    old_marker.parent.mkdir()
    old_marker.write_text("preserved prior marker")
    contexts: list[dict[str, Any]] = []
    controls: list[dict[str, Any]] = []
    for index, kind in enumerate(module.KINDS, 1):
        cfg = {
            "workspace": f"artifacts/cases/{kind}",
            "maximum_decisions": index + 2,
            "cases": [{"key": kind, "player": 2, "seed": f"WORLD{index}"}],
            "implementation_sha256": {VERIFIER: _sha_file(verifier)},
            "helpers_sha256": {},
        }
        contexts.append(
            {"config": cfg, "environment": {"manifest_id": "environment"}, "working_app": {}}
        )
        recipe = tmp_path / f"recipe-{index}.json"
        recipe.write_text(json.dumps(cfg))
        controls.append(
            {"recipe": {"path": recipe.name}, "launch": {"path": f"launch-{index}.json"}}
        )
    cfg = {
        "workspace": "artifacts/native-selection-flows/new-ledger",
        "controls": controls,
        "sources": {VERIFIER: _sha_file(verifier)},
        "parent_plan": {"path": parent.name, "sha256": _sha_file(parent)},
        "preserved_parent_marker": {
            "path": "old/active.json",
            "sha256": _sha_file(old_marker),
        },
    }
    plan = tmp_path / "new-plan.json"
    plan.write_text(json.dumps(cfg))
    first = live_result(tmp_path, contexts[0])
    verification(tmp_path, contexts[0], first, 1)
    calls: list[tuple[str, int]] = []

    def call(command: list[str], *, cwd: Path) -> int:
        assert cwd == tmp_path
        if command[0] == "bash":
            index = next(
                i
                for i, control in enumerate(controls, 1)
                if control["recipe"]["path"] == command[2]
            )
            assert index != 1, "A completed control must never launch again"
            calls.append(("game", index))
            live_result(tmp_path, contexts[index - 1])
        else:
            assert "spireshift.native_flow_verification_v12" in command
            recipe = command[command.index("spireshift.native_flow_verification_v12") + 1]
            index = next(
                i for i, control in enumerate(controls, 1) if control["recipe"]["path"] == recipe
            )
            calls.append(("verify", index))
            context = contexts[index - 1]
            report = module.identified(tmp_path / context["config"]["workspace"] / "report.json")
            verification(tmp_path, context, report, index)
        return 0

    monkeypatch.setattr(module.subprocess, "call", call)
    monkeypatch.setattr(module, "preflight_working_app", lambda _: None)
    monkeypatch.setattr("spireshift.engine_native._running_games", lambda: [])
    return {
        "module": module,
        "root": tmp_path,
        "path": plan,
        "config": cfg,
        "contexts": contexts,
        "calls": calls,
        "old_marker": old_marker,
    }


def run_batch(batch: dict[str, Any], *, allow_games: bool = True) -> dict[str, Any]:
    result: dict[str, Any] = batch["module"].run(
        batch["root"], batch["path"], batch["config"], batch["contexts"], allow_games=allow_games
    )
    return result


def test_real_verifier_schema_is_accepted_without_an_evidence_map(batch: dict[str, Any]) -> None:
    root, context, module = batch["root"], batch["contexts"][0], batch["module"]
    path = root / context["config"]["workspace"]
    report = module.identified(path / "report.json")
    witness = module.identified(path / "verification-v1/report.json")
    assert "evidence" not in witness
    module.validate_verification(root, context, report, witness)


@pytest.mark.parametrize(
    "field,value",
    [
        ("valid", False),
        ("source_report_id", "another-report"),
        ("verifier_sha256", "another-verifier"),
        ("cases", []),
        ("games_launched", 1),
        ("optimizer_updates", 1),
        ("original_weights_and_all_Adam_unchanged", False),
    ],
)
def test_unbound_or_incomplete_verification_rejects(
    batch: dict[str, Any], field: str, value: Any
) -> None:
    root, context, module = batch["root"], batch["contexts"][0], batch["module"]
    path = root / context["config"]["workspace"]
    report = module.identified(path / "report.json")
    witness = module.identified(path / "verification-v1/report.json")
    witness[field] = value
    with pytest.raises(ValueError, match="Saved verification"):
        module.validate_verification(root, context, report, witness)


def test_saved_only_then_resume_reuses_the_first_control_and_all_immutable_files(
    batch: dict[str, Any],
) -> None:
    root = batch["root"]
    ledger = root / batch["config"]["workspace"]
    originals = {
        p: p.read_bytes()
        for p in [batch["old_marker"], *(root / "artifacts/cases/reward_glyphs").rglob("*")]
        if p.is_file()
    }
    saved = run_batch(batch, allow_games=False)
    assert saved["status"] == "saved_progress_ready"
    assert saved["completed_controls"] == 1 and saved["remaining_controls"] == 3
    assert saved["new_game_starts_this_session"] == 0 and batch["calls"] == []
    assert not (ledger / "active.json").exists() and not (ledger / "report.json").exists()
    unit = (ledger / "units/01.json").read_bytes()
    complete = run_batch(batch)
    assert complete["status"] == "targeted_panel_pass"
    assert complete["completed_controls"] == 4 and complete["remaining_controls"] == 0
    assert complete["new_game_starts_this_session"] == 6
    assert batch["calls"] == [
        ("game", 2),
        ("verify", 2),
        ("game", 3),
        ("verify", 3),
        ("game", 4),
        ("verify", 4),
    ]
    assert (ledger / "units/01.json").read_bytes() == unit
    assert all(p.read_bytes() == value for p, value in originals.items())
    before_calls = copy.deepcopy(batch["calls"])
    assert run_batch(batch) == complete
    assert batch["calls"] == before_calls


def test_changed_raw_evidence_blocks_before_any_new_case(batch: dict[str, Any]) -> None:
    root = batch["root"]
    (root / "artifacts/cases/reward_glyphs/raw.txt").write_text("corrupt")
    result = run_batch(batch)
    assert result["status"] == "stopped_preserving_evidence"
    assert batch["calls"] == []
    assert (root / batch["config"]["workspace"] / "active.json").exists()


def test_zero_exit_with_capped_verification_cannot_grant_a_pass(batch: dict[str, Any]) -> None:
    write_identified(
        batch["root"] / "artifacts/resources/map-settling-control-1-verify-v1.json",
        {"status": "completed", "exit_code": 0, "cap": {"wall_seconds": 180}},
    )
    result = run_batch(batch)
    assert result["status"] == "stopped_preserving_evidence"
    assert "budget" in result["error"] and batch["calls"] == []


def test_unverified_worker_blocks_later_cases(batch: dict[str, Any]) -> None:
    path = batch["root"] / "artifacts/cases/reward_glyphs/report.json"
    report = batch["module"].identified(path)
    report["cases"][0]["official"]["checks"]["natural_shutdown"] = False
    write_identified(path, report)
    result = run_batch(batch)
    assert "restore cleanly" in result["error"] and batch["calls"] == []


def test_a_matching_short_prefix_does_not_pass_the_declared_target(batch: dict[str, Any]) -> None:
    root, context = batch["root"], batch["contexts"][0]
    path = root / context["config"]["workspace"] / "report.json"
    report = batch["module"].identified(path)
    report["cases"][0]["native"]["policy_decisions"] -= 1
    report["cases"][0]["official"]["probe"]["policy_decisions"] -= 1
    report["cases"][0]["comparison"]["equal_input_prefix"] -= 1
    report = write_identified(path, report)
    smaller = copy.deepcopy(context)
    smaller["config"]["maximum_decisions"] -= 1
    verification(root, smaller, report, 1)
    result = run_batch(batch)
    assert result["completed_controls"] == 4
    assert result["status"] == "targeted_panel_completed_with_mismatches"
    assert result["controls"][0]["target_prefix_reached"] is False


def test_unstarted_but_uncertain_case_is_never_replayed(batch: dict[str, Any]) -> None:
    path = batch["root"] / batch["contexts"][1]["config"]["workspace"]
    path.mkdir(parents=True)
    (path / "active.json").write_text("uncertain attempt")
    result = run_batch(batch)
    assert result["completed_controls"] == 1
    assert "unfinished case" in result["error"] and batch["calls"] == []
