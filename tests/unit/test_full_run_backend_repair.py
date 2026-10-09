from __future__ import annotations

import difflib
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from spireshift import full_run_backend_repair as repair
from spireshift.core.manifest import load_patch_manifest, manifest_identifier
from spireshift.resource_tracking import EXPERIMENT_METRICS_ENV


def git(path: Path, *arguments: str) -> str:
    return subprocess.check_output(["git", "-C", str(path), *arguments], text=True).strip()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def recipe(tmp_path: Path) -> repair.RepairRecipe:
    root = tmp_path
    base = root / "artifacts/base"
    source = "src/Sts2Emulator/Core/Run/RunEngine.cs"
    tests = "patches/tests.cs"
    patch = "patches/repair.patch"
    (base / source).parent.mkdir(parents=True)
    (base / source).write_text("// synthetic old rule\n")
    (base / "src/Sts2Emulator.Tests").mkdir()
    (base / "src/Sts2Emulator.Tests/.keep").touch()
    (base / ".gitignore").write_text("out/\nbin/\nobj/\n")
    git(base, "init")
    git(base, "add", ".")
    git(
        base,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@localhost",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-m",
        "synthetic base",
    )
    revision = git(base, "rev-parse", "HEAD")
    (root / "patches").mkdir()
    (root / tests).write_text("// synthetic regression source\n")
    new_source = "// synthetic repaired rule\n"
    (root / patch).write_text(
        "".join(
            difflib.unified_diff(
                (base / source).read_text().splitlines(keepends=True),
                new_source.splitlines(keepends=True),
                fromfile=f"a/{source}",
                tofile=f"b/{source}",
            )
        )
    )
    base_manifest = load_patch_manifest(
        Path("manifests/patches/sts2-v0.107.1-evangambit-37e4264-macos-arm64-admitted.json")
    )
    manifest = base_manifest.body_dict()
    engine = base_manifest.engine.as_dict()
    engine.update(revision=revision, digest={"algorithm": "git-commit-sha1", "value": revision})
    manifest["engine"] = engine
    manifest["manifest_id"] = manifest_identifier(manifest)
    (root / "manifest.json").write_text(json.dumps(manifest))
    document: dict[str, Any] = {
        "schema_version": "full-run-backend-repair-config-v1",
        "base_upstream": "artifacts/base",
        "base_revision": revision,
        "base_manifest": "manifest.json",
        "base_manifest_id": manifest["manifest_id"],
        "patch": {"path": patch, "sha256": digest(root / patch)},
        "regression_tests": {"path": tests, "sha256": digest(root / tests)},
        "engine_source": {
            "path": source,
            "base_sha256": digest(base / source),
            "repaired_sha256": hashlib.sha256(new_source.encode()).hexdigest(),
        },
        "candidate_upstream": "artifacts/candidate",
        "output_dir": "artifacts/repair",
        "runtime": "osx-arm64",
        "minimum_regression_tests": 9,
        "resource_limits": {
            "wall_seconds": 1800,
            "cpu_seconds": 7200,
            "memory_bytes": 12000000000,
            "storage_bytes": 4000000000,
        },
        "automatic_admission": False,
        "automatic_training": False,
    }
    document["config_id"] = manifest_identifier(document)
    (root / "config.json").write_text(json.dumps(document))
    return repair.load_repair_recipe(root / "config.json", root=root)


def write_trx(path: Path, *, passed: bool = True, correct_class: bool = True) -> None:
    class_name = repair.TEST_CLASS if correct_class else "UnrelatedTests"
    path.write_text(
        '<TestRun xmlns="http://microsoft.com/schemas/VisualStudio/TeamTest/2010">'
        '<ResultSummary><Counters total="9" executed="9" '
        f'passed="{9 if passed else 8}" failed="{0 if passed else 1}" /></ResultSummary>'
        "<Results>"
        + "".join(
            f'<UnitTestResult testName="{class_name}.Case{i}" outcome="Passed" />' for i in range(9)
        )
        + "</Results></TestRun>"
    )


def test_preparation_is_isolated_and_repeated_preparation_reuses_exact_tree(
    recipe: repair.RepairRecipe,
) -> None:
    before = git(recipe.path(recipe.document["base_upstream"]), "rev-parse", "HEAD")
    result = repair.prepare_backend_repair(recipe)
    assert result["candidate_revision"] != before
    assert git(recipe.candidate, "rev-parse", "HEAD^") == before
    assert git(recipe.path(recipe.document["base_upstream"]), "rev-parse", "HEAD") == before
    assert (
        digest(
            recipe.path(recipe.document["base_upstream"]) / recipe.document["engine_source"]["path"]
        )
        == recipe.document["engine_source"]["base_sha256"]
    )
    assert result["training_allowed"] is False
    assert result["native_build_started"] is False
    assert repair.prepare_backend_repair(recipe) == result


def test_dirty_original_or_candidate_is_refused_without_overwriting(
    recipe: repair.RepairRecipe,
) -> None:
    base_source = (
        recipe.path(recipe.document["base_upstream"]) / recipe.document["engine_source"]["path"]
    )
    old = base_source.read_text()
    base_source.write_text(old + "unexpected\n")
    with pytest.raises(ValueError, match="original checkout changed"):
        repair.prepare_backend_repair(recipe)
    assert not recipe.candidate.exists()
    base_source.write_text(old)
    repair.prepare_backend_repair(recipe)
    extra = recipe.candidate / "unrelated.txt"
    extra.write_text("preserve this\n")
    with pytest.raises(ValueError, match="unrelated modifications"):
        repair.prepare_backend_repair(recipe)
    assert extra.read_text() == "preserve this\n"


def test_patch_drift_and_nested_output_cannot_change_a_prepared_protocol(
    recipe: repair.RepairRecipe,
) -> None:
    p = recipe.path(recipe.document["patch"]["path"])
    p.write_text(p.read_text() + "unexpected\n")
    with pytest.raises(ValueError, match="patch identity"):
        repair.load_repair_recipe(recipe.root / "config.json", root=recipe.root)
    d = recipe.document.copy()
    d["output_dir"] = d["base_upstream"] + "/result"
    d["config_id"] = manifest_identifier({k: v for k, v in d.items() if k != "config_id"})
    (recipe.root / "config.json").write_text(json.dumps(d))
    with pytest.raises(ValueError, match="cannot contain"):
        repair.load_repair_recipe(recipe.root / "config.json", root=recipe.root)


def test_unwrapped_native_build_is_refused_before_preparation(
    recipe: repair.RepairRecipe, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(EXPERIMENT_METRICS_ENV, raising=False)
    with pytest.raises(ValueError, match="owner-run repair script"):
        repair.build_backend_repair(recipe)
    assert not recipe.candidate.exists()


@pytest.mark.parametrize(("passed", "correct_class"), [(False, True), (True, False)])
def test_regressions_require_success_of_the_right_test_class(
    tmp_path: Path, passed: bool, correct_class: bool
) -> None:
    path = tmp_path / "completion.trx"
    write_trx(path, passed=passed, correct_class=correct_class)
    with pytest.raises(ValueError, match="regression"):
        repair.read_regression_result(path, 9)


def test_successful_build_stays_pending_and_never_launches_a_player(
    recipe: repair.RepairRecipe, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    environments: list[dict[str, str] | None] = []

    def fake_stage(
        command: list[str],
        directory: Path,
        log: Path,
        *,
        environment: dict[str, str] | None = None,
    ) -> None:
        calls.append(command)
        environments.append(environment)
        log.write_text("synthetic stage output\n")
        if command[1] == "test":
            write_trx(log.parent / "completion.trx")
        else:
            (directory / "out").mkdir(exist_ok=True)
            (directory / "out/Sts2Emulator.dylib").write_bytes(b"synthetic compiler artifact")

    monkeypatch.setenv(EXPERIMENT_METRICS_ENV, str(recipe.root / "metrics.json"))
    monkeypatch.setenv("DOTNET_ROLL_FORWARD", "Disable")
    monkeypatch.setattr(
        repair,
        "inspect_test_runtime",
        lambda directory: repair.select_test_runtime("Microsoft.NETCore.App 10.0.12 [/runtime]"),
    )
    monkeypatch.setattr(repair, "_run_logged", fake_stage)
    result = repair.build_backend_repair(recipe)
    assert [c[1] for c in calls] == ["test", "publish"]
    assert result["admitted"] is False and result["training_allowed"] is False
    assert result["games_played"] == 0 and result["automatic_followup"] is False
    assert result["test_runtime"]["expected_test_runtime"]["version"] == "10.0.12"
    assert environments[0] is not None
    assert environments[0]["DOTNET_ROLL_FORWARD"] == "Major"
    assert environments[0]["DOTNET_ROLL_FORWARD_TO_PRERELEASE"] == "0"
    assert environments[1] is None
    assert os.environ["DOTNET_ROLL_FORWARD"] == "Disable"
    manifest = load_patch_manifest(recipe.output / "candidate-manifest.json")
    assert manifest.admission_status == "pending_conformance"
    assert manifest.patch == recipe.manifest.patch
    assert manifest.engine.revision == result["candidate_revision"]
    assert repair.build_backend_repair(recipe) == result and len(calls) == 2
    runtime_path = recipe.output / result["test_runtime_report"]
    original = runtime_path.read_text()
    runtime_path.write_text(original + "changed evidence")
    with pytest.raises(ValueError, match="runtime evidence changed"):
        repair.show_backend_repair(recipe)
    runtime_path.write_text(original)
    (recipe.candidate / "out/Sts2Emulator.dylib").write_bytes(b"changed binary")
    with pytest.raises(ValueError, match="binary differs"):
        repair.show_backend_repair(recipe)


@pytest.mark.parametrize(
    ("installed", "expected", "roll_forward"),
    [
        ("Microsoft.NETCore.App 9.0.4 [/runtime]", "9.0.4", "LatestPatch"),
        ("Microsoft.NETCore.App 10.0.12 [/runtime]", "10.0.12", "Major"),
        (
            "Microsoft.NETCore.App 10.0.12 [/runtime]\n"
            "Microsoft.NETCore.App 9.0.2 [/runtime]\n"
            "Microsoft.NETCore.App 9.0.10 [/runtime]",
            "9.0.10",
            "LatestPatch",
        ),
    ],
)
def test_test_host_prefers_net9_and_can_use_installed_net10(
    installed: str, expected: str, roll_forward: str
) -> None:
    runtime = repair.select_test_runtime(installed)
    assert runtime["expected_test_runtime"]["version"] == expected
    assert runtime["roll_forward"] == roll_forward
    assert runtime["target_framework"] == "net9.0"
    assert runtime["policy_id"] == repair.TEST_RUNTIME_POLICY


@pytest.mark.parametrize(
    "installed",
    [
        "Microsoft.NETCore.App 8.0.12 [/runtime]",
        "Microsoft.AspNetCore.App 10.0.12 [/runtime]",
        "Microsoft.NETCore.App 10.0.0-preview.1 [/runtime]",
        "Microsoft.NETCore.App 11.0.0 [/runtime]",
        "",
    ],
)
def test_test_host_does_not_silently_accept_other_major_versions_or_previews(
    installed: str,
) -> None:
    with pytest.raises(ValueError, match="No compatible test host"):
        repair.select_test_runtime(installed)


def test_runtime_preflight_failure_prevents_test_and_publish_stages(
    recipe: repair.RepairRecipe, monkeypatch: pytest.MonkeyPatch
) -> None:
    def missing_runtime(directory: Path) -> dict[str, Any]:
        raise ValueError("No compatible test host")

    def unexpected_stage(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Runtime preflight must happen before native test/build stages")

    monkeypatch.setenv(EXPERIMENT_METRICS_ENV, str(recipe.root / "metrics.json"))
    monkeypatch.setattr(repair, "inspect_test_runtime", missing_runtime)
    monkeypatch.setattr(repair, "_run_logged", unexpected_stage)
    with pytest.raises(ValueError, match="No compatible test host"):
        repair.build_backend_repair(recipe)
    assert not (recipe.output / "build-attempts").exists()
    assert not (recipe.output / "build-report.json").exists()


def test_runtime_preflight_records_the_sdk_and_runtime_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    def fake_process(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        assert kwargs["cwd"] == tmp_path and kwargs["timeout"] == 10
        output = (
            "Microsoft.NETCore.App 10.0.12 [/runtime]\n"
            if command[1] == "--list-runtimes"
            else "10.0.401\n"
        )
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

    monkeypatch.setattr(
        "spireshift.full_run_backend_repair.shutil.which", lambda name: str(tmp_path / "dotnet")
    )
    monkeypatch.setattr(subprocess, "run", fake_process)
    runtime = repair.inspect_test_runtime(tmp_path)
    assert [c[1] for c in calls] == ["--list-runtimes", "--version"]
    assert runtime["sdk_version"] == "10.0.401"
    assert runtime["dotnet_executable"] == str(tmp_path / "dotnet")
    assert runtime["expected_test_runtime"]["version"] == "10.0.12"


def test_owner_script_caps_match_the_recipe_and_has_no_training_followup() -> None:
    recipe = repair.load_repair_recipe(
        Path("configs/backend-repair/sts2-v0.107.1-full-run-completion-v1.json")
    )
    script = Path("scripts/build-full-run-backend-repair-v1.sh").read_text()
    for flag, key in (
        ("--max-wall-seconds", "wall_seconds"),
        ("--max-cpu-seconds", "cpu_seconds"),
        ("--max-memory-bytes", "memory_bytes"),
        ("--max-storage-bytes", "storage_bytes"),
    ):
        assert f"{flag} {recipe.document['resource_limits'][key]}" in script
    assert "full-run evolve" not in script
    assert "backend admit" not in script
