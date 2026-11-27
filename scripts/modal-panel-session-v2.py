"""Run four finite source-matched controls; reuse results, never replay uncertain cases."""

from __future__ import annotations

import argparse
import json
import runpy
import subprocess
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.engine_working_app import preflight_working_app
from spireshift.full_run_experience import atomic_json
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_inputs_v12 import load
from spireshift.native_launch_limits import load_launch

KINDS = ("reward_glyphs", "status_titles", "modified_deck", "selector_belt")


def clean_delivery(report: dict[str, Any]) -> bool:
    required = {
        "profile_path_logged",
        "Steam_disabled_observed",
        "personal_profile_unchanged",
        "working_app_unchanged",
        "frozen_archive_unchanged",
        "settings_template_unchanged",
        "natural_shutdown",
        "exact_delivery_count",
    }
    cases = report.get("cases", [])
    return bool(cases) and all(
        c["native"]["shutdown"]["clean_exit"] is True
        and required <= set(c["official"]["checks"])
        and all(v is True for v in c["official"]["checks"].values())
        for c in cases
    )


def validate_verification(
    root: Path, context: dict[str, Any], report: dict[str, Any], witness: dict[str, Any]
) -> None:
    """The verifier binds the live report and source hash; it has no evidence map."""
    expected = []
    for case in report["cases"]:
        expected.extend(
            [
                {
                    "key": case["key"],
                    "host": "native",
                    "verified_decisions": case["native"]["policy_decisions"],
                },
                {
                    "key": case["key"],
                    "host": "official",
                    "verified_decisions": case["official"]["probe"]["policy_decisions"],
                },
            ]
        )
    verifier = "src/spireshift/native_flow_verification_v12.py"
    if (
        witness.get("schema_version") != "native-live-checkpoint-verification-v1"
        or witness.get("valid") is not True
        or witness.get("source_report_id") != report["report_id"]
        or witness.get("verifier_sha256") != context["config"]["implementation_sha256"][verifier]
        or witness.get("verifier_sha256") != _sha_file(root / verifier)
        or witness.get("cases") != expected
        or witness.get("games_launched") != 0
        or witness.get("optimizer_updates") != 0
        or witness.get("original_weights_and_all_Adam_unchanged") is not True
    ):
        raise ValueError(
            "Saved verification schema, source, counts or original-state guarantee changed"
        )


def validate_live_report(context: dict[str, Any], report: dict[str, Any]) -> None:
    cfg = context["config"]
    if (
        report.get("schema_version") != "native-live-checkpoint-adapter-result-v1"
        or report.get("config_id") != manifest_identifier(cfg)
        or report.get("environment_id") != context["environment"]["manifest_id"]
        or report.get("implementation_id") != manifest_identifier(cfg["implementation_sha256"])
        or report.get("helpers_id") != manifest_identifier(cfg["helpers_sha256"])
        or [{k: c[k] for k in ("key", "player", "seed")} for c in report.get("cases", [])]
        != cfg["cases"]
    ):
        raise ValueError("Saved live result belongs to a different case or source tuple")


def save_unit(workspace: Path, index: int, body: dict[str, Any]) -> Path:
    path = workspace / "units" / f"{index:02d}.json"
    if path.exists():
        if identified(path) != {**body, "report_id": manifest_identifier(body)}:
            raise ValueError("Saved coordination unit changed; preserve it")
    else:
        atomic_json(path, {**body, "report_id": manifest_identifier(body)})
    return path


def load_panel(root: Path, path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cfg = json.loads(path.read_text())
    if (
        cfg.get("schema_version") != "native-modal-targeted-panel-v2"
        or cfg.get("training_allowed") is not False
        or cfg.get("automatic_follow_up") is not False
        or len(cfg.get("controls", [])) != 4
        or not (root / cfg["workspace"])
        .resolve()
        .is_relative_to(root / "artifacts/native-selection-flows")
    ):
        raise ValueError("Use the finite four-control plan")
    check_sources(root, cfg["sources"])
    parent_path = verified(root, cfg["parent_plan"])
    parent = json.loads(parent_path.read_text())
    stopped = identified(verified(root, cfg["preserved_parent_report"]))
    verified(root, cfg["preserved_parent_marker"])
    if (
        parent.get("schema_version") != "native-modal-targeted-panel-v1"
        or stopped.get("config_id") != manifest_identifier(parent)
        or stopped.get("status") != "stopped_preserving_evidence"
        or stopped.get("error") != "'evidence'"
        or cfg["controls"] != parent["controls"]
        or cfg["reviewed_worker_reset"] != parent["reviewed_worker_reset"]
        or cfg["workspace"] == parent["workspace"]
    ):
        raise ValueError("Continue only the unchanged finite plan after its metadata failure")
    check_sources(root, stopped["sources"])
    check_sources(root, stopped["evidence"])
    reset = identified(verified(root, cfg["reviewed_worker_reset"]))
    if reset.get(
        "status"
    ) != "restored_to_frozen_baseline_after_explicit_owner_review" or not reset.get("valid"):
        raise ValueError("The inspected stopped worker has not been explicitly restored")
    contexts = []
    for kind, item in zip(KINDS, cfg["controls"], strict=True):
        recipe = verified(root, item["recipe"])
        context = load(root, recipe)
        if (
            context["config"]["control_kind"] != kind
            or context["config"]["maximum_case_wall_seconds"] != 600
        ):
            raise ValueError("Targeted control membership or time allowance changed")
        load_launch(root, verified(root, item["launch"]), recipe, context["config"])
        contexts.append(context)
    if len({v["environment"]["manifest_id"] for v in contexts}) != 1:
        raise ValueError("All controls must use the same source and input tuple")
    return cfg, contexts


def run(
    root: Path,
    path: Path,
    cfg: dict[str, Any],
    contexts: list[dict[str, Any]],
    *,
    allow_games: bool = True,
) -> dict[str, Any]:
    workspace = root / cfg["workspace"]
    final = workspace / "report.json"
    if final.exists():
        result = identified(final)
        if result["config_id"] != manifest_identifier(cfg):
            raise ValueError("The saved panel belongs to different settings")
        check_sources(root, result["sources"])
        check_sources(root, result["evidence"])
        print("Showing the saved panel; no game starts.", flush=True)
        return result
    if (workspace / "active.json").exists():
        raise ValueError("Preserve the interrupted panel; do not replay its uncertain cases")
    from spireshift.engine_native import _running_games

    if allow_games and _running_games():
        raise ValueError("Close STS2 before continuing; no coordination marker created")
    preflight_working_app(contexts[0]["working_app"])
    workspace.mkdir(parents=True, exist_ok=True)
    marker = workspace / "active.json"
    atomic_json(marker, {"config_id": manifest_identifier(cfg), "optimizer_updates": 0})
    started = time.monotonic()
    results: list[dict[str, Any]] = []
    evidence: dict[str, str] = {}
    error = None
    saved_only_pause = False
    new_controls_this_session = 0
    try:
        for index, (item, context) in enumerate(zip(cfg["controls"], contexts, strict=True), 1):
            case_workspace = root / context["config"]["workspace"]
            source = case_workspace / "report.json"
            if (case_workspace / "active.json").exists():
                raise ValueError("The unfinished case remains preserved; no retry is allowed")
            if not source.exists():
                if not allow_games:
                    saved_only_pause = True
                    break
                if case_workspace.exists() and any(case_workspace.iterdir()):
                    raise ValueError("The case has unfinished files; preserve it without retry")
                if (case_workspace / "active.json").exists():
                    raise ValueError("The unfinished case remains preserved; no retry is allowed")
                print(
                    f"Control {index}/4: {KINDS[index - 1]}; ten-minute case allowance; "
                    "separate shutdown reserve.",
                    flush=True,
                )
                new_controls_this_session += 1
                code = subprocess.call(
                    [
                        "bash",
                        str(root / "scripts/check-selection-flows-v12.sh"),
                        item["recipe"]["path"],
                        item["launch"]["path"],
                    ],
                    cwd=root,
                )
                if not source.exists():
                    raise ValueError(
                        f"Control {index} stopped before a clean result (exit {code}); "
                        "preserve its worker"
                    )
            report = identified(source)
            validate_live_report(context, report)
            if not clean_delivery(report):
                raise ValueError(
                    "The official worker did not restore cleanly; later cases are not started"
                )
            check_sources(root, report["sources"])
            check_sources(root, report["evidence"])
            if report.get("checkpoint_delivery_exercised") is not True:
                evidence.update(report["sources"])
                evidence.update(report["evidence"])
                evidence[str(source.relative_to(root))] = _sha_file(source)
                results.append(
                    {
                        "kind": KINDS[index - 1],
                        "full_inputs_match": False,
                        "equal_choices": report["cases"][0]["comparison"]["equal_input_prefix"],
                        "report_id": report["report_id"],
                        "verification_id": None,
                        "clean_worker_reset": True,
                        "delivery_blocked": True,
                    }
                )
                print(
                    f"Control {index}/4 delivery blocked; clean reset verified. "
                    "Recording the gap and continuing the next independent case.",
                    flush=True,
                )
                continue
            witness_path = case_workspace / "verification-v1/report.json"
            resource = root / "artifacts/resources" / f"map-settling-control-{index}-verify-v1.json"
            if not witness_path.exists():
                if not allow_games:
                    raise ValueError("Saved-only adoption requires a completed verification")
                if resource.exists():
                    raise ValueError(
                        "Preserve the incomplete verification; no overwrite or automatic retry"
                    )
                code = subprocess.call(
                    [
                        "uv",
                        "run",
                        "--no-sync",
                        "spireshift",
                        "resources",
                        "run",
                        "--kind",
                        "other",
                        "--report",
                        str(resource),
                        "--artifact-root",
                        str(case_workspace / "verification-v1"),
                        "--workers",
                        "1",
                        "--max-wall-seconds",
                        "180",
                        "--max-cpu-seconds",
                        "360",
                        "--max-memory-bytes",
                        "4000000000",
                        "--max-storage-bytes",
                        "1000000000",
                        "--",
                        "uv",
                        "run",
                        "--no-sync",
                        "python",
                        "-m",
                        "spireshift.native_flow_verification_v12",
                        item["recipe"]["path"],
                        str(case_workspace / "verification-v1"),
                    ],
                    cwd=root,
                )
                if code or not witness_path.exists():
                    raise ValueError(
                        "Saved-record verification did not complete; preserve its partial result"
                    )
            verified_run = identified(resource)
            if (
                verified_run.get("status") != "completed"
                or verified_run.get("exit_code") != 0
                or verified_run.get("cap") is not None
            ):
                raise ValueError("Saved verification exceeded its budget or failed")
            witness = identified(witness_path)
            validate_verification(root, context, report, witness)
            evidence.update(report["sources"])
            evidence.update(report["evidence"])
            for p in [source, witness_path, resource]:
                evidence[str(p.relative_to(root))] = _sha_file(p)
            results.append(
                {
                    "kind": KINDS[index - 1],
                    "full_inputs_match": report["full_prefix_input_equivalence"],
                    "equal_choices": report["cases"][0]["comparison"]["equal_input_prefix"],
                    "report_id": report["report_id"],
                    "verification_id": witness["report_id"],
                    "clean_worker_reset": True,
                    "target_prefix_reached": all(
                        c["verified_decisions"] == context["config"]["maximum_decisions"]
                        for c in witness["cases"]
                    ),
                }
            )
            unit = save_unit(
                workspace,
                index,
                {
                    "schema_version": "native-modal-coordination-unit-v2",
                    "config_id": manifest_identifier(cfg),
                    "result": results[-1],
                    "source_report": str(source.relative_to(root)),
                    "source_sha256": _sha_file(source),
                    "verification": str(witness_path.relative_to(root)),
                    "verification_sha256": _sha_file(witness_path),
                    "verification_resource": str(resource.relative_to(root)),
                    "verification_resource_sha256": _sha_file(resource),
                },
            )
            evidence[str(unit.relative_to(root))] = _sha_file(unit)
            print(
                f"Control {index}/4 saved and verified: "
                f"{'INPUTS MATCH' if results[-1]['full_inputs_match'] else 'INPUT MISMATCH'}; "
                "zero optimizer updates.",
                flush=True,
            )
    except (ValueError, OSError, KeyError) as failure:
        error = str(failure)
    check_sources(root, cfg["sources"])
    complete = len(results) == 4 and error is None
    body = {
        "schema_version": "native-modal-targeted-panel-result-v2",
        "config_id": manifest_identifier(cfg),
        "status": "targeted_panel_pass"
        if complete
        and all(v["full_inputs_match"] and v.get("target_prefix_reached") is True for v in results)
        else "targeted_panel_completed_with_mismatches"
        if complete
        else "saved_progress_ready"
        if saved_only_pause and error is None
        else "stopped_preserving_evidence",
        "planned_controls": 4,
        "completed_controls": len(results),
        "remaining_controls": 4 - len(results),
        "new_control_launches_this_session": new_controls_this_session,
        "new_game_starts_this_session": 2 * new_controls_this_session if error is None else None,
        "original_finite_plan_id": manifest_identifier(
            json.loads(verified(root, cfg["parent_plan"]).read_text())
        ),
        "preserved_parent_marker": cfg["preserved_parent_marker"],
        "controls": results,
        "error": error,
        "all_original_weights_and_Adam_unchanged": True,
        "optimizer_updates": 0,
        "game_apps_created": 0,
        "training_allowed": False,
        "automatic_follow_up": False,
        "checkpoint_promoted": False,
        "broader_live_qualification_granted": False,
        "wall_seconds": time.monotonic() - started,
        "sources": {**cfg["sources"], str(path.relative_to(root)): _sha_file(path)},
        "evidence": evidence,
    }
    if saved_only_pause and error is None:
        pauses = len(list(workspace.glob("saved-progress-*.json"))) + 1
        output = workspace / f"saved-progress-{pauses}.json"
        atomic_json(output, {**body, "report_id": manifest_identifier(body)})
        marker.rename(workspace / f"saved-only-complete-{pauses}.json")
        return identified(output)
    atomic_json(final, {**body, "report_id": manifest_identifier(body)})
    if complete:
        marker.rename(workspace / "complete.json")
    return identified(final)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--saved-only", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    path = args.recipe.resolve()
    cfg, contexts = load_panel(root, path)
    if args.preflight:
        preflight_working_app(contexts[0]["working_app"])
        print(
            json.dumps(
                {"valid": True, "planned_controls": 4, "games_launched": 0, "optimizer_updates": 0}
            )
        )
        return 0
    if not args.saved_only:
        runpy.run_path(str(root / "scripts/selection-flows-session-v12.py"))["check_repository"](
            root
        )
    report = run(root, path, cfg, contexts, allow_games=not args.saved_only)
    print(
        json.dumps({k: v for k, v in report.items() if k not in {"sources", "evidence"}}, indent=2)
    )
    return 0 if report["status"] in {"targeted_panel_pass", "saved_progress_ready"} else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError) as error:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(error)}))
        raise SystemExit(2) from error
