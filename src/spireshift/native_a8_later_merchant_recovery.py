"""Verify the two saved shared-head prefixes and the stopped shop exit."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift import native_a8_later_recovery as recovery
from spireshift import native_a8_later_training as original
from spireshift import native_a8_later_training_plan as plan
from spireshift import native_a8_later_training_resume as previous
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_reward_exit_recovery import chunk_evidence_id
from spireshift.native_compatibility_contract import verified
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_flow_verification_v12 import records

FAILED = "t03a2s-p3"
ERROR = "ValueError: Native worker failed: Incomplete public state: native_potion_merchant_target"


def check_attempt(
    study: original.Study, store: ChunkJournal, cfg: dict[str, Any], control_id: str
) -> dict[str, Any]:
    root = study.recovery.root
    path = verified(root, cfg["interrupted_report"])
    resources_path = verified(root, cfg["interrupted_resources"])
    report, resources = identified(path), identified(resources_path)
    attempt = path.stem.removeprefix("session-")
    if (
        path != store.workspace / f"session-{attempt}.json"
        or resources_path != store.workspace / f"resources-{attempt}.json"
        or json.loads((store.workspace / "config-at-launch.json").read_text()) != store.recipe
        or report["schema_version"] != previous.SCHEMA
        or report["config_id"] != store.config_id
        or report["control_id"] != control_id
        or report["status"] != "stopped_preserving_evidence"
        or report["stop"] != {"unit": FAILED, "error": ERROR}
        or report["starting_states"] != study.cfg["starting_states"]
        or report["final_checkpoint_ids"] != {}
        or report["frozen_checks"] != study.recovery.original.source.study.frozen_checks
        or resources["status"] != "failed"
        or resources["exit_code"] != 2
        or resources["cap"] is not None
        or resources["command"]
        != ["uv", "run", "--no-sync", "python", "-m", previous.MODULE, "--execute", attempt]
        or resources["artifacts"]["roots"] != [str(store.workspace)]
    ):
        raise ValueError("Require the exact interrupted merchant-map training attempt")
    return report


def _last(path: Path, *, kind: str | None = None) -> tuple[int, dict[str, Any]]:
    count, last = 0, {}
    for row in records(path):
        if kind is None or row.get("kind") == kind:
            count += 1
            last = row
    return count, last


def failure_row(
    store: ChunkJournal,
    cfg: dict[str, Any],
    request: dict[str, Any],
    start: dict[str, Any],
    expected_initial: str,
) -> dict[str, Any]:
    target = store.path(FAILED)
    worker = target / "worker"
    marker = json.loads((target / "active.json").read_text())
    identity = json.loads((worker / "identity.json").read_text())
    stopped = json.loads((worker / "native-process-stop.json").read_text())
    load = previous.verify_control_delivery(target, start)
    total, endpoint = _last(target / "shared-public.jsonl.gz")
    choices, last_choice = _last(target / "shared-public.jsonl.gz", kind="policy_choice")
    observed, last_frame = _last(worker / "public-observations.jsonl.gz")
    receipts, exit_receipt = _last(worker / "public-receipts.jsonl.gz")
    first = next(records(target / "shared-public.jsonl.gz"))
    frame = endpoint["frame"]
    if (
        marker["config_id"] != store.config_id
        or marker["key"] != FAILED
        or marker["request"] != request
        or marker["request_id"] != manifest_identifier(request)
        or chunk_evidence_id(target) != cfg["failed_chunk_id"]
        or any((target / name).exists() for name in ("done.json", "report.json"))
        or identity["initial_identity"]["active"] is not False
        or stopped["process_id"] != identity["runtime_identity"]["process_id"]
        or stopped["exit"] != {"code": 143, "signal": None, "error": None}
        or load["loaded_decision"] != "map_select"
        or first["kind"] != "policy_input"
        or manifest_identifier(first["frame"]["public_input"]) != expected_initial
        or total != choices * 2 + 1
        or observed != choices + 1
        or receipts != choices + 1
        or endpoint["kind"] != "policy_input"
        or frame["source_family"] != "shop_room"
        or frame["terminal"] is not False
        or last_frame["snapshot"]["snapshot_id"] != frame["observation"]["snapshot_id"]
        or last_choice["receipt"]["successor_snapshot_id"] != exit_receipt["snapshot_id"]
        or exit_receipt["snapshot_id"] != last_frame["snapshot"]["snapshot_id"]
        or exit_receipt["index"] != choices
        or exit_receipt["action"]["label"] != "Leave shop and open map"
        or exit_receipt["action"]["bound_action_id"]
        not in {binding["bound_action_id"] for binding in frame["actions"]}
        or exit_receipt["delivery"] != "delivered"
        or not exit_receipt["successor_snapshot_id"]
    ):
        raise ValueError("The preserved merchant exit differs from its native receipt")
    return {
        **request,
        "outcome": "failed",
        "stage": "merchant_map_observation",
        "native_decisions": 0,
        "saved_prefix_choices": choices,
        "saved_exit_receipt": exit_receipt["delivery"],
    }


def inspect(
    study: original.Study,
    earlier: ChunkJournal,
    store: ChunkJournal,
    cfg: dict[str, Any],
    first: dict[str, Any],
    report: dict[str, Any],
) -> dict[str, Any]:
    history = recovery.HistoryJournal(earlier, store.recipe, first["carried"])
    verifier = original.Session(study, False, 0)
    verifier.store = history
    states = {p: verifier.copy_parent(p) for p in PLAYERS}
    carried = dict(first["carried"])
    continuation_keys: set[str] = set()
    starts: dict[str, str] = {}
    outcomes: dict[int, Counter[str]] = {act: Counter() for act in (1, 2, 3)}
    act1_clears, fits = 0, []
    failures = {recovery.FAILED: first["failure"]}

    def load(key: str, request: dict[str, Any]) -> dict[str, Any]:
        seal = recovery.require_seal(history, key, request)
        carried[key] = seal["report_id"]
        if key not in first["carried"]:
            continuation_keys.add(key)
        return seal

    for round_index, worlds in enumerate(study.worlds["training"][:3], 1):
        prepared = {
            w["key"]: load(f"{w['key']}-start", recovery.start_request(w))["result"]
            for w in worlds
            if w["act"] > 1
        }
        for p in PLAYERS:
            games = []
            for world in worlds:
                start = prepared.get(world["key"])
                seed = start["seed"] if start else world["seed"]
                task = plan.training_task(world, p, round_index, seed, False)
                key = task["key"]
                request = recovery.game_request(task, states[p], start)
                if key == recovery.FAILED:
                    if any(failures[key][name] != value for name, value in request.items()):
                        raise ValueError("The prior failed load changed its checkpoint")
                    games.append(manifest_identifier(failures[key]))
                    continue
                if key == FAILED:
                    if start is None:
                        raise ValueError("The stopped merchant case requires its original save")
                    failures[key] = failure_row(store, cfg, request, start, starts[seed])
                    break
                seal = load(key, request)
                row = seal["result"]
                if (
                    row["task"] != task
                    or row["model_id"] != request["model_id"]
                    or row.get("setup_id") != request.get("setup_id")
                    or row["outcome"] not in plan.TERMINAL
                    or starts.setdefault(seed, row["initial_public_input_id"])
                    != row["initial_public_input_id"]
                ):
                    raise ValueError(f"The saved game differs from its start or checkpoint: {key}")
                outcomes[world["act"]][row["outcome"]] += 1
                act1_clears += int(world["act"] == 1 and row["completed_acts"] >= 1)
                games.append(seal["report_id"])
            else:
                fit_key = f"fit-p{p}-r{round_index:02d}"
                seal = load(fit_key, {"parent_state_id": states[p][1], "games": games})
                fit = seal["result"]
                updated = verifier.checkpoint(fit_key, "shared", fit["states"]["shared"])
                steps = fit["work"]["optimizer_steps"]
                if (
                    updated[0].actor_adam.steps - states[p][0].actor_adam.steps != steps
                    or updated[0].value_adam.steps - states[p][0].value_adam.steps != steps
                ):
                    raise ValueError("The sealed optimizer transition differs")
                states[p] = updated
                fits.append(
                    {"round": round_index, "player": p, "seal_id": seal["report_id"], **fit}
                )
    game_count = sum(sum(counts.values()) for counts in outcomes.values())
    updates = sum(fit["work"]["optimizer_steps"] for fit in fits)
    if (
        set(failures) != {recovery.FAILED, FAILED}
        or {path.name for path in (store.workspace / "chunks").iterdir()}
        != {*continuation_keys, FAILED}
        or report["continued_from"] != first["report_id"]
        or report["preserved_training_failure"] != first["failure"]
        or report["training"] != fits
        or report["verified_games"] != game_count
        or report["optimizer_updates"] != updates
        or report["carried_optimizer_updates"] != first["updates"]
        or report["new_optimizer_updates"] != updates - first["updates"]
        or report["normal_start_evaluation"] != verifier.summary()
    ):
        raise ValueError("The carried training games, optimizer work or unstarted panel differ")
    return {
        "history": history,
        "carried": carried,
        "failures": failures,
        "games": game_count,
        "updates": updates,
        "report_id": report["report_id"],
        "outcomes": {str(act): dict(counts) for act, counts in outcomes.items()},
        "normal_start_act1_clears": act1_clears,
        "latest_checkpoints": {str(p): state[1] for p, state in states.items()},
    }


class HistoryJournal(recovery.HistoryJournal):
    """Read both sealed prefixes and reserve the two failed training slots."""

    def completed(self, key: str, request: dict[str, Any]) -> dict[str, Any] | None:
        if key == FAILED:
            raise ValueError("The interrupted merchant game must remain unresolved")
        return super().completed(key, request)

    def begin(self, key: str, request: dict[str, Any]) -> Path:
        if key == FAILED:
            raise ValueError("Preserve the interrupted merchant game")
        return super().begin(key, request)

    def commit(
        self,
        key: str,
        request: dict[str, Any],
        result: dict[str, Any],
        extra_sources: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if key == FAILED:
            raise ValueError("Preserve the interrupted merchant game")
        return super().commit(key, request, result, extra_sources)
