"""Finite actual-engine tactical cases, explicitly privileged and never full-run PPO.

The two diagnostic goals are finish this encounter with the first move, and survive
one advertised enemy turn with End Turn as the fixed continuation. Native branches
define the answers. Unplayed actions are never assigned guessed damage/HP labels.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_neural import validate_public_input
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_reuse import check_sources
from spireshift.native_policy_trial_inputs import load as load_comparison
from spireshift.native_tactical_worker import SCRIPT, TacticalWorker

FAMILIES = ("finish_combat", "survive_turn")
SOURCES = (
    "native_tactical_worker.py",
    "native_tactical_cases.py",
    "native_tactical_learning.py",
    "native_tactical_study.py",
    "native_conditional_control.py",
)


def tasks(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"key": f"case-{seed['id']}-{family.replace('_', '-')}", "seed": seed, "family": family}
        for seed in cfg["seeds"]
        for family in FAMILIES
    ]


def load(root: Path, path: Path) -> dict[str, Any]:
    from spireshift.engine_learning import identified
    from spireshift.engine_worker import worker_helpers

    cfg = json.loads(path.read_text())
    if (
        cfg["schema_version"] != "native-tactical-learning-config-v1"
        or cfg["stage"] not in {"short_control", "finite_diagnostic"}
        or cfg["families"] != list(FAMILIES)
        or cfg["rounds"] != (8 if cfg["stage"] == "short_control" else 256)
        or cfg["sampled_choices_per_round"] != 64
        or cfg["maximum_actions_per_branch"] != 2
        or cfg["session_wall_seconds"] != (240 if cfg["stage"] == "short_control" else 900)
        or cfg["ordinary_PPO_eligible"] is not False
        or cfg["information_scope"] != "privileged_native_tactical_diagnostic_public_actor_inputs"
    ):
        raise ValueError("Preserve the finite diagnostic goals, schedule and information boundary")
    if cfg["implementation_sha256"] != {
        n: _sha_file(root / "src/spireshift" / n) for n in SOURCES
    } or cfg["helpers_sha256"] != worker_helpers(root, SCRIPT):
        raise ValueError("Tactical implementation or native helpers changed")
    context = load_comparison(root, root / cfg["comparison_recipe"])
    assessment = identified(root / cfg["comparison_assessment"]["path"])
    if (
        assessment["report_id"] != cfg["comparison_assessment"]["id"]
        or not assessment["summary_reconstructed_from_sealed_units"]
        or not assessment["decision"]["complete_clean_comparison"]
    ):
        raise ValueError("Assess the completed prepared comparison before this follow-up")
    check_sources(root, assessment["sources"])
    seeds = cfg["seeds"]
    fit = 1 if cfg["stage"] == "short_control" else 24
    held = 1 if cfg["stage"] == "short_control" else 8
    if (
        len(seeds) != fit + held
        or sum(s["partition"] == "fit" for s in seeds) != fit
        or sum(s["partition"] == "heldout" for s in seeds) != held
        or len({s["id"] for s in seeds}) != len(seeds)
        or len({s["seed"] for s in seeds}) != len(seeds)
        or any(s["partition"] not in {"fit", "heldout"} for s in seeds)
    ):
        raise ValueError("Tactical fitting and held-out complete seeds must be disjoint")
    excluded = {s["seed"] for s in context["seeds"]}
    for ref in context["config"]["freshness_exclusions"]:
        excluded.update(s["seed"] for s in json.loads((root / ref["path"]).read_text())["seeds"])
    excluded.update(cfg["excluded_probe_and_control_seeds"])
    if {s["seed"] for s in seeds} & excluded:
        raise ValueError("Do not reuse old training, evaluation, probe or control seeds")
    if cfg["stage"] == "finite_diagnostic":
        ref = cfg["control_report"]
        control = identified(root / ref["path"])
        if control["report_id"] != ref["id"] or control["status"] != "tactical_control_complete":
            raise ValueError("Complete the separate short native/control pipeline first")
        check_sources(root, control["sources"])
    return {"config": cfg, "comparison": context}


def outcome(family: str, root: dict[str, Any], successor: dict[str, Any]) -> float:
    public = successor["model_input"]
    hp = public["context"]["persistent"]["player"]["hp"]
    if family == "finish_combat":
        kind = public["context"]["interaction"]["kind"]
        if kind not in {"combat_turn", "reward_claim"}:
            raise ValueError("Encounter-ending evidence must be the native combat reward holder")
        return float(hp > 0 and kind == "reward_claim")
    if family != "survive_turn":
        raise ValueError("Unknown finite tactical objective")
    before = root["model_input"]["context"]["interaction"]["content"]["context"]["round"]
    after = public["context"]["interaction"]
    if hp <= 0:
        return 0.0
    if after["kind"] != "combat_turn" or after["content"]["context"]["round"] <= before:
        raise ValueError(
            "Survival labels require an observed next enemy/player turn, not an HP guess"
        )
    return 1.0


def qualify_case(public: dict[str, Any], values: list[float]) -> int:
    validate_public_input(public)
    if (
        public["context"]["persistent"]["run"]["ascension"] != 8
        or public["context"]["persistent"]["player"]["character_definition_id"] != "IRONCLAD"
        or public["context"]["interaction"]["kind"] != "combat_turn"
        or len(public["candidates"]) != len(values)
        or len(values) < 2
        or any(v not in (0.0, 1.0) for v in values)
        or values.count(1.0) != 1
        or values.count(0.0) < 1
    ):
        raise ValueError("A tactical lesson requires a native-verified unique success and failure")
    return values.index(1.0)


def collect_case(
    q: EngineQualificationConfig,
    inputs: dict[str, Any],
    cfg: dict[str, Any],
    task: dict[str, Any],
    target: Path,
) -> dict[str, Any]:
    public, key, branches, sources = None, None, [], {}
    actions = None
    index = 0
    while actions is None or index < actions:
        worker = TacticalWorker(
            q, inputs, target / f"branch-{index:02d}", Path(cfg["node"]), cfg["helpers_sha256"]
        )
        try:
            current = worker.request(
                "prepare_tactical", family=task["family"], seed=task["seed"]["seed"], timeout=35
            )
            if public is None:
                public, key = current["model_input"], current["public_key"]
                actions = len(public["candidates"])
                if not 2 <= actions <= 3:
                    raise ValueError("Basic tactical fixture has an unexpected action space")
            if current["public_key"] != key or current["model_input"] != public:
                raise ValueError(
                    "Counterfactual branches did not reproduce the identical public root"
                )
            root = current
            current = worker.request(
                "step", snapshot_id=current["snapshot"]["snapshot_id"], action_index=index
            )
            if task["family"] == "survive_turn" and not current["facts"]["terminal"]:
                interaction = current["model_input"]["context"]["interaction"]
                before = root["model_input"]["context"]["interaction"]["content"]["context"]
                if (
                    interaction["kind"] == "combat_turn"
                    and interaction["content"]["context"]["round"] == before["round"]
                ):
                    end = [
                        i
                        for i, c in enumerate(current["model_input"]["candidates"])
                        if c["verb"] == "end_turn"
                    ]
                    if len(end) != 1:
                        raise ValueError("The fixed continuation lacks one current End Turn")
                    current = worker.request(
                        "step",
                        snapshot_id=current["snapshot"]["snapshot_id"],
                        action_index=end[0],
                    )
            value = outcome(task["family"], root, current)
            branches.append(
                {"action": index, "outcome": value, "successor": current["model_input"]}
            )
            worker.close()
        except BaseException:
            worker.retire("Tactical diagnostic failure; preserve this branch without retry")
            raise
        finally:
            worker.stop()
        index += 1
    assert public is not None
    best = qualify_case(public, [b["outcome"] for b in branches])
    atomic_json(
        target / "lesson.json", {"public_input": public, "branches": branches, "best": best}
    )
    sources.update(
        {str(p.relative_to(q.root)): _sha_file(p) for p in target.rglob("*") if p.is_file()}
    )
    return {
        "kind": "tactical_case",
        "task": task,
        "lesson_path": str((target / "lesson.json").relative_to(q.root)),
        "public_input_id": manifest_identifier(public),
        "native_branches": len(branches),
        "unique_native_success": best,
        "privileged_fixture": True,
        "ordinary_PPO_eligible": False,
        "full_run_attempts": 0,
        "sources": sources,
    }
