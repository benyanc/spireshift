"""A finite frozen-player diagnostic pool; collection and analysis never train a player."""

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
from spireshift.engine_experience_audit import audit_worker_experience
from spireshift.engine_learning import (
    IMPLEMENTATION,
    choice_sampling_seed,
    identified,
    load_learning_config,
    summarize,
)
from spireshift.engine_mechanics_admission import require_composed_mechanics
from spireshift.engine_native import (
    _private_path,
    _require_native_launch_support,
    _running_games,
    _shared_snapshot,
)
from spireshift.engine_neural import NativeActorCritic, predict
from spireshift.engine_qualification import (
    EngineQualificationConfig,
    _sha_file,
    load_engine_qualification_config,
)
from spireshift.engine_run import _run_inputs
from spireshift.engine_worker import EngineWorker
from spireshift.engine_worker_qualification import (
    immutable_checks,
    load_worker_config,
    worker_script,
)
from spireshift.full_run_experience import atomic_json
from spireshift.native_gradient_checks import (
    batch_size_checks,
    game_gradient,
    production_gradient_check,
)
from spireshift.native_gradient_study import SOURCES
from spireshift.native_pilot_assessment import SavedFiles, _case, _worker_audits
from spireshift.training_objective import load_training_score_spec

POOL_SOURCES = tuple(dict.fromkeys(("native_gradient_pool.py", *SOURCES, *IMPLEMENTATION)))
INHERITED = (
    "environment_manifest",
    "training_spec",
    "worker_qualification_config",
    "worker_report",
    "helpers_sha256",
    "mechanics_coverage",
    "maximum_decisions",
    "episode_wall_seconds",
    "failure_policy",
    "network",
    "worker_script",
    "liveness_policy",
)


def require_pool_seeds(d: dict[str, Any], seeds: dict[str, Any]) -> None:
    control = d["stage"] == "short_collection_control"
    ids = d["seed_ids"]
    by_id = {r["id"]: r for r in seeds["seeds"]}
    if (
        len(ids) != (4 if control else 256)
        or len(set(ids)) != len(ids)
        or len(by_id) != len(seeds["seeds"])
        or len({r["seed"] for r in seeds["seeds"]}) != len(by_id)
        or any(
            i not in by_id or by_id[i]["partition"] != ("control" if control else "train")
            for i in ids
        )
        or seeds["environment_id"] != d["environment_manifest"]["id"]
    ):
        raise ValueError(
            "Frozen pool must use distinct planned TRAIN/control seeds, never reserved tests"
        )


def load_pool(q: EngineQualificationConfig, path: Path) -> tuple[dict[str, Any], NativeActorCritic]:
    d = json.loads(path.read_text())
    if (
        d.get("schema_version") != "native-frozen-gradient-pool-config-v1"
        or d.get("stage") not in {"short_collection_control", "frozen_train_pool"}
        or d.get("qualification_config_id") != q.config_id
        or d.get("workers") != 2
        or d.get("optimizer_steps") != 0
        or d.get("partitions") != 32
        or d.get("batch_sizes") != [4, 8, 16, 32, 64, 128]
        or d.get("partition_salt") != 20261017
        or d.get("implementation_sha256")
        != {n: _sha_file(q.root / "src/spireshift" / n) for n in POOL_SOURCES}
    ):
        raise ValueError("Frozen gradient collection scope/implementation differs")
    parent = load_learning_config(q.root / d["parent_recipe"]["path"], q)
    if (
        manifest_identifier(parent) != d["parent_recipe"]["id"]
        or any(d[k] != parent[k] for k in INHERITED)
        or d["learning"]["ppo"] != parent["learning"]["ppo"]
        or d["evaluation_policy"]["temperature"] != d["learning"]["ppo"]["temperature"]
    ):
        raise ValueError("Collection cannot change the admitted native player/score/worker rules")
    for n, digest in parent["implementation_sha256"].items():
        if _sha_file(q.root / "src/spireshift" / n) != digest:
            raise ValueError("Admitted native collection source differs")
    ref = d["source_model"]
    # Chosen by predeclared training phase, never from confirmation/development rankings.
    if ref["path"] != str(Path(parent["workspace"]) / "round-007-checkpoint.json"):
        raise ValueError("Pool must freeze the normalized player before its last training round")
    model = NativeActorCritic.from_mapping(
        json.loads(_private_path(q.root, ref["path"]).read_text())
    )
    if (
        model.model_id != ref["id"]
        or model.actor.environment_id != d["environment_manifest"]["id"]
        or model.actor.input_normalization != "native-actor-hash-quarter-v1"
    ):
        raise ValueError("Frozen source player identity differs")
    seeds = identified(q.root / d["seed_manifest"]["path"], "manifest_id")
    if seeds["manifest_id"] != d["seed_manifest"]["id"]:
        raise ValueError("Frozen collection seed manifest changed")
    require_pool_seeds(d, seeds)
    old = identified(q.root / parent["seed_manifest"]["path"], "manifest_id")
    if {s["seed"] for s in seeds["seeds"]} & {s["seed"] for s in old["seeds"]}:
        raise ValueError("Larger diagnostic pool needs fresh native run seeds")
    study = identified(q.root / d["gradient_study"]["path"])
    if (
        study["report_id"] != d["gradient_study"]["id"]
        or study.get("controls_pass") is not True
        or study.get("verified_training_games") != 128
        or study.get("confirmation_or_development_episodes_opened") != 0
        or study.get("optimizer_steps") != 0
    ):
        raise ValueError("Independent-game gradient controls must pass before collection")
    for r in study["sources"]:
        if _sha_file(q.root / r["path"]) != r["sha256"]:
            raise ValueError("Saved gradient study source changed")
    if d["stage"] == "frozen_train_pool":
        ref = d["control"]
        if (
            json.loads((q.root / ref["path"]).read_text()).get("stage")
            != "short_collection_control"
        ):
            raise ValueError("Pool control cannot recursively reference another large pool")
        cfg, _ = load_pool(q, q.root / ref["path"])
        summary = identified(q.root / cfg["workspace"] / "summary.json")
        analysis = identified(q.root / cfg["workspace"] / "gradient-report.json")
        if (
            manifest_identifier(cfg) != ref["id"]
            or cfg["stage"] != "short_collection_control"
            or summary["report_id"] != ref["collection_report_id"]
            or analysis["report_id"] != ref["analysis_report_id"]
            or summary["status"] != "frozen_collection_complete"
            or summary["completed_games"] != 4
            or summary["source_model_id"] != model.model_id
            or analysis.get("production_reference", {}).get("passed") is not True
        ):
            raise ValueError("Separate four-game frozen collection/gradient control must pass")
        for item in analysis["sources"]:
            if _sha_file(q.root / item["path"]) != item["sha256"]:
                raise ValueError("Frozen collection control evidence changed")
    return d, model


def launch_inputs(q: EngineQualificationConfig, d: dict[str, Any]) -> dict[str, Any]:
    wcfg = load_worker_config(q.root / d["worker_qualification_config"], q)
    inputs = _run_inputs(q, q.root / wcfg["base_run_recipe"])
    require_composed_mechanics(q, inputs, d["mechanics_coverage"])
    score = load_training_score_spec(q.root / d["training_spec"]["path"])
    if score.evaluation_objective.as_dict() != inputs["objective"]:
        raise ValueError("Frozen collection cannot change the terminal victory/CPU objective")
    return inputs


def preflight(q: EngineQualificationConfig, path: Path) -> dict[str, Any]:
    d, model = load_pool(q, path)
    launch_inputs(q, d)
    return {
        "ready": not (q.root / d["workspace"]).exists(),
        "planned_games": len(d["seed_ids"]),
        "source_model_id": model.model_id,
        "workspace": d["workspace"],
        "games_launched": 0,
        "optimizer_steps": 0,
        "game_apps_created": 0,
        "training_allowed": False,
    }


def collect(q: EngineQualificationConfig, path: Path, node: Path) -> dict[str, Any]:
    _require_native_launch_support()
    if _running_games() or not node.is_file():
        raise ValueError("Close the game and select the local Node runtime")
    d, model = load_pool(q, path)
    inputs = launch_inputs(q, d)
    score = load_training_score_spec(q.root / d["training_spec"]["path"])
    seed_doc = identified(q.root / d["seed_manifest"]["path"], "manifest_id")
    by_id = {r["id"]: r for r in seed_doc["seeds"]}
    output = _private_path(q.root, d["workspace"])
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "config.json", d)
    source = output / "source-at-launch"
    source.mkdir()
    for n in POOL_SOURCES:
        (source / n).write_bytes((q.root / "src/spireshift" / n).read_bytes())
    atomic_json(output / "source-checkpoint.json", model.as_dict())
    before = _shared_snapshot(Path.home() / "Library/Application Support/SlayTheSpire2")
    started = time.monotonic()
    deadline = started + d["resource_limits"]["wall_seconds"] - 20
    panel = output / "frozen-pool"
    panel.mkdir()
    progress: list[dict[str, Any]] = []
    lock = Lock()

    def lane(index: int) -> list[dict[str, Any]]:
        worker: EngineWorker | None = None
        segment: list[dict[str, Any]] = []
        cases: list[dict[str, Any]] = []
        generation = 0

        def audit() -> None:
            assert worker is not None
            atomic_json(
                worker.workspace / "experience-audit.json",
                audit_worker_experience(worker.workspace, segment),
            )

        try:
            for seed_id in d["seed_ids"][index :: d["workers"]]:
                with lock:
                    if sum(c["status"] != "terminal" for c in progress) > 2:
                        raise ValueError("Frozen pool exceeded its failed-game allowance")
                if time.monotonic() >= deadline:
                    raise TimeoutError("Frozen collection wall cap")
                if worker is None:
                    name = f"worker-{index}" + (f"-generation-{generation}" if generation else "")
                    worker = EngineWorker(
                        q, inputs, panel / name, node, d["helpers_sha256"], script=worker_script(d)
                    )
                    segment = []
                seed = by_id[seed_id]
                training = seed["partition"] == "train"
                sampling_seed = choice_sampling_seed(d, "frozen-pool", seed_id, training)
                case = worker.episode(
                    seed["seed"],
                    maximum_decisions=d["maximum_decisions"],
                    wall_seconds=min(d["episode_wall_seconds"], deadline - time.monotonic()),
                    cpu_seconds=score.evaluation_objective.whole_run_budget,
                    chooser=partial(
                        predict,
                        model,
                        rng=random.Random(sampling_seed),
                        temperature=d["learning"]["ppo"]["temperature"],
                    ),
                )
                case["worker_workspace"] = str(worker.workspace.relative_to(output))
                if not score_episode(case, seed_id, score)["completed"]:
                    case.update(
                        status="failed", error=case.get("error", "Outside admitted outcome budget")
                    )
                binding = {
                    "environment_id": d["environment_manifest"]["id"],
                    "config_id": manifest_identifier(d),
                    "seed_manifest_id": d["seed_manifest"]["id"],
                    "seed_id": seed_id,
                    "native_seed": seed["seed"],
                    "partition": seed["partition"],
                    "panel": "frozen-pool",
                    "model_id": model.model_id,
                    "training_spec_id": score.spec_id,
                    "sampling_seed": sampling_seed,
                    "behavior": "sampled_softmax",
                    "panel_purpose": "training" if training else "frozen_policy_evaluation",
                }
                saved = panel / f"case-{seed_id}.json"
                save_native_episode(saved, case, binding)
                case = read_native_episode(saved, binding)
                cases.append(case)
                segment.append(case)
                with lock:
                    progress.append(case)
                    if len(progress) % 8 == 0 or len(progress) == len(d["seed_ids"]):
                        s = summarize(progress, len(progress))
                        print(
                            f"Frozen player: {len(progress)}/{len(d['seed_ids'])} games; "
                            f"wins {s['wins']}; mean floor {s['mean_floor']:.2f}; "
                            f"best floor {s['best_floor']}; failures {s['failed_games']}. "
                            "No player updates.",
                            flush=True,
                        )
                if case["status"] != "terminal":
                    worker.retire(case.get("error", "Frozen game failed"))
                    audit()
                    worker = None
                    generation += 1
            if worker is not None and not worker.closed:
                worker.close()
                audit()
        except (ValueError, OSError, TimeoutError, subprocess.TimeoutExpired) as exc:
            atomic_json(
                panel / f"worker-{index}-failure.json",
                {"error": str(exc), "recorded_games": len(cases), "replacement_started": False},
            )
        finally:
            if worker is not None:
                worker.stop()
        return cases

    with ThreadPoolExecutor(max_workers=d["workers"]) as pool:
        futures = [pool.submit(lane, i) for i in range(d["workers"])]
        cases = [c for f in futures for c in f.result()]
    summary = summarize(cases, len(d["seed_ids"]))
    atomic_json(panel / "summary.json", summary)
    checks = immutable_checks(q, inputs)
    checks["account_profile_unchanged"] = (
        _shared_snapshot(Path.home() / "Library/Application Support/SlayTheSpire2") == before
    )
    checks["source_player_unchanged"] = (
        identified(q.root / d["source_model"]["path"], "model_id")["model_id"] == model.model_id
    )
    worker_failures = len(list(panel.glob("worker-*-failure.json")))
    clean = summary["failed_games"] == summary[
        "not_attempted_games"
    ] == worker_failures == 0 and all(checks.values())
    body = {
        "schema_version": "native-frozen-gradient-pool-v1",
        "config_id": manifest_identifier(d),
        "stage": d["stage"],
        "source_model_id": model.model_id,
        "status": "frozen_collection_complete" if clean else "frozen_collection_incomplete",
        **summary,
        "checks": checks,
        "worker_failures": worker_failures,
        "game_apps_created": 0,
        "optimizer_steps": 0,
        "checkpoint_promoted": False,
        "base_readiness_passed": False,
        "adaptive_controller_allowed": False,
        "wall_seconds": time.monotonic() - started,
        "claim_scope": "finite_frozen_player_diagnostic_collection_not_learning",
    }
    result = {**body, "report_id": manifest_identifier(body)}
    atomic_json(output / "summary.json", result)
    return result


def analyze(q: EngineQualificationConfig, path: Path) -> dict[str, Any]:
    d, model = load_pool(q, path)
    output = _private_path(q.root, d["workspace"])
    target = output / "gradient-report.json"
    if target.exists():
        result = identified(target)
        if result["config_id"] != manifest_identifier(d):
            raise ValueError("Saved pool analysis belongs to another config")
        return result
    files = SavedFiles(q.root, d["analysis_limits"]["wall_seconds"] - 5)
    summary = files.read(output / "summary.json", "report_id")
    if (
        summary["config_id"] != manifest_identifier(d)
        or summary["status"] != "frozen_collection_complete"
        or summary["completed_games"] != len(d["seed_ids"])
        or not all(summary["checks"].values())
    ):
        raise ValueError(
            "Preserve incomplete pool; every planned clean game is required for analysis"
        )
    for n in POOL_SOURCES:
        if files.pin(output / "source-at-launch" / n) != d["implementation_sha256"][n]:
            raise ValueError("Collection launch source changed")
    files.pin(path)
    seeds = files.read(q.root / d["seed_manifest"]["path"], "manifest_id")
    score = load_training_score_spec(q.root / d["training_spec"]["path"])
    files.pin(q.root / d["training_spec"]["path"])
    files.pin(q.root / d["source_model"]["path"])
    by_id = {s["id"]: s for s in seeds["seeds"]}
    partition = "control" if d["stage"] == "short_collection_control" else "train"
    panel = {"name": "frozen-pool", "partition": partition, "ids": d["seed_ids"]}
    if {p.name for p in (output / "frozen-pool").glob("case-*.json")} != {
        f"case-{seed}.json" for seed in d["seed_ids"]
    }:
        raise ValueError("Frozen pool case inventory differs from its planned denominator")
    scope = manifest_identifier(
        {"config_id": manifest_identifier(d), "model_id": model.model_id, "partition": partition}
    )
    games, samples, outcomes = [], [], []
    for seed in [s for lane in range(d["workers"]) for s in d["seed_ids"][lane :: d["workers"]]]:
        p = output / "frozen-pool" / f"case-{seed}.json"
        outcomes.append(_case(files, p, d, panel, by_id[seed], model.model_id, score))
        case = read_native_episode(p, json.loads(p.read_text())["binding"])
        g, s = game_gradient(
            model, case, seed, 0, score, d["learning"]["ppo"]["temperature"], scope
        )
        games.append(g)
        # Keep only four games' sparse menus/states for the independent numeric
        # loss check. All games retain exact score Jacobians and value features,
        # but keeping every encoded menu too would exceed the larger pool's RAM.
        if len(games) <= 4:
            samples.extend(s)
        del s, case
        if len(games) % 32 == 0:
            print(
                f"Gradient inputs: {len(games)}/{len(d['seed_ids'])} "
                "verified frozen games; no optimizer.",
                flush=True,
            )
    _worker_audits(files, output, d, outcomes)
    reference = production_gradient_check(model, games[:4], samples, d["learning"]["ppo"])
    reference.update(
        checked_games=4,
        checked_decisions=len(samples),
        covers_entire_pool=len(games) == 4,
        scope="bounded_numeric_loss_reference_all_pool_likelihoods_separately_verified",
    )
    checks = batch_size_checks(
        games,
        d["batch_sizes"],
        d["partitions"],
        d["partition_salt"],
        d["learning"]["ppo"]["entropy_coefficient"],
    )
    body = {
        "schema_version": "native-frozen-gradient-pool-analysis-v1",
        "config_id": manifest_identifier(d),
        "collection_report_id": summary["report_id"],
        "source_model_id": model.model_id,
        "production_reference": reference,
        **checks,
        "sources": files.sources(),
        "confirmation_or_development_episodes_opened": 0,
        "games_launched": 0,
        "optimizer_steps": 0,
        "checkpoint_promoted": False,
        "base_readiness_passed": False,
        "adaptive_controller_allowed": False,
        "claim_scope": "single_frozen_policy_TRAIN_gradient_geometry_not_learning_improvement",
    }
    result = {**body, "report_id": manifest_identifier(body)}
    atomic_json(target, result)
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["preflight", "collect", "analyze", "show"])
    p.add_argument("config", type=Path)
    p.add_argument("--node", type=Path)
    a = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    path = (root / a.config).resolve()
    raw = json.loads(path.read_text())
    q = load_engine_qualification_config(root / raw["qualification_config"])
    if a.command == "preflight":
        result = preflight(q, path)
    elif a.command == "collect":
        if a.node is None:
            raise ValueError("Collection requires the local Node runtime")
        result = collect(q, path, a.node)
    elif a.command == "analyze":
        result = analyze(q, path)
    else:
        d, _ = load_pool(q, path)
        result = identified(root / d["workspace"] / "gradient-report.json")
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in {"sources", "disjoint_group_curves"}},
            indent=2,
        )
    )
    for c in result.get("disjoint_group_curves", []):
        print(json.dumps({k: v for k, v in c.items() if k != "partition_details"}))
    return 0 if result.get("status") != "frozen_collection_incomplete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
