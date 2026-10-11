"""Owner-launched, finite native/shipped startup, unlock and save comparisons.

This checks starting input equivalence and repeated seed behavior, not broad gameplay
parity, full-run speed, learning or policy strength. Every case keeps its source evidence.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_checkpoint import _probe_shipped_checkpoint_document
from spireshift.engine_cli_probe import _probe_cli_document
from spireshift.engine_native import _private_path
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.full_run_experience import atomic_json


def validate_bridge_cases(document: dict[str, Any]) -> list[dict[str, str]]:
    cases = document.get("cases")
    if (
        not isinstance(cases, list)
        or len(cases) != 12
        or any(not isinstance(case, dict) for case in cases)
        or any(not isinstance(case.get("case_id"), str) for case in cases)
        or any(not isinstance(case.get("seed"), str) for case in cases)
        or any(not re.fullmatch(r"[a-z0-9-]{1,48}", case["case_id"]) for case in cases)
        or any(not re.fullmatch(r"[A-Z0-9]{1,64}", case["seed"]) for case in cases)
        or len({case["case_id"] for case in cases}) != len(cases)
    ):
        raise ValueError("Exactly twelve named, explicitly seeded startup cases are required")
    counts = {
        seed: sum(case["seed"] == seed for case in cases) for seed in {c["seed"] for c in cases}
    }
    if len(counts) != 6 or any(count != 2 for count in counts.values()):
        raise ValueError(
            "Use six independent seeds, each repeated twice; do not count repeats as independent"
        )
    return [{"case_id": case["case_id"], "seed": case["seed"]} for case in cases]


def load_starting_bridge_config(
    qualification: EngineQualificationConfig, path: Path
) -> tuple[dict[str, Any], list[dict[str, str]], dict[str, tuple[Path, dict[str, Any]]]]:
    """Validate finite cases and frozen templates without launching native code."""
    document = json.loads(path.read_text())
    if (
        document.get("schema_version") != "engine-starting-bridges-config-v1"
        or document.get("stage") != "owner_native_shipped_starting_inputs_only"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("training_allowed") is not False
        or document.get("max_wall_seconds") != 900
        or document.get("successful_payload_policy") != "remove_after_verified_success"
    ):
        raise ValueError("Expected the finite owner starting-input comparison configuration")
    cases = validate_bridge_cases(document)
    templates: dict[str, tuple[Path, dict[str, Any]]] = {}
    for role in ("native", "shipped"):
        template = qualification.root / document[f"{role}_template"]
        body = json.loads(template.read_text())
        if (
            template.resolve().parent != path.resolve().parent
            or manifest_identifier(body) != document[f"{role}_template_id"]
        ):
            raise ValueError("The exact startup templates changed")
        templates[role] = (template, body)
    return document, cases, templates


def run_starting_bridges(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    document, cases, templates = load_starting_bridge_config(qualification, path)
    workspace = _private_path(qualification.root, document["workspace"])
    workspace.mkdir(parents=True, exist_ok=True)
    progress = workspace / "batch.json"
    marker = workspace / "in-progress.json"
    if progress.exists() or marker.exists():
        raise FileExistsError(
            "Preserve this batch; choose a new explicitly versioned workspace before another launch"
        )
    started = time.monotonic()
    result: dict[str, Any] = {
        "schema_version": "engine-starting-bridges-v1",
        "config_id": manifest_identifier(document),
        "qualification_config_id": qualification.config_id,
        "status": "in_progress",
        "cases": [],
        "independent_seeds": 6,
        "planned_cases": 12,
        "full_run_attempts": 0,
        "completed_cases": 0,
        "failed_cases": 0,
        "not_attempted_cases": 12,
        "optimizer_steps": 0,
        "training_allowed": False,
        "shipped_cross_host_parity": False,
        "claim_scope": (
            "six_native_A8_starting_seeds_twice_imported_into_shipped_Host_"
            "public_option_titles_and_availability_only"
        ),
    }
    atomic_json(marker, result)
    current_case: dict[str, str] | None = None
    try:
        for index, case in enumerate(cases):
            # Each child has its own strict cap. Do not begin one if it could exceed the batch cap.
            if time.monotonic() - started > document["max_wall_seconds"] - 240:
                raise TimeoutError("Startup batch reached its finite launch allowance")
            if shutil.disk_usage(workspace).free < 3_500_000_000:
                raise ValueError(
                    "At least 3.5 GB free space is required for one disposable game copy"
                )
            current_case = case
            result["not_attempted_cases"] -= 1
            print(
                f"Starting comparison {index + 1}/12 ({case['case_id']}); one disposable A8 host.",
                flush=True,
            )
            native_path, native_template = templates["native"]
            native_config = copy.deepcopy(native_template)
            native_config["seed"] = case["seed"]
            native_config["workspace"] = str(
                (workspace / case["case_id"] / "native").relative_to(qualification.root)
            )
            native = _probe_cli_document(
                qualification, native_path, node, native_config, panel="checkpoint"
            )
            native_report = workspace / case["case_id"] / "native-report.json"
            atomic_json(native_report, native)
            if native["status"] != "checkpoint_public_projection_regression_pass":
                raise ValueError(f"Native startup failed in {case['case_id']}; evidence preserved")
            snapshot = Path(native["report_path"]).parent / "private-starting-snapshot.json"
            shipped_path, shipped_template = templates["shipped"]
            shipped_config = copy.deepcopy(shipped_template)
            shipped_config.update(
                seed=case["seed"],
                checkpoint_report=str(native_report.relative_to(qualification.root)),
                checkpoint_report_id=native["report_id"],
                snapshot_sha256=_sha_file(snapshot),
                workspace=str(
                    (workspace / case["case_id"] / "shipped").relative_to(qualification.root)
                ),
                successful_payload_policy=document["successful_payload_policy"],
            )
            shipped = _probe_shipped_checkpoint_document(
                qualification, shipped_path, shipped_config, node=node
            )
            shipped_report = workspace / case["case_id"] / "shipped-report.json"
            atomic_json(shipped_report, shipped)
            entry = {
                **case,
                "native_report": str(native_report.relative_to(qualification.root)),
                "native_report_id": native["report_id"],
                "shipped_report": str(shipped_report.relative_to(qualification.root)),
                "shipped_report_id": shipped["report_id"],
                "status": shipped["verdict"]["status"],
                "disposable_payload_removed_after_verified_success": shipped[
                    "disposable_payload_removed_after_verified_success"
                ],
                "starting_options": shipped["probe"].get("starting_options_comparison", {}),
            }
            result["cases"].append(entry)
            if shipped["verdict"]["status"] != "shipped_checkpoint_input_pass":
                raise ValueError(
                    f"Shipped startup comparison failed in {case['case_id']}; no next case follows"
                )
            result["completed_cases"] += 1
            current_case = None
            atomic_json(workspace / "progress" / f"comparison-{index + 1:03d}.json", result)
            print(
                f"Comparison {index + 1}/12 passed: A8/seed and starting choices agree; saved.",
                flush=True,
            )
        pairs: dict[str, list[dict[str, Any]]] = {}
        for case in result["cases"]:
            pairs.setdefault(case["seed"], []).append(case["starting_options"])
        result["repeated_seed_choices_identical"] = all(
            values[0] == values[1] for values in pairs.values()
        )
        if not result["repeated_seed_choices_identical"]:
            raise ValueError(
                "A repeated native seed changed its starting choices; preserve the first divergence"
            )
        result["status"] = "starting_input_comparisons_pass"
    except (OSError, ValueError, subprocess.SubprocessError, KeyboardInterrupt) as error:
        result["status"] = "starting_input_comparisons_incomplete"
        result["error"] = str(error) or "interrupted"
        if current_case is not None:
            result["failed_cases"] += 1
            result["failed_case"] = current_case
    result["wall_seconds"] = time.monotonic() - started
    result["report_id"] = manifest_identifier(result)
    atomic_json(progress, result)
    marker.unlink()
    return result
