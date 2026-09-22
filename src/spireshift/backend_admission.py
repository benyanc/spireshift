from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from spireshift.adapters.evangambit import EvanGambitRuntimeEvidence
from spireshift.core.manifest import (
    PatchManifest,
    freeze_patch_manifest,
    manifest_identifier,
    verify_installation_identity,
    write_frozen_manifest,
)

BACKEND_ADMISSION_REPORT_VERSION = "backend-admission-report-v1"
MANDATORY_CONFORMANCE_CHECKS = frozenset(
    {
        "identity",
        "reset",
        "legal_actions",
        "stepping",
        "illegal_action",
        "faithful_clone",
        "hidden_resampling",
        "replay",
        "public_state_isolation",
        "terminal_reward",
    }
)


@dataclass(frozen=True, slots=True)
class BackendAdmissionAssessment:
    report: dict[str, object]
    admitted_manifest: PatchManifest | None


def assess_backend_admission(
    source_manifest: PatchManifest,
    conformance_report: object,
    external_evidence: object,
    installation_manifest: object,
    runtime: EvanGambitRuntimeEvidence,
    *,
    adapter_source: Path,
) -> BackendAdmissionAssessment:
    conformance = _mapping(conformance_report, "conformance report")
    evidence = _mapping(external_evidence, "external evidence")
    installation = _mapping(installation_manifest, "installation manifest")
    checks: list[dict[str, str]] = []

    _record(
        checks,
        "source_manifest",
        source_manifest.admission_status == "pending_conformance",
        "Source manifest is pending conformance",
        "Source manifest status is "
        f"{source_manifest.admission_status!r}, expected pending_conformance",
    )
    _record(
        checks,
        "runtime_revision",
        runtime.upstream_revision == source_manifest.engine.revision,
        "Runtime checkout matches the pinned engine revision",
        "Runtime checkout differs from the pinned engine revision",
    )
    _record(
        checks,
        "runtime_patch",
        runtime.game_version == source_manifest.patch.game_version
        and runtime.steam_build_id == source_manifest.patch.steam_build_id,
        "Runtime game version and Steam build match the source manifest",
        "Runtime game version or Steam build differs from the source manifest",
    )

    installation_errors = verify_installation_identity(source_manifest, installation)
    _record(
        checks,
        "installed_game_identity",
        not installation_errors,
        "Installed authoritative game identity matches the source manifest",
        "; ".join(installation_errors),
    )

    conformance_errors = _conformance_errors(conformance, source_manifest)
    _record(
        checks,
        "environment_conformance",
        not conformance_errors,
        "Every mandatory environment-conformance check passed",
        "; ".join(conformance_errors),
    )

    evidence_errors = _external_evidence_errors(evidence, source_manifest)
    _record(
        checks,
        "authoritative_differential_evidence",
        not evidence_errors,
        "Pinned authoritative fixture executions report no observed divergence",
        "; ".join(evidence_errors),
    )

    adapter_path = adapter_source.resolve()
    try:
        adapter_bytes = adapter_path.read_bytes()
    except OSError as error:
        adapter_bytes = b""
        adapter_error = f"Cannot read adapter source: {error}"
    else:
        adapter_error = ""
    _record(
        checks,
        "adapter_source",
        bool(adapter_bytes),
        "SpireShift adapter source is present and content-addressed",
        adapter_error or "Adapter source is empty",
    )

    admitted = all(check["status"] == "pass" for check in checks)
    candidate = _candidate_manifest(source_manifest, runtime, adapter_bytes) if admitted else None
    limitations_value = evidence.get("coverage_gaps", [])
    limitations = (
        [
            str(item)
            for item in limitations_value
            if "not yet been projected through a SpireShift adapter" not in str(item)
        ]
        if isinstance(limitations_value, list)
        else ["External evidence did not contain a valid coverage-gaps list"]
    )
    report_body: dict[str, object] = {
        "schema_version": BACKEND_ADMISSION_REPORT_VERSION,
        "verdict": "admitted" if admitted else "rejected",
        "source_manifest_id": source_manifest.manifest_id,
        "admitted_manifest_id": candidate.manifest_id if candidate is not None else None,
        "conformance_sha256": _sha256_document(conformance),
        "external_evidence_id": evidence.get("evidence_id"),
        "runtime": runtime.as_dict(),
        "adapter": {
            "component_id": "spireshift-evangambit-environment-adapter",
            "version": "1",
            "sha256": hashlib.sha256(adapter_bytes).hexdigest() if adapter_bytes else None,
        },
        "checks": checks,
        "coverage_limitations": limitations,
    }
    report = {**report_body, "report_id": manifest_identifier(report_body)}
    return BackendAdmissionAssessment(report=report, admitted_manifest=candidate)


def verify_backend_admission(
    report_value: object,
    admitted_manifest: PatchManifest | None = None,
) -> tuple[str, ...]:
    report = _mapping(report_value, "backend admission report")
    errors: list[str] = []
    if report.get("schema_version") != BACKEND_ADMISSION_REPORT_VERSION:
        errors.append("unsupported backend admission report schema")
    report_id = report.get("report_id")
    body = dict(report)
    body.pop("report_id", None)
    if report_id != manifest_identifier(body):
        errors.append("backend admission report identity mismatch")
    checks = report.get("checks")
    if not isinstance(checks, list) or not checks:
        errors.append("backend admission report has no checks")
    else:
        failed = [
            str(check.get("check_id"))
            for check in checks
            if isinstance(check, dict) and check.get("status") != "pass"
        ]
        if report.get("verdict") == "admitted" and failed:
            errors.append(f"admitted report contains failed checks: {failed}")
    if admitted_manifest is not None:
        if admitted_manifest.admission_status != "admitted":
            errors.append("candidate manifest is not admitted")
        if report.get("admitted_manifest_id") != admitted_manifest.manifest_id:
            errors.append("admitted manifest identity differs from report")
    elif report.get("verdict") == "admitted":
        errors.append("admitted report requires its admitted manifest")
    return tuple(errors)


def load_backend_admission_report(path: Path) -> dict[str, object]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load backend admission report {path}: {error}") from error
    return _mapping(value, "backend admission report")


def write_backend_admission(
    assessment: BackendAdmissionAssessment,
    *,
    report_path: Path,
    manifest_path: Path | None,
) -> None:
    encoded = json.dumps(assessment.report, indent=2, ensure_ascii=True) + "\n"
    _write_immutable(report_path, encoded, "backend admission report")
    if assessment.admitted_manifest is None:
        if manifest_path is not None:
            raise ValueError("Cannot write an admitted manifest for a rejected assessment")
        return
    if manifest_path is None:
        raise ValueError("An admitted assessment requires an output manifest path")
    write_frozen_manifest(assessment.admitted_manifest, manifest_path)


def _candidate_manifest(
    source: PatchManifest,
    runtime: EvanGambitRuntimeEvidence,
    adapter_bytes: bytes,
) -> PatchManifest:
    specification = source.as_dict()
    specification.pop("manifest_id")
    specification["admission_status"] = "admitted"
    adapter_digest = hashlib.sha256(adapter_bytes).hexdigest()
    specification["adapter"] = {
        "component_id": "spireshift-evangambit-environment-adapter",
        "version": "1",
        "revision": adapter_digest,
        "source": "https://github.com/benyanc/spireshift/blob/main/src/spireshift/adapters/evangambit.py",
        "digest": {"algorithm": "sha256", "value": adapter_digest},
    }
    mechanics = cast(list[object], specification["mechanics"])
    mechanics.append(
        {
            "artifact_id": (
                "evangambit-sts2-nativeaot-"
                f"{runtime.platform}-{runtime.architecture}-{runtime.upstream_revision[:7]}"
            ),
            "kind": "compiled-simulator-library",
            "version": runtime.upstream_revision,
            "platform": runtime.platform,
            "architecture": runtime.architecture,
            "digest": {"algorithm": "sha256", "value": runtime.native_sha256},
            "size_bytes": runtime.native_size_bytes,
        }
    )
    return freeze_patch_manifest(specification)


def _conformance_errors(report: dict[str, object], source_manifest: PatchManifest) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != "conformance-report-v1":
        errors.append("unsupported conformance report schema")
    if report.get("verdict") != "pass":
        errors.append(f"conformance verdict is {report.get('verdict')!r}, expected 'pass'")
    ruleset = report.get("ruleset")
    if not isinstance(ruleset, dict) or ruleset.get("manifest_id") != source_manifest.manifest_id:
        errors.append("conformance report ruleset differs from source manifest")
    checks = report.get("checks")
    if not isinstance(checks, list):
        errors.append("conformance checks are missing")
        return errors
    statuses = {
        str(check.get("check_id")): check.get("status")
        for check in checks
        if isinstance(check, dict)
    }
    missing = sorted(MANDATORY_CONFORMANCE_CHECKS - statuses.keys())
    failed = sorted(
        check_id for check_id in MANDATORY_CONFORMANCE_CHECKS if statuses.get(check_id) != "pass"
    )
    if missing:
        errors.append(f"missing mandatory checks: {missing}")
    if failed:
        errors.append(f"mandatory checks did not pass: {failed}")
    return errors


def _external_evidence_errors(
    evidence: dict[str, object], source_manifest: PatchManifest
) -> list[str]:
    errors: list[str] = []
    evidence_id = evidence.get("evidence_id")
    body = dict(evidence)
    body.pop("evidence_id", None)
    if evidence_id != manifest_identifier(body):
        errors.append("external evidence identity mismatch")
    subject = evidence.get("subject")
    if not isinstance(subject, dict):
        errors.append("external evidence subject is missing")
    else:
        if subject.get("ruleset_manifest_id") != source_manifest.manifest_id:
            errors.append("external evidence ruleset differs from source manifest")
        if subject.get("revision") != source_manifest.engine.revision:
            errors.append("external evidence revision differs from source manifest")
        if subject.get("game_version") != source_manifest.patch.game_version:
            errors.append("external evidence game version differs from source manifest")
        if subject.get("steam_build_id") != source_manifest.patch.steam_build_id:
            errors.append("external evidence Steam build differs from source manifest")
    differential = evidence.get("differential_result")
    if not isinstance(differential, dict):
        errors.append("external differential result is missing")
    elif (
        differential.get("verdict") != "no_observed_divergence"
        or differential.get("observed_divergences") != 0
        or differential.get("catalogued_open_divergences") != 0
    ):
        errors.append("external evidence reports divergence")
    executions = evidence.get("executions")
    if not isinstance(executions, list) or not executions:
        errors.append("external evidence contains no executions")
    elif any(
        isinstance(execution, dict) and execution.get("status") == "fail"
        for execution in executions
    ):
        errors.append("an authoritative fixture execution failed")
    return errors


def _record(
    checks: list[dict[str, str]],
    check_id: str,
    passed: bool,
    passed_detail: str,
    failed_detail: str,
) -> None:
    checks.append(
        {
            "check_id": check_id,
            "status": "pass" if passed else "fail",
            "detail": passed_detail if passed else failed_detail,
        }
    )


def _sha256_document(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return cast(dict[str, object], value)


def _write_immutable(path: Path, encoded: str, label: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise FileExistsError(f"Refusing to replace immutable {label}: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded, encoding="utf-8")
