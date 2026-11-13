from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _sha_file
from spireshift.native_interface_audit import inventory
from spireshift.native_interface_build import verify_build


def test_source_inventory_includes_generic_reads_and_nullable_owned_records(tmp_path: Path) -> None:
    host = tmp_path / "host/LiveHost"
    host.mkdir(parents=True)
    reader = host / "LiveObservationReader.cs"
    reader.write_text(
        'new("shop_room", static () => new ShopRoom());\npublic string Kind => "rest_site";'
    )
    contract = host / "LiveHostContracts.cs"
    contract.write_text(
        "public sealed record Offer(string EntityId, string SlotEntityId, "
        "string? Description, IReadOnlyDictionary<string, int> Costs);"
    )
    reads = host / "ReadService.cs"
    reads.write_text('const string kind = "surface_card";')
    simulator = tmp_path / "RunSimulator.cs"
    simulator.write_text('["decision"] = "event_choice";')
    result = inventory([reader, contract, reads, simulator])
    assert result["official_surface_kinds"] == ["rest_site", "shop_room"]
    assert result["official_read_kinds"] == ["surface_card"]
    assert result["CLI_decisions"] == ["event_choice"]
    fields = result["declared_record_fields"]["Offer"]
    assert [f["field"] for f in fields] == ["entity_id", "slot_entity_id", "description", "costs"]
    assert fields[2]["nullable"] and not fields[3]["nullable"]


def test_changed_second_export_build_does_not_qualify(tmp_path: Path) -> None:
    artifact = tmp_path / "host.dll"
    artifact.write_bytes(b"one exact diagnostic assembly")
    pin = {"artifact_sha256": _sha_file(artifact), "source_diff_id": "one"}
    cfg = {"expected_baseline": pin, "expected_repaired": pin}
    run = {**pin, "artifact": str(artifact)}
    report = {
        "schema_version": "interface-cli-export-build-result-v1",
        "config_id": manifest_identifier(cfg),
        "sources": {},
        "build": {
            "status": "local_candidate_built_unqualified",
            "baseline": [run, run],
            "repaired": [run, {**run, "source_diff_id": "changed"}],
        },
    }
    with pytest.raises(ValueError, match="exact pins"):
        verify_build(tmp_path, cfg, report)


def test_export_receipt_cannot_hide_changed_assembly_bytes(tmp_path: Path) -> None:
    artifact = tmp_path / "host.dll"
    artifact.write_bytes(b"original")
    pin = {"artifact_sha256": _sha_file(artifact)}
    cfg = {"expected_baseline": pin, "expected_repaired": pin}
    run = {**pin, "artifact": str(artifact)}
    report = {
        "schema_version": "interface-cli-export-build-result-v1",
        "config_id": manifest_identifier(cfg),
        "sources": {},
        "build": {
            "status": "local_candidate_built_unqualified",
            "baseline": [run, run],
            "repaired": [run, run],
        },
    }
    artifact.write_bytes(b"changed")
    with pytest.raises(ValueError, match="assembly bytes"):
        verify_build(tmp_path, cfg, report)


def test_live_interface_context_requires_exact_source_membership_before_launch(
    tmp_path: Path,
) -> None:
    from spireshift.native_interface_inputs import load

    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema_version": "wrong", "training_allowed": False}))
    with pytest.raises(ValueError, match="finite"):
        load(tmp_path, path)
    assert list(tmp_path.iterdir()) == [path]


def test_js_interface_contract_checks_when_node_is_available() -> None:
    import shutil

    node = shutil.which("node")
    if node is None:
        pytest.skip("Bundled Node contract suite is run explicitly on native hosts")
    root = Path(__file__).resolve().parents[2]
    subprocess.run(
        [node, "--test", "scripts/engine-interface-contract-v1.test.mjs"],
        cwd=root,
        check=True,
        timeout=20,
        capture_output=True,
    )
