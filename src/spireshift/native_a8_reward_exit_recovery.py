"""Recover the interrupted endpoint without resuming its worker or resealing its world."""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_ordinary_policy import REASON
from spireshift.native_a8_ordinary_session import MODULE as PREVIOUS_MODULE
from spireshift.native_a8_rescue_curriculum import first_change
from spireshift.native_a8_rescue_game import TRACE, decisions, public_state
from spireshift.native_a8_rescue_session import NO_UPDATES
from spireshift.native_a8_reward_exit import verify_exit
from spireshift.native_a8_reward_exit_episode import verify, verify_loss
from spireshift.native_compatibility_contract import verified
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_flow_verification_v12 import records, same


def chunk_evidence_id(target: Path) -> str:
    sources = {}
    for path in target.rglob("*"):
        if path.is_symlink():
            raise ValueError("Interrupted evidence must not alias other files")
        if path.is_file():
            sources[path.relative_to(target).as_posix()] = _sha_file(path)
    return manifest_identifier(sources)


def previous_attempt(
    root: Path, ctx: dict[str, Any], cfg: dict[str, Any], previous: ChunkJournal
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    attempt_file = verified(root, cfg["previous_attempt"])
    attempt, resources = (
        identified(attempt_file),
        identified(verified(root, cfg["previous_resources"])),
    )
    if (
        json.loads((previous.workspace / "config-at-launch.json").read_text()) != previous.recipe
        or attempt["config_id"] != previous.config_id
        or attempt["execution_id"] != ctx["ordinary_execution_id"]
        or attempt["status"] != "ordinary_lethal_comparison_incomplete"
        or attempt["stop"]["reason"] != "unsealed_world"
        or resources["status"] != "failed"
        or resources["cap"] is not None
        or resources["exit_code"] != 2
        or resources["command"]
        != [
            "uv",
            "run",
            "--no-sync",
            "python",
            "-m",
            PREVIOUS_MODULE,
            "--run",
            "--attempt",
            attempt_file.stem.removeprefix("attempt-"),
        ]
        or resources["artifacts"]["roots"] != [str(previous.workspace)]
    ):
        raise ValueError("The exact interrupted ordinary-fight attempt is required")
    worlds = previous.recipe["worlds"]
    finished = attempt["sealed_worlds"]
    if not 0 <= finished < len(worlds):
        raise ValueError("Missing interrupted world in the original comparison")
    interrupted = worlds[finished]
    remaining = worlds[finished + 1 :]
    if (
        len(worlds) != attempt["planned_worlds"]
        or interrupted["key"] != attempt["stop"]["world"]
        or [case["key"] for case in remaining] != cfg["remaining_worlds"]
        or {case["key"] for case in worlds[:finished]} != set(attempt["seals"])
    ):
        raise ValueError("The continuation must retain the original world order and denominator")
    for case in worlds[:finished]:
        seal = previous.completed(case["key"], case)
        if seal is None or seal["report_id"] != attempt["seals"][case["key"]]:
            raise ValueError("A prior clean pair seal differs from the interrupted report")
    target = previous.path(interrupted["key"])
    if (
        (target / "done.json").exists()
        or chunk_evidence_id(target) != cfg["interrupted_chunk_id"]
        or any(previous.path(case["key"]).exists() for case in remaining)
    ):
        raise ValueError("Interrupted evidence or the previously unstarted worlds changed")
    return attempt, resources, interrupted, remaining


def saved_exit(target: Path, seed: str) -> dict[str, Any]:
    """Check an independent sealed clear against the new exact boundary."""
    report = identified(target / "report.json")
    if report["outcome"] != "act1_clear" or not report["shutdown"]["clean_exit"]:
        raise ValueError("Expected a previously sealed clean Act 1 clear")
    tail: deque[tuple[int, dict[str, Any], dict[str, Any] | None]] = deque(maxlen=2)
    saw_boss = False
    for row in decisions(target / TRACE):
        _, _, owner = public_state(row[1])
        saw_boss |= (
            owner["kind"] == "combat_turn"
            and owner["content"]["context"].get("encounter_type") == "boss"
        )
        tail.append(row)
    (_, before, action), (_, after, final) = tail
    source = target / "worker"
    observations = deque(records(source / "public-observations.jsonl.gz"), maxlen=2)
    if (
        not saw_boss
        or action is None
        or final is not None
        or len(observations) != 2
        or observations[0]["index"] + 1 != observations[1]["index"]
        or any(
            raw["episode"] != 1
            or raw["snapshot"]["snapshot_id"] != frame["observation"]["snapshot_id"]
            for raw, frame in zip(observations, (before, after), strict=True)
        )
        or identified(target / "native-start.json")["identity"]["seed"] != seed
    ):
        raise ValueError("Sealed clear does not have a bound Act 1 boss reward transition")
    proof = verify_exit(
        source, before, action["choice"], action["receipt"], after, observations[1]["index"]
    )
    if proof["hp"] != report["final_hp"]:
        raise ValueError("Sealed clear HP differs from the native Act 2 successor")
    return {
        "source_report_id": report["report_id"],
        "owner": proof["native_reward_owner"],
        "act": proof["act"],
        "hp": proof["hp"],
    }


def saved_regressions(root: Path, ctx: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    tactical = ctx["tactical_config"]
    sources = {
        "tactical": {
            **tactical,
            "workspace": tactical["diagnostic_workspace"],
            "worlds": tactical["diagnostic_worlds"],
        },
        "survival": ctx["config"],
    }
    result = {}
    for spec in cfg["saved_regressions"]:
        recipe = sources[spec["study"]]
        store = ChunkJournal(root, recipe)
        worlds = recipe["worlds"] if spec["study"] == "tactical" else recipe["worlds"]["qualify"]
        case = next(c for c in worlds if c["key"] == spec["key"])
        original = identified(verified(root, spec["seal"]))
        seal = store.completed(case["key"], case)
        if seal is None or original["report_id"] != seal["report_id"]:
            raise ValueError("Independent boss reward regression seal differs")
        result[case["key"]] = saved_exit(store.path(case["key"]) / spec["arm"], case["seed"])
    return result


def recover(
    ctx: dict[str, Any],
    case: dict[str, Any],
    source: Path,
    output: Path,
    attempt: dict[str, Any],
    resources: dict[str, Any],
    deadline: float,
) -> dict[str, Any]:
    tactical, ordinary = source / "tactical", source / "ordinary"
    report = identified(tactical / "report.json")
    closed = json.loads((tactical / "worker/closed.json").read_text())
    marker = json.loads((source / "active.json").read_text())
    start = identified(ordinary / "native-start.json")
    stop = json.loads((ordinary / "worker/native-process-stop.json").read_text())
    if (
        marker["config_id"] != attempt["config_id"]
        or marker["request"] != case
        or marker["request_id"] != manifest_identifier(case)
        or report["case"] != case
        or report["outcome"] != "act1_loss"
        or report["cap"]
        or closed != report["shutdown"]
        or closed["clean_exit"] is not True
        or start["identity"]["seed"] != case["seed"]
        or start["identity"]["started_with_neow"] is not True
        or stop["process_id"] != start["process_id"]
        or stop["exit"] != {"code": 143, "signal": None, "error": None}
        or not (ordinary / "worker/active.json").is_file()
        or (ordinary / "worker/closed.json").exists()
        or (ordinary / "report.json").exists()
    ):
        raise ValueError(
            "Interrupted world or its clean reference does not match the recovery scope"
        )
    ending = report["native_ending"]
    verify_loss(ending, case["seed"])
    last_identity = deque(
        (
            row["response"]
            for row in records(tactical / "worker/private-transcript.jsonl.gz")
            if row["request"]["cmd"] == "run_identity"
        ),
        maxlen=1,
    )
    if not last_identity or last_identity[0] != ending["private_final_identity"]:
        raise ValueError("Saved tactical loss does not match the raw native ending")

    reference = verify(ctx, case, "tactical", tactical, output / "tactical", [], deadline)
    recovered = verify(
        ctx, case, "ordinary", ordinary, output / "ordinary", [], deadline, interrupted=True
    )
    changed = first_change(tactical / TRACE, ordinary / TRACE)
    if (
        any(not same(v, report[k]) for k, v in reference.items() if k != "act2_reward_exit")
        or reference["initial_public_input_id"] != recovered["initial_public_input_id"]
        or changed is None
        or changed["reason"] != REASON
    ):
        raise ValueError("The recovered world must match its original reference and first change")
    return {
        "status": "saved_boss_reward_exit_recovered",
        "case": case,
        "source_attempt_id": attempt["report_id"],
        "source_resources_id": resources["report_id"],
        "source_chunk_id": chunk_evidence_id(source),
        "tactical_report_id": report["report_id"],
        "original_interruption": attempt["stop"],
        "original_worker_exit": stop["exit"],
        "original_seal_exists": False,
        "ordinary_clean_shutdown": False,
        "ordinary_final_public_trace_frame_recorded": False,
        "fresh_native_replay": False,
        "confirmed_rescue": False,
        "claim_scope": "saved_native_diagnostic_only",
        "first_change": changed,
        "episodes": {"tactical": reference, "ordinary": recovered},
        **NO_UPDATES,
    }
