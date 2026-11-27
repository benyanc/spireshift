"""One sealed policy qualification, exact-state fork, collection, fit or evaluation."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_native import _shared_snapshot
from spireshift.engine_qualification import EngineQualificationConfig
from spireshift.engine_worker_qualification import immutable_checks
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_ppo_math import Sample
from spireshift.native_combat_behavior_game import branch
from spireshift.native_context_journal import ChunkJournal, load_state, save_state
from spireshift.native_exploration_collector import collect_panel
from spireshift.native_exploration_training import prepare_compact
from spireshift.native_policy_updates import SETTINGS, qualify, update


def training_paths(
    root: Path,
    cfg: dict[str, Any],
    task: dict[str, Any],
    done: dict[str, dict[str, Any]],
    model_id: str,
) -> list[Path]:
    """Only this recipe's newly collected sampled TRAIN games, in planned order."""
    paths: dict[int, Path] = {}
    for key in task["collections"]:
        for name in done[key]["paths"]:
            path = root / name
            header = json.loads(path.read_text())
            bound = header["binding"]
            seed_id = bound["seed_id"]
            if (
                bound["config_id"] != manifest_identifier(cfg)
                or bound["partition"] != "train"
                or bound["panel_purpose"] != "training"
                or bound["model_id"] != model_id
                or bound["seed_manifest_id"] != cfg["seed_manifest"]["id"]
                or seed_id not in task["seed_ids"]
                or seed_id in paths
                or bound["native_seed"]
                != dict(zip(task["seed_ids"], task["native_seeds"], strict=True)).get(seed_id)
                or header["episode"].get("privileged_fixed_world_teacher", False)
                or header["episode"].get("ordinary_PPO_eligible") is False
            ):
                raise ValueError(
                    "Never admit greedy, stale, foreign or duplicate experience as PPO"
                )
            paths[seed_id] = path
    if set(paths) != set(task["seed_ids"]):
        raise ValueError("Do not silently omit or replace a scheduled training game")
    return [paths[n] for n in task["seed_ids"]]


def execute(
    root: Path,
    context: dict[str, Any],
    store: ChunkJournal,
    task: dict[str, Any],
    req: dict[str, Any],
    done: dict[str, dict[str, Any]],
    deadline: float,
    native: tuple[EngineQualificationConfig, dict[str, Any]] | None,
) -> dict[str, Any]:
    cfg, score = context["config"], context["score"]
    if task["kind"] == "qualify":
        players = [
            {"player": p, **qualify(context["models"][p], context["adams"][p])} for p in (2, 3)
        ]
        target = store.begin(task["key"], req)
        result = {
            "kind": "qualify",
            "passed": all(p["passed"] for p in players),
            "players": players,
            "games_recorded": 0,
        }
        atomic_json(target / "policy-checks.json", result)
        store.commit(task["key"], req, result)
        return result
    if task["kind"] == "import":
        model, adam = context["models"][task["player"]], context["adams"][task["player"]]
        prior_id = next(
            p["state_id"] for p in cfg["players"] if p["numerical_seed"] == task["player"]
        )
    else:
        before = done[task["state"]]
        model, adam, prior_id = load_state(root / before["state_path"])
        if prior_id != req["predecessor_state_id"] or adam.steps != before["optimizer_steps"]:
            raise ValueError("Continue the exact preceding weights and complete Adam state")
    target = store.begin(task["key"], req)
    sources: dict[str, str] = {}
    if task["kind"] == "import":
        save_state(target / "state.json", model, adam)
        _, _, state_id = load_state(target / "state.json")
        if state_id != prior_id:
            raise ValueError("The imported original model or an Adam moment changed")
        result = {
            "kind": "import",
            "player": task["player"],
            "state_id": state_id,
            "state_path": str((target / "state.json").relative_to(root)),
            "model_id": model.model_id,
            "optimizer_steps": adam.steps,
            "new_optimizer_steps": 0,
            "games_recorded": 0,
        }
    elif task["kind"] == "fit":
        paths = training_paths(root, cfg, task, done, model.model_id)
        samples, credit = prepare_compact(
            paths, model, score, SETTINGS, cfg["credit"], task["round"], 0
        )
        after, optimizer, work = update(model, adam, cast(list[Sample], samples), task["round"])
        if time.monotonic() >= deadline:
            raise TimeoutError(
                "Policy fitting reached its finite cap; preserve its unfinished unit"
            )
        save_state(target / "state.json", after, optimizer)
        _, _, sid = load_state(target / "state.json")
        atomic_json(target / "credit.json", credit)
        atomic_json(target / "work.json", work)
        result = {
            "kind": "fit",
            "player": task["player"],
            "round": task["round"],
            "state_path": str((target / "state.json").relative_to(root)),
            "state_id": sid,
            "model_id": after.model_id,
            "optimizer_steps": optimizer.steps,
            "new_optimizer_steps": optimizer.steps - adam.steps,
            "games_recorded": 0,
            "clean_training_games": credit["clean_complete_training_games"],
            "source_training_games": len(paths),
            "stop_reason": work["stop_reason"],
        }
        print(
            f"Player {task['player']}, round {task['round']}: Adam {adam.steps}→{optimizer.steps}; "
            f"{credit['clean_complete_training_games']}/{len(paths)} clean games; "
            "no score regression.",
            flush=True,
        )
        del samples
    else:
        assert native is not None
        q, inputs = native
        account = Path.home() / "Library/Application Support/SlayTheSpire2"
        snapshot = _shared_snapshot(account)
        if task["kind"] == "collect":
            parent = {
                "environment_manifest": cfg["environment_manifest"],
                "helpers_sha256": cfg["helpers_sha256"],
                "learning": {"ppo": SETTINGS},
                "maximum_decisions": cfg["maximum_decisions"],
                "episode_wall_seconds": cfg["episode_wall_seconds"],
            }
            paths, report, sources = collect_panel(
                q,
                cfg,
                parent,
                inputs,
                task["seeds"],
                Path(cfg["node"]),
                target / "games",
                model,
                score,
                task["player"],
                f"policy-round-{task['round']:02d}",
                True,
                deadline,
                0,
            )
            result = {
                "kind": "collect",
                "player": task["player"],
                "round": task["round"],
                "paths": [str(p.relative_to(root)) for p in paths],
                "summary": report,
                "games_recorded": len(paths),
                "model_id": model.model_id,
                "collection_id": manifest_identifier(report),
            }
        elif task["kind"] == "evaluate":
            eval_task = {
                "key": task["key"],
                "stage": "game",
                "seed": task["seed"],
                "numerical_seed": task["player"],
                "variant": task["variant"],
                "arm": "greedy",
                "duplicate_of": None,
            }
            result = {
                **branch(
                    q, cfg, inputs, target, Path(cfg["node"]), eval_task, model, score, deadline
                ),
                "kind": "evaluate",
                "player": task["player"],
                "variant": task["variant"],
                "games_recorded": 1,
            }
        else:
            raise ValueError("Unknown policy-update task")
        checks = immutable_checks(q, inputs)
        checks["account_profile_unchanged"] = snapshot == _shared_snapshot(account)
        if not all(checks.values()):
            raise ValueError("A frozen native input or account profile changed")
        result["checks"] = checks
    store.commit(task["key"], req, result, sources)
    return result
