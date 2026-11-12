"""Verify and preserve the original later-act training lineage."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift import native_a8_later_start as prepared
from spireshift import native_a8_later_training as previous
from spireshift import native_a8_later_training_plan as plan
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.native_a8_head_study import Saved
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_reward_exit_recovery import chunk_evidence_id
from spireshift.native_compatibility_contract import verified
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_flow_verification_v12 import records

FAILED = "t02a2s-p3"
ERROR = "ValueError: Native worker failed: JSON-line response timed out after 15000ms."


def start_request(world: dict[str, Any]) -> dict[str, Any]:
    return {"world": world}


def game_request(
    task: dict[str, Any], state: Saved, start: dict[str, Any] | None
) -> dict[str, Any]:
    request = {"task": task, "behavior_state_id": state[1], "model_id": state[0].model.model_id}
    return {**request, "setup_id": start["report_id"]} if start is not None else request


def require_seal(history: ChunkJournal, key: str, request: dict[str, Any]) -> dict[str, Any]:
    seal = history.completed(key, request)
    if seal is None:
        raise ValueError(f"Missing original sealed training chunk {key}")
    return seal


def failure_row(
    history: ChunkJournal, request: dict[str, Any], cfg: dict[str, Any]
) -> dict[str, Any]:
    target = history.path(FAILED)
    worker = target / "worker"
    active = json.loads((target / "active.json").read_text())
    identity = json.loads((worker / "identity.json").read_text())
    stop = json.loads((worker / "native-process-stop.json").read_text())
    initial = identity["initial_identity"]
    if (
        active["key"] != FAILED
        or active["config_id"] != history.config_id
        or active["request"] != request
        or active["request_id"] != manifest_identifier(request)
        or chunk_evidence_id(target) != cfg["failed_chunk_id"]
        or initial["active"] is not False
        or initial["prepared_load_initialized"] is not False
        or stop["process_id"] != identity["runtime_identity"]["process_id"]
        or any(
            (target / name).exists()
            for name in (
                "done.json",
                "report.json",
                "shared-public.jsonl.gz",
                "worker/public-observations.jsonl.gz",
                "worker/public-receipts.jsonl.gz",
            )
        )
        or [row["request"]["cmd"] for row in records(worker / "private-transcript.jsonl.gz")]
        != ["runtime_identity", "run_identity", "process_metrics"]
    ):
        raise ValueError("The preserved save-load failure differs from its startup evidence")
    return {**request, "outcome": "failed", "stage": "prepared_save_load", "native_decisions": 0}


def inspect(
    study: previous.Study, history: ChunkJournal, cfg: dict[str, Any], control_id: str
) -> dict[str, Any]:
    root = study.recovery.root
    report_path = verified(root, cfg["interrupted_report"])
    resource_path = verified(root, cfg["interrupted_resources"])
    report, resources = identified(report_path), identified(resource_path)
    attempt = resource_path.stem.removeprefix("resources-")
    if (
        report_path != history.workspace / f"session-{attempt}.json"
        or resource_path != history.workspace / f"resources-{attempt}.json"
        or json.loads((history.workspace / "config-at-launch.json").read_text()) != history.recipe
        or report["schema_version"] != previous.SCHEMA
        or report["config_id"] != history.config_id
        or report["control_id"] != control_id
        or report["starting_states"] != study.cfg["starting_states"]
        or report["frozen_checks"] != study.recovery.original.source.study.frozen_checks
        or report["status"] != "stopped_preserving_evidence"
        or report["stop"] != {"unit": FAILED, "error": ERROR}
        or report["final_checkpoint_ids"] != {}
        or resources["status"] != "failed"
        or resources["exit_code"] != 2
        or resources["cap"] is not None
        or resources["artifacts"]["roots"] != [str(history.workspace)]
        or resources["command"]
        != ["uv", "run", "--no-sync", "python", "-m", previous.MODULE, "--execute", attempt]
    ):
        raise ValueError("Require the exact stopped later-act training attempt")
    verifier = previous.Session(study, False, 0)
    verifier.store = history
    carried: dict[str, str] = {}
    outcomes: dict[int, Counter[str]] = {act: Counter() for act in (1, 2, 3)}
    states = {}
    for p, parent in study.parents.items():
        key = f"copy-p{p}"
        seal = require_seal(history, key, {"parent_state_id": parent[1]})
        carried[key] = seal["report_id"]
        states[p] = verifier.checkpoint(key, "shared", seal["result"]["states"]["shared"])
        if states[p] != parent:
            raise ValueError("The original shared parent copy changed")
    fits = []
    initial_public_ids: dict[str, str] = {}
    for index, worlds in enumerate(study.worlds["training"][:2], 1):
        starts = {}
        for world in worlds:
            if world["act"] == 1:
                continue
            key = f"{world['key']}-start"
            seal = require_seal(history, key, start_request(world))
            carried[key] = seal["report_id"]
            start = seal["result"]
            if (
                start["kind"] != prepared.KIND
                or start["evaluation_eligible"] is not False
                or start["scenario"]["act"] != world["act"]
                or start["seed"] not in start["scenario"]["seed_pool"]
                or (world["archived"] is not None and start["seed"] != world["seed"])
            ):
                raise ValueError(
                    "The original prepared start is outside its declared training slot"
                )
            verified(root, {"path": start["save_path"], "sha256": start["save_sha256"]})
            starts[world["key"]] = start
        for p in PLAYERS:
            games = []
            for world in worlds:
                start = starts.get(world["key"])
                seed = world["seed"] if start is None else start["seed"]
                task = plan.training_task(world, p, index, seed, False)
                key = task["key"]
                request = game_request(task, states[p], start)
                if key == FAILED:
                    failure = failure_row(history, request, cfg)
                    break
                seal = require_seal(history, key, request)
                carried[key] = seal["report_id"]
                row = seal["result"]
                if (
                    row["task"] != task
                    or row["model_id"] != request["model_id"]
                    or row["outcome"] not in plan.TERMINAL
                    or initial_public_ids.setdefault(seed, row["initial_public_input_id"])
                    != row["initial_public_input_id"]
                ):
                    raise ValueError(
                        "An original game differs from its behavior state or matched start"
                    )
                outcomes[world["act"]][row["outcome"]] += 1
                games.append(seal["report_id"])
            else:
                key = f"fit-p{p}-r{index:02d}"
                seal = require_seal(history, key, {"parent_state_id": states[p][1], "games": games})
                carried[key] = seal["report_id"]
                fit = seal["result"]
                state = verifier.checkpoint(key, "shared", fit["states"]["shared"])
                steps = fit["work"]["optimizer_steps"]
                if (
                    state[0].actor_adam.steps - states[p][0].actor_adam.steps != steps
                    or state[0].value_adam.steps - states[p][0].value_adam.steps != steps
                ):
                    raise ValueError("The carried shared-head Adam transition differs")
                states[p] = state
                fits.append({"round": index, "player": p, "seal_id": seal["report_id"], **fit})
    game_count = sum(sum(counts.values()) for counts in outcomes.values())
    if (
        {path.name for path in (history.workspace / "chunks").iterdir()} != {*carried, FAILED}
        or report["training"] != fits
        or report["verified_games"] != game_count
        or report["optimizer_updates"] != sum(fit["work"]["optimizer_steps"] for fit in fits)
        or report["normal_start_evaluation"] != verifier.summary()
        or game_count != 56
    ):
        raise ValueError("The original sealed games, optimizer work or unstarted panel differ")
    return {
        "carried": carried,
        "failure": failure,
        "games": game_count,
        "updates": report["optimizer_updates"],
        "outcomes": {str(act): dict(counts) for act, counts in outcomes.items()},
        "report_id": report["report_id"],
        "latest_checkpoints": {str(p): state[1] for p, state in states.items()},
    }


class HistoryJournal(ChunkJournal):
    """Keep historical sealed chunks read-only while writing new work separately."""

    def __init__(
        self, history: ChunkJournal, recipe: dict[str, Any], carried: dict[str, str]
    ) -> None:
        super().__init__(history.root, recipe)
        self.history, self.carried = history, carried

    def path(self, key: str) -> Path:
        return self.history.path(key) if key in self.carried else super().path(key)

    def completed(self, key: str, request: dict[str, Any]) -> dict[str, Any] | None:
        if key in self.carried:
            seal = require_seal(self.history, key, request)
            if seal["report_id"] != self.carried[key]:
                raise ValueError(f"The carried seal changed: {key}")
            return seal
        if key == FAILED:
            raise ValueError("The timed-out training game must remain unresolved")
        return super().completed(key, request)

    def begin(self, key: str, request: dict[str, Any]) -> Path:
        if key in self.carried or key == FAILED:
            raise ValueError("Preserve the original training workspace")
        return super().begin(key, request)

    def commit(
        self,
        key: str,
        request: dict[str, Any],
        result: dict[str, Any],
        extra_sources: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if key in self.carried or key == FAILED:
            raise ValueError("Preserve the original training workspace")
        return super().commit(key, request, result, extra_sources)
