"""Verify the saved full-menu A8 world-credit fitting and evaluation."""

from __future__ import annotations

import argparse
import fcntl
import json
import math
import os
import time
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any
from unittest.mock import patch

from spireshift import native_win4_game
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path
from spireshift.native_a8_feedback_session import LIMITS, copied_state
from spireshift.native_a8_mix_audit import first_difference, source
from spireshift.native_a8_mix_session import Study, unchanged
from spireshift.native_a8_own_experience import groups, policy
from spireshift.native_a8_own_training import SCOPE, State
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_paired_report import diagnostics, summarize
from spireshift.native_a8_rescue_game import TRACE
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_a8_world_credit import ARMS, DRAWS, FITTED, SETTINGS, run_return
from spireshift.native_a8_world_credit import policy as draw_policy
from spireshift.native_a8_world_credit_reload import MODULE, admitted, require_reloads
from spireshift.native_a8_world_credit_session import AREA, COMPLETE, GATE, journal, tally
from spireshift.native_combat_behavior_data import intervals
from spireshift.native_curriculum_config import THREADS, execution_runtime
from spireshift.native_flow_verification_v12 import records, same

STATUS = "world_credit_saved_verified"


def replay(
    base: Study, directory: Path, out: Path, row: dict[str, Any], state: State, deadline: float
) -> tuple[int, int, str, str]:
    task, model = row["task"], state[0]
    training = task["partition"] == "train"
    start, episode = (identified(directory / name) for name in ("start.json", "report.json"))
    ending = episode["native_ending"]
    identity = ending["private_final_identity"]
    won = row["outcome"] == "win"
    if (
        start["scenario"] != task
        or start["seed"] != task["seed"]
        or start["kind"] != "natural_training"
        or start["save_path"] is not None
        or start["evaluation_eligible"] is not (not training)
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
        or any(row[k] != v for k, v in diagnostics(directory / TRACE, won).items())
    ):
        raise ValueError(
            f"Saved normal start, checkpoint, terminal or shutdown differs: {task['key']}"
        )
    if not training:
        out.mkdir()
        with patch.object(native_win4_game, "policy", policy):
            count = native_win4_game.verify_episode(
                base.ctx, start, "own_policy", directory, out, deadline, model=model
            )
        if count != row["native_decisions"]:
            raise ValueError("The saved evaluation actor does not reproduce its decisions")
    receipts = iter(records(directory / "worker/public-receipts.jsonl.gz"))
    domains = iter(records(directory / "worker/answer-plan-deliveries.jsonl.gz"))
    actual = local = 0
    first_draw = ""
    last = {}
    for group in groups(directory, model.model_id):
        if actual == 0:
            frame, choice = group[0]
            if manifest_identifier(frame["public_input"]) != row["initial_public_input_id"]:
                raise ValueError("Initial public menu differs")
            first_draw = choice["draw_key"]
            if training:
                replayed = draw_policy(base.ctx, start, "own_policy", model).choose(frame)
                if not same(replayed, choice):
                    raise ValueError("The declared independent policy draw does not reconstruct")
        for frame, choice in group:
            receipt, domain = next(receipts), next(domains)
            raw_id = frame["observation"]["snapshot_id"]
            if (
                receipt["snapshot_id"] != raw_id
                or receipt["action"]["bound_action_id"] != choice["bound_action_id"]
                or receipt["delivery"] != "delivered"
                or domain["before_snapshot_id"] != raw_id
                or domain["action_id"] != choice["bound_action_id"]
                or domain["successor_snapshot_id"] != receipt["successor_snapshot_id"]
                or "credit_root" in choice
            ):
                raise ValueError("Native choice ownership or delivery differs")
        last = group[0][0]
        actual += 1
        local += len(group) - 1
    if (
        actual != row["native_decisions"]
        or actual != episode["actual_deliveries_independently_verified"]
        or local != row["local_answer_factors"]
        or local != episode["local_answer_factors"]
        or next(receipts, None) is not None
        or next(domains, None) is not None
    ):
        raise ValueError("Native receipt or local-factor count differs")
    encounter = last["public_input"]["context"]["interaction"]["content"]["context"]
    return actual, local, first_draw, str(encounter.get("encounter_type", last["source_family"]))


def assess(root: Path, attempt: int, deadline: float) -> dict[str, Any]:
    base, cfg, reload_cfg, short_states = admitted(root)
    short = require_reloads(base, reload_cfg, short_states)
    before = frozen(root, base.ctx)
    store = journal(root, cfg, False)
    owner_path = store.workspace / f"attempt-{attempt}.json"
    resource_path = store.workspace.with_name(f"{store.workspace.name}-{attempt}-resources.json")
    owner, resource = (identified(path) for path in (owner_path, resource_path))
    plan = cfg["study"]
    keys = {t["key"] for tasks in plan.values() for t in tasks}
    if (
        owner["status"] != COMPLETE
        or owner["config_id"] != store.config_id
        or owner["stop"] is not None
        or owner["frozen_checks"] != before
        or owner["shared_profile_unchanged"] is not True
        or owner["original_optimizer_updates"] != 0
        or owner["forced_action_probes_used"] != 0
        or any(owner[k] is not v for k, v in SCOPE.items())
        or set(owner["games"]) != keys
        or set(owner["seals"]) != keys | {f"fit-p{p}" for p in PLAYERS}
        or resource["status"] != "completed"
        or resource["exit_code"] != 0
        or resource["cap"] is not None
        or resource["limits"] != LIMITS
        or resource["artifacts"]["roots"] != [str(store.workspace)]
        or resource["command"]
        != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--study", str(attempt)]
    ):
        raise ValueError("Require the exact completed owner world-credit comparison")
    out = _private_path(root, f"{AREA}/assessment-v3-{attempt}")
    out.mkdir()
    states = {(p, "original"): state for p, state in base.originals.items()}
    rows: dict[str, dict[str, Any]] = {}
    initials: dict[str, str] = {}
    counts: Counter[str] = Counter()
    train_draws: dict[tuple[int, str], set[str]] = defaultdict(set)
    owners: dict[str, Counter[str]] = {arm: Counter() for arm in ARMS}

    def sealed_game(task: dict[str, Any], state: State) -> None:
        key = task["key"]
        seal = store.completed(key, {"task": task, "state_id": state[2]})
        if seal is None or seal["report_id"] != owner["seals"][key]:
            raise ValueError(f"Missing game seal for {key}")
        row = seal["result"]
        if (
            row != owner["games"][key]
            or row["task"] != task
            or row["model_id"] != state[0].model_id
            or row["outcome"] not in {"win", "loss"}
            or initials.setdefault(task["seed"], row["initial_public_input_id"])
            != row["initial_public_input_id"]
        ):
            raise ValueError(f"Native public start or outcome differs for {key}")
        actual, local, draw, terminal_owner = replay(
            base, store.path(key), out / key, row, state, deadline
        )
        counts.update(sealed_files=len(seal["sources"]), local_factors=local)
        if task["partition"] == "train":
            train_draws[task["player"], task["seed"]].add(draw)
            counts["training_choices"] += actual
        else:
            counts["evaluation_choices"] += actual
            owners[task["arm"]][terminal_owner] += row["outcome"] == "loss"
        rows[key] = row

    with (store.workspace / "session.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        if json.loads((store.workspace / "config-at-launch.json").read_text()) != cfg:
            raise ValueError("The saved owner recipe changed")
        for task in plan["training"]:
            sealed_game(task, states[task["player"], "original"])
        if any(len(draws) != DRAWS for draws in train_draws.values()):
            raise ValueError("Expected three independent model draws per training world")
        print(f"Verified {len(plan['training'])} saved training runs.", flush=True)
        varied = {}
        for p in PLAYERS:
            train = [t for t in plan["training"] if t["player"] == p]
            original = states[p, "original"]
            returns: dict[str, list[float]] = defaultdict(list)
            for task in train:
                returns[task["seed"]].append(run_return(rows[task["key"]], base.ctx["score"]))
            varied[str(p)] = sum(len(set(batch)) > 1 for batch in returns.values())
            key = f"fit-p{p}"
            request = {
                "player": p,
                "original_id": original[2],
                "training_seals": [owner["seals"][t["key"]] for t in train],
            }
            seal = store.completed(key, request)
            if seal is None or seal["report_id"] != owner["seals"][key]:
                raise ValueError("Missing exact fitted state")
            fit = seal["result"]
            choices = sum(rows[t["key"]]["native_decisions"] for t in train)
            if (
                fit != owner["fits"][str(p)]
                or fit["training_returns"] != returns
                or fit["varied_worlds"] != varied[str(p)]
                or fit["varied_worlds"] < GATE["study"]
                or fit["training_games"] != len(train)
                or fit["native_decisions"] != choices
                or fit["optimizer_updates_per_copy"]
                != math.ceil(choices / SETTINGS["minibatch_decisions"])
                or fit["initial_behavior_kl"] > 1e-12
            ):
                raise ValueError("Training eligibility or matched optimizer work differs")
            counts["sealed_files"] += len(seal["sources"])
            for arm in FITTED:
                fitted = copied_state(store, p, arm, fit)
                if (
                    fitted[1].steps - original[1].steps != fit["optimizer_updates_per_copy"]
                    or fit["work"][arm]["final_behavior_joint_kl"] > SETTINGS["target_kl"]
                    or fitted[0].actor.genome == original[0].actor.genome
                ):
                    raise ValueError("A fitted copy differs from its declared work")
                states[p, arm] = fitted
            pooled, within = (states[p, arm][0] for arm in FITTED)
            if (
                pooled.actor.genome == within.actor.genome
                or (pooled.value_weights == within.value_weights) != fit["critics_exactly_matched"]
            ):
                raise ValueError("Actor or critic comparison differs")
        if owner["varied_worlds_by_initializer"] != varied or owner[
            "optimizer_updates_on_copies"
        ] != 2 * sum(fit["optimizer_updates_per_copy"] for fit in owner["fits"].values()):
            raise ValueError("Saved fitting gate or total optimizer work differs")
        for i, task in enumerate(plan["evaluation"], 1):
            sealed_game(task, states[task["player"], task["arm"]])
            if i % 12 == 0:
                print(f"Reconstructed {i}/{len(plan['evaluation'])} evaluation games.", flush=True)
        unchanged(base, before, deadline)
        after = admitted(root)
        if (
            require_reloads(after[0], after[2], after[3]) != short
            or execution_runtime(base.ctx["node"]) != base.runtime
        ):
            raise ValueError("Frozen admission or execution runtime differs")

    for part in ("training", "evaluation"):
        if tally(plan[part], rows, None) != owner[part]:
            raise ValueError("Saved completion denominator differs")
    worlds = list(dict.fromkeys(t["seed"] for t in plan["evaluation"]))
    games = {(t["seed"], t["player"], t["arm"]): rows[t["key"]] for t in plan["evaluation"]}
    comparisons = {}
    for a, b in (("pooled", "within_world"), ("original", "pooled"), ("original", "within_world")):
        pair = f"{b}_minus_{a}"
        summary = summarize(
            worlds,
            {
                (w, p, "original" if arm == a else "fitted"): row
                for (w, p, arm), row in games.items()
                if arm in (a, b)
            },
        )
        if owner["development"][pair] != {"reference_arm": a, "candidate_arm": b, **summary}:
            raise ValueError("Saved matched win comparison differs")
        floor_deltas, identical_traces = [], 0
        for w in worlds:
            world_deltas = []
            for p in PLAYERS:
                left, right = (games[w, p, arm] for arm in (a, b))
                world_deltas.append(right["maximum_floor"] - left["maximum_floor"])
                if (
                    first_difference(
                        store.path(left["task"]["key"]) / TRACE,
                        store.path(right["task"]["key"]) / TRACE,
                    )
                    is None
                ):
                    identical_traces += 1
            floor_deltas.append(world_deltas)
        flat = [d for batch in floor_deltas for d in batch]
        comparisons[pair] = {
            "mean_floor_delta": fmean(flat),
            "floor_delta_interval_95_descriptive": intervals(
                [[*d, fmean(d), 0.0] for d in floor_deltas]
            )[2],
            "higher": sum(d > 0 for d in flat),
            "tied": flat.count(0),
            "lower": sum(d < 0 for d in flat),
            "same_choices_entire_trace": identical_traces,
            "win_rate_difference": summary["pooled_fitted_minus_original_win_rate_bounds"],
        }
    arms = {}
    for arm in ARMS:
        evaluation = [row for (_, _, name), row in games.items() if name == arm]
        arms[arm] = {
            "planned_games": len(evaluation),
            "wins": sum(row["outcome"] == "win" for row in evaluation),
            "act1_clears": sum(row["completed_acts"] >= 1 for row in evaluation),
            "act1_bosses_reached": sum(
                any(b["act"] == 1 for b in row["bosses_reached"]) for row in evaluation
            ),
            "mean_maximum_floor": fmean(row["maximum_floor"] for row in evaluation),
            "losses_by_last_owner": dict(owners[arm]),
        }
    return native_win4_game.write(
        out / "report.json",
        {
            "schema_version": "native-a8-world-credit-saved-audit-v1",
            "status": STATUS,
            "owner": source(root, owner_path),
            "resources": source(root, resource_path),
            "config_id": store.config_id,
            "environment_id": cfg["environment_id"],
            "training": owner["training"],
            "evaluation": owner["evaluation"],
            "varied_worlds_by_initializer": varied,
            "minimum_varied_worlds_per_initializer": GATE["study"],
            "fitting_qualified": True,
            "optimizer_updates_on_copies": owner["optimizer_updates_on_copies"],
            "fits": owner["fits"],
            "audit_counts": dict(counts),
            "arms": arms,
            "comparisons": comparisons,
            "frozen_checks": before,
            "native_game_launches": 0,
            "optimizer_updates_during_audit": 0,
            **SCOPE,
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt", type=int)
    args = parser.parse_args()
    if any(os.environ.get(name) != "1" for name in THREADS):
        raise SystemExit("Use the pinned numerical environment")
    report = assess(Path.cwd(), args.attempt, time.monotonic() + 270)
    print(json.dumps({k: v for k, v in report.items() if k != "fits"}, indent=2))
