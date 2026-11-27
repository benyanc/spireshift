"""Recheck saved rest fixtures and UI delivery without launching any games."""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_checkpoint import _saved_private_path, verify_checkpoint_input
from spireshift.engine_connector import _evaluate_connector_checkpoint
from spireshift.engine_journey_verification import _hashed
from spireshift.engine_native import _private_path
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.engine_rest_bridge import validate_rest_cases, verify_rest_tutorial_baseline


def verify_rest_bridges(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    document = json.loads(path.read_text())
    if (
        document.get("schema_version") != "engine-rest-bridges-config-v1"
        or document.get("stage") != "owner_privileged_rest_fixture_differentials_only"
        or document.get("training_allowed") is not False
        or document.get("qualification_config_id") != qualification.config_id
    ):
        raise ValueError("Expected the frozen scoped rest comparison configuration")
    planned = validate_rest_cases(document)
    template_path = qualification.root / document["template"]
    template = json.loads(template_path.read_text())
    fresh_tutorial = template.get("schema_version") == "engine-rest-bridge-config-v2"
    if (
        template_path.resolve().parent != path.resolve().parent
        or manifest_identifier(template) != document["template_id"]
    ):
        raise ValueError("Frozen rest comparison template changed")
    for name, expected in template["helpers_sha256"].items():
        if Path(name).name != name or _sha_file(qualification.root / "scripts" / name) != expected:
            raise ValueError("Frozen rest comparison helper changed")
    native_template_path = qualification.root / template["native_config"]
    native_template = json.loads(native_template_path.read_text())
    connector = json.loads((qualification.root / template["connector_config"]).read_text())
    if (
        manifest_identifier(native_template) != template["native_config_id"]
        or manifest_identifier(connector) != template["connector_config_id"]
    ):
        raise ValueError("Frozen native or shipped rest configuration changed")
    if fresh_tutorial:
        if "rest_tutorial_baseline" in template:
            raise ValueError(
                "Fresh rest qualification cannot inherit already-seen tutorial progress"
            )
    else:
        verify_rest_tutorial_baseline(
            qualification, template["rest_tutorial_baseline"], template["connector_config_id"]
        )
    workspace = _private_path(qualification.root, document["workspace"])
    batch = _hashed(workspace / "batch.json")
    if (
        batch.get("config_id") != manifest_identifier(document)
        or batch.get("qualification_config_id") != qualification.config_id
        or batch.get("status") != "rest_comparisons_pass"
        or batch.get("schema_version") != "engine-rest-bridges-v1"
        or batch.get("completed_cases") != 8
        or batch.get("planned_cases") != 8
        or batch.get("independent_seeds") != 2
        or batch.get("seed_scenario_pairs") != 4
        or batch.get("repeated_public_prefixes_identical") is not True
        or batch.get("failed_cases") != 0
        or batch.get("not_attempted_cases") != 0
        or batch.get("training_allowed") is not False
        or batch.get("full_run_attempts") != 0
        or batch.get("optimizer_steps") != 0
        or batch.get("privileged_fixture") is not True
        or batch.get("shipped_cross_host_parity") is not False
        or [{k: c.get(k) for k in ("case_id", "seed", "scenario")} for c in batch["cases"]]
        != planned
    ):
        raise ValueError("Expected the complete frozen eight-case rest batch")
    inputs = []
    pairs: dict[tuple[str, str], list[Any]] = {}
    for case in batch["cases"]:
        directory = workspace / case["case_id"]
        comparison = _hashed(directory / "comparison.json")
        if {k: v for k, v in case.items() if k not in {"case_id", "report"}} != comparison:
            raise ValueError("Saved comparison and batch disagree")
        effective = copy.deepcopy(template)
        effective.update(
            seed=case["seed"],
            scenario=case["scenario"],
            workspace=str(directory.relative_to(qualification.root)),
        )
        native_config = copy.deepcopy(native_template)
        native_config.update(
            seed=case["seed"],
            workspace=str((directory / "native").relative_to(qualification.root)),
            rest_bridge={"scenario": case["scenario"]},
        )
        if (
            json.loads((directory / "config.json").read_text()) != effective
            or comparison.get("config_id") != manifest_identifier(effective)
            or json.loads((directory / "native-config.json").read_text()) != native_config
        ):
            raise ValueError("Saved effective rest configuration changed")
        native_path = _private_path(qualification.root, case["native_report"])
        shipped_path = _private_path(qualification.root, case["shipped_report"])
        if (native_path, shipped_path) != (
            directory / "native-report.json",
            directory / "shipped-report.json",
        ):
            raise ValueError("Rest case evidence moved outside its named directory")
        native, shipped = _hashed(native_path), _hashed(shipped_path)
        native_original = _saved_private_path(qualification, native["report_path"])
        shipped_original = _saved_private_path(qualification, shipped["report_path"])
        attempt = native_original.parent
        verify_checkpoint_input(
            qualification,
            {
                "checkpoint_report": case["native_report"],
                "checkpoint_report_id": native["report_id"],
                "snapshot_sha256": _sha_file(attempt / "private-starting-snapshot.json"),
                "seed": case["seed"],
            },
            panel="rest_bridge",
        )
        plan = native["probe"]["journey"]
        consent = shipped.get("profile_settings_consent", {})
        if fresh_tutorial:
            if (
                batch.get("fresh_rest_tutorial_required") is not True
                or case.get("fresh_rest_tutorial_required") is not True
                or case.get("rest_tutorial_steps") != 1
                or shipped.get("checks", {}).get("fresh_rest_tutorial_dismissed") is not True
                or consent.get("fresh_rest_progress_absent_before_launch") is not True
                or "rest_tutorial_baseline" in consent
            ):
                raise ValueError("Fresh rest tutorial was not explicitly qualified")
        elif consent.get("rest_tutorial_baseline") != template["rest_tutorial_baseline"]:
            raise ValueError("Already-seen rest tutorial provenance changed")
        if (
            native.get("config_id") != manifest_identifier(native_config)
            or native.get("report_id") != case["native_report_id"]
            or shipped.get("report_id") != case["shipped_report_id"]
            or shipped.get("config_id") != template["connector_config_id"]
            or shipped.get("qualification_config_id") != qualification.config_id
            or _hashed(native_original) != {k: v for k, v in native.items() if k != "report_path"}
            or _hashed(shipped_original) != {k: v for k, v in shipped.items() if k != "report_path"}
            or _evaluate_connector_checkpoint(
                shipped.get("checks", {}), rest_bridge=True, fresh_rest_tutorial=fresh_tutorial
            )["status"]
            != "shipped_checkpoint_input_pass"
            or not shipped.get("checks")
            or any(v is not True for v in shipped["checks"].values())
            or shipped.get("training_allowed") is not False
            or shipped.get("mechanics_qualified") is not False
            or shipped.get("full_run_attempts") != 0
            or shipped.get("optimizer_steps") != 0
            or native.get("probe", {}).get("public_actions_delivered") != 6
            or case.get("compared_snapshots") != 7
            or case.get("status") != "rest_action_comparison_pass"
            or case.get("semantic_actions_delivered") != 6
            or case.get("public_actions_delivered") != 7
            or case.get("upgrade_ui_steps") != 1
            or case.get("native_public_prefix_id") != manifest_identifier(plan)
            or case.get("disposable_payload_removed_after_verified_success") is not True
            or shipped.get("disposable_payload_removed_after_verified_success") is not True
            or (shipped_original.parent / "game").exists()
        ):
            raise ValueError(f"Incomplete or changed rest case: {case['case_id']}")
        inputs.append(
            {
                "scenario": case["scenario"],
                "plan": plan,
                "native_snapshots": str(attempt / "private-rest-snapshots.jsonl"),
                "shipped": shipped["probe"],
                "fresh_tutorial": fresh_tutorial,
            }
        )
        pairs.setdefault((case["seed"], case["scenario"]), []).append(plan)
    if any(len(rows) != 2 or rows[0] != rows[1] for rows in pairs.values()):
        raise ValueError("Repeated native rest prefixes differ")
    helper = qualification.root / "scripts/verify-engine-rest-saved.mjs"
    audited = subprocess.run(
        [str(node), str(helper)],
        input=json.dumps(inputs),
        text=True,
        capture_output=True,
        timeout=30,
        check=True,
    )
    counts = json.loads(audited.stdout)
    result = {
        "schema_version": "engine-rest-saved-verification-v1",
        "valid": True,
        "batch_report_id": batch["report_id"],
        "verifier_sha256": _sha_file(helper),
        "verified_cases": len(counts),
        "independent_seeds": 2,
        "seed_scenario_pairs": 4,
        **{
            key: sum(row[key] for row in counts)
            for key in (
                "compared_snapshots",
                "semantic_actions_delivered",
                "public_actions_delivered",
                "upgrade_ui_steps",
            )
        },
        "repeated_public_prefixes_identical": True,
        **(
            {"rest_tutorial_steps": sum(row["rest_tutorial_steps"] for row in counts)}
            if fresh_tutorial
            else {}
        ),
        "games_launched": 0,
        "optimizer_steps": 0,
        "training_allowed": False,
        "privileged_fixture": True,
        "shipped_cross_host_parity": False,
        "claim_scope": (
            "saved_privileged_rest_raw_snapshots_unique_actions_preview_effects_and_delivery_only"
        ),
    }
    result["report_id"] = manifest_identifier(result)
    return result
