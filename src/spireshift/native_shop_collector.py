"""Finite native collection with auditable, public-only shop navigation.

Raw worker observations and delivered controls keep their original exact audit.
Only the separately bound strategy menu is normalized; original workers are reused.
"""

from __future__ import annotations

import hashlib
import random
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode, save_native_episode, score_episode
from spireshift.engine_experience_stream import audit_worker_streaming, compact_case
from spireshift.engine_learning import identified, summarize
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.engine_worker import EngineWorker
from spireshift.engine_worker_qualification import worker_script
from spireshift.full_run_experience import atomic_json
from spireshift.native_action_context import ActionContextModel
from spireshift.native_shop_policy import CONTRACT, ShopNavigation, choose, verified_samples
from spireshift.training_objective import TrainingScoreSpec


def collect_panel(
    q: EngineQualificationConfig,
    cfg: dict[str, Any],
    parent: dict[str, Any],
    inputs: dict[str, Any],
    seeds: list[dict[str, Any]],
    node: Path,
    output: Path,
    model: ActionContextModel,
    score: TrainingScoreSpec,
    replicate: int,
    label: str,
    training: bool,
    deadline: float,
) -> tuple[list[Path], dict[str, Any], dict[str, str]]:
    output.mkdir(parents=True, exist_ok=False)
    sources: dict[str, str] = {}

    def lane(index: int) -> tuple[list[Path], list[dict[str, Any]]]:
        recorded, outcomes = [], []
        segment: list[Path] = []
        worker: EngineWorker | None = None
        generation = 0

        def audit() -> None:
            assert worker is not None
            report = audit_worker_streaming(worker.workspace, segment, deadline=deadline)
            atomic_json(worker.workspace / "experience-audit.json", report)

        try:
            for seed in seeds[index::2]:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Native context panel wall cap")
                if worker is None:
                    worker = EngineWorker(
                        q,
                        inputs,
                        output / f"worker-{index}-generation-{generation}",
                        node,
                        parent["helpers_sha256"],
                        script=worker_script(parent),
                    )
                    segment = []
                # Neither mode nor checkpoint enters the sampling seed. Paired
                # initial/final evaluation uses the same reserved seeds/draws.
                salt = (
                    f"native-context-rng-v1|{replicate}|"
                    f"{label if training else 'frozen'}|{seed['id']}"
                )
                sampling = int.from_bytes(hashlib.sha256(salt.encode()).digest()[:8], "big")
                navigation = ShopNavigation()
                case = worker.episode(
                    seed["seed"],
                    maximum_decisions=parent["maximum_decisions"],
                    wall_seconds=min(parent["episode_wall_seconds"], deadline - time.monotonic()),
                    cpu_seconds=score.evaluation_objective.whole_run_budget,
                    chooser=partial(
                        choose,
                        model,
                        score,
                        navigation=navigation,
                        rng=random.Random(sampling),
                        temperature=parent["learning"]["ppo"]["temperature"],
                    ),
                )
                case["worker_workspace"] = str(worker.workspace.relative_to(output))
                scored = score_episode(case, seed["id"], score)
                if not scored["completed"]:
                    case.update(status="failed", error=case.get("error", "Outside admitted budget"))
                binding = {
                    "environment_id": parent["environment_manifest"]["id"],
                    "config_id": manifest_identifier(cfg),
                    "seed_manifest_id": cfg["seed_manifest"]["id"],
                    "seed_id": seed["id"],
                    "native_seed": seed["seed"],
                    "partition": seed["partition"],
                    "panel": label,
                    "model_id": model.model_id,
                    "training_spec_id": score.spec_id,
                    "sampling_seed": sampling,
                    "behavior": "sampled_softmax_with_public_navigation",
                    "policy_contract": CONTRACT,
                    "panel_purpose": "training" if training else "frozen_policy_evaluation",
                }
                navigation_steps = sum(d["choice"]["navigation_only"] for d in case["decisions"])
                case["policy_contract"] = CONTRACT
                case["navigation_steps"] = navigation_steps
                saved = output / f"case-{seed['id']}.json"
                save_native_episode(saved, case, binding)
                del case
                verified = read_native_episode(saved, binding)
                compact = compact_case(verified)
                # Reconstruct ALL behavior probabilities even on evaluation.
                if compact["status"] == "terminal":
                    verified_samples(
                        verified,
                        model,
                        score,
                        scored["training_return"],
                        parent["learning"]["ppo"]["temperature"],
                    )
                del verified
                recorded.append(saved)
                segment.append(saved)
                outcomes.append(
                    {
                        **compact,
                        "seed_id": seed["id"],
                        "training_return": scored["training_return"],
                        "navigation_steps": navigation_steps,
                    }
                )
                if compact["status"] != "terminal":
                    worker.retire(compact["error"] or "Native context game failed")
                    audit()
                    worker = None
                    generation += 1
            if worker is not None:
                worker.close()
                audit()
        except (ValueError, OSError, TimeoutError, subprocess.TimeoutExpired) as exc:
            atomic_json(
                output / f"worker-{index}-failure.json",
                {"error": str(exc), "recorded_games": len(recorded)},
            )
        finally:
            if worker is not None:
                worker.stop()
        return recorded, outcomes

    with ThreadPoolExecutor(max_workers=2) as pool:
        lanes = list(pool.map(lane, (0, 1)))
    paths = [p for row, _ in lanes for p in row]
    outcomes = [o for _, row in lanes for o in row]
    summary = {
        **summarize([{**c, "decisions": range(c["decision_count"])} for c in outcomes], len(seeds)),
        "outcomes": outcomes,
        "policy_contract": CONTRACT,
        "navigation_steps": sum(o["navigation_steps"] for o in outcomes),
        "label": label,
        "model_id": model.model_id,
        "worker_failures": len(list(output.glob("worker-*-failure.json"))),
    }
    atomic_json(output / "summary.json", summary)
    for path in [*paths, *[p.with_suffix(".jsonl.gz") for p in paths], output / "summary.json"]:
        sources[str(path.relative_to(q.root))] = _sha_file(path)
    for path in output.glob("worker-*/experience-audit.json"):
        audit_report = identified(path)
        sources[str(path.relative_to(q.root))] = _sha_file(path)
        sources.update(
            {
                str((path.parent / n).relative_to(q.root)): sha
                for n, sha in audit_report["source_sha256"].items()
            }
        )
    print(
        f"{model.mode}, seed {replicate}, {label}: wins {summary['wins']}/{len(seeds)}; "
        f"average floor {summary['mean_floor']:.2f}; best floor {summary['best_floor']}, "
        f"{summary['best_completed_acts']} acts; failures/missing "
        f"{summary['failed_games'] + summary['not_attempted_games']}.",
        flush=True,
    )
    allowance = 0 if cfg["stage"] == "short_bridge_control" else 2
    if (
        summary["not_attempted_games"]
        or summary["worker_failures"]
        or summary["failed_games"] > allowance
    ):
        raise ValueError(
            "Native context panel is missing, unauditable or exceeds failed-game allowance"
        )
    return paths, summary, sources
