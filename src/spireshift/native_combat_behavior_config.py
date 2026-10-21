"""Freeze both players, native admission, genuinely fresh seeds and the sole treatment."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.engine_selection_worker import SCRIPT
from spireshift.engine_worker import worker_helpers
from spireshift.native_combat_behavior_policy import ARMS, CONTRACT, RNG, TEMPERATURE
from spireshift.native_combat_planning_config import SOURCES as PRIOR_SOURCES
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import load_state
from spireshift.native_context_reuse import check_sources
from spireshift.training_objective import TrainingScoreSpec, load_training_score_spec

SOURCES = tuple(
    sorted(
        set(
            (
                *PRIOR_SOURCES,
                "native_combat_behavior_policy.py",
                "native_combat_behavior_data.py",
                "native_combat_behavior_config.py",
                "native_combat_behavior_game.py",
                "native_combat_behavior.py",
            )
        )
    )
)
ENTRIES = (
    "native-combat-behavior-v1.py",
    "compare-native-combat-behavior-v1.sh",
    "verify-selection-cursor-v1.mjs",
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
        cfg.get("schema_version") != "native-combat-behavior-config-v1"
        or cfg.get("stage") not in {"short_control", "fresh_game_comparison"}
        or cfg.get("policy_contract") != CONTRACT
        or cfg.get("rng_contract") != RNG
        or cfg.get("arms") != list(ARMS)
        or cfg.get("temperature") != TEMPERATURE
        or cfg.get("information_scope") != "current_public_state_only_no_search"
        or cfg.get("ordinary_PPO_eligible") is not False
        or cfg.get("episode_wall_seconds") != 120
        or cfg.get("maximum_decisions") != 4096
        or cfg.get("implementation_sha256")
        != {n: _sha_file(root / "src/spireshift" / n) for n in SOURCES}
        or cfg.get("entry_sha256") != {n: _sha_file(root / "scripts" / n) for n in ENTRIES}
        or cfg.get("helpers_sha256") != worker_helpers(root, SCRIPT)
        or cfg.get("session_limits")
        != {
            "wall_seconds": 240 if control else 900,
            "cpu_seconds": 480 if control else 1800,
            "resident_memory_bytes": 2000000000,
            "storage_bytes": 1000000000 if control else 4000000000,
        }
    ):
        raise ValueError(
            "Freeze combat treatment, matched noncombat behavior, sources and finite caps"
        )
    sources = {str(path.relative_to(root)): _sha_file(path)}
    sources.update({f"src/spireshift/{n}": s for n, s in cfg["implementation_sha256"].items()})
    sources.update({f"scripts/{n}": s for n, s in cfg["entry_sha256"].items()})

    def ref(name: str, key: str = "report_id") -> dict[str, Any]:
        value = identified(root / cfg[name]["path"], key)
        if value[key] != cfg[name]["id"]:
            raise ValueError(f"Frozen combat comparison reference differs: {name}")
        sources[cfg[name]["path"]] = _sha_file(root / cfg[name]["path"])
        return value

    prior = ref("qualified_native_control")
    old = json.loads((root / prior["recipe_path"]).read_text())
    if (
        prior["status"] != "native_bounded_combat_comparison_complete"
        or prior["failed_branches"]
        or prior["skipped_branches"]
        or not prior["baseline_control_traces_match"]
        or not prior["duplicate_selected_traces_match"]
        or any(
            old[k] != cfg[k]
            for k in (
                "qualification",
                "qualification_id",
                "node",
                "native_inputs",
                "helpers_sha256",
            )
        )
    ):
        raise ValueError(
            "Keep the already qualified native bridge and immutable working-file policy"
        )
    check_sources(root, prior["sources"])
    sources.update(prior["sources"])
    sources[prior["recipe_path"]] = _sha_file(root / prior["recipe_path"])
    corpus = ref("players_source")
    environment = ref("environment_manifest", "manifest_id")
    score = load_training_score_spec(root / cfg["training_spec"]["path"])
    sources[cfg["training_spec"]["path"]] = _sha_file(root / cfg["training_spec"]["path"])
    if (
        score.spec_id != cfg["training_spec"]["id"]
        or corpus["training_spec"] != cfg["training_spec"]
        or corpus["environment_manifest"] != cfg["environment_manifest"]
        or environment["ascension"] != 8
        or environment["character"] != "Ironclad"
        or environment["version"] != "v0.111.0"
        or environment["commit"] != "41cef1ea"
        or score.evaluation_objective.whole_run_budget != 128
    ):
        raise ValueError(
            "Do not change Ironclad/A8, native version or whole-run victory/CPU objective"
        )
    models = {}
    if [p["numerical_seed"] for p in cfg["players"]] != [2, 3]:
        raise ValueError("Keep both original players in every comparison")
    original = {p["numerical_seed"]: p for p in corpus["models"]}
    for player in cfg["players"]:
        model, adam, state_id = load_state(root / player["path"])
        expected = original[player["numerical_seed"]]
        if (
            _sha_file(root / player["path"]) != player["sha256"]
            or state_id != player["state_id"]
            or model.model_id != player["model_id"]
            or adam.steps != player["optimizer_steps"]
            or player["path"] != expected["state_path"]
            or any(player[k] != expected[k] for k in ("state_id", "model_id", "optimizer_steps"))
            or model.actor.environment_id != environment["manifest_id"]
        ):
            raise ValueError("Preserve both exact full weights and every Adam moment/counter")
        sources[player["path"]] = player["sha256"]
        models[player["numerical_seed"]] = model
    manifest = ref("seed_manifest", "manifest_id")
    seeds = manifest["seeds"]
    if (
        manifest["schema_version"] != "native-combat-behavior-seeds-v1"
        or manifest["environment_id"] != environment["manifest_id"]
        or manifest["partition"] != ("control" if control else "development")
        or len(seeds) != (2 if control else 64)
        or any(
            set(s) != {"id", "seed"}
            or type(s["id"]) is not int
            or not isinstance(s["seed"], str)
            or not s["seed"]
            for s in seeds
        )
        or len({s["id"] for s in seeds}) != len(seeds)
        or len({s["seed"].upper() for s in seeds}) != len(seeds)
    ):
        raise ValueError(
            "Freeze distinct fresh complete-game seeds, shared across both fixed players"
        )
    historical = cfg["historical_seed_manifests"]
    recorded_seed_files = {
        n for n in prior["sources"] if n.startswith("manifests/splits/") and "native" in n
    }
    if not historical or not recorded_seed_files.issubset({r["path"] for r in historical}):
        raise ValueError("Retain the historical native seed exclusions")
    for excluded in [*historical, *cfg["excluded_seed_manifests"]]:
        other = identified(root / excluded["path"], "manifest_id")
        if other["manifest_id"] != excluded["id"]:
            raise ValueError("A prior seed exclusion changed")
        old_seeds = other["seeds"]
        if {s["id"] for s in seeds} & {s["id"] for s in old_seeds} or {
            s["seed"].upper() for s in seeds
        } & {s["seed"].upper() for s in old_seeds}:
            raise ValueError("Fresh comparison overlaps previously reserved or control seeds")
        sources[excluded["path"]] = _sha_file(root / excluded["path"])
    if not control:
        passed, audited = ref("control_report"), ref("control_audit")
        previous = json.loads((root / passed["recipe_path"]).read_text())
        shared = (
            "players",
            "players_source",
            "environment_manifest",
            "training_spec",
            "qualified_native_control",
            "qualification",
            "qualification_id",
            "native_inputs",
            "node",
            "policy_contract",
            "rng_contract",
            "arms",
            "temperature",
            "maximum_decisions",
            "episode_wall_seconds",
            "implementation_sha256",
            "helpers_sha256",
            "entry_sha256",
            "information_scope",
            "ordinary_PPO_eligible",
            "historical_seed_manifests",
        )
        if (
            passed["status"] != "native_combat_behavior_complete"
            or passed["failed_games"]
            or not passed["duplicate_traces_match"]
            or passed["completed_units"] != 12
            or not passed["noncombat_matching"]["valid"]
            or any(cfg[k] != previous[k] for k in shared)
            or previous["stage"] != "short_control"
            or audited["source_report_id"] != passed["report_id"]
            or audited["auditor_sha256"]
            != cfg["implementation_sha256"]["native_combat_behavior_game.py"]
            or audited["episodes_reconstructed"] != 12
            or not audited["all_choices_reconstructed"]
        ):
            raise ValueError(
                "Matching native repeat/matched-noncombat and saved-inference controls must pass"
            )
        if previous["seed_manifest"] not in cfg["excluded_seed_manifests"]:
            raise ValueError("Fresh development games must also exclude the new control seeds")
        check_sources(root, passed["sources"])
        sources.update(passed["sources"])
        sources[passed["recipe_path"]] = _sha_file(root / passed["recipe_path"])
    return cfg, seeds, models, score, sources
