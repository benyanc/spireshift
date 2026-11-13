"""Independent saved shop audits; no game launches or optimizers."""

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
from spireshift.engine_shop_bridge import validate_shop_cases, validate_shop_template


def _case_input(
    qualification: EngineQualificationConfig,
    document: dict[str, Any],
    native_template: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    directory = _private_path(qualification.root, document["workspace"])
    comparison = _hashed(directory / "comparison.json")
    native_path = _private_path(qualification.root, comparison["native_report"])
    shipped_path = _private_path(qualification.root, comparison["shipped_report"])
    if (native_path, shipped_path) != (
        directory / "native-report.json",
        directory / "shipped-report.json",
    ):
        raise ValueError("Shop reports moved outside their named fixture directory")
    native, shipped = _hashed(native_path), _hashed(shipped_path)
    native_config = copy.deepcopy(native_template)
    native_config.update(
        seed=document["seed"],
        workspace=str((directory / "native").relative_to(qualification.root)),
        shop_bridge={"scenario": document["scenario"]},
    )
    native_original = _saved_private_path(qualification, native["report_path"])
    shipped_original = _saved_private_path(qualification, shipped["report_path"])
    attempt = native_original.parent
    verify_checkpoint_input(
        qualification,
        {
            "checkpoint_report": comparison["native_report"],
            "checkpoint_report_id": native["report_id"],
            "snapshot_sha256": _sha_file(attempt / "private-starting-snapshot.json"),
            "seed": document["seed"],
        },
        panel="shop_bridge",
    )
    count = 8 if document["scenario"] == "ordinary-purchases-removal" else 9
    plan = native["probe"]["journey"]
    if (
        comparison.get("config_id") != manifest_identifier(document)
        or comparison.get("qualification_config_id") != qualification.config_id
        or comparison.get("seed") != document["seed"]
        or comparison.get("scenario") != document["scenario"]
        or json.loads((directory / "native-config.json").read_text()) != native_config
        or native.get("config_id") != manifest_identifier(native_config)
        or native.get("report_id") != comparison.get("native_report_id")
        or shipped.get("report_id") != comparison.get("shipped_report_id")
        or shipped.get("config_id") != document["connector_config_id"]
        or shipped.get("qualification_config_id") != qualification.config_id
        or _hashed(native_original) != {k: v for k, v in native.items() if k != "report_path"}
        or _hashed(shipped_original) != {k: v for k, v in shipped.items() if k != "report_path"}
        or _evaluate_connector_checkpoint(shipped.get("checks", {}), shop_bridge=True)["status"]
        != "shipped_checkpoint_input_pass"
        or not shipped.get("checks")
        or any(value is not True for value in shipped["checks"].values())
        or shipped.get("training_allowed") is not False
        or shipped.get("mechanics_qualified") is not False
        or shipped.get("full_run_attempts") != 0
        or shipped.get("optimizer_steps") != 0
        or shipped.get("profile_settings_consent", {}).get(
            "fresh_shop_progress_absent_before_launch"
        )
        is not True
        or "rest_tutorial_baseline" in shipped.get("profile_settings_consent", {})
        or native.get("probe", {}).get("public_actions_delivered") != count
        or comparison.get("compared_snapshots") != count + 1
        or comparison.get("status") != "shop_action_comparison_pass"
        or comparison.get("semantic_actions_delivered") != count
        or comparison.get("public_actions_delivered") != count + 4
        or comparison.get("shop_ui_steps") != 3
        or comparison.get("potion_tutorial_steps") != 1
        or comparison.get("native_public_prefix_id") != manifest_identifier(plan)
        or comparison.get("privileged_fixture") is not True
        or comparison.get("fresh_profile_required") is not True
        or comparison.get("training_allowed") is not False
        or comparison.get("shipped_cross_host_parity") is not False
        or comparison.get("full_run_attempts") != 0
        or comparison.get("optimizer_steps") != 0
        or comparison.get("disposable_payload_removed_after_verified_success") is not True
        or shipped.get("disposable_payload_removed_after_verified_success") is not True
        or (shipped_original.parent / "game").exists()
    ):
        raise ValueError("Incomplete or changed saved shop comparison")
    return comparison, {
        "scenario": document["scenario"],
        "plan": plan,
        "native_snapshots": str(attempt / "private-shop-snapshots.jsonl"),
        "shipped": shipped["probe"],
    }


def _audit(
    qualification: EngineQualificationConfig, inputs: list[dict[str, Any]], node: Path
) -> list[dict[str, int]]:
    run = subprocess.run(
        [str(node), str(qualification.root / "scripts/verify-engine-shop-saved.mjs")],
        input=json.dumps(inputs),
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
        cwd=qualification.root,
    )
    if run.returncode:
        raise ValueError(f"Saved shop public-state audit failed: {run.stderr.strip()[:1200]}")
    result: list[dict[str, int]] = json.loads(run.stdout)
    return result


def verify_shop_bridge(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    document = json.loads(path.read_text())
    native, _ = validate_shop_template(qualification, path, document)
    comparison, item = _case_input(qualification, document, native)
    audit = _audit(qualification, [item], node)
    result = {
        "schema_version": "engine-shop-bridge-verification-v1",
        "valid": True,
        "comparison_report_id": comparison["report_id"],
        "cases": 1,
        "audits": audit,
        "verifier_sha256": _sha_file(qualification.root / "scripts/verify-engine-shop-saved.mjs"),
        "games_launched": 0,
        "optimizer_steps": 0,
        "training_allowed": False,
        "shipped_cross_host_parity": False,
        "claim_scope": "saved_scoped_privileged_shop_public_action_effects_only",
    }
    result["report_id"] = manifest_identifier(result)
    return result


def verify_shop_bridges(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    document = json.loads(path.read_text())
    if (
        document.get("schema_version") != "engine-shop-bridges-config-v1"
        or document.get("stage") != "owner_privileged_shop_fixture_differentials_only"
        or document.get("training_allowed") is not False
        or document.get("qualification_config_id") != qualification.config_id
    ):
        raise ValueError("Expected the frozen scoped shop batch configuration")
    planned = validate_shop_cases(document)
    template_path = qualification.root / document["template"]
    template = json.loads(template_path.read_text())
    if (
        template_path.resolve().parent != path.resolve().parent
        or manifest_identifier(template) != document["template_id"]
    ):
        raise ValueError("Frozen shop comparison template changed")
    native, _ = validate_shop_template(qualification, template_path, template)
    connector = json.loads((qualification.root / template["connector_config"]).read_text())
    if manifest_identifier(connector) != template["connector_config_id"]:
        raise ValueError("Frozen shipped shop configuration changed")
    workspace = _private_path(qualification.root, document["workspace"])
    batch = _hashed(workspace / "batch.json")
    if (
        batch.get("config_id") != manifest_identifier(document)
        or batch.get("qualification_config_id") != qualification.config_id
        or batch.get("schema_version") != "engine-shop-bridges-v1"
        or batch.get("status") != "shop_comparisons_pass"
        or batch.get("completed_cases") != 8
        or batch.get("planned_cases") != 8
        or batch.get("failed_cases") != 0
        or batch.get("not_attempted_cases") != 0
        or batch.get("independent_seeds") != 2
        or batch.get("seed_scenario_pairs") != 4
        or batch.get("repeated_public_prefixes_identical") is not True
        or batch.get("privileged_fixture") is not True
        or batch.get("fresh_profile_required") is not True
        or batch.get("training_allowed") is not False
        or batch.get("shipped_cross_host_parity") is not False
        or batch.get("full_run_attempts") != 0
        or batch.get("optimizer_steps") != 0
        or [
            {k: row.get(k) for k in ("case_id", "seed", "scenario")}
            for row in batch.get("cases", [])
        ]
        != planned
    ):
        raise ValueError("Expected the completed frozen eight-case shop batch")
    inputs = []
    prefixes: dict[tuple[str, str], list[str]] = {}
    for row in batch["cases"]:
        directory = workspace / row["case_id"]
        effective = copy.deepcopy(template)
        effective.update(
            seed=row["seed"],
            scenario=row["scenario"],
            workspace=str(directory.relative_to(qualification.root)),
        )
        comparison, item = _case_input(qualification, effective, native)
        if (
            {k: value for k, value in row.items() if k not in {"case_id", "report"}} != comparison
            or json.loads((directory / "config.json").read_text()) != effective
            or _private_path(qualification.root, row["report"]) != directory / "comparison.json"
        ):
            raise ValueError("Saved shop case configuration or batch reference changed")
        prefixes.setdefault((row["seed"], row["scenario"]), []).append(
            comparison["native_public_prefix_id"]
        )
        inputs.append(item)
    if any(len(set(values)) != 1 for values in prefixes.values()):
        raise ValueError("Repeated shop public prefixes differ")
    audits = _audit(qualification, inputs, node)
    result = {
        "schema_version": "engine-shop-bridges-verification-v1",
        "valid": True,
        "batch_report_id": batch["report_id"],
        "cases": len(audits),
        "compared_snapshots": sum(row["compared_snapshots"] for row in audits),
        "semantic_actions_delivered": sum(row["semantic_actions_delivered"] for row in audits),
        "public_actions_delivered": sum(row["public_actions_delivered"] for row in audits),
        "shop_ui_steps": sum(row["shop_ui_steps"] for row in audits),
        "potion_tutorial_steps": sum(row["potion_tutorial_steps"] for row in audits),
        "verifier_sha256": _sha_file(qualification.root / "scripts/verify-engine-shop-saved.mjs"),
        "games_launched": 0,
        "optimizer_steps": 0,
        "training_allowed": False,
        "shipped_cross_host_parity": False,
        "claim_scope": "saved_repeated_privileged_shop_public_action_effects_only",
    }
    result["report_id"] = manifest_identifier(result)
    return result
