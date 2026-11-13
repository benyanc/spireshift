"""Audit saved first-turn comparisons without launching or replaying any game."""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_checkpoint import _saved_private_path, verify_checkpoint_input
from spireshift.engine_connector import _evaluate_connector_checkpoint
from spireshift.engine_journey_bridges import validate_journey_cases
from spireshift.engine_native import _private_path
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file


def _hashed(path: Path) -> dict[str, Any]:
    value: dict[str, Any] = json.loads(path.read_text())
    if manifest_identifier(
        {k: v for k, v in value.items() if k not in {"report_id", "report_path"}}
    ) != value.get("report_id"):
        raise ValueError(f"Saved report changed: {path.name}")
    return value


def verify_journey_bridges(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    document = json.loads(path.read_text())
    if (
        document.get("schema_version") != "engine-journey-bridges-config-v1"
        or document.get("stage") != "owner_first_combat_prefix_differentials_only"
        or document.get("training_allowed") is not False
        or document.get("qualification_config_id") != qualification.config_id
    ):
        raise ValueError("Expected the frozen scoped first-combat configuration")
    planned = validate_journey_cases(document)
    templates = {}
    for role in ("native", "shipped"):
        template_path = qualification.root / document[f"{role}_template"]
        templates[role] = json.loads(template_path.read_text())
        if (
            template_path.resolve().parent != path.resolve().parent
            or manifest_identifier(templates[role]) != document[f"{role}_template_id"]
        ):
            raise ValueError("Frozen first-combat template changed")
    for name, expected in templates["shipped"]["helpers_sha256"].items():
        if Path(name).name != name or _sha_file(qualification.root / "scripts" / name) != expected:
            raise ValueError("Frozen first-combat comparison helper changed")
    workspace = _private_path(qualification.root, document["workspace"])
    batch = _hashed(workspace / "batch.json")
    if (
        batch.get("config_id") != manifest_identifier(document)
        or batch.get("qualification_config_id") != qualification.config_id
        or batch.get("status") != "first_combat_comparisons_pass"
        or batch.get("completed_cases") != 8
        or batch.get("planned_cases") != 8
        or batch.get("independent_seeds") != 2
        or batch.get("seed_option_pairs") != 4
        or batch.get("repeated_public_prefixes_identical") is not True
        or batch.get("failed_cases") != 0
        or batch.get("not_attempted_cases") != 0
        or batch.get("training_allowed") is not False
        or batch.get("full_run_attempts") != 0
        or batch.get("optimizer_steps") != 0
        or batch.get("shipped_cross_host_parity") is not False
        or [{k: c.get(k) for k in ("case_id", "seed", "starting_option")} for c in batch["cases"]]
        != planned
    ):
        raise ValueError("Expected the complete frozen eight-case first-combat batch")
    inputs = []
    pairs: dict[tuple[str, str], list[Any]] = {}
    for case in batch["cases"]:
        directory = workspace / case["case_id"]
        native_path = _private_path(qualification.root, case["native_report"])
        shipped_path = _private_path(qualification.root, case["shipped_report"])
        if (native_path, shipped_path) != (
            directory / "native-report.json",
            directory / "shipped-report.json",
        ):
            raise ValueError("Case evidence moved outside its named directory")
        native, shipped = _hashed(native_path), _hashed(shipped_path)
        native_config = copy.deepcopy(templates["native"])
        native_config.update(
            seed=case["seed"], workspace=str((directory / "native").relative_to(qualification.root))
        )
        native_config["journey"]["starting_option"] = case["starting_option"]
        attempt = _saved_private_path(qualification, native["report_path"]).parent
        shipped_config = copy.deepcopy(templates["shipped"])
        shipped_config.update(
            seed=case["seed"],
            workspace=str((directory / "shipped").relative_to(qualification.root)),
            checkpoint_report=case["native_report"],
            checkpoint_report_id=case["native_report_id"],
            snapshot_sha256=_sha_file(attempt / "private-starting-snapshot.json"),
            effective_native_config_id=manifest_identifier(native_config),
        )
        verify_checkpoint_input(qualification, shipped_config, panel="journey")
        original = _hashed(
            _saved_private_path(qualification, shipped["private_shipped_report_path"])
        )
        plan = native["probe"]["journey"]
        if (
            native.get("config_id") != manifest_identifier(native_config)
            or native.get("report_id") != case["native_report_id"]
            or shipped.get("report_id") != case["shipped_report_id"]
            or shipped.get("journey_config_id") != manifest_identifier(shipped_config)
            or shipped.get("native_report_id") != native["report_id"]
            or shipped.get("status") != "first_combat_prefix_pass"
            or shipped.get("training_allowed") is not False
            or shipped.get("shipped_cross_host_parity") is not False
            or shipped.get("mechanics_qualified") is not False
            or _evaluate_connector_checkpoint(shipped.get("checks", {}), journey=True)["status"]
            != "shipped_checkpoint_input_pass"
            or not shipped.get("checks")
            or any(v is not True for v in shipped["checks"].values())
            or original.get("probe") != shipped.get("probe")
            or native.get("probe", {}).get("public_actions_delivered") != len(plan) - 1
            or case.get("compared_snapshots") != len(plan)
            or case.get("status") != "first_combat_prefix_pass"
            or case.get("tutorial_steps") != 3
            or case.get("public_actions_delivered") != len(plan) - 1
            or case.get("native_public_prefix_id") != manifest_identifier(plan)
            or case.get("disposable_payload_removed_after_verified_success") is not True
            or shipped.get("disposable_payload_removed_after_verified_success") is not True
            or (
                _saved_private_path(qualification, shipped["private_shipped_report_path"]).parent
                / "game"
            ).exists()
        ):
            raise ValueError(f"Incomplete or changed first-combat case: {case['case_id']}")
        inputs.append(
            {
                "plan": plan,
                "native_snapshots": str(attempt / "private-journey-snapshots.jsonl"),
                "shipped": shipped["probe"],
            }
        )
        pairs.setdefault((case["seed"], case["starting_option"]), []).append(plan)
    if any(len(rows) != 2 or rows[0] != rows[1] for rows in pairs.values()):
        raise ValueError("Repeated native public prefixes differ")
    audited = subprocess.run(
        [str(node), str(qualification.root / "scripts/verify-engine-journey-saved.mjs")],
        input=json.dumps(inputs),
        text=True,
        capture_output=True,
        timeout=30,
        check=True,
    )
    counts = json.loads(audited.stdout)
    result = {
        "schema_version": "engine-journey-saved-verification-v1",
        "valid": True,
        "batch_report_id": batch["report_id"],
        "verifier_sha256": _sha_file(
            qualification.root / "scripts/verify-engine-journey-saved.mjs"
        ),
        "verified_cases": len(counts),
        "independent_seeds": 2,
        **{
            key: sum(row[key] for row in counts)
            for key in ("compared_snapshots", "public_actions_delivered", "tutorial_steps")
        },
        "games_launched": 0,
        "optimizer_steps": 0,
        "training_allowed": False,
        "claim_scope": (
            "saved_first_turn_raw_public_snapshots_actions_delivery_and_tutorial_facts_only"
        ),
    }
    result["report_id"] = manifest_identifier(result)
    return result
