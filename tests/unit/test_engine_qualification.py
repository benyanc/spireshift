from __future__ import annotations

import hashlib
import io
import json
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import spireshift.engine_download as download
import spireshift.engine_qualification as engine
from spireshift.cli import main
from spireshift.doctor import GameCandidate


@pytest.fixture
def build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    monkeypatch.setattr("spireshift.doctor.platform.system", lambda: "Darwin")
    monkeypatch.setattr("spireshift.doctor.platform.machine", lambda: "arm64")
    game = tmp_path / "library/steamapps/common/Slay the Spire 2"
    contents = game / "SlayTheSpire2.app/Contents"
    resources = contents / "Resources"
    data = resources / "data_sts2_macos_arm64"
    data.mkdir(parents=True)
    exe = contents / "MacOS/Slay the Spire 2"
    exe.parent.mkdir()
    exe.write_bytes(b"fixture executable")
    exe.chmod(0o755)
    (contents / "Info.plist").write_text("fixture app metadata")
    (resources / "Slay the Spire 2.pck").write_bytes(b"fixture assets")
    (resources / "release_info.json").write_text(
        json.dumps(
            {
                "version": "v0.111.0",
                "commit": "41cef1ea",
                "main_assembly_hash": 1172974615,
            }
        )
    )
    (data / "sts2.runtimeconfig.json").write_text(
        json.dumps(
            {
                "runtimeOptions": {"tfm": "net9.0"},
            }
        )
    )
    (data / "sts2.deps.json").write_text("{}")
    dll = data / "sts2.dll"
    dll.write_bytes(b"fixture official assembly")
    godot = data / "GodotSharp.dll"
    godot.write_bytes(b"fixture Godot assembly")
    config_document: dict[str, Any] = json.loads(
        Path("configs/engine-qualification/sts2-v0.111.0-macos-arm64-v1.json").read_text()
    )
    config_document["target"].update(
        {
            "assembly_sha256": hashlib.sha256(dll.read_bytes()).hexdigest(),
            "executable_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
            "godotsharp_sha256": hashlib.sha256(godot.read_bytes()).hexdigest(),
            "runtime_main_assembly_hash": struct.unpack(
                "<i", hashlib.sha1(dll.read_bytes()).digest()[:4]
            )[0],
        }
    )
    config = tmp_path / "configs/engine-qualification/fixture.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps(config_document))
    candidate = GameCandidate(game, "test", None)
    monkeypatch.setattr(engine, "discover_game_candidates", lambda **_: [candidate])
    monkeypatch.setattr(
        engine,
        "_git",
        lambda root, *args: (
            config_document["sources"][0 if "headless" in root.name else 1]["commit"]
            if args == ("rev-parse", "HEAD")
            else ""
        ),
    )
    return config, game


def test_exact_identity_is_not_gameplay_or_training_admission(build: tuple[Path, Path]) -> None:
    config, game = build
    result = engine.engine_preflight(engine.load_engine_qualification_config(config), game_dir=game)
    assert result["status"] == "identity_ready"
    assert result["matching_game_paths"] == [str(game)]
    assert not any(result["decision"].values())
    assert result["games_launched"] == result["downloads_started"] == 0
    assert result["qualification_required"]
    # The game's declared cross-architecture hash is not the selected arm64 assembly identity.
    assert (
        result["games"][0]["installation"]["assembly"]["release_declared_main_assembly_hash"]
        == 1172974615
    )


@pytest.mark.parametrize(
    "file",
    [
        "MacOS/Slay the Spire 2",
        "Resources/data_sts2_macos_arm64/sts2.dll",
        "Resources/data_sts2_macos_arm64/GodotSharp.dll",
    ],
)
def test_version_label_cannot_hide_wrong_binary(
    build: tuple[Path, Path],
    tmp_path: Path,
    file: str,
) -> None:
    config_path, game = build
    (game / "SlayTheSpire2.app/Contents" / file).write_bytes(b"different build or patch")
    config = engine.load_engine_qualification_config(config_path)
    result = engine.engine_preflight(config, game_dir=game)
    assert result["status"] == "needs_inputs"
    assert not result["matching_game_paths"]
    destination = tmp_path / "archive"
    with pytest.raises(ValueError, match="Exact game identity required"):
        engine.freeze_game_archive(config, game, destination)
    assert not destination.exists()


def test_v107_is_reported_and_preserved_not_silently_selected(
    build: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    config_path, game = build
    release = game / "SlayTheSpire2.app/Contents/Resources/release_info.json"
    release.write_text(json.dumps({"version": "v0.107.1", "commit": "59260271"}))
    original = release.read_bytes()
    report = engine.engine_preflight(
        engine.load_engine_qualification_config(config_path), game_dir=game
    )
    assert report["next_step"] == "owner_download_exact_game"
    assert report["games"][0]["identity"]["version"] == "v0.107.1"
    assert release.read_bytes() == original
    assert (
        main(
            [
                "engine",
                "freeze",
                str(config_path),
                "--game-dir",
                str(game),
                "--destination",
                str(tmp_path / "archive"),
            ]
        )
        == 1
    )
    assert not (tmp_path / "archive").exists()


def test_missing_assets_do_not_qualify_as_a_complete_game(build: tuple[Path, Path]) -> None:
    config, game = build
    (game / "SlayTheSpire2.app/Contents/Resources/Slay the Spire 2.pck").unlink()
    result = engine.engine_preflight(engine.load_engine_qualification_config(config), game_dir=game)
    assert not result["matching_game_paths"]
    assert "Required base-game file missing" in result["games"][0]["errors"][0]


@pytest.mark.parametrize("change", ["source_commit", "untracked_patch"])
def test_source_drift_blocks_preflight(
    build: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    path, game = build
    original = engine._git
    monkeypatch.setattr(
        engine,
        "_git",
        lambda root, *args: (
            "0" * 40
            if change == "source_commit" and args == ("rev-parse", "HEAD")
            else "?? injected-host.cs"
            if change == "untracked_patch" and args[0] == "status"
            else original(root, *args)
        ),
    )
    result = engine.engine_preflight(engine.load_engine_qualification_config(path), game_dir=game)
    assert result["matching_game_paths"]
    assert result["status"] == "needs_inputs"
    assert result["next_step"] == "prepare_pinned_sources"
    assert not result["decision"]["training_allowed"]


def test_archive_round_trip_detects_asset_and_permission_drift(
    build: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    path, game = build
    config = engine.load_engine_qualification_config(path)
    archive = tmp_path / "frozen-copy"
    record = engine.freeze_game_archive(config, game, archive)
    assert record["files"] == 8
    assert not record["launch_verified"] and not record["training_allowed"]
    assert not (archive / "freeze-in-progress.json").exists()
    assert engine.verify_game_archive(config, archive)["valid"]
    exe = archive / engine.GAME_RELATIVE / "SlayTheSpire2.app/Contents/MacOS/Slay the Spire 2"
    exe.chmod(0o644)
    assert not engine.verify_game_archive(config, archive)["valid"]
    exe.chmod(0o755)
    assets = (
        archive / engine.GAME_RELATIVE / "SlayTheSpire2.app/Contents/Resources/Slay the Spire 2.pck"
    )
    assets.write_bytes(b"different game assets")
    assert not engine.verify_game_archive(config, archive)["valid"]
    assert (
        game / "SlayTheSpire2.app/Contents/Resources/Slay the Spire 2.pck"
    ).read_bytes() == b"fixture assets"


def test_existing_archive_is_verified_never_overwritten(
    build: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    config_path, game = build
    config = engine.load_engine_qualification_config(config_path)
    archive = tmp_path / "archive"
    engine.freeze_game_archive(config, game, archive)
    saved = (archive / engine.ARCHIVE_RECORD).read_bytes()
    with pytest.raises(FileExistsError, match="use verify-archive"):
        engine.freeze_game_archive(config, game, archive)
    assert main(["engine", "freeze", str(config_path), "--destination", str(archive)]) == 0
    assert (archive / engine.ARCHIVE_RECORD).read_bytes() == saved
    (archive / engine.GAME_RELATIVE / "new-file").write_text("changed")
    assert main(["engine", "freeze", str(config_path), "--destination", str(archive)]) == 1
    assert (archive / engine.ARCHIVE_RECORD).read_bytes() == saved


@pytest.mark.parametrize("kind", ["nested_source", "steam_managed", "symlink", "modded"])
def test_unsafe_or_unqualified_archive_is_rejected_before_copy(
    build: tuple[Path, Path],
    tmp_path: Path,
    kind: str,
) -> None:
    path, game = build
    archive = tmp_path / "archive"
    if kind == "nested_source":
        archive = game / "archive"
    elif kind == "steam_managed":
        archive = game.parent.parent / "archives/new"
    elif kind == "symlink":
        (game / "external-assets").symlink_to(tmp_path, target_is_directory=True)
    else:
        mods = game / "SlayTheSpire2.app/Contents/MacOS/mods"
        mods.mkdir()
        (mods / "unqualified.dll").write_bytes(b"mod")
    with pytest.raises(ValueError):
        engine.freeze_game_archive(engine.load_engine_qualification_config(path), game, archive)
    assert not archive.exists()


def test_source_changes_during_copy_leave_failed_partial_evidence(
    build: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, game = build
    original_copy = shutil.copytree

    def changed_copy(source: Any, destination: Any, *args: Any, **kwargs: Any) -> Path:
        result = original_copy(source, destination, *args, **kwargs)
        if Path(source) == game:
            (game / "SlayTheSpire2.app/Contents/Info.plist").write_text("Steam changed the game")
        return Path(result)

    monkeypatch.setattr(shutil, "copytree", changed_copy)
    archive = tmp_path / "failed-archive"
    config = engine.load_engine_qualification_config(path)
    with pytest.raises(ValueError, match="Source game changed"):
        engine.freeze_game_archive(config, game, archive)
    assert (archive / "freeze-failure.json").is_file()
    assert not (archive / engine.ARCHIVE_RECORD).exists()
    assert not engine.verify_game_archive(config, archive)["valid"]


def test_cross_configuration_archive_and_record_tampering_are_rejected(
    build: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    path, game = build
    config = engine.load_engine_qualification_config(path)
    archive = tmp_path / "archive"
    engine.freeze_game_archive(config, game, archive)
    changed = engine.EngineQualificationConfig(
        {**config.document, "archive_name": "different"}, config.root
    )
    assert not engine.verify_game_archive(changed, archive)["valid"]
    record_path = archive / engine.ARCHIVE_RECORD
    record = json.loads(record_path.read_text())
    record["training_allowed"] = True
    record_path.write_text(json.dumps(record))
    assert not engine.verify_game_archive(config, archive)["valid"]


def test_steam_depot_candidates_do_not_borrow_old_installation_manifest(
    build: tuple[Path, Path],
) -> None:
    path, game = build
    candidates = engine.downloaded_game_candidates(engine.load_engine_qualification_config(path))
    assert game.parents[2] / "steamapps/content/app_2868840/depot_2868842" in [
        item.path for item in candidates
    ]
    assert all(item.app_manifest_path is None for item in candidates)


def test_preflight_report_and_console_request_have_no_automatic_side_effects(
    build: tuple[Path, Path],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path, game = build
    assert main(["engine", "download-command", str(path)]) == 0
    assert capsys.readouterr().out.strip() == "download_depot 2868840 2868842 5045320271505434676"
    output = tmp_path / "preflight.json"
    assert (
        main(["engine", "preflight", str(path), "--game-dir", str(game), "--output", str(output)])
        == 0
    )
    saved = output.read_bytes()
    assert json.loads(saved)["games_launched"] == 0
    assert (
        main(["engine", "preflight", str(path), "--game-dir", str(game), "--output", str(output)])
        == 1
    )
    assert output.read_bytes() == saved


def test_checked_in_target_configuration_is_valid_and_pinned() -> None:
    config = engine.load_engine_qualification_config(
        Path("configs/engine-qualification/sts2-v0.111.0-macos-arm64-v1.json")
    )
    assert config.target["version"] == "v0.111.0"
    assert config.target["commit"] == "41cef1ea"
    assert config.target["platform"] == "macos"
    assert config.document["acquisition"]["availability"] == "not_yet_verified_with_Steam_servers"


def _download_fixture(path: Path) -> download.EngineDownloadConfig:
    config = engine.load_engine_qualification_config(path)
    document = json.loads(
        Path("configs/engine-qualification/sts2-v0.111.0-depotdownloader-v1.json").read_text()
    )
    document["qualification_config_id"] = config.config_id
    download_path = path.with_name("download.json")
    download_path.write_text(json.dumps(document))
    return download.load_engine_download_config(download_path, config)


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("branch", "public", "public-beta"),
        ("qualification_config_id", "sha256:" + "0" * 64, "exact qualification"),
        ("max_wall_seconds", 0, "max_wall_seconds"),
    ],
)
def test_download_cannot_change_patch_branch_or_remove_cap(
    build: tuple[Path, Path], key: str, value: Any, message: str
) -> None:
    path, _ = build
    config = _download_fixture(path)
    config.document[key] = value
    download_path = path.with_name("download.json")
    download_path.write_text(json.dumps(config.document))
    with pytest.raises(ValueError, match=message):
        download.load_engine_download_config(download_path, config.qualification)


def test_download_plan_has_no_side_effects_or_credentials(
    build: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path, _ = build
    config = _download_fixture(path)
    monkeypatch.setattr(download, "prepare_downloader", lambda _: pytest.fail("Unexpected setup"))
    assert main(["engine", "download-plan", str(path), str(path.with_name("download.json"))]) == 0
    plan = json.loads(capsys.readouterr().out)
    arguments = plan["arguments_without_account_credentials"]
    assert arguments[arguments.index("-manifest") + 1] == "5045320271505434676"
    assert arguments[arguments.index("-branch") + 1] == "public-beta"
    assert "-password" not in arguments and "-remember-password" not in arguments
    assert not config.work_directory.exists() and not config.tool_directory.exists()
    assert plan["downloads_started"] == 0 and not plan["training_allowed"]


def test_noninteractive_download_cannot_start_or_prepare_tools(
    build: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _download_fixture(build[0])
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(isatty=lambda: False))
    monkeypatch.setattr(download, "prepare_downloader", lambda _: pytest.fail("Unexpected setup"))
    with pytest.raises(ValueError, match="Start the download yourself"):
        download.download_exact_game(config)
    assert not config.work_directory.exists()


def test_download_directory_symlink_cannot_modify_installed_game(
    build: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    path, game = build
    config = _download_fixture(path)
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(isatty=lambda: True))
    config.work_directory.parent.mkdir(parents=True)
    config.work_directory.symlink_to(game, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        download.download_exact_game(config)
    assert not (game / "game").exists()


def test_wrong_downloader_fingerprint_is_preserved_and_never_executed(
    build: tuple[Path, Path],
) -> None:
    config = _download_fixture(build[0])
    config.tool_directory.mkdir(parents=True)
    binary = config.tool_directory / "DepotDownloader"
    binary.write_bytes(b"unexpected executable")
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        download.prepare_downloader(config)
    assert binary.read_bytes() == b"unexpected executable"


@pytest.mark.parametrize("valid", [True, False])
def test_short_tool_preparation_checks_downloaded_bytes_and_extracts_only_named_members(
    build: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, valid: bool
) -> None:
    config = _download_fixture(build[0])
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("DepotDownloader", b"fixture tool")
        package.writestr("LICENSE", b"fixture license")
        package.writestr("../outside-tool-directory", b"never extract")
    data = archive.getvalue()
    config.document["downloader"].update(
        archive_bytes=len(data),
        archive_sha256=hashlib.sha256(data).hexdigest() if valid else "0" * 64,
        executable_sha256=hashlib.sha256(b"fixture tool").hexdigest(),
    )
    requests: list[str] = []

    def request(url: str, **kwargs: Any) -> io.BytesIO:
        requests.append(url)
        assert kwargs["timeout"] == 20
        return io.BytesIO(data)

    monkeypatch.setattr("spireshift.engine_download.urllib.request.urlopen", request)
    if valid:
        binary = download.prepare_downloader(config)
        assert binary.read_bytes() == b"fixture tool" and binary.stat().st_mode & 0o111
        assert (config.tool_directory / "LICENSE").read_bytes() == b"fixture license"
    else:
        with pytest.raises(ValueError, match="archive fingerprint mismatch"):
            download.prepare_downloader(config)
        assert not (config.tool_directory / "DepotDownloader").exists()
    assert len(requests) == 1
    assert not (config.tool_directory.parent / "outside-tool-directory").exists()
    assert not config.game_directory.exists()


@pytest.mark.parametrize("outcome", ["success", "nonzero", "missing_game", "cap"])
def test_owner_download_checks_identity_and_stops_without_followup(
    build: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    path, game = build
    config = _download_fixture(path)
    config.tool_directory.mkdir(parents=True)
    binary = config.tool_directory / "DepotDownloader"
    binary.write_bytes(b"fixture downloader")
    binary.chmod(0o755)
    config.document["downloader"]["executable_sha256"] = hashlib.sha256(
        binary.read_bytes()
    ).hexdigest()
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr("builtins.input", lambda _: "owner")
    invocations: list[list[str]] = []

    def process(arguments: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        invocations.append(arguments)
        assert kwargs["timeout"] == 3600
        assert kwargs["cwd"] == config.work_directory
        assert arguments[arguments.index("-dir") + 1] == str(config.game_directory)
        assert arguments[arguments.index("-branch") + 1] == "public-beta"
        assert arguments[arguments.index("-manifest") + 1] == "5045320271505434676"
        assert "-password" not in arguments and "-remember-password" not in arguments
        if outcome == "cap":
            raise subprocess.TimeoutExpired(arguments, 3600)
        if outcome == "success":
            shutil.copytree(game, config.game_directory)
        return subprocess.CompletedProcess(arguments, 1 if outcome == "nonzero" else 0)

    monkeypatch.setattr("spireshift.engine_download.subprocess.run", process)
    if outcome == "nonzero":
        with pytest.raises(ValueError, match="exited with code 1"):
            download.download_exact_game(config)
    elif outcome == "cap":
        with pytest.raises(subprocess.TimeoutExpired):
            download.download_exact_game(config)
    else:
        result = download.download_exact_game(config)
        assert result["status"] == (
            "downloaded_identity_matches" if outcome == "success" else "identity_mismatch"
        )
        assert not result["training_allowed"] and not result["archive_created"]
    assert len(invocations) == 1  # No fallback manifests or automatic game/training processes.
    assert game.is_dir()


def test_acquired_game_is_a_candidate_without_false_installed_manifest(
    build: tuple[Path, Path],
) -> None:
    config = _download_fixture(build[0])
    candidates = engine.downloaded_game_candidates(config.qualification)
    candidate = next(item for item in candidates if item.path == config.game_directory)
    assert candidate.source == "licensed_depotdownloader" and candidate.app_manifest_path is None
