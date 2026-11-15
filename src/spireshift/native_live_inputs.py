"""Pinned shared-input environment and explicit unchanged numerical checkpoint imports."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_connector import _verify_toolchain, load_connector_qualification_config
from spireshift.engine_learning import identified
from spireshift.engine_profile import load_profile_policy, verify_benchmark_progress
from spireshift.engine_qualification import _sha_file, load_engine_qualification_config
from spireshift.engine_relic_worker import SCRIPT
from spireshift.engine_run import _run_inputs
from spireshift.engine_startup import _script_closure
from spireshift.engine_worker import worker_helpers
from spireshift.engine_working_app import load_working_app_policy
from spireshift.native_compatibility_contract import checkpoint, local, verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_live_policy import CONTRACT, import_checkpoint
from spireshift.training_objective import load_training_score_spec

SOURCES = (
    "native_live_inputs.py",
    "native_live_policy.py",
    "native_shared_transport.py",
    "native_official_session.py",
    "native_live_checkpoint.py",
)
ENTRIES = {"engine-shared-input-v1.mjs", "engine-live-checkpoint-v1.mjs"}
WRAPPERS = ("check-live-checkpoint-adapter-v1.sh", "compare-live-checkpoint-canary-v1.sh")


def dependencies(root: Path) -> set[str]:
    pending = [f"spireshift.{name[:-3]}" for name in SOURCES]
    seen: set[str] = set()
    files: set[str] = set()
    while pending:
        module = pending.pop()
        if module in seen or not module.startswith("spireshift"):
            continue
        seen.add(module)
        path = root / "src" / Path(*module.split("."))
        path = (
            path.with_suffix(".py") if path.with_suffix(".py").is_file() else path / "__init__.py"
        )
        if not path.is_file():
            continue
        files.add(str(path.relative_to(root)))
        for item in ast.walk(ast.parse(path.read_text())):
            if isinstance(item, ast.ImportFrom) and item.module:
                pending.append(item.module)
            elif isinstance(item, ast.Import):
                pending.extend(alias.name for alias in item.names)
    return files


def load(root: Path, path: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    control = cfg.get("stage") == "short_control"
    if (
        cfg.get("schema_version") != "native-live-checkpoint-config-v1"
        or cfg.get("stage") not in {"short_control", "bounded_live_checkpoint_canary"}
        or cfg.get("contract") != CONTRACT
        or cfg.get("training_allowed") is not False
        or not str(cfg.get("workspace", "")).startswith("artifacts/native-live-adapter/")
        or cfg.get("maximum_decisions") != (2 if control else 64)
        or cfg.get("maximum_case_wall_seconds") != (180 if control else 210)
        or cfg.get("session_limits")
        != {
            "wall_seconds": 240 if control else 900,
            "cpu_seconds": 480 if control else 1800,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 1000000000,
        }
        or len(cfg.get("cases", [])) != (1 if control else 4)
        or len({c["key"] for c in cfg["cases"]}) != len(cfg["cases"])
        or cfg.get("implementation_sha256")
        != {name: _sha_file(root / name) for name in sorted(dependencies(root))}
        or cfg.get("helpers_sha256")
        != {
            f"scripts/{name}": _sha_file(root / "scripts" / name)
            for name in sorted(_script_closure(root / "scripts", ENTRIES))
        }
        or cfg.get("entry_sha256")
        != {f"scripts/{name}": _sha_file(root / "scripts" / name) for name in WRAPPERS}
    ):
        raise ValueError("Use the pinned finite shared-input/checkpoint adapter recipe")
    sources = {
        str(path.relative_to(root)): _sha_file(path),
        **cfg["implementation_sha256"],
        **cfg["helpers_sha256"],
        **cfg["entry_sha256"],
    }
    for ref in cfg["inputs"].values():
        verified(root, ref)
        sources[ref["path"]] = ref["sha256"]
    q = load_engine_qualification_config(local(root, cfg["inputs"]["qualification"]["path"]))
    native = _run_inputs(q, local(root, cfg["inputs"]["native"]["path"]))
    env = identified(local(root, cfg["inputs"]["environment"]["path"]), "manifest_id")
    old = identified(local(root, cfg["inputs"]["parent_environment"]["path"]), "manifest_id")
    connector = load_connector_qualification_config(
        local(root, cfg["inputs"]["connector"]["path"]), q
    )
    _verify_toolchain(connector)
    app = load_working_app_policy(local(root, cfg["inputs"]["working_app"]["path"]), q)
    profile = load_profile_policy(local(root, cfg["inputs"]["profile_policy"]["path"]), q)
    progress = local(root, cfg["inputs"]["benchmark_progress"]["path"])
    verify_benchmark_progress(progress, profile)
    score = load_training_score_spec(local(root, cfg["inputs"]["score"]["path"]))
    helpers = worker_helpers(root, SCRIPT)
    if (
        env["parent_environment_id"] != old["manifest_id"]
        or env["qualification_config_id"] != q.config_id
        or env["version"] != q.target["version"]
        or env["commit"] != q.target["commit"]
        or env["game_assembly_sha256"] != q.target["assembly_sha256"]
        or env["input_config_id"] != native["recipe"]["input_config_id"]
        or env["build_report_id"] != native["inputs"]["build_report_id"]
        or env["worker_script"] != SCRIPT
        or env["helpers_sha256"] != helpers
        or env["shared_input_contract"] != CONTRACT
        or env["shared_input_helpers_sha256"]
        != {
            f"scripts/{name}": _sha_file(root / "scripts" / name)
            for name in sorted(_script_closure(root / "scripts", {"engine-shared-input-v1.mjs"}))
        }
        or env["official_connector_config_id"] != connector.config_id
        or env["profile"] != "native_benchmark_full_v1"
        or env["character"] != "Ironclad"
        or env["ascension"] != 8
        or score.evaluation_objective.primary != "terminal_victory"
        or score.evaluation_objective.whole_run_budget != 128
    ):
        raise ValueError("Shared-input environment is not bound to both exact execution hosts")
    refs = cfg["players"]
    if set(refs) != {"2", "3"}:
        raise ValueError("Preserve both fixed initializers; do not select a player from results")
    for ref in [*refs.values(), *cfg["protected_originals"]]:
        verified(root, ref)
        sources[ref["path"]] = ref["sha256"]
    for ref in refs.values():
        checkpoint(root, ref, old["manifest_id"], score.spec_id)
    for case in cfg["cases"]:
        if (
            str(case["player"]) not in refs
            or not case["seed"].isalnum()
            or not case["seed"].isupper()
        ):
            raise ValueError("Every live case needs a fixed player and explicit native seed")
    if len({(c["player"], c["seed"]) for c in cfg["cases"]}) != len(cfg["cases"]):
        raise ValueError("Do not replay the same player/world in this finite canary")
    if not control:
        ref = cfg["control_receipt"]
        report = identified(verified(root, ref))
        if (
            report["report_id"] != ref["id"]
            or report["status"] != "live_checkpoint_delivery_control_pass"
            or report["environment_id"] != env["manifest_id"]
            or report["implementation_id"] != manifest_identifier(cfg["implementation_sha256"])
            or report["helpers_id"] != manifest_identifier(cfg["helpers_sha256"])
        ):
            raise ValueError(
                "Complete the exact short live adapter control before the owner canary"
            )
        check_sources(root, report["sources"])
        sources[ref["path"]] = ref["sha256"]
        if {c["seed"] for c in cfg["cases"]} & set(report["seeds"]):
            raise ValueError("Use fresh canary worlds, never retry a control seed")
    return {
        "config": cfg,
        "sources": sources,
        "qualification": q,
        "native": native,
        "environment": env,
        "connector": connector,
        "working_app": app,
        "profile_policy": profile,
        "progress": progress,
        "score": score,
        "native_helpers": helpers,
    }


def prepare(root: Path, context: dict[str, Any]) -> dict[int, Any]:
    cfg = context["config"]
    directory = local(root, cfg["workspace"]) / "imports"
    directory.mkdir(parents=True, exist_ok=True)
    result = {}
    for player, ref in cfg["players"].items():
        model, adam, receipt = import_checkpoint(
            root, ref, context["environment"], context["score"], directory / f"player-{player}.json"
        )
        result[int(player)] = model, adam, receipt
    check_sources(root, context["sources"])
    return result
