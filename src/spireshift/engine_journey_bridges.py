"""Owner-launched repeated first-combat differentials; no learning or full runs follow."""

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
from spireshift.engine_cli_probe import _probe_cli_document
from spireshift.engine_journey import _probe_shipped_journey_document
from spireshift.engine_native import _private_path
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.engine_starting_bridges import verify_starting_bridges
from spireshift.full_run_experience import atomic_json


def validate_journey_cases(document: dict[str, Any]) -> list[dict[str, str]]:
    cases = document.get("cases")
    if (
        not isinstance(cases, list)
        or len(cases) != 8
        or any(not isinstance(case, dict) for case in cases)
        or any(
            not isinstance(case.get("case_id"), str)
            or not re.fullmatch(r"[a-z0-9-]{1,64}", case["case_id"])
            for case in cases
        )
        or any(
            not isinstance(case.get("seed"), str)
            or not re.fullmatch(r"[A-Z0-9]{1,64}", case["seed"])
            for case in cases
        )
        or any(case.get("starting_option") not in {"Winged Boots", "Dowsing Rod"} for case in cases)
        or len({case["case_id"] for case in cases}) != 8
        or len({case["seed"] for case in cases}) != 2
    ):
        raise ValueError(
            "Expected eight named cases: two seeds, two frozen starting choices, twice each"
        )
    pairs = {(case["seed"], case["starting_option"]) for case in cases}
    if len(pairs) != 4 or any(
        sum((case["seed"], case["starting_option"]) == pair for case in cases) != 2
        for pair in pairs
    ):
        raise ValueError(
            "Repeat each of the four seed/option pairs twice; repeats are not independent seeds"
        )
    return [{key: case[key] for key in ("case_id", "seed", "starting_option")} for case in cases]


def run_journey_bridges(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    document = json.loads(path.read_text())
    if (
        document.get("schema_version") != "engine-journey-bridges-config-v1"
        or document.get("stage") != "owner_first_combat_prefix_differentials_only"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("training_allowed") is not False
        or document.get("max_wall_seconds") != 900
    ):
        raise ValueError("Expected the finite owner first-combat comparison configuration")
    cases = validate_journey_cases(document)
    templates = {}
    for role in ("native", "shipped"):
        template_path = qualification.root / document[f"{role}_template"]
        template = json.loads(template_path.read_text())
        if (
            template_path.resolve().parent != path.resolve().parent
            or manifest_identifier(template) != document[f"{role}_template_id"]
        ):
            raise ValueError("Frozen first-combat templates changed")
        templates[role] = (template_path, template)
    shipped_template = templates["shipped"][1]
    prerequisite = verify_starting_bridges(
        qualification, qualification.root / shipped_template["starting_bridge_config"]
    )
    if prerequisite["batch_report_id"] != shipped_template["starting_bridge_report_id"]:
        raise ValueError("The completed startup prerequisite changed; no native process follows")
    workspace = _private_path(qualification.root, document["workspace"])
    workspace.mkdir(parents=True, exist_ok=True)
    marker, output = workspace / "in-progress.json", workspace / "batch.json"
    if marker.exists() or output.exists():
        raise FileExistsError("Preserve this batch; do not silently restart or overwrite it")
    result: dict[str, Any] = {
        "schema_version": "engine-journey-bridges-v1",
        "config_id": manifest_identifier(document),
        "qualification_config_id": qualification.config_id,
        "status": "in_progress",
        "cases": [],
        "planned_cases": 8,
        "independent_seeds": 2,
        "seed_option_pairs": 4,
        "completed_cases": 0,
        "failed_cases": 0,
        "not_attempted_cases": 8,
        "full_run_attempts": 0,
        "optimizer_steps": 0,
        "training_allowed": False,
        "shipped_cross_host_parity": False,
        "claim_scope": (
            "two_A8_seeds_two_starting_choices_twice_first_combat_turn_scoped_public_fields_only"
        ),
    }
    atomic_json(marker, result)
    started = time.monotonic()
    active = None
    try:
        for i, case in enumerate(cases):
            if time.monotonic() - started > document["max_wall_seconds"] - 250:
                raise TimeoutError("Finite first-combat batch reached its launch allowance")
            if shutil.disk_usage(workspace).free < 3_500_000_000:
                raise ValueError("At least 3.5 GB free is required for one disposable copy")
            active = case
            result["not_attempted_cases"] -= 1
            directory = workspace / case["case_id"]
            print(
                f"First-combat comparison {i + 1}/8 ({case['case_id']}); one disposable A8 host.",
                flush=True,
            )
            native_path, native_template = templates["native"]
            native_config = copy.deepcopy(native_template)
            native_config.update(
                seed=case["seed"],
                workspace=str((directory / "native").relative_to(qualification.root)),
            )
            native_config["journey"]["starting_option"] = case["starting_option"]
            atomic_json(directory / "native-config.json", native_config)
            native = _probe_cli_document(
                qualification, native_path, node, native_config, panel="journey"
            )
            native_report = directory / "native-report.json"
            atomic_json(native_report, native)
            entry = {
                **case,
                "native_report": str(native_report.relative_to(qualification.root)),
                "native_report_id": native["report_id"],
                "status": native["status"],
            }
            result["cases"].append(entry)
            if native["status"] != "journey_public_projection_regression_pass":
                raise ValueError(
                    "Native prefix incomplete; evidence preserved and no next case follows"
                )
            shipped_path, shipped_template = templates["shipped"]
            shipped_config = copy.deepcopy(shipped_template)
            snapshot = Path(native["report_path"]).parent / "private-starting-snapshot.json"
            shipped_config.update(
                seed=case["seed"],
                workspace=str((directory / "shipped").relative_to(qualification.root)),
                checkpoint_report=str(native_report.relative_to(qualification.root)),
                checkpoint_report_id=native["report_id"],
                snapshot_sha256=_sha_file(snapshot),
                effective_native_config_id=manifest_identifier(native_config),
            )
            atomic_json(directory / "shipped-config.json", shipped_config)
            shipped = _probe_shipped_journey_document(
                qualification,
                shipped_path,
                shipped_config,
                node=node,
                native_override=native_config,
            )
            shipped_report = directory / "shipped-report.json"
            atomic_json(shipped_report, shipped)
            shipped_probe = shipped.get("probe", {})
            entry.update(
                shipped_report=str(shipped_report.relative_to(qualification.root)),
                shipped_report_id=shipped["report_id"],
                status=shipped["status"],
                public_actions_requested=shipped_probe.get("public_actions_requested"),
                public_actions_delivered=shipped_probe.get("public_actions_requested")
                if shipped["status"] == "first_combat_prefix_pass"
                else None,
                compared_snapshots=len(shipped_probe.get("comparisons", [])),
                tutorial_steps=len(shipped_probe.get("tutorial_steps", [])),
                disposable_payload_removed_after_verified_success=shipped[
                    "disposable_payload_removed_after_verified_success"
                ],
                native_public_prefix_id=manifest_identifier(native["probe"]["journey"]),
            )
            if shipped["status"] != "first_combat_prefix_pass":
                raise ValueError(
                    "First public-state/action divergence preserved; no next case follows"
                )
            result["completed_cases"] += 1
            active = None
            atomic_json(workspace / "progress" / f"comparison-{i + 1:03d}.json", result)
            print(
                f"Comparison {i + 1}/8 passed: {entry['public_actions_delivered']} game actions, "
                f"{entry['compared_snapshots']} observations; saved.",
                flush=True,
            )
        pairs: dict[tuple[str, str], list[str]] = {}
        for case in result["cases"]:
            pairs.setdefault((case["seed"], case["starting_option"]), []).append(
                case["native_public_prefix_id"]
            )
        result["repeated_public_prefixes_identical"] = all(
            values[0] == values[1] for values in pairs.values()
        )
        if not result["repeated_public_prefixes_identical"]:
            raise ValueError(
                "Repeated seed/option prefix differs; do not claim deterministic behavior"
            )
        result["status"] = "first_combat_comparisons_pass"
    except (OSError, ValueError, subprocess.SubprocessError, KeyboardInterrupt) as error:
        result.update(
            status="first_combat_comparisons_incomplete", error=str(error) or "interrupted"
        )
        if active is not None:
            result["failed_cases"] += 1
            result["failed_case"] = active
    result["wall_seconds"] = time.monotonic() - started
    result["report_id"] = manifest_identifier(result)
    atomic_json(output, result)
    marker.unlink()
    return result
