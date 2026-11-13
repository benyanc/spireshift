"""Isolated support-library build; frozen game and CLI56 are never edited."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.engine_qualification import _inventory, _sha_file
from spireshift.native_win2_game import write
from spireshift.native_win2_inputs import RECIPE, frozen_checks, load

WORKSPACE = "artifacts/native-win-curriculum/godot-index-build-v57-r2"
PATCH = "backend-patches/godot-node-index-v1/node-index.patch"
PROBE = "backend-patches/godot-node-index-v1/Probe.csproj"


def build(root: Path) -> dict[str, Any]:
    context = load(root, root / RECIPE)
    before = frozen_checks(context)
    out = root / WORKSPACE
    out.mkdir(parents=True, exist_ok=False)
    old = context["native"]["candidate"]
    old_build = identified(
        root / "artifacts/native-entry-text-repair/native-build-v56/report.json"
    )["build"]
    toolchain = old_build["toolchain"]
    sdk = subprocess.check_output(["dotnet", "--version"], text=True).strip()
    if sdk != toolchain["sdk_version"]:
        raise ValueError("Compiler SDK changed")
    listed = subprocess.check_output(["dotnet", "--list-sdks"], text=True)
    sdk_dir = next(
        line.split("[", 1)[1].rstrip("]")
        for line in listed.splitlines()
        if line.startswith(sdk + " [")
    )
    compiler = Path(sdk_dir) / sdk / "Roslyn/bincore/csc.dll"
    if _sha_file(compiler) != toolchain["csc_sha256"]:
        raise ValueError("Compiler bytes changed")
    step = 0

    def run(command: list[str], cwd: Path = root) -> str:
        nonlocal step
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=90,
            env={**os.environ, "DOTNET_ROLL_FORWARD": "Major"},
            check=False,
        )
        (out / f"step-{step}.log").write_text(result.stdout + result.stderr)
        step += 1
        if result.returncode:
            raise ValueError("Support build/probe failed; preserve its log")
        return result.stdout

    run(
        [
            "dotnet",
            "build",
            str(root / PROBE),
            "--artifacts-path",
            str(out / "probe-artifacts"),
            "-v:q",
        ]
    )
    probe = next((out / "probe-artifacts/bin").rglob("Probe.dll"))

    def check(mode: str, path: Path) -> dict[str, Any]:
        raw = run([str(context["native"]["runtime"] / "dotnet"), str(probe), mode, str(path)])
        return dict(json.loads(raw.strip().splitlines()[-1]))

    results = []
    source_inventory = {
        str(p.relative_to(old / "src")): _sha_file(p)
        for p in (old / "src").rglob("*")
        if p.is_file() and p.suffix in {".cs", ".csproj"} and not {"bin", "obj"} & set(p.parts)
    }
    for tag in ["candidate", "independent-build"]:
        candidate = out / tag
        shutil.copytree(old, candidate, ignore=shutil.ignore_patterns(".git", "bin", "obj"))
        run(["git", "apply", "--no-index", "--whitespace=error-all", str(root / PATCH)], candidate)
        after_sources = {
            str(p.relative_to(candidate / "src")): _sha_file(p)
            for p in (candidate / "src").rglob("*")
            if p.is_file() and p.suffix in {".cs", ".csproj"}
        }
        changed = [
            n
            for n in source_inventory.keys() | after_sources.keys()
            if source_inventory.get(n) != after_sources.get(n)
        ]
        if changed != ["GodotStubs/Core.cs"]:
            raise ValueError("Changes exceed the declared support method")
        run(
            ["dotnet", "build", "src/Sts2Headless/Sts2Headless.csproj", "-c", "Release", "-v:q"],
            candidate,
        )
        artifact = candidate / "src/Sts2Headless/bin/Release/net9.0/Sts2Headless.dll"
        host = check("fingerprint", artifact)
        api, jit = check("api", candidate), check("jit", candidate)
        if jit.get("jit_prepared") is not True:
            raise ValueError("Reattach visual method still cannot be compiled")
        game_hash = _sha_file(candidate / "lib/sts2.dll")
        if game_hash != context["native"]["build"]["runtime_sts2_sha256"]:
            raise ValueError("The game assembly changed")
        results.append(
            {
                "candidate": str(candidate.relative_to(root)),
                "artifact_sha256": host["sha256"],
                "artifact_mvid": host["mvid"],
                "godot_stub_sha256": _sha_file(artifact.parent / "GodotSharp.dll"),
                "runtime_sts2_sha256": game_hash,
                "api": api,
                "jit": jit,
                "source_inventory": after_sources,
            }
        )
    if any(
        results[0][k] != results[1][k]
        for k in [
            "artifact_sha256",
            "artifact_mvid",
            "godot_stub_sha256",
            "runtime_sts2_sha256",
            "source_inventory",
        ]
    ):
        raise ValueError("Independent support builds differ")
    old_jit = check("jit", old)
    if old_jit.get("jit_prepared") is not False or "GetIndex" not in old_jit.get("error", ""):
        raise ValueError("Exact old missing-method error did not reproduce")
    after = frozen_checks(context)
    sources = {
        n: _sha_file(root / n)
        for n in [
            PATCH,
            PROBE,
            "backend-patches/godot-node-index-v1/Program.cs",
            "src/spireshift/native_win3_build.py",
        ]
    }
    candidate = root / results[0]["candidate"]
    report = write(
        out / "report.json",
        {
            "schema_version": "native-godot-index-build-v57",
            "status": "support_build_and_jit_verified",
            "old_jit": old_jit,
            "builds": results,
            "candidate_inventory": _inventory(candidate),
            "changed_production_source_files": ["GodotStubs/Core.cs"],
            "all_host_CLI_and_game_rules_source_unchanged": True,
            "compiler": toolchain,
            "checks_before": before,
            "checks_after": after,
            "game_build_frozen": True,
            "new_games": 0,
            "optimizer_updates": 0,
            "sources": sources,
            "evidence": {
                str(p.relative_to(root)): _sha_file(p) for p in out.rglob("*") if p.is_file()
            },
        },
    )
    return report


if __name__ == "__main__":
    result = build(Path.cwd())
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in {"sources", "evidence", "builds", "candidate_inventory"}
            }
        )
    )
