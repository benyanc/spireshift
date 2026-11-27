"""A finite first-combat action differential, separately scoped from training admission."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_checkpoint import verify_checkpoint_input
from spireshift.engine_connector import (
    _probe_connector_private,
    load_connector_qualification_config,
)
from spireshift.engine_native import _private_path
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.engine_starting_bridges import verify_starting_bridges


def probe_shipped_journey(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    return _probe_shipped_journey_document(
        qualification, path, json.loads(path.read_text()), node=node
    )


def _probe_shipped_journey_document(
    qualification: EngineQualificationConfig,
    path: Path,
    document: dict[str, Any],
    *,
    node: Path,
    native_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if (
        document.get("schema_version") != "engine-shipped-journey-config-v1"
        or document.get("stage") != "single_first_combat_public_action_differential_only"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("training_allowed") is not False
        or document.get("successful_payload_policy") != "remove_after_verified_success"
    ):
        raise ValueError("Expected the explicitly scoped single first-combat comparison")
    bridge_path = qualification.root / document["starting_bridge_config"]
    prerequisite = verify_starting_bridges(qualification, bridge_path)
    if prerequisite["batch_report_id"] != document.get("starting_bridge_report_id"):
        raise ValueError("Starting comparison prerequisite changed")
    revision = document.get("journey_revision", "v1")
    if revision not in {"v1", "v2"}:
        raise ValueError("Unknown shipped journey revision")
    ui_revision = document.get("shipped_ui_revision")
    if ui_revision not in {None, "tutorial_v3", "tutorial_v4"} or (
        ui_revision is not None and revision != "v2"
    ):
        raise ValueError("Unknown shipped tutorial revision")
    helpers: tuple[str, ...] = (
        "engine-menu-probe.mjs",
        "engine-checkpoint-shipped-probe.mjs",
        "engine-journey-contract-v2.mjs" if revision == "v2" else "engine-journey-contract.mjs",
        "engine-journey-shipped-probe-v4.mjs"
        if ui_revision == "tutorial_v4"
        else "engine-journey-shipped-probe-v3.mjs"
        if ui_revision == "tutorial_v3"
        else "engine-journey-shipped-probe-v2.mjs"
        if revision == "v2"
        else "engine-journey-shipped-probe.mjs",
    )
    if ui_revision == "tutorial_v3":
        helpers += ("engine-journey-tutorial-v3.mjs",)
    elif ui_revision == "tutorial_v4":
        helpers += ("engine-journey-tutorial-v4.mjs",)
    for name in helpers:
        if _sha_file(qualification.root / "scripts" / name) != document.get(
            "helpers_sha256", {}
        ).get(name):
            raise ValueError("A pinned first-combat comparison helper changed")
    native_path = _private_path(qualification.root, document["checkpoint_report"])
    native = json.loads(native_path.read_text())
    native_config_path = qualification.root / document["native_config"]
    native_config = (
        native_override
        if native_override is not None
        else json.loads(native_config_path.read_text())
    )
    if native_override is not None and document.get(
        "effective_native_config_id"
    ) != manifest_identifier(native_override):
        raise ValueError("The batch's effective native configuration changed")
    journey = native.get("probe", {}).get("journey", [])
    if (
        native_config_path.resolve().parent != path.resolve().parent
        or native.get("config_id") != manifest_identifier(native_config)
        or native_config.get("seed") != document.get("seed")
        or native_config.get("journey_revision", "v1") != revision
        or native_config.get("journey", {}).get("max_actions") != 12
        or not 4 <= len(journey) <= 13
        or journey[0].get("facts", {}).get("kind") != "event_option"
        or journey[-1].get("facts", {}).get("combat", {}).get("round") != 2
        or journey[-1].get("action") is not None
        or any(row.get("action") is None for row in journey[:-1])
        or native.get("probe", {}).get("public_actions_delivered") != len(journey) - 1
        or not native.get("probe", {}).get("gates")
        or any(value is not True for value in native["probe"]["gates"].values())
    ):
        raise ValueError("A complete frozen native first-turn prefix is required")
    fixture = verify_checkpoint_input(qualification, document, panel="journey")
    fixture.update(
        comparison_mode=f"journey_{revision}",
        shipped_ui_revision=ui_revision,
        journey_report_path=str(native_path),
        workspace=str(
            _private_path(qualification.root, document["workspace"]).relative_to(qualification.root)
        ),
    )
    connector_path = qualification.root / document["connector_config"]
    if connector_path.resolve().parent != path.resolve().parent:
        raise ValueError("Pinned Connector prerequisite must remain beside the journey config")
    connector = load_connector_qualification_config(connector_path, qualification)
    if connector.config_id != document["connector_config_id"]:
        raise ValueError("Pinned Connector prerequisite changed")
    result = _probe_connector_private(
        connector, node=node, fixture=fixture, retain_working_game=False
    )
    verify_checkpoint_input(qualification, document, panel="journey")
    # The native prefix is itself hashed, not just the starting save used by the import.
    if json.loads(native_path.read_text()) != native:
        raise ValueError("Native prefix changed during the shipped comparison")
    private_report = result["report_path"]
    result = {k: v for k, v in result.items() if k not in {"report_id", "report_path"}}
    result.update(
        schema_version="engine-shipped-journey-v1",
        journey_config_id=manifest_identifier(document),
        native_report_id=native["report_id"],
        starting_bridge_report_id=prerequisite["batch_report_id"],
        private_shipped_report_path=private_report,
        status="first_combat_prefix_pass"
        if result["verdict"]["status"] == "shipped_checkpoint_input_pass"
        else "first_combat_prefix_incomplete",
        shipped_cross_host_parity=False,
        mechanics_qualified=False,
        claim_scope="single_A8_seed_initial_event_map_entry_first_combat_turn_scoped_public_fields_and_actions_only",
        comparison_exclusions=[
            "effect_text",
            "card_preview_stats",
            "relic_counters",
            "full_map_topology",
            "pile_contents",
            "other_decision_families",
            "later_turns_acts_and_endings",
        ],
    )
    result["report_id"] = manifest_identifier(result)
    return result
