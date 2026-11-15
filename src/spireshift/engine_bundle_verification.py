"""Saved-only bundle evidence reconstruction; never launches games or training."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_journey_verification import _hashed
from spireshift.engine_native import _private_path
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file


def verify_bundle_saved(
    qualification: EngineQualificationConfig, comparison: dict[str, Any], *, node: Path
) -> dict[str, Any]:
    if (
        comparison.get("status") != "bundle_action_comparison_pass"
        or comparison.get("training_allowed") is not False
    ):
        raise ValueError("Expected one completed separately scoped bundle comparison")
    native_path = _private_path(qualification.root, comparison["native_report"])
    shipped_path = _private_path(qualification.root, comparison["shipped_report"])
    native, shipped = _hashed(native_path), _hashed(shipped_path)
    if (
        native["report_id"] != comparison["native_report_id"]
        or shipped["report_id"] != comparison["shipped_report_id"]
        or native.get("qualification_config_id") != qualification.config_id
        or shipped.get("qualification_config_id") != qualification.config_id
        or native.get("status") != "bundle_bridge_public_projection_regression_pass"
        or shipped.get("verdict", {}).get("status") != "shipped_checkpoint_input_pass"
        or not native.get("checks")
        or not shipped.get("checks")
        or any(v is not True for v in native.get("checks", {}).values())
        or any(v is not True for v in shipped.get("checks", {}).values())
        or native.get("full_run_attempts") != 0
        or shipped.get("full_run_attempts") != 0
        or native.get("training_allowed") is not False
        or shipped.get("training_allowed") is not False
    ):
        raise ValueError("Saved bundle report binding changed")
    attempt = Path(native["report_path"]).parent
    snapshots = _private_path(
        qualification.root,
        str((attempt / "private-bundle-snapshots.jsonl").relative_to(qualification.root)),
    )
    spec = {
        "native_report": str(native_path),
        "shipped_report": str(shipped_path),
        "native_snapshots": str(snapshots),
    }
    try:
        process = subprocess.run(
            [str(node), str(qualification.root / "scripts/verify-engine-bundle-saved-v1.mjs")],
            input=json.dumps(spec),
            text=True,
            capture_output=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired as error:
        raise ValueError("Saved bundle verification exceeded its 15-second cap") from error
    if process.returncode:
        raise ValueError("Saved raw bundle verification failed: " + process.stderr[-500:])
    verified = json.loads(process.stdout)
    if (
        verified.get("valid") is not True
        or verified.get("games_launched") != 0
        or verified.get("training_allowed") is not False
    ):
        raise ValueError("Invalid saved bundle verification result")
    result = {
        **verified,
        "schema_version": "engine-bundle-saved-verification-v1",
        "native_report_id": native["report_id"],
        "shipped_report_id": shipped["report_id"],
        "native_raw_snapshots_sha256": _sha_file(snapshots),
        "verifier_sha256": _sha_file(
            qualification.root / "scripts/verify-engine-bundle-saved-v1.mjs"
        ),
        "claim_scope": "saved_raw_bundle_public_facts_preview_award_and_delivery_only",
    }
    result["report_id"] = manifest_identifier(result)
    return result
