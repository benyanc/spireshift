"""Build a separate CanvasItem compatibility candidate and inspect its ABI."""

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
from spireshift.native_win4_inputs import RECIPE, frozen_checks, load

PATCH = "backend-patches/godot-canvas-item-v1/self-modulate.patch"
PROJECT = "backend-patches/godot-canvas-item-v1/Probe.csproj"
CHANGED_FILE = "GodotStubs/UI.cs"
WORKSPACE = "artifacts/native-win-curriculum/godot-canvas-build-v58"


def source_inventory(candidate: Path) -> dict[str, str]:
    source = candidate / "src"
    return {
        str(path.relative_to(source)): _sha_file(path)
        for path in source.rglob("*")
        if path.is_file() and not {"bin", "obj"} & set(path.relative_to(source).parts)
    }


def build(root: Path, out: Path) -> dict[str, Any]:
    context = load(root, root / RECIPE)
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

    def inspect(candidate: Path) -> dict[str, Any]:
        output = run([runtime, str(probe), str(candidate)])
        return dict(json.loads(output.strip().splitlines()[-1]))

    baseline = inspect(old)
    if (
        baseline["setter_present"]
        or "SetSelfModulate" not in baseline["test_subject_jit"]["SetColor"]
    ):
        raise ValueError("The exact baseline missing-method exception did not reproduce")
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
        run(
            ["dotnet", "build", "src/Sts2Headless/Sts2Headless.csproj", "-c", "Release", "-v:q"],
            candidate,
        )
        checked = inspect(candidate)
        if (
            not checked["setter_semantics"]
            or checked["test_subject_jit"]["SetColor"] is not None
            or checked["godot_method_references_checked"]
            != baseline["godot_method_references_checked"]
            or set(baseline["unresolved"]) - set(checked["unresolved"])
            != {
                token
                for token, message in baseline["unresolved"].items()
                if "CanvasItem.SetSelfModulate" in message
            }
            or len(checked["unresolved"]) != len(baseline["unresolved"]) - 1
            or set(checked["unresolved"]) - set(baseline["unresolved"])
        ):
            raise ValueError("Rebuilt ABI differs beyond the reached setter")
        game_hash = _sha_file(candidate / "lib/sts2.dll")
        if game_hash != expected_game:
            raise ValueError("Frozen game assembly changed")
        stub = candidate / "src/Sts2Headless/bin/Release/net9.0/GodotSharp.dll"
        builds.append(
            {
                "candidate": str(candidate.relative_to(root)),
                "artifact_sha256": checked["artifact_sha256"],
                "artifact_mvid": checked["artifact_mvid"],
                "godot_stub_sha256": _sha_file(stub),
                "runtime_sts2_sha256": game_hash,
                "probe": checked,
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
            "schema_version": "native-godot-canvas-build-v58",
            "status": "canvas_item_abi_verified",
            "parent_environment_id": context["environment"]["manifest_id"],
            "baseline_probe": baseline,
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
                    "backend-patches/godot-canvas-item-v1/Program.cs",
                    "src/spireshift/native_win5_build.py",
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
