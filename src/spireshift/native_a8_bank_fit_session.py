"""Prepare or run the finite offline two-copy fitting stage, then stop."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_ppo_math import Adam
from spireshift.native_a8_bank_fit import batch, metrics, update, world_schedule
from spireshift.native_a8_bank_fit_inputs import (
    CHUNK,
    CONTROL_CHUNK,
    CONTROL_UPDATES,
    PLAYERS,
    UPDATES,
    binding,
    declaration,
    load,
    verify_frozen,
)
from spireshift.native_compatibility_contract import local
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_curriculum_store import Pause, reserve, snapshot
from spireshift.native_structured_state import load as load_state
from spireshift.native_structured_state import save
from spireshift.native_win4_game import write


def job(ctx: dict[str, Any], *, control: bool) -> dict[str, Any]:
    recipe = ctx["fitting_recipe"]
    return {
        "schema_version": "native-win-copy-fitting-job-v1",
        "workspace": recipe["control_workspace" if control else "workspace"],
        "launch_binding_id": binding(recipe),
        "control": control,
        "bank_id": ctx["bank_id"],
        "dataset_id": ctx["dataset_id"],
        "environment_id": ctx["environment"]["manifest_id"],
        "objective": ctx["objective"].as_dict(),
        "score_id": ctx["score"].spec_id,
        "original_state_ids": {p: row["imported_state_id"] for p, row in ctx["originals"].items()},
        "work": {
            **recipe["work"],
            "updates_per_copy": CONTROL_UPDATES if control else UPDATES,
            "updates_per_chunk": CONTROL_CHUNK if control else CHUNK,
        },
    }


def state_receipt(
    root: Path, path: Path, state_id: str, model: CachedContextModel, adam: Adam
) -> dict[str, Any]:
    return {
        "state_path": str(path.relative_to(root)),
        "state_id": state_id,
        "model_id": model.model_id,
        "optimizer_id": manifest_identifier(adam.as_dict()),
        "optimizer_steps": adam.steps,
    }


def read_state(root: Path, ref: dict[str, Any]) -> tuple[CachedContextModel, Adam]:
    path = local(root, ref["state_path"])
    model, adam, state_id = load_state(path)
    if ref != state_receipt(root, path, state_id, model, adam):
        raise ValueError("Full copied state or Adam changed since its seal")
    return model, adam


def run(
    root: Path,
    ctx: dict[str, Any],
    cfg: dict[str, Any],
    deadline: float,
    *,
    max_new_units: int | None = None,
) -> dict[str, Any]:
    store = ChunkJournal(root, cfg)
    target_report = store.workspace / "report.json"
    updates, chunk = cfg["work"]["updates_per_copy"], cfg["work"]["updates_per_chunk"]
    tasks = [(player, 0, 0) for player in PLAYERS] + [
        (player, start, min(start + chunk, updates))
        for start in range(0, updates, chunk)
        for player in PLAYERS
    ]
    expected = {f"p{player}-u{stop:03d}" for player, _, stop in tasks}
    schedule = world_schedule(ctx["fit"], updates, ctx["bank_id"])
    schedule_id = manifest_identifier(schedule)
    if not cfg["control"] and any(
        len(set(indices)) != len(ctx["fit"][world]) for world, indices in schedule.items()
    ):
        raise ValueError("The main schedule must sample every admitted decision")
    current: dict[int, dict[str, Any]] = {}
    new = 0
    with store.lock():
        for path in (store.workspace / "chunks").glob("*"):
            if path.name not in expected or not (path / "done.json").is_file():
                raise FileExistsError("Preserve an unfinished or foreign fitting unit")
        if target_report.is_file():
            result = identified(target_report)
            if (
                result["status"] != "world_balanced_candidates_frozen"
                or result["job_id"] != store.config_id
                or result["schedule_id"] != schedule_id
            ):
                raise ValueError("The existing fitting result belongs to another job")
            check_sources(root, result["sources"])
            check_sources(root, result["evidence"])
            return result
        sources = dict(ctx["fitting_sources"])
        sources.update(ctx["dataset"]["source_traces"])
        sources.update(
            snapshot(
                {"qualification": ctx["qualification"], "config": ctx["fitting_recipe"]}, store
            )
        )
        try:
            for player, start, stop in tasks:
                key = f"p{player}-u{stop:03d}"
                original = ctx["originals"][str(player)]
                parent = current.get(player)
                request = {
                    "player": player,
                    "start_update": start,
                    "end_update": stop,
                    "schedule_id": schedule_id,
                    "parent_state_id": parent["state_id"]
                    if parent
                    else original["imported_state_id"],
                    "parent_optimizer_id": parent["optimizer_id"]
                    if parent
                    else original["optimizer_id"],
                }
                sealed = store.completed(key, request)
                if sealed is not None:
                    current[player] = sealed["result"]["state"]
                    continue
                reserve(deadline, 20, new, max_new_units)
                check_sources(root, ctx["fitting_recipe"]["implementation"])
                where = store.begin(key, request)
                if parent is None:
                    model, adam = ctx["models"][player], ctx["adams"][player]
                else:
                    model, adam = read_state(root, parent)
                if adam.steps != original["optimizer_steps"] + start:
                    raise ValueError("A fitting unit started from the wrong Adam counter")
                losses = []
                for step in range(start, stop):
                    model, adam, loss = update(model, adam, batch(ctx["fit"], schedule, step))
                    losses.append(loss)
                path = where / "state.json"
                saved = save(path, model, adam)
                ref = state_receipt(root, path, saved["state_id"], model, adam)
                if stop == 0 and (
                    ref["state_id"] != original["imported_state_id"]
                    or ref["optimizer_id"] != original["optimizer_id"]
                ):
                    raise ValueError("The initial copy changed weights or full Adam")
                restored, restored_adam = read_state(root, ref)
                if restored.weights() != model.weights() or restored_adam != adam:
                    raise ValueError("Saved fitting state changed on reload")
                store.commit(
                    key,
                    request,
                    {
                        "state": ref,
                        "optimizer_updates": stop - start,
                        "batch_joint_nll": losses,
                    },
                    ctx["fitting_sources"],
                )
                current[player] = ref
                new += 1
                print(f"Fitting: {key} sealed", flush=True)
        except Pause:
            return {
                "status": "paused_at_clean_fitting_boundary",
                "job_id": store.config_id,
                "resume": "same_owner_command",
                "automatic_follow_up": False,
            }
        candidates = {}
        for player in PLAYERS:
            model, adam = read_state(root, current[player])
            original_model = ctx["models"][player]
            expected_steps = ctx["originals"][str(player)]["optimizer_steps"] + updates
            if adam.steps != expected_steps or model.value_weights != original_model.value_weights:
                raise ValueError("Final copied Adam work or critic weights differ")
            candidates[str(player)] = {
                **current[player],
                "initial_model_id": original_model.model_id,
                "initial_state_id": ctx["originals"][str(player)]["imported_state_id"],
                "initial_optimizer_steps": expected_steps - updates,
                "fit_diagnostics": {
                    "initial": metrics(original_model, ctx["fit"]),
                    "final": metrics(model, ctx["fit"]),
                },
                "development_diagnostics": {
                    "initial": metrics(original_model, ctx["development"]),
                    "final": metrics(model, ctx["development"]),
                },
            }
        checks = verify_frozen(root, ctx)
        return write(
            target_report,
            {
                "schema_version": "native-win-world-balanced-fitting-result-v1",
                "status": "world_balanced_candidates_frozen",
                "job_id": store.config_id,
                "bank_id": ctx["bank_id"],
                "dataset_id": ctx["dataset_id"],
                "environment_id": cfg["environment_id"],
                "objective": cfg["objective"],
                "schedule_id": schedule_id,
                "candidates": candidates,
                "copies": len(PLAYERS),
                "optimizer_updates": len(PLAYERS) * updates,
                "updates_per_copy": updates,
                "draws_per_copy": updates * len(schedule),
                "draws_by_world_per_copy": {world: updates for world in schedule},
                "fixed_final_update": updates,
                "development_cases": ctx["dataset"]["development_cases"],
                "successful_development_teacher_probes": len(ctx["development"]),
                "development_labels_used_for_updates_or_selection": False,
                "critic_weights_unchanged": True,
                "checks_after": checks,
                "game_launches": 0,
                "ordinary_PPO_allowed": False,
                "official_live_qualification_granted": False,
                "full_game_playing_strength_evaluated": False,
                "promotion_allowed": False,
                "automatic_follow_up": False,
                "sources": sources,
                "evidence": {
                    str(p.relative_to(root)): _sha_file(p)
                    for p in store.workspace.rglob("*")
                    if p.is_file() and p.name != "session.lock"
                },
            },
        )


def control(root: Path, ctx: dict[str, Any], deadline: float) -> dict[str, Any]:
    cfg = job(ctx, control=True)
    work = root / cfg["workspace"]
    main = root / ctx["fitting_recipe"]["workspace"]
    if work.exists() or main.exists():
        raise ValueError("The disposable control and main fitting must start in unused workspaces")
    before = verify_frozen(root, ctx)
    paused = run(root, ctx, cfg, deadline, max_new_units=4)
    if (
        paused["status"] != "paused_at_clean_fitting_boundary"
        or len(list((work / "chunks").glob("*/done.json"))) != 4
    ):
        raise ValueError("The short run must stop after both first chunks seal")
    result = run(root, ctx, cfg, deadline)
    if result["status"] != "world_balanced_candidates_frozen":
        raise ValueError("The disposable copies did not reach the fixed final")
    schedule = world_schedule(ctx["fit"], CONTROL_UPDATES, ctx["bank_id"])
    main_schedule = world_schedule(ctx["fit"], UPDATES, ctx["bank_id"])
    if (
        any(
            indices != main_schedule[world][:CONTROL_UPDATES] for world, indices in schedule.items()
        )
        or any(
            len(set(indices)) != len(ctx["fit"][world]) for world, indices in main_schedule.items()
        )
        or set(schedule) & set(ctx["development"])
        or main.exists()
    ):
        raise ValueError("The full declared schedule lost coverage or split isolation")
    checked = {}
    for player in PLAYERS:
        model, adam = ctx["models"][player], ctx["adams"][player]
        for step in range(CONTROL_UPDATES):
            model, adam, _ = update(model, adam, batch(ctx["fit"], schedule, step))
        ref = result["candidates"][str(player)]
        stored, moments = read_state(
            root,
            {
                key: ref[key]
                for key in ("state_path", "state_id", "model_id", "optimizer_id", "optimizer_steps")
            },
        )
        if (
            stored.as_dict() != model.as_dict()
            or moments != adam
            or stored.actor.genome == ctx["models"][player].actor.genome
        ):
            raise ValueError("Resume must reproduce uninterrupted weights and all Adam exactly")
        checked[str(player)] = {
            "optimizer_steps": adam.steps,
            "state_id": ref["state_id"],
            "fit_diagnostics": ref["fit_diagnostics"],
            "development_diagnostics": ref["development_diagnostics"],
        }
    return write(
        work / "control.json",
        {
            "schema_version": "native-win-world-balanced-fitting-control-v1",
            "status": "world_balanced_copy_fitting_control_verified",
            "launch_binding_id": cfg["launch_binding_id"],
            "bank_id": ctx["bank_id"],
            "dataset_id": ctx["dataset_id"],
            "copy_updates": len(PLAYERS) * CONTROL_UPDATES,
            "uninterrupted_reconstruction_updates": len(PLAYERS) * CONTROL_UPDATES,
            "copy_results": checked,
            "dataset": ctx["dataset"],
            "checks_before": before,
            "checks_after": verify_frozen(root, ctx),
            "checks": {
                "warm_full_adam_copy_and_reload": True,
                "resume_matches_uninterrupted_full_state": True,
                "equal_world_draws_and_complete_main_coverage": True,
                "development_separate_from_fitting": True,
                "critic_weights_preserved": True,
            },
            "main_fitting_started": False,
            "control_states_enter_main": False,
            "game_launches": 0,
            "evidence": {
                str(p.relative_to(root)): _sha_file(p)
                for p in work.rglob("*")
                if p.is_file() and p.name != "session.lock"
            },
        },
    )


def owner_main(root: Path) -> int:
    recipe = declaration(root)
    command = ["uv", "run", "--no-sync", "spireshift", "resources", "run", "--kind", "other"]
    attempt = 1
    while (
        root / f"artifacts/resources/win-world-balanced-fitting-v1-attempt-{attempt}.json"
    ).exists():
        attempt += 1
    command.extend(
        [
            "--report",
            f"artifacts/resources/win-world-balanced-fitting-v1-attempt-{attempt}.json",
            "--artifact-root",
            str(root / recipe["workspace"]),
            "--workers",
            "1",
        ]
    )
    for flag, key in (
        ("--max-wall-seconds", "wall_seconds"),
        ("--max-cpu-seconds", "cpu_seconds"),
        ("--max-memory-bytes", "resident_memory_bytes"),
        ("--max-storage-bytes", "storage_bytes"),
    ):
        command.extend([flag, str(recipe["session_limits"][key])])
    command.extend(
        [
            "--",
            "uv",
            "run",
            "--no-sync",
            "python",
            "-m",
            "spireshift.native_a8_bank_fit_session",
            "--run",
        ]
    )
    print(
        "Fit one copy of each original checkpoint on the admitted 25-world A8 bank.\n"
        "Each copy gets 200 updates and 200 draws per world. Saved inputs only.\n"
        "Allow several minutes. The same command resumes cleanly sealed chunks.\n"
        "Both candidates freeze at update 200, with separate offline development metrics.",
        flush=True,
    )
    return subprocess.call(command, cwd=root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    for flag in ("--run", "--control", "--preflight"):
        mode.add_argument(flag, action="store_true")
    args = parser.parse_args()
    root = Path.cwd()
    if not any((args.run, args.control, args.preflight)):
        return owner_main(root)
    started = time.monotonic()
    ctx = load(root, require_control=not args.control)
    if args.control:
        value = control(root, ctx, started + 265)
    elif args.preflight:
        cfg = job(ctx, control=False)
        if (root / cfg["workspace"]).exists():
            raise ValueError("A new fitting preflight requires an unused main workspace")
        value = {
            "status": "exact_fitting_preflight_verified",
            "job_id": manifest_identifier(cfg),
            "bank_id": ctx["bank_id"],
            "dataset_id": ctx["dataset_id"],
            "checks": verify_frozen(root, ctx),
            "optimizer_updates": 0,
            "main_fitting_started": False,
        }
    else:
        verify_frozen(root, ctx)
        deadline = started + ctx["fitting_recipe"]["session_limits"]["wall_seconds"] - 20
        value = run(root, ctx, job(ctx, control=False), deadline)
    print(
        json.dumps(
            {
                k: v
                for k, v in value.items()
                if k
                not in {
                    "sources",
                    "evidence",
                    "dataset",
                    "copy_results",
                    "candidates",
                    "draws_by_world_per_copy",
                }
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    for name in THREADS:
        os.environ[name] = "1"
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TimeoutError) as exc:
        print(
            json.dumps(
                {
                    "status": "stopped_preserving_evidence",
                    "error": str(exc),
                    "automatic_follow_up": False,
                }
            )
        )
        raise SystemExit(2) from exc
