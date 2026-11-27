"""Bounded saved-delivery audits; interrupted prefixes are diagnostic evidence only.

Keep one sealed episode, two observations and one record from each compressed
journal in memory. Historical whole-journal auditors stay frozen for reproduction.
Never clear, close, reset or modify a recovered worker or its marker.
"""

from __future__ import annotations

import gzip
import json
import time
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import psutil

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode
from spireshift.engine_qualification import _sha_file
from spireshift.engine_run import _verify_saved_observation

JOURNALS = (
    "private-transcript.jsonl.gz",
    "public-observations.jsonl.gz",
    "public-receipts.jsonl.gz",
)
ALLOWED = {
    "runtime_identity",
    "run_identity",
    "process_metrics",
    "start_run",
    "reset_run",
    "get_map",
    "observe",
    "action",
    "quit",
}


def records(path: Path, deadline: float) -> Iterator[dict[str, Any]]:
    with gzip.open(path, "rt") as stream:
        for line in stream:
            if time.monotonic() >= deadline:
                raise TimeoutError("Streaming experience verification reached its wall cap")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("Journal record must be an object")
            yield value


class Cursor:
    def __init__(self, values: Iterator[dict[str, Any]]) -> None:
        self.values = values
        self.current = next(values, None)

    def pop(self) -> dict[str, Any]:
        if self.current is None:
            raise ValueError("Saved journal ended before its bound episode")
        result = self.current
        self.current = next(self.values, None)
        return result


def raw_episodes(path: Path, deadline: float) -> Iterator[dict[str, Any]]:
    """Consume every raw request; retain only a start and the last native identity."""
    current: dict[str, Any] | None = None
    for row in records(path, deadline):
        request = row["request"]
        command = request["cmd"]
        if command not in ALLOWED:
            raise ValueError("Saved worker contains a fixture or unbound native command")
        if command in {"start_run", "reset_run"}:
            if current is not None:
                yield current
            current = {"start": request, "last_identity": None}
        elif command == "run_identity" and current is not None:
            current["last_identity"] = row["response"]
    if current is not None:
        yield current


def stopped_worker_evidence(workspace: Path) -> dict[str, Any]:
    """Observe process absence, never signal a process or rewrite shutdown evidence."""
    identity = json.loads((workspace / "identity.json").read_text())
    pids = [identity["runtime_identity"]["process_id"]]
    if (workspace / "active.json").is_file():
        pids.append(json.loads((workspace / "active.json").read_text())["owner_process"])
    if any(type(pid) is not int or pid <= 0 or psutil.pid_exists(pid) for pid in pids):
        raise ValueError("A recorded interrupted worker process still exists; leave it untouched")
    controllers = []
    for process in psutil.process_iter(["pid", "cmdline"]):
        try:
            if any(
                Path(arg).name == "engine-native-worker-v9.mjs"
                for arg in process.info["cmdline"] or []
            ):
                controllers.append(process.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if controllers:
        raise ValueError("A native worker controller is still present; no prefix recovery")
    return {
        "recorded_process_ids": pids,
        "recorded_processes_absent": True,
        "matching_worker_controllers_absent": True,
        "processes_signalled": 0,
        "worker_workspace_reusable": False,
    }


def compact_case(case: dict[str, Any]) -> dict[str, Any]:
    return {
        k: case[k]
        for k in (
            "status",
            "seed",
            "victory",
            "completed_acts",
            "maximum_floor",
            "cpu_seconds",
            "worker_workspace",
        )
    } | {"decision_count": len(case["decisions"]), "error": case.get("error")}


def _closure(workspace: Path, interrupted: bool) -> tuple[str, dict[str, Any] | None]:
    if interrupted:
        if not (workspace / "active.json").is_file() or (workspace / "closed.json").exists():
            raise ValueError("Interrupted prefix must preserve its original active marker")
        return "active.json", stopped_worker_evidence(workspace)
    if (workspace / "retired.json").is_file():
        retired = json.loads((workspace / "retired.json").read_text())
        stopped = json.loads((workspace / "native-process-stop.json").read_text())
        if (
            retired.get("schema_version") != "actual-engine-worker-retirement-v1"
            or retired.get("controller_process_stopped") is not True
            or retired.get("native_process_stopped") is not True
            or retired.get("workspace_reusable") is not False
            or retired.get("failed_seed_retried") is not False
            or stopped.get("process_id") != retired.get("native_process_id")
            or not stopped.get("exit")
            or not (workspace / "active.json").is_file()
            or (workspace / "closed.json").exists()
        ):
            raise ValueError("Retired worker lacks its original verified shutdown")
        return "retired.json", None
    closed = json.loads((workspace / "closed.json").read_text())
    if closed.get("clean_exit") is not True or (workspace / "active.json").exists():
        raise ValueError("Saved experience worker did not finish cleanly")
    return "closed.json", None


def audit_worker_streaming(
    workspace: Path,
    paths: Sequence[Path],
    *,
    interrupted: bool = False,
    deadline: float,
) -> dict[str, Any]:
    """Exact delivery/ending checks with ordered, one-episode-at-a-time journal reads.

    Interrupted recovery is intentionally distinct from normal or retired-worker
    admission: verified completed games are usable only in a diagnostic pool.
    The bounded unfinished suffix, all its commands and every missing seed remain
    visible. A malformed/compressed tail stops verification; it is never truncated.
    """
    if not paths or len(set(paths)) != len(paths):
        raise ValueError("Streaming audit requires distinct bound episode paths")
    closure, process = _closure(workspace, interrupted)
    names = [*JOURNALS, closure, "identity.json"]
    if closure == "retired.json":
        names += ["native-process-stop.json", "active.json"]
    names = [n for n in names if (workspace / n).is_file()]
    before = {name: _sha_file(workspace / name) for name in names}
    observations = Cursor(records(workspace / JOURNALS[1], deadline))
    receipts = Cursor(records(workspace / JOURNALS[2], deadline))
    raw = Cursor(raw_episodes(workspace / JOURNALS[0], deadline))
    decisions = excluded = complete = 0
    outcomes, starts, sealed = [], [], []
    for episode, path in enumerate(paths, 1):
        header = json.loads(path.read_text())
        case = read_native_episode(path, header["binding"])
        sealed.append(
            {
                "path": str(path),
                "sha256": _sha_file(path),
                "trace_sha256": header["trace_file_sha256"],
                "case_id": header["case_id"],
            }
        )
        if case["status"] != "terminal":
            if episode != len(paths) or closure != "retired.json":
                raise ValueError("Only an explicitly retired final failed game may be excluded")
            excluded += 1
            if raw.current is not None:
                starts.append(raw.pop()["start"]["seed"])
            continue
        native = raw.pop()
        start = native["start"]
        starts.append(start["seed"])
        if (
            case.get("privileged_fixture") is not False
            or case.get("recovered") is not False
            or start.get("seed") != case["seed"]
            or start.get("ascension") != 8
            or start.get("character") != "Ironclad"
            or start.get("content_policy") != "native_benchmark_full_v1"
        ):
            raise ValueError("Streaming episode scope, seed or clean status differs")
        current = observations.pop()
        runtime = current["snapshot"]["session"]["runtime_instance_id"]
        _verify_saved_observation(current, runtime)
        for index, decision in enumerate(case["decisions"]):
            successor, delivery = observations.pop(), receipts.pop()
            _verify_saved_observation(successor, runtime)
            selected = decision["choice"]["action_index"]
            actions = current["snapshot"]["bound_actions"]["actions"]
            if type(selected) is not int or not 0 <= selected < len(actions):
                raise ValueError("Saved choice is outside its current complete legal menu")
            if (
                current["episode"] != episode
                or successor["episode"] != episode
                or delivery["episode"] != episode
                or current["index"] != index
                or successor["index"] != index + 1
                or delivery["index"] != index
                or current["model_input"] != decision["public_input"]
                or current["public_key"] != decision["public_key"]
                or delivery["snapshot_id"] != current["snapshot"]["snapshot_id"]
                or delivery["action"] != actions[selected]
                or delivery["delivery"] != "delivered"
                or delivery["successor_snapshot_id"] != successor["snapshot"]["snapshot_id"]
            ):
                raise ValueError("Streaming input/choice/delivery/observation chain differs")
            decisions += 1
            current = successor
        if (
            current["episode"] != episode
            or current["index"] != len(case["decisions"])
            or not current["facts"]["terminal"]
            or current["facts"]["victory"] != case["victory"]
            or case.get("native_ending_evidence_agrees") is not True
            or native["last_identity"] != case["private_final_identity"]
        ):
            raise ValueError("Streaming native/public terminal evidence differs")
        complete += 1
        outcomes.append(compact_case(case))
        del case
    tail_starts = []
    while raw.current is not None:
        tail_starts.append(raw.pop()["start"]["seed"])
    tail_observations = tail_receipts = 0
    for cursor, label in ((observations, "observations"), (receipts, "receipts")):
        while cursor.current is not None:
            row = cursor.pop()
            if row.get("episode") != len(paths) + (0 if excluded else 1):
                raise ValueError("Unbound journal episode outside the single unfinished suffix")
            if label == "observations":
                tail_observations += 1
            else:
                tail_receipts += 1
    if interrupted:
        if len(tail_starts) > 1 or len(set([*starts, *tail_starts])) != len(starts) + len(
            tail_starts
        ):
            raise ValueError("Interrupted journal contains duplicate or multiple unbound starts")
        if (tail_observations or tail_receipts) and len(tail_starts) != 1:
            raise ValueError("Unfinished public records lack their native start")
    elif closure == "closed.json":
        if (
            tail_starts
            or tail_observations
            or tail_receipts
            or excluded
            or json.loads((workspace / closure).read_text())["episodes"] != complete
        ):
            raise ValueError("Clean worker has missing or extra episode evidence")
    elif len(tail_starts) or excluded != 1:
        raise ValueError("Retired worker has more than its final failed game")
    if before != {name: _sha_file(workspace / name) for name in names}:
        raise ValueError("Worker evidence changed while being read")
    body = {
        "schema_version": "actual-engine-streamed-experience-audit-v1",
        "valid": True,
        "games": complete,
        "excluded_failed_games": excluded,
        "decisions": decisions,
        "interrupted_diagnostic_prefix": interrupted,
        "ordinary_training_admission": False,
        "process_evidence": process,
        "started_native_seeds": [*starts, *tail_starts],
        "unfinished_native_seeds": tail_starts,
        "unfinished_observations": tail_observations,
        "unfinished_receipts": tail_receipts,
        "outcomes": outcomes,
        "sealed_cases": sealed,
        "source_sha256": before,
        "maximum_retained_episode_histories": 1,
        "games_replayed": 0,
        "worker_workspace_reused": False,
        "claim_scope": "saved_delivery_and_ending_verification_only_not_new_environment_admission",
    }
    return {**body, "report_id": manifest_identifier(body)}
