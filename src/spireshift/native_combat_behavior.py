"""Restartable native fresh-seed comparison: combat greediness is the sole treatment."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file, load_engine_qualification_config
from spireshift.engine_run import _run_inputs
from spireshift.engine_worker_qualification import immutable_checks
from spireshift.full_run_experience import atomic_json
from spireshift.native_combat_behavior_config import load
from spireshift.native_combat_behavior_data import summarize, tasks
from spireshift.native_combat_behavior_game import audit, branch, matched_noncombat
from spireshift.native_combat_behavior_policy import CONTRACT
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_context_reuse import check_sources

COMPLETE = "native_combat_behavior_complete"


def receipt(
    store: ChunkJournal, task: dict[str, Any], sources: dict[str, str]
) -> dict[str, Any] | None:
    saved = store.completed(task["key"], {**task, "policy_contract": CONTRACT})
    if saved is None:
        return None
    value = saved["result"]
    if (
        any(value[k] != task[k] for k in ("numerical_seed", "arm", "duplicate_of"))
        or value["seed_id"] != task["seed"]["id"]
        or not value["native_audit_valid"]
        or not value["inference_audit_valid"]
    ):
        raise ValueError("Saved combat behavior result has a different paired cell or audit")
    sources.update(saved["sources"])
    sources[str((store.path(task["key"]) / "done.json").relative_to(store.root))] = _sha_file(
        store.path(task["key"]) / "done.json"
    )
    return dict(value)


def run(root: Path, path: Path, node: Path, *, status_only: bool = False) -> dict[str, Any]:
    started = time.monotonic()
    cfg, seeds, models, score, sources = load(root, path)
    store = ChunkJournal(root, cfg)
    planned = tasks(seeds, cfg["stage"] == "short_control")
    final = store.workspace / "report.json"
    if final.exists():
        saved = identified(final)
        if saved["config_id"] != store.config_id or saved["status"] not in {
            COMPLETE,
            COMPLETE + "_with_failures",
        }:
            raise ValueError("Preserve the saved comparison under its original recipe")
        check_sources(root, saved["sources"])
        return saved
    if status_only:
        return {
            "status": "fresh_combat_behavior_plan_only",
            "fixed_players": 2,
            "fresh_game_seeds": len(seeds),
            "scored_games": 4 * len(seeds),
            "native_attempt_upper_bound": len(planned),
            "new_games": 0,
            "optimizer_steps": 0,
        }
    if node != Path(cfg["node"]) or not node.is_file() or _running_games():
        raise ValueError("Close STS2 and use the pinned runtime before the isolated comparison")
    q = load_engine_qualification_config(root / cfg["qualification"])
    inputs = _run_inputs(q, root / cfg["native_inputs"]["path"])
    if (
        q.config_id != cfg["qualification_id"]
        or manifest_identifier(inputs["recipe"]) != cfg["native_inputs"]["id"]
        or inputs["objective"] != score.evaluation_objective.as_dict()
    ):
        raise ValueError("Preserve the exact native rules, full-run objective and CPU ceiling")
    before = _shared_snapshot(Path.home() / "Library/Application Support/SlayTheSpire2")
    deadline = started + cfg["session_limits"]["wall_seconds"] - 10
    completed: dict[str, dict[str, Any]] = {}
    new, stopped = 0, False
    with store.lock():
        for task in planned:
            value = receipt(store, task, sources)
            if value is None:
                if deadline - time.monotonic() < 150:
                    break
                request = {**task, "policy_contract": CONTRACT}
                target = store.begin(task["key"], request)
                value = branch(
                    q,
                    cfg,
                    inputs,
                    target,
                    node,
                    task,
                    models[task["numerical_seed"]],
                    score,
                    deadline,
                )
                store.commit(task["key"], request, value)
                value = receipt(store, task, sources)
                if value is None:
                    raise ValueError("A completed game lost its immutable receipt")
                new += 1
            completed[task["key"]] = value
            if (
                task["duplicate_of"]
                and value["status"] == "terminal"
                and value["trace_id"] != completed[task["duplicate_of"]]["trace_id"]
            ):
                raise ValueError("Exact duplicate behavior game changed its public trace")
            if not task["duplicate_of"] and len(completed) % 4 == 0:
                primary = [v for v in completed.values() if not v["duplicate_of"]]
                descriptions = []
                for arm in cfg["arms"]:
                    own = [v for v in primary if v["arm"] == arm and v["status"] == "terminal"]
                    total = sum(v["arm"] == arm for v in primary)
                    descriptions.append(
                        f"{arm}: wins {sum(v['victory'] for v in own)}/{total}, "
                        f"average floor {sum(v['maximum_floor'] for v in own) / total:.2f}, "
                        f"best floor {max((v['maximum_floor'] for v in own), default=0)}"
                    )
                print(
                    f"Fresh combat comparison: {len(primary)}/{4 * len(seeds)} saved; "
                    + " | ".join(descriptions),
                    flush=True,
                )
            allowance = 0 if cfg["stage"] == "short_control" else 2
            failed = sum(
                v["status"] != "terminal"
                and v["numerical_seed"] == task["numerical_seed"]
                and v["arm"] == task["arm"]
                for v in completed.values()
            )
            if failed > allowance:
                stopped = True
                break
        done = len(completed) == len(planned)
        checks = immutable_checks(q, inputs)
        checks["account_profile_unchanged"] = (
            _shared_snapshot(Path.home() / "Library/Application Support/SlayTheSpire2") == before
        )
        check_sources(root, sources)
        if not all(checks.values()):
            raise ValueError("Combat comparison changed shared native inputs or account profile")
        matching = matched_noncombat(root, completed)
        duplicates = [
            v["trace_id"] == completed[v["duplicate_of"]]["trace_id"]
            for v in completed.values()
            if v["duplicate_of"] and v["status"] == "terminal"
        ]
        failures = sum(v["status"] != "terminal" for v in completed.values())
        if (
            done
            and cfg["stage"] == "short_control"
            and (
                len(duplicates) != 4
                or not all(duplicates)
                or matching["shared_noncombat_draw_keys"] == 0
                or any(
                    not any(v["counts"].get(f"{a}_combat", 0) for v in completed.values())
                    for a in ("sampled", "greedy")
                )
            )
        ):
            raise ValueError("Native control lacks repeat, combat or matched noncombat coverage")
        summary = summarize(seeds, completed, control=cfg["stage"] == "short_control")
        body = {
            "schema_version": "native-combat-behavior-comparison-v1",
            "recipe_path": str(path.relative_to(root)),
            "config_id": store.config_id,
            "status": COMPLETE + ("_with_failures" if failures else "")
            if done
            else "stopped_failed_game_allowance"
            if stopped
            else "paused_between_committed_games",
            "completed_units": len(completed),
            "native_attempt_upper_bound": len(planned),
            "new_games_this_session": new,
            "failed_games": failures,
            "summary": summary,
            "noncombat_matching": matching,
            "duplicate_traces_match": all(duplicates) if duplicates else None,
            "checks": checks,
            "full_states_unchanged": True,
            "optimizer_counters": {
                str(p["numerical_seed"]): p["optimizer_steps"] for p in cfg["players"]
            },
            "production_optimizer_steps": 0,
            "game_apps_created": 0,
            "information_scope": cfg["information_scope"],
            "ordinary_PPO_eligible": False,
            "sole_treatment": (
                "greedy_or_temperature_0_8_sampled_combat_including_owned_nested_choices"
            ),
            "noncombat_policy_temperature_and_room_family_draws_matched": True,
            "checkpoint_promoted": False,
            "base_readiness_passed": False,
            "adaptive_controller_allowed": False,
            "automatic_training_follows": False,
            "sources": sources,
            "session_wall_seconds": time.monotonic() - started,
        }
        result = {**body, "report_id": manifest_identifier(body)}
        index = len(list((store.workspace / "sessions").glob("session-*.json"))) + 1
        atomic_json(store.workspace / f"sessions/session-{index:03d}.json", result)
        if done:
            atomic_json(final, result)
        return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("recipe", type=Path)
    p.add_argument("--node", type=Path)
    p.add_argument("--status", action="store_true")
    p.add_argument("--audit-output", type=Path)
    p.add_argument("--max-wall-seconds", type=int, default=210, choices=range(1, 1801))
    a = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    try:
        if a.audit_output:
            result = audit(root, root / a.recipe, time.monotonic() + a.max_wall_seconds)
            atomic_json(root / a.audit_output, result)
        else:
            result = run(root, root / a.recipe, a.node or Path("not-used"), status_only=a.status)
        print(json.dumps({k: v for k, v in result.items() if k != "sources"}, indent=2))
        return (
            1
            if result.get("status", "").startswith("stopped") or result.get("failed_games", 0)
            else 0
        )
    except (ValueError, KeyError, OSError, TimeoutError) as error:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
