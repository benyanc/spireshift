"""Admission of the repaired public A8 simulator for policy-only learning.

Live UI fidelity is deliberately not asserted by this evidence. Raw captures and
game assemblies stay private; every existing result remains immutable.
"""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from spireshift.adapters.evangambit_public_choices import (
    ADAPTER_ID,
    choice_view,
    load_public_choice_backend,
    public_adapter_digest,
)
from spireshift.backend_admission import MANDATORY_CONFORMANCE_CHECKS
from spireshift.core.manifest import (
    PatchManifest,
    load_patch_manifest,
    manifest_identifier,
    write_frozen_manifest,
)
from spireshift.full_run_backend_repair import load_repair_recipe, show_backend_repair
from spireshift.full_run_experience import atomic_json

PROFILE_ID = "evangambit-source-fixed-ascension-8-v1"
LIMITATIONS = (
    "Only executed committed game fixtures have differential coverage.",
    "Act 2/3 boundaries have synthetic regressions and a pinned-game source audit, "
    "not UI captures.",
    "Forced Architect closing dialogue is collapsed; live playback still needs those UI steps.",
    "Six legacy combat captures omit per-turn hands.",
    "Reachable uncaptured cards, later ancient relics and exact generation odds remain incomplete.",
    "Hidden-world search requires its separate clone qualification; admission is policy-only.",
    "No trained agent win, complete live fidelity or foundation readiness is established.",
)


def identified_document(path: Path, key: str = "report_id") -> dict[str, Any]:
    d: dict[str, Any] = json.loads(path.read_text())
    if d.get(key) != manifest_identifier({k: v for k, v in d.items() if k != key}):
        raise ValueError(f"Saved evidence identity differs: {path}")
    return d


def check_a8_evidence(
    manifest: PatchManifest,
    build: dict[str, Any],
    native_suite: dict[str, Any],
    python_suite: dict[str, Any],
    contract: dict[str, Any],
    rule_audit: dict[str, Any],
    assembly_digest: str,
    assembly_size: int,
    profile: dict[str, Any],
) -> tuple[str, ...]:
    """Assess identities and executed evidence, without native import or admission."""
    errors = []
    libraries = [a for a in manifest.mechanics if a.kind == "compiled-simulator-library"]
    assemblies = [a for a in manifest.mechanics if a.kind == "authoritative-game-assembly"]
    if (
        manifest.admission_status != "pending_conformance"
        or manifest.adapter.component_id != ADAPTER_ID
        or manifest.adapter.digest.value != public_adapter_digest()
        or manifest.patch.game_version != "v0.107.1"
        or manifest.patch.steam_build_id != "23811903"
        or len(libraries) != 1
        or len(assemblies) != 1
    ):
        return ("Candidate is not the pinned public-menu A8 scope",)
    native_sha = libraries[0].digest.value
    if assemblies[0].digest.value != assembly_digest or assemblies[0].size_bytes != assembly_size:
        errors.append("Preserved authoritative game assembly differs")
    if (
        build.get("candidate_revision") != manifest.engine.revision
        or build.get("native_sha256") != native_sha
        or build.get("regression_tests", {}).get("passed") != 240
        or build.get("regression_tests", {}).get("failed") != 0
    ):
        errors.append("Native repair/build identity or targeted checks differ")
    if (
        native_suite.get("build_report_id") != build.get("report_id")
        or native_suite.get("candidate_revision") != manifest.engine.revision
        or native_suite.get("native_sha256") != native_sha
        or native_suite.get("counts", {}).get("passed", 0) < 4942
        or native_suite.get("counts", {}).get("failed") != 0
        or len(native_suite.get("skips", [])) != 1
        or "StepCostProbe" not in native_suite["skips"][0]
    ):
        errors.append("Complete native suite is missing, failed or from another candidate")
    suites = {e.get("suite"): e for e in python_suite.get("executions", [])}
    if (
        python_suite.get("candidate_revision") != manifest.engine.revision
        or python_suite.get("native_sha256") != native_sha
        or set(suites) != {"test_sts2_gym.py", "test_live_fixtures.py"}
        or any(e.get("status") != "pass" or e.get("failed") != 0 for e in suites.values())
        or suites.get("test_sts2_gym.py", {}).get("passed") != 31
        or suites.get("test_live_fixtures.py", {}).get("passed") != 420
        or suites.get("test_live_fixtures.py", {}).get("skipped") != 6
        or any(
            reason != "capture predates per-turn hands"
            for reason in suites.get("test_live_fixtures.py", {}).get("skip_reasons", [])
        )
    ):
        errors.append("Native Python and live-fixture checks differ or did not all pass")
    c = contract.get("conformance", {})
    statuses = {check.get("check_id"): check.get("status") for check in c.get("checks", [])}
    if (
        contract.get("ruleset_manifest_id") != manifest.manifest_id
        or c.get("ruleset", {}).get("manifest_id") != manifest.manifest_id
        or c.get("verdict") != "pass"
        or any(statuses.get(k) != "pass" for k in MANDATORY_CONFORMANCE_CHECKS)
    ):
        errors.append("Public environment contract differs or has incomplete checks")
    if (
        rule_audit.get("assembly_sha256") != assembly_digest
        or rule_audit.get("empirical_act2_or_act3_fixture_added") is not False
        or rule_audit.get("all_ascension8_effects_verified") is not False
        or {finding.get("rule") for finding in rule_audit.get("source_findings", [])}
        != {
            "earlier_boss_reward_advances_to_next_act",
            "total_floor_is_distinct_from_act_progress",
            "ending_includes_forced_architect_dialogue",
            "a8_is_not_a0_or_double_boss",
        }
    ):
        errors.append("Pinned rule audit differs or hides its coverage limitations")
    if profile != {
        "profile_id": PROFILE_ID,
        "source_declared_ascension_level": 8,
        "selectable_difficulty": False,
        "live_game_conformance_verified": False,
    }:
        errors.append("Actual native profile differs from fixed A8")
    return tuple(errors)


def admit_a8_candidate(config_path: Path, game_assembly: Path) -> dict[str, Any]:
    config = identified_document(config_path, "config_id")
    if config.get("schema_version") != "public-a8-admission-config-v1":
        raise ValueError("Unsupported A8 admission configuration")
    refs = config["inputs"]
    for ref in refs.values():
        if hashlib.sha256(Path(ref["path"]).read_bytes()).hexdigest() != ref["sha256"]:
            raise ValueError(f"Pinned admission input bytes differ: {ref['path']}")
    recipe = load_repair_recipe(Path(refs["repair_config"]["path"]))
    build = show_backend_repair(recipe)
    manifest = load_patch_manifest(Path(refs["public_manifest"]["path"]))
    native_suite = identified_document(Path(refs["native_suite"]["path"]))
    python_suite = identified_document(Path(refs["python_suite"]["path"]))
    contract = identified_document(Path(refs["contract"]["path"]))
    audit = identified_document(Path(refs["rule_audit"]["path"]), "evidence_id")
    # Check the executed test bytes as well as the signed summary. All nine
    # three-act/reward regression cases must actually be present and successful.
    trx = Path(refs["native_suite"]["path"]).parent / "full-suite.trx"
    if hashlib.sha256(trx.read_bytes()).hexdigest() != native_suite["test_report_sha256"]:
        raise ValueError("Native test execution bytes differ")
    results = [e for e in ET.parse(trx).getroot().iter() if e.tag.endswith("UnitTestResult")]
    boundaries = [
        e for e in results if "SpireShiftFullRunCompletionTests." in e.get("testName", "")
    ]
    if len(boundaries) != 9 or any(e.get("outcome") != "Passed" for e in boundaries):
        raise ValueError("Executed three-act/terminal regressions are incomplete")
    for execution in python_suite["executions"]:
        log = Path(refs["python_suite"]["path"]).parent / (execution["suite"] + ".log")
        if hashlib.sha256(log.read_bytes()).hexdigest() != execution["log_sha256"]:
            raise ValueError("Python fixture execution bytes differ")
    # Revalidate the original authoritative fixture tree; no new capture or
    # synthetic state can silently replace that ground truth.
    import subprocess

    tree = subprocess.check_output(
        ["git", "-C", str(recipe.candidate), "rev-parse", "HEAD:tests/fixtures"], text=True
    ).strip()
    if tree != config["authoritative_fixture_tree"]:
        raise ValueError("Authoritative fixture tree changed")
    digest = hashlib.sha256(game_assembly.read_bytes()).hexdigest()
    loaded = load_public_choice_backend(
        recipe.candidate, Path(refs["public_manifest"]["path"]), allow_pending=True
    )
    env = loaded.factory()
    try:
        profile = choice_view(env.reset(config["inspected_train_seed"])).fixed_profile
    finally:
        env.close()
    errors = check_a8_evidence(
        manifest,
        build,
        native_suite,
        python_suite,
        contract,
        audit,
        digest,
        game_assembly.stat().st_size,
        profile,
    )
    if errors:
        raise ValueError("A8 admission rejected: " + "; ".join(errors))
    body = manifest.body_dict()
    body["admission_status"] = "admitted"
    admitted = PatchManifest.from_mapping({**body, "manifest_id": manifest_identifier(body)})
    report = {
        "schema_version": "public-a8-policy-learning-admission-v1",
        "config_id": config["config_id"],
        "verdict": "admitted_for_policy_only_a8_learning",
        "source_manifest_id": manifest.manifest_id,
        "admitted_manifest_id": admitted.manifest_id,
        "runtime": loaded.evidence.as_dict(),
        "profile": profile,
        "build_report_id": build["report_id"],
        "native_suite_report_id": native_suite["report_id"],
        "python_suite_report_id": python_suite["report_id"],
        "contract_report_id": contract["report_id"],
        "rule_audit_id": audit["evidence_id"],
        "authoritative_fixture_tree": tree,
        "three_act_and_terminal_regressions": len(boundaries),
        "empirical_later_act_ui_parity": False,
        "coverage_limitations": list(LIMITATIONS),
        "agent_games_played": 0,
        "native_profile_resets": 1,
        "optimizer_steps": 0,
        "foundation_readiness_established": False,
        "automatic_followup": False,
        "claim_scope": (
            "pinned_captured_fixture_and_public_contract_admission_not_complete_live_fidelity"
        ),
    }
    report["report_id"] = manifest_identifier(report)
    output = Path(config["output_dir"])
    path = output / "admission-report.json"
    if path.exists():
        saved = identified_document(path)
        if saved != report:
            raise ValueError("Saved admission differs; never replace its evidence")
    else:
        atomic_json(path, report)
    write_frozen_manifest(admitted, Path(config["admitted_manifest"]))
    return report
