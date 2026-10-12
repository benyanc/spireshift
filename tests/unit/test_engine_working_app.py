"""Working-app reuse, clean profiles, storage bounds and interrupted-worker quarantine."""

import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_native import EXE_RELATIVE
from spireshift.engine_qualification import (
    ARCHIVE_RECORD,
    GAME_RELATIVE,
    EngineQualificationConfig,
    _inventory,
)
from spireshift.engine_working_app import (
    WorkingAppPolicy,
    lease_working_app,
    load_working_app_policy,
    preflight_working_app,
    working_app_inventory,
)


def copy_data(source: str | Path, destination: str | Path) -> str:
    return str(shutil.copy2(source, destination))


@pytest.fixture
def inputs(tmp_path: Path) -> tuple[WorkingAppPolicy, Path, Path]:
    qualification = EngineQualificationConfig({"archive_name": "synthetic-game"}, tmp_path)
    config: dict[str, Any] = {
        "schema_version": "engine-working-app-config-v1",
        "qualification_config_id": qualification.config_id,
        "mode": "serial_reuse",
        "workspace": "artifacts/engine-working-apps/synthetic-game/worker-00",
        "max_pool_apps": 2,
        "max_pool_bytes": 5_000_000_000,
        "training_allowed": False,
    }
    recipe = tmp_path / "policy.json"
    recipe.write_text(json.dumps(config))
    policy = load_working_app_policy(recipe, qualification)
    archive = tmp_path / "frozen"
    game = archive / GAME_RELATIVE
    executable = game / EXE_RELATIVE
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"official executable")
    executable.chmod(0o644)
    asset = game / "asset.pck"
    asset.write_bytes(b"official assets")
    inventory = _inventory(game)
    (archive / ARCHIVE_RECORD).write_text(
        json.dumps({"archive_id": manifest_identifier(inventory), "inventory": inventory})
    )
    attempts = tmp_path / "artifacts/runs"
    attempts.mkdir(parents=True)
    return policy, archive, attempts


def prepare(game: Path, profile: str) -> list[dict[str, Any]]:
    executable = game / EXE_RELATIVE
    executable.chmod(0o755)
    (executable.parent / "override.cfg").write_text(profile)
    mods = executable.parent / "mods"
    mods.mkdir()
    (mods / "connector.dll").write_text("pinned host")
    return _inventory(game)


def test_many_attempts_reuse_one_app_and_restore_owned_settings(
    inputs: tuple[WorkingAppPolicy, Path, Path],
) -> None:
    policy, archive, attempts = inputs
    original = _inventory(archive / GAME_RELATIVE)
    copies = []

    def copy_file(source: str | Path, destination: str | Path) -> str:
        copies.append(str(source))
        return str(shutil.copy2(source, destination))

    reports = []
    for number in range(3):
        attempt = attempts / str(number)
        attempt.mkdir()
        (attempt / "save.json").write_text(f"fresh save {number}")
        with lease_working_app(policy, archive, attempt, copy_file=copy_file) as lease:
            assert _inventory(lease.game) == original
            expected = prepare(lease.game, f"fresh profile {number}")
            reports.append(lease.restore(expected))
        assert _inventory(policy.slot / "game") == original
        assert not (policy.slot / "active.json").exists()
        assert (attempt / "save.json").read_text() == f"fresh save {number}"
    assert len(copies) == len(original)
    assert [row["app_copies_created"] for row in reports] == [1, 0, 0]
    assert len({row["app_inode"] for row in reports}) == 1
    assert _inventory(archive / GAME_RELATIVE) == original
    assert working_app_inventory(policy.qualification)["apps"] == 1


def test_same_worker_cannot_be_leased_concurrently(
    inputs: tuple[WorkingAppPolicy, Path, Path],
) -> None:
    policy, archive, attempts = inputs
    first, second = attempts / "first", attempts / "second"
    first.mkdir()
    second.mkdir()
    with lease_working_app(policy, archive, first, copy_file=copy_data) as lease:
        with (
            pytest.raises(ValueError, match="Another run owns"),
            lease_working_app(policy, archive, second, copy_file=copy_data),
        ):
            pytest.fail("Overlapping worker was admitted")
        lease.restore(prepare(lease.game, "first"))
    assert not (second / "working-app-lease.json").exists()


def test_interruption_retains_one_blocked_app_and_no_silent_recopy(
    inputs: tuple[WorkingAppPolicy, Path, Path],
) -> None:
    policy, archive, attempts = inputs
    first, second = attempts / "first", attempts / "second"
    first.mkdir()
    second.mkdir()
    with (
        pytest.raises(RuntimeError, match="interrupted"),
        lease_working_app(policy, archive, first, copy_file=copy_data),
    ):
        raise RuntimeError("interrupted")
    assert (first / "working-app-blocked.json").exists()
    with (
        pytest.raises(ValueError, match="active or interrupted"),
        lease_working_app(policy, archive, second, copy_file=copy_data),
    ):
        pytest.fail("Interrupted worker was resumed")
    assert working_app_inventory(policy.qualification)["apps"] == 1


@pytest.mark.parametrize("drift", ["official", "addition", "symlink"])
def test_unknown_mutations_are_preserved_and_block_reuse(
    inputs: tuple[WorkingAppPolicy, Path, Path], drift: str
) -> None:
    policy, archive, attempts = inputs
    attempt = attempts / drift
    attempt.mkdir()
    original = _inventory(archive / GAME_RELATIVE)
    with (
        pytest.raises(ValueError),
        lease_working_app(policy, archive, attempt, copy_file=copy_data) as lease,
    ):
        expected = prepare(lease.game, "first")
        if drift == "official":
            (lease.game / "asset.pck").write_text("unexpected mutation")
            expected = _inventory(lease.game)
        elif drift == "addition":
            (lease.game / "unexpected").write_text("preserve forensic data")
            expected = _inventory(lease.game)
        else:
            (lease.game / "outside-link").symlink_to(archive / GAME_RELATIVE / "asset.pck")
        lease.restore(expected)
    assert (policy.slot / "active.json").exists()
    assert _inventory(archive / GAME_RELATIVE) == original
    assert (attempt / "working-app-blocked.json").exists()


def test_partial_copy_blocks_worker_without_making_new_app(
    inputs: tuple[WorkingAppPolicy, Path, Path],
) -> None:
    policy, archive, attempts = inputs
    attempt = attempts / "partial"
    attempt.mkdir()

    def fail(source: str | Path, destination: str | Path) -> str:
        shutil.copy2(source, destination)
        raise RuntimeError("copy interrupted")

    with (
        pytest.raises(RuntimeError, match="copy interrupted"),
        lease_working_app(policy, archive, attempt, copy_file=fail),
    ):
        pytest.fail("Partial copy was admitted")
    with pytest.raises(ValueError, match="active or interrupted"):
        preflight_working_app(policy)
    assert working_app_inventory(policy.qualification)["apps"] == 1


@pytest.mark.parametrize("limit", ["count", "bytes"])
def test_global_cap_refuses_extra_apps_without_deleting_older_workers(
    inputs: tuple[WorkingAppPolicy, Path, Path], monkeypatch: pytest.MonkeyPatch, limit: str
) -> None:
    policy, archive, attempts = inputs
    attempt = attempts / limit
    attempt.mkdir()
    if limit == "count":
        for number in range(2):
            game = policy.pool / f"other-{number}/worker-00/game"
            game.mkdir(parents=True)
            (game / "asset").write_text("preserve previous worker")
    else:
        monkeypatch.setattr(
            "spireshift.engine_working_app.working_app_inventory",
            lambda qualification, **kwargs: {"apps": 1, "logical_bytes": 5_000_000_000},
        )
    with (
        pytest.raises(ValueError, match="global two-app/5 GB cap"),
        lease_working_app(policy, archive, attempt, copy_file=copy_data),
    ):
        pytest.fail("Storage cap was ignored")
    assert not (policy.slot / "game").exists()
    assert not (policy.slot / "active.json").exists()
    if limit == "count":
        assert (
            policy.pool / "other-0/worker-00/game/asset"
        ).read_text() == "preserve previous worker"


def test_hard_links_to_master_are_rejected_before_mutating_it(
    inputs: tuple[WorkingAppPolicy, Path, Path],
) -> None:
    policy, archive, attempts = inputs
    attempt = attempts / "hardlink"
    attempt.mkdir()
    original = _inventory(archive / GAME_RELATIVE)

    def link(source: str | Path, destination: str | Path) -> str:
        os.link(source, destination)
        return str(destination)

    with (
        pytest.raises(ValueError, match="cannot hard-link"),
        lease_working_app(policy, archive, attempt, copy_file=link),
    ):
        pytest.fail("Hard-linked master was admitted")
    assert _inventory(archive / GAME_RELATIVE) == original


def test_policy_cannot_redirect_worker_outside_pool(
    inputs: tuple[WorkingAppPolicy, Path, Path],
) -> None:
    policy, _, attempts = inputs
    document = {**policy.document, "workspace": "artifacts/../../frozen"}
    path = attempts / "bad-policy.json"
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="pinned serial worker"):
        load_working_app_policy(path, policy.qualification)


def test_reset_cannot_run_after_worker_lock_is_released(
    inputs: tuple[WorkingAppPolicy, Path, Path],
) -> None:
    policy, archive, attempts = inputs
    attempt = attempts / "late-reset"
    attempt.mkdir()
    with lease_working_app(policy, archive, attempt, copy_file=copy_data) as lease:
        expected = prepare(lease.game, "first")
        lease.restore(expected)
    with pytest.raises(ValueError, match="still-held worker lock"):
        lease.restore(expected)


def test_changed_ownership_is_refused_before_any_reset_deletion(
    inputs: tuple[WorkingAppPolicy, Path, Path],
) -> None:
    policy, archive, attempts = inputs
    attempt = attempts / "ownership"
    attempt.mkdir()
    with (
        pytest.raises(ValueError, match="ownership changed"),
        lease_working_app(policy, archive, attempt, copy_file=copy_data) as lease,
    ):
        expected = prepare(lease.game, "first")
        (policy.slot / "active.json").write_text("{}")
        lease.restore(expected)
    assert (lease.game / Path(EXE_RELATIVE).parent / "mods/connector.dll").exists()
    assert (lease.game / Path(EXE_RELATIVE).parent / "override.cfg").exists()


@pytest.mark.parametrize("field", ["config_id", "attempt", "app_copies_created", "app_inode"])
def test_saved_reset_receipt_tampering_is_refused(
    inputs: tuple[WorkingAppPolicy, Path, Path],
    field: str,
) -> None:
    from spireshift.engine_working_app import verify_working_app_receipt

    policy, archive, attempts = inputs
    attempt = attempts / "receipt"
    attempt.mkdir()
    with lease_working_app(policy, archive, attempt, copy_file=copy_data) as lease:
        result = lease.restore(prepare(lease.game, "first"))
    archive_id = json.loads((archive / ARCHIVE_RECORD).read_text())["archive_id"]
    verify_working_app_receipt(policy, result, attempt=attempt, archive_id=archive_id)
    changed = {**result, field: 0 if field == "app_inode" else "changed"}
    changed["report_id"] = manifest_identifier(
        {key: value for key, value in changed.items() if key != "report_id"}
    )
    (attempt / "working-app-restored.json").write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="ownership or reset receipt"):
        verify_working_app_receipt(policy, changed, attempt=attempt, archive_id=archive_id)


def test_inventory_reports_legacy_payloads_without_deleting_them(
    inputs: tuple[WorkingAppPolicy, Path, Path],
) -> None:
    policy, _, attempts = inputs
    legacy = attempts / "checkpoint-old/game"
    legacy.mkdir(parents=True)
    (legacy / "asset").write_text("preserved old attempt")
    inventory = working_app_inventory(policy.qualification)
    assert inventory["apps"] == 0
    assert inventory["files_deleted"] == 0
    assert inventory["scan_errors"] == []
    assert inventory["other_game_payloads"] == [
        {
            "path": str(legacy),
            "logical_bytes": len("preserved old attempt"),
            "classification": "legacy_or_unclassified_payload",
            "automatically_deletable": False,
        }
    ]
    assert (legacy / "asset").read_text() == "preserved old attempt"
    # Per-run quota checks inspect only the bounded pool; full history scans are on demand.
    assert (
        working_app_inventory(policy.qualification, include_other_payloads=False)[
            "other_game_payloads"
        ]
        == []
    )


def test_bootstrap_records_override_before_reusable_app_reset(
    inputs: tuple[WorkingAppPolicy, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import spireshift.engine_native as native

    policy, archive, attempts = inputs
    native_config = native.NativeQualificationConfig(
        {
            "workspace": "artifacts/native-checks",
            "settings_schema": 8,
            "quit_after_frames": 1200,
            "max_wall_seconds": 60,
        },
        policy.qualification,
    )
    monkeypatch.setattr(native, "_require_native_launch_support", lambda: None)
    monkeypatch.setattr(native, "_running_games", lambda: [])
    monkeypatch.setattr(
        native, "_verified_archive", lambda config: (archive, {"report_id": "synthetic-verified"})
    )
    monkeypatch.setattr(native, "_shared_snapshot", lambda path: {"present": False})
    monkeypatch.setattr(
        native,
        "verify_game_archive",
        lambda *args: {"valid": True, "report_id": "synthetic-verified"},
    )
    fake_home = attempts / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    def boot(command: list[str], cwd: Path, attempt: Path, cap: int) -> dict[str, Any]:
        override = (cwd / "override.cfg").read_text()
        line = next(
            row for row in override.splitlines() if row.startswith("config/custom_user_dir_name=")
        )
        profile = fake_home / "Library/Application Support" / json.loads(line.split("=", 1)[1])
        settings = profile / "default/1/settings.save"
        settings.parent.mkdir(parents=True)
        settings.write_text('{"schema_version":8}')
        (attempt / "stdout.log").write_text(
            f"User Data Directory: {profile}\nSteam initialization skipped\n"
        )
        (attempt / "stderr.log").write_text("")
        return {"returncode": 0, "timed_out": False}

    monkeypatch.setattr(native, "_run_boot", boot)
    result = native.bootstrap_native_profile(native_config, working_app=policy)
    assert result["verdict"]["status"] == "native_profile_bootstrap_pass"
    assert len(result["working_copy_changes"]["override_sha256"]) == 64
    assert result["working_app"]["restored"] is True
    assert not (policy.slot / "game" / Path(EXE_RELATIVE).parent / "override.cfg").exists()
    assert not (policy.slot / "active.json").exists()


@pytest.mark.parametrize("change", ["removed", "modified"])
def test_idle_app_drift_is_refused_before_allocating_new_attempt(
    inputs: tuple[WorkingAppPolicy, Path, Path],
    change: str,
) -> None:
    policy, archive, attempts = inputs
    first = attempts / "first"
    first.mkdir()
    with lease_working_app(policy, archive, first, copy_file=copy_data) as lease:
        lease.restore(prepare(lease.game, "first"))
    if change == "removed":
        shutil.rmtree(policy.slot / "game")
    else:
        (policy.slot / "game/asset.pck").write_text("preserve idle corruption")
    with pytest.raises(ValueError, match="explicit repair"):
        preflight_working_app(policy)
    assert not (policy.slot / "active.json").exists()
    assert (policy.slot / "app.json").exists()
    if change == "removed":
        assert not (policy.slot / "game").exists()
