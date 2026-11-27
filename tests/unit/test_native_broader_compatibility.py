from __future__ import annotations

import copy
import gzip
import json
from pathlib import Path
from typing import Any

import pytest

from spireshift import native_broader_compatibility_v1 as study
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified as read_identified
from spireshift.engine_qualification import _sha_file


def identified(path: Path, body: dict[str, Any]) -> dict[str, Any]:
    value = {**body, "report_id": manifest_identifier(body)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return value


def frame(family: str = "combat", *, terminal: bool = False) -> dict[str, Any]:
    return {
        "source_family": family,
        "terminal": terminal,
        "ending": {"victory": False, "reason": "death"} if terminal else None,
    }


def write_frames(path: Path, values: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt") as stream:
        for value in values:
            stream.write(json.dumps({"kind": "policy_input", "frame": value}) + "\n")


@pytest.fixture
def batch(tmp_path: Path) -> tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]]:
    root = tmp_path
    verifier = root / study.VERIFIER
    verifier.parent.mkdir(parents=True)
    verifier.write_text("unchanged verifier")
    cfg: dict[str, Any] = {
        "workspace": "artifacts/native-selection-flows/live",
        "maximum_decisions": 3,
        "implementation_sha256": {study.VERIFIER: _sha_file(verifier)},
        "helpers_sha256": {},
        "cases": [
            {"key": f"player-{p}-world-{w}", "player": p, "seed": f"WORLD{w}"}
            for p in (2, 3)
            for w in (1, 2)
        ],
    }
    context = {"config": cfg, "environment": {"manifest_id": "same-build"}}
    cases = []
    for declared in cfg["cases"]:
        directory = root / cfg["workspace"] / declared["key"]
        for host, filename in (
            ("native", "shared-public.jsonl.gz"),
            ("official", "live-public.jsonl.gz"),
        ):
            write_frames(directory / host / filename, [frame("map"), frame(), frame()])
        cases.append(
            {
                **declared,
                "native": {
                    "status": "native_prefix_pass",
                    "policy_decisions": 3,
                    "shutdown": {"clean_exit": True},
                },
                "official": {
                    "status": "official_prefix_pass",
                    "probe": {"policy_decisions": 3},
                    "checks": dict.fromkeys(study.RESET_CHECKS, True),
                },
                "comparison": {"equal_input_prefix": 3, "complete_prefix_input_equivalence": True},
            }
        )
    report = {
        "schema_version": "native-live-checkpoint-adapter-result-v1",
        "config_id": manifest_identifier(cfg),
        "environment_id": "same-build",
        "implementation_id": manifest_identifier(cfg["implementation_sha256"]),
        "helpers_id": manifest_identifier(cfg["helpers_sha256"]),
        "cases": cases,
        "sources": {study.VERIFIER: _sha_file(verifier)},
        "evidence": {
            str(p.relative_to(root)): _sha_file(p) for p in (root / cfg["workspace"]).rglob("*.gz")
        },
        "game_starts": 8,
        "checkpoint_delivery_exercised": True,
        "optimizer_updates": 0,
        "training_allowed": False,
        "original_weights_and_all_Adam_unchanged": True,
    }
    plan = {
        "workspace": "artifacts/native-selection-flows/coordination",
        "recipe": {"path": "configs/recipe.json"},
        "launch": {"path": "configs/launch.json"},
        "sources": report["sources"],
    }
    return root, plan, context, report


def witness(root: Path, report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "native-live-checkpoint-verification-v1",
        "valid": True,
        "source_report_id": report["report_id"],
        "verifier_sha256": _sha_file(root / study.VERIFIER),
        "cases": [
            {"key": case["key"], "host": host, "verified_decisions": 3}
            for case in report["cases"]
            for host in ("native", "official")
        ],
        "games_launched": 0,
        "optimizer_updates": 0,
        "original_weights_and_all_Adam_unchanged": True,
    }


def test_matching_prefix_reports_observed_transitions_without_inventing_endings(
    batch: tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    root, _, context, report = batch
    assert study.validate_report(context, report)
    result = study.coverage(root, context, report)
    assert result["all_declared_prefixes_or_endings_match"]
    assert result["paired_observed_transitions"] == {"combat -> combat": 4, "map -> combat": 4}
    assert result["genuine_ending_pairs_observed"] == 0
    assert result["unobserved_families_and_endings_are_not_qualified"]
    assert not result["final_uncaptured_successor_equivalence_granted"]


@pytest.mark.parametrize("fault", ["short", "different_ending", "after_ending", "too_many"])
def test_incomplete_or_conflicting_terminal_evidence_never_passes(
    batch: tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]],
    fault: str,
) -> None:
    root, _, context, report = batch
    case = report["cases"][0]
    case["native"]["policy_decisions"] = case["official"]["probe"]["policy_decisions"] = 2
    case["comparison"]["equal_input_prefix"] = 3
    observations = [frame(), frame(), frame("game_over", terminal=True)]
    for host, filename in (
        ("native", "shared-public.jsonl.gz"),
        ("official", "live-public.jsonl.gz"),
    ):
        write_frames(
            root / context["config"]["workspace"] / case["key"] / host / filename, observations
        )
    if fault == "different_ending":
        observations[-1]["ending"]["victory"] = True
    elif fault == "short":
        observations = observations[:2]
        case["comparison"]["equal_input_prefix"] = 2
    elif fault == "after_ending":
        observations = [frame("game_over", terminal=True), frame(), frame()]
    else:
        observations = [frame()] * 5
    write_frames(
        root / context["config"]["workspace"] / case["key"] / "official/live-public.jsonl.gz",
        observations,
    )
    if fault in {"after_ending", "too_many"}:
        with pytest.raises(ValueError):
            study.coverage(root, context, report)
    else:
        assert not study.coverage(root, context, report)["all_declared_prefixes_or_endings_match"]


def test_a_real_matching_ending_may_finish_before_the_decision_limit(
    batch: tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    root, _, context, report = batch
    case = report["cases"][0]
    case["native"]["policy_decisions"] = case["official"]["probe"]["policy_decisions"] = 2
    for host, filename in (
        ("native", "shared-public.jsonl.gz"),
        ("official", "live-public.jsonl.gz"),
    ):
        write_frames(
            root / context["config"]["workspace"] / case["key"] / host / filename,
            [frame(), frame(), frame("game_over", terminal=True)],
        )
    result = study.coverage(root, context, report)
    assert result["all_declared_prefixes_or_endings_match"]
    assert result["genuine_ending_pairs_observed"] == 1


def test_later_states_after_divergence_are_never_counted_as_matched_effects(
    batch: tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    root, _, context, report = batch
    case = report["cases"][0]
    case["comparison"].update(equal_input_prefix=1, complete_prefix_input_equivalence=False)
    result = study.coverage(root, context, report)
    assert not result["all_declared_prefixes_or_endings_match"]
    assert result["cases"][0]["matching_successor_inputs_between_decisions"] == 0
    assert result["paired_observed_transitions"] == {"combat -> combat": 3, "map -> combat": 3}
    assert not result["later_divergent_states_realignable"]


@pytest.mark.parametrize("fault", ["missing_host", "count", "source", "verifier", "updates"])
def test_verification_must_bind_all_choices_and_the_exact_producer(
    batch: tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]],
    fault: str,
) -> None:
    root, _, context, report = batch
    report["report_id"] = "saved-report"
    proof = witness(root, report)
    study.validate_verification(root, context, report, proof)
    if fault == "missing_host":
        proof["cases"].pop()
    elif fault == "count":
        proof["cases"][0]["verified_decisions"] = 2
    elif fault == "source":
        proof["source_report_id"] = "other-report"
    elif fault == "verifier":
        proof["verifier_sha256"] = "other-verifier"
    else:
        proof["optimizer_updates"] = 1
    with pytest.raises(ValueError, match="reconstruction"):
        study.validate_verification(root, context, report, proof)


@pytest.mark.parametrize("fault", ["environment", "case", "reset", "updates"])
def test_drift_or_unverified_reset_blocks_the_result(
    batch: tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]],
    fault: str,
) -> None:
    _, _, context, report = batch
    if fault == "environment":
        report["environment_id"] = "new-build"
    elif fault == "case":
        report["cases"][0]["seed"] = "OTHER"
    elif fault == "reset":
        del report["cases"][0]["official"]["checks"]["natural_shutdown"]
    else:
        report["optimizer_updates"] = 1
    with pytest.raises(ValueError):
        study.validate_report(context, report)


@pytest.mark.parametrize(
    "status,cap", [("capped", None), ("failed", None), ("completed", {"kind": "wall"})]
)
def test_zero_exit_cannot_hide_a_failed_or_capped_verification(status: str, cap: Any) -> None:
    with pytest.raises(ValueError, match="capped"):
        study.check_resource({"status": status, "exit_code": 0, "cap": cap})


def test_clean_pause_resumes_and_saved_results_never_relaunch_games(
    batch: tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, plan, context, raw = batch
    path = root / "plan.json"
    path.write_text(json.dumps(plan))
    calls: list[str] = []

    def child(command: list[str], *, cwd: Path) -> int:
        assert cwd == root
        if command[0] == "bash":
            calls.append("game-batch")
            resource = root / f"artifacts/resources/recipe-attempt-{len(calls)}.json"
            identified(resource, {"status": "completed", "exit_code": 0, "cap": None})
            if calls.count("game-batch") == 2:
                identified(root / context["config"]["workspace"] / "report.json", raw)
        else:
            calls.append("verify")
            saved = read_identified(root / context["config"]["workspace"] / "report.json")
            output = root / plan["workspace"]
            identified(output / "verification-v1/report.json", witness(root, saved))
            identified(
                output / "verification-resources-v1.json",
                {"status": "completed", "exit_code": 0, "cap": None},
            )
        return 0

    monkeypatch.setattr("spireshift.native_broader_compatibility_v1.subprocess.call", child)
    monkeypatch.setattr("spireshift.native_broader_compatibility_v1._running_games", lambda: [])
    first = study.run(root, path, plan, context)
    assert first["status"] == "clean_pause"
    saved = study.run(root, path, plan, context)
    assert saved["status"] == "broader_prefix_compatibility_pass"
    assert calls == ["game-batch", "game-batch", "verify"]
    assert study.run(root, path, plan, context) == saved
    assert calls == ["game-batch", "game-batch", "verify"]
    frozen = copy.deepcopy(saved)
    changed = next((root / context["config"]["workspace"]).rglob("*.gz"))
    changed.write_bytes(b"changed evidence")
    with pytest.raises(ValueError, match="changed"):
        study.run(root, path, plan, context)
    assert read_identified(root / plan["workspace"] / "report.json") == frozen
    assert not saved["training_allowed"] and not saved["broader_live_qualification_granted"]


def test_uncertain_attempt_is_not_retried(
    batch: tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, plan, context, _ = batch
    marker = root / context["config"]["workspace"] / "active.json"
    marker.write_text("uncertain action")

    def never(*args: Any, **kwargs: Any) -> int:
        raise AssertionError("An uncertain seed must never relaunch")

    monkeypatch.setattr("spireshift.native_broader_compatibility_v1.subprocess.call", never)
    with pytest.raises(ValueError, match="uncertain"):
        study.run(root, root / "plan.json", plan, context)
    assert marker.read_text() == "uncertain action"


def test_open_game_refuses_startup_without_creating_a_coordination_marker(
    batch: tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, plan, context, _ = batch
    monkeypatch.setattr("spireshift.native_broader_compatibility_v1._running_games", lambda: [1])
    with pytest.raises(ValueError, match="no coordination marker"):
        study.run(root, root / "plan.json", plan, context)
    assert not (root / plan["workspace"]).exists()
