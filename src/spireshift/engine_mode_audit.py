"""Read-only mode-reference coverage and explicit review; never admits training."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_journey_verification import _hashed
from spireshift.engine_native import (
    DATA_RELATIVE,
    _failure,
    _finish,
    _private_path,
    _verified_archive,
    load_native_qualification_config,
)
from spireshift.engine_qualification import (
    GAME_RELATIVE,
    EngineQualificationConfig,
    _inventory,
    _sha_file,
    verify_game_archive,
)
from spireshift.full_run_experience import atomic_json

TARGETS = {
    "MegaCrit.Sts2.Core.TestSupport.TestMode",
    "MegaCrit.Sts2.Core.Helpers.NonInteractiveMode",
}
CLASSIFICATIONS = {
    "rules_rng_divergence",
    "profile_dependent_rules",
    "choice_or_lifecycle_seam",
    "presentation_or_diagnostics",
    "test_only_api",
    "mode_definition",
}


def review_key(site: dict[str, Any]) -> str:
    """An async state machine is reviewed with its source method, not as MoveNext."""
    state = re.search(r"\+<([^>]+)>d__", site["declaring_type"])
    owner = site["declaring_type"].split("+", 1)[0]
    member = state.group(1) if state else site["method"]
    return f"{owner}.{member}"


def validate_inventory(document: dict[str, Any], assembly_sha: str) -> list[dict[str, Any]]:
    if (
        document.get("schema_version") != "managed-mode-reference-inventory-v1"
        or document.get("assembly_sha256") != assembly_sha
        or set(document.get("target_types", [])) != TARGETS
        or document.get("game_assembly_executed") is not False
        or document.get("undecoded_bodies") != 0
        or type(document.get("method_bodies")) is not int
        or not 0 < document["method_bodies"] <= document.get("methods", 0)
        or type(document.get("decoded_instructions")) is not int
        or document["decoded_instructions"] <= 0
    ):
        raise ValueError("Incomplete or differently bound static mode inventory")
    rows = document.get("sites")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Expected explicitly decoded mode references")
    seen = set()
    for row in rows:
        if (
            not isinstance(row, dict)
            or row.get("target_type") not in TARGETS
            or type(row.get("method_token")) is not int
            or row["method_token"] >> 24 != 6
            or type(row.get("il_offset")) is not int
            or row["il_offset"] < 0
            or not all(
                isinstance(row.get(k), str) and row[k]
                for k in ("declaring_type", "method", "target_member", "opcode")
            )
            or not all(
                re.fullmatch(r"[0-9a-f]{64}", str(row.get(k, "")))
                for k in ("method_il_sha256", "signature_sha256")
            )
        ):
            raise ValueError("Malformed static mode reference")
        key = (row["method_token"], row["il_offset"])
        if key in seen:
            raise ValueError("Duplicate static mode reference")
        seen.add(key)
    return rows


def assess_reviews(rows: list[dict[str, Any]], reviews: list[dict[str, Any]]) -> dict[str, Any]:
    by_method: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_method.setdefault(review_key(row), []).append(row)
    catalog: dict[str, dict[str, Any]] = {}
    for review in reviews:
        key = review.get("method")
        if (
            not isinstance(key, str)
            or key in catalog
            or key not in by_method
            or review.get("classification") not in CLASSIFICATIONS
            or not isinstance(review.get("rationale"), str)
            or not review["rationale"].strip()
            or set(review.get("method_il_sha256", []))
            != {row["method_il_sha256"] for row in by_method[key]}
        ):
            raise ValueError("Review is duplicated, stale, unbound or unexplained")
        catalog[key] = review
    reviewed = [row for row in rows if review_key(row) in catalog]
    unreviewed = [row for row in rows if review_key(row) not in catalog]
    blockers = [
        {"method": key, "classification": value["classification"], "rationale": value["rationale"]}
        for key, value in catalog.items()
        if value["classification"]
        in {"rules_rng_divergence", "profile_dependent_rules", "choice_or_lifecycle_seam"}
    ]
    return {
        "references": len(rows),
        "method_groups": len(by_method),
        "reviewed_method_groups": len(catalog),
        "reviewed_references": len(reviewed),
        "unreviewed_references": len(unreviewed),
        "unreviewed_method_groups": sorted(set(by_method) - set(catalog)),
        "classifications": dict(Counter(row["classification"] for row in catalog.values())),
        "findings": blockers,
        "semantic_review_complete": not unreviewed,
        # Static classification is never runtime parity, even with every row reviewed.
        "training_allowed": False,
        "mechanics_qualified": False,
    }


def audit_mode_references(qualification: EngineQualificationConfig, path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text())
    if (
        document.get("schema_version") != "engine-mode-audit-config-v1"
        or document.get("stage") != "private_static_mode_inventory_and_scoped_review_only"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("training_allowed") is not False
        or type(document.get("max_wall_seconds")) is not int
        or not 10 <= document["max_wall_seconds"] <= 120
    ):
        raise ValueError("Expected a short read-only exact-assembly mode audit")
    native_path = qualification.root / document["native_config"]
    if native_path.resolve().parent != path.resolve().parent:
        raise ValueError("Native audit prerequisite must be beside its configuration")
    native = load_native_qualification_config(native_path, qualification)
    archive, before = _verified_archive(native)
    source = _hashed(_private_path(qualification.root, document["source_report"]))
    source_root = _private_path(
        qualification.root, str(Path(source["output"]).relative_to(qualification.root))
    )
    if (
        source["report_id"] != document["source_report_id"]
        or source.get("assembly_sha256") != qualification.target["assembly_sha256"]
        or source.get("status") != "private_source_extraction_complete"
        or _inventory(source_root) != source["inventory"]
    ):
        raise ValueError("Private source review input changed")
    inspector = _private_path(qualification.root, document["inspector"])
    project = qualification.root / "mod/SpireShift.ModeInventory"
    if (
        _sha_file(inspector) != document["inspector_sha256"]
        or set(document["inspector_sources"]) != {"Program.cs", "SpireShift.ModeInventory.csproj"}
        or any(
            _sha_file(project / name) != sha for name, sha in document["inspector_sources"].items()
        )
    ):
        raise ValueError("Mode inspector binary or source changed")
    dotnet = Path(document["dotnet"])
    if (
        not dotnet.is_absolute()
        or not dotnet.is_file()
        or _sha_file(dotnet) != document["dotnet_sha256"]
    ):
        raise ValueError("Static inspector runtime changed")
    build = _hashed(_private_path(qualification.root, document["candidate_build_report"]))
    if build["report_id"] != document["candidate_build_report_id"]:
        raise ValueError("Candidate build prerequisite changed")
    candidate = build["build"]["repaired"][0]
    wrapper = _private_path(
        qualification.root, str(Path(candidate["artifact"]).relative_to(qualification.root))
    )
    if _sha_file(wrapper) != candidate["artifact_sha256"]:
        raise ValueError("Candidate assembly changed")
    workspace = _private_path(qualification.root, document["workspace"])
    workspace.mkdir(parents=True, exist_ok=True)
    if (workspace / "report.json").exists() or (workspace / "in-progress.json").exists():
        raise FileExistsError("Preserve the existing audit; use a separately versioned attempt")
    attempt = Path(tempfile.mkdtemp(prefix="audit-", dir=workspace))
    atomic_json(
        workspace / "in-progress.json", {"attempt": str(attempt), "training_allowed": False}
    )
    atomic_json(attempt / "in-progress.json", {"training_allowed": False})
    started = time.monotonic()
    try:
        inventories = {}
        inputs = {"game": archive / GAME_RELATIVE / DATA_RELATIVE / "sts2.dll", "wrapper": wrapper}
        expected = {
            "game": qualification.target["assembly_sha256"],
            "wrapper": candidate["artifact_sha256"],
        }
        for role, assembly in inputs.items():
            output = attempt / f"{role}-mode-references.json"
            run = subprocess.run(
                [str(dotnet), str(inspector), "--assembly", str(assembly), "--output", str(output)],
                text=True,
                capture_output=True,
                timeout=max(1, document["max_wall_seconds"] - (time.monotonic() - started)),
            )
            (attempt / f"{role}-scanner.log").write_text(run.stdout + run.stderr)
            if run.returncode:
                raise ValueError(f"{role} mode inventory failed: {run.stderr[:500]}")
            inventories[role] = json.loads(output.read_text())
            validate_inventory(inventories[role], expected[role])
        assessment = assess_reviews(inventories["game"]["sites"], document["reviews"])
        atomic_json(attempt / "private-review-assessment.json", assessment)
        after = verify_game_archive(qualification, archive)
        if (
            not after["valid"]
            or _sha_file(wrapper) != expected["wrapper"]
            or _inventory(source_root) != source["inventory"]
        ):
            raise ValueError("Audit inputs changed during static inspection")
        summary = {
            key: value for key, value in assessment.items() if key != "unreviewed_method_groups"
        }
        result = _finish(
            attempt,
            {
                "schema_version": "engine-mode-audit-v1",
                "config_id": manifest_identifier(document),
                "qualification_config_id": qualification.config_id,
                "source_report_id": source["report_id"],
                "candidate_build_report_id": build["report_id"],
                "inspector_sha256": document["inspector_sha256"],
                "archive_verification_before": before["report_id"],
                "archive_verification_after": after["report_id"],
                "status": "static_inventory_complete_semantic_review_partial"
                if not assessment["semantic_review_complete"]
                else "static_inventory_and_reviews_complete_runtime_unqualified",
                "inventories": {
                    role: {
                        k: value[k]
                        for k in (
                            "assembly_sha256",
                            "module_mvid",
                            "methods",
                            "method_bodies",
                            "decoded_instructions",
                            "undecoded_bodies",
                        )
                    }
                    | {
                        "references": len(value["sites"]),
                        "inventory_id": manifest_identifier(value),
                    }
                    for role, value in inventories.items()
                },
                "assessment": summary,
                "wall_seconds": time.monotonic() - started,
                "raw_material_private": True,
                "games_launched": 0,
                "full_run_attempts": 0,
                "optimizer_steps": 0,
                "training_allowed": False,
                "mechanics_qualified": False,
                "claim_scope": (
                    "complete_direct_IL_references_to_two_mode_types_and_explicit_method_reviews_"
                    "not_reflection_indirect_aliases_stubs_or_runtime_parity"
                ),
            },
        )
        atomic_json(workspace / "report.json", result)
        (workspace / "in-progress.json").unlink()
        return result
    except BaseException as error:
        _failure(attempt, error)
        raise
