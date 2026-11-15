"""Read only the frozen game's localization from an unencrypted standalone Godot V3 pack.

No game rules, fallback text, game launch or training. See Godot 4.5 file_access_pack.cpp
for the public directory format. Proprietary table bytes remain under artifacts/.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_native import _private_path
from spireshift.engine_qualification import (
    GAME_RELATIVE,
    EngineQualificationConfig,
    _inventory,
    _sha_file,
)
from spireshift.full_run_experience import atomic_json

PACK_RELATIVE = "SlayTheSpire2.app/Contents/Resources/Slay the Spire 2.pck"
LOCALIZATION_PATTERN = re.compile(r"localization/(eng|zhs)/([a-z0-9_]+\.json)")


def _read(stream: BinaryIO, size: int) -> bytes:
    value = stream.read(size)
    if len(value) != size:
        raise ValueError("Truncated game pack")
    return value


def read_localization_pack(pack: Path) -> tuple[dict[str, bytes], dict[str, Any]]:
    """Bounded directory and table reads; reject encryption, deltas and unsafe names."""
    length = pack.stat().st_size
    tables: dict[str, bytes] = {}
    seen: set[str] = set()
    entries = []
    with pack.open("rb") as stream:
        magic, version, major, minor, patch, flags = struct.unpack("<6I", _read(stream, 24))
        if magic != 0x43504447 or version != 3 or (major, minor, patch) != (4, 5, 1):
            raise ValueError("Expected the frozen game's standalone Godot 4.5.1 V3 pack")
        if flags != 2:
            raise ValueError("Encrypted, sparse or unknown game packs are unsupported")
        base, directory = struct.unpack("<2Q", _read(stream, 16))
        if not 40 <= base <= directory < length - 4:
            raise ValueError("Invalid game pack directory bounds")
        stream.seek(directory)
        count = struct.unpack("<I", _read(stream, 4))[0]
        if not 1 <= count <= 100_000:
            raise ValueError("Invalid game pack file count")
        for _ in range(count):
            size = struct.unpack("<I", _read(stream, 4))[0]
            if not 1 <= size <= 4096:
                raise ValueError("Invalid game pack path length")
            name = _read(stream, size).rstrip(b"\0").decode("utf-8")
            path = PurePosixPath(name)
            if (
                "\0" in name
                or "\\" in name
                or path.is_absolute()
                or ".." in path.parts
                or str(path) != name
                or name in seen
            ):
                raise ValueError("Unsafe or duplicate game pack path")
            seen.add(name)
            offset, file_size = struct.unpack("<2Q", _read(stream, 16))
            digest = _read(stream, 16)
            file_flags = struct.unpack("<I", _read(stream, 4))[0]
            matched = LOCALIZATION_PATTERN.fullmatch(name)
            if matched is None:
                continue
            if file_flags != 0 or not 0 < file_size <= 2_000_000:
                raise ValueError("Unsupported localization entry or size")
            if base + offset + file_size > directory:
                raise ValueError("Localization entry exceeds pack data bounds")
            entries.append((name, base + offset, file_size, digest))
        if len(entries) > 128 or sum(item[2] for item in entries) > 16_000_000:
            raise ValueError("Localization extraction exceeds its finite cap")
        for name, offset, size, digest in entries:
            stream.seek(offset)
            content = _read(stream, size)
            if hashlib.md5(content, usedforsecurity=False).digest() != digest:
                raise ValueError("Localization entry differs from its native pack digest")
            document = json.loads(content)
            if not isinstance(document, dict) or not all(
                isinstance(key, str) and isinstance(value, str) for key, value in document.items()
            ):
                raise ValueError("Expected a native string localization table")
            tables[name] = content
    if not tables:
        raise ValueError("No native English/Chinese localization tables were found")
    return tables, {"pack_format": version, "godot_version": "4.5.1", "pack_entries": count}


def extract_native_localization(
    qualification: EngineQualificationConfig,
    archive: Path,
    destination: Path,
    expected_pack_sha256: str,
) -> dict[str, Any]:
    destination = _private_path(qualification.root, str(destination))
    if destination.exists():
        raise FileExistsError("Preserve the existing extraction; verify it rather than overwriting")
    pack = archive / GAME_RELATIVE / PACK_RELATIVE
    if _sha_file(pack) != expected_pack_sha256:
        raise ValueError("Game pack differs from the exact frozen asset pin")
    tables, details = read_localization_pack(pack)
    destination.mkdir(parents=True)
    counts: dict[str, int] = {}
    keys: dict[str, int] = {}
    for name, content in tables.items():
        _, language, filename = name.split("/")
        target = destination / f"localization_{language}" / filename
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(content)
        counts[language] = counts.get(language, 0) + 1
        keys[language] = keys.get(language, 0) + len(json.loads(content))
    body = {
        "schema_version": "native-localization-extraction-v1",
        "qualification_config_id": qualification.config_id,
        "pack_sha256": expected_pack_sha256,
        **details,
        "tables": counts,
        "keys": keys,
        "directory": str(destination),
        "inventory": _inventory(destination),
        "games_launched": 0,
        "training_allowed": False,
    }
    body["report_id"] = manifest_identifier(body)
    atomic_json(destination / "extraction.json", body)
    return body


def verify_native_localization(
    qualification: EngineQualificationConfig, pins: dict[str, Any]
) -> Path:
    directory = _private_path(qualification.root, pins["directory"])
    document = json.loads((directory / "extraction.json").read_text())
    body = {key: value for key, value in document.items() if key != "report_id"}
    inventory = [item for item in _inventory(directory) if item["path"] != "extraction.json"]
    if (
        manifest_identifier(body) != document.get("report_id")
        or document.get("schema_version") != "native-localization-extraction-v1"
        or document.get("report_id") != pins.get("report_id")
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("directory") != str(directory)
        or document.get("pack_sha256") != pins.get("pack_sha256")
        or document.get("tables") != {"eng": 46, "zhs": 46}
        or inventory != document.get("inventory")
        or document.get("games_launched") != 0
        or document.get("training_allowed") is not False
    ):
        raise ValueError("Native localization evidence or extracted tables changed")
    return directory
