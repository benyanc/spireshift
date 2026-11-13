"""Saved-only audit of paired A8 choices, native effects, and fitting admission."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_win4_game
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path
from spireshift.native_a8_action_credit_policy import ARMS, STRATA, policy
from spireshift.native_a8_action_credit_session import (
    AREA,
    GATE,
    MODULE,
    RECIPE,
    inputs,
    journal,
    pair,
    require_control,
)
from spireshift.native_a8_feedback_session import LIMITS
from spireshift.native_a8_mix_audit import source
from spireshift.native_a8_mix_session import Study, unchanged
from spireshift.native_a8_own_experience import groups
from spireshift.native_a8_own_training import SCOPE
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_paired_report import diagnostics
from spireshift.native_a8_rescue_game import TRACE, decisions
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_curriculum_config import THREADS, execution_runtime
from spireshift.native_flow_verification_v12 import records

STATUS = "paired_action_credit_saved_verified"


def replay(
    base: Study, path: Path, out: Path, row: dict[str, Any], deadline: float
) -> tuple[int, int]:
    task = row["task"]
    model = base.originals[task["player"]][0]
    start, episode = (identified(path / name) for name in ("start.json", "report.json"))
    ending = episode["native_ending"]
    identity = ending["private_final_identity"]
    won = row["outcome"] == "win"
    if (
        start["scenario"] != task
        or start["seed"] != task["seed"]
        or start["kind"] != "natural_training"
        or start["save_path"] is not None
        or start["evaluation_eligible"] is not False
        or episode["start_id"] != start["report_id"]
        or episode["report_id"] != row["episode_report_id"]
        or episode["model_id"] != model.model_id
        or episode["status"] != "complete"
        or episode["optimizer_updates"] != 0
        or episode["native_terminal"] is not True
        or episode["full_run_win"] is not won
        or episode["shutdown"]["clean_exit"] is not True
        or episode["shutdown"]["runtime_errors"]
        or ending["native_ending_evidence_agrees"] is not True
        or identity["seed"] != task["seed"]
        or identity["ascension"] != 8
        or identity["native_victory_room"] is not won
        or not (identity["native_game_over"] or (not won and identity["native_player_dead"]))
        or ending["usage"]["native_cpu_seconds"] != row["native_cpu_seconds"]
        or row["native_cpu_seconds"] > base.ctx["score"].evaluation_objective.whole_run_budget
        or any(row[k] != v for k, v in diagnostics(path / TRACE, won).items())
    ):
        raise ValueError(f"Saved start, checkpoint, outcome or shutdown differs for {task['key']}")
    out.mkdir()
    with patch.object(native_win4_game, "policy", policy):
        count = native_win4_game.verify_episode(
            base.ctx, start, "own_policy", path, out, deadline, model=model
        )
    actual = local = 0
    for group in groups(path, model.model_id):
        if (
            actual == 0
            and manifest_identifier(group[0][0]["public_input"]) != row["initial_public_input_id"]
        ):
            raise ValueError("Initial public menu differs")
        actual += 1
        local += len(group) - 1
    if (
        count != actual
        or count != row["native_decisions"]
        or count != episode["actual_deliveries_independently_verified"]
        or local != row["local_answer_factors"]
        or local != episode["local_answer_factors"]
    ):
        raise ValueError("Saved native deliveries or local factors differ")
    return actual, local


def map_binding(path: Path) -> tuple[int, int] | None:
    requests = (
        row["request"]["args"]
        for row in records(path / "worker/private-transcript.jsonl.gz")
        if row["request"].get("action") == "select_map_node"
    )
    for _, frame, delivered in decisions(path / TRACE):
        if delivered is None or frame["source_family"] != "map_navigation":
            continue
        choice = delivered["choice"]
        action = frame["public_input"]["candidates"][choice["action_index"]]
        props = (action.get("subject") or {}).get("properties", {})
        position = None
        if {"col", "row", "point_type"} <= props.keys():
            args = next(requests)
            position = (props["col"], props["row"])
            if (args["col"], args["row"]) != position:
                raise ValueError("Native map request does not name the selected destination")
        if choice.get("credit_root"):
            return position
    raise ValueError("No delivered map root in the saved route trace")


def assess(root: Path, attempt: int, deadline: float) -> dict[str, Any]:
    base, cfg = inputs(root)
    require_control(base, cfg)
    before = frozen(root, base.ctx)
    store = journal(root, cfg, False)
    owner_path = store.workspace / f"attempt-{attempt}.json"
    usage_path = store.workspace.with_name(f"{store.workspace.name}-{attempt}-resources.json")
    owner, usage = (identified(path) for path in (owner_path, usage_path))
    cases = cfg["study"]
    gate_passed = owner["status"] == "action_credit_candidate_ready"
    if (
        owner["status"] not in {"action_credit_gate_blocked", "action_credit_candidate_ready"}
        or owner["stop"] is not None
        or owner["config_id"] != store.config_id
        or owner["planned_pairs"] != len(cases)
        or owner["planned_games"] != len(cases) * len(ARMS)
        or set(owner["pairs"]) != {c["key"] for c in cases}
        or set(owner["games"]) != {f"{c['key']}-{a}" for c in cases for a in ARMS}
        or owner["frozen_checks"] != before
        or owner["optimizer_updates"] != 0
        or owner["training_admission_granted"] is not False
        or any(owner[k] is not v for k, v in SCOPE.items())
        or usage["command"]
        != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--collect", str(attempt)]
        or usage["artifacts"]["roots"] != [str(store.workspace)]
        or usage["limits"] != LIMITS
        or usage["cap"] is not None
        or usage["exit_code"] != (0 if gate_passed else 2)
        or usage["status"] != ("completed" if gate_passed else "failed")
    ):
        raise ValueError("Require the complete and exact action-credit pilot")
    out = _private_path(root, f"{AREA}/assessment-v1-{attempt}")
    out.mkdir()
    counts: Counter[str] = Counter()
    outcomes: Counter[str] = Counter()
    strata: Counter[str] = Counter()
    players: Counter[str] = Counter()
    preferred: Counter[str] = Counter()
    map_bindings = {}
    wins = dict.fromkeys(ARMS, 0)
    act1_clears = dict.fromkeys(ARMS, 0)
    bosses_reached = dict.fromkeys(ARMS, 0)
    with (store.workspace / "session.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        if json.loads((store.workspace / "config-at-launch.json").read_text()) != cfg:
            raise ValueError("Saved action-credit recipe differs")
        for ordinal, case in enumerate(cases, 1):
            player = case["player"]
            state = base.originals[player]
            rows = {}
            for arm in ARMS:
                key = f"{case['key']}-{arm}"
                task = {**case, "key": key, "arm": arm}
                seal = store.completed(key, {"task": task, "state_id": state[2]})
                if seal is None:
                    raise ValueError(f"Missing pilot seal for {key}")
                row = seal["result"]
                if (
                    row["task"] != task
                    or row["model_id"] != state[0].model_id
                    or row["outcome"] not in {"win", "loss"}
                    or owner["games"][key]
                    != {"outcome": row["outcome"], "seal_id": seal["report_id"]}
                ):
                    raise ValueError(f"Pilot arm differs for {key}")
                native, local = replay(base, store.path(key), out / key, row, deadline)
                counts.update(
                    games=1,
                    native_deliveries=native,
                    local_factors=local,
                    sealed_files=len(seal["sources"]),
                )
                outcomes[row["outcome"]] += 1
                wins[arm] += row["outcome"] == "win"
                act1_clears[arm] += row["completed_acts"] >= 1
                bosses_reached[arm] += any(b["act"] == 1 for b in row["bosses_reached"])
                rows[arm] = row
            matched = pair(base, store, case, rows)
            if matched != owner["pairs"][case["key"]]:
                raise ValueError("Saved paired root or credit differs")
            credit_root = matched["root"]
            if credit_root is None:
                counts["no_eligible_root"] += 1
            elif not credit_root["different_public_successor"]:
                counts["same_public_successor"] += 1
            elif matched["preferred_arm"] is None:
                counts["changed_successor_tied_return"] += 1
            else:
                counts["informative"] += 1
                strata[case["stratum"]] += 1
                players[str(player)] += 1
                preferred[matched["preferred_arm"]] += 1
            if credit_root and case["stratum"] == "route":
                destinations = {
                    arm: map_binding(store.path(r["task"]["key"])) for arm, r in rows.items()
                }
                if (
                    destinations["reference"] is not None
                    and destinations["reference"] == destinations["alternate"]
                ):
                    raise ValueError("Different route actions must deliver different coordinates")
                map_bindings[case["key"]] = destinations
            if ordinal % 6 == 0:
                print(f"Verified {ordinal}/{len(cases)} saved pairs.", flush=True)
        unchanged(base, before, deadline)
        if (
            json.loads((root / RECIPE).read_text()) != cfg
            or execution_runtime(base.ctx["node"]) != base.runtime
        ):
            raise ValueError("Collection inputs or runtime changed during saved verification")
        check_sources(root, cfg["implementation"])

    checks = {
        "overall": counts["informative"] >= GATE["minimum_pairs"],
        "every_stratum": all(strata[k] >= GATE["minimum_per_stratum"] for k in STRATA),
        "both_initializers": all(
            players[str(p)] >= GATE["minimum_per_initializer"] for p in PLAYERS
        ),
    }
    if (
        outcomes != owner["outcomes"]
        or counts["informative"] != owner["informative_pairs"]
        or strata != owner["informative_by_stratum"]
        or players != owner["informative_by_initializer"]
        or gate_passed != all(checks.values())
    ):
        raise ValueError("Fitting gate does not reconstruct")
    return native_win4_game.write(
        out / "report.json",
        {
            "schema_version": "native-a8-action-credit-saved-audit-v1",
            "status": STATUS,
            "owner": source(root, owner_path),
            "resources": source(root, usage_path),
            "config_id": store.config_id,
            "environment_id": cfg["environment_id"],
            "worlds": len({case["seed"] for case in cases}),
            "complete_pairs": len(cases),
            "counts": dict(counts),
            "outcomes": dict(outcomes),
            "wins_by_arm": wins,
            "act1_clears_by_arm": act1_clears,
            "bosses_reached_by_arm": bosses_reached,
            "preferred_arms": dict(preferred),
            "informative_by_stratum": dict(strata),
            "informative_by_initializer": dict(players),
            "map_root_deliveries": map_bindings,
            "gate": GATE,
            "gate_checks": checks,
            "fitting_candidate": gate_passed,
            "training_admission_granted": False,
            "frozen_checks": before,
            "native_game_launches": 0,
            "optimizer_updates": 0,
            **SCOPE,
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt", type=int)
    args = parser.parse_args()
    if any(os.environ.get(name) != "1" for name in THREADS):
        raise SystemExit("Use the pinned numerical environment")
    print(json.dumps(assess(Path.cwd(), args.attempt, time.monotonic() + 267), indent=2))
