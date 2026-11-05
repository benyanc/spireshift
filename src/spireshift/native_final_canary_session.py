"""Exact-final, six-pair compatibility-only owner session on the frozen study."""

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
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_curriculum_evaluate import canary, require_canaries
from spireshift.native_curriculum_policy import policy
from spireshift.native_curriculum_store import final, journal
from spireshift.native_fitting_session import LAUNCH as FITTING_LAUNCH
from spireshift.native_fitting_session import frozen_checks as fitting_frozen_checks
from spireshift.native_fitting_session import prepare as prepare_fitting
from spireshift.native_structured_state import load

LAUNCH = "configs/native-curriculum/sts2-v0.111.0-a8-varied-final-canaries-launch-v1.json"
SCHEMA = "native-varied-exact-final-canary-launch-v1"
OPERATION = "qualify_six_declared_final_policy_modes_only"
LIMITS = {
    "wall_seconds": 4200,
    "cpu_seconds": 7200,
    "resident_memory_bytes": 4000000000,
    "storage_bytes": 4000000000,
}
BUDGET = {
    "pairs": 6,
    "hosts": 12,
    "maximum_pair_wall_seconds": 600,
    "whole_run_cpu_seconds": 128,
    "maximum_decisions": 384,
    "optimizer_updates": 0,
}
FILES = (
    "src/spireshift/native_final_canary_session.py",
    "scripts/compare-varied-finals-v1.sh",
    "scripts/varied-final-canaries-session-v1.py",
    "tests/unit/test_native_final_canary_session.py",
)


def implementation(root: Path) -> dict[str, str]:
    return {name: _sha_file(root / name) for name in FILES}


def binding(launch: dict[str, Any]) -> str:
    return manifest_identifier({k: v for k, v in launch.items() if k != "short_check"})


def read_launch(root: Path, path: Path) -> dict[str, Any]:
    launch: dict[str, Any] = json.loads(path.read_text())
    if (
        launch.get("schema_version") != SCHEMA
        or launch.get("operation") != OPERATION
        or launch.get("budget") != BUDGET
        or launch.get("session_limits") != LIMITS
        or launch.get("implementation") != implementation(root)
        or launch.get("fitting_launch", {}).get("path") != FITTING_LAUNCH
        or launch.get("automatic_follow_up") is not False
    ):
        raise ValueError("Use the exact six-pair, zero-update, compatibility-only launch")
    verified(root, launch["fitting_launch"])
    return launch


def require_assessed_finals(
    context: dict[str, Any],
    launch: dict[str, Any],
    assessed: dict[str, Any],
    fitted: dict[str, Any],
) -> None:
    if (
        assessed.get("status")
        != "all_256_updates_full_Adam_and_fixed_finals_independently_reconstructed"
        or launch.get("config_id") != context["config_id"]
        or assessed.get("config_id") != context["config_id"]
        or fitted.get("config_id") != context["config_id"]
        or fitted.get("status") != "diagnostic_finals_frozen"
        or fitted.get("optimizer_updates") != 256
        or assessed.get("source_report_id") != fitted.get("report_id")
        or assessed.get("frozen_finals_id") != fitted.get("frozen_finals_id")
        or launch.get("frozen_finals_id") != fitted.get("frozen_finals_id")
        or assessed.get("bank_id") != fitted.get("bank_id")
        or assessed.get("environment_id") != context["environment"]["manifest_id"]
        or assessed.get("guard_receipt_id") != context["guard_receipt"]["report_id"]
        or assessed.get("sealed_units_verified") != 67
        or assessed.get("unique_checkpoint_recorded_regressions_verified") != 66
        or assessed.get("registered_main_optimizer_updates") != 256
        or assessed.get("separate_numerical_reconstruction_steps") != 256
        or assessed.get("all_original_weights_and_full_Adam_unchanged") is not True
        or assessed.get("no_evaluation_used_for_final_selection") is not True
        or assessed.get("new_checkpoint_live_delivery_qualified") is not False
        or fitted.get("new_checkpoint_live_delivery_qualified") is not False
    ):
        raise ValueError("The independently assessed exact epoch-16 finals are required")
    if launch["cases"] != context["config"]["plan"]["canary_cases"] or len(launch["cases"]) != 6:
        raise ValueError("Preserve the prospectively fixed six players, modes and fresh worlds")
    plan = context["config"]["plan"]
    for key in ["maximum_pair_wall_seconds", "whole_run_cpu_seconds", "maximum_decisions"]:
        if plan[key] != BUDGET[key]:
            raise ValueError("Per-pair, whole-game CPU or choice guards changed")


def verify_final_files(
    context: dict[str, Any], launch: dict[str, Any], fitted: dict[str, Any]
) -> None:
    root = context["qualification"].root
    expected = {f"p{p}-{a}" for p in [2, 3] for a in ["original", "reference", "teacher"]}
    if set(launch["finals"]) != expected or set(fitted["finals"]) != expected:
        raise ValueError("Bind all four fitted finals and both original routing anchors")
    for name, ref in launch["finals"].items():
        saved = fitted["finals"][name]
        if ref["path"] != saved["state_path"] or any(
            ref[k] != saved[k] for k in ["state_id", "model_id", "optimizer_id", "optimizer_steps"]
        ):
            raise ValueError("A final or its complete Adam binding was substituted")
        model, adam, sid = load(verified(root, ref))
        if (
            sid != ref["state_id"]
            or model.model_id != ref["model_id"]
            or manifest_identifier(adam.as_dict()) != ref["optimizer_id"]
            or adam.steps != ref["optimizer_steps"]
        ):
            raise ValueError("Current final model/full Adam differs from its assessed state")
        p = int(name[1])
        baseline = context["adams"][p].steps
        if adam.steps != baseline + (0 if name.endswith("original") else 64):
            raise ValueError("A nonfinal epoch or changed original routing anchor was supplied")
        if name.endswith("original") and (
            model.as_dict() != context["models"][p].as_dict()
            or adam.as_dict() != context["adams"][p].as_dict()
        ):
            raise ValueError("The original noncombat anchor changed numerical weights or Adam")
    for case in launch["cases"]:
        policy(
            context, case["player"], case["variant"], "static-final-binding-check", fitted["finals"]
        )


def require_short_check(report: dict[str, Any], launch: dict[str, Any]) -> None:
    if (
        report.get("status") != "all_six_exact_modes_saved_inputs_verified"
        or report.get("launch_binding_id") != binding(launch)
        or report.get("saved_mode_menu_comparisons") != 6 * 292
        or report.get("new_games") != 0
        or report.get("optimizer_updates") != 0
        or report.get("planned_canary_worlds_used") is not False
        or report.get("live_qualification_granted") is not False
        or not report.get("checks")
        or not all(report["checks"].values())
    ):
        raise ValueError(
            "The exact-final saved-mode short check must pass without consuming worlds"
        )


def prepare(root: Path, path: Path, *, require_short: bool = True) -> dict[str, Any]:
    launch = read_launch(root, path)
    context = prepare_fitting(root, verified(root, launch["fitting_launch"]))
    assessed = identified(verified(root, launch["fitting_assessment"]))
    resource = identified(verified(root, launch["assessment_resource"]))
    if (
        resource["status"] != "completed"
        or resource["exit_code"] != 0
        or resource["cap"] is not None
    ):
        raise ValueError("The full saved-fitting assessment did not finish cleanly")
    check_sources(root, assessed["sources"])
    check_sources(root, assessed["evidence"])
    fitted = final(context, "fitting")
    if fitted is None:
        raise ValueError("Require the completed fitting report; this launcher never fits")
    fitted_path = root / context["config"]["workspace"] / "fitting/report.json"
    if verified(root, launch["fitting_report"]).resolve() != fitted_path.resolve():
        raise ValueError("The canary launcher must name the exact completed fitting report")
    require_assessed_finals(context, launch, assessed, fitted)
    verify_final_files(context, launch, fitted)
    refs = [
        launch[n]
        for n in [
            "fitting_launch",
            "fitting_assessment",
            "fitting_report",
            "assessment_resource",
            "protection",
        ]
    ]
    refs.extend(launch["finals"].values())
    if require_short:
        short = launch["short_check"]
        report = identified(verified(root, short["report"]))
        require_short_check(report, launch)
        check_sources(root, report["sources"])
        check_sources(root, report["evidence"])
        res = identified(verified(root, short["resource"]))
        if res["status"] != "completed" or res["exit_code"] != 0 or res["cap"] is not None:
            raise ValueError("The saved-mode short check failed or capped")
        refs.extend([short["report"], short["resource"]])
    context["sources"] = {
        **context["sources"],
        **launch["implementation"],
        **{r["path"]: r["sha256"] for r in refs},
        str(path.relative_to(root)): _sha_file(path),
    }
    context.update(canary_launch=launch, canary_launch_path=path, canary_fitted=fitted)
    verify_resume(context)
    return context


def scope(context: dict[str, Any]) -> dict[str, Any]:
    launch = context["canary_launch"]
    body = {
        "schema_version": "exact-final-canary-attempt-scope-v1",
        "operation": OPERATION,
        "launch_binding_id": binding(launch),
        "config_id": context["config_id"],
        "frozen_finals_id": launch["frozen_finals_id"],
        "finals": launch["finals"],
        "cases": launch["cases"],
        "budget": BUDGET,
        "session_limits": LIMITS,
        "prior_live_qualification_inherited": False,
        "training_allowed": False,
        "promotion_allowed": False,
        "automatic_follow_up": False,
    }
    return {**body, "report_id": manifest_identifier(body)}


def verify_resume(context: dict[str, Any]) -> int:
    root, cfg, launch = context["qualification"].root, context["config"], context["canary_launch"]
    store = journal(context, "canaries")
    if not store.workspace.exists():
        return 0
    declared = root / cfg["workspace"] / "canary-launch/scope.json"
    if not declared.is_file() or identified(declared) != scope(context):
        raise ValueError("Existing canary evidence has no exact current attempt scope; preserve it")
    expected = {c["key"] for c in launch["cases"]}
    chunks = store.workspace / "chunks"
    if chunks.exists() and any(p.name not in expected for p in chunks.iterdir()):
        raise ValueError("Unexpected canary evidence must be inspected, not cleared")
    sealed, gap = 0, False
    for case in launch["cases"]:
        request = {
            "case": case,
            "frozen_finals_id": launch["frozen_finals_id"],
            "guard_id": context["guard_receipt"]["report_id"],
        }
        receipt = store.completed(case["key"], request)
        if receipt is None:
            gap = True
            continue
        if gap or receipt["sources"].get(
            str(context["canary_launch_path"].relative_to(root))
        ) != _sha_file(context["canary_launch_path"]):
            raise ValueError("Canary prefix order or exact launcher binding changed")
        result = receipt["result"]
        if (
            result.get("case") != case
            or result.get("status") != "matching_genuine_endings"
            or result.get("clean_reset") is not True
        ):
            raise ValueError("An incomplete prefix cannot qualify or be replayed")
        sealed += 1
    return sealed


def frozen_checks(context: dict[str, Any]) -> dict[str, bool]:
    checks = fitting_frozen_checks(context)
    root, launch = context["qualification"].root, context["canary_launch"]
    check_sources(root, json.loads(verified(root, launch["protection"]).read_text()))
    verify_final_files(context, launch, context["canary_fitted"])
    return {**checks, "all_protected_finals_and_originals_exact": True}


def snapshot(context: dict[str, Any]) -> Path:
    root, cfg, launch = context["qualification"].root, context["config"], context["canary_launch"]
    target: Path = root / cfg["workspace"] / "canary-launch"
    names = {
        **launch["implementation"],
        str(context["canary_launch_path"].relative_to(root)): _sha_file(
            context["canary_launch_path"]
        ),
    }
    for name, digest in names.items():
        dest = target / "source-at-launch" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            if _sha_file(dest) != digest:
                raise ValueError("Preserve changed canary-launch source snapshots")
        else:
            with dest.open("xb") as handle:
                handle.write((root / name).read_bytes())
    declared = target / "scope.json"
    if declared.exists():
        if identified(declared) != scope(context):
            raise ValueError("Preserve a changed exact-final attempt scope")
    else:
        with declared.open("x") as handle:
            handle.write(json.dumps(scope(context), indent=2, sort_keys=True) + "\n")
    context["sources"] = {
        **context["sources"],
        str(declared.relative_to(root)): _sha_file(declared),
    }
    return target


def require_result(context: dict[str, Any], result: dict[str, Any]) -> None:
    launch = context["canary_launch"]
    require_canaries(result, context["config_id"], launch["frozen_finals_id"], launch["cases"])
    if result.get("optimizer_updates") != 0 or result.get("broader_live_admission") is not False:
        raise ValueError("Canary results cannot grant training or broader live admission")


def resource_command(root: Path, path: Path, attempt: int) -> list[str]:
    launch = read_launch(root, path)
    fitting_launch = json.loads(verified(root, launch["fitting_launch"]).read_text())
    cfg = json.loads(verified(root, fitting_launch["recipe"]).read_text())
    command = [
        "uv",
        "run",
        "--no-sync",
        "spireshift",
        "resources",
        "run",
        "--kind",
        "other",
        "--report",
        f"artifacts/resources/varied-final-canaries-v1-attempt-{attempt}.json",
        "--artifact-root",
        str(Path(cfg["workspace"]) / "canaries"),
        "--artifact-root",
        str(Path(cfg["workspace"]) / "canary-launch"),
        "--workers",
        "1",
    ]
    for option, key in [
        ("--max-wall-seconds", "wall_seconds"),
        ("--max-cpu-seconds", "cpu_seconds"),
        ("--max-memory-bytes", "resident_memory_bytes"),
        ("--max-storage-bytes", "storage_bytes"),
    ]:
        command.extend([option, str(launch["session_limits"][key])])
    return [
        *command,
        "--",
        "uv",
        "run",
        "--no-sync",
        "python",
        "-m",
        "spireshift.native_final_canary_session",
        str(path.relative_to(root)),
    ]


def owner_main(root: Path) -> int:
    path = root / LAUNCH
    read_launch(root, path)
    print(
        "Close STS2. Six fresh native/official pairs for the exact assessed epoch-16 finals.",
        flush=True,
    )
    print(
        "Frozen v0.111.0 / 41cef1ea; CLI56 / Connector31 / worker24 / converter16 / layout12.",
        flush=True,
    )
    print(
        "Reference, teacher and same-teacher/original-noncombat modes; both initializers.",
        flush=True,
    )
    print("Allow about 25–45 minutes; 70-minute outer cap, 10 minutes per pair.", flush=True)
    print(
        "Each host retains 128 gameplay CPU seconds / 384 choices. "
        "Genuine matching endings required.",
        flush=True,
    )
    print(
        "Original/full final weights and Adam stay fixed. Zero updates; no fitting or evaluation.",
        flush=True,
    )
    print(
        "Clean seals resume; incomplete or uncertain cases are preserved without retry. Then stop.",
        flush=True,
    )
    runpy.run_path(str(root / "scripts/selection-flows-session-v12.py"))["check_repository"](root)
    attempt = 1
    while (root / f"artifacts/resources/varied-final-canaries-v1-attempt-{attempt}.json").exists():
        attempt += 1
    return subprocess.run(resource_command(root, path, attempt), cwd=root, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("launch", type=Path)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    try:
        context = prepare(root, args.launch.resolve())
        before = frozen_checks(context)
        if args.preflight:
            print(
                json.dumps(
                    {
                        "valid": True,
                        "operation": OPERATION,
                        "pairs": 6,
                        "frozen_finals_id": context["canary_launch"]["frozen_finals_id"],
                        "new_games": 0,
                        "optimizer_updates": 0,
                        "automatic_follow_up": False,
                    }
                )
            )
            return 0
        target = snapshot(context)
        result = canary(context, deadline=started + LIMITS["wall_seconds"] - 45)
        after = frozen_checks(context)
        if result["status"] == "trained_policy_canaries_verified":
            require_result(context, result)
        elif result["status"] != "clean_session_boundary":
            raise ValueError("An incomplete canary panel cannot qualify these policy modes")
        receipt = {
            "schema_version": "exact-final-canary-session-receipt-v1",
            "launch_binding_id": binding(context["canary_launch"]),
            "status": result["status"],
            "canary_report_id": result.get("report_id"),
            "checks_before": before,
            "checks_after": after,
            "optimizer_updates": 0,
            "automatic_follow_up": False,
            "wall_seconds": time.monotonic() - started,
        }
        receipt["report_id"] = manifest_identifier(receipt)
        n = 1
        while True:
            try:
                with (target / f"session-{n}.json").open("x") as handle:
                    handle.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
                break
            except FileExistsError:
                n += 1
        print(
            json.dumps(
                {k: v for k, v in result.items() if k not in {"sources", "evidence"}}, indent=2
            )
        )
        return 0
    except (ValueError, OSError, KeyError) as error:
        print(
            json.dumps(
                {
                    "status": "stopped_preserving_evidence",
                    "error": str(error),
                    "optimizer_updates": 0,
                    "automatic_follow_up": False,
                }
            ),
            flush=True,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
