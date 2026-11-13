"""Fresh-seed frozen standard players versus their own original initializers.

Read four historical states, never write them. Reuse the qualified collector,
public inference, sampled evaluation, worker retirement and sealed chunk journal.
This module has no fitting or checkpoint-selection path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from contextlib import nullcontext
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import SCHEMA
from spireshift.engine_experience_stream import compact_case
from spireshift.engine_learning import identified, summarize
from spireshift.engine_native import (
    _require_native_launch_support,
    _running_games,
    _shared_snapshot,
)
from spireshift.engine_qualification import (
    EngineQualificationConfig,
    _sha_file,
    load_engine_qualification_config,
)
from spireshift.engine_worker_qualification import immutable_checks
from spireshift.full_run_experience import atomic_json
from spireshift.native_action_context import CROSSED
from spireshift.native_confirmation_metrics import RULE, compare
from spireshift.native_context_journal import ChunkJournal, load_state
from spireshift.native_context_reuse import check_sources
from spireshift.native_context_trial import collect_panel, launch_inputs
from spireshift.native_optimizer_trial import SOURCES as TRIAL_SOURCES
from spireshift.native_optimizer_trial import load_trial
from spireshift.training_objective import load_training_score_spec

SOURCES = (*TRIAL_SOURCES, "native_confirmation_metrics.py", "native_policy_confirmation.py")
COMPLETE = "native_policy_confirmation_complete"
CONTROL = "native_policy_confirmation_control_pass"


def validate_plan(cfg: dict[str, Any], seeds: dict[str, Any]) -> None:
    short = cfg.get("stage") == "short_bridge_control"
    if (
        cfg.get("schema_version") != "native-policy-confirmation-config-v1"
        or cfg.get("stage") not in {"short_bridge_control", "fresh_frozen_confirmation"}
        or cfg.get("training_seeds") != [2, 3]
        or cfg.get("evaluation_games") != (2 if short else 64)
        or cfg.get("chunk_games") != (2 if short else 8)
        or cfg.get("behavior") != "sampled_softmax"
        or cfg.get("sampling") != "unchanged_native_context_frozen_paired_draws_v1"
        or cfg.get("checkpoint_selection") != "frozen_initial_and_final_standard_only"
        or cfg.get("confirmation_rule") != RULE
        or cfg.get("invocation_wall_seconds") != (180 if short else 3600)
        or cfg.get("session_limits")
        != {
            "wall_seconds": 180 if short else 900,
            "cpu_seconds": 360 if short else 1800,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 1000000000 if short else 2000000000,
        }
    ):
        raise ValueError("Freeze the four players, paired evaluation, finite extent and caps")
    rows = seeds["seeds"]
    if (
        len(rows) != 2 * cfg["evaluation_games"]
        or len({s["id"] for s in rows}) != len(rows)
        or len({s["seed"] for s in rows}) != len(rows)
        or any(
            type(s["id"]) is not int
            or not isinstance(s["seed"], str)
            or not s["seed"]
            or s["partition"] != ("control_eval" if short else "confirmation")
            or s["numerical_seed"] not in cfg["training_seeds"]
            for s in rows
        )
        or any(
            sum(s["numerical_seed"] == n for s in rows) != cfg["evaluation_games"]
            for n in cfg["training_seeds"]
        )
    ):
        raise ValueError("Confirmation seeds repeat, cross ownership or miss their reserved panel")


def load_confirmation(
    q: EngineQualificationConfig, path: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str]]:
    cfg = json.loads(path.read_text())
    old_path = q.root / cfg["source_trial"]["path"]
    old, parent, _ = load_trial(q, old_path)
    report_path = q.root / cfg["source_report"]["path"]
    report = identified(report_path)
    if (
        cfg["source_trial"]["id"] != manifest_identifier(old)
        or old["stage"] != "bounded_optimizer_learning_curve"
        or report_path != q.root / old["workspace"] / "report.json"
        or cfg["source_report"]["id"] != report["report_id"]
        or report["config_id"] != manifest_identifier(old)
        or report["status"] != "native_optimizer_learning_curve_complete"
        or report["games_recorded"] != 2368
        or report["planned_games"] != 2368
        or report["completed_units"] != 340
        or report["planned_units"] != 340
        or cfg.get("implementation_sha256")
        != {n: _sha_file(q.root / "src/spireshift" / n) for n in SOURCES}
        or cfg.get("temperature") != parent["learning"]["ppo"]["temperature"]
        or cfg.get("entry_sha256") != _sha_file(q.root / "scripts/policy-confirmation-v1.py")
    ):
        raise ValueError(
            "Completed learning curve, evaluation settings or confirmation sources changed"
        )
    check_sources(q.root, report["sources"])
    sources = {
        **report["sources"],
        **{f"src/spireshift/{n}": v for n, v in cfg["implementation_sha256"].items()},
        "scripts/policy-confirmation-v1.py": cfg["entry_sha256"],
    }
    score = load_training_score_spec(q.root / parent["training_spec"]["path"])
    expected = [(n, v) for n in (2, 3) for v in ("initial", "trained")]
    if [(p["numerical_seed"], p["version"]) for p in cfg["players"]] != expected:
        raise ValueError("Confirmation must keep both final standard players and both originals")
    for ref in cfg["players"]:
        number, version = ref["numerical_seed"], ref["version"]
        key = f"seed-{number}-standard-" + ("initial" if version == "initial" else "batch-016-fit")
        state = q.root / old["workspace"] / "chunks" / key / "state.json"
        receipt_path = state.with_name("done.json")
        receipt = identified(receipt_path)
        m, optimizer, state_id = load_state(state)
        evaluated = next(
            p
            for p in report["learning_curves"]
            if p["arm"] == "standard"
            and p["numerical_seed"] == number
            and p["training_games"] == (0 if version == "initial" else 512)
        )
        if (
            str(state.relative_to(q.root)) != ref["path"]
            or receipt["config_id"] != report["config_id"]
            or receipt["key"] != key
            or receipt["result"]["state_path"] != ref["path"]
            or receipt["result"]["state_id"] != state_id
            or ref["state_id"] != state_id
            or receipt["result"]["model_id"] != m.model_id
            or ref["model_id"] != m.model_id
            or evaluated["model_id"] != m.model_id
            or _sha_file(state) != ref["sha256"]
            or report["sources"][ref["path"]] != ref["sha256"]
            or report["sources"][str(receipt_path.relative_to(q.root))] != _sha_file(receipt_path)
            or m.mode != CROSSED
            or m.actor.environment_id != parent["environment_manifest"]["id"]
            or m.feature_spec_id != score.spec_id
            or (optimizer.steps == 0) != (version == "initial")
        ):
            raise ValueError("Frozen player is not the declared final standard/original state")
    seeds = identified(q.root / cfg["seed_manifest"]["path"], "manifest_id")
    if (
        seeds["manifest_id"] != cfg["seed_manifest"]["id"]
        or seeds["environment_id"] != parent["environment_manifest"]["id"]
    ):
        raise ValueError("Confirmation seed/environment identity changed")
    validate_plan(cfg, seeds)
    excluded = {ref["path"] for ref in cfg["excluded_seed_manifests"]}
    required = {
        old["seed_manifest"]["path"],
        *[ref["path"] for ref in old["excluded_seed_manifests"]],
    }
    if not required <= excluded:
        raise ValueError("Confirmation must exclude every learning-curve and prior control seed")
    for ref in cfg["excluded_seed_manifests"]:
        prior = identified(q.root / ref["path"], "manifest_id")
        if (
            prior["manifest_id"] != ref["id"]
            or {s["id"] for s in seeds["seeds"]} & {s["id"] for s in prior["seeds"]}
            or {s["seed"] for s in seeds["seeds"]} & {s["seed"] for s in prior["seeds"]}
        ):
            raise ValueError(
                "Fresh confirmation overlaps prior training, development or control seeds"
            )
        sources[ref["path"]] = _sha_file(q.root / ref["path"])
    if cfg["stage"] == "fresh_frozen_confirmation":
        control = identified(q.root / cfg["control_report"]["path"])
        control_cfg = json.loads((q.root / control["recipe_path"]).read_text())
        if (
            control["report_id"] != cfg["control_report"]["id"]
            or control["status"] != CONTROL
            or control["config_id"] != manifest_identifier(control_cfg)
            or control_cfg["stage"] != "short_bridge_control"
            or control_cfg["players"] != cfg["players"]
            or control_cfg["implementation_sha256"] != cfg["implementation_sha256"]
            or control_cfg["entry_sha256"] != cfg["entry_sha256"]
            or control_cfg["source_report"] != cfg["source_report"]
            or control["games_recorded"] != 8
            or control_cfg["seed_manifest"]["path"] not in excluded
        ):
            raise ValueError("Short four-player collector check must pass on separate seeds first")
        check_sources(q.root, control["sources"])
        sources.update(control["sources"])
        sources[cfg["control_report"]["path"]] = _sha_file(q.root / cfg["control_report"]["path"])
    for p in (path, old_path, report_path, q.root / cfg["seed_manifest"]["path"]):
        sources[str(p.relative_to(q.root))] = _sha_file(p)
    return cfg, parent, seeds, sources


def plan(cfg: dict[str, Any], seeds: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for number in cfg["training_seeds"]:
        own = [s for s in seeds["seeds"] if s["numerical_seed"] == number]
        for offset in range(0, len(own), cfg["chunk_games"]):
            # Interleave the original and trained player on each small paired batch.
            for version in ("initial", "trained"):
                ref = next(
                    p
                    for p in cfg["players"]
                    if p["numerical_seed"] == number and p["version"] == version
                )
                result.append(
                    {
                        "key": f"seed-{number}-pair-{offset // cfg['chunk_games']:02d}-{version}",
                        "numerical_seed": number,
                        "version": version,
                        "player": ref,
                        "seeds": own[offset : offset + cfg["chunk_games"]],
                    }
                )
    return result


def outcomes_for(
    q: EngineQualificationConfig,
    cfg: dict[str, Any],
    parent: dict[str, Any],
    task: dict[str, Any],
    receipt: dict[str, Any],
) -> list[dict[str, Any]]:
    result = receipt["result"]
    rows: list[dict[str, Any]] = result["summary"]["outcomes"]
    by_id = {r["seed_id"]: r for r in rows}
    paths = result["paths"]
    if (
        len(rows) != len(task["seeds"])
        or len(by_id) != len(rows)
        or len(paths) != len(rows)
        or by_id.keys() != {s["id"] for s in task["seeds"]}
        or result["model_id"] != task["player"]["model_id"]
        or result["summary"].get("worker_failures", 0)
    ):
        raise ValueError("Frozen collection has missing, duplicate or unaudited games")
    headers = {}
    for name in paths:
        h = json.loads((q.root / name).read_text())
        body = {k: v for k, v in h.items() if k not in {"case_id", "trace_file_sha256"}}
        trace = str(Path(name).with_suffix(".jsonl.gz"))
        if (
            h["schema_version"] != SCHEMA
            or h["case_id"] != manifest_identifier(body)
            or receipt["sources"].get(trace) != h["trace_file_sha256"]
            or h["binding"]["seed_id"] in headers
        ):
            raise ValueError("Frozen episode header or compressed trace identity changed")
        headers[h["binding"]["seed_id"]] = h
    if headers.keys() != by_id.keys():
        raise ValueError("Frozen episode paths have different reserved seeds")
    for seed in task["seeds"]:
        h = headers[seed["id"]]
        b, episode = h["binding"], h["episode"]
        sampling = int.from_bytes(
            hashlib.sha256(
                f"native-context-rng-v1|{task['numerical_seed']}|frozen|{seed['id']}".encode()
            ).digest()[:8],
            "big",
        )
        expected = {
            "environment_id": parent["environment_manifest"]["id"],
            "config_id": manifest_identifier(cfg),
            "seed_manifest_id": cfg["seed_manifest"]["id"],
            "seed_id": seed["id"],
            "native_seed": seed["seed"],
            "partition": seed["partition"],
            "panel": "fresh-confirmation",
            "model_id": task["player"]["model_id"],
            "training_spec_id": parent["training_spec"]["id"],
            "sampling_seed": sampling,
            "behavior": "sampled_softmax",
            "panel_purpose": "frozen_policy_evaluation",
        }
        compact = compact_case({**episode, "decisions": range(h["decision_count"])})
        if (
            b != expected
            or compact["seed"] != seed["seed"]
            or any(compact[k] != by_id[seed["id"]][k] for k in compact)
            or episode.get("recovered") is not False
            or episode.get("privileged_fixture") is not False
            or episode.get("game_apps_created") != 0
            or episode["status"] == "terminal"
            and not episode.get("native_ending_evidence_agrees")
        ):
            raise ValueError("Frozen episode ownership, outcome or information boundary changed")
    return rows


def panels(
    q: EngineQualificationConfig,
    cfg: dict[str, Any],
    parent: dict[str, Any],
    tasks: list[dict[str, Any]],
    completed: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    result = []
    for number in cfg["training_seeds"]:
        for version in ("initial", "trained"):
            selected = [
                t for t in tasks if t["numerical_seed"] == number and t["version"] == version
            ]
            if any(t["key"] not in completed for t in selected):
                continue
            rows = [
                o for t in selected for o in outcomes_for(q, cfg, parent, t, completed[t["key"]])
            ]
            result.append(
                {
                    "numerical_seed": number,
                    "version": version,
                    "outcomes": rows,
                    "summary": summarize(
                        [{**r, "decisions": range(r["decision_count"])} for r in rows], len(rows)
                    ),
                }
            )
    return result


def session(
    q: EngineQualificationConfig,
    path: Path,
    node: Path,
    *,
    status_only: bool = False,
    maximum_steps: int | None = None,
    wall_seconds: int | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    cfg, parent, seeds, sources = load_confirmation(q, path)
    store, tasks = ChunkJournal(q.root, cfg), plan(cfg, seeds)
    wall = cfg["session_limits"]["wall_seconds"] if wall_seconds is None else wall_seconds
    if (
        not 30 <= wall <= cfg["session_limits"]["wall_seconds"]
        or maximum_steps is not None
        and maximum_steps < 1
    ):
        raise ValueError("Use a positive step limit and a session within its frozen cap")
    deadline, executed = started + wall - 15, 0
    completed: dict[str, dict[str, Any]] = {}
    with nullcontext() if status_only else store.lock():
        for task in tasks:
            cached = store.completed(task["key"], task)
            if cached is None:
                allowance = 60 if cfg["stage"] == "short_bridge_control" else 300
                if (
                    status_only
                    or (maximum_steps is not None and executed >= maximum_steps)
                    or deadline - time.monotonic() < allowance + 15
                ):
                    break
                _require_native_launch_support()
                if _running_games() or not node.is_file():
                    raise ValueError(
                        "Close the game and select the local Node runtime before comparison"
                    )
                inputs = launch_inputs(q, parent)
                m, _, state_id = load_state(q.root / task["player"]["path"])
                if (
                    state_id != task["player"]["state_id"]
                    or m.model_id != task["player"]["model_id"]
                ):
                    raise ValueError("Historical player changed before collection")
                target = store.begin(task["key"], task)
                shared = Path.home() / "Library/Application Support/SlayTheSpire2"
                snapshot = _shared_snapshot(shared)
                score = load_training_score_spec(q.root / parent["training_spec"]["path"])
                print(
                    f"Player {task['numerical_seed']}, {task['version']}: "
                    f"comparing {len(task['seeds'])} fresh games.",
                    flush=True,
                )
                collection_started = time.monotonic()
                paths, summary, seals = collect_panel(
                    q,
                    cfg,
                    parent,
                    inputs,
                    task["seeds"],
                    node,
                    target / "games",
                    m,
                    score,
                    task["numerical_seed"],
                    "fresh-confirmation",
                    False,
                    min(deadline, time.monotonic() + allowance),
                )
                checks = immutable_checks(q, inputs)
                checks["account_profile_unchanged"] = _shared_snapshot(shared) == snapshot
                previous = sum(
                    completed[t["key"]]["result"]["summary"]["failed_games"]
                    for t in tasks
                    if t["key"] in completed
                    and t["numerical_seed"] == task["numerical_seed"]
                    and t["version"] == task["version"]
                )
                if not all(checks.values()) or previous + summary["failed_games"] > (
                    0 if cfg["stage"] == "short_bridge_control" else 2
                ):
                    raise ValueError(
                        "Shared inputs changed or whole-panel failure allowance exceeded"
                    )
                check_sources(q.root, {task["player"]["path"]: task["player"]["sha256"]})
                body = {
                    "paths": [str(p.relative_to(q.root)) for p in paths],
                    "summary": summary,
                    "checks": checks,
                    "model_id": m.model_id,
                    "state_id": state_id,
                    "games_recorded": len(paths),
                    "collection_wall_seconds": time.monotonic() - collection_started,
                }
                candidate = {"result": body, "sources": seals}
                outcomes_for(q, cfg, parent, task, candidate)
                cached = store.commit(task["key"], task, body, seals)
                executed += 1
            completed[task["key"]] = cached
            if executed and task["version"] == "trained":
                print(
                    f"Saved {len(completed)}/{len(tasks)} comparison chunks; "
                    "completed games will be reused.",
                    flush=True,
                )
        for task in tasks[: len(completed)]:
            receipt = completed[task["key"]]
            outcomes_for(q, cfg, parent, task, receipt)
            sources.update(receipt["sources"])
            p = store.path(task["key"]) / "done.json"
            sources[str(p.relative_to(q.root))] = _sha_file(p)
        own_panels = panels(q, cfg, parent, tasks, completed)
        launch_cfg = store.workspace / "config-at-launch.json"
        if launch_cfg.exists():
            if json.loads(launch_cfg.read_text()) != cfg:
                raise ValueError("Saved confirmation launch config changed")
            sources[str(launch_cfg.relative_to(q.root))] = _sha_file(launch_cfg)
        done = len(completed) == len(tasks)
        body = {
            "schema_version": "native-policy-confirmation-v1",
            "config_id": store.config_id,
            "recipe_path": str(path.relative_to(q.root)),
            "status": (CONTROL if cfg["stage"] == "short_bridge_control" else COMPLETE)
            if done
            else "paused_between_committed_chunks",
            "completed_units": len(completed),
            "planned_units": len(tasks),
            "games_recorded": sum(c["result"]["games_recorded"] for c in completed.values()),
            "planned_games": sum(len(t["seeds"]) for t in tasks),
            "new_units_this_session": executed,
            "panels": own_panels,
            "comparison": compare(cfg, own_panels, seeds) if done else None,
            "sources": sources,
            "wall_seconds": time.monotonic() - started,
            "game_apps_created": 0,
            "optimizer_steps": 0,
            "checkpoint_promoted": False,
            "base_readiness_passed": False,
            "adaptive_controller_allowed": False,
            "claim_scope": "fresh_fixed_A8_frozen_standard_players_not_population_or_readiness",
        }
        final = store.workspace / "report.json"
        if final.exists():
            saved = identified(final)
            check_sources(q.root, saved["sources"])
            if (
                saved["config_id"] != store.config_id
                or saved["comparison"] != body["comparison"]
                or not done
            ):
                raise ValueError("Completed confirmation does not reconstruct")
            return saved
        result = {**body, "report_id": manifest_identifier(body)}
        if not status_only:
            check_sources(q.root, sources)
            sessions = store.workspace / "sessions"
            n = len(list(sessions.glob("session-*.json"))) + 1
            atomic_json(sessions / f"session-{n:03d}.json", result)
            if done:
                atomic_json(final, result)
        return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("qualification", type=Path)
    p.add_argument("config", type=Path)
    p.add_argument("--node", type=Path, required=True)
    p.add_argument("--status", action="store_true")
    p.add_argument("--maximum-steps", type=int)
    p.add_argument("--wall-seconds", type=int)
    a = p.parse_args()
    q = load_engine_qualification_config(a.qualification)
    try:
        r = session(
            q,
            q.root / a.config,
            a.node,
            status_only=a.status,
            maximum_steps=a.maximum_steps,
            wall_seconds=a.wall_seconds,
        )
    except (ValueError, OSError, TimeoutError) as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({k: v for k, v in r.items() if k not in {"sources", "panels"}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
