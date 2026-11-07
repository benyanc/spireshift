"""Bind the unchanged engine/parents, new whole-world bank and finite search work."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.engine_relic_worker import SCRIPT
from spireshift.engine_worker import worker_helpers
from spireshift.native_context_reuse import check_sources
from spireshift.native_coordinated_data import ARMS, CONTRACT, ENTRIES, LIMITS
from spireshift.native_coordinated_roots import base

SOURCES = (
    "native_coordinated_data.py",
    "native_coordinated_roots.py",
    "native_coordinated_branch.py",
    "native_coordinated_inputs.py",
    "native_coordinated_teacher.py",
    "native_coordinated_study.py",
)
ENTRYPATHS = ("compare-coordinated-teacher-v2.py", "compare-coordinated-teacher-v2.sh")


def load(root: Path, path: Path, *, require_control: bool = True) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    control = cfg.get("stage") == "qualification_control"
    if (
        cfg.get("schema_version") != "native-coordinated-teacher-config-v2"
        or cfg.get("stage") not in {"qualification_control", "bounded_comparison"}
        or cfg.get("contract") != CONTRACT
        or cfg.get("arms") != list(ARMS)
        or cfg.get("entries") != list(ENTRIES)
        or cfg.get("limits") != LIMITS
        or cfg.get("lineages") != (1 if control else 4)
        or cfg.get("session_limits")
        != {
            "wall_seconds": 900,
            "cpu_seconds": 1800,
            "resident_memory_bytes": 2000000000,
            "storage_bytes": 3000000000,
        }
        or cfg.get("implementation_sha256")
        != {n: _sha_file(root / "src/spireshift" / n) for n in SOURCES}
        or cfg.get("entry_sha256") != {n: _sha_file(root / "scripts" / n) for n in ENTRYPATHS}
        or cfg.get("helpers_sha256") != worker_helpers(root, SCRIPT)
    ):
        raise ValueError("Preserve the finite 2x2 search comparison and pinned implementation")
    context = base(root)
    bank_path = cfg["root_bank_path"]
    if bank_path != "artifacts/native-coordinated/roots-v2/report.json":
        raise ValueError("Use fresh v2 controls; preserve the interrupted v1 world")
    bank = identified(root / bank_path)
    if bank["report_id"] != cfg["root_bank_id"] or cfg["node"] != context["source"]["node"]:
        raise ValueError("Bind the prepared fresh first-turn TRAIN roots and qualified runtime")
    check_sources(root, bank["sources"])
    roots = [r for r in bank["roots"] if (r["pool"] == "control") == control]
    if (
        len(roots) != (2 if control else 8)
        or len({r["world"] for r in roots}) != len(roots)
        or {r["player"] for r in roots} != {2, 3}
        or (not control and sum(r["partition"] == "fit" for r in roots) != 4)
    ):
        raise ValueError("Keep the control/fit/held world split and both fixed parents")
    for r in bank["roots"]:
        if r["root_id"] != manifest_identifier({k: v for k, v in r.items() if k != "root_id"}):
            raise ValueError("A world, root, partition or observed prefix changed")
    context["sources"].update(bank["sources"])
    context["sources"][bank_path] = _sha_file(root / bank_path)
    if not control and require_control:
        c = json.loads((root / cfg["control_recipe"]).read_text())
        if any(
            c[k] != cfg[k]
            for k in ("implementation_sha256", "entry_sha256", "helpers_sha256", "root_bank_id")
        ):
            raise ValueError("Control must qualify this exact search implementation")
        name = c["workspace"] + "/report.json"
        report = identified(root / name)
        if (
            report["status"] != "coordinated_teacher_complete"
            or not report["control_checks_passed"]
            or report["config_id"] != manifest_identifier(c)
        ):
            raise ValueError("Complete the short genuine coordinated/native replay control first")
        check_sources(root, report["sources"])
        context["sources"].update(report["sources"])
        context["sources"][name] = _sha_file(root / name)
    context["sources"].update(
        {f"src/spireshift/{n}": s for n, s in cfg["implementation_sha256"].items()}
    )
    context["sources"].update(
        {f"scripts/{n}": s for n, s in {**cfg["entry_sha256"], **cfg["helpers_sha256"]}.items()}
    )
    context["sources"][str(path.relative_to(root))] = _sha_file(path)
    context.update(config=cfg, roots=roots)
    return context


def snapshot(root: Path, cfg: dict[str, Any], workspace: Path) -> dict[str, str]:
    folder = workspace / "python-at-launch"
    folder.mkdir(exist_ok=True)
    sources = {}
    for name, sha in cfg["implementation_sha256"].items():
        target = folder / name
        if not target.exists():
            target.write_bytes((root / "src/spireshift" / name).read_bytes())
        if _sha_file(target) != sha:
            raise ValueError("Preserve original coordinated-search implementation snapshots")
        sources[str(target.relative_to(root))] = sha
    return sources
