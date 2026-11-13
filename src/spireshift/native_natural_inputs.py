"""Freeze natural teacher ownership, exact warm states and finite comparison budgets."""

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
from spireshift.native_natural_data import CONTRACT, LEARNING, LIMITS
from spireshift.native_natural_roots import BANK, base
from spireshift.native_structured_inputs import exclude_worlds

SOURCES = (
    "native_natural_data.py",
    "native_natural_roots.py",
    "native_natural_inputs.py",
    "native_natural_audit.py",
    "native_natural_branch.py",
    "native_natural_teacher.py",
    "native_natural_learning.py",
    "native_natural_curriculum.py",
    "native_natural_study.py",
    "native_conditional_control.py",
    "native_experience_game.py",
    "native_structured_policy.py",
    "native_structured_model.py",
    "full_run_ppo_math.py",
)
ENTRIES = (
    "test-natural-combat-curriculum-v1.py",
    "test-natural-combat-curriculum-v1.sh",
    "verify-selection-cursor-v1.mjs",
)


def load(root: Path, recipe: Path, *, require_control: bool = True) -> dict[str, Any]:
    cfg = json.loads(recipe.read_text())
    control = cfg.get("stage") == "short_control"
    if (
        cfg.get("schema_version") != "natural-combat-curriculum-config-v1"
        or cfg.get("stage") not in {"short_control", "natural_multiturn_test"}
        or cfg.get("contract") != CONTRACT
        or cfg.get("limits") != LIMITS
        or cfg.get("learning") != {**LEARNING, "epochs": 2 if control else 16}
        or cfg.get("maximum_mutations") != (4 if control else 16)
        or cfg.get("session_limits")
        != {
            "wall_seconds": 240 if control else 900,
            "cpu_seconds": 480 if control else 1800,
            "resident_memory_bytes": 2000000000,
            "storage_bytes": 3000000000,
        }
        or cfg.get("implementation_sha256")
        != {n: _sha_file(root / "src/spireshift" / n) for n in SOURCES}
        or cfg.get("entry_sha256") != {n: _sha_file(root / "scripts" / n) for n in ENTRIES}
        or cfg.get("helpers_sha256") != worker_helpers(root, SCRIPT)
    ):
        raise ValueError("Preserve the finite natural teacher/CE curriculum and pinned sources")
    context = base(root)
    source = context["source"]
    if cfg["node"] != source["node"]:
        raise ValueError("Use the already qualified Node runtime")
    bank = identified(root / BANK)
    if (
        bank["report_id"] != cfg["root_bank_id"]
        or bank["source_environment"] != source["environment_manifest"]
    ):
        raise ValueError("Only exact repaired TRAIN roots may enter this curriculum")
    check_sources(root, bank["sources"])
    all_roots = bank["roots"]
    for r in all_roots:
        if r["root_id"] != manifest_identifier({k: v for k, v in r.items() if k != "root_id"}):
            raise ValueError("Natural source root, world, partition or prefix identity changed")
    roots = [dict(r) for r in all_roots if (r["pool"] == "control") == control]
    if (
        len(roots) != (2 if control else 12)
        or len({r["world"] for r in roots}) != len(roots)
        or sum(r["partition"] == "fit" for r in roots) != (1 if control else 8)
    ):
        raise ValueError("Keep whole native worlds separate in control, fit and held-out sets")
    seeds = cfg["evaluation_seeds"]
    seed_ref = cfg["seed_manifest"]
    seed_manifest = identified(root / seed_ref["path"], "manifest_id")
    if (
        len(seeds) != (1 if control else 32)
        or len({s["id"] for s in seeds}) != len(seeds)
        or len({s["seed"] for s in seeds}) != len(seeds)
        or seed_manifest["manifest_id"] != seed_ref["id"]
        or seed_manifest["seeds"] != seeds
        or seed_manifest["environment_id"] != source["environment_manifest"]["id"]
        or any(
            set(s) != {"id", "seed", "partition"}
            or type(s["id"]) is not int
            or s["partition"] != "development"
            or not isinstance(s["seed"], str)
            for s in seeds
        )
    ):
        raise ValueError("Keep the finite fresh full-game panel independent")
    exclusions = [source["seed_manifest"], *source["freshness_exclusions"]]
    for ref in exclusions:
        exclude_worlds(seeds, json.loads((root / ref["path"]).read_text())["seeds"])
    exclude_worlds(seeds, [{"id": r["seed_id"], "seed": r["world"]} for r in all_roots])
    context["sources"].update(bank["sources"])
    context["sources"][BANK] = _sha_file(root / BANK)
    context["sources"][seed_ref["path"]] = _sha_file(root / seed_ref["path"])
    if not control and require_control:
        cpath = root / cfg["control_recipe"]
        c = json.loads(cpath.read_text())
        for k in ("implementation_sha256", "entry_sha256", "helpers_sha256", "root_bank_id"):
            if c[k] != cfg[k]:
                raise ValueError("The short control must qualify this exact implementation")
        exclude_worlds(seeds, c["evaluation_seeds"])
        report_path = root / c["workspace"] / "curriculum/report.json"
        check = identified(report_path)
        if check["status"] != "natural_curriculum_complete" or not check["control_checks_passed"]:
            raise ValueError(
                "Complete the short native teacher/curriculum integration control first"
            )
        check_sources(root, check["sources"])
        context["sources"].update(check["sources"])
        context["sources"][str(report_path.relative_to(root))] = _sha_file(report_path)
    context["sources"].update(
        {f"src/spireshift/{n}": s for n, s in cfg["implementation_sha256"].items()}
    )
    context["sources"].update(
        {f"scripts/{n}": s for n, s in {**cfg["entry_sha256"], **cfg["helpers_sha256"]}.items()}
    )
    context["sources"][str(recipe.relative_to(root))] = _sha_file(recipe)
    context.update(config=cfg, roots=roots)
    return context


def snapshot(root: Path, cfg: dict[str, Any], workspace: Path) -> dict[str, str]:
    """Keep small Python sources for old/failed receipts, never another game app."""
    target = workspace / "python-at-launch"
    target.mkdir(exist_ok=True)
    sealed = {}
    for name, sha in cfg["implementation_sha256"].items():
        path = target / name
        if not path.exists():
            path.write_bytes((root / "src/spireshift" / name).read_bytes())
        if _sha_file(path) != sha:
            raise ValueError("Preserve the original Python implementation snapshot")
        sealed[str(path.relative_to(root))] = sha
    return sealed
