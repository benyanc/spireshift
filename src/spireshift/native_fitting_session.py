"""Assessed-bank, fitting-only owner session around the unchanged fixed study."""

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
from spireshift.engine_qualification import _sha_file, verify_game_archive
from spireshift.engine_worker_qualification import immutable_checks
from spireshift.engine_working_app import preflight_working_app
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_curriculum_config import execution_runtime, load
from spireshift.native_curriculum_fit import fit
from spireshift.native_curriculum_store import final
from spireshift.native_curriculum_study import require_control
from spireshift.native_learner_guard import require_scope

LAUNCH = "configs/native-curriculum/sts2-v0.111.0-a8-varied-fitting-launch-v1.json"
RECIPE = "configs/native-curriculum/sts2-v0.111.0-a8-varied-v1.json"
SCHEMA = "native-varied-fitting-only-launch-v1"
WORK = {"copies": 4, "updates_per_copy": 64, "draws_per_copy": 2048, "total_updates": 256}
FILES = (
    "src/spireshift/native_fitting_session.py",
    "scripts/fit-varied-teaching-v1.sh",
    "scripts/varied-fitting-session-v1.py",
    "tests/unit/test_native_fitting_session.py",
)


def implementation(root: Path) -> dict[str, str]:
    return {n: _sha_file(root / n) for n in FILES}


def binding(launch: dict[str, Any]) -> str:
    # The short check is bound to all execution inputs; its own resulting
    # report/resource references are added only after it completes.
    return manifest_identifier({k: v for k, v in launch.items() if k != "short_check"})


def read_launch(root: Path, path: Path) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    launch = json.loads(path.read_text())
    if (
        launch.get("schema_version") != SCHEMA
        or launch.get("phase") != "fit_only"
        or launch.get("work") != WORK
        or launch.get("recipe", {}).get("path") != RECIPE
        or launch.get("implementation") != implementation(root)
        or launch.get("automatic_follow_up") is not False
    ):
        raise ValueError("Use the exact assessed-bank, four-copy fitting-only launcher")
    recipe = verified(root, launch["recipe"])
    cfg = json.loads(recipe.read_text())
    if (
        manifest_identifier(cfg) != launch["config_id"]
        or cfg["stage"] != "bounded_study"
        or launch["session_limits"] != cfg["session_limits"]
        or launch["session_limits"]
        != {
            "wall_seconds": 1800,
            "cpu_seconds": 3600,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 4000000000,
        }
        or cfg["plan"]["learning"]["epochs"] * cfg["plan"]["learning"]["steps_per_epoch"] != 64
        or cfg["plan"]["learning"]["batch_choices"] != 32
    ):
        raise ValueError("The saved study, optimizer work or finite session limits changed")
    workspace = Path(cfg["workspace"])
    if workspace.is_absolute() or not (root / workspace).resolve().is_relative_to(
        root / "artifacts/native-varied-teaching"
    ):
        raise ValueError("Use the fitting workspace read from the pinned study recipe")
    return launch, recipe, cfg


def require_assessed_bank(
    context: dict[str, Any],
    assessment: dict[str, Any],
    collection: dict[str, Any],
    curriculum: dict[str, Any],
) -> None:
    if (
        assessment.get("status")
        != "finite_curriculum_independently_verified_ready_for_declared_copy_fitting"
        or assessment.get("config_id") != context["config_id"]
        or collection.get("config_id") != context["config_id"]
        or assessment.get("source_report_id") != collection.get("report_id")
        or assessment.get("bank_id") != curriculum.get("bank_id")
        or collection.get("bank_id") != curriculum.get("bank_id")
        or assessment.get("guard_receipt_id") != context["guard_receipt"]["report_id"]
        or assessment.get("environment_id") != context["environment"]["manifest_id"]
        or collection.get("status") != "curriculum_qualified"
        or assessment.get("actual_selection_and_complete_lesson_bank_reconstructed") is not True
        or assessment.get("original_weights_and_complete_Adam_unchanged") is not True
        or assessment.get("capped_proposals_supply_no_labels") is not True
        or collection.get("all_natural_sources_clean") is not True
        or collection.get("all_prospective_withheld_worlds_have_public_roots") is not True
        or collection.get("fitting_started") is not False
        or collection.get("optimizer_updates") != 0
        or curriculum.get("control_only") is not False
        or curriculum.get("heldout_labels_or_outcomes_used") is not False
        or curriculum.get("student_inputs_public_only") is not True
        or curriculum.get("quality", {}).get("passed") is not True
    ):
        raise ValueError("The exact independently assessed, public fitting-only bank is required")
    cases = context["config"]["plan"]["worlds"]
    fitting = {c["seed"] for c in cases if c["partition"] == "fit"}
    withheld = {c["seed"] for c in cases if c["partition"] == "heldout"}
    if not curriculum["lessons"] or any(
        lesson["partition"] != "fit"
        or lesson["world"] not in fitting
        or lesson["world"] in withheld
        for lesson in curriculum["lessons"]
    ):
        raise ValueError("A control, withheld or foreign world entered fitting labels")


def require_short_check(report: dict[str, Any], launch: dict[str, Any]) -> None:
    if (
        report.get("status") != "assessed_bank_fitting_control_pass"
        or report.get("launch_binding_id") != binding(launch)
        or report.get("matched_copy_optimizer_updates") != 16
        or report.get("resume_fork_optimizer_updates") != 4
        or report.get("separate_numerical_reconstruction_steps") != 4
        or report.get("main_fitting_started") is not False
        or report.get("control_finals_enter_main") is not False
        or not report.get("checks")
        or not all(report["checks"].values())
    ):
        raise ValueError("The exact assessed-bank warm-Adam fitting control must pass first")


def prepare(root: Path, path: Path, *, require_short: bool = True) -> dict[str, Any]:
    launch, recipe, _ = read_launch(root, path)
    context = load(root, recipe)
    require_control(context)
    require_scope(context["guard_receipt"], context["guard_binding"], "fit_diagnostic_copy")
    assessment = identified(verified(root, launch["assessment"]))
    assessment_resource = identified(verified(root, launch["assessment_resource"]))
    if (
        assessment_resource["status"] != "completed"
        or assessment_resource["exit_code"] != 0
        or assessment_resource["cap"] is not None
    ):
        raise ValueError("Saved collection assessment did not finish cleanly")
    check_sources(root, assessment["sources"])
    check_sources(root, assessment["evidence"])
    collection = final(context, "collection")
    if collection is None:
        raise ValueError("Preserve the completed collection; do not recollect in this launcher")
    curriculum = identified(verified(root, launch["bank"]), "bank_id")
    if (root / collection["bank_path"]).resolve() != verified(root, launch["bank"]).resolve():
        raise ValueError("The launcher and completed collection name different banks")
    require_assessed_bank(context, assessment, collection, curriculum)
    refs = [launch[n] for n in ["assessment", "assessment_resource", "bank", "protection"]]
    if require_short:
        report_ref, resource_ref = (
            launch["short_check"]["report"],
            launch["short_check"]["resource"],
        )
        report = identified(verified(root, report_ref))
        require_short_check(report, launch)
        check_sources(root, report["sources"])
        check_sources(root, report["evidence"])
        resource = identified(verified(root, resource_ref))
        if (
            resource["status"] != "completed"
            or resource["exit_code"] != 0
            or resource["cap"] is not None
        ):
            raise ValueError("The fitting control resource receipt failed or capped")
        refs.extend([report_ref, resource_ref])
    context["sources"] = {
        **context["sources"],
        **launch["implementation"],
        **{r["path"]: r["sha256"] for r in refs},
        str(path.relative_to(root)): _sha_file(path),
    }
    context.update(
        fitting_launch=launch,
        fitting_launch_path=path,
        fitting_bank=curriculum,
        fitting_collection=collection,
    )
    return context


def frozen_checks(context: dict[str, Any]) -> dict[str, Any]:
    root, cfg, launch = context["qualification"].root, context["config"], context["fitting_launch"]
    check_sources(root, context["sources"])
    check_sources(root, json.loads(verified(root, launch["protection"]).read_text()))
    checks = immutable_checks(context["qualification"], context["native"])
    checks["game_archive_verified"] = verify_game_archive(
        context["qualification"], context["native"]["archive"]
    )["valid"]
    checks["execution_runtime_exact"] = cfg["execution_runtime"] == execution_runtime(cfg["node"])
    if not all(checks.values()):
        raise ValueError("Frozen game, CLI, runtime, sources or original weights/Adam changed")
    preflight_working_app(context["working_app"])
    return checks


def snapshot_launch(context: dict[str, Any]) -> Path:
    root, cfg, launch = context["qualification"].root, context["config"], context["fitting_launch"]
    target: Path = root / cfg["workspace"] / "fitting-launch"
    names = {
        **launch["implementation"],
        str(context["fitting_launch_path"].relative_to(root)): _sha_file(
            context["fitting_launch_path"]
        ),
    }
    for name, digest in names.items():
        dest = target / "source-at-launch" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            if _sha_file(dest) != digest:
                raise ValueError("Preserve a changed fitting-launch source snapshot")
        else:
            with dest.open("xb") as handle:
                handle.write((root / name).read_bytes())
    return target


def resource_command(root: Path, launch_path: Path, attempt: int) -> list[str]:
    launch, _, cfg = read_launch(root, launch_path)
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
        f"artifacts/resources/varied-fitting-v1-attempt-{attempt}.json",
        "--artifact-root",
        str(Path(cfg["workspace"]) / "fitting"),
        "--artifact-root",
        str(Path(cfg["workspace"]) / "fitting-launch"),
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
        "spireshift.native_fitting_session",
        str(launch_path.relative_to(root)),
    ]


def owner_main(root: Path) -> int:
    path = root / LAUNCH
    read_launch(root, path)
    print(
        "Close STS2. Fit four copies on the independently verified saved lesson bank.", flush=True
    )
    print(
        "64 updates / 2,048 draws per copy; 256 updates total. "
        "Original full weights/Adam stay frozen.",
        flush=True,
    )
    print("Allow about 6–12 minutes; one 30-minute / 3,600-CPU-second / 4-GB session.", flush=True)
    print("No games or evaluation. Freeze all finals, report the result, then stop.", flush=True)
    print(
        "Clean sealed boundaries resume; unfinished updates are preserved without replay.",
        flush=True,
    )
    runpy.run_path(str(root / "scripts/selection-flows-session-v12.py"))["check_repository"](root)
    attempt = 1
    while (root / f"artifacts/resources/varied-fitting-v1-attempt-{attempt}.json").exists():
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
                        "phase": "fit_only",
                        "work": WORK,
                        "bank_id": context["fitting_bank"]["bank_id"],
                        "new_games": 0,
                        "optimizer_updates": 0,
                        "automatic_follow_up": False,
                    }
                )
            )
            return 0
        target = snapshot_launch(context)
        result = fit(
            context,
            deadline=started + context["fitting_launch"]["session_limits"]["wall_seconds"] - 15,
        )
        after = frozen_checks(context)
        receipt = {
            "schema_version": "native-varied-fitting-session-receipt-v1",
            "launch_binding_id": binding(context["fitting_launch"]),
            "status": result["status"],
            "fitting_report_id": result.get("report_id"),
            "checks_before": before,
            "checks_after": after,
            "new_games": 0,
            "automatic_follow_up": False,
            "wall_seconds": time.monotonic() - started,
        }
        receipt["report_id"] = manifest_identifier(receipt)
        number = 1
        while True:
            try:
                with (target / f"session-{number}.json").open("x") as handle:
                    handle.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
                break
            except FileExistsError:
                number += 1
        print(
            json.dumps(
                {k: v for k, v in result.items() if k not in {"sources", "evidence", "finals"}},
                indent=2,
            )
        )
        return (
            0 if result["status"] in {"diagnostic_finals_frozen", "clean_session_boundary"} else 2
        )
    except (ValueError, OSError, KeyError) as error:
        print(
            json.dumps({"status": "stopped_preserving_evidence", "error": str(error)}), flush=True
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
