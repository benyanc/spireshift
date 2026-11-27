"""Audit the stopped study without gameplay or updates; preserve its failed chunk."""

from __future__ import annotations

import json
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_own_experience import groups
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_combat_intent_model import load as load_state
from spireshift.native_combat_intent_model import using_intent_encoder
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_flow_verification_v12 import records
from spireshift.native_qualified_learning_inputs_v2 import RECIPE, context, load
from spireshift.native_qualified_learning_verification_v2 import verify_episode
from spireshift.native_win4_game import write

FAILED = "train-0571-p3-learner"
WORKSPACE = "artifacts/native-qualified-learning/recovery-v1"
STATUS = "qualified_learning_saved_prefix_and_checker_repair_verified"


def task(seed: str, index: int, player: int, round_index: int) -> dict[str, Any]:
    return {
        "key": f"train-{index:04d}-p{player}-learner",
        "seed": seed,
        "seed_id": index,
        "player": player,
        "round": round_index,
        "partition": "train",
        "arm": "shared",
    }


def audit(root: Path) -> dict[str, Any]:
    cfg = load(root)
    ctx = context(root, cfg)
    before = frozen(root, ctx)
    profile = _shared_snapshot(Path.home() / SHARED_PROFILE)
    output = root / WORKSPACE
    output.mkdir(parents=True, exist_ok=True)
    report = output / "report.json"
    if report.exists():
        result = identified(report)
        check_sources(root, result["sources"])
        if result["frozen_checks"] != before:
            raise ValueError("Frozen inputs changed after saved assessment")
        return result
    store = ChunkJournal(root, cfg)
    units: dict[str, str] = {}
    sources = {RECIPE: _sha_file(root / RECIPE)}
    counts: dict[str, Any] = {}
    updates = 0
    states = {p: load_state(verified(root, cfg["starting_states"][str(p)])) for p in (2, 3)}
    failed_request: dict[str, Any] | None = None
    with store.lock():
        control = root / cfg["control_workspace"] / "report.json"
        control_result = identified(control)
        check_sources(root, control_result["sources"])
        sources[str(control.relative_to(root))] = _sha_file(control)
        if control_result["status"] != "qualified_model_only_collect_fit_reload_verified":
            raise ValueError("The exact collect/fit/reload control must pass")
        for r in range(1, 65):
            for p in (2, 3):
                rows = []
                for i in range((r - 1) * 16 + 1, r * 16 + 1):
                    game_task = task(cfg["plan"]["training"][i - 1], i, p, r)
                    request: dict[str, Any] = {"task": game_task, "behavior_state_id": states[p][1]}
                    key = game_task["key"]
                    if key == FAILED:
                        failed_request = request
                        break
                    seal = store.completed(key, request)
                    if seal is None:
                        raise ValueError(f"Unexpected missing predecessor {key}; never replay it")
                    row = seal["result"]
                    if (
                        row["task"] != game_task
                        or row["model_id"] != states[p][0].model.model_id
                        or row["outcome"] not in {"win", "loss", "capped"}
                    ):
                        raise ValueError("A saved game changed model, outcome or world")
                    units[key] = seal["report_id"]
                    sources[str((store.path(key) / "done.json").relative_to(root))] = _sha_file(
                        store.path(key) / "done.json"
                    )
                    rows.append(row)
                    info = counts.setdefault(
                        str(p),
                        {
                            "games": 0,
                            "outcomes": Counter(),
                            "act1_clears": 0,
                            "act2_clears": 0,
                            "sealed_rounds": 0,
                            "optimizer_updates": 0,
                        },
                    )
                    info["games"] += 1
                    info["outcomes"][row["outcome"]] += 1
                    if row["outcome"] in {"win", "loss"}:
                        info["act1_clears"] += row["completed_acts"] >= 1
                        info["act2_clears"] += row["completed_acts"] >= 2
                if failed_request is not None:
                    break
                key = f"fit-p{p}-r{r:03d}"
                request = {
                    "player": p,
                    "round": r,
                    "prior_state_id": states[p][1],
                    "game_seals": [units[row["task"]["key"]] for row in rows],
                }
                seal = store.completed(key, request)
                if seal is None:
                    raise ValueError("A predecessor fit is missing; never repeat its updates")
                row = seal["result"]
                state, state_id = load_state(store.path(key) / "shared.json")
                steps = row["work"]["optimizer_updates"]
                if (
                    state_id != row["state_id"]
                    or state.model.model_id != row["model_id"]
                    or state.actor_adam.steps != states[p][0].actor_adam.steps + steps
                    or state.value_adam.steps != states[p][0].value_adam.steps + steps
                    or row["actor_steps"] != state.actor_adam.steps
                    or row["value_steps"] != state.value_adam.steps
                    or state.model.arm != "shared"
                ):
                    raise ValueError("The saved actor, critic or full Adam lineage changed")
                states[p] = state, state_id
                units[key] = seal["report_id"]
                sources[str((store.path(key) / "done.json").relative_to(root))] = _sha_file(
                    store.path(key) / "done.json"
                )
                updates += steps
                counts[str(p)]["sealed_rounds"] += 1
                counts[str(p)]["optimizer_updates"] += steps
            if failed_request is not None:
                break
        directories = {p.name for p in (store.workspace / "chunks").iterdir() if p.is_dir()}
        if directories != {*units, FAILED} or failed_request is None:
            raise ValueError("Unexpected missing, extra or interrupted study units")
        failed = store.path(FAILED)
        active = json.loads((failed / "active.json").read_text())
        if (
            (failed / "done.json").exists()
            or active["request"] != failed_request
            or active["config_id"] != store.config_id
            or active["request_id"] != manifest_identifier(failed_request)
        ):
            raise ValueError("The failed chunk no longer matches the observed verifier stop")
        legacy = subprocess.run(
            [
                ctx["node"],
                str(root / "scripts/engine-ordered-plan-verify-v1.mjs"),
                str(failed / "worker"),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if legacy.returncode == 0 or "Local plan prefix changed" not in legacy.stderr:
            raise ValueError("The preserved legacy checker failure did not reproduce")
        verification = output / "failed-game-verification"
        verification.mkdir()
        with using_intent_encoder():
            delivered = verify_episode(
                ctx,
                identified(failed / "start.json"),
                "own_policy",
                failed,
                verification,
                time.monotonic() + 75,
                model=states[3][0].model,
            )
        final = None
        for saved in records(failed / "shared-public.jsonl.gz"):
            if saved["kind"] == "final_observation":
                if final is not None:
                    raise ValueError("Extra final observation")
                final = saved["frame"]
        identities = [
            row["response"]
            for row in records(failed / "worker/private-transcript.jsonl.gz")
            if row["request"]["cmd"] == "run_identity" and row["response"].get("active")
        ]
        closed = json.loads((failed / "worker/closed.json").read_text())
        if (
            final is None
            or final["terminal"] is not True
            or final["ending"]["victory"] is not False
            or not identities
            or identities[-1]["seed"] != failed_request["task"]["seed"]
            or identities[-1]["native_player_dead"] is not True
            or identities[-1]["native_game_over"] is not True
            or identities[-1]["action_executor_running"]
            or identities[-1]["pending_host_operation"]
            or closed["clean_exit"] is not True
            or closed["runtime_errors"]
        ):
            raise ValueError("Failed-verification game lacks a clean, genuine saved loss")
        total = local = 0
        for group in groups(failed, states[3][0].model.model_id):
            total += 1
            local += len(group) - 1
        proof = identified(verification / "ordered-answer-raw-verification.json")
        if total != delivered or local != proof["local_factors"]:
            raise ValueError("Saved native decisions and conditional factors disagree")
        for path in failed.rglob("*"):
            if path.is_file():
                sources[str(path.relative_to(root))] = _sha_file(path)
        for path in verification.rglob("*"):
            if path.is_file():
                sources[str(path.relative_to(root))] = _sha_file(path)
        resource_ids = []
        for path in sorted(store.workspace.glob("resources-*.json")):
            resource_ids.append(identified(path)["report_id"])
            sources[str(path.relative_to(root))] = _sha_file(path)
        if frozen(root, ctx) != before or _shared_snapshot(Path.home() / SHARED_PROFILE) != profile:
            raise ValueError(
                "Frozen build, source checkpoints/full Adam or personal profile changed"
            )
        return write(
            report,
            {
                "schema_version": "native-qualified-learning-saved-recovery-v1",
                "status": STATUS,
                "parent_config_id": store.config_id,
                "inherited_units": units,
                "inherited_optimizer_updates": updates,
                "by_initializer": counts,
                "planned_training_games": 2048,
                "sealed_training_games": sum(info["games"] for info in counts.values()),
                "preserved_failed_training_games": 1,
                "unstarted_training_games": 901,
                "planned_development_games": 128,
                "development_games_started": 0,
                "failed_request": failed_request,
                "failed_game_diagnostic": {
                    "outcome": "loss",
                    "native_deliveries": delivered,
                    "local_factors": proof["local_factors"],
                    "native_answer_commits": proof["ordered_answer_native_commits"],
                    "all_choices_and_probabilities_reconstructed": True,
                    "clean_native_ending": True,
                    "training_admitted": False,
                    "legacy_checker_failure_preserved": True,
                },
                "current_states": {str(p): states[p][1] for p in (2, 3)},
                "resource_attempt_ids": resource_ids,
                "frozen_checks": before,
                "personal_profile_unchanged": True,
                "games_launched": 0,
                "optimizer_updates": 0,
                "original_optimizer_updates": 0,
                "promotion_allowed": False,
                "automatic_follow_up": False,
                "sources": sources,
            },
        )


def main() -> int:
    result = audit(Path.cwd())
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "status",
                    "by_initializer",
                    "sealed_training_games",
                    "unstarted_training_games",
                    "failed_game_diagnostic",
                    "inherited_optimizer_updates",
                    "frozen_checks",
                    "report_id",
                )
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
