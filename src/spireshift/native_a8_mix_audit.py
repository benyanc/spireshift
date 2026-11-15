"""Independently reconstruct the saved matched A8 practice comparison."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import time
from collections import Counter
from contextlib import closing
from pathlib import Path
from statistics import fmean
from typing import Any
from unittest.mock import patch

from spireshift import native_win4_game
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_feedback_session import LIMITS
from spireshift.native_a8_mix_fit import ARMS
from spireshift.native_a8_mix_session import (
    AREA,
    COMPLETE,
    MODULE,
    Study,
    admit,
    require_prepared,
    tasks,
    unchanged,
)
from spireshift.native_a8_own_experience import groups, policy
from spireshift.native_a8_own_training import SCOPE
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_paired_report import diagnostics, summarize
from spireshift.native_a8_rescue_game import TRACE, decisions
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS, execution_runtime

STATUS = "matched_practice_saved_verified"


def source(root: Path, path: Path) -> dict[str, str]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": _sha_file(path),
        "report_id": identified(path)["report_id"],
    }


def first_difference(left: Path, right: Path) -> dict[str, Any] | None:
    with closing(decisions(left)) as normal, closing(decisions(right)) as mixed:
        for (_, before, a), (_, after, b) in zip(normal, mixed, strict=True):
            if before["public_input"] != after["public_input"] or (a is None) != (b is None):
                raise ValueError("Native public input diverged before the first different action")
            if a is None or b is None:
                return None
            i, j = a["choice"]["action_index"], b["choice"]["action_index"]
            if i != j:
                public = before["public_input"]
                return {
                    "floor": public["context"]["persistent"]["run"]["floor"],
                    "family": before["source_family"],
                    "same_display_label": public["candidates"][i]["label"]
                    == public["candidates"][j]["label"],
                }
    raise ValueError("Saved trace is missing its final public observation")


def replay(
    study: Study, directory: Path, output: Path, game: dict[str, Any], model: Any, deadline: float
) -> tuple[Counter[str], str]:
    task, trace = game["task"], directory / TRACE
    start, episode = (identified(directory / name) for name in ("start.json", "report.json"))
    ending = episode["native_ending"]
    identity = ending["private_final_identity"]
    won = game["outcome"] == "win"
    if (
        start["scenario"] != task
        or start["seed"] != task["seed"]
        or start["kind"] != "natural_training"
        or start["save_path"] is not None
        or start["evaluation_eligible"] is not True
        or episode["start_id"] != start["report_id"]
        or episode["report_id"] != game["episode_report_id"]
        or episode["status"] != "complete"
        or episode["optimizer_updates"] != 0
        or episode["model_id"] != model.model_id
        or episode["initial_public_input_id"] != game["initial_public_input_id"]
        or episode["native_terminal"] is not True
        or episode["full_run_win"] is not won
        or ending["native_ending_evidence_agrees"] is not True
        or identity["seed"] != task["seed"]
        or identity["ascension"] != 8
        or identity["native_victory_room"] is not won
        or (won and identity["native_game_over"] is not True)
        or (not won and not (identity["native_game_over"] or identity["native_player_dead"]))
        or episode["shutdown"]["clean_exit"] is not True
        or episode["shutdown"]["runtime_errors"]
        or ending["usage"]["native_cpu_seconds"] != game["native_cpu_seconds"]
        or game["native_cpu_seconds"] > study.ctx["score"].evaluation_objective.whole_run_budget
    ):
        raise ValueError("Saved start, checkpoint, native ending or shutdown differs")
    output.mkdir()
    with patch.object(native_win4_game, "policy", policy):
        count = native_win4_game.verify_episode(
            study.ctx, start, "own_policy", directory, output, deadline, model=model
        )
    families: Counter[str] = Counter()
    offered: set[str] = set()
    local = 0
    previous = None
    for group in groups(directory, model.model_id):
        initial = manifest_identifier(group[0][0]["public_input"]) if previous is None else None
        if initial is not None and initial != game["initial_public_input_id"]:
            raise ValueError("Saved initial public menu differs")
        previous = group[0][0]
        families[previous["source_family"]] += 1
        offered.update(frame["source_family"] for frame, _ in group)
        local += len(group) - 1
    if (
        previous is None
        or count != game["native_decisions"]
        or count != episode["actual_deliveries_independently_verified"]
        or count != sum(families.values())
        or local != game["local_answer_factors"]
        or local != episode["local_answer_factors"]
        or offered != set(episode["families"])
        or any(game[k] != v for k, v in diagnostics(trace, won).items())
    ):
        raise ValueError("Saved choices, native receipts or public diagnostics differ")
    context = previous["public_input"]["context"]["interaction"]["content"]["context"]
    owner = context.get("encounter_type", previous["source_family"])
    return families, str(owner)


def assess(root: Path, attempt: int, deadline: float) -> dict[str, Any]:
    study = admit(root)
    store = ChunkJournal(root, study.cfg)
    proof, states = require_prepared(study)
    before = frozen(root, study.ctx)
    report_path = store.workspace / f"attempt-{attempt}.json"
    resource_path = store.workspace.with_name(f"{store.workspace.name}-{attempt}-resources.json")
    report, resource = (identified(path) for path in (report_path, resource_path))
    plan = tasks(study.cfg)
    if (
        report["status"] != COMPLETE
        or report["config_id"] != store.config_id
        or report["preparation_id"] != proof["report_id"]
        or report["planned_worlds"] != study.cfg["development"]
        or report["planned_games"] != len(plan)
        or report["terminal_games"] != len(plan)
        or report["stop"] is not None
        or report["optimizer_updates"] != 0
        or report["frozen_checks"] != before
        or any(report[k] is not v for k, v in SCOPE.items())
        or set(report["games"]) != {task["key"] for task in plan}
        or resource["status"] != "completed"
        or resource["exit_code"] != 0
        or resource["cap"] is not None
        or resource["limits"] != LIMITS
        or resource["command"]
        != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--execute-study", str(attempt)]
        or resource["artifacts"]["roots"] != [str(store.workspace)]
    ):
        raise ValueError("Require the exact completed owner comparison")
    out = _private_path(root, f"{AREA}/assessment-v2-{attempt}")
    out.mkdir()
    rows, traces = {}, {}
    initials: dict[str, str] = {}
    counts: dict[str, Counter[str]] = {arm: Counter() for arm in ARMS}
    losses: dict[str, Counter[str]] = {arm: Counter() for arm in ARMS}
    files = 0
    with (store.workspace / "session.lock").open("rb") as handle:
        fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
        if json.loads((store.workspace / "config-at-launch.json").read_text()) != study.cfg:
            raise ValueError("The comparison recipe changed after launch")
        for index, task in enumerate(plan, 1):
            key, seed, player, arm = (task[k] for k in ("key", "seed", "player", "arm"))
            model, _, state_id = states[player, arm]
            request = {"task": task, "state_id": state_id, "preparation_id": proof["report_id"]}
            seal = store.completed(key, request)
            if seal is None:
                raise ValueError(f"Missing saved comparison seal for {key}")
            game = seal["result"]
            initial = game["initial_public_input_id"]
            if (
                {"seal_id": seal["report_id"], **game} != report["games"][key]
                or game["outcome"] not in {"win", "loss"}
                or game["task"] != task
                or game["model_id"] != model.model_id
                or initials.setdefault(seed, initial) != initial
            ):
                raise ValueError(f"Saved comparison identity differs for {key}")
            directory = store.path(key)
            families, owner = replay(study, directory, out / key, game, model, deadline)
            counts[arm].update(families)
            if game["outcome"] == "loss":
                losses[arm][owner] += 1
            rows[seed, player, arm], traces[seed, player, arm] = game, directory / TRACE
            files += len(seal["sources"])
            if index % 12 == 0:
                print(f"Verified {index}/{len(plan)} saved native games.", flush=True)
        differences = {}
        for left, right in (("normal", "mixed"), ("original", "normal"), ("original", "mixed")):
            pair = f"{right}_minus_{left}"
            expected = {
                "reference_arm": left,
                "candidate_arm": right,
                **summarize(
                    study.cfg["development"],
                    {
                        (seed, player, "original" if arm == left else "fitted"): row
                        for (seed, player, arm), row in rows.items()
                        if arm in (left, right)
                    },
                ),
            }
            if report["development"][pair] != expected:
                raise ValueError("The saved paired result does not reconstruct")
            changes, floors = [], []
            for seed in study.cfg["development"]:
                for player in PLAYERS:
                    a, b = (seed, player, left), (seed, player, right)
                    floors.append(rows[b]["maximum_floor"] - rows[a]["maximum_floor"])
                    change = first_difference(traces[a], traces[b])
                    if change:
                        changes.append(change)
            differences[pair] = {
                "win_rate_difference": expected["pooled_fitted_minus_original_win_rate_bounds"],
                "floor_mean_difference": fmean(floors),
                "floor_higher": sum(floor > 0 for floor in floors),
                "floor_same": floors.count(0),
                "floor_lower": sum(floor < 0 for floor in floors),
                "pairs_with_a_different_action": len(changes),
                "first_difference_floors": dict(
                    Counter(str(change["floor"]) for change in changes)
                ),
                "first_difference_families": dict(Counter(change["family"] for change in changes)),
                "first_different_action_with_same_label": sum(
                    change["same_display_label"] for change in changes
                ),
            }
        unchanged(study, before, deadline)
        if (
            require_prepared(study)[0] != proof
            or execution_runtime(study.ctx["node"]) != study.runtime
        ):
            raise ValueError("The compared full states or numerical runtime changed during audit")

    arms = {}
    for arm in ARMS:
        games = [row for (_, _, name), row in rows.items() if name == arm]
        arms[arm] = {
            "games": len(games),
            "wins": sum(row["outcome"] == "win" for row in games),
            "act1_clears": sum(row["completed_acts"] >= 1 for row in games),
            "act1_bosses_reached": sum(
                any(b["act"] == 1 for b in row["bosses_reached"]) for row in games
            ),
            "mean_maximum_floor": fmean(row["maximum_floor"] for row in games),
            "native_decisions": sum(counts[arm].values()),
            "local_answer_factors": sum(row["local_answer_factors"] for row in games),
            "losses_by_last_owner": dict(losses[arm]),
            "native_decisions_by_family": dict(counts[arm]),
            "shop_open_and_close": sum(
                n
                for row in games
                for label, n in row["shop_actions"].items()
                if label in {"Open inventory", "Close shop inventory"}
            ),
        }
    return native_win4_game.write(
        out / "report.json",
        {
            "schema_version": "native-a8-matched-practice-saved-audit-v2",
            "status": STATUS,
            "owner_report": source(root, report_path),
            "owner_resources": source(root, resource_path),
            "preparation_id": proof["report_id"],
            "config_id": store.config_id,
            "environment_id": study.cfg["environment_id"],
            "worlds": len(initials),
            "sealed_terminal_games": len(rows),
            "sealed_files_verified": files,
            "actual_native_deliveries_verified": sum(n["native_decisions"] for n in arms.values()),
            "arms": arms,
            "comparisons": differences,
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
    print(json.dumps(assess(Path.cwd(), args.attempt, time.monotonic() + 255), indent=2))
