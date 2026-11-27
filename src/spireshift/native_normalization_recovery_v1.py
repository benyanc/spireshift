"""Independently verify the sealed normalization prefix without replaying its stop."""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_capacity_recovery_v1 import game_task
from spireshift.native_capacity_result_v1 import episode
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_flow_verification_v12 import records
from spireshift.native_normalization_inputs_v1 import RECIPE, context, load
from spireshift.native_normalized_actor_v1 import METHODS, CorrectionActor, initialize
from spireshift.native_normalized_actor_v1 import load as load_state
from spireshift.native_win4_game import write

FAILED = "train-0993-p2-normalized"
STOP = "stop-1795701231442595000.json"
WORKSPACE = "artifacts/native-hidden-normalization/recovery-v1"
STATUS = "normalization_prefix_and_complete_Adam_lineages_verified"


def failure_facts(path: Path) -> dict[str, Any]:
    last = error = None
    for row in records(path / "worker/private-transcript.jsonl.gz"):
        if row["response"].get("type") == "decision":
            last = row["response"]
        if row["response"].get("type") == "error":
            error = row
    receipts = list(records(path / "worker/public-receipts.jsonl.gz"))
    if (
        last is None
        or error is None
        or error["request"].get("action") != "discard_potion"
        or error["response"].get("message") != "Native potion discard enqueue was not confirmed"
        or last["decision"] != "generated_card_choice"
        or last["selection_combat"]["is_play_phase"] is not False
        or receipts[-1]["delivery"] != "unknown"
        or receipts[-1]["successor_snapshot_id"] is not None
        or any(r["delivery"] != "delivered" for r in receipts[:-1])
        or (path / "done.json").exists()
        or (path / "worker/closed.json").exists()
    ):
        raise ValueError("Preserve the exact unsealed opening-selector discard failure")
    return {
        "request": error["request"],
        "error": error["response"]["message"],
        "decision": last["decision"],
        "context": last["context"],
        "is_play_phase": False,
        "acknowledged_prefix_deliveries": len(receipts) - 1,
        "unknown_deliveries": 1,
        "training_admitted": False,
        "replayed": False,
        "clean_close": False,
    }


def audit(root: Path, deadline: float) -> dict[str, Any]:
    cfg = load(root)
    ctx = context(root, cfg)
    before = frozen(root, ctx)
    out = root / WORKSPACE
    out.mkdir(parents=True, exist_ok=True)
    final = out / "report.json"
    if final.exists():
        result = identified(final)
        check_sources(root, result["sources"])
        if result["frozen_checks"] != before:
            raise ValueError("Frozen inputs changed after the prefix audit")
        return result
    store = ChunkJournal(root, cfg)
    stop_path = store.workspace / STOP
    stopped = identified(stop_path)
    if (
        stopped["config_id"] != manifest_identifier(cfg)
        or stopped["status"] != "stopped_preserving_evidence"
        or stopped["stop"]["unit"] != FAILED
        or stopped["optimizer_updates_on_copies"] != 15252
    ):
        raise ValueError("The preserved normalization stop changed")
    sources = {
        RECIPE: _sha_file(root / RECIPE),
        str(stop_path.relative_to(root)): _sha_file(stop_path),
        str(Path(__file__).relative_to(root)): _sha_file(Path(__file__)),
    }
    units: dict[str, str] = {}
    covered: set[str] = set()
    counts: dict[str, Any] = {}
    fits = []
    capped = []
    failed_request = None

    def require(key: str, request: dict[str, Any]) -> dict[str, Any]:
        if time.monotonic() >= deadline:
            raise TimeoutError("The prefix audit reached its bounded deadline")
        seal = store.completed(key, request)
        if seal is None or seal["report_id"] != stopped["chunk_seals"].get(key):
            raise ValueError(f"Missing or changed historical unit: {key}")
        # completed() checks every real file once; bind those verified hashes to
        # the aggregate stop without rereading all compressed game bytes twice.
        for name, sha in seal["sources"].items():
            if stopped["sources"].get(name) != sha:
                raise ValueError("The aggregate stop and independently verified unit disagree")
            covered.add(name)
        path = store.path(key) / "done.json"
        name = str(path.relative_to(root))
        sources[name] = _sha_file(path)
        if stopped["sources"].get(name) != sources[name]:
            raise ValueError("A unit seal changed since the original stop")
        covered.add(name)
        units[key] = seal["report_id"]
        return {"seal_id": seal["report_id"], **seal["result"]}

    with store.lock():
        starting = {p: load_state(verified(root, cfg["starting_states"][str(p)])) for p in (2, 3)}
        require(
            "source-copies",
            {
                "source_states": {str(p): starting[p][1] for p in (2, 3)},
                "initialization": cfg["initialization"],
            },
        )
        current = {
            m: {p: load_state(store.path("source-copies") / f"p{p}-{m}.json") for p in (2, 3)}
            for m in METHODS
        }
        for m in METHODS:
            for p in (2, 3):
                if current[m][p][0] != initialize(
                    starting[p][0], m, cfg["initialization"]["correction_seeds"][str(p)]
                ):
                    raise ValueError(
                        "An initial full copied correction/reference/critic/Adam changed"
                    )
        for r in range(1, 65):
            for p in (2, 3):
                for method in METHODS if (r + p) % 2 else METHODS[::-1]:
                    cohort = counts.setdefault(
                        f"p{p}-{method}",
                        dict(outcomes=Counter(), act1_clears=0, act2_clears=0, fits=0),
                    )
                    rows = []
                    for i in range((r - 1) * 16 + 1, r * 16 + 1):
                        task = game_task(cfg["plan"]["training"][i - 1], i, p, r, method)
                        request = {"task": task, "behavior_state_id": current[method][p][1]}
                        if task["key"] == FAILED:
                            failed_request = request
                            break
                        row = require(task["key"], request)
                        if (
                            row["task"] != task
                            or row["model_id"] != current[method][p][0].model.model_id
                        ):
                            raise ValueError("A source game used a different behavior or world")
                        episode(store.path(task["key"]), row)
                        cohort["outcomes"][row["outcome"]] += 1
                        if row["outcome"] == "capped":
                            capped.append(task["key"])
                        else:
                            cohort["act1_clears"] += row["completed_acts"] >= 1
                            cohort["act2_clears"] += row["completed_acts"] >= 2
                        rows.append(row)
                    if failed_request is not None:
                        break
                    key = f"fit-p{p}-{method}-r{r:03d}"
                    fitted = require(
                        key,
                        {
                            "player": p,
                            "method": method,
                            "round": r,
                            "prior_state_id": current[method][p][1],
                            "game_seals": [row["seal_id"] for row in rows],
                        },
                    )
                    state, state_id = load_state(store.path(key) / "shared.json")
                    prior = current[method][p][0]
                    steps = fitted["work"]["optimizer_updates"]
                    if (
                        state_id != fitted["state_id"]
                        or state.model.model_id != fitted["model_id"]
                        or state.actor_adam.steps != prior.actor_adam.steps + steps
                        or state.value_adam.steps != prior.value_adam.steps + steps
                        or state.actor_adam.steps != fitted["actor_steps"]
                        or state.value_adam.steps != fitted["value_steps"]
                        or not isinstance(state.model.actor, CorrectionActor)
                        or state.model.actor.reference != starting[p][0].model.actor
                        or state.model.actor.correction_normalization != method
                        or fitted["eligible_terminal_worlds"]
                        != sum(row["outcome"] in {"win", "loss"} for row in rows)
                    ):
                        raise ValueError("A complete full-Adam/model/credit lineage changed")
                    current[method][p] = state, state_id
                    fits.append(fitted)
                    cohort["fits"] += 1
                if failed_request is not None:
                    break
            if failed_request is not None:
                break
        if failed_request is None or {p.name for p in (store.workspace / "chunks").iterdir()} != {
            *units,
            FAILED,
        }:
            raise ValueError("Missing or unexpectedly started historical cells")
        active = json.loads((store.path(FAILED) / "active.json").read_text())
        if active["request"] != failed_request or active["request_id"] != manifest_identifier(
            failed_request
        ):
            raise ValueError("The exact failed request or behavior state changed")
        facts = failure_facts(store.path(FAILED))
        check_sources(root, {n: sha for n, sha in stopped["sources"].items() if n not in covered})
        for path in store.path(FAILED).rglob("*"):
            if path.is_file():
                sources[str(path.relative_to(root))] = _sha_file(path)
        updates = sum(row["work"]["optimizer_updates"] for row in fits)
        games = sum(sum(c["outcomes"].values()) for c in counts.values())
        if (
            len(units) != 4234
            or len(fits) != 249
            or games != 3984
            or updates != 15252
            or len(capped) != 1
        ):
            raise ValueError("The declared prefix sizes or optimizer work differ")
    if frozen(root, ctx) != before:
        raise ValueError("Frozen inputs changed during saved-only audit")
    return write(
        final,
        {
            "status": STATUS,
            "parent_config_id": manifest_identifier(cfg),
            "parent_stop_id": stopped["report_id"],
            "inherited_units": units,
            "sealed_training_games": games,
            "sealed_fits": len(fits),
            "inherited_optimizer_updates": updates,
            "cohorts": counts,
            "capped_training_units": capped,
            "failed_request": failed_request,
            "failed_game": facts,
            "unstarted_training_games": 111,
            "unstarted_development_games": 768,
            "last_full_states": {m: {str(p): current[m][p][1] for p in (2, 3)} for m in METHODS},
            "games_launched": 0,
            "optimizer_updates": 0,
            "frozen_checks": before,
            "historical_menus_relabelled": False,
            "failed_prefix_used_as_training": False,
            "sources": sources,
        },
    )


if __name__ == "__main__":
    result = audit(Path.cwd(), time.monotonic() + 270)
    print(json.dumps({k: v for k, v in result.items() if k not in {"sources", "inherited_units"}}))
