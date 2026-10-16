"""Finite TRAIN-only normalization sensitivity and artificial conditional-learning checks.

No gameplay labels are invented: artificial Rest/Smith labels test conditional
capacity only. No production checkpoint, game, or environment admission follows.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode
from spireshift.engine_native import _private_path
from spireshift.engine_neural import DIRECT, NativeActorCritic, encode_public_input
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_policy import FullRunModel, dense_features, score_gradient
from spireshift.full_run_ppo_math import Adam
from spireshift.native_input_normalization import NONE, QUARTER, normalize_actor_rows
from spireshift.native_learning_diagnosis import run_diagnosis
from spireshift.neural_combat import _numpy

SOURCES = (
    "native_normalization_checks.py",
    "native_input_normalization.py",
    "engine_neural.py",
    "engine_experience.py",
    "native_learning_diagnosis.py",
    "full_run_ppo_math.py",
    "full_run_policy.py",
)


def artificial_rest_examples(
    anchors: list[dict[str, Any]], normalization: str, *, remove_hp_signal: bool = False
) -> list[tuple[tuple[dict[int, float], ...], int]]:
    result = []
    for anchor in anchors:
        for low in (True, False):
            public = copy.deepcopy(anchor["public"])

            def change(value: Any, owner: str = "", low_hp: bool = low) -> None:
                if isinstance(value, dict):
                    if owner == "player" and "hp" in value and "max_hp" in value:
                        value["hp"] = (
                            value["max_hp"] // 2
                            if remove_hp_signal
                            else (1 if low_hp else value["max_hp"])
                        )
                    for key, child in value.items():
                        change(child, key)
                elif isinstance(value, list):
                    for child in value:
                        change(child, owner)

            change(public["context"])
            rows, _ = encode_public_input(public, 512, normalization)
            label = "Rest" if low else "Smith"
            selected = next(i for i, c in enumerate(public["candidates"]) if c["label"] == label)
            result.append((rows, selected))
    return result


def _classification(
    model: NativeActorCritic, examples: list[tuple[tuple[dict[int, float], ...], int]]
) -> dict[str, float]:
    np = _numpy()
    weights, bias, output, linear = model.actor.unpack()
    probabilities, correct = [], []
    for rows, label in examples:
        x = dense_features(rows, 512)
        z = np.tanh(x @ weights.T + bias) @ output + x @ linear
        p = np.exp(z - z.max())
        p /= p.sum()
        probabilities.append(float(p[label]))
        correct.append(float(np.argmax(p) == label))
    return {
        "accuracy": math.fsum(correct) / len(correct),
        "mean_target_probability": math.fsum(probabilities) / len(probabilities),
    }


def conditional_control(
    source: NativeActorCritic, fit: list[dict[str, Any]], held: list[dict[str, Any]], mode: str
) -> dict[str, Any]:
    np = _numpy()
    model = replace(source, actor=replace(source.actor, input_normalization=mode))
    training, validation = artificial_rest_examples(fit, mode), artificial_rest_examples(held, mode)
    negative = artificial_rest_examples(held, mode, remove_hp_signal=True)
    for i in range(0, len(negative), 2):
        if negative[i][0] != negative[i + 1][0] or negative[i][1] == negative[i + 1][1]:
            raise ValueError("Negative control did not remove the conditional information")
    rows = tuple(row for options, _ in training for row in options)
    x = dense_features(rows, 512)
    labels = np.asarray([label for _, label in training])
    optimizer = Adam.zero(model.parameter_count)
    checkpoints = [
        {
            "step": 0,
            "fit": _classification(model, training),
            "held": _classification(model, validation),
        }
    ]
    for step in range(1, 301):
        w, b, out, linear = model.actor.unpack()
        z = (np.tanh(x @ w.T + b) @ out + x @ linear).reshape(len(training), 2)
        p = np.exp(z - z.max(axis=1)[:, None])
        p /= p.sum(axis=1)[:, None]
        p[np.arange(len(labels)), labels] -= 1
        gradient = score_gradient(cast(FullRunModel, model.actor), rows, p.ravel() / len(labels))
        updated, optimizer, _ = optimizer.update(
            cast(Any, model),
            (*gradient, *([0.0] * len(model.value_weights))),
            actor_rate=0.003,
            value_rate=0,
            maximum_norm=1.0,
        )
        model = cast(NativeActorCritic, updated)
        if step in (50, 100, 200, 300):
            checkpoints.append(
                {
                    "step": step,
                    "fit": _classification(model, training),
                    "held": _classification(model, validation),
                }
            )
    return {
        "input_normalization": mode,
        "starting_model_id": source.model_id,
        "diagnostic_steps": optimizer.steps,
        "learning_curve": checkpoints,
        "negative_control": _classification(model, negative),
        "negative_control_identical_input_opposite_label_pairs": len(negative) // 2,
        "actor_changed": source.actor.genome != model.actor.genome,
        "critic_unchanged": source.value_weights == model.value_weights,
        "production_model_written": False,
        "artificial_labels_are_not_optimal_gameplay_labels": True,
    }


def run_checks(root: Path, config_path: Path) -> dict[str, Any]:
    cfg = json.loads(config_path.read_text())
    if (
        cfg.get("schema_version") != "native-input-normalization-check-config-v1"
        or cfg.get("normalization") != QUARTER
        or cfg.get("maximum_states_per_family") != 24
        or cfg.get("conditional_fit_runs") != 8
        or cfg.get("implementation_sha256")
        != {name: _sha_file(root / "src/spireshift" / name) for name in SOURCES}
    ):
        raise ValueError(
            "Normalization checks require their frozen finite scope and implementation"
        )
    output = _private_path(root, cfg["workspace"])
    if output.exists() or output.is_symlink():
        raise FileExistsError("Preserve previous normalization evidence")
    experiment_path = root / cfg["experiment"]["path"]
    experiment = json.loads(experiment_path.read_text())
    if manifest_identifier(experiment) != cfg["experiment"]["id"]:
        raise ValueError("Normalization source experiment differs")
    pilot = root / experiment["workspace"]
    audit = run_diagnosis(root, experiment_path, output / "source-audit")
    sources = dict(audit["sources"])
    sources[str(config_path.relative_to(root))] = _sha_file(config_path)
    for name, digest in cfg["implementation_sha256"].items():
        sources[str(Path("src/spireshift") / name)] = digest
    states: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for index, seeds in enumerate(experiment["learning"]["rollout_panels"], 1):
        for seed in seeds:
            path = pilot / f"round-{index:03}-sampled/case-{seed}.json"
            case = read_native_episode(path, json.loads(path.read_text())["binding"])
            seen = set()
            for decision, row in enumerate(case["decisions"]):
                public = row["public_input"]
                kind = public["context"]["interaction"]["kind"]
                if len(public["candidates"]) < 2 or kind in seen or counts[kind] >= 24:
                    continue
                seen.add(kind)
                counts[kind] += 1
                states.append(
                    {
                        "seed": seed,
                        "family": kind,
                        "path": str(path.relative_to(root)),
                        "decision": decision,
                        "public": public,
                    }
                )
    models = []
    for label in ("initial", "round-004", "round-008"):
        path = pilot / f"{label}-checkpoint.json"
        sources[str(path.relative_to(root))] = _sha_file(path)
        models.append((label, NativeActorCritic.from_mapping(json.loads(path.read_text()))))
    np = _numpy()
    measurements = []
    aliases = {NONE: 0, QUARTER: 0}
    candidate_count = 0
    for anchor in states:
        rows, state = encode_public_input(anchor["public"], 512)
        scaled, critic = encode_public_input(anchor["public"], 512, QUARTER)
        if state != critic or rows != tuple(
            {i: v if i < len(DIRECT) else v * 4 for i, v in row.items()} for row in scaled
        ):
            raise ValueError("Normalization lost encoded information or changed the critic")
        if scaled != normalize_actor_rows(rows, len(DIRECT), QUARTER):
            raise ValueError("Native encoder and checked normalization differ")
        candidate_count += len(rows)
        for mode, encoded in ((NONE, rows), (QUARTER, scaled)):
            x = dense_features(encoded, 512)
            aliases[mode] += sum(
                bool(np.array_equal(x[i], x[j])) for i in range(len(x)) for j in range(i)
            )
            for label, model in models:
                w, b, _, _ = model.actor.unpack()
                h = np.tanh(x @ w.T + b)
                measurements.append(
                    {
                        "seed": anchor["seed"],
                        "family": anchor["family"],
                        "model": label,
                        "normalization": mode,
                        "saturation": float(np.mean(np.abs(h) > 0.99)),
                        "mean_derivative": float(np.mean(1 - h * h)),
                        "mean_input_l2": float(np.mean(np.linalg.norm(x, axis=1))),
                    }
                )
    grouped: list[dict[str, Any]] = []
    for label, _ in models:
        for mode in (NONE, QUARTER):
            for family in ["all", *sorted(counts)]:
                rows_stats = [
                    s
                    for s in measurements
                    if s["model"] == label
                    and s["normalization"] == mode
                    and (family == "all" or s["family"] == family)
                ]
                grouped.append(
                    {
                        "model": label,
                        "normalization": mode,
                        "family": family,
                        "states": len(rows_stats),
                        **{
                            k: math.fsum(s[k] for s in rows_stats) / len(rows_stats)
                            for k in ("saturation", "mean_derivative", "mean_input_l2")
                        },
                    }
                )
    anchors = [
        s
        for s in states
        if s["family"] == "rest_site"
        and len(s["public"]["candidates"]) == 2
        and {c["label"] for c in s["public"]["candidates"]} == {"Rest", "Smith"}
    ]
    anchors.sort(
        key=lambda s: manifest_identifier(
            {"salt": "native-normalization-whole-run-rest-v1", "seed": s["seed"]}
        )
    )
    if len(anchors) < 12 or len({a["seed"] for a in anchors}) != len(anchors):
        raise ValueError("Conditional control needs distinct fitting/held TRAIN games")
    fit, held = anchors[:8], anchors[8:]
    controls = [
        conditional_control(model, fit, held, mode)
        for label, model in (models[0], models[-1])
        for mode in (NONE, QUARTER)
    ]
    final = [c["learning_curve"][-1]["held"] for c in controls]

    def ratio(mode: str) -> float:
        return float(
            next(
                s["saturation"]
                for s in grouped
                if s["model"] == "round-008" and s["normalization"] == mode and s["family"] == "all"
            )
        )

    checks = {
        "all_sampled_vectors_recover_exactly": True,
        "critic_input_unchanged": True,
        "candidate_aliases_not_increased": aliases[QUARTER] <= aliases[NONE],
        "late_saturation_reduced_at_least_half": ratio(QUARTER) <= ratio(NONE) * 0.5,
        "held_conditional_accuracy_preserved": final[1]["accuracy"] >= final[0]["accuracy"]
        and final[3]["accuracy"] >= final[2]["accuracy"],
        "normalized_held_conditional_signal": all(
            final[i]["accuracy"] >= 0.95 and final[i]["mean_target_probability"] >= 0.9
            for i in (1, 3)
        ),
        "negative_control_chance_only": all(
            c["negative_control"]["accuracy"] == 0.5 for c in controls
        ),
        "all_diagnostic_actors_changed": all(c["actor_changed"] for c in controls),
    }
    for name, digest in sources.items():
        if _sha_file(root / name) != digest:
            raise ValueError("Normalization diagnostic source changed")
    body = {
        "schema_version": "native-input-normalization-checks-v1",
        "config_id": manifest_identifier(cfg),
        "source_report_id": audit["source_report_id"],
        "source_audit_id": audit["report_id"],
        "training_runs_audited": audit["training_runs"],
        "training_decisions_audited": audit["training_decisions"],
        "probe_states": len(states),
        "probe_candidates": candidate_count,
        "families": dict(counts),
        "one_anchor_per_run_per_family": True,
        "candidate_alias_pairs": aliases,
        "measurements": grouped,
        "conditional_fit_runs": [s["seed"] for s in fit],
        "conditional_held_runs": [s["seed"] for s in held],
        "conditional_examples": {"fit": len(fit) * 2, "held": len(held) * 2},
        "conditional_controls": controls,
        "checks": checks,
        "normalization_control_pass": all(checks.values()),
        "diagnostic_optimizer_steps": sum(c["diagnostic_steps"] for c in controls),
        "confirmation_or_development_episodes_opened": 0,
        "games_launched": 0,
        "production_checkpoints_written": 0,
        "checkpoint_promoted": False,
        "training_allowed": False,
        "sampled_encoded_information_preserved_hash_collisions_not_eliminated": True,
        "saturation_probe_uses_same_historical_weights_for_sensitivity_not_model_migration": True,
        "claim_scope": (
            "bounded_saved_TRAIN_representation_and_artificial_conditional_controls_not_game_strength"
        ),
        "sources": sources,
    }
    result = {**body, "report_id": manifest_identifier(body)}
    atomic_json(output / "probe-states.json", states)
    atomic_json(output / "report.json", result)
    atomic_json(output / "config-at-launch.json", cfg)
    for name in SOURCES:
        (output / name).write_bytes((root / "src/spireshift" / name).read_bytes())
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    report = run_checks(root, (root / args.config).resolve())
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in {"sources", "measurements", "conditional_controls"}
            },
            indent=2,
        )
    )
    print(
        json.dumps(
            [r for r in report["measurements"] if r["family"] in {"all", "combat_turn"}], indent=2
        )
    )
    for c in report["conditional_controls"]:
        print(
            c["input_normalization"],
            c["starting_model_id"],
            c["learning_curve"][-1],
            "negative",
            c["negative_control"],
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
