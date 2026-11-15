"""Pinned export-only CLI build. Existing host builds and recipes remain immutable."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import GAME_RELATIVE, _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_live_inputs import load

PIN_FIELDS = (
    "artifact_sha256",
    "artifact_mvid",
    "godot_stub_sha256",
    "runtime_sts2_sha256",
    "reference_pack_id",
    "source_diff_id",
    "runtime_dependencies_id",
)


def verify_build(root: Path, cfg: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    if report.get("schema_version") != "interface-cli-export-build-result-v1" or report.get(
        "config_id"
    ) != manifest_identifier(cfg):
        raise ValueError("Export build belongs to different source/configuration")
    built = report["build"]
    if built.get("status") != "local_candidate_built_unqualified":
        raise ValueError("Export build did not complete")
    for name, expected in [
        ("baseline", cfg["expected_baseline"]),
        ("repaired", cfg["expected_repaired"]),
    ]:
        runs = built[name]
        if len(runs) != 2 or any(any(run.get(k) != v for k, v in expected.items()) for run in runs):
            raise ValueError("Fresh export builds differ from their exact pins")
        for run in runs:
            if _sha_file(Path(run["artifact"])) != run["artifact_sha256"]:
                raise ValueError("Export assembly bytes changed")
    check_sources(root, report["sources"])
    return built["repaired"][0]  # type: ignore[no-any-return]


def build(root: Path, path: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    if (
        cfg.get("schema_version") != "interface-cli-export-build-config-v1"
        or cfg.get("games_allowed") is not False
    ):
        raise ValueError("Use the short, export-only build recipe")
    check_sources(root, cfg["sources"])
    context = load(root, root / cfg["parent_live_recipe"])
    workspace = root / cfg["workspace"]
    if not workspace.is_relative_to(root / "artifacts/native-interface-audit"):
        raise ValueError("Preserve old CLI build outputs")
    final = workspace / "report.json"
    if final.exists():
        report = identified(final)
        verify_build(root, cfg, report)
        return report
    workspace.mkdir(parents=True, exist_ok=False)
    spec = {
        k: cfg[k]
        for k in [
            "expected_toolchain",
            "expected_baseline",
            "expected_repaired",
            "expected_source_diff_id",
        ]
    }
    spec.update(
        headless_root=str(root / "artifacts/engine-sources/sts2-headless-v1.0.1"),
        game=str(context["native"]["archive"] / GAME_RELATIVE),
        attempt=str(workspace),
        clone_cache=str(root / cfg["clone_cache"]),
        local_patch=str(root / cfg["local_patch"]),
        local_patch_sha256=cfg["sources"][cfg["local_patch"]],
    )
    atomic_json(workspace / "active.json", {"config_id": manifest_identifier(cfg)})
    atomic_json(workspace / "build-spec.json", spec)
    with (workspace / "console.log").open("xb") as console:
        done = subprocess.run(
            [cfg["node"], str(root / "scripts/engine-cli-local-build.mjs")],
            input=json.dumps(spec).encode(),
            stdout=console,
            stderr=subprocess.STDOUT,
            env={**os.environ, "DOTNET_ROLL_FORWARD": "Major"},
            timeout=230,
            check=False,
        )
    if done.returncode:
        raise ValueError("Export build failed; preserve source, compiler output and active marker")
    built = json.loads((workspace / "candidate-build.json").read_text())
    report = {
        "schema_version": "interface-cli-export-build-result-v1",
        "config_id": manifest_identifier(cfg),
        "build": built,
        "sources": {str(path.relative_to(root)): _sha_file(path), **cfg["sources"]},
        "games_launched": 0,
        "optimizer_updates": 0,
        "training_allowed": False,
    }
    report["report_id"] = manifest_identifier(report)
    verify_build(root, cfg, report)
    check_sources(root, context["sources"])
    atomic_json(final, report)
    (workspace / "active.json").rename(workspace / "completed.json")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    args = parser.parse_args()
    try:
        report = build(Path.cwd(), args.recipe.resolve())
        print(
            json.dumps({k: v for k, v in report.items() if k not in {"build", "sources"}}, indent=2)
        )
        return 0
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
