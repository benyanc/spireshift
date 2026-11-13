"""Saved-only assessment and initialization sensitivity; never starts learning."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_neural import encode_public_input, initial_actor, initialize_native_critic
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_policy import FullRunModel, score_features, score_gradient
from spireshift.native_conditional_control import TASK, load_config, output_path, passed
from spireshift.native_input_normalization import QUARTER
from spireshift.native_learning_control import public_input


def initial_conditioning(seed: int) -> dict[str, Any]:
    environment = manifest_identifier({"synthetic_task_v1": TASK.as_dict()})
    model = initialize_native_critic(
        initial_actor(environment, 512, 32, seed, input_normalization=QUARTER)
    )
    low, _ = encode_public_input(public_input(TASK, False), 512, QUARTER)
    high, _ = encode_public_input(public_input(TASK, True), 512, QUARTER)
    deltas = [
        {
            i: high[a].get(i, 0) - low[a].get(i, 0)
            for i in set(low[a]) | set(high[a])
            if high[a].get(i, 0) != low[a].get(i, 0)
        }
        for a in range(2)
    ]
    rows = (*high, *low)
    actor = cast(FullRunModel, model.actor)
    logits = score_features(actor, rows)
    # High Commit-minus-Decline gap minus the same low-HP gap.
    conditional = score_gradient(actor, rows, (1.0, -1.0, -1.0, 1.0))
    ordinary = score_gradient(actor, rows, (0.5, -0.5, 0.5, -0.5))

    def norm(values: tuple[float, ...]) -> float:
        return math.sqrt(math.fsum(v * v for v in values))

    return {
        "seed": seed,
        "initial_model_id": model.model_id,
        "public_HP_difference_survives_encoding": bool(deltas[0]),
        "HP_difference_same_for_both_candidate_rows": deltas[0] == deltas[1],
        "direct_linear_conditional_gradient_norm": norm(conditional[-512:]),
        "whole_actor_conditional_gradient_norm": norm(conditional),
        "ordinary_action_preference_gradient_norm": norm(ordinary),
        "conditional_to_ordinary_gradient_norm_ratio": norm(conditional) / norm(ordinary),
        "initial_high_minus_low_commit_logit_gap": logits[0] - logits[1] - logits[2] + logits[3],
        "actual_optimizer_updates_measured_by_this_probe": False,
    }


def assess(root: Path, config_path: Path) -> dict[str, Any]:
    cfg, _, _ = load_config(root, config_path)
    output = output_path(root, cfg)
    # Deliberately do not call the runner: absence of a saved report is an error,
    # never permission for an assessment command to begin fitting.
    report = identified(output / "report.json")
    if (
        report["config_id"] != manifest_identifier(cfg)
        or report["status"] != "complete"
        or not report["comparison_integrity_pass"]
        or json.loads((output / "config-at-launch.json").read_text()) != cfg
    ):
        raise ValueError("Need the complete unchanged conditional comparison")
    files = []
    for ref in report["files"]:
        p = output / ref["path"]
        if p.name != ref["path"] or p.is_symlink() or _sha_file(p) != ref["sha256"]:
            raise ValueError("Saved conditional source seal differs")
        files.append(ref)
    rounds = [identified(output / f["path"]) for f in files if "-round-" in f["path"]]
    if (
        len(rounds) != 96
        or {(r["training_seed"], r["round"]) for r in rounds}
        != {(s, i) for s in cfg["training_seeds"] for i in range(1, cfg["rounds"] + 1)}
        or sum(r["collection"]["complete_synthetic_episodes"] for r in rounds)
        != report["sampled_synthetic_episodes"]
        or sum(d["optimizer_steps"] for r in rounds for d in r["optimizer"].values())
        != report["synthetic_optimizer_steps"]
    ):
        raise ValueError("Saved conditional work totals differ")
    for record in rounds:
        ppo, taught = (record["optimizer"][name] for name in ("ppo", "direct_teaching"))
        for field in ("optimizer_steps", "sample_decision_presentations", "choice_presentations"):
            if ppo[field] != taught[field]:
                raise ValueError("Saved paired optimizer work was not equal")
    initial = [initial_conditioning(seed) for seed in cfg["training_seeds"]]
    summaries = []
    for seed, probe in zip(cfg["training_seeds"], initial, strict=True):
        pair = identified(output / f"seed-{seed}.json")
        if any(m["initial_model_id"] != probe["initial_model_id"] for m in pair["methods"]):
            raise ValueError("Initialization probe belongs to different players")
        for method in pair["methods"]:
            for field, value in method["work"].items():
                if value != sum(
                    r["optimizer"].get(method["name"], {}).get(field, 0)
                    for r in rounds
                    if r["training_seed"] == seed
                ):
                    raise ValueError("Per-method work differs from its saved rounds")
            if (
                passed(method["curve"][0]["evaluation"], method["final"], cfg["acceptance"])
                != method["passed_learning_criterion"]
            ):
                raise ValueError("Learning criterion was changed after fitting")
            summaries.append(
                {
                    "seed": seed,
                    "method": method["name"],
                    "expected_victory": method["final"]["expected_victory"],
                    "minimum_optimal_action_probability": method["final"][
                        "minimum_optimal_action_probability"
                    ],
                    "greedy_accuracy": method["final"]["greedy_accuracy"],
                    "passed": method["passed_learning_criterion"],
                    "optimizer_work": method["work"],
                }
            )
    body = {
        "schema_version": "synthetic-native-conditional-assessment-v1",
        "config_id": manifest_identifier(cfg),
        "source_report_id": report["report_id"],
        "assessment_implementation_sha256": _sha_file(Path(__file__)),
        "verified_round_and_pair_files": len(files),
        "summaries": summaries,
        "initial_conditioning": initial,
        "derivative_probe_proves_cause_or_learning_speed": False,
        "capacity_proven_insufficient": False,
        "optimizer_steps": 0,
        "games_launched": 0,
        "production_checkpoints_written": 0,
        "checkpoint_promoted": False,
        "base_readiness_passed": False,
        "adaptive_controller_allowed": False,
        "claim_scope": (
            "saved_synthetic_conditional_results_and_initial_parameter_sensitivity_not_native_skill"
        ),
    }
    result = {**body, "report_id": manifest_identifier(body)}
    target = output / "assessment.json"
    if target.exists():
        if identified(target) != result:
            raise ValueError("Preserve the earlier assessment under its original implementation")
    else:
        atomic_json(target, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    print(json.dumps(assess(root, root / args.config), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
