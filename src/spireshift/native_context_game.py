"""Versioned inference/experience bridge and a saved-TRAIN projection check.

The new encoding cannot be supplied to the historical experience verifier under
an old model ID. No game or optimizer is started by the saved-state check.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode
from spireshift.engine_learning import identified
from spireshift.engine_neural import DIRECT, encode_public_input
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_ppo_math import Sample
from spireshift.native_action_context import (
    MODES,
    ORIGINAL,
    ActionContextModel,
    encode,
    initialize,
    policy,
)
from spireshift.native_action_context_study import load_config
from spireshift.native_conditional_control import output_path
from spireshift.training_objective import TrainingScoreSpec

SOURCES = ("native_context_game.py", "native_action_context.py", "engine_experience.py")


def predict(
    model: ActionContextModel,
    score: TrainingScoreSpec,
    public: dict[str, Any],
    rng: random.Random | None,
    temperature: float,
) -> dict[str, Any]:
    rows, state, logs = policy(public, model, score, temperature)
    if not rows:
        raise ValueError("Action-context policy requires a complete nonterminal menu")
    if rng is None:
        selected = max(range(len(rows)), key=lambda i: (logs[i], -i))
    else:
        draw, cumulative, selected = rng.random(), 0.0, len(rows) - 1
        for i, logp in enumerate(logs):
            cumulative += math.exp(logp)
            if draw < cumulative:
                selected = i
                break
    return {
        "action_index": selected,
        "log_probability": logs[selected],
        "value": model.value(state),
        "model_id": model.model_id,
        "public_input_id": manifest_identifier(public),
        "temperature": temperature,
        "behavior": "greedy" if rng is None else "sampled_softmax",
    }


def verified_samples(
    case: dict[str, Any],
    model: ActionContextModel,
    score: TrainingScoreSpec,
    training_return: float,
    temperature: float,
) -> list[Sample]:
    if (
        case.get("status") != "terminal"
        or case.get("privileged_fixture") is not False
        or case.get("recovered") is not False
        or case.get("native_ending_evidence_agrees") is not True
        or not math.isfinite(training_return)
        or not 0 <= training_return <= 1
        or not case.get("decisions")
    ):
        raise ValueError("Only clean complete on-policy games can supply action-context PPO")
    result = []
    for row in case["decisions"]:
        public, choice = row["public_input"], row["choice"]
        rows, state, logs = policy(public, model, score, temperature)
        action = choice["action_index"]
        if (
            choice.get("model_id") != model.model_id
            or choice.get("public_input_id") != manifest_identifier(public)
            or choice.get("behavior") != "sampled_softmax"
            or choice.get("temperature") != temperature
            or type(action) is not int
            or not 0 <= action < len(rows)
        ):
            raise ValueError("Action-context behavior is stale, greedy or bound to another input")
        value = model.value(state)
        if not math.isclose(
            choice["log_probability"], logs[action], rel_tol=0, abs_tol=1e-10
        ) or not math.isclose(choice["value"], value, rel_tol=0, abs_tol=1e-10):
            raise ValueError("Action-context probability/value does not reconstruct")
        result.append(
            Sample(rows, state, action, logs[action], training_return, training_return - value)
        )
    return result


def probe(root: Path, path: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    if cfg.get("schema_version") != "native-action-context-probe-config-v1" or cfg.get(
        "implementation_sha256"
    ) != {n: _sha_file(root / "src/spireshift" / n) for n in SOURCES}:
        raise ValueError("Projection check must bind its implementation")
    _, _, score = load_config(root, root / cfg["study_config"]["path"])
    if (
        manifest_identifier(json.loads((root / cfg["study_config"]["path"]).read_text()))
        != cfg["study_config"]["id"]
    ):
        raise ValueError("Projection check study recipe differs")
    report = identified(root / cfg["source_report"]["path"])
    if (
        report["report_id"] != cfg["source_report"]["id"]
        or not report["normalization_control_pass"]
    ):
        raise ValueError("Projection check source was not verified")
    output = output_path(root, cfg)
    sources = {
        **report["sources"],
        cfg["source_report"]["path"]: _sha_file(root / cfg["source_report"]["path"]),
    }
    sources.update({cfg["anchors"]["path"]: cfg["anchors"]["sha256"]})
    sources.update({str(path.relative_to(root)): _sha_file(path)})
    sources.update(
        {f"src/spireshift/{n}": digest for n, digest in cfg["implementation_sha256"].items()}
    )
    for name, digest in sources.items():
        if _sha_file(root / name) != digest:
            raise ValueError("Saved projection source evidence differs")
    if output.exists():
        cached = identified(output / "report.json")
        if cached["config_id"] != manifest_identifier(cfg) or cached["sources"] != sources:
            raise ValueError("Cached projection result recipe/sources differ")
        return cached
    anchors = json.loads((root / cfg["anchors"]["path"]).read_text())
    if len(anchors) != report["probe_states"] or cfg.get("maximum_states") != 278:
        raise ValueError("Projection check must preserve its finite representative state set")
    started = time.monotonic()
    models = {mode: initialize(cfg["environment_id"], score.spec_id, 0, mode) for mode in MODES}
    aliases: Counter[str] = Counter()
    families: Counter[str] = Counter()
    candidates = 0
    last_path = ""
    case: dict[str, Any] = {}
    # Sort by episode and retain at most one saved game's full decision history.
    for anchor in sorted(anchors, key=lambda a: (a["path"], a["decision"])):
        if time.monotonic() - started > 150:
            raise TimeoutError("Finite saved projection check cap")
        if anchor["path"] != last_path:
            last_path = anchor["path"]
            header = json.loads((root / last_path).read_text())
            binding = header["binding"]
            if (
                binding["partition"] != "train"
                or binding["panel_purpose"] != "training"
                or binding["environment_id"] != cfg["environment_id"]
                or binding["training_spec_id"] != score.spec_id
                or last_path not in report["sources"]
                or str(Path(last_path).with_suffix(".jsonl.gz")) not in report["sources"]
            ):
                raise ValueError("Projection check can only inspect sealed original TRAIN games")
            case = read_native_episode(root / last_path, binding)
            if (
                case["status"] != "terminal"
                or case.get("recovered") is not False
                or case.get("privileged_fixture") is not False
            ):
                raise ValueError("Projection check source is not a clean whole run")
        public = anchor["public"]
        if (
            case["decisions"][anchor["decision"]]["public_input"] != public
            or header["binding"]["seed_id"] != anchor["seed"]
            or public["context"]["interaction"]["kind"] != anchor["family"]
        ):
            raise ValueError("Saved anchor differs from the sealed TRAIN decision")
        base, state = encode_public_input(public, 512, models[ORIGINAL].actor.input_normalization)
        candidates += len(base)
        families[anchor["family"]] += 1
        for mode, model in models.items():
            rows, same = encode(public, model, score)
            if len(rows) != len(base) or same != state or mode == ORIGINAL and rows != base:
                raise ValueError("New projection lost a legal action or changed the critic/base")
            for old, new in zip(base, rows, strict=True):
                if any(old.get(i, 0) != new.get(i, 0) for i in range(len(DIRECT))) or not all(
                    math.isfinite(v) for v in new.values()
                ):
                    raise ValueError("New projection changed a direct signal or became nonfinite")
            aliases[mode] += sum(rows[i] == rows[j] for i in range(len(rows)) for j in range(i))
    for name, digest in sources.items():
        if _sha_file(root / name) != digest:
            raise ValueError("Projection source changed during checking")
    checks = {
        "all_original_inputs_rebound_to_sealed_TRAIN_episodes": True,
        "direct_signals_and_critic_and_legal_candidates_preserved": True,
        "finite_representative_rows": True,
        "candidate_alias_pairs_not_increased": all(aliases[m] <= aliases[ORIGINAL] for m in MODES),
    }
    body = {
        "schema_version": "native-action-context-probe-v1",
        "config_id": manifest_identifier(cfg),
        "states": len(anchors),
        "runs": len({a["seed"] for a in anchors}),
        "candidate_rows_per_mode": candidates,
        "families": dict(families),
        "candidate_alias_pairs": {m: aliases[m] for m in MODES},
        "checks": checks,
        "projection_pass": all(checks.values()),
        "sources": sources,
        "wall_seconds": time.monotonic() - started,
        "games_launched": 0,
        "optimizer_steps": 0,
        "checkpoint_promoted": False,
        "native_training_allowed": False,
        "adaptive_controller_allowed": False,
        "exhaustive_mechanics_or_information_preservation_proof": False,
        "claim_scope": "finite_saved_TRAIN_projection_only_not_game_strength_or_training_admission",
    }
    result = {**body, "report_id": manifest_identifier(body)}
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "config-at-launch.json", cfg)
    atomic_json(output / "report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    result = probe(root, root / args.config)
    print(json.dumps({k: v for k, v in result.items() if k != "sources"}, indent=2))
    return 0 if result["projection_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
