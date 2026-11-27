"""Audit the capacity study's sealed prefix; never replay its failed potion request."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_capacity_inputs_v1 import METHODS, RECIPE, context, load
from spireshift.native_combat_intent_model import load as load_state
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_flow_verification_v12 import records
from spireshift.native_win4_game import write

FAILED = "train-0154-p3-expanded"
WORKSPACE = "artifacts/native-policy-capacity/recovery-v1"
STATUS = "capacity_prefix_and_full_Adam_lineages_verified"
STOP = "stop-1795559551581062000.json"


def game_task(seed: str, index: int, p: int, r: int, method: str) -> dict[str, Any]:
    return dict(
        key=f"train-{index:04d}-p{p}-{method}",
        seed=seed,
        seed_id=index,
        player=p,
        round=r,
        partition="train",
        arm="shared",
    )


def failure_facts(path: Path) -> dict[str, Any]:
    decision = None
    failed = None
    for row in records(path / "worker/private-transcript.jsonl.gz"):
        response = row["response"]
        if response.get("decision") == "card_select":
            decision = response
        if response.get("type") == "error":
            failed = row
    if (
        failed is None
        or decision is None
        or failed["request"].get("action") != "discard_potion"
        or "Godot.Callable.From" not in failed["response"]["message"]
        or "GameAction.Cancel()" not in failed["response"]["stack_trace"]
        or decision["selection_combat"]["is_play_phase"] is not False
        or (path / "done.json").exists()
        or (path / "worker/closed.json").exists()
    ):
        raise ValueError("Preserve the exact unfinished post-End-Turn potion failure")
    return {
        "request": failed["request"],
        "decision": decision["decision"],
        "selection_owner": decision["selection_owner"],
        "is_play_phase": decision["selection_combat"]["is_play_phase"],
        "turn_owner": decision["selection_combat"]["turn_owner"],
        "context": decision["context"],
        "training_admitted": False,
        "replayed": False,
        "clean_close": False,
    }


def audit(root: Path) -> dict[str, Any]:
    cfg = load(root)
    ctx = context(root, cfg)
    before = frozen(root, ctx)
    out = root / WORKSPACE
    out.mkdir(parents=True, exist_ok=True)
    if (out / "report.json").exists():
        result = identified(out / "report.json")
        check_sources(root, result["sources"])
        if result["frozen_checks"] != before:
            raise ValueError("Frozen inputs changed after capacity-prefix audit")
        return result
    store = ChunkJournal(root, cfg)
    stop_path = store.workspace / STOP
    stopped = identified(stop_path)
    check_sources(root, stopped["sources"])
    if stopped["stop"]["unit"] != FAILED or stopped["optimizer_updates_on_copies"] != 2429:
        raise ValueError("The preserved capacity stop differs")
    sources = {
        RECIPE: _sha_file(root / RECIPE),
        str(stop_path.relative_to(root)): _sha_file(stop_path),
    }
    units: dict[str, str] = {}
    counts: dict[str, Any] = {}
    updates = 0
    failed_request = None
    with store.lock():
        request = {
            "source_states": {
                str(p): load_state(verified(root, cfg["starting_states"][str(p)]))[1]
                for p in (2, 3)
            },
            "initialization": cfg["initialization"],
        }
        initial = store.completed("source-copies", request)
        if initial is None:
            raise ValueError("Missing the original four complete source copies")

        def retain(key: str, seal: dict[str, Any]) -> None:
            units[key] = seal["report_id"]
            path = store.path(key) / "done.json"
            sources[str(path.relative_to(root))] = _sha_file(path)

        retain("source-copies", initial)
        current = {
            m: {p: load_state(store.path("source-copies") / f"p{p}-{m}.json") for p in (2, 3)}
            for m in METHODS
        }
        for r in range(1, 65):
            for p in (2, 3):
                for method in METHODS if (r + p) % 2 else METHODS[::-1]:
                    rows = []
                    cohort = counts.setdefault(
                        f"p{p}-{method}",
                        dict(games=0, outcomes=Counter(), act1_clears=0, act2_clears=0, fits=0),
                    )
                    for i in range((r - 1) * 16 + 1, r * 16 + 1):
                        task = game_task(cfg["plan"]["training"][i - 1], i, p, r, method)
                        key = task["key"]
                        request = {"task": task, "behavior_state_id": current[method][p][1]}
                        if key == FAILED:
                            failed_request = request
                            break
                        seal = store.completed(key, request)
                        if seal is None:
                            raise ValueError(f"Missing historical game {key}; never replay it")
                        row = seal["result"]
                        closed = json.loads((store.path(key) / "worker/closed.json").read_text())
                        if (
                            row["task"] != task
                            or row["model_id"] != current[method][p][0].model.model_id
                            or row["outcome"] not in {"win", "loss"}
                            or not closed["clean_exit"]
                            or closed["runtime_errors"]
                        ):
                            raise ValueError("Historical outcome, behavior model or reset differs")
                        retain(key, seal)
                        rows.append(row)
                        cohort["games"] += 1
                        cohort["outcomes"][row["outcome"]] += 1
                        cohort["act1_clears"] += row["completed_acts"] >= 1
                        cohort["act2_clears"] += row["completed_acts"] >= 2
                    if failed_request is not None:
                        break
                    key = f"fit-p{p}-{method}-r{r:03d}"
                    request = {
                        "player": p,
                        "method": method,
                        "round": r,
                        "prior_state_id": current[method][p][1],
                        "game_seals": [units[row["task"]["key"]] for row in rows],
                    }
                    seal = store.completed(key, request)
                    if seal is None:
                        raise ValueError("Missing a historical fit; never repeat its updates")
                    row = seal["result"]
                    state, state_id = load_state(store.path(key) / "shared.json")
                    steps = row["work"]["optimizer_updates"]
                    prior = current[method][p][0]
                    if (
                        state_id != row["state_id"]
                        or state.model.model_id != row["model_id"]
                        or state.actor_adam.steps != prior.actor_adam.steps + steps
                        or state.value_adam.steps != prior.value_adam.steps + steps
                        or state.actor_adam.steps != row["actor_steps"]
                        or state.value_adam.steps != row["value_steps"]
                        or state.model.actor.hidden_units != (32 if method == "standard" else 128)
                    ):
                        raise ValueError("A complete model/Adam lineage changed")
                    current[method][p] = state, state_id
                    retain(key, seal)
                    updates += steps
                    cohort["fits"] += 1
                if failed_request is not None:
                    break
            if failed_request is not None:
                break
        if failed_request is None or {p.name for p in (store.workspace / "chunks").iterdir()} != {
            *units,
            FAILED,
        }:
            raise ValueError("Unexpected missing, extra or started historical units")
        active = json.loads((store.path(FAILED) / "active.json").read_text())
        if active["request"] != failed_request or active["request_id"] != manifest_identifier(
            failed_request
        ):
            raise ValueError("The excluded failed request or behavior state changed")
        facts = failure_facts(store.path(FAILED))
        for path in store.path(FAILED).rglob("*"):
            if path.is_file():
                sources[str(path.relative_to(root))] = _sha_file(path)
        if sum(c["games"] for c in counts.values()) != 633 or updates != 2429 or len(units) != 673:
            raise ValueError("The clean prefix counts or optimizer work differ")
    if frozen(root, ctx) != before:
        raise ValueError("Frozen inputs changed during read-only assessment")
    return write(
        out / "report.json",
        {
            "status": STATUS,
            "parent_config_id": manifest_identifier(cfg),
            "parent_stop_id": stopped["report_id"],
            "inherited_units": units,
            "sealed_training_games": 633,
            "sealed_fits": 39,
            "inherited_optimizer_updates": updates,
            "cohorts": counts,
            "failed_request": failed_request,
            "failed_game": facts,
            "unstarted_training_games": 3462,
            "unstarted_development_games": 768,
            "games_launched": 0,
            "optimizer_updates": 0,
            "frozen_checks": before,
            "historical_menus_relabelled": False,
            "sources": sources,
        },
    )


if __name__ == "__main__":
    result = audit(Path.cwd())
    print(json.dumps({k: v for k, v in result.items() if k not in {"sources", "inherited_units"}}))
