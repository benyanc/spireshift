"""Streamed frozen-pool recovery, bounded collection and explicit diagnostic union.

The capped pool and its legacy source bytes stay untouched. Recovered completed
episodes are diagnostic data, never ordinary policy-training admission. An
interrupted seed is never replayed, and its original failure remains counted.
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from threading import Lock
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode, save_native_episode, score_episode
from spireshift.engine_experience_stream import audit_worker_streaming, compact_case
from spireshift.engine_learning import choice_sampling_seed, identified, summarize
from spireshift.engine_native import _private_path, _running_games, _shared_snapshot
from spireshift.engine_neural import predict
from spireshift.engine_qualification import (
    EngineQualificationConfig,
    _sha_file,
    load_engine_qualification_config,
)
from spireshift.engine_worker import EngineWorker
from spireshift.engine_worker_qualification import immutable_checks, worker_script
from spireshift.full_run_experience import atomic_json
from spireshift.native_gradient_checks import (
    batch_size_checks,
    game_gradient,
    production_gradient_check,
)
from spireshift.native_gradient_pool import launch_inputs, load_pool
from spireshift.native_pilot_assessment import SavedFiles, _case
from spireshift.training_objective import load_training_score_spec

SOURCES = ("engine_experience_stream.py", "native_gradient_stream.py")


def compact_summary(cases: list[dict[str, Any]], denominator: int) -> dict[str, Any]:
    # range retains the existing exact summary semantics without retaining a trace.
    return summarize([{**c, "decisions": range(c["decision_count"])} for c in cases], denominator)


def load_stream(
    q: EngineQualificationConfig, path: Path
) -> tuple[dict[str, Any], dict[str, Any], Any]:
    cfg = json.loads(path.read_text())
    if (
        cfg.get("schema_version") != "native-streamed-gradient-recovery-config-v1"
        or cfg.get("implementation_sha256")
        != {n: _sha_file(q.root / "src/spireshift" / n) for n in SOURCES}
        or cfg.get("interrupted_seed_ids") != [700253]
        or cfg.get("unstarted_seed_ids") != [700255]
        or cfg.get("additional_seed_ids") != [700257]
        or cfg.get("expected_recovered_games") != 254
        or cfg.get("target_clean_diagnostic_games") != 256
        or cfg.get("ordinary_training_allowed") is not False
        or cfg.get("maximum_retained_episode_histories_per_lane") != 1
        or cfg.get("recovery_limits")
        != {
            "wall_seconds": 180,
            "cpu_seconds": 180,
            "resident_memory_bytes": 1000000000,
            "storage_bytes": 500000000,
        }
        or cfg.get("collection_limits")
        != {
            "wall_seconds": 180,
            "cpu_seconds": 360,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 1000000000,
        }
        or cfg.get("analysis_limits")
        != {
            "wall_seconds": 600,
            "cpu_seconds": 1200,
            "resident_memory_bytes": 8000000000,
            "storage_bytes": 2000000000,
        }
    ):
        raise ValueError(
            "Freeze the explicit recovery scope, replacement and bounded implementation"
        )
    source, model = load_pool(q, q.root / cfg["source_pool_config"]["path"])
    if manifest_identifier(source) != cfg["source_pool_config"]["id"]:
        raise ValueError("Recovery source pool differs")
    seeds = identified(q.root / cfg["seed_manifest"]["path"], "manifest_id")
    old = identified(q.root / source["seed_manifest"]["path"], "manifest_id")
    by_id = {s["id"]: s for s in seeds["seeds"]}
    old_ids = {s["id"] for s in old["seeds"]}
    if (
        seeds["manifest_id"] != cfg["seed_manifest"]["id"]
        or seeds["environment_id"] != source["environment_manifest"]["id"]
        or len(by_id) != len(seeds["seeds"])
        or len({s["seed"] for s in seeds["seeds"]}) != len(by_id)
        or any(by_id.get(s["id"]) != s for s in old["seeds"])
        or set(by_id) - old_ids != {700257}
        or by_id[700257] != {"id": 700257, "seed": "SP1RESH1FTA8GRD100257", "partition": "train"}
    ):
        raise ValueError("Recovery cannot replace old seeds or hide the interrupted attempt")
    _private_path(q.root, cfg["workspace"])
    return cfg, source, model


def _save(path: Path, body: dict[str, Any]) -> dict[str, Any]:
    report = {**body, "report_id": manifest_identifier(body)}
    atomic_json(path, report)
    return report


def _cached(path: Path, cfg: dict[str, Any], root: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    report = identified(path)
    if report["config_id"] != manifest_identifier(cfg):
        raise ValueError("Saved streamed result belongs to another recipe")
    for ref in report.get("sources", []):
        p = SavedFiles(root, 30).path(ref["path"])
        if _sha_file(p) != ref["sha256"]:
            raise ValueError("Saved streamed evidence changed")
    return report


def recover(q: EngineQualificationConfig, path: Path) -> dict[str, Any]:
    cfg, source, model = load_stream(q, path)
    output = _private_path(q.root, cfg["workspace"])
    target = output / "recovery.json"
    cached = _cached(target, cfg, q.root)
    if cached is not None:
        return cached
    phase = output / "recovery"
    phase.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "config-at-launch.json", cfg)
    snapshot = output / "source-at-launch"
    snapshot.mkdir()
    for name in SOURCES:
        (snapshot / name).write_bytes((q.root / "src/spireshift" / name).read_bytes())
    cap_path = q.root / cfg["capped_resource_report"]["path"]
    cap = identified(cap_path)
    if (
        cap["report_id"] != cfg["capped_resource_report"]["id"]
        or cap["status"] != "capped"
        or cap["cap"]["resource"] != "resident_memory_bytes"
        or cap["artifacts"]["roots"] != [str(q.root / source["workspace"])]
    ):
        raise ValueError("Recovery must preserve the exact original memory-cap receipt")
    old = q.root / source["workspace"]
    if json.loads((old / "config.json").read_text()) != source:
        raise ValueError("Capped collection source config changed")
    for name, sha in source["implementation_sha256"].items():
        if _sha_file(old / "source-at-launch" / name) != sha:
            raise ValueError("Capped collection source-at-launch changed")
    if identified(old / "source-checkpoint.json", "model_id")["model_id"] != model.model_id:
        raise ValueError("Capped frozen player changed")
    seeds = identified(q.root / source["seed_manifest"]["path"], "manifest_id")
    by_id = {s["id"]: s for s in seeds["seeds"]}
    saved = {
        int(p.stem.removeprefix("case-")): p for p in (old / "frozen-pool").glob("case-*.json")
    }
    expected = set(source["seed_ids"]) - set(
        cfg["interrupted_seed_ids"] + cfg["unstarted_seed_ids"]
    )
    if set(saved) != expected or len(saved) != cfg["expected_recovered_games"]:
        raise ValueError("Saved recovery inventory differs; preserve it for review")
    started = time.monotonic()
    deadline = started + cfg["recovery_limits"]["wall_seconds"] - 5
    files = SavedFiles(q.root, cfg["recovery_limits"]["wall_seconds"] - 5)
    files.pin(path)
    files.pin(cap_path)
    files.pin(old / "config.json")
    files.pin(old / "source-checkpoint.json")
    score = load_training_score_spec(q.root / source["training_spec"]["path"])
    panel = {"name": "frozen-pool", "partition": "train", "ids": source["seed_ids"]}
    entries, audits, started_seeds = [], [], []
    for lane in range(source["workers"]):
        ids = [s for s in source["seed_ids"][lane :: source["workers"]] if s in saved]
        workspace = old / "frozen-pool" / f"worker-{lane}"
        interrupted = (workspace / "active.json").exists()
        audit = audit_worker_streaming(
            workspace, [saved[s] for s in ids], interrupted=interrupted, deadline=deadline
        )
        audit_path = phase / f"worker-{lane}-audit.json"
        atomic_json(audit_path, audit)
        files.pin(audit_path)
        for name in audit["source_sha256"]:
            if files.pin(workspace / name) != audit["source_sha256"][name]:
                raise ValueError("Recovered journal changed after its audit")
        started_seeds.extend(audit["started_native_seeds"])
        for seed in ids:
            # This path already streams decisions and verifies seal, score, scope,
            # action shape and original sampling ownership without retaining a pool.
            outcome = _case(files, saved[seed], source, panel, by_id[seed], model.model_id, score)
            if not outcome["terminal"]:
                raise ValueError("A recovered finished prefix contains a failed episode")
            entries.append(
                {
                    "seed_id": seed,
                    "path": str(saved[seed].relative_to(q.root)),
                    "origin": "capped_original",
                    "worker_audit": str(audit_path.relative_to(q.root)),
                }
            )
        audits.append(
            {"path": str(audit_path.relative_to(q.root)), "report_id": audit["report_id"]}
        )
        print(
            f"Verified saved worker {lane}: {audit['games']} complete games; "
            f"unfinished starts {len(audit['unfinished_native_seeds'])}. No games replayed.",
            flush=True,
        )
    expected_started = [
        by_id[s]["seed"] for s in set(source["seed_ids"]) - set(cfg["unstarted_seed_ids"])
    ]
    if sorted(started_seeds) != sorted(expected_started):
        raise ValueError("Original attempted/unstarted seed accounting differs")
    return _save(
        target,
        {
            "schema_version": "native-streamed-pool-recovery-v1",
            "config_id": manifest_identifier(cfg),
            "status": "saved_prefixes_verified",
            "source_pool_config_id": manifest_identifier(source),
            "source_model_id": model.model_id,
            "original_planned_games": len(source["seed_ids"]),
            "original_saved_games_verified": len(entries),
            "original_interrupted_seed_ids": cfg["interrupted_seed_ids"],
            "original_unstarted_seed_ids": cfg["unstarted_seed_ids"],
            "original_attempted_games": len(started_seeds),
            "new_completion_seed_ids": cfg["unstarted_seed_ids"] + cfg["additional_seed_ids"],
            "entries": entries,
            "audits": audits,
            "sources": files.sources(),
            "wall_seconds": time.monotonic() - started,
            "games_launched": 0,
            "games_replayed": 0,
            "source_files_modified": 0,
            "worker_markers_removed": 0,
            "worker_workspaces_reused": 0,
            "ordinary_training_allowed": False,
            "optimizer_steps": 0,
            "checkpoint_promoted": False,
            "base_readiness_passed": False,
            "claim_scope": "verified_saved_diagnostic_prefixes_not_resumed_original_admission",
        },
    )


def episode_recipe(cfg: dict[str, Any], source: dict[str, Any], phase: str) -> dict[str, Any]:
    ids = (
        [900101, 900102, 900103, 900104]
        if phase == "control"
        else (cfg["unstarted_seed_ids"] + cfg["additional_seed_ids"])
    )
    return {
        **source,
        "stage": f"streamed_{phase}",
        "seed_ids": ids,
        "seed_manifest": cfg["seed_manifest"],
        "workspace": str(Path(cfg["workspace"]) / phase),
        "memory_policy": "sealed_paths_and_compact_outcomes_one_episode_per_lane_v1",
        "stream_implementation_sha256": cfg["implementation_sha256"],
        "recovery_config_id": manifest_identifier(cfg),
        "resource_limits": cfg["collection_limits"],
    }


def collect_stream(
    q: EngineQualificationConfig, path: Path, node: Path, phase: str
) -> dict[str, Any]:
    cfg, source, model = load_stream(q, path)
    if phase not in {"control", "completion"}:
        raise ValueError("Unknown bounded collection phase")
    if _running_games() or not node.is_file():
        raise ValueError("Close the game and select the local Node runtime")
    root = q.root / cfg["workspace"]
    target = root / f"{phase}.json"
    cached = _cached(target, cfg, q.root)
    if cached is not None:
        return cached
    if phase == "completion":
        recovery = _cached(root / "recovery.json", cfg, q.root)
        control = _cached(root / "control.json", cfg, q.root)
        if (
            recovery is None
            or control is None
            or control["status"] != "stream_collection_complete"
            or control.get("production_reference", {}).get("passed") is not True
        ):
            raise ValueError(
                "Verify saved recovery and the separate stream control before completion"
            )
    recipe = episode_recipe(cfg, source, phase)
    output = _private_path(q.root, recipe["workspace"])
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "config.json", recipe)
    inputs = launch_inputs(q, source)
    score = load_training_score_spec(q.root / source["training_spec"]["path"])
    seeds = identified(q.root / cfg["seed_manifest"]["path"], "manifest_id")
    by_id = {s["id"]: s for s in seeds["seeds"]}
    account = Path.home() / "Library/Application Support/SlayTheSpire2"
    before = _shared_snapshot(account)
    started = time.monotonic()
    deadline = started + cfg["collection_limits"]["wall_seconds"] - 10
    lock = Lock()
    progress: list[dict[str, Any]] = []

    def lane(index: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        outcomes: list[dict[str, Any]] = []
        entries: list[dict[str, Any]] = []
        paths: list[Path] = []
        worker: EngineWorker | None = None
        try:
            worker = EngineWorker(
                q,
                inputs,
                output / f"worker-{index}",
                node,
                source["helpers_sha256"],
                script=worker_script(source),
            )
            for seed_id in recipe["seed_ids"][index :: source["workers"]]:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Bounded stream collection wall cap")
                seed = by_id[seed_id]
                sampling = choice_sampling_seed(recipe, "frozen-pool", seed_id, phase != "control")
                case = worker.episode(
                    seed["seed"],
                    maximum_decisions=recipe["maximum_decisions"],
                    wall_seconds=min(recipe["episode_wall_seconds"], deadline - time.monotonic()),
                    cpu_seconds=score.evaluation_objective.whole_run_budget,
                    chooser=partial(
                        predict,
                        model,
                        rng=random.Random(sampling),
                        temperature=recipe["learning"]["ppo"]["temperature"],
                    ),
                )
                case["worker_workspace"] = str(worker.workspace.relative_to(output))
                if not score_episode(case, seed_id, score)["completed"]:
                    case.update(status="failed", error=case.get("error", "Outside admitted budget"))
                binding = {
                    "environment_id": recipe["environment_manifest"]["id"],
                    "config_id": manifest_identifier(recipe),
                    "seed_manifest_id": recipe["seed_manifest"]["id"],
                    "seed_id": seed_id,
                    "native_seed": seed["seed"],
                    "partition": seed["partition"],
                    "panel": "frozen-pool",
                    "model_id": model.model_id,
                    "training_spec_id": recipe["training_spec"]["id"],
                    "sampling_seed": sampling,
                    "behavior": "sampled_softmax",
                    "panel_purpose": "training"
                    if phase != "control"
                    else "frozen_policy_evaluation",
                }
                saved = output / f"case-{seed_id}.json"
                save_native_episode(saved, case, binding)
                # Release the live trace before reconstructing its sealed counterpart.
                del case
                verified = read_native_episode(saved, binding)
                compact = compact_case(verified)
                del verified
                paths.append(saved)
                outcomes.append(compact)
                entries.append(
                    {
                        "seed_id": seed_id,
                        "path": str(saved.relative_to(q.root)),
                        "origin": phase,
                        "worker_audit": str(
                            (worker.workspace / "experience-audit.json").relative_to(q.root)
                        ),
                    }
                )
                with lock:
                    progress.append(compact)
                    print(
                        f"Stream {phase}: {len(progress)}/{len(recipe['seed_ids'])} saved games; "
                        "prior traces released, no player updates.",
                        flush=True,
                    )
                if compact["status"] != "terminal":
                    worker.retire(compact["error"] or "Stream game failed")
                    break  # no automatic replacement/retry in this two-game completion
            if not worker.closed:
                worker.close()
            audit = audit_worker_streaming(worker.workspace, paths, deadline=deadline)
            atomic_json(worker.workspace / "experience-audit.json", audit)
        except (ValueError, OSError, TimeoutError, subprocess.TimeoutExpired) as exc:
            atomic_json(
                output / f"worker-{index}-failure.json",
                {"error": str(exc), "replacement_started": False},
            )
        finally:
            if worker is not None:
                worker.stop()
        return outcomes, entries

    with ThreadPoolExecutor(max_workers=source["workers"]) as pool:
        parts = list(pool.map(lane, range(source["workers"])))
    cases = [c for outcomes, _ in parts for c in outcomes]
    entries = [e for _, row in parts for e in row]
    summary = compact_summary(cases, len(recipe["seed_ids"]))
    checks = immutable_checks(q, inputs)
    checks["account_profile_unchanged"] = _shared_snapshot(account) == before
    checks["source_player_unchanged"] = (
        identified(q.root / source["source_model"]["path"], "model_id")["model_id"]
        == model.model_id
    )
    clean = (
        not summary["failed_games"]
        and not summary["not_attempted_games"]
        and not list(output.glob("worker-*-failure.json"))
        and all(checks.values())
    )
    files = SavedFiles(q.root, 30)
    files.pin(output / "config.json")
    for e in entries:
        files.pin(q.root / e["path"])
        files.pin((q.root / e["path"]).with_suffix(".jsonl.gz"))
        audit_path = q.root / e["worker_audit"]
        if audit_path.is_file():
            audit = files.read(audit_path, "report_id")
            for name in audit["source_sha256"]:
                if files.pin(audit_path.parent / name) != audit["source_sha256"][name]:
                    raise ValueError("Stream worker evidence changed")
    reference = None
    if phase == "control" and clean:
        games, samples = [], []
        scope = manifest_identifier({"stream_control": manifest_identifier(cfg)})
        for entry in entries:
            p = q.root / entry["path"]
            panel = {"name": "frozen-pool", "partition": "control", "ids": recipe["seed_ids"]}
            _case(files, p, recipe, panel, by_id[entry["seed_id"]], model.model_id, score)
            case = read_native_episode(p, json.loads(p.read_text())["binding"])
            game, batch = game_gradient(
                model,
                case,
                entry["seed_id"],
                0,
                score,
                recipe["learning"]["ppo"]["temperature"],
                scope,
            )
            games.append(game)
            samples.extend(batch)
        reference = production_gradient_check(model, games, samples, recipe["learning"]["ppo"])
        clean = clean and reference["passed"] is True
    return _save(
        target,
        {
            "schema_version": "native-streamed-pool-collection-v1",
            "config_id": manifest_identifier(cfg),
            "status": "stream_collection_complete" if clean else "stream_collection_incomplete",
            "phase": phase,
            **summary,
            "checks": checks,
            "entries": entries,
            "episode_config_id": manifest_identifier(recipe),
            "production_reference": reference,
            "sources": files.sources(),
            "maximum_retained_episode_histories_per_lane": 1,
            "wall_seconds": time.monotonic() - started,
            "optimizer_steps": 0,
            "game_apps_created": 0,
            "checkpoint_promoted": False,
            "ordinary_training_allowed": False,
        },
    )


def prepare_union(q: EngineQualificationConfig, path: Path) -> dict[str, Any]:
    cfg, source, model = load_stream(q, path)
    root = q.root / cfg["workspace"]
    recovery = _cached(root / "recovery.json", cfg, q.root)
    completion = _cached(root / "completion.json", cfg, q.root)
    if (
        recovery is None
        or completion is None
        or completion["status"] != "stream_collection_complete"
    ):
        raise ValueError("Diagnostic union needs verified recovery and complete bounded additions")
    cached = _cached(root / "union.json", cfg, q.root)
    if cached is not None:
        return cached
    entries = recovery["entries"] + completion["entries"]
    ids = {e["seed_id"] for e in entries}
    if (
        len(entries) != cfg["target_clean_diagnostic_games"]
        or len(ids) != len(entries)
        or ids & set(cfg["interrupted_seed_ids"])
        or ids
        != set(source["seed_ids"]) - set(cfg["interrupted_seed_ids"])
        | set(cfg["additional_seed_ids"])
    ):
        raise ValueError("Diagnostic union cannot retry, duplicate or silently remove an attempt")
    return _save(
        root / "union.json",
        {
            "schema_version": "native-recovered-gradient-diagnostic-union-v1",
            "config_id": manifest_identifier(cfg),
            "source_model_id": model.model_id,
            "clean_diagnostic_games": len(entries),
            "entries": entries,
            "original_planned_games": len(source["seed_ids"]),
            "original_completed_games_after_completion": len(source["seed_ids"]) - 1,
            "original_interrupted_seed_ids": cfg["interrupted_seed_ids"],
            "original_unstarted_games_after_completion": 0,
            "additional_planned_games": len(cfg["additional_seed_ids"]),
            "total_planned_and_attempted_games_including_interruption": len(source["seed_ids"])
            + len(cfg["additional_seed_ids"]),
            "interrupted_attempts_excluded_from_gradient_inputs_but_counted": 1,
            "recovery_report_id": recovery["report_id"],
            "completion_report_id": completion["report_id"],
            "ordinary_training_allowed": False,
            "optimizer_steps": 0,
            "claim_scope": (
                "explicit_256_clean_diagnostic_games_from_257_attempts"
                "_not_original_clean_collection"
            ),
        },
    )


def analyze_union(q: EngineQualificationConfig, path: Path) -> dict[str, Any]:
    cfg, source, model = load_stream(q, path)
    output = q.root / cfg["workspace"]
    target = output / "gradient-report.json"
    cached = _cached(target, cfg, q.root)
    if cached is not None:
        return cached
    union = identified(output / "union.json")
    # Recheck source seals via the phase reports before any gradient computation.
    recovery, completion = (
        _cached(output / "recovery.json", cfg, q.root),
        _cached(output / "completion.json", cfg, q.root),
    )
    if recovery is None or completion is None or union["config_id"] != manifest_identifier(cfg):
        raise ValueError("Recovered diagnostic sources are missing")
    if (
        union["recovery_report_id"] != recovery["report_id"]
        or union["completion_report_id"] != completion["report_id"]
    ):
        raise ValueError("Diagnostic union phase identities differ")
    files = SavedFiles(q.root, cfg["analysis_limits"]["wall_seconds"] - 5)
    for p in (path, output / "union.json", output / "recovery.json", output / "completion.json"):
        files.pin(p)
    seeds = identified(q.root / cfg["seed_manifest"]["path"], "manifest_id")
    by_id = {s["id"]: s for s in seeds["seeds"]}
    score = load_training_score_spec(q.root / source["training_spec"]["path"])
    scope = manifest_identifier({"diagnostic_union": union["report_id"], "model": model.model_id})
    games, samples = [], []
    for entry in union["entries"]:
        case_path = q.root / entry["path"]
        origin = (
            source
            if entry["origin"] == "capped_original"
            else episode_recipe(cfg, source, "completion")
        )
        panel = {"name": "frozen-pool", "partition": "train", "ids": origin["seed_ids"]}
        _case(files, case_path, origin, panel, by_id[entry["seed_id"]], model.model_id, score)
        case = read_native_episode(case_path, json.loads(case_path.read_text())["binding"])
        game, batch = game_gradient(
            model, case, entry["seed_id"], 0, score, source["learning"]["ppo"]["temperature"], scope
        )
        games.append(game)
        if len(games) <= 4:
            samples.extend(batch)
        del case, batch
        if len(games) % 32 == 0:
            print(
                f"Recovered gradient inputs: {len(games)}/256; "
                "every source likelihood verified; no optimizer.",
                flush=True,
            )
    reference = production_gradient_check(model, games[:4], samples, source["learning"]["ppo"])
    reference.update(checked_games=4, checked_decisions=len(samples), covers_entire_pool=False)
    checks = batch_size_checks(
        games,
        source["batch_sizes"],
        source["partitions"],
        source["partition_salt"],
        source["learning"]["ppo"]["entropy_coefficient"],
    )
    return _save(
        target,
        {
            "schema_version": "native-recovered-gradient-analysis-v1",
            "config_id": manifest_identifier(cfg),
            "union_report_id": union["report_id"],
            "source_model_id": model.model_id,
            "production_reference": reference,
            **checks,
            "sources": files.sources(),
            "original_interrupted_attempts": 1,
            "total_attempts_including_interruption": 257,
            "confirmation_or_development_episodes_opened": 0,
            "games_launched": 0,
            "optimizer_steps": 0,
            "ordinary_training_allowed": False,
            "checkpoint_promoted": False,
            "base_readiness_passed": False,
            "adaptive_controller_allowed": False,
            "claim_scope": (
                "recovered_diagnostic_TRAIN_gradient_geometry"
                "_not_learning_or_original_clean_collection"
            ),
        },
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["recover", "control", "completion", "prepare", "analyze"])
    p.add_argument("config", type=Path)
    p.add_argument("--node", type=Path)
    a = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    cfg = json.loads((root / a.config).read_text())
    q = load_engine_qualification_config(root / cfg["qualification_config"])
    if a.command in {"control", "completion"}:
        if a.node is None:
            raise ValueError("Bounded collection needs the local Node runtime")
        result = collect_stream(q, root / a.config, a.node, a.command)
    else:
        result = {"recover": recover, "prepare": prepare_union, "analyze": analyze_union}[
            a.command
        ](q, root / a.config)
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in {"sources", "entries", "disjoint_group_curves"}
            },
            indent=2,
        )
    )
    for row in result.get("disjoint_group_curves", []):
        print(json.dumps({k: v for k, v in row.items() if k != "partition_details"}))
    return 1 if result.get("status") == "stream_collection_incomplete" else 0


if __name__ == "__main__":
    raise SystemExit(main())
