"""Freeze the production learner, preserved originals and a separately labelled diagnostic."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.engine_worker import worker_helpers
from spireshift.native_context_journal import load_state
from spireshift.native_context_reuse import check_sources
from spireshift.native_delayed_data import ARMS, CONTRACT, FAMILIES, HORIZON
from spireshift.native_delayed_worker import SCRIPT
from spireshift.native_experience_inputs import migrate
from spireshift.native_policy_updates import SETTINGS
from spireshift.training_objective import load_training_score_spec

SOURCES = (
    "native_delayed_data.py",
    "native_delayed_collect.py",
    "native_delayed_worker.py",
    "native_delayed_learning.py",
    "native_delayed_evaluate.py",
    "native_delayed_inputs.py",
    "native_delayed_study.py",
    "native_delayed_execute.py",
    "native_policy_updates.py",
    "native_value_credit.py",
    "native_structured_policy.py",
    "native_structured_model.py",
    "native_action_context.py",
    "native_context_cache.py",
    "native_structured_state.py",
    "native_compact_training.py",
    "full_run_ppo_math.py",
)
ENTRIES = ("check-native-delayed-learning-v1.py", "check-native-delayed-learning-v1.sh")


def load(root: Path, path: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    control = cfg.get("stage") == "short_control"
    if (
        cfg.get("schema_version") != "native-delayed-learning-config-v1"
        or cfg.get("stage") not in {"short_control", "finite_delayed_diagnostic"}
        or cfg.get("contract") != CONTRACT
        or cfg.get("arms") != list(ARMS)
        or cfg.get("families") != list(FAMILIES)
        or cfg.get("maximum_actions") != HORIZON
        or cfg.get("episodes_per_round") != 32
        or cfg.get("rounds") != (4 if control else 128)
        or cfg.get("chunk_rounds") != (4 if control else 8)
        or cfg.get("learning") != SETTINGS
        or cfg.get("ordinary_PPO_eligible") is not False
        or cfg.get("session_limits")
        != {
            "wall_seconds": 240 if control else 900,
            "cpu_seconds": 480 if control else 1800,
            "resident_memory_bytes": 2000000000,
            "storage_bytes": 1000000000,
        }
        or cfg.get("implementation_sha256")
        != {n: _sha_file(root / "src/spireshift" / n) for n in SOURCES}
        or cfg.get("entry_sha256") != {n: _sha_file(root / "scripts" / n) for n in ENTRIES}
        or cfg.get("helpers_sha256") != worker_helpers(root, SCRIPT)
    ):
        raise ValueError(
            "Preserve the finite delayed tasks, production settings and pinned sources"
        )
    source_ref, report_ref = cfg["source_recipe"], cfg["protection_report"]
    source = json.loads((root / source_ref["path"]).read_text())
    report = identified(root / report_ref["path"])
    if (
        manifest_identifier(source) != source_ref["id"]
        or report["report_id"] != report_ref["id"]
        or report["config_id"] != source_ref["id"]
        or report["status"] != "native_experience_comparison_complete"
        or report["games_recorded"] != 832
        or report["failed_games"]
        or cfg["learning"] != source["learning"]
        or cfg["credit"] != source["credit"]
    ):
        raise ValueError("Bind the assessed completed comparison and unchanged production learner")
    sources = dict(report["sources"])
    sources[report_ref["path"]] = _sha_file(root / report_ref["path"])
    seeds = cfg["seeds"]
    fit, held = (2, 1) if control else (8, 4)
    if (
        len(seeds) != fit + held
        or len({s["id"] for s in seeds}) != len(seeds)
        or len({s["seed"] for s in seeds}) != len(seeds)
        or sum(s["partition"] == "fit" for s in seeds) != fit
        or sum(s["partition"] == "heldout" for s in seeds) != held
        or any(
            set(s) != {"id", "seed", "partition", "variant"}
            or type(s["id"]) is not int
            or s["id"] < 0
            or type(s["variant"]) is not int
            or s["variant"] not in (0, 1, 2)
            or s["partition"] not in {"fit", "heldout"}
            or not isinstance(s["seed"], str)
            or not re.fullmatch(r"[A-HJ-NP-Z0-9]+", s["seed"])
            for s in seeds
        )
        or not {0, 2} <= {s["variant"] for s in seeds if s["partition"] == "fit"}
    ):
        raise ValueError("Keep distinct fitting/held worlds and both native menu orders")
    historical = []
    for ref in [source["seed_manifest"], *source["freshness_exclusions"]]:
        historical.extend(json.loads((root / ref["path"]).read_text())["seeds"])
    from spireshift.native_structured_inputs import exclude_worlds

    exclude_worlds(seeds, historical)
    if {s["seed"] for s in seeds} & set(cfg["excluded_probe_and_control_seeds"]):
        raise ValueError("Exclude prototype/control worlds from this diagnostic")
    models, adams = {}, {}
    for player in source["players"]:
        if _sha_file(root / player["path"]) != player["sha256"]:
            raise ValueError("An original full player state changed")
        model, adam, sid = load_state(root / player["path"])
        if (
            sid != player["state_id"]
            or model.model_id != player["model_id"]
            or adam.steps != player["optimizer_steps"]
        ):
            raise ValueError("Preserve every original numerical weight, Adam moment and counter")
        models[player["numerical_seed"]] = migrate(model, source["environment_manifest"]["id"])
        adams[player["numerical_seed"]] = adam
    score = load_training_score_spec(root / source["training_spec"]["path"])
    if (
        score.spec_id != source["training_spec"]["id"]
        or score.evaluation_objective.primary != "terminal_victory"
    ):
        raise ValueError("Diagnostic subgoals never replace the full-run ObjectiveSpec")
    if not control:
        ref = cfg["control_report"]
        c = identified(root / ref["path"])
        cc = json.loads((root / c["recipe_path"]).read_text())
        if (
            c["report_id"] != ref["id"]
            or c["status"] != "delayed_control_complete"
            or not c["pipeline_control_passed"]
        ):
            raise ValueError(
                "Complete the separate production-path delayed integration control first"
            )
        if any(
            cfg[k] != cc[k]
            for k in (
                "implementation_sha256",
                "helpers_sha256",
                "entry_sha256",
                "source_recipe",
                "protection_report",
                "credit",
                "learning",
            )
        ):
            raise ValueError("The short control must qualify these exact diagnostic sources")
        exclude_worlds(seeds, cc["seeds"])
        check_sources(root, c["sources"])
        sources.update(c["sources"])
        sources[ref["path"]] = _sha_file(root / ref["path"])
    sources[str(path.relative_to(root))] = _sha_file(path)
    sources.update({f"src/spireshift/{n}": s for n, s in cfg["implementation_sha256"].items()})
    sources.update(
        {f"scripts/{n}": s for n, s in {**cfg["helpers_sha256"], **cfg["entry_sha256"]}.items()}
    )
    check_sources(root, sources)
    return {
        "config": cfg,
        "source": source,
        "score": score,
        "models": models,
        "adams": adams,
        "sources": sources,
    }


def plan(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = [{"key": f"initial-p{p}", "kind": "import", "player": p} for p in (2, 3)]
    tasks += [
        {
            "key": f"case-{s['id']}-{family.replace('_', '-')}",
            "kind": "collect",
            "seed": s,
            "family": family,
        }
        for s in cfg["seeds"]
        for family in FAMILIES
    ]
    states = {(p, arm): f"initial-p{p}" for p in (2, 3) for arm in ARMS}
    for start in range(1, cfg["rounds"] + 1, cfg["chunk_rounds"]):
        for p in (2, 3):
            for arm in ARMS:
                key = f"fit-p{p}-{arm}-r{start:03d}"
                tasks.append(
                    {
                        "key": key,
                        "kind": "fit",
                        "player": p,
                        "arm": arm,
                        "start_round": start,
                        "end_round": start + cfg["chunk_rounds"] - 1,
                        "state": states[p, arm],
                    }
                )
                states[p, arm] = key
    tasks += [
        {
            "key": f"evaluate-p{p}-{arm}",
            "kind": "evaluate",
            "player": p,
            "arm": arm,
            "state": states[p, arm],
        }
        for p in (2, 3)
        for arm in ARMS
    ]
    return tasks
