"""Saved training-only return/value diagnostics; no workers, fitting or policy selection."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode, score_episode
from spireshift.engine_native import _private_path
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.training_objective import load_training_score_spec


def signal_metrics(pairs: list[tuple[float, float]]) -> dict[str, Any]:
    """Population moments on the stated decision set, not independent-outcome counts."""
    if not pairs or any(not math.isfinite(v) for pair in pairs for v in pair):
        raise ValueError("Expected finite target/value pairs")
    n = len(pairs)
    target = math.fsum(y for y, _ in pairs) / n
    residual = math.fsum(y - v for y, v in pairs) / n
    target_var = math.fsum((y - target) ** 2 for y, _ in pairs) / n
    residual_var = math.fsum((y - v - residual) ** 2 for y, v in pairs) / n
    return {
        "decisions": n,
        "target_mean": target,
        "target_std": math.sqrt(target_var),
        "value_mean": math.fsum(v for _, v in pairs) / n,
        "advantage_mean": residual,
        "advantage_std": math.sqrt(residual_var),
        "critic_explained_variance": 1 - residual_var / target_var if target_var else None,
        "critic_mse_over_in_sample_constant": (
            (residual_var + residual**2) / target_var if target_var else None
        ),
        "positive_raw_advantage_fraction": sum(y > v for y, v in pairs) / n,
        "constant_reference_is_diagnostic_not_independently_fitted": True,
    }


def run_diagnosis(root: Path, experiment_path: Path, output: Path) -> dict[str, Any]:
    """Check the frozen launch/source boundary; never open a development episode."""
    cfg = json.loads(experiment_path.read_text())
    pilot = _private_path(root, cfg["workspace"])
    _private_path(root, str(output.relative_to(root)))
    if output == pilot or pilot in output.parents or output in pilot.parents:
        raise ValueError("Diagnostic output cannot alter the source pilot")
    if output.exists() or output.is_symlink():
        raise FileExistsError("Preserve existing diagnostic evidence")
    summary = json.loads((pilot / "summary.json").read_text())
    if (
        cfg.get("stage") != "bounded_policy_only_pilot"
        or summary.get("status") != "bounded_pilot_complete"
        or summary.get("config_id") != manifest_identifier(cfg)
        or summary.get("report_id")
        != manifest_identifier({k: v for k, v in summary.items() if k != "report_id"})
        or summary.get("failed_games") != 0
        or summary.get("not_attempted_games") != 0
    ):
        raise ValueError("Expected the complete sealed, failure-free native pilot")
    source_files: dict[str, str] = {}

    def pin(path: Path) -> None:
        source_files[str(path.relative_to(root))] = _sha_file(path)

    pin(experiment_path)
    pin(pilot / "summary.json")
    for name, digest in cfg["implementation_sha256"].items():
        source = pilot / "source-at-launch" / name
        if _sha_file(source) != digest:
            raise ValueError("Frozen learner implementation changed")
        pin(source)
    seeds_path = root / cfg["seed_manifest"]["path"]
    seeds = json.loads(seeds_path.read_text())
    if seeds.get("manifest_id") != cfg["seed_manifest"]["id"] or seeds[
        "manifest_id"
    ] != manifest_identifier({k: v for k, v in seeds.items() if k != "manifest_id"}):
        raise ValueError("Frozen seed ownership changed")
    owned = {row["id"]: row for row in seeds["seeds"]}
    pin(seeds_path)
    score_path = root / cfg["training_spec"]["path"]
    score = load_training_score_spec(score_path)
    if score.spec_id != cfg["training_spec"]["id"]:
        raise ValueError("Frozen training score changed")
    pin(score_path)
    rounds, total_games, total_decisions = [], 0, 0
    for index, ids in enumerate(cfg["learning"]["rollout_panels"], 1):
        all_pairs: list[tuple[float, float]] = []
        active_pairs: list[tuple[float, float]] = []
        families: dict[str, list[tuple[float, float]]] = defaultdict(list)
        episode_returns = []
        for seed in ids:
            if owned[seed]["partition"] != "train":
                raise ValueError("Diagnostic panel crosses the training boundary")
            path = pilot / f"round-{index:03}-sampled/case-{seed}.json"
            doc = json.loads(path.read_text())
            binding = doc["binding"]
            if (
                binding["partition"] != "train"
                or binding["seed_id"] != seed
                or binding["native_seed"] != owned[seed]["seed"]
                or binding["config_id"] != summary["config_id"]
                or binding["panel"] != f"round-{index:03}-sampled"
                or binding["model_id"] != summary["rounds"][index - 1]["behavior_model_id"]
            ):
                raise ValueError("Saved training behavior/run ownership differs")
            case = read_native_episode(path, binding)
            if (
                case["status"] != "terminal"
                or case["privileged_fixture"] is not False
                or case["recovered"] is not False
                or case["native_ending_evidence_agrees"] is not True
            ):
                raise ValueError("Diagnostic requires ordinary, verified terminal training runs")
            target = score_episode(case, seed, score)["training_return"]
            for row in case["decisions"]:
                choice, public = row["choice"], row["public_input"]
                if choice["model_id"] != binding["model_id"]:
                    raise ValueError("Saved decision belongs to another behavior model")
                pair = (target, choice["value"])
                all_pairs.append(pair)
                if len(public["candidates"]) > 1:
                    active_pairs.append(pair)
                families[public["context"]["interaction"]["kind"]].append(pair)
            episode_returns.append(target)
            pin(path)
            pin(path.with_suffix(".jsonl.gz"))
        total_games += len(episode_returns)
        total_decisions += len(all_pairs)
        rounds.append(
            {
                "round": index,
                "independent_training_runs": len(episode_returns),
                "unique_episode_targets": len(set(episode_returns)),
                "all_decisions": signal_metrics(all_pairs),
                "choice_bearing_decisions": signal_metrics(active_pairs),
                "single_action_decisions": len(all_pairs) - len(active_pairs),
                "families": {key: signal_metrics(values) for key, values in families.items()},
            }
        )
    if total_decisions != summary["sampled_decisions_verified"]:
        raise ValueError("Saved diagnostic and PPO decision denominators differ")
    for name, digest in source_files.items():
        if _sha_file(root / name) != digest:
            raise ValueError("A source changed during the read-only diagnostic")
    body = {
        "schema_version": "native-training-signal-diagnosis-v1",
        "source_report_id": summary["report_id"],
        "experiment_config_id": summary["config_id"],
        "implementation_sha256": _sha_file(Path(__file__)),
        "training_runs": total_games,
        "training_decisions": total_decisions,
        "rounds": rounds,
        "sources": source_files,
        "development_episodes_opened": 0,
        "games_launched": 0,
        "optimizer_steps": 0,
        "checkpoint_promoted": False,
        "claim_scope": (
            "saved_train_only_return_and_behavior_critic_moments_not_causal_game_ablation"
        ),
    }
    result = {**body, "report_id": manifest_identifier(body)}
    _private_path(root, str(output.relative_to(root)))
    output.mkdir(parents=True, exist_ok=False)
    (output / "source-at-launch.py").write_bytes(Path(__file__).read_bytes())
    atomic_json(output / "report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    report = run_diagnosis(root, (root / args.experiment).resolve(), (root / args.output).resolve())
    print(json.dumps({k: v for k, v in report.items() if k not in {"sources", "rounds"}}, indent=2))
    for row in report["rounds"]:
        print(
            "round",
            row["round"],
            "choice-bearing critic explained variance",
            row["choice_bearing_decisions"]["critic_explained_variance"],
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
