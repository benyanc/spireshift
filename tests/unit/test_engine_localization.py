"""Synthetic packs only: finite exact asset extraction, integrity and path boundaries."""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_localization import read_localization_pack, verify_native_localization
from spireshift.engine_qualification import EngineQualificationConfig, _inventory


def synthetic_pack(
    path: Path,
    names: tuple[str, ...] = ("localization/eng/cards.json",),
    *,
    body: bytes = b'{"EXAMPLE.title":"Example"}',
    pack_flags: int = 2,
    file_flags: int = 0,
    bad_digest: bool = False,
    offset: int = 0,
) -> None:
    header_size = 112
    directory_offset = header_size + len(body)
    header = struct.pack(
        "<6I2Q", 0x43504447, 3, 4, 5, 1, pack_flags, header_size, directory_offset
    ).ljust(header_size, b"\0")
    directory = struct.pack("<I", len(names))
    for name in names:
        encoded = name.encode("utf-8")
        digest = b"0" * 16 if bad_digest else hashlib.md5(body, usedforsecurity=False).digest()
        directory += (
            struct.pack("<I", len(encoded))
            + encoded
            + struct.pack("<2Q", offset, len(body))
            + digest
            + struct.pack("<I", file_flags)
        )
    path.write_bytes(header + body + directory)


def test_only_named_languages_are_extracted_byte_for_byte(tmp_path: Path) -> None:
    pack = tmp_path / "synthetic.pck"
    synthetic_pack(
        pack,
        (
            "localization/eng/cards.json",
            "localization/zhs/cards.json",
            "localization/deu/cards.json",
            "textures/example.png",
        ),
    )
    tables, metadata = read_localization_pack(pack)
    assert set(tables) == {"localization/eng/cards.json", "localization/zhs/cards.json"}
    assert tables["localization/eng/cards.json"] == b'{"EXAMPLE.title":"Example"}'
    assert metadata["pack_entries"] == 4


@pytest.mark.parametrize(
    "name",
    [
        "../localization/eng/cards.json",
        "/localization/eng/cards.json",
        "localization\\eng\\cards.json",
        "localization/eng/../cards.json",
    ],
)
def test_no_path_can_escape_the_private_extraction(tmp_path: Path, name: str) -> None:
    pack = tmp_path / "synthetic.pck"
    synthetic_pack(pack, (name,))
    with pytest.raises(ValueError, match="Unsafe"):
        read_localization_pack(pack)


def test_duplicate_native_entries_are_not_silently_overwritten(tmp_path: Path) -> None:
    pack = tmp_path / "synthetic.pck"
    synthetic_pack(pack, ("localization/eng/cards.json",) * 2)
    with pytest.raises(ValueError, match="duplicate"):
        read_localization_pack(pack)


@pytest.mark.parametrize("flags", [0, 1, 3, 6])
def test_encrypted_sparse_and_unknown_packs_are_refused(tmp_path: Path, flags: int) -> None:
    pack = tmp_path / "synthetic.pck"
    synthetic_pack(pack, pack_flags=flags)
    with pytest.raises(ValueError, match="unsupported"):
        read_localization_pack(pack)


@pytest.mark.parametrize(
    "mutation, message",
    [("digest", "native pack digest"), ("offset", "bounds"), ("file_flags", "entry")],
)
def test_corrupt_or_uninterpretable_entries_fail_closed(
    tmp_path: Path, mutation: str, message: str
) -> None:
    pack = tmp_path / "synthetic.pck"
    synthetic_pack(
        pack,
        bad_digest=mutation == "digest",
        offset=1000 if mutation == "offset" else 0,
        file_flags=1 if mutation == "file_flags" else 0,
    )
    with pytest.raises(ValueError, match=message):
        read_localization_pack(pack)


def test_truncated_directory_is_refused(tmp_path: Path) -> None:
    pack = tmp_path / "synthetic.pck"
    synthetic_pack(pack)
    pack.write_bytes(pack.read_bytes()[:-2])
    with pytest.raises(ValueError, match="Truncated"):
        read_localization_pack(pack)


def test_arbitrary_json_is_not_accepted_as_native_string_text(tmp_path: Path) -> None:
    pack = tmp_path / "synthetic.pck"
    synthetic_pack(pack, body=json.dumps({"arbitrary": {"nested": 1}}).encode())
    with pytest.raises(ValueError, match="string localization"):
        read_localization_pack(pack)


@pytest.mark.parametrize("changed", ["text", "extra_file", "report"])
def test_completed_text_inventory_rejects_changes_before_a_native_launch(
    tmp_path: Path, changed: str
) -> None:
    qualification = EngineQualificationConfig({"test": "qualification"}, tmp_path)
    directory = tmp_path / "artifacts/native-text"
    for language in ("eng", "zhs"):
        target = directory / f"localization_{language}"
        target.mkdir(parents=True)
        for index in range(46):
            (target / f"table_{index}.json").write_text('{"EXAMPLE.title":"Synthetic"}')
    document = {
        "schema_version": "native-localization-extraction-v1",
        "qualification_config_id": qualification.config_id,
        "pack_sha256": "0" * 64,
        "directory": str(directory),
        "tables": {"eng": 46, "zhs": 46},
        "inventory": _inventory(directory),
        "games_launched": 0,
        "training_allowed": False,
    }
    document["report_id"] = manifest_identifier(document)
    report = directory / "extraction.json"
    report.write_text(json.dumps(document))
    pins = {
        "directory": "artifacts/native-text",
        "report_id": document["report_id"],
        "pack_sha256": document["pack_sha256"],
    }
    assert verify_native_localization(qualification, pins) == directory
    if changed == "text":
        (directory / "localization_eng/table_0.json").write_text('{"EXAMPLE.title":"Changed"}')
    elif changed == "extra_file":
        (directory / "localization_eng/unpinned.json").write_text("{}")
    else:
        document["training_allowed"] = True
        report.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="changed"):
        verify_native_localization(qualification, pins)
