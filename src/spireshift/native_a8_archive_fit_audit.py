"""Verify the saved A8 archive comparison and summarize full-menu play."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
import time
from collections import Counter
from pathlib import Path
from statistics import fmean
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.native_a8_archive_fit_inputs import LIMITS, UPDATES, ArchiveFit, archive_fit
from spireshift.native_a8_archive_fit_session import (
    COMPLETE,
    MODULE,
    check_inputs,
    development_result,
    fit_request,
    journal,
    require_control,
    resource_path,
    tasks,
)
from spireshift.native_a8_mix_audit import first_difference, replay, source
from spireshift.native_a8_own_experience import groups
from spireshift.native_a8_own_training import SCOPE, restored
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_paired_report import ARMS
from spireshift.native_a8_rescue_game import TRACE
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_curriculum_config import THREADS

SHORT_SECONDS = 260


def combat_choices(directory: Path, model_id: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for answer in groups(directory, model_id):
        for frame, choice in answer:
            if frame["source_family"] != "combat_turn":
                continue
            public = frame["public_input"]
            candidates = public["candidates"]
            selected = candidates[choice["action_index"]]["verb"]
            verbs = {candidate["verb"] for candidate in candidates}
            counts[f"selected_{selected}"] += 1
            if {"play", "end_turn"} <= verbs:
                counts["play_or_end_turn_offered"] += 1
                counts["end_turn_with_card_play_offered"] += selected == "end_turn"
            if "use" in verbs:
                counts["potion_use_offered"] += 1
    return counts


def assess(study: ArchiveFit, output: Path, deadline: float) -> dict[str, Any]:
    base, store = study.base, journal(study, False)
    root = base.root
    plan = tasks(study, False)
    control_id = require_control(study)
    before = study.frozen_checks
    states = {(p, "original"): base.originals[p] for p in PLAYERS}
    outcomes, traces = {}, {}
    initials: dict[str, str] = {}
    families = {(p, arm): Counter[str]() for p in PLAYERS for arm in ARMS}
    combat = {(p, arm): Counter[str]() for p in PLAYERS for arm in ARMS}
    deaths = {(p, arm): Counter[str]() for p in PLAYERS for arm in ARMS}
    files = 0
    with (store.workspace / "session.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        report_path, resources_path = store.workspace / "report.json", resource_path(store)
        report, resource = identified(report_path), identified(resources_path)
        keys = {task["key"] for task in plan}
        if (
            json.loads((store.workspace / "config-at-launch.json").read_text()) != store.recipe
            or report["status"] != COMPLETE
            or report["config_id"] != store.config_id
            or report["objective"] != study.cfg["objective"]
            or report["archive_bank_id"] != study.bank["report_id"]
            or report["control_id"] != control_id
            or report["stop"] is not None
            or report["frozen_checks"] != before
            or report["shared_profile_unchanged"] is not True
            or report["copied_optimizer_updates"] != UPDATES * len(PLAYERS)
            or report["original_optimizer_updates"] != 0
            or report["evaluation_optimizer_updates"] != 0
            or any(report[k] is not v for k, v in SCOPE.items())
            or report["planned_games"] != len(plan)
            or report["terminal_games"] != len(plan)
            or set(report["games"]) != keys
            or set(report["seals"]) != keys | {f"fit-p{p}" for p in PLAYERS}
            or resource["status"] != "completed"
            or resource["exit_code"] != 0
            or resource["cap"] is not None
            or resource["limits"] != LIMITS
            or resource["command"]
            != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--execute", "study"]
            or resource["artifacts"]["roots"] != [str(store.workspace)]
        ):
            raise ValueError("Require the exact completed A8 archive comparison")
        for p in PLAYERS:
            key = f"fit-p{p}"
            seal = store.completed(key, fit_request(study, p, UPDATES))
            if (
                seal is None
                or seal["report_id"] != report["seals"][key]
                or seal["result"] != report["fits"][str(p)]
            ):
                raise ValueError("The fitted copy seal differs")
            states[p, "fitted"] = restored(store, key, seal)
            files += len(seal["sources"])

        for task in plan:
            key, seed, p, arm = (task[k] for k in ("key", "seed", "player", "arm"))
            model, _, state_id = states[p, arm]
            seal = store.completed(
                key, {"task": task, "state_id": state_id, "control_id": control_id}
            )
            if seal is None or seal["report_id"] != report["seals"][key]:
                raise ValueError(f"The saved game seal differs for {key}")
            row = seal["result"]
            if (
                row != report["games"][key]
                or row["task"] != task
                or row["model_id"] != model.model_id
                or row["outcome"] not in {"win", "loss"}
                or initials.setdefault(seed, row["initial_public_input_id"])
                != row["initial_public_input_id"]
            ):
                raise ValueError(f"The matched opening, checkpoint or ending differs for {key}")
            directory = store.path(key)
            observed, owner = replay(base, directory, output / key, row, model, deadline)
            families[p, arm].update(observed)
            combat[p, arm].update(combat_choices(directory, model.model_id))
            if row["outcome"] == "loss":
                deaths[p, arm][owner] += 1
            outcomes[seed, p, arm], traces[seed, p, arm] = row, directory / TRACE
            files += len(seal["sources"])

        development = development_result(study, outcomes)
        if report["development"] != development:
            raise ValueError("The paired development result does not reconstruct")
        comparisons: dict[str, Any] = {}
        for p in PLAYERS:
            arms: dict[str, Any] = {}
            for arm in ARMS:
                games = [outcomes[seed, p, arm] for seed in study.cfg["development"]]
                arms[arm] = {
                    "mean_maximum_floor": fmean(game["maximum_floor"] for game in games),
                    "act1_boss_reaches": sum(
                        any(boss["act"] == 1 for boss in game["bosses_reached"]) for game in games
                    ),
                    "losses_by_owner": dict(deaths[p, arm]),
                    "native_decisions_by_owner": dict(families[p, arm]),
                    "combat_choice_counts": dict(combat[p, arm]),
                }
            differences = Counter(
                (
                    outcomes[seed, p, "fitted"]["maximum_floor"]
                    > outcomes[seed, p, "original"]["maximum_floor"]
                )
                - (
                    outcomes[seed, p, "fitted"]["maximum_floor"]
                    < outcomes[seed, p, "original"]["maximum_floor"]
                )
                for seed in study.cfg["development"]
            )
            first = [
                first_difference(traces[seed, p, "original"], traces[seed, p, "fitted"])
                for seed in study.cfg["development"]
            ]
            comparisons[str(p)] = {
                "arms": arms,
                "fitted_floor_comparison": {
                    "ahead": differences[1],
                    "tied": differences[0],
                    "behind": differences[-1],
                },
                "first_changed_action_by_owner": dict(
                    Counter(row["family"] for row in first if row is not None)
                ),
            }
        check_inputs(study)
        if frozen(root, base.ctx) != before:
            raise ValueError("Frozen game or checkpoint inputs changed during the audit")
        return {
            "schema_version": "native-a8-archive-copy-fit-audit-v1",
            "comparison": source(root, report_path),
            "resources": source(root, resources_path),
            "archive_bank_id": study.bank["report_id"],
            "games_verified": len(outcomes),
            "sealed_files_verified": files,
            "native_deliveries_reconstructed": sum(sum(v.values()) for v in families.values()),
            "local_answer_factors": sum(row["local_answer_factors"] for row in outcomes.values()),
            "development": development,
            "diagnostics": comparisons,
            "frozen_checks": before,
            "optimizer_updates": 0,
        }


def main() -> None:
    if any(os.environ.get(name) != "1" for name in THREADS):
        raise ValueError("Use the frozen single-thread numerical settings")
    deadline = time.monotonic() + SHORT_SECONDS
    study = archive_fit(Path.cwd())
    with tempfile.TemporaryDirectory(prefix="spireshift-archive-fit-audit-") as output:
        result = assess(study, Path(output), deadline)
    print(json.dumps({**result, "report_id": manifest_identifier(result)}, sort_keys=True))


if __name__ == "__main__":
    main()
