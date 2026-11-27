"""Exact current environment and immutable historical cross-host evidence bindings."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_connector import _verify_toolchain, load_connector_qualification_config
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file, load_engine_qualification_config
from spireshift.engine_relic_worker import SCRIPT
from spireshift.engine_run import _run_inputs
from spireshift.engine_startup import _script_closure
from spireshift.engine_worker import worker_helpers
from spireshift.native_compatibility_contract import CONTRACT, checkpoint, local, verified
from spireshift.native_context_cache import CachedContextModel
from spireshift.neural_combat import _numpy
from spireshift.training_objective import load_training_score_spec

SOURCES = (
    "native_compatibility_contract.py",
    "native_compatibility_inputs.py",
    "native_compatibility.py",
)
ENTRY = "check-native-compatibility-v1.mjs"
WRAPPER = "scripts/check-native-compatibility-v1.sh"


def python_dependencies(root: Path) -> set[str]:
    """Pin the local import closure, including imports inside model/encoder functions."""
    pending = [f"spireshift.{n[:-3]}" for n in SOURCES]
    seen: set[str] = set()
    result = set()
    while pending:
        module = pending.pop()
        if module in seen or not module.startswith("spireshift"):
            continue
        seen.add(module)
        path = root / "src" / Path(*module.split("."))
        path = path.with_suffix(".py") if path.with_suffix(".py").exists() else path / "__init__.py"
        if not path.is_file():
            continue
        result.add(str(path.relative_to(root)))
        for item in ast.walk(ast.parse(path.read_text())):
            if isinstance(item, ast.ImportFrom) and item.module:
                pending.append(item.module)
            elif isinstance(item, ast.Import):
                pending.extend(alias.name for alias in item.names)
    return result


def check_sources(root: Path, sources: dict[str, str]) -> None:
    for name, digest in sources.items():
        if _sha_file(local(root, name)) != digest:
            raise ValueError(f"Compatibility evidence or code changed: {name}")


def load(root: Path, path: Path, overrides: tuple[str, ...] = ()) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    if (
        cfg.get("schema_version") != "native-checkpoint-compatibility-config-v1"
        or cfg.get("contract") != CONTRACT
        or cfg.get("stage") != "recorded_checkpoint_regression"
        or cfg.get("training_allowed") is not False
        or cfg.get("temperature") != 0.8
        or not str(cfg.get("workspace", "")).startswith("artifacts/native-compatibility/")
        or cfg.get("session_limits")
        != {
            "wall_seconds": 240,
            "cpu_seconds": 480,
            "resident_memory_bytes": 2000000000,
            "storage_bytes": 100000000,
        }
        or not 1 <= len(cfg.get("cases", [])) <= 8
        or len({c["key"] for c in cfg["cases"]}) != len(cfg["cases"])
        or not 1 <= len(overrides or cfg.get("checkpoints", [])) <= 8
    ):
        raise ValueError("Use the finite, public-only checkpoint compatibility recipe")
    sources = {str(path.relative_to(root)): _sha_file(path)}
    for section in ("implementation_sha256", "helpers_sha256", "policy_dependency_sha256"):
        for name, digest in cfg[section].items():
            if name in sources and sources[name] != digest:
                raise ValueError("Conflicting compatibility dependency identities")
            sources[name] = digest
    required_helpers = _script_closure(root / "scripts", {ENTRY})
    if set(cfg["implementation_sha256"]) != {f"src/spireshift/{n}" for n in SOURCES} or set(
        cfg["helpers_sha256"]
    ) != {f"scripts/{n}" for n in required_helpers}:
        raise ValueError("Bind the exact compatibility implementation and projection closure")
    if set(cfg["policy_dependency_sha256"]) != python_dependencies(root) - set(
        cfg["implementation_sha256"]
    ):
        raise ValueError("Bind every policy/feature/optimizer implementation used by the gate")
    check_sources(root, sources)
    if cfg["wrapper"]["path"] != WRAPPER:
        raise ValueError("Bind the versioned compatibility command wrapper")
    verified(root, cfg["wrapper"])
    sources[WRAPPER] = cfg["wrapper"]["sha256"]
    for ref in cfg["environment"].values():
        verified(root, ref)
        sources[ref["path"]] = ref["sha256"]
    env = cfg["environment"]
    q = load_engine_qualification_config(local(root, env["qualification"]["path"]))
    manifest = identified(local(root, env["manifest"]["path"]), "manifest_id")
    if (
        manifest["manifest_id"] != env["manifest"]["id"]
        or manifest["qualification_config_id"] != q.config_id
        or manifest["character"] != "Ironclad"
        or manifest["ascension"] != 8
        or manifest["profile"] != "native_benchmark_full_v1"
        or manifest["version"] != q.target["version"]
        or manifest["commit"] != q.target["commit"]
        or manifest["game_assembly_sha256"] != q.target["assembly_sha256"]
        or manifest["worker_script"] != SCRIPT
        or manifest["helpers_sha256"] != worker_helpers(root, SCRIPT)
    ):
        raise ValueError("Compatibility gate requires the exact current Ironclad/A8 environment")
    native = _run_inputs(q, local(root, env["native_inputs"]["path"]))
    # Report a stale environment label rather than silently migrating old models
    # or aborting before the useful, separately scoped saved-input diagnosis.
    environment_checks = {
        "manifest_input_config_id": manifest["input_config_id"],
        "verified_input_config_id": native["recipe"]["input_config_id"],
        "manifest_build_report_id": manifest["build_report_id"],
        "verified_build_report_id": native["inputs"]["build_report_id"],
        "passed": native["recipe"]["input_config_id"] == manifest["input_config_id"]
        and native["inputs"]["build_report_id"] == manifest["build_report_id"],
    }
    connector = load_connector_qualification_config(
        local(root, env["official_connector"]["path"]), q
    )
    _verify_toolchain(connector)
    score = load_training_score_spec(local(root, env["training_spec"]["path"]))
    if score.spec_id != env["training_spec"]["id"] or score.evaluation_objective.primary != (
        "terminal_victory"
    ):
        raise ValueError("Compatibility cannot change the full-run objective or credit score")
    refs = cfg["checkpoints"]
    if overrides:
        refs = [{"path": n, "sha256": _sha_file(local(root, n))} for n in overrides]
    models: dict[str, CachedContextModel] = {}
    states = []
    for ref in refs:
        model, state = checkpoint(root, ref, manifest["manifest_id"], score.spec_id)
        if state["state_id"] in models:
            raise ValueError("Do not count the same checkpoint twice")
        models[state["state_id"]] = model
        states.append(state)
        sources[state["path"]] = state["sha256"]
    for ref in cfg["protected_originals"]:
        verified(root, ref)
        sources[ref["path"]] = ref["sha256"]
    for case in cfg["cases"]:
        if case["scenario"] not in {"corruption", "temporary-stats"}:
            raise ValueError("Reference-bank projection has an undeclared scenario")
        for key in ("native", "official", "snapshots"):
            verified(root, case[key])
            sources[case[key]["path"]] = case[key]["sha256"]
        n = json.loads(local(root, case["native"]["path"]).read_text())
        s = json.loads(local(root, case["official"]["path"]).read_text())
        if (
            n["report_id"] != case["native"]["id"]
            or s["report_id"] != case["official"]["id"]
            or n["qualification_config_id"] != q.config_id
            or s["qualification_config_id"] != q.config_id
            or n["probe"]["runtime_identity"]["sts2_assembly_sha256"] != q.target["assembly_sha256"]
            or not all(v is True for v in n["checks"].values())
            or not all(v is True for v in s["checks"].values())
            or any(d["process"]["returncode"] != 0 or d["process"]["timed_out"] for d in (n, s))
        ):
            raise ValueError("Reference bank needs complete exact-game native and official records")
    binding = {
        "environment_id": manifest["manifest_id"],
        "qualification_id": q.config_id,
        "official_connector_id": connector.config_id,
        "verified_native_recipe_id": manifest_identifier(native["recipe"]),
        "verified_native_build_id": native["inputs"]["build_report_id"],
        "checkpoint_state_ids": sorted(models),
        "suite_id": manifest_identifier(cfg["cases"]),
        "dependencies_id": manifest_identifier(sources),
        "inference_runtime": {
            "python": sys.version,
            "numpy": str(_numpy().__version__),
            "node_binary_sha256": _sha_file(Path(cfg["node"])),
        },
    }
    return {
        "config": cfg,
        "models": models,
        "states": states,
        "sources": sources,
        "score": score,
        "binding": binding,
        "native_build_report_id": native["inputs"]["build_report_id"],
        "environment_checks": environment_checks,
    }


def project(root: Path, cfg: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    spec = {k: str(local(root, case[k]["path"])) for k in ("native", "official", "snapshots")}
    spec.update(key=case["key"], scenario=case["scenario"])
    done = subprocess.run(
        [cfg["node"], str(root / "scripts" / ENTRY)],
        input=json.dumps(spec),
        text=True,
        capture_output=True,
        check=False,
        timeout=25,
        cwd=root,
    )
    if done.returncode != 0:
        raise ValueError(f"Recorded native/official reconstruction failed: {done.stderr[-1500:]}")
    if len(done.stdout) > 10_000_000:
        raise ValueError("Compatibility projection exceeded its bounded output")
    result: dict[str, Any] = json.loads(done.stdout)
    return result
