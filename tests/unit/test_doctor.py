from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from spireshift.doctor import (
    GameCandidate,
    GameInstallationError,
    find_game_installation,
    inspect_game_installation,
    parse_steam_library_folders,
)


def _write_macos_installation(root: Path, *, assembly: bytes = b"fake-sts2-assembly") -> None:
    contents = root / "SlayTheSpire2.app/Contents"
    executable = contents / "MacOS/Slay the Spire 2"
    resources = contents / "Resources"
    data = resources / "data_sts2_macos_arm64"
    executable.parent.mkdir(parents=True)
    data.mkdir(parents=True)
    executable.write_bytes(b"fake executable")
    (resources / "release_info.json").write_text(
        json.dumps(
            {
                "version": "v0.test.1",
                "commit": "deadbeef",
                "branch": "test",
                "date": "2026-09-19T00:00:00Z",
                "main_assembly_hash": 123,
            }
        )
    )
    (data / "sts2.runtimeconfig.json").write_text(
        json.dumps(
            {
                "runtimeOptions": {
                    "tfm": "net9.0",
                    "includedFrameworks": [{"name": "Microsoft.NETCore.App", "version": "9.0.7"}],
                }
            }
        )
    )
    (data / "sts2.dll").write_bytes(assembly)


def test_empty_game_directory_is_rejected(tmp_path: Path) -> None:
    game = tmp_path / "Slay the Spire 2"
    game.mkdir()
    candidate = GameCandidate(game, "test", None)

    with pytest.raises(GameInstallationError) as raised:
        inspect_game_installation(candidate, system="Darwin", machine="arm64")

    message = str(raised.value)
    assert "executable is missing" in message
    assert "release_info.json is missing" in message
    assert "sts2.runtimeconfig.json is missing" in message
    assert "sts2.dll is missing" in message


def test_valid_installation_emits_stable_identity_manifest(tmp_path: Path) -> None:
    game = tmp_path / "Slay the Spire 2"
    assembly = b"fixture assembly bytes"
    _write_macos_installation(game, assembly=assembly)
    app_manifest = tmp_path / "appmanifest_2868840.acf"
    app_manifest.write_text('"buildid" "23811903"')
    candidate = GameCandidate(game, "test", app_manifest)

    installation = inspect_game_installation(candidate, system="Darwin", machine="arm64")
    manifest = installation.manifest()

    assert installation.version == "v0.test.1"
    assert installation.commit == "deadbeef"
    assert installation.runtime_tfm == "net9.0"
    assert installation.runtime_frameworks == ("Microsoft.NETCore.App/9.0.7",)
    assert installation.steam_build_id == "23811903"
    assert installation.assembly_sha256 == hashlib.sha256(assembly).hexdigest()
    assert manifest["schema_version"] == "game-installation-v1"
    assert manifest["platform"] == "macos"
    assert manifest["architecture"] == "arm64"
    assert cast_dict(manifest["release"])["steam_build_id"] == "23811903"
    assert cast_dict(manifest["assembly"])["sha256"] == hashlib.sha256(assembly).hexdigest()


def test_discovers_game_in_secondary_steam_library(tmp_path: Path) -> None:
    home = tmp_path / "home"
    steam = home / "Library/Application Support/Steam"
    secondary = tmp_path / "Secondary Steam"
    game = secondary / "steamapps/common/Slay the Spire 2"
    steamapps = steam / "steamapps"
    steamapps.mkdir(parents=True)
    (steamapps / "libraryfolders.vdf").write_text(
        f'"libraryfolders"\n{{\n  "1" {{ "path" "{secondary}" }}\n}}\n'
    )
    (secondary / "steamapps").mkdir(parents=True, exist_ok=True)
    (secondary / "steamapps/appmanifest_2868840.acf").write_text('"buildid" "42"')
    _write_macos_installation(game)

    installation = find_game_installation(
        home=home,
        system="Darwin",
        machine="arm64",
        environ={},
    )

    assert installation is not None
    assert installation.root == game.resolve()
    assert installation.steam_build_id == "42"


def test_explicit_invalid_path_does_not_fall_back_silently(tmp_path: Path) -> None:
    home = tmp_path / "home"
    default_game = home / "Library/Application Support/Steam/steamapps/common/Slay the Spire 2"
    _write_macos_installation(default_game)
    invalid = tmp_path / "empty"
    invalid.mkdir()

    installation = find_game_installation(
        home=home,
        system="Darwin",
        machine="arm64",
        environ={"SPIRESHIFT_GAME_DIR": str(invalid)},
    )

    assert installation is None


def test_host_architecture_must_have_its_own_runtime(tmp_path: Path) -> None:
    game = tmp_path / "Slay the Spire 2"
    _write_macos_installation(game)
    candidate = GameCandidate(game, "test", None)

    with pytest.raises(GameInstallationError, match="data_sts2_macos_x86_64"):
        inspect_game_installation(candidate, system="Darwin", machine="x86_64")


def test_corrupt_release_metadata_is_rejected(tmp_path: Path) -> None:
    game = tmp_path / "Slay the Spire 2"
    _write_macos_installation(game)
    release = game / "SlayTheSpire2.app/Contents/Resources/release_info.json"
    release.write_text("not json")

    with pytest.raises(GameInstallationError, match="release_info.json is invalid"):
        inspect_game_installation(
            GameCandidate(game, "test", None),
            system="Darwin",
            machine="arm64",
        )


def test_parses_modern_and_legacy_steam_library_formats() -> None:
    content = r"""
"libraryfolders"
{
    "1" "D:\\LegacySteam"
    "2"
    {
        "path" "E:\\ModernSteam"
    }
}
"""

    assert parse_steam_library_folders(content) == [
        r"E:\ModernSteam",
        r"D:\LegacySteam",
    ]


def cast_dict(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value
