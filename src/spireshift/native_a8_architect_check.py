"""Run one privileged Architect persistence regression with a fresh private profile."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.engine_native import (
    _require_native_launch_support,
    _run_boot,
    _sandbox,
    _shared_snapshot,
)
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_paired_inputs import freeze, load
from spireshift.native_win4_game import write

PROJECT = Path("mod/SpireShift.ArchitectPersistenceCheck")
AREA = Path("artifacts/native-a8-paired")


def run(root: Path, attempt: int) -> dict[str, Any]:
    _require_native_launch_support()
    out = root / AREA / f"architect-attempt-{attempt}"
    out.mkdir(parents=True, exist_ok=False)
    ctx = load(root)
    before = freeze(root, ctx)
    native = ctx["native"]
    candidate = native["candidate"]
    toolchain = identified(
        root / "artifacts/native-entry-text-repair/native-build-v56/report.json"
    )["build"]["toolchain"]
    sdk = toolchain["sdk_version"]
    if subprocess.check_output(["dotnet", "--version"], text=True, timeout=10).strip() != sdk:
        raise ValueError("The pinned compiler SDK changed")
    listed = subprocess.check_output(["dotnet", "--list-sdks"], text=True, timeout=10)
    sdk_dir = next(
        line.split("[", 1)[1].rstrip("]")
        for line in listed.splitlines()
        if line.startswith(sdk + " [")
    )
    if _sha_file(Path(sdk_dir) / sdk / "Roslyn/bincore/csc.dll") != toolchain["csc_sha256"]:
        raise ValueError("The pinned C# compiler changed")

    sources = {
        str(p.relative_to(root)): _sha_file(p)
        for p in [*sorted((root / PROJECT).glob("*.*")), Path(__file__).resolve()]
    }
    built = out / "build"
    with (out / "build.log").open("wb") as log:
        subprocess.run(
            [
                "dotnet",
                "build",
                str(root / PROJECT / f"{PROJECT.name}.csproj"),
                "-c",
                "Release",
                "--disable-build-servers",
                "-v:q",
                "--artifacts-path",
                str(built),
                f"-p:CandidateDirectory={candidate}",
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            cwd=root,
            timeout=45,
            check=True,
        )
    (binary,) = (built / "bin").rglob(f"{PROJECT.name}.dll")
    shared = Path.home() / "Library/Application Support/SlayTheSpire2"
    shared_before = _shared_snapshot(shared)
    guard = out / "profile-isolation.sb"
    guard.write_text(
        _sandbox(
            [
                shared,
                shared.parent / "Godot/app_userdata/SlayTheSpire2",
                shared.parent / "Steam",
                native["archive"].parent,
                candidate,
                native["runtime"],
                native["localization"],
                built,
                *(root / p["imported_path"] for p in ctx["originals"].values()),
                *(root / p["state_path"] for p in ctx["fitting_evidence"]["candidates"].values()),
            ]
        )
    )
    raw = out / "native-check.json"
    seed = f"SP1RESH1FTARCH60{attempt:02d}"
    process = _run_boot(
        [
            "/usr/bin/env",
            f"STS2_NATIVE_LOCALIZATION={native['localization']}",
            "DOTNET_ROLL_FORWARD=LatestPatch",
            "/usr/bin/sandbox-exec",
            "-f",
            str(guard),
            str(native["runtime"] / "dotnet"),
            str(binary),
            str(candidate),
            seed,
            str(raw),
        ],
        out,
        out,
        60,
    )
    write(out / "process.json", process)
    result = json.loads(raw.read_text()) if raw.is_file() else {}
    after = freeze(root, ctx)
    checks = {
        **result.get("checks", {}),
        "native_check_passed": result.get("status") == "architect_persistence_pass",
        "probe_exit_clean": process["returncode"] == 0 and not process["timed_out"],
        "shared_profile_unchanged": _shared_snapshot(shared) == shared_before,
        "game_assembly_exact": result.get("game_sha256") == native["build"]["runtime_sts2_sha256"],
        "headless_assembly_exact": result.get("wrapper_sha256")
        == native["build"]["artifact_sha256"],
        "godot_assembly_exact": result.get("godot_stub_sha256")
        == native["build"]["godot_stub_sha256"],
        "managed_runtime_exact": result.get("managed_runtime_version") == "9.0.7",
        "before_after_frozen": before == after and all(after.values()),
        "fixture_scope": result.get("seed") == seed
        and result.get("fixture_forced_boss_defeats") == 3
        and result.get("natural_victories") == result.get("optimizer_updates") == 0,
    }
    return write(
        out / "report.json",
        {
            "schema_version": "native-a8-architect-persistence-v1",
            "status": "architect_persistence_verified"
            if all(checks.values())
            else "architect_persistence_blocked",
            "environment_id": ctx["environment"]["manifest_id"],
            "objective": ctx["native"]["objective"],
            "fitting_evidence_id": ctx["fitting_evidence"]["report_id"],
            "seed": seed,
            "process": process,
            "checks": checks,
            "error": result.get("error"),
            "fixture_forced_boss_defeats": result.get("fixture_forced_boss_defeats"),
            "native_save_facts": result.get("stages", [])[-1] if result.get("stages") else None,
            "normal_start_evaluation_wins": 0,
            "optimizer_updates": 0,
            "official_live_qualification_granted": False,
            "sources": sources,
            "evidence": {
                str(p.relative_to(root)): _sha_file(p)
                for p in [
                    *out.glob("*.json"),
                    *out.glob("*.log"),
                    guard,
                    *sorted((out / "profile").rglob("*")),
                ]
                if p.is_file()
            },
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=int, required=True)
    args = parser.parse_args()
    if not 1 <= args.attempt <= 99:
        parser.error("Use a declared fresh attempt number in 1–99")
    result = run(Path.cwd(), args.attempt)
    print(
        json.dumps(
            {k: result[k] for k in ("status", "report_id", "seed", "checks", "error")}, indent=2
        )
    )
    return 0 if result["status"] == "architect_persistence_verified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
