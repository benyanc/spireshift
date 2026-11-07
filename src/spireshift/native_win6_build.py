"""Build the exact headless Trial presentation patch over support build 58."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.engine_qualification import _inventory, _sha_file
from spireshift.native_win4_game import write
from spireshift.native_win5_build import source_inventory
from spireshift.native_win5_inputs import frozen_checks, load

PATCH = "backend-patches/headless-trial-portrait-v1/trial-portrait.patch"
PROJECT = "backend-patches/godot-node-index-v1/Probe.csproj"
CHANGED_FILE = "Sts2Headless/RunSimulator.cs"
WORKSPACE = "artifacts/native-win-curriculum/trial-portrait-build-v59-r2"


def build(root: Path, out: Path) -> dict[str, Any]:
    context = load(root)
    before = frozen_checks(context)
    old = context["native"]["candidate"]
    expected_game = context["native"]["build"]["runtime_sts2_sha256"]
    toolchain = identified(
        root / "artifacts/native-entry-text-repair/native-build-v56/report.json"
    )["build"]["toolchain"]
    sdk = subprocess.check_output(["dotnet", "--version"], text=True, timeout=10).strip()
    if sdk != toolchain["sdk_version"]:
        raise ValueError("Pinned compiler SDK changed")
    listed = subprocess.check_output(["dotnet", "--list-sdks"], text=True, timeout=10)
    sdk_dir = next(
        line.split("[", 1)[1].rstrip("]")
        for line in listed.splitlines()
        if line.startswith(sdk + " [")
    )
    if _sha_file(Path(sdk_dir) / sdk / "Roslyn/bincore/csc.dll") != toolchain["csc_sha256"]:
        raise ValueError("Pinned compiler bytes changed")
    out.mkdir(parents=True, exist_ok=False)
    step = 0

    def run(command: list[str], cwd: Path = root) -> str:
        nonlocal step
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=70,
            env={**os.environ, "DOTNET_ROLL_FORWARD": "Major"},
            check=False,
        )
        (out / f"step-{step:02d}.log").write_text(result.stdout + result.stderr)
        step += 1
        if result.returncode:
            raise ValueError("Support build or ABI probe failed. Preserve the recorded step.")
        return result.stdout

    run(["dotnet", "build", str(root / PROJECT), "--artifacts-path", str(out / "probe"), "-v:q"])
    probe = next((out / "probe/bin").rglob("Probe.dll"))
    runtime = str(context["native"]["runtime"] / "dotnet")

    def inspect(artifact: Path) -> dict[str, Any]:
        output = run([runtime, str(probe), "fingerprint", str(artifact)])
        return dict(json.loads(output.strip().splitlines()[-1]))

    original_sources = source_inventory(old)
    builds: list[dict[str, Any]] = []
    for name in ("candidate", "independent-build"):
        candidate = out / name
        shutil.copytree(old, candidate, ignore=shutil.ignore_patterns(".git", "bin", "obj"))
        run(["git", "apply", "--no-index", "--whitespace=error-all", str(root / PATCH)], candidate)
        sources = source_inventory(candidate)
        changed = sorted(
            k
            for k in original_sources.keys() | sources.keys()
            if original_sources.get(k) != sources.get(k)
        )
        if changed != [CHANGED_FILE]:
            raise ValueError("Support patch changed an undeclared source file")
        # Use the existing reference and runtime DLLs. A rebuild would stamp
        # the checkout's current revision into the otherwise unchanged stub.
        for name in ("bin/Release/net9.0", "obj/Release/net9.0/ref"):
            directory = Path("src/GodotStubs") / name
            shutil.copytree(old / directory, candidate / directory)
        run(
            [
                "dotnet",
                "build",
                "src/Sts2Headless/Sts2Headless.csproj",
                "-c",
                "Release",
                "-v:q",
                "-p:BuildProjectReferences=false",
                "-p:EnableSourceControlManagerQueries=false",
            ],
            candidate,
        )
        artifact = candidate / "src/Sts2Headless/bin/Release/net9.0/Sts2Headless.dll"
        checked = inspect(artifact)
        game_hash = _sha_file(candidate / "lib/sts2.dll")
        if game_hash != expected_game:
            raise ValueError("Frozen game assembly changed")
        stub = candidate / "src/Sts2Headless/bin/Release/net9.0/GodotSharp.dll"
        if _sha_file(stub) != context["native"]["build"]["godot_stub_sha256"]:
            raise ValueError("Pinned Godot support library changed")
        builds.append(
            {
                "candidate": str(candidate.relative_to(root)),
                "artifact_sha256": checked["sha256"],
                "artifact_mvid": checked["mvid"],
                "godot_stub_sha256": _sha_file(stub),
                "runtime_sts2_sha256": game_hash,
            }
        )
    if {k: v for k, v in builds[0].items() if k != "candidate"} != {
        k: v for k, v in builds[1].items() if k != "candidate"
    }:
        raise ValueError("Independent support builds disagree")
    after = frozen_checks(context)
    if not all(before.values()) or not all(after.values()):
        raise ValueError("Frozen inputs changed during the build")
    return write(
        out / "report.json",
        {
            "schema_version": "native-headless-trial-build-v59",
            "status": "trial_portrait_bridge_built",
            "parent_environment_id": context["environment"]["manifest_id"],
            "builds": builds,
            "candidate_inventory": _inventory(root / builds[0]["candidate"]),
            "changed_production_source_files": [CHANGED_FILE],
            "checks_before": before,
            "checks_after": after,
            "sources": {
                name: _sha_file(root / name)
                for name in [
                    PATCH,
                    PROJECT,
                    "backend-patches/godot-node-index-v1/Program.cs",
                    "src/spireshift/native_win6_build.py",
                ]
            },
            "evidence": {
                str(path.relative_to(root)): _sha_file(path)
                for path in sorted(out.glob("step-*.log"))
            },
            "new_games": 0,
            "optimizer_updates": 0,
        },
    )


if __name__ == "__main__":
    import sys

    root = Path.cwd()
    result = build(root, root / (sys.argv[1] if len(sys.argv) > 1 else WORKSPACE))
    print(
        json.dumps(
            {k: result[k] for k in ["status", "report_id", "changed_production_source_files"]}
        )
    )
