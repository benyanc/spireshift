from __future__ import annotations

import hashlib
import io
import json
import secrets
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
import spireshift.engine_native as native
import spireshift.engine_qualification as engine
from spireshift.cli import main
from spireshift.core.manifest import manifest_identifier
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


def _native_fixture(
    build: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> native.NativeQualificationConfig:
    config_path, game = build
    qualification = engine.load_engine_qualification_config(config_path)
    user_root = tmp_path / "user"
    user_root.mkdir()
    monkeypatch.setattr(Path, "home", lambda: user_root)
    archive = engine.default_archive_path(qualification)
    (game / native.EXE_RELATIVE).chmod(0o644)  # Steam's depot download drops the launch permission.
    engine.freeze_game_archive(qualification, game, archive)
    document = json.loads(
        Path("configs/engine-qualification/sts2-v0.111.0-native-bootstrap-v1.json").read_text()
    )
    document["qualification_config_id"] = qualification.config_id
    for item in document["decompiler"]["files"]:
        target = qualification.root / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"fixture tool")
        item["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    path = config_path.with_name("native.json")
    path.write_text(json.dumps(document))
    monkeypatch.setattr(native, "_require_native_launch_support", lambda: None)
    monkeypatch.setattr(native, "_running_games", lambda: [])
    return native.load_native_qualification_config(path, qualification)


def _fake_native_boot(command: list[str], cwd: Path, attempt: Path, cap: int) -> dict[str, Any]:
    assert cap <= 60
    assert "--headless" in command and "--force-steam=off" in command
    assert "--quit-after" in command
    override = (cwd / "override.cfg").read_text()
    name = json.loads(override.split("config/custom_user_dir_name=", 1)[1].splitlines()[0])
    profile = Path.home() / "Library/Application Support" / name
    settings = profile / "default/1/settings.save"
    settings.parent.mkdir(parents=True)
    settings.write_text('{"schema_version":8}')
    (attempt / "stdout.log").write_text(
        f"Steam initialization skipped\nUser Data Directory: {profile}\n"
    )
    (attempt / "stderr.log").write_text("ERROR: fixture renderer diagnostic\n")
    return {"returncode": 0, "timed_out": False, "wall_seconds": 0.1}


def test_native_profile_bootstrap_preserves_archive_and_never_admits_gameplay(
    build: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _native_fixture(build, tmp_path, monkeypatch)
    monkeypatch.setattr(native, "_run_boot", _fake_native_boot)
    result = native.bootstrap_native_profile(config)
    assert result["verdict"]["status"] == "native_profile_bootstrap_pass"
    assert all(result["checks"].values())
    assert result["working_copy_changes"]["executable_mode_before"] == 0o644
    assert result["working_copy_changes"]["executable_mode_after"] == 0o755
    assert result["working_copy_changes"]["rules_or_asset_patches"] == 0
    assert result["diagnostics"]["error_lines"] == 1  # A boot pass is not a clean runtime claim.
    assert result["games_launched"] == 1 and result["full_run_attempts"] == 0
    assert result["optimizer_steps"] == 0
    assert not result["training_allowed"] and not result["mechanics_qualified"]
    archive_exe = (
        engine.default_archive_path(config.qualification)
        / engine.GAME_RELATIVE
        / native.EXE_RELATIVE
    )
    assert archive_exe.stat().st_mode & 0o777 == 0o644
    second = native.bootstrap_native_profile(config)
    assert second["profile"] != result["profile"]  # Always a fresh process and native profile.


@pytest.mark.parametrize(
    "gap", ["wrong_path", "wrong_schema", "shared_changed", "game_changed", "capped"]
)
def test_native_boot_refuses_missing_isolation_or_integrity_evidence(
    build: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, gap: str
) -> None:
    config = _native_fixture(build, tmp_path, monkeypatch)

    def boot(command: list[str], cwd: Path, attempt: Path, cap: int) -> dict[str, Any]:
        result = _fake_native_boot(command, cwd, attempt, cap)
        if gap == "wrong_path":
            (attempt / "stdout.log").write_text(
                "Steam initialization skipped\nUser Data Directory: unrelated\n"
            )
        elif gap == "wrong_schema":
            for settings in (
                Path.home() / "Library/Application Support/SpireShift/engine-profiles"
            ).rglob("settings.save"):
                settings.write_text('{"schema_version":9}')
        elif gap == "shared_changed":
            shared = Path.home() / "Library/Application Support/SlayTheSpire2"
            shared.mkdir(parents=True)
            (shared / "unexpected.save").write_text("changed")
        elif gap == "game_changed":
            (cwd / "unexpected-mod.dll").write_bytes(b"changed")
        else:
            result["timed_out"] = True
        return result

    monkeypatch.setattr(native, "_run_boot", boot)
    result = native.bootstrap_native_profile(config)
    assert result["verdict"]["status"] == "native_profile_bootstrap_incomplete"
    assert result["verdict"]["errors"]
    assert not result["training_allowed"]
    assert Path(result["report_path"]).is_file()


def test_native_short_cap_terminates_child_without_changing_parent_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SteamAppId", "must-not-propagate")
    monkeypatch.setenv("SteamGameId", "must-not-propagate")
    import os

    parent_directory = os.environ.get("HOME")
    result = native._run_boot(
        [
            sys.executable,
            "-c",
            "import os,time;"
            "print(os.environ.get('HOME'),os.environ.get('SteamAppId'),flush=True);"
            "time.sleep(10)",
        ],
        tmp_path,
        tmp_path,
        1,
    )
    assert result["timed_out"] and result["returncode"] != 0
    assert result["wall_seconds"] < 4
    assert (tmp_path / "stdout.log").read_text().strip() == f"{parent_directory} None"
    assert os.environ.get("HOME") == parent_directory
    assert os.environ["SteamAppId"] == "must-not-propagate"  # noqa: SIM112 (Steam's native name)


def test_native_check_rejects_archive_drift_and_active_game_before_launch(
    build: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _native_fixture(build, tmp_path, monkeypatch)
    monkeypatch.setattr(native, "_running_games", lambda: [123])
    with pytest.raises(ValueError, match="Close the existing"):
        native.bootstrap_native_profile(config)
    assert not config.workspace.exists()
    monkeypatch.setattr(native, "_running_games", lambda: [])
    dll = (
        engine.default_archive_path(config.qualification)
        / engine.GAME_RELATIVE
        / native.DATA_RELATIVE
        / "sts2.dll"
    )
    dll.write_bytes(b"changed")
    with pytest.raises(ValueError, match="archive verification failed"):
        native.bootstrap_native_profile(config)
    assert not config.workspace.exists()


REGISTRY_FIXTURE = """using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Relics;
public static class AbstractModelSubtypes {
private static readonly Type _t0 = typeof(Strike);
private static readonly Type _t1 = typeof(DeprecatedRelic);
private static readonly Type[] _subtypes = new Type[2] { _t0, _t1 };
public static int Count => 2;
public static IReadOnlyList<Type> All => _subtypes;
}
"""
CLASSES_FIXTURE = """Class MegaCrit.Sts2.Core.Models.Cards.Strike
Class MegaCrit.Sts2.Core.Models.Relics.DeprecatedRelic
"""


def test_registry_inspection_distinguishes_type_coverage_from_offered_content() -> None:
    rows = native.parse_model_registry(REGISTRY_FIXTURE, CLASSES_FIXTURE)
    assert [row["family"] for row in rows] == ["Cards", "Relics"]
    assert [row["nonplayable_name_hint"] for row in rows] == [False, True]
    assert all(row["offered_in_normal_play"] is None for row in rows)


@pytest.mark.parametrize(
    "gap", ["missing_member", "duplicate", "unknown", "ambiguous", "missing_all"]
)
def test_registry_cannot_silently_skip_unknown_or_ambiguous_types(gap: str) -> None:
    source, classes = REGISTRY_FIXTURE, CLASSES_FIXTURE
    if gap == "missing_member":
        source = source.replace("Count => 2", "Count => 3")
    elif gap == "duplicate":
        source = source.replace("{ _t0, _t1 }", "{ _t0, _t0 }")
    elif gap == "unknown":
        classes = classes.replace(".Cards.Strike", ".Cards.Another")
    elif gap == "ambiguous":
        classes += "Class MegaCrit.Sts2.Core.Models.Relics.Strike\n"
    else:
        source = source.replace("All => _subtypes;", "All => other;")
    with pytest.raises(ValueError):
        native.parse_model_registry(source, classes)


def test_registry_command_pins_tool_and_keeps_source_private_without_running_game(
    build: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _native_fixture(build, tmp_path, monkeypatch)
    arguments_seen: list[list[str]] = []

    def tool(arguments: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        arguments_seen.append(arguments)
        assert kwargs["timeout"] == 45 and "--disable-updatecheck" in arguments
        result = "ilspycmd: 9.1.0.7988\nICSharpCode.Decompiler: 9.1.0.7988"
        if "-l" in arguments:
            result = CLASSES_FIXTURE
        elif "-t" in arguments:
            result = (
                REGISTRY_FIXTURE
                if "AbstractModelSubtypes" in arguments[-2]
                else "fixture ModelDb source"
            )
        return subprocess.CompletedProcess(arguments, 0, result, "")

    monkeypatch.setattr("spireshift.engine_native.subprocess.run", tool)
    result = native.inspect_model_registry(config)
    assert result["models"] == 2
    assert result["unresolved_bindings"] == 0
    assert result["offered_in_normal_play"] == "unverified"
    assert result["games_launched"] == 0 and not result["training_allowed"]
    assert len(arguments_seen) == 4
    assert Path(result["raw_inventory_path"]).is_relative_to(
        config.qualification.root / "artifacts"
    )
    raw = json.loads(Path(result["raw_inventory_path"]).read_text())
    assert not raw["runtime_instantiation_verified"] and not raw["training_input"]
    binary = config.qualification.root / config.document["decompiler"]["files"][0]["path"]
    binary.write_bytes(b"changed tool")
    with pytest.raises(ValueError, match="decompiler changed"):
        native.inspect_model_registry(config)
    assert len(arguments_seen) == 4


def test_native_config_and_output_paths_do_not_escape_private_workspaces(
    build: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _native_fixture(build, tmp_path, monkeypatch)
    document = dict(config.document)
    path = tmp_path / "native-invalid.json"
    for changes in (
        {"qualification_config_id": "sha256:" + "0" * 64},
        {"workspace": "artifacts/../sources/not-private"},
        {"max_wall_seconds": 300},
        {"settings_schema": True},
    ):
        path.write_text(json.dumps({**document, **changes}))
        with pytest.raises(ValueError):
            native.load_native_qualification_config(path, config.qualification)
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (config.qualification.root / "artifacts/link").symlink_to(outside, target_is_directory=True)
    path.write_text(json.dumps({**document, "workspace": "artifacts/link/native"}))
    with pytest.raises(ValueError, match="symlinks"):
        native.load_native_qualification_config(path, config.qualification)


# Connector transport/control qualification. The following fixtures never play games.
def _connector_fixture(
    build: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Any:
    from spireshift import engine_connector as connector

    native_config = _native_fixture(build, tmp_path, monkeypatch)
    monkeypatch.setattr(connector, "_require_native_launch_support", lambda: None)
    monkeypatch.setattr(connector, "_running_games", lambda: [])
    # These tiny fixtures test control/provenance, independently of host disk space.
    from types import SimpleNamespace

    monkeypatch.setattr(
        "spireshift.engine_connector.shutil.disk_usage",
        lambda _: SimpleNamespace(free=10_000_000_000),
    )
    monkeypatch.setattr(native, "_run_boot", _fake_native_boot)
    report = native.bootstrap_native_profile(native_config)
    report_path = native_config.qualification.root / "artifacts/fixture-bootstrap.json"
    report_path.write_text(json.dumps(report))
    document = json.loads(
        Path("configs/engine-qualification/sts2-v0.111.0-connector-menu-v1.json").read_text()
    )
    document["qualification_config_id"] = native_config.qualification.config_id
    document["native_config"] = "configs/engine-qualification/native.json"
    document["bootstrap_report"] = str(report_path.relative_to(native_config.qualification.root))
    document["bootstrap_report_id"] = report["report_id"]
    template = Path(report["profile"]) / "default/1/settings.save"
    document["bootstrap_settings_sha256"] = engine._sha_file(template)
    config_path = build[0].with_name("connector.json")
    config_path.write_text(json.dumps(document))
    config = connector.load_connector_qualification_config(config_path, native_config.qualification)
    tools = config.private("toolchain")
    tools.mkdir(parents=True)
    (tools / "fixture-tool").write_text("verified tool")
    body = {"config_id": config.config_id, "inventory": engine._inventory(tools)}
    (tools / "toolchain.json").write_text(
        json.dumps({**body, "report_id": manifest_identifier(body)})
    )
    return config


def test_connector_tools_and_template_drift_stop_before_game_launch(
    build: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from spireshift import engine_connector as connector

    config = _connector_fixture(build, tmp_path, monkeypatch)
    assert connector._verify_toolchain(config)["config_id"] == config.config_id
    settings, _ = connector._settings_template(config)
    original = settings.read_bytes()
    settings.write_text('{"schema_version":9}')
    with pytest.raises(ValueError, match="template changed"):
        connector._settings_template(config)
    settings.write_bytes(original)
    (config.private("toolchain") / "fixture-tool").write_text("modified")
    with pytest.raises(ValueError, match="tools changed"):
        connector.probe_connector_menu(config, node=Path(sys.executable))
    assert not config.private("workspace").exists()


@pytest.mark.parametrize("entry", ["../escape", "/absolute", "package/../escape", "link"])
def test_connector_extraction_blocks_traversal_and_links(tmp_path: Path, entry: str) -> None:
    import tarfile

    from spireshift import engine_connector as connector

    archive = tmp_path / "tools.tgz"
    with tarfile.open(archive, "w:gz") as tar:
        member = tarfile.TarInfo(entry)
        if entry == "link":
            member.type = tarfile.SYMTYPE
            member.linkname = "../escape"
            tar.addfile(member)
        else:
            member.size = 4
            tar.addfile(member, io.BytesIO(b"test"))
    destination = tmp_path / "extracted"
    with pytest.raises(ValueError, match="Unsafe"):
        connector._extract(archive, destination)
    assert not destination.exists() and not (tmp_path / "escape").exists()


def test_connector_mod_consent_only_changes_two_settings_and_keeps_backup(tmp_path: Path) -> None:
    from spireshift import engine_connector as connector

    settings = tmp_path / "settings.save"
    original = {
        "schema_version": 8,
        "mod_settings": None,
        "seen_ea_disclaimer": False,
        "native_setting": {"keep": 42},
    }
    settings.write_text(json.dumps(original))
    connector._enable_mod_settings(settings, 8)
    assert (
        json.loads(settings.with_name("settings.save.before-connector-consent").read_text())
        == original
    )
    updated = json.loads(settings.read_text())
    assert {
        key: value
        for key, value in updated.items()
        if key not in {"mod_settings", "seen_ea_disclaimer"}
    } == {
        key: value
        for key, value in original.items()
        if key not in {"mod_settings", "seen_ea_disclaimer"}
    }
    assert updated["mod_settings"]["mods_enabled"] and updated["seen_ea_disclaimer"]


@pytest.mark.parametrize("gap", [None, "identity", "transition", "timeout", "payload"])
def test_disposable_connector_stage_counts_failed_gates_and_preserves_native_source(
    build: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, gap: str | None
) -> None:
    from spireshift import engine_connector as connector

    config = _connector_fixture(build, tmp_path, monkeypatch)
    monkeypatch.setattr(connector, "_require_native_launch_support", lambda: None)
    monkeypatch.setattr(connector, "_running_games", lambda: [])

    def install(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if args[0][-1] == "/usr/bin/true":
            return subprocess.CompletedProcess(args[0], 0, "", "")
        assert args[0][-1] == "--install"
        spec = json.loads(kwargs["input"])
        mods = Path(spec["game"]) / native.EXE_RELATIVE
        mods = mods.parent / "mods"
        mods.mkdir()
        (mods / "STS2_MCP.dll").write_bytes(b"fixture host")
        return subprocess.CompletedProcess(args[0], 0, "{}", "")

    def probe(
        config: Any, node: Path, attempt: Path, executable: Path, port: int
    ) -> dict[str, Any]:
        override = executable.with_name("override.cfg").read_text()
        profile_name = json.loads(
            override.split("config/custom_user_dir_name=", 1)[1].splitlines()[0]
        )
        profile = Path.home() / "Library/Application Support" / profile_name
        assert sorted(p.name for p in (profile / "default/1").iterdir()) == [
            "settings.save",
            "settings.save.before-connector-consent",
        ]
        (attempt / "stdout.log").write_text(
            f"Steam initialization skipped\nUser Data Directory: {profile}\n"
        )
        (attempt / "stderr.log").write_text("ERROR: preserved native diagnostic\n")
        if gap == "payload":
            (executable.parent / "unexpected.dll").write_text("drift")
        return {
            "returncode": 0,
            "forced_cleanup": False,
            "timed_out": gap == "timeout",
            "wall_seconds": 0.1,
            "probe": {
                "checks": {
                    "loaded_identity": gap != "identity",
                    "endpoint_owned_by_child": True,
                    "complete_public_menu": True,
                    "completed_menu_transition": gap != "transition",
                    "duplicate_idempotent": True,
                    "stale_rejected": True,
                },
                "shutdown_requested": True,
                "menu_actions_requested": 1,
            },
        }

    monkeypatch.setattr(subprocess, "run", install)
    monkeypatch.setattr(connector, "_run_menu_probe", probe)
    result = connector.probe_connector_menu(config, node=Path(sys.executable))
    assert (result["verdict"]["status"] == "shipped_connector_menu_pass") == (gap is None)
    assert result["full_run_attempts"] == 0 and not result["training_allowed"]
    assert result["diagnostics"]["error_lines"] == 1
    assert result["checks"]["template_unchanged"] and result["checks"]["archive_still_valid"]
    assert Path(result["report_path"]).is_file()
    assert not Path(result["report_path"]).with_name("in-progress.json").exists()


def test_connector_short_timeout_cleans_owned_game_and_keeps_secrets_out_of_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    from spireshift import engine_connector as connector

    secret = "a" * 64
    monkeypatch.setattr(secrets, "token_hex", lambda _: secret)
    actual_popen = subprocess.Popen
    parent_home = os.environ.get("HOME")
    child_pid = None

    def launch(*args: Any, **kwargs: Any) -> Any:
        nonlocal child_pid
        assert kwargs["env"]["HOME"] == parent_home
        assert kwargs["env"]["STS2_CONNECTOR_HOST_CONTROL_TOKEN"] == secret
        child = actual_popen([sys.executable, "-c", "import time;time.sleep(20)"], **kwargs)
        child_pid = child.pid
        return child

    def timeout(*args: Any, **kwargs: Any) -> Any:
        assert json.loads(kwargs["input"])["host_control_token"] == secret
        raise subprocess.TimeoutExpired(args[0], 1)

    config: Any = SimpleNamespace(
        document={"connector": {"source_revision": "b" * 40}, "max_wall_seconds": 30},
        qualification=SimpleNamespace(root=tmp_path, target={}),
        private=lambda _: tmp_path,
    )
    monkeypatch.setattr(subprocess, "Popen", launch)
    monkeypatch.setattr(subprocess, "run", timeout)
    result = connector._run_menu_probe(
        config, Path(sys.executable), tmp_path, tmp_path / "game", 12345
    )
    assert result["timed_out"] and result["forced_cleanup"] and result["returncode"] != 0
    assert result["wall_seconds"] < 4 and result["pid"] == child_pid
    assert secret not in json.dumps(result)
    assert all(secret not in item.read_text() for item in tmp_path.iterdir() if item.is_file())


@pytest.mark.parametrize("gap", [None, "empty", "no_project", "tool_failed"])
def test_private_source_extraction_is_separate_from_mechanics_and_training(
    build: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, gap: str | None
) -> None:
    from spireshift import engine_source as source

    native_config = _native_fixture(build, tmp_path, monkeypatch)
    document = json.loads(
        Path("configs/engine-qualification/sts2-v0.111.0-source-inspection-v1.json").read_text()
    )
    document["qualification_config_id"] = native_config.qualification.config_id
    document["native_config"] = "configs/engine-qualification/native.json"
    path = build[0].with_name("source.json")
    path.write_text(json.dumps(document))
    monkeypatch.setattr(source, "_require_native_launch_support", lambda: None)

    def launch(command: list[str], **kwargs: Any) -> Any:
        assert "--project" in command and "--disable-updatecheck" in command
        assert "--headless" not in command
        target = Path(command[command.index("--outputdir") + 1])
        target.mkdir(parents=True)
        if gap != "empty":
            (target / "Fixture.cs").write_text("public class Fixture {}")
        if gap != "no_project":
            (target / "Fixture.csproj").write_text("<Project/>")
        return SimpleNamespace(
            returncode=1 if gap == "tool_failed" else 0, wait=lambda **_: None, poll=lambda: 0
        )

    monkeypatch.setattr(subprocess, "Popen", launch)
    monkeypatch.setattr(source, "_stop_child", lambda _: None)
    result = source.inspect_game_source(native_config.qualification, path)
    assert (result["status"] == "private_source_extraction_complete") == (gap is None)
    assert result["games_launched"] == 0 and result["optimizer_steps"] == 0
    assert not result["training_allowed"] and not result["mechanics_qualified"]
    assert result["checks"]["archive_still_valid"] and result["checks"]["tools_unchanged"]
    assert Path(result["report_path"]).is_file()


def test_source_inspection_refuses_decompiler_drift_before_long_stage(
    build: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from spireshift import engine_source as source

    native_config = _native_fixture(build, tmp_path, monkeypatch)
    document = json.loads(
        Path("configs/engine-qualification/sts2-v0.111.0-source-inspection-v1.json").read_text()
    )
    document["qualification_config_id"] = native_config.qualification.config_id
    document["native_config"] = "configs/engine-qualification/native.json"
    path = build[0].with_name("source.json")
    path.write_text(json.dumps(document))
    monkeypatch.setattr(source, "_require_native_launch_support", lambda: None)
    tool = native_config.qualification.root / native_config.document["decompiler"]["executable"]
    tool.write_text("changed")
    with pytest.raises(ValueError, match="decompiler changed"):
        source.inspect_game_source(native_config.qualification, path)
    assert not (native_config.qualification.root / document["workspace"]).exists()


def test_cli_build_refuses_invalid_menu_evidence_before_cloning_or_compiling(
    build: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from spireshift import engine_candidate as candidate

    config = _connector_fixture(build, tmp_path, monkeypatch)
    qualification = config.qualification
    document = json.loads(
        Path("configs/engine-qualification/sts2-v0.111.0-cli-build-v1.json").read_text()
    )
    document["qualification_config_id"] = qualification.config_id
    document["native_config"] = "configs/engine-qualification/native.json"
    document["menu_report"] = "artifacts/fixture-menu.json"
    (qualification.root / document["menu_report"]).write_text(
        json.dumps({"verdict": {"status": "incomplete"}})
    )
    path = build[0].with_name("candidate.json")
    path.write_text(json.dumps(document))
    monkeypatch.setattr(candidate, "_running_games", lambda: [])
    with pytest.raises(ValueError, match="verified same-game Connector"):
        candidate.build_cli_candidate(qualification, path, Path(sys.executable))
    assert not (qualification.root / document["workspace"]).exists()


@pytest.mark.parametrize("mode", ["success", "failed_identity", "retain_success"])
def test_checkpoint_payload_removal_requires_verified_success_and_preserves_evidence(
    build: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    from spireshift import engine_connector as connector

    config = _connector_fixture(build, tmp_path, monkeypatch)
    save = tmp_path / "synthetic-native.save"
    save.write_text("synthetic native save")
    fixture = {
        "checkpoint_path": str(save),
        "checkpoint_sha256": engine._sha_file(save),
        "workspace": "artifacts/synthetic-checkpoint",
    }
    copies = []

    def install(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if args[0][-1] != "/usr/bin/true":
            spec = json.loads(kwargs["input"])
            mods = Path(spec["game"]) / native.EXE_RELATIVE
            mods = mods.parent / "mods"
            mods.mkdir()
            (mods / "STS2_MCP.dll").write_bytes(b"fixture host")
        return subprocess.CompletedProcess(args[0], 0, "{}", "")

    def probe(
        config: Any, node: Path, attempt: Path, executable: Path, port: int, *, fixture: Any
    ) -> dict[str, Any]:
        copies.append(attempt / "game")
        override = executable.with_name("override.cfg").read_text()
        profile_name = json.loads(
            override.split("config/custom_user_dir_name=", 1)[1].splitlines()[0]
        )
        profile = Path.home() / "Library/Application Support" / profile_name
        assert (
            profile / "default/1/modded/profile1/saves/current_run.save"
        ).read_text() == save.read_text()
        (attempt / "stdout.log").write_text(
            f"Steam initialization skipped\nUser Data Directory: {profile}\n"
        )
        (attempt / "stderr.log").write_text("ERROR: retained diagnostic\n")
        checks = {
            key: True
            for key in (
                "loaded_identity",
                "endpoint_owned_by_child",
                "native_continue_offered",
                "native_checkpoint_loaded",
                "complete_public_starting_event",
                "native_A8_seed_preserved",
                "same_starting_public_option_titles_and_availability",
            )
        }
        checks["loaded_identity"] = mode != "failed_identity"
        return {
            "returncode": 0,
            "forced_cleanup": False,
            "timed_out": False,
            "wall_seconds": 0.1,
            "probe": {"checks": checks, "shutdown_requested": True},
        }

    monkeypatch.setattr(subprocess, "run", install)
    monkeypatch.setattr(connector, "_run_menu_probe", probe)
    result = connector._probe_connector_private(
        config,
        node=Path(sys.executable),
        fixture=fixture,
        retain_working_game=mode == "retain_success",
    )
    removed = mode == "success"
    assert result["disposable_payload_removed_after_verified_success"] is removed
    assert result["working_payload_retained"] is not removed
    assert copies[0].exists() is not removed
    assert Path(result["report_path"]).with_name("stderr.log").is_file()
    assert Path(result["report_path"]).is_file() and save.read_text() == "synthetic native save"
    assert result["checks"]["archive_still_valid"] and result["checks"]["shared_profile_unchanged"]
    assert result["training_allowed"] is False
