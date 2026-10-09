"""Finite A8 on-policy learning with immutable episodes and independent evaluation."""

from __future__ import annotations

import hashlib
import json
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spireshift.adapters.evangambit_public_choices import (
    ADAPTER_ID,
    LoadedPublicChoiceBackend,
    load_public_choice_backend,
    public_adapter_digest,
)
from spireshift.core.manifest import RulesetIdentity, load_patch_manifest, manifest_identifier
from spireshift.full_run_a8_admission import PROFILE_ID, identified_document
from spireshift.full_run_a8_experience import (
    collect_a8_episode,
    episode_binding,
    implementation_id,
    load_a8_episode,
    verified_samples,
)
from spireshift.full_run_experience import atomic_json, save_episode
from spireshift.full_run_ppo_math import ActorCritic, Adam, fit_round, initialize_critic
from spireshift.full_run_public_policy import initial_public_full_run_model
from spireshift.models import _exact_keys, _mapping
from spireshift.neural_combat_features import load_printed_card_catalog
from spireshift.resource_tracking import (
    ExperimentMetrics,
    update_experiment_metrics,
    write_experiment_metrics,
)
from spireshift.splits import SplitManifest, SplitName, load_split_manifest
from spireshift.training_objective import (
    TrainingOutcome,
    TrainingPanel,
    TrainingScoreSpec,
    TrainingStage,
    assess_training_graduation,
    load_training_score_spec,
    score_training_panel,
)

CONFIG_SCHEMA = "public-a8-ppo-config-v1"
REPORT_SCHEMA = "public-a8-ppo-report-v1"


def bounded_integer(value: object, label: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{label} must be an integer in [{low}, {high}]")
    return value


def bounded_number(value: object, label: str, low: float, high: float) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not low <= value <= high:
        raise ValueError(f"{label} must be finite in [{low}, {high}]")
    return float(value)


@dataclass(frozen=True, slots=True)
class PPOConfig:
    document: dict[str, Any]
    score: TrainingScoreSpec
    splits: SplitManifest
    ruleset: RulesetIdentity

    @property
    def config_id(self) -> str:
        return str(self.document["config_id"])

    @classmethod
    def from_mapping(cls, value: object) -> PPOConfig:
        d = _mapping(value, "A8 PPO config")
        _exact_keys(
            d,
            {
                "schema_version",
                "config_id",
                "inputs",
                "network",
                "learning",
                "workers",
                "maximum_decisions",
                "resource_limits",
            },
            "A8 PPO config",
        )
        if d["schema_version"] != CONFIG_SCHEMA or d["config_id"] != manifest_identifier(
            {k: v for k, v in d.items() if k != "config_id"}
        ):
            raise ValueError("PPO config identity or schema differs")
        inputs = _mapping(d["inputs"], "PPO inputs")
        names = ("training_spec", "split_manifest", "ruleset_manifest", "admission_report")
        _exact_keys(inputs, {*names, "upstream_root"}, "PPO inputs")
        for name in names:
            ref = _mapping(inputs[name], name)
            _exact_keys(ref, {"path", "id"}, name)
            if not isinstance(ref["path"], str) or not ref["path"]:
                raise ValueError("PPO input path missing")
        if not isinstance(inputs["upstream_root"], str) or not inputs["upstream_root"]:
            raise ValueError("PPO upstream root missing")
        score = load_training_score_spec(Path(inputs["training_spec"]["path"]))
        splits = load_split_manifest(Path(inputs["split_manifest"]["path"]))
        manifest = load_patch_manifest(Path(inputs["ruleset_manifest"]["path"]))
        ruleset = manifest.ruleset_identity()
        admission = identified_document(Path(inputs["admission_report"]["path"]))
        if (
            inputs["training_spec"]["id"] != score.spec_id
            or inputs["split_manifest"]["id"] != splits.manifest_id
            or inputs["ruleset_manifest"]["id"] != ruleset.manifest_id
            or inputs["admission_report"]["id"] != admission["report_id"]
            or manifest.admission_status != "admitted"
            or manifest.adapter.component_id != ADAPTER_ID
            or manifest.adapter.digest.value != public_adapter_digest()
            or admission.get("verdict") != "admitted_for_policy_only_a8_learning"
            or admission.get("admitted_manifest_id") != ruleset.manifest_id
            or admission.get("profile", {}).get("profile_id") != PROFILE_ID
            or admission.get("profile", {}).get("source_declared_ascension_level") != 8
            or splits.ruleset_manifest_id != ruleset.manifest_id
            or score.scope.ruleset_manifest_id != ruleset.manifest_id
            or splits.objective_id != score.evaluation_objective.objective_id
            or score.scope.character != "ironclad"
            or score.scope.ascension != 8
        ):
            raise ValueError("PPO identities, admission, difficulty or objective differ")
        n = _mapping(d["network"], "network")
        _exact_keys(
            n, {"dimension", "hidden_units", "initialization_seed", "card_source_sha256"}, "network"
        )
        bounded_integer(n["dimension"], "dimension", 128, 1024)
        bounded_integer(n["hidden_units"], "hidden units", 4, 64)
        bounded_integer(n["initialization_seed"], "initialization seed", 0, 2**31 - 1)
        digest = n["card_source_sha256"]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
        ):
            raise ValueError("Printed-card source hash invalid")
        learning = _mapping(d["learning"], "learning")
        _exact_keys(
            learning,
            {
                "maximum_rounds",
                "minimum_rounds",
                "rollout_seed_panels",
                "confirmation_train_seeds",
                "development_seeds",
                "confirmation_every",
                "plateau_confirmations",
                "sampling_rng_seed",
                "shuffle_rng_seed",
                "epochs",
                "minibatch_decisions",
                "clip",
                "entropy_coefficient",
                "value_coefficient",
                "actor_learning_rate",
                "value_learning_rate",
                "gradient_clip",
                "target_kl",
                "temperature",
            },
            "learning",
        )
        rounds = bounded_integer(learning["maximum_rounds"], "rounds", 1, 100)
        bounded_integer(learning["minimum_rounds"], "minimum rounds", 1, rounds)
        bounded_integer(learning["confirmation_every"], "confirmation interval", 1, rounds)
        bounded_integer(learning["plateau_confirmations"], "plateau checks", 1, 100)
        for key in ("sampling_rng_seed", "shuffle_rng_seed"):
            bounded_integer(learning[key], key, 0, 2**31 - 1)
        bounded_integer(learning["epochs"], "epochs", 1, 10)
        bounded_integer(learning["minibatch_decisions"], "minibatch decisions", 2, 2048)
        for key, low, high in (
            ("clip", 0.01, 0.4),
            ("entropy_coefficient", 0, 0.1),
            ("value_coefficient", 0.01, 2),
            ("actor_learning_rate", 1e-6, 0.05),
            ("value_learning_rate", 1e-6, 0.05),
            ("gradient_clip", 0.1, 20),
            ("target_kl", 0.001, 0.2),
            ("temperature", 0.1, 2),
        ):
            bounded_number(learning[key], key, low, high)
        panels = learning["rollout_seed_panels"]
        if not isinstance(panels, list) or len(panels) != rounds:
            raise ValueError("Exactly one frozen training panel required per PPO round")
        seen: set[int] = set()
        for seeds, split in [(p, SplitName.TRAIN) for p in panels] + [
            (learning["confirmation_train_seeds"], SplitName.TRAIN),
            (learning["development_seeds"], SplitName.VALIDATION),
        ]:
            if not isinstance(seeds, list) or not 2 <= len(seeds) <= 512:
                raise ValueError("PPO panels require 2-512 complete-run seeds")
            for seed in seeds:
                bounded_integer(seed, "seed", 0, 2**31 - 1)
                if seed in seen or splits.split_for_seed(seed) != split:
                    raise ValueError("PPO seed panels overlap or cross complete-run partitions")
                seen.add(seed)
        bounded_integer(d["workers"], "workers", 1, 16)
        bounded_integer(d["maximum_decisions"], "decisions", 1, 10000)
        limits = _mapping(d["resource_limits"], "resource limits")
        _exact_keys(
            limits, {"wall_seconds", "cpu_seconds", "storage_bytes", "memory_bytes"}, "limits"
        )
        for key in limits:
            bounded_integer(limits[key], key, 1, 10**13)
        return cls(d, score, splits, ruleset)


def load_ppo_config(path: Path) -> PPOConfig:
    return PPOConfig.from_mapping(json.loads(path.read_text()))


def load_actor_critic(path: Path) -> ActorCritic:
    return ActorCritic.from_mapping(json.loads(path.read_text()))


def frozen_json(path: Path, body: dict[str, Any], key: str) -> dict[str, Any]:
    result = {**body, key: manifest_identifier(body)}
    if path.exists():
        if json.loads(path.read_text()) != result:
            raise ValueError(f"Saved PPO checkpoint differs: {path}")
    else:
        atomic_json(path, result)
    return result


def ppo_protocol(config: PPOConfig) -> dict[str, Any]:
    return {
        "config_id": config.config_id,
        "experience_implementation_id": implementation_id(),
        "runner_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "training_spec_id": config.score.spec_id,
        "split_manifest_id": config.splits.manifest_id,
        "ruleset_manifest_id": config.ruleset.manifest_id,
        "claim_scope": "sampled_a8_ppo_bootstrap_with_frozen_independent_greedy_development",
        "automatic_followup": False,
        "adaptive_controller_allowed": False,
        "checkpoint_promoted": False,
        "final_test_opened": False,
    }


_BACKEND: LoadedPublicChoiceBackend | None = None
_WORKER_CONFIG: tuple[str, PPOConfig] | None = None
_WORKER_MODELS: dict[str, ActorCritic] = {}


def episode_worker(request: dict[str, Any]) -> dict[str, Any]:
    global _BACKEND, _WORKER_CONFIG
    config_path = request["config_path"]
    if _WORKER_CONFIG is None:
        _WORKER_CONFIG = (config_path, load_ppo_config(Path(config_path)))
    if _WORKER_CONFIG[0] != config_path:
        raise ValueError("Worker cannot switch frozen PPO protocols")
    config = _WORKER_CONFIG[1]
    model_path = request["model_path"]
    if model_path not in _WORKER_MODELS:
        _WORKER_MODELS[model_path] = load_actor_critic(Path(model_path))
    model = _WORKER_MODELS[model_path]
    # Check seed ownership and sampled behavior before opening the native backend.
    episode_binding(
        config.ruleset,
        model,
        config.score,
        config.splits,
        request["seed"],
        request["partition"],
        config.document["maximum_decisions"],
        request["behavior"],
        request["temperature"],
        request["sampling_seed"],
    )
    if _BACKEND is None:
        inputs = config.document["inputs"]
        _BACKEND = load_public_choice_backend(
            Path(inputs["upstream_root"]),
            Path(inputs["ruleset_manifest"]["path"]),
            max_episode_steps=config.document["maximum_decisions"] + 1,
        )
    case, trace = collect_a8_episode(
        _BACKEND.factory,
        config.ruleset,
        model,
        config.score,
        config.splits,
        seed=request["seed"],
        partition=request["partition"],
        behavior=request["behavior"],
        sampling_seed=request["sampling_seed"],
        temperature=request["temperature"],
        maximum_decisions=config.document["maximum_decisions"],
    )
    save_episode(Path(request["case_path"]), case, trace)
    return case


class ExperienceStore:
    def __init__(
        self, config: PPOConfig, config_path: Path, output: Path, executor: ProcessPoolExecutor
    ) -> None:
        self.config, self.config_path, self.output, self.executor = (
            config,
            config_path,
            output,
            executor,
        )
        self.new_attempts = self.new_transitions = 0
        self.cases: dict[str, dict[str, Any]] = {}
        self.paths: dict[str, Path] = {}

    def save_model(self, model: ActorCritic) -> Path:
        path = self.output / "models" / (model.model_id[7:] + ".json")
        if path.exists():
            if load_actor_critic(path).as_dict() != model.as_dict():
                raise ValueError("Saved PPO model differs")
        else:
            atomic_json(path, model.as_dict())
        return path

    def failure(self, binding: dict[str, Any], path: Path, error: str) -> dict[str, Any]:
        return frozen_json(
            path,
            {
                "schema_version": "public-a8-worker-failure-v1",
                "binding": binding,
                "error": error,
                "cpu_seconds_known": False,
                "outcome": {
                    "seed": binding["seed"],
                    "status": "runtime_error",
                    "completed_acts": 0,
                    "maximum_floor": 0,
                    "decisions": 0,
                    "cpu_seconds": 0.0,
                },
            },
            "case_id",
        )

    def panel(
        self,
        model: ActorCritic,
        seeds: list[int],
        partition: str,
        *,
        round_index: int | None,
        label: str,
    ) -> tuple[dict[str, Any], list[str]]:
        model_path = self.save_model(model)
        futures, keys = {}, []
        sampled = round_index is not None
        learning = self.config.document["learning"]
        for seed in seeds:
            sampling_seed = (
                int.from_bytes(
                    hashlib.sha256(
                        f"{learning['sampling_rng_seed']}|{round_index}|{seed}".encode()
                    ).digest()[:8],
                    "big",
                )
                if sampled
                else 0
            )
            binding = episode_binding(
                self.config.ruleset,
                model,
                self.config.score,
                self.config.splits,
                seed,
                partition,
                self.config.document["maximum_decisions"],
                "sampled_softmax" if sampled else "greedy_argmax",
                learning["temperature"] if sampled else 1.0,
                sampling_seed,
            )
            key = manifest_identifier(binding)[7:]
            keys.append(key)
            if key in self.cases:
                continue
            directory = self.output / "cases" / key
            path, failure_path = directory / "case.json", directory / "failure.json"
            if path.exists() and failure_path.exists():
                raise ValueError("One PPO attempt cannot be both completed and failed")
            if path.exists():
                self.cases[key], _ = load_a8_episode(path, binding)
                self.paths[key] = path
                continue
            if failure_path.exists():
                saved = identified_document(failure_path, "case_id")
                if saved["binding"] != binding or saved.get("cpu_seconds_known") is not False:
                    raise ValueError("Saved PPO failure differs")
                self.cases[key], self.paths[key] = saved, failure_path
                continue
            started = directory / "started.json"
            if started.exists():
                if identified_document(started, "request_id")["binding"] != binding:
                    raise ValueError("Interrupted PPO attempt scope differs")
                self.cases[key] = self.failure(
                    binding,
                    failure_path,
                    "Prior interrupted/queued attempt retained; CPU and partial decisions unknown",
                )
                self.paths[key] = failure_path
                continue
            frozen_json(started, {"binding": binding}, "request_id")
            request = {
                "config_path": str(self.config_path.resolve()),
                "model_path": str(model_path.resolve()),
                "case_path": str(path.resolve()),
                "seed": seed,
                "partition": partition,
                "behavior": binding["behavior"],
                "temperature": binding["temperature"],
                "sampling_seed": sampling_seed,
            }
            try:
                future = self.executor.submit(episode_worker, request)
            except Exception as exc:
                self.cases[key] = self.failure(binding, failure_path, f"Submission failed: {exc}")
                self.paths[key] = failure_path
                self.new_attempts += 1
            else:
                futures[future] = (key, binding, path)
        done = len(keys) - len(futures)
        print(f"{label}: {done}/{len(keys)} saved games; {len(futures)} new attempts.", flush=True)
        for future in as_completed(futures):
            key, binding, path = futures[future]
            try:
                future.result()
                case, _ = load_a8_episode(path, binding)
            except Exception as exc:
                if path.exists():
                    # Corrupt recorded output is a hard evidence error, never silently a retry.
                    raise ValueError(
                        f"Saved worker output failed verification: {path}: {exc}"
                    ) from exc
                case = self.failure(
                    binding, path.with_name("failure.json"), f"{type(exc).__name__}: {exc}"
                )
            self.cases[key] = case
            self.paths[key] = path if path.exists() else path.with_name("failure.json")
            self.new_attempts += 1
            self.new_transitions += case["outcome"]["decisions"]
            update_experiment_metrics(
                ExperimentMetrics(
                    trajectories=self.new_attempts, simulations=0, transitions=self.new_transitions
                )
            )
            done += 1
            if done % 8 == 0 or done == len(keys):
                print(f"{label}: {done}/{len(keys)} games recorded.", flush=True)
        outcomes = tuple(TrainingOutcome.from_mapping(self.cases[k]["outcome"]) for k in keys)
        panel = TrainingPanel(partition, tuple(seeds), outcomes)
        scored = score_training_panel(self.config.score, panel)
        summary = {
            **scored["summary"],
            "mean_maximum_floor": sum(o.maximum_floor for o in outcomes) / len(seeds),
            "mean_completed_acts": sum(o.completed_acts for o in outcomes) / len(seeds),
        }
        result = {
            "model_id": model.model_id,
            "case_ids": [self.cases[k]["case_id"] for k in keys],
            "seeds": seeds,
            "summary": summary,
            "score_report_id": scored["report_id"],
        }
        return result, keys


def run_ppo(config_path: Path, output: Path, *, resume: bool = False) -> dict[str, Any]:
    config, protocol = load_ppo_config(config_path), None
    protocol = ppo_protocol(config)
    if output.exists() and not resume:
        raise FileExistsError(f"Use explicit --resume for existing PPO results: {output}")
    output.mkdir(parents=True, exist_ok=True)
    import fcntl

    with (output / ".owner-run.lock").open("a") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("This A8 training job is active in another terminal") from exc
        frozen_json(output / "protocol.json", protocol, "protocol_id")
        if (output / "ppo-report.json").exists():
            return inspect_ppo(config_path, output)
        return run_locked(config, config_path, output, protocol)


def run_locked(
    config: PPOConfig, config_path: Path, output: Path, protocol: dict[str, Any]
) -> dict[str, Any]:
    frozen_json(output / "protocol.json", protocol, "protocol_id")
    inputs, n, learning = (config.document[k] for k in ("inputs", "network", "learning"))
    catalog = load_printed_card_catalog(Path(inputs["upstream_root"]), n["card_source_sha256"])
    initial = initialize_critic(
        initial_public_full_run_model(
            config.ruleset,
            catalog,
            n["card_source_sha256"],
            dimension=n["dimension"],
            hidden_units=n["hidden_units"],
            initialization_seed=n["initialization_seed"],
        )
    )
    model, champion = initial, initial
    optimizer = Adam.zero(initial.parameter_count)
    updates: list[dict[str, Any]] = []
    plateau, stop = 0, "round_limit"
    write_experiment_metrics(ExperimentMetrics(trajectories=0, simulations=0, transitions=0))
    with ProcessPoolExecutor(
        max_workers=config.document["workers"], mp_context=multiprocessing.get_context("spawn")
    ) as executor:
        store = ExperienceStore(config, config_path, output, executor)
        store.save_model(initial)
        confirmation, _ = store.panel(
            initial,
            learning["confirmation_train_seeds"],
            "train",
            round_index=None,
            label="Initial player confirmation",
        )
        for round_index, seeds in enumerate(learning["rollout_seed_panels"]):
            path = output / f"round-{round_index:03d}.json"
            if path.exists():
                saved = identified_document(path, "round_id")
                if (
                    saved["protocol"] != protocol
                    or saved["round_index"] != round_index
                    or saved["behavior_model_id"] != model.model_id
                    or saved["optimizer_before"] != optimizer.as_dict()
                ):
                    raise ValueError("Saved PPO round state differs")
                # Load every source case into the store even when no optimizer rerun is needed.
                panel, _ = store.panel(
                    model,
                    seeds,
                    "train",
                    round_index=round_index,
                    label=f"Saved round {round_index + 1}",
                )
                if panel != saved["sampled_training_panel"]:
                    raise ValueError("Saved round source panel differs")
                model = load_actor_critic(
                    output / "models" / (saved["updated_model_id"][7:] + ".json")
                )
                optimizer = Adam.from_mapping(saved["optimizer_after"], model.parameter_count)
                candidate_confirmation = saved["candidate_confirmation"]
            else:
                panel, keys = store.panel(
                    model,
                    seeds,
                    "train",
                    round_index=round_index,
                    label=f"Round {round_index + 1}/{learning['maximum_rounds']}",
                )
                samples = []
                for key in keys:
                    case = store.cases[key]
                    if case.get("cpu_seconds_known") is False:
                        continue  # No recorded decisions to learn from; failure remains in panel.
                    _, trace = load_a8_episode(store.paths[key], case["binding"])
                    samples.extend(
                        verified_samples(case, trace, config.ruleset, model, config.score)
                    )
                if not samples:
                    stop = "no_verified_sampled_decisions"
                    break
                before_model, before_optimizer = model, optimizer
                model, optimizer, optimization = fit_round(
                    model, optimizer, samples, learning, learning["shuffle_rng_seed"] + round_index
                )
                store.save_model(model)
                candidate_confirmation = None
                if (round_index + 1) % learning[
                    "confirmation_every"
                ] == 0 or round_index + 1 == learning["maximum_rounds"]:
                    candidate_confirmation, _ = store.panel(
                        model,
                        learning["confirmation_train_seeds"],
                        "train",
                        round_index=None,
                        label=f"Round {round_index + 1} confirmation",
                    )
                saved = frozen_json(
                    path,
                    {
                        "protocol": protocol,
                        "round_index": round_index,
                        "behavior_model_id": before_model.model_id,
                        "updated_model_id": model.model_id,
                        "optimizer_before": before_optimizer.as_dict(),
                        "optimizer_after": optimizer.as_dict(),
                        "sampled_training_panel": panel,
                        "optimization": optimization,
                        "candidate_confirmation": candidate_confirmation,
                    },
                    "round_id",
                )
            updates.append(
                {
                    k: v
                    for k, v in saved.items()
                    if k not in {"optimizer_before", "optimizer_after", "protocol"}
                }
            )
            if candidate_confirmation is not None:
                # Recover source cases and validate a saved confirmation, without replay.
                checked, _ = store.panel(
                    model,
                    learning["confirmation_train_seeds"],
                    "train",
                    round_index=None,
                    label="Checkpoint comparison",
                )
                if checked != candidate_confirmation:
                    raise ValueError("Saved confirmation outcomes differ")
                if tuple(checked["summary"]["fitness_rank"]) > tuple(
                    confirmation["summary"]["fitness_rank"]
                ):
                    champion, confirmation, plateau = model, checked, 0
                else:
                    plateau += 1
                print(
                    f"Confirmed player: {confirmation['summary']['victories']} wins / "
                    f"{len(learning['confirmation_train_seeds'])}; "
                    f"mean floor {confirmation['summary']['mean_maximum_floor']:.2f}; "
                    f"{confirmation['summary']['failed_runs']} failures.",
                    flush=True,
                )
                if (
                    len(updates) >= learning["minimum_rounds"]
                    and plateau >= learning["plateau_confirmations"]
                ):
                    stop = "confirmed_training_plateau"
                    break
        selection = frozen_json(
            output / "train-selection.json",
            {
                "protocol": protocol,
                "initial_model_id": initial.model_id,
                "champion_model_id": champion.model_id,
                "latest_model_id": model.model_id,
                "round_ids": [r["round_id"] for r in updates],
                "stop_reason": stop,
                "champion_confirmation": confirmation,
                "selection_uses_development": False,
                "checkpoint_promoted": False,
            },
            "selection_id",
        )
        # This checkpoint is frozen before opening any development seed. No optimizer
        # step, candidate selection or follow-up experiment may depend on its results.
        development = {}
        for player in {initial.model_id: initial, champion.model_id: champion}.values():
            result, _ = store.panel(
                player,
                learning["development_seeds"],
                "development",
                round_index=None,
                label="Frozen independent development",
            )
            development[player.model_id] = result
        initial_dev, champion_dev = development[initial.model_id], development[champion.model_id]
        paired = paired_summary(initial_dev, champion_dev, store)
        train_outcomes = tuple(
            TrainingOutcome.from_mapping(o["outcome"])
            for o in store.cases.values()
            if o["binding"]["model_id"] == champion.model_id
            and o["binding"]["seed"] in learning["confirmation_train_seeds"]
        )
        dev_outcomes = tuple(
            TrainingOutcome.from_mapping(o["outcome"])
            for o in store.cases.values()
            if o["binding"]["model_id"] == champion.model_id
            and o["binding"]["partition"] == "development"
        )
        graduation = (
            assess_training_graduation(
                config.score,
                TrainingPanel("train", tuple(learning["confirmation_train_seeds"]), train_outcomes),
                TrainingPanel("development", tuple(learning["development_seeds"]), dev_outcomes),
            )
            if config.score.stage == TrainingStage.BOOTSTRAP
            else None
        )
        cases = sorted(store.cases.values(), key=lambda c: c["case_id"])
        report = frozen_json(
            output / "ppo-report.json",
            {
                "schema_version": REPORT_SCHEMA,
                "protocol": protocol,
                "selection_id": selection["selection_id"],
                "initial_model_id": initial.model_id,
                "champion_model_id": champion.model_id,
                "latest_model_id": model.model_id,
                "rounds_completed": len(updates),
                "stop_reason": stop,
                "updates": updates,
                "development": development,
                "paired_development": paired,
                "champion_checkpoint": str(store.save_model(champion).relative_to(output)),
                "experience_cases": len(cases),
                "public_decisions": sum(c["outcome"]["decisions"] for c in cases),
                "recorded_episode_cpu_seconds": sum(c["outcome"]["cpu_seconds"] for c in cases),
                "all_episode_costs_known": all(c.get("cpu_seconds_known", True) for c in cases),
                "interrupted_or_worker_failed_attempts": sum(
                    c.get("cpu_seconds_known") is False for c in cases
                ),
                "cases": [
                    {
                        "case_id": c["case_id"],
                        "path": str(
                            store.paths[manifest_identifier(c["binding"])[7:]].relative_to(output)
                        ),
                    }
                    for c in cases
                ],
                "graduation": graduation,
                "checkpoint_promoted": False,
                "foundation_readiness_established": False,
                "final_test_opened": False,
                "automatic_followup": False,
                "compute_scope": (
                    "episode_costs_plus_separate_job_wide_resource_reports_including_optimizer"
                ),
            },
            "report_id",
        )
    return report


def paired_summary(
    initial: dict[str, Any], champion: dict[str, Any], store: ExperienceStore
) -> dict[str, Any]:
    by_id = {c["case_id"]: c for c in store.cases.values()}
    pairs = [
        (by_id[a], by_id[b]) for a, b in zip(initial["case_ids"], champion["case_ids"], strict=True)
    ]
    differences = [b["outcome"]["maximum_floor"] - a["outcome"]["maximum_floor"] for a, b in pairs]
    return {
        "planned_pairs": len(pairs),
        "both_completed": sum(
            a.get("score", {}).get("completed", False)
            and b.get("score", {}).get("completed", False)
            for a, b in pairs
        ),
        "champion_only_victories": sum(
            not a.get("score", {}).get("victory", False)
            and b.get("score", {}).get("victory", False)
            for a, b in pairs
        ),
        "initial_only_victories": sum(
            a.get("score", {}).get("victory", False)
            and not b.get("score", {}).get("victory", False)
            for a, b in pairs
        ),
        "mean_maximum_floor_difference": sum(differences) / len(pairs),
        "claim_scope": "paired_independent_development_not_final_test_or_foundation_readiness",
    }


def inspect_ppo(config_path: Path, output: Path) -> dict[str, Any]:
    config = load_ppo_config(config_path)
    report = identified_document(output / "ppo-report.json")
    if report["schema_version"] != REPORT_SCHEMA or report["protocol"] != ppo_protocol(config):
        raise ValueError("Saved PPO result belongs to another implementation or configuration")
    saved_protocol = identified_document(output / "protocol.json", "protocol_id")
    if {k: v for k, v in saved_protocol.items() if k != "protocol_id"} != report["protocol"]:
        raise ValueError("Saved PPO protocol differs")
    selection = identified_document(output / "train-selection.json", "selection_id")
    if (
        selection["selection_id"] != report["selection_id"]
        or selection["champion_model_id"] != report["champion_model_id"]
        or selection["selection_uses_development"] is not False
    ):
        raise ValueError("Saved training-only checkpoint selection differs")
    for round_index, update in enumerate(report["updates"]):
        saved_round = identified_document(output / f"round-{round_index:03d}.json", "round_id")
        if (
            saved_round["round_id"] != update["round_id"]
            or saved_round["protocol"] != report["protocol"]
        ):
            raise ValueError("Saved PPO optimizer checkpoint differs")
    for name in ("initial_model_id", "champion_model_id", "latest_model_id"):
        if (
            load_actor_critic(output / "models" / (report[name][7:] + ".json")).model_id
            != report[name]
        ):
            raise ValueError("Saved PPO model identity differs")
    for ref in report["cases"]:
        path = output / ref["path"]
        case = (
            identified_document(path, "case_id")
            if path.name == "failure.json"
            else json.loads(path.read_text())
        )
        if path.name != "failure.json":
            case, _ = load_a8_episode(path, case["binding"])
        if case["case_id"] != ref["case_id"]:
            raise ValueError("Saved PPO experience identity differs")
        binding = case["binding"]
        behavior_model = load_actor_critic(output / "models" / (binding["model_id"][7:] + ".json"))
        expected = episode_binding(
            config.ruleset,
            behavior_model,
            config.score,
            config.splits,
            binding["seed"],
            binding["partition"],
            config.document["maximum_decisions"],
            binding["behavior"],
            binding["temperature"],
            binding["sampling_seed"],
        )
        if binding != expected:
            raise ValueError("Saved episode experiment binding differs")
    return report


def summarize_ppo(report: dict[str, Any], output: Path) -> dict[str, Any]:
    return {
        "report_id": report["report_id"],
        "rounds_completed": report["rounds_completed"],
        "stop_reason": report["stop_reason"],
        "initial": report["development"][report["initial_model_id"]]["summary"],
        "trained": report["development"][report["champion_model_id"]]["summary"],
        "paired_development": report["paired_development"],
        "champion_checkpoint": str((output / report["champion_checkpoint"]).resolve()),
        "experience_cases": report["experience_cases"],
        "public_decisions": report["public_decisions"],
        "all_episode_costs_known": report["all_episode_costs_known"],
        "selected_player_is_initializer": report["champion_model_id"] == report["initial_model_id"],
        "interrupted_or_worker_failed_attempts": report["interrupted_or_worker_failed_attempts"],
        "checkpoint_promoted": False,
        "foundation_readiness_established": False,
        "final_test_opened": False,
        "automatic_followup": False,
    }
