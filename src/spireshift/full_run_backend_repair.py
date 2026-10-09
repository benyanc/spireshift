"""Isolated, owner-built repair candidate; never automatically admit or train it."""

from __future__ import annotations

import ctypes
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spireshift.core.manifest import PatchManifest, load_patch_manifest, manifest_identifier
from spireshift.full_run_experience import atomic_json
from spireshift.resource_tracking import EXPERIMENT_METRICS_ENV

TEST_DESTINATION = "src/Sts2Emulator.Tests/SpireShiftFullRunCompletionTests.cs"
TEST_CLASS = "SpireShiftFullRunCompletionTests"
PUBLIC_TEST_DESTINATION = "src/Sts2Emulator.Tests/SpireShiftPublicChoicesTests.cs"
PUBLIC_TEST_CLASS = "SpireShiftPublicChoicesTests"
EVENT_TEST_DESTINATION = "src/Sts2Emulator.Tests/SpireShiftEventContinuationTests.cs"
EVENT_TEST_CLASS = "SpireShiftEventContinuationTests"
TEST_RUNTIME_POLICY = "net9-preferred-net10-test-host-v1"
REMAINING_CHECKS = (
    "expose_and_bind_all_public_combat_selection_candidates",
    "bind_confirmation_and_selected_bundle_state",
    "declare_actual_fixed_ascension_rules",
    "validate_changed_act_boundaries_against_the_frozen_game",
    "readmit_new_ruleset_before_a_new_training_recipe",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(root: Path, *arguments: str, environment: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    if result.returncode:
        raise ValueError(f"Repair Git operation failed: {result.stderr.strip()}")
    return result.stdout.strip()


@dataclass(frozen=True)
class RepairRecipe:
    document: dict[str, Any]
    root: Path
    manifest: PatchManifest

    def path(self, value: str) -> Path:
        return (self.root / value).resolve()

    @property
    def candidate(self) -> Path:
        return self.path(self.document["candidate_upstream"])

    @property
    def output(self) -> Path:
        return self.path(self.document["output_dir"])

    @property
    def public_choices(self) -> bool:
        return self.document["schema_version"] in {
            "full-run-backend-repair-config-v2",
            "full-run-backend-repair-config-v3",
        }

    @property
    def event_continuation(self) -> bool:
        return bool(self.document["schema_version"] == "full-run-backend-repair-config-v3")

    @property
    def sources(self) -> tuple[dict[str, Any], ...]:
        if self.public_choices:
            return tuple(self.document["engine_sources"])
        return (self.document["engine_source"],)

    @property
    def test_destination(self) -> str:
        if self.event_continuation:
            return EVENT_TEST_DESTINATION
        return PUBLIC_TEST_DESTINATION if self.public_choices else TEST_DESTINATION

    @property
    def test_classes(self) -> tuple[str, ...]:
        if self.event_continuation:
            return (TEST_CLASS, PUBLIC_TEST_CLASS, EVENT_TEST_CLASS)
        return (TEST_CLASS, PUBLIC_TEST_CLASS) if self.public_choices else (TEST_CLASS,)


def load_repair_recipe(path: Path, *, root: Path | None = None) -> RepairRecipe:
    root = (root or Path.cwd()).resolve()
    d = json.loads(path.read_text())
    if not isinstance(d, dict) or d.get("schema_version") not in {
        "full-run-backend-repair-config-v1",
        "full-run-backend-repair-config-v2",
        "full-run-backend-repair-config-v3",
    }:
        raise ValueError("Unsupported backend repair configuration version")
    event_continuation = d["schema_version"] == "full-run-backend-repair-config-v3"
    public_choices = d["schema_version"] != "full-run-backend-repair-config-v1"
    keys = {
        "schema_version",
        "base_upstream",
        "base_revision",
        "base_manifest",
        "base_manifest_id",
        "patch",
        "regression_tests",
        "engine_sources" if public_choices else "engine_source",
        "candidate_upstream",
        "output_dir",
        "runtime",
        "resource_limits",
        "automatic_training",
        "automatic_admission",
        "minimum_regression_tests",
        "config_id",
    }
    if set(d) != keys:
        raise ValueError("Unexpected backend repair configuration fields")
    if d["config_id"] != manifest_identifier({k: v for k, v in d.items() if k != "config_id"}):
        raise ValueError("Backend repair configuration identity differs")
    if d["automatic_training"] is not False or d["automatic_admission"] is not False:
        raise ValueError("A build candidate cannot authorize training or admission")
    if d["runtime"] != "osx-arm64" or d["minimum_regression_tests"] != (
        32 if event_continuation else 23 if public_choices else 9
    ):
        raise ValueError("Unsupported frozen backend repair scope")
    for key in ("base_upstream", "candidate_upstream", "output_dir"):
        p = (root / d[key]).resolve()
        if not p.is_relative_to(root / "artifacts"):
            raise ValueError("Backend repair checkouts and outputs must remain private artifacts")
    private_paths = [
        (root / d[k]).resolve() for k in ("base_upstream", "candidate_upstream", "output_dir")
    ]
    if any(
        a.is_relative_to(b)
        for i, a in enumerate(private_paths)
        for j, b in enumerate(private_paths)
        if i != j
    ):
        raise ValueError("Backend repair paths must be separate and cannot contain each other")
    for key in ("patch", "regression_tests"):
        entry = d[key]
        if set(entry) != {"path", "sha256"} or _sha(root / entry["path"]) != entry["sha256"]:
            raise ValueError(f"Backend repair {key} identity differs")
    sources = d["engine_sources"] if public_choices else [d["engine_source"]]
    if (
        not isinstance(sources, list)
        or not sources
        or any(
            not isinstance(s, dict) or set(s) != {"path", "base_sha256", "repaired_sha256"}
            for s in sources
        )
    ):
        raise ValueError("Backend repair engine source fields differ")
    if len({s["path"] for s in sources}) != len(sources):
        raise ValueError("Backend repair source paths are duplicated")
    if public_choices:
        expected_sources = (
            {"src/Sts2Emulator/Core/Run/RunEngine.cs"}
            if event_continuation
            else {
                "src/Sts2Emulator/Core/CombatObservation.cs",
                "src/Sts2Emulator/Core/Run/RunPublicChoices.cs",
                "src/Sts2Emulator/Interop/RunNativeExports.cs",
            }
        )
        if {s["path"] for s in sources} != expected_sources:
            raise ValueError("Public-choice repair source scope differs")
    limits = d["resource_limits"]
    if set(limits) != {"wall_seconds", "cpu_seconds", "memory_bytes", "storage_bytes"} or any(
        type(v) is not int or v <= 0 for v in limits.values()
    ):
        raise ValueError("Backend repair resource limits must be positive integers")
    manifest = load_patch_manifest(root / d["base_manifest"])
    if (
        manifest.manifest_id != d["base_manifest_id"]
        or manifest.engine.revision != d["base_revision"]
    ):
        raise ValueError("Backend repair base ruleset differs")
    return RepairRecipe(d, root, manifest)


def _identified(path: Path, body: dict[str, Any]) -> dict[str, Any]:
    value = {**body, "report_id": manifest_identifier(body)}
    if path.exists():
        if json.loads(path.read_text()) != value:
            raise ValueError(f"Existing repair result belongs to another source: {path}")
    else:
        atomic_json(path, value)
    return value


def _prepare(recipe: RepairRecipe) -> dict[str, Any]:
    d, candidate = recipe.document, recipe.candidate
    base = recipe.path(d["base_upstream"])
    if _git(base, "rev-parse", "HEAD") != d["base_revision"] or _git(base, "status", "--porcelain"):
        raise ValueError("Pinned original checkout changed; it will not be modified")

    def matches(root: Path, source: dict[str, Any], key: str) -> bool:
        path = root / source["path"]
        return (
            not path.exists()
            if source[key] is None
            else path.is_file() and _sha(path) == source[key]
        )

    if not all(matches(base, source, "base_sha256") for source in recipe.sources):
        raise ValueError("Pinned original engine source changed")
    if not candidate.exists():
        candidate.parent.mkdir(parents=True, exist_ok=True)
        _git(base, "worktree", "add", "--detach", str(candidate), d["base_revision"])
    head = _git(candidate, "rev-parse", "HEAD")
    changed_paths = {s["path"] for s in recipe.sources} | {recipe.test_destination}
    if head == d["base_revision"]:
        # An interrupted preparation may already contain the exact source/test repair.
        if not all(matches(candidate, source, "repaired_sha256") for source in recipe.sources):
            if not all(matches(candidate, source, "base_sha256") for source in recipe.sources):
                raise ValueError("Candidate engine does not match the base or exact repair")
            _git(candidate, "apply", "--check", str(recipe.path(d["patch"]["path"])))
            _git(candidate, "apply", str(recipe.path(d["patch"]["path"])))
        target = candidate / recipe.test_destination
        if target.exists() and _sha(target) != d["regression_tests"]["sha256"]:
            raise ValueError("Candidate regression tests differ; refusing to replace them")
        if not target.exists():
            shutil.copyfile(recipe.path(d["regression_tests"]["path"]), target)
        if not all(matches(candidate, source, "repaired_sha256") for source in recipe.sources):
            raise ValueError("Candidate engine does not match the exact repair")
        expected_names = _git(candidate, "diff", "--name-only", "HEAD").splitlines()
        untracked = _git(candidate, "ls-files", "--others", "--exclude-standard").splitlines()
        if (set(expected_names) | set(untracked)) - changed_paths:
            raise ValueError("Candidate has unrelated changes")
        _git(candidate, "add", "--", *sorted(changed_paths))
        environment = {
            **os.environ,
            "GIT_AUTHOR_DATE": "2026-10-08T00:00:00+00:00",
            "GIT_COMMITTER_DATE": "2026-10-08T00:00:00+00:00",
        }
        _git(
            candidate,
            "-c",
            "user.name=SpireShift",
            "-c",
            "user.email=spireshift@localhost",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-m",
            f"SpireShift full-run completion repair {d['config_id']}",
            environment=environment,
        )
    if _git(candidate, "status", "--porcelain"):
        raise ValueError("Candidate checkout contains unrelated modifications")
    revision = _git(candidate, "rev-parse", "HEAD")
    if (
        _git(candidate, "rev-parse", "HEAD^") != d["base_revision"]
        or set(_git(candidate, "diff", "--name-only", "HEAD^", "HEAD").splitlines())
        != changed_paths
    ):
        raise ValueError("Candidate revision is not the isolated source/test repair")
    if (
        not all(matches(candidate, source, "repaired_sha256") for source in recipe.sources)
        or _sha(candidate / recipe.test_destination) != d["regression_tests"]["sha256"]
    ):
        raise ValueError("Candidate source differs from the frozen repair")
    return _identified(
        recipe.output / "preparation.json",
        {
            "schema_version": "full-run-backend-repair-preparation-v1",
            "config_id": d["config_id"],
            "base_revision": d["base_revision"],
            "candidate_revision": revision,
            "candidate_tree": _git(candidate, "rev-parse", "HEAD^{tree}"),
            "patch_sha256": d["patch"]["sha256"],
            "regression_tests_sha256": d["regression_tests"]["sha256"],
            "native_build_started": False,
            "training_allowed": False,
            "admitted": False,
        },
    )


def prepare_backend_repair(recipe: RepairRecipe) -> dict[str, Any]:
    recipe.output.mkdir(parents=True, exist_ok=True)
    with (recipe.output / "owner.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _prepare(recipe)


def read_regression_result(
    path: Path, minimum: int, classes: tuple[str, ...] = (TEST_CLASS,)
) -> dict[str, int]:
    try:
        document = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise ValueError(f"Cannot read native regression results: {path}") from exc
    counters = next((e for e in document.iter() if e.tag.rsplit("}", 1)[-1] == "Counters"), None)
    if counters is None:
        raise ValueError("Native regression report has no test counters")
    summary = {
        k: int(counters.attrib.get(k, "0")) for k in ("total", "executed", "passed", "failed")
    }
    if (
        summary["passed"] < minimum
        or summary["passed"] != summary["total"]
        or summary["executed"] != summary["total"]
        or summary["failed"]
    ):
        raise ValueError("Required native completion regressions did not all pass")
    results = [e for e in document.iter() if e.tag.rsplit("}", 1)[-1] == "UnitTestResult"]
    if len(results) != summary["total"] or any(
        not any(name in e.attrib.get("testName", "") for name in classes)
        or e.attrib.get("outcome") != "Passed"
        for e in results
    ):
        raise ValueError("Native regression results do not belong to the completion repair")
    if any(not any(name in e.attrib.get("testName", "") for e in results) for name in classes):
        raise ValueError("A required native regression class is missing")
    return summary


def inspect_public_choice_exports(library: Path) -> dict[str, Any]:
    """Read capabilities on an empty handle, with zero reset/step calls or game attempts."""
    from spireshift.public_run_choices import decode_public_choices, read_complete_state_list

    native = ctypes.CDLL(str(library))
    native.Sts2Run_Create.restype = ctypes.c_int
    native.Sts2Run_Create.argtypes = []
    native.Sts2Run_Destroy.restype = None
    native.Sts2Run_Destroy.argtypes = [ctypes.c_int]
    native.Sts2Run_GetStateList.restype = ctypes.c_int
    native.Sts2Run_GetStateList.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_int),
        ctypes.c_int,
    ]
    handle = native.Sts2Run_Create()
    if handle < 0:
        raise ValueError("Could not allocate a public-choice capability handle")
    try:
        lists = {
            i: read_complete_state_list(native.Sts2Run_GetStateList, handle, i)
            for i in (22, 23, 24)
        }
        view = decode_public_choices("combat", lists[22], lists[23], lists[24])
        if view.combat_selection is not None or view.bundle_selection is not None:
            raise ValueError("Empty capability handle exposes stale menu choices")
        return {
            "schema_version": "public-choice-export-check-v1",
            "view": view.as_dict(),
            "games_played": 0,
        }
    finally:
        native.Sts2Run_Destroy(handle)


def select_test_runtime(installed_runtimes: str) -> dict[str, Any]:
    """Prefer the target runtime; permit only the inspected .NET 10 test-host fallback."""
    runtimes = []
    for line in installed_runtimes.splitlines():
        match = re.fullmatch(r"Microsoft\.NETCore\.App (\d+\.\d+\.\d+) \[(.+)\]", line)
        if match:
            version, directory = match.groups()
            runtimes.append({"version": version, "directory": directory})
    selected = None
    for major in (9, 10):
        candidates = [r for r in runtimes if r["version"].startswith(f"{major}.0.")]
        if candidates:
            selected = max(candidates, key=lambda r: int(r["version"].rsplit(".", 1)[1]))
            break
    if selected is None:
        raise ValueError(
            "Native regression tests target .NET 9 and require an installed stable .NET 9.0 "
            "or 10.0 runtime. No compatible test host was found; no build was launched."
        )
    return {
        "policy_id": TEST_RUNTIME_POLICY,
        "target_framework": "net9.0",
        "expected_test_runtime": selected,
        "installed_core_runtimes": runtimes,
        "roll_forward": "LatestPatch" if selected["version"].startswith("9.") else "Major",
        "scope": "regression_test_host_only_native_target_unchanged",
    }


def inspect_test_runtime(directory: Path) -> dict[str, Any]:
    executable = shutil.which("dotnet")
    if executable is None:
        raise ValueError("The owner build needs dotnet on PATH; no native build was launched")
    output = {}
    for flag in ("--list-runtimes", "--version"):
        try:
            result = subprocess.run(
                [executable, flag],
                cwd=directory,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
        except subprocess.TimeoutExpired as exc:
            raise ValueError(".NET test-host preflight timed out; no build was launched") from exc
        if result.returncode:
            raise ValueError(f".NET test-host preflight failed: {result.stderr.strip()}")
        output[flag] = result.stdout.strip()
    return {
        **select_test_runtime(output["--list-runtimes"]),
        "dotnet_executable": str(Path(executable).resolve()),
        "sdk_version": output["--version"],
    }


def _run_logged(
    command: list[str],
    directory: Path,
    log: Path,
    *,
    environment: dict[str, str] | None = None,
) -> None:
    with log.open("x") as handle:
        result = subprocess.run(
            command,
            cwd=directory,
            stdout=handle,
            stderr=subprocess.STDOUT,
            check=False,
            env=environment,
        )
    if result.returncode:
        tail = "\n".join(log.read_text(errors="replace").splitlines()[-20:])
        raise ValueError(f"Native repair stage failed; saved log: {log}\n{tail}")


def _pending_manifest(
    recipe: RepairRecipe, prepared: dict[str, Any], library: Path
) -> dict[str, Any]:
    body = recipe.manifest.body_dict()
    revision = prepared["candidate_revision"]
    engine = dict(recipe.manifest.engine.as_dict())
    engine.update(revision=revision, digest={"algorithm": "git-commit-sha1", "value": revision})
    body["engine"] = engine
    body["admission_status"] = "pending_conformance"
    mechanics = []
    for artifact in recipe.manifest.mechanics:
        item = artifact.as_dict()
        if artifact.kind == "simulator-rule-source":
            item.update(
                version=revision, digest={"algorithm": "git-commit-sha1", "value": revision}
            )
        if artifact.kind == "compiled-simulator-library":
            item.update(
                version=revision,
                digest={"algorithm": "sha256", "value": _sha(library)},
                size_bytes=library.stat().st_size,
            )
        mechanics.append(item)
    body["mechanics"] = mechanics
    return PatchManifest.from_mapping({**body, "manifest_id": manifest_identifier(body)}).as_dict()


def show_backend_repair(recipe: RepairRecipe) -> dict[str, Any]:
    value: dict[str, Any] = json.loads((recipe.output / "build-report.json").read_text())
    if (
        value["report_id"]
        != manifest_identifier({k: v for k, v in value.items() if k != "report_id"})
        or value["config_id"] != recipe.document["config_id"]
    ):
        raise ValueError("Saved backend repair report identity differs")
    manifest_path = recipe.output / "candidate-manifest.json"
    manifest = load_patch_manifest(manifest_path)
    if (
        manifest.manifest_id != value["candidate_manifest_id"]
        or manifest.admission_status != "pending_conformance"
    ):
        raise ValueError("Saved repair candidate cannot be treated as admitted")
    if _sha(recipe.candidate / "out/Sts2Emulator.dylib") != value["native_sha256"]:
        raise ValueError("Saved repair binary differs from its report")
    if _sha(recipe.output / value["test_report"]) != value["test_report_sha256"]:
        raise ValueError("Saved native regression results changed")
    if (
        "test_runtime_report" in value
        and _sha(recipe.output / value["test_runtime_report"])
        != value["test_runtime_report_sha256"]
    ):
        raise ValueError("Saved regression runtime evidence changed")
    if _git(recipe.candidate, "rev-parse", "HEAD") != value["candidate_revision"] or _git(
        recipe.candidate, "status", "--porcelain"
    ):
        raise ValueError("Saved native candidate source changed")
    return value


def build_backend_repair(recipe: RepairRecipe) -> dict[str, Any]:
    if not os.environ.get(EXPERIMENT_METRICS_ENV):
        raise ValueError(
            "Only the owner-run repair script launches native builds with resource caps"
        )
    recipe.output.mkdir(parents=True, exist_ok=True)
    with (recipe.output / "owner.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        prepared = _prepare(recipe)
        if (recipe.output / "build-report.json").exists():
            return show_backend_repair(recipe)
        runtime = inspect_test_runtime(recipe.candidate)
        attempts = recipe.output / "build-attempts"
        attempts.mkdir(exist_ok=True)
        n = 1
        while (attempts / f"attempt-{n:04d}").exists():
            n += 1
        attempt = attempts / f"attempt-{n:04d}"
        attempt.mkdir()
        runtime_path = attempt / "test-runtime.json"
        _identified(runtime_path, {"schema_version": "backend-repair-test-runtime-v1", **runtime})
        print(
            f"Regression test host: .NET {runtime['expected_test_runtime']['version']} "
            f"({runtime['roll_forward']}); native target remains net9.0.",
            flush=True,
        )
        print(
            f"Checking {recipe.document['minimum_regression_tests']} synthetic repair regressions; "
            "no player training.",
            flush=True,
        )
        _run_logged(
            [
                "dotnet",
                "test",
                "src/Sts2Emulator.Tests/Sts2Emulator.Tests.csproj",
                "-c",
                "Release",
                "--filter",
                "|".join(f"FullyQualifiedName~{name}" for name in recipe.test_classes),
                "--logger",
                "trx;LogFileName=completion.trx",
                "--results-directory",
                str(attempt),
                "-m:2",
            ],
            recipe.candidate,
            attempt / "regression.log",
            environment={
                **os.environ,
                "DOTNET_ROLL_FORWARD": runtime["roll_forward"],
                "DOTNET_ROLL_FORWARD_TO_PRERELEASE": "0",
            },
        )
        regression_path = attempt / "completion.trx"
        counts = read_regression_result(
            regression_path, recipe.document["minimum_regression_tests"], recipe.test_classes
        )
        print(
            "Building the separate native candidate. Existing simulator remains intact.", flush=True
        )
        _run_logged(
            [
                "dotnet",
                "publish",
                "src/Sts2Emulator/Sts2Emulator.csproj",
                "-c",
                "Release",
                "-r",
                recipe.document["runtime"],
                "--self-contained",
                "-o",
                "out",
                "-m:2",
            ],
            recipe.candidate,
            attempt / "publish.log",
        )
        library = recipe.candidate / "out/Sts2Emulator.dylib"
        if not library.is_file() or not library.stat().st_size:
            raise ValueError("Native repair publish did not produce its library")
        # Build tools must not rewrite checked-in rules or generated game data.
        if _git(recipe.candidate, "status", "--porcelain"):
            raise ValueError("Native build modified tracked candidate source")
        public_check = inspect_public_choice_exports(library) if recipe.public_choices else None
        manifest = _pending_manifest(recipe, prepared, library)
        manifest_path = recipe.output / "candidate-manifest.json"
        if manifest_path.exists():
            if json.loads(manifest_path.read_text()) != manifest:
                raise ValueError("Existing candidate manifest belongs to a different native build")
        else:
            atomic_json(manifest_path, manifest)
        return _identified(
            recipe.output / "build-report.json",
            {
                "schema_version": "full-run-backend-repair-build-v1",
                "config_id": recipe.document["config_id"],
                "preparation_id": prepared["report_id"],
                "candidate_revision": prepared["candidate_revision"],
                "candidate_manifest_id": manifest["manifest_id"],
                "native_sha256": _sha(library),
                "native_size_bytes": library.stat().st_size,
                "regression_tests": counts,
                "test_report": str(regression_path.relative_to(recipe.output)),
                "test_report_sha256": _sha(regression_path),
                "test_runtime": runtime,
                "test_runtime_report": str(runtime_path.relative_to(recipe.output)),
                "test_runtime_report_sha256": _sha(runtime_path),
                "admitted": False,
                "training_allowed": False,
                "checkpoint_promoted": False,
                "automatic_followup": False,
                "games_played": 0,
                **(
                    {
                        "public_choice_export_check": public_check,
                        "agent_integration_complete": False,
                    }
                    if recipe.public_choices
                    else {}
                ),
                "claim_scope": "synthetic_regressions_and_native_build_not_live_game_conformance",
                "remaining_checks": (
                    [
                        "derive_new_adapter_manifest_for_event_repair_native_identity",
                        "replay_all_89_original_failures_with_event_endpoint_checks",
                        "verify_source_fixed_ascension_8_against_the_frozen_game",
                        *REMAINING_CHECKS[3:],
                    ]
                    if recipe.event_continuation
                    else [
                        "integrate_sidecar_into_new_adapter_and_full_run_encoder",
                        "verify_source_fixed_ascension_8_against_the_frozen_game",
                        *REMAINING_CHECKS[3:],
                    ]
                    if recipe.public_choices
                    else list(REMAINING_CHECKS)
                ),
            },
        )
