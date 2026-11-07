"""Admission for fresh TRAIN worlds, exact saved players and a bounded teacher only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_combat_behavior_config import SOURCES as PRIOR_SOURCES
from spireshift.native_combat_behavior_config import load as load_behavior
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_reuse import check_sources
from spireshift.native_greedy_turn_policy import CONTRACT, ROOT_SELECTION
from spireshift.training_objective import TrainingScoreSpec

SOURCES = tuple(
    sorted(
        set(
            (
                *PRIOR_SOURCES,
                "native_greedy_turn_policy.py",
                "native_greedy_turn_data.py",
                "native_greedy_turn_config.py",
                "native_greedy_turn_branch.py",
                "native_greedy_turn_teacher.py",
                "native_greedy_turn_audit.py",
            )
        )
    )
)
ENTRIES = ("native-greedy-turn-teacher-v1.py", "collect-native-greedy-turn-teacher-v1.sh")
SHARED = (
    "behavior_recipe",
    "behavior_report",
    "policy_contract",
    "root_selection",
    "temperature",
    "proposal_temperature",
    "maximum_decisions",
    "episode_wall_seconds",
    "information_scope",
    "ordinary_PPO_eligible",
    "implementation_sha256",
    "entry_sha256",
    "qualification",
    "qualification_id",
    "native_inputs",
    "helpers_sha256",
    "node",
    "freshness_exclusions",
    "proposal_cpu_cap",
    "proposal_call_cpu_cap",
    "candidate_selection",
    "cost_accounting",
)


def load(
    root: Path, path: Path
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    dict[int, CachedContextModel],
    TrainingScoreSpec,
    dict[str, str],
]:
    cfg = json.loads(path.read_text())
    control = cfg.get("stage") == "short_control"
    if (
        cfg.get("schema_version") != "native-greedy-turn-teacher-config-v1"
        or cfg.get("stage") not in {"short_control", "fresh_train_teacher"}
        or cfg.get("policy_contract") != CONTRACT
        or cfg.get("root_selection") != ROOT_SELECTION
        or cfg.get("temperature") != 0.8
        or cfg.get("proposal_temperature") != 1.2
        or cfg.get("maximum_decisions") != 4096
        or cfg.get("episode_wall_seconds") != 120
        or cfg.get("repeats") != (2 if control else 8)
        or cfg.get("information_scope")
        != "public_student_inputs_original_fixed_hidden_world_teacher"
        or cfg.get("ordinary_PPO_eligible") is not False
        or cfg.get("proposal_cpu_cap") != 64.0
        or cfg.get("proposal_call_cpu_cap") != 32.0
        or cfg.get("candidate_selection") != "all_first_moves_exact_trace_dedup_no_outcome_filter"
        or cfg.get("cost_accounting")
        != "all_proposal_episode_CPU_to_each_alternative_reference_zero_no_amortization"
        or cfg.get("implementation_sha256")
        != {n: _sha_file(root / "src/spireshift" / n) for n in SOURCES}
        or cfg.get("entry_sha256") != {n: _sha_file(root / "scripts" / n) for n in ENTRIES}
        or cfg.get("session_limits")
        != {
            "wall_seconds": 240 if control else 900,
            "cpu_seconds": 480 if control else 1800,
            "resident_memory_bytes": 2000000000,
            "storage_bytes": 1000000000 if control else 4000000000,
        }
    ):
        raise ValueError(
            "Freeze the public greedy-turn teacher, complete legal menus and finite budgets"
        )
    base_path = root / cfg["behavior_recipe"]["path"]
    if _sha_file(base_path) != cfg["behavior_recipe"]["sha256"]:
        raise ValueError("Preserve the qualified public greedy behavior and exact original players")
    base, _, models, score, sources = load_behavior(root, base_path)
    if base["stage"] != "fresh_game_comparison" or any(
        cfg[k] != base[k]
        for k in ("qualification", "qualification_id", "native_inputs", "node", "helpers_sha256")
    ):
        raise ValueError("Preserve qualified Ironclad/A8 native inputs, helpers and runtimes")
    sources[str(path.relative_to(root))] = _sha_file(path)
    sources.update({f"src/spireshift/{n}": s for n, s in cfg["implementation_sha256"].items()})
    sources.update({f"scripts/{n}": s for n, s in cfg["entry_sha256"].items()})

    def ref(name: str, key: str = "report_id") -> dict[str, Any]:
        value = identified(root / cfg[name]["path"], key)
        if value[key] != cfg[name]["id"]:
            raise ValueError(f"A frozen greedy-turn reference changed: {name}")
        sources[cfg[name]["path"]] = _sha_file(root / cfg[name]["path"])
        return value

    passed = ref("behavior_report")
    if (
        passed["config_id"] != manifest_identifier(base)
        or passed["status"] != "native_combat_behavior_complete"
        or passed["failed_games"]
        or passed["completed_units"] != 256
        or not passed["noncombat_matching"]["valid"]
        or not passed["full_states_unchanged"]
        or not all(passed["checks"].values())
    ):
        raise ValueError("Require the completed clean fresh-world greedy combat comparison")
    check_sources(root, passed["sources"])
    sources.update(passed["sources"])
    expected = [
        *base["historical_seed_manifests"],
        *base["excluded_seed_manifests"],
        base["seed_manifest"],
    ]
    expected = list({r["path"]: r for r in expected}.values())
    if cfg["freshness_exclusions"] != expected:
        raise ValueError(
            "Retain every prior TRAIN, development, confirmation and control seed exclusion"
        )
    manifest = ref("seed_manifest", "manifest_id")
    seeds = manifest["seeds"]
    if (
        manifest["schema_version"] != "native-greedy-turn-seeds-v1"
        or manifest["environment_id"] != models[2].actor.environment_id
        or manifest["partition"] != ("control" if control else "train")
        or len(seeds) != (2 if control else 8)
        or any(
            set(s) != {"id", "seed", "numerical_seed"}
            or type(s["id"]) is not int
            or type(s["numerical_seed"]) is not int
            or not isinstance(s["seed"], str)
            or not s["seed"]
            or s["numerical_seed"] != (2 + i % 2)
            for i, s in enumerate(seeds)
        )
        or len({s["id"] for s in seeds}) != len(seeds)
        or len({s["seed"].upper() for s in seeds}) != len(seeds)
    ):
        raise ValueError(
            "Freeze distinct fresh worlds, alternating both players, without replacement"
        )
    excluded = [*expected, *cfg["excluded_seed_manifests"]]
    for old_ref in excluded:
        old = identified(root / old_ref["path"], "manifest_id")
        if (
            old["manifest_id"] != old_ref["id"]
            or {s["id"] for s in seeds} & {s["id"] for s in old["seeds"]}
            or {s["seed"].upper() for s in seeds} & {s["seed"].upper() for s in old["seeds"]}
        ):
            raise ValueError("Fresh teacher worlds overlap a previously reserved game seed")
        sources[old_ref["path"]] = _sha_file(root / old_ref["path"])
    if not control:
        check, audited = ref("control_report"), ref("control_audit")
        previous = json.loads((root / check["recipe_path"]).read_text())
        if (
            previous["stage"] != "short_control"
            or any(cfg[k] != previous[k] for k in SHARED)
            or check["status"] != "native_greedy_turn_teacher_complete"
            or check["failed_branches"]
            or check["unavailable_source_worlds"]
            or check["blocked_source_roots"]
            or check["completed_units"] != 16
            or check["completed_source_comparisons"] != 2
            or not check["duplicate_public_traces_identical"]
            or not check["noncombat_matching"]["valid"]
            or audited["source_report_id"] != check["report_id"]
            or audited["auditor_sha256"]
            != cfg["implementation_sha256"]["native_greedy_turn_audit.py"]
            or audited["branch_receipts_verified"] != 16
            or not audited["all_choices_and_root_selection_reconstructed"]
            or previous["seed_manifest"] not in cfg["excluded_seed_manifests"]
        ):
            raise ValueError(
                "Matching native repeat and full saved-choice teacher controls must pass"
            )
        check_sources(root, check["sources"])
        sources.update(check["sources"])
        sources[check["recipe_path"]] = _sha_file(root / check["recipe_path"])
    return cfg, seeds, models, score, sources
