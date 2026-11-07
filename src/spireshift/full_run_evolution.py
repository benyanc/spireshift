"""Owner-launched, finite direct evolution of the complete unified neural genome."""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import random
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spireshift.adapters.evangambit import LoadedEvanGambitBackend, load_evangambit_backend
from spireshift.core.manifest import RulesetIdentity, load_patch_manifest, manifest_identifier
from spireshift.full_run_experience import (
    atomic_json,
    case_binding,
    collect_episode,
    implementation_id,
    load_episode,
    save_episode,
)
from spireshift.full_run_policy import (
    FullRunModel,
    FullRunPolicy,
    initial_full_run_model,
    load_full_run_model,
)
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
    assess_training_graduation,
    load_training_score_spec,
    score_training_panel,
)

CONFIG_SCHEMA = "unified-full-run-evolution-config-v1"
REPORT_SCHEMA = "unified-full-run-evolution-report-v1"


def _positive(value: object, name: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in [{low},{high}]")
    return value


@dataclass(frozen=True, slots=True)
class EvolutionConfig:
    document: dict[str, Any]
    score: TrainingScoreSpec
    splits: SplitManifest
    ruleset: RulesetIdentity

    @property
    def config_id(self) -> str:
        return self.document["config_id"]  # type: ignore[no-any-return]

    @classmethod
    def from_mapping(cls, value: object) -> EvolutionConfig:
        d = _mapping(value, "full-run evolution config")
        _exact_keys(
            d,
            {
                "schema_version",
                "config_id",
                "inputs",
                "network",
                "evolution",
                "workers",
                "maximum_decisions",
                "resource_limits",
            },
            "evolution config",
        )
        if d["schema_version"] != CONFIG_SCHEMA or d["config_id"] != manifest_identifier(
            {k: v for k, v in d.items() if k != "config_id"}
        ):
            raise ValueError("Evolution config identity or schema differs")
        inputs = _mapping(d["inputs"], "evolution inputs")
        _exact_keys(
            inputs,
            {"training_spec", "split_manifest", "ruleset_manifest", "upstream_root"},
            "inputs",
        )
        for name in ("training_spec", "split_manifest", "ruleset_manifest"):
            ref = _mapping(inputs[name], name)
            _exact_keys(ref, {"path", "id"}, name)
            if not isinstance(ref["path"], str) or not ref["path"]:
                raise ValueError("Evolution input path is missing")
        score = load_training_score_spec(Path(inputs["training_spec"]["path"]))
        splits = load_split_manifest(Path(inputs["split_manifest"]["path"]))
        manifest = load_patch_manifest(Path(inputs["ruleset_manifest"]["path"]))
        ruleset = manifest.ruleset_identity()
        if (
            inputs["training_spec"]["id"] != score.spec_id
            or inputs["split_manifest"]["id"] != splits.manifest_id
            or inputs["ruleset_manifest"]["id"] != ruleset.manifest_id
            or splits.ruleset_manifest_id != ruleset.manifest_id
            or score.scope.ruleset_manifest_id != ruleset.manifest_id
            or splits.objective_id != score.evaluation_objective.objective_id
            or score.scope.character != "ironclad"
            or score.scope.ascension != 0
        ):
            raise ValueError("Evolution input identities, difficulty or objectives differ")
        if not isinstance(inputs["upstream_root"], str) or not inputs["upstream_root"]:
            raise ValueError("Evolution upstream root is missing")
        network = _mapping(d["network"], "network")
        _exact_keys(
            network,
            {"dimension", "hidden_units", "initialization_seed", "card_source_sha256"},
            "network",
        )
        _positive(network["dimension"], "dimension", 128, 4096)
        _positive(network["hidden_units"], "hidden units", 4, 128)
        _positive(network["initialization_seed"], "initialization seed", 0, 2**31 - 1)
        digest = network["card_source_sha256"]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
        ):
            raise ValueError("Evolution printed-card source hash is invalid")
        e = _mapping(d["evolution"], "evolution")
        _exact_keys(
            e,
            {
                "population_size",
                "maximum_generations",
                "elite_count",
                "mutation_probability",
                "mutation_scales",
                "initial_diversity",
                "rng_seed",
                "plateau_generations",
                "generation_train_seeds",
                "confirmation_train_seeds",
                "development_seeds",
            },
            "evolution",
        )
        population = _positive(e["population_size"], "population", 4, 128)
        generations = _positive(e["maximum_generations"], "generations", 1, 100)
        _positive(e["elite_count"], "elites", 2, population - 1)
        _positive(e["rng_seed"], "evolution RNG seed", 0, 2**31 - 1)
        _positive(e["plateau_generations"], "plateau", 1, generations)
        for name in ("mutation_probability", "initial_diversity"):
            if type(e[name]) not in (int, float) or not 0 < e[name] <= 1:
                raise ValueError(f"Invalid {name}")
        if (
            not isinstance(e["mutation_scales"], list)
            or not e["mutation_scales"]
            or any(type(v) not in (int, float) or not 0 < v <= 2 for v in e["mutation_scales"])
        ):
            raise ValueError("Mutation scales must be finite positive values <=2")
        seen: set[int] = set()
        for name in ("generation_train_seeds", "confirmation_train_seeds"):
            panels = e[name]
            if not isinstance(panels, list) or len(panels) != generations:
                raise ValueError("Every generation requires frozen training/confirmation panels")
            for panel in panels:
                if not isinstance(panel, list) or not 2 <= len(panel) <= 1024:
                    raise ValueError("Evolution seed panels must be nonempty complete-run panels")
                for seed in panel:
                    if (
                        type(seed) is not int
                        or seed in seen
                        or splits.split_for_seed(seed) != SplitName.TRAIN
                    ):
                        raise ValueError(
                            "Evolution training panels overlap or cross run-owned splits"
                        )
                    seen.add(seed)
        dev = e["development_seeds"]
        if not isinstance(dev, list) or not 2 <= len(dev) <= 1024 or len(set(dev)) != len(dev):
            raise ValueError("Invalid development panel")
        if any(type(s) is not int or splits.split_for_seed(s) != SplitName.VALIDATION for s in dev):
            raise ValueError(
                "Evolution development must use validation seeds; final test stays sealed"
            )
        _positive(d["workers"], "workers", 1, 32)
        _positive(d["maximum_decisions"], "decisions", 1, 10000)
        limits = _mapping(d["resource_limits"], "resource limits")
        _exact_keys(
            limits, {"wall_seconds", "cpu_seconds", "memory_bytes", "storage_bytes"}, "limits"
        )
        for key, cap in limits.items():
            _positive(cap, key, 1, 10**12)
        return cls(d, score, splits, ruleset)


def load_evolution_config(path: Path) -> EvolutionConfig:
    return EvolutionConfig.from_mapping(json.loads(path.read_text(encoding="utf-8")))


def mutate_genome(
    model: FullRunModel, rng: random.Random, scale: float, probability: float
) -> FullRunModel:
    # All four layers are mutable. No distance limit to an old scorer or phase freeze.
    genes = tuple(
        max(-100.0, min(100.0, v + rng.gauss(0, scale))) if rng.random() < probability else v
        for v in model.genome
    )
    return model.with_genome(genes)


def population_models(
    config: EvolutionConfig,
    initial: FullRunModel,
    champion: FullRunModel,
    parents: list[FullRunModel],
    generation: int,
) -> tuple[list[FullRunModel], list[dict[str, Any]]]:
    e = config.document["evolution"]
    # Generation-specific RNG is a checkpointable deterministic schedule, independent
    # of worker completion order. Record its exact seed and genealogy with each stage.
    rng_seed = e["rng_seed"] + generation * 100003
    rng = random.Random(rng_seed)
    retained = [champion, initial, *parents]
    models, lineage, seen = [], [], set()
    for model in retained:
        if model.model_id not in seen:
            models.append(model)
            lineage.append(
                {
                    "model_id": model.model_id,
                    "parent_model_id": None,
                    "operator": "retained",
                    "generation_rng_seed": rng_seed,
                }
            )
            seen.add(model.model_id)
    models, lineage = models[: e["elite_count"]], lineage[: e["elite_count"]]
    while len(models) < e["population_size"]:
        parent = rng.choice(parents or [initial])
        scale = rng.choice(e["mutation_scales"])
        probability = e["initial_diversity"] if generation == 0 else e["mutation_probability"]
        candidate = mutate_genome(parent, rng, scale, probability)
        if candidate.model_id in seen:
            continue
        models.append(candidate)
        seen.add(candidate.model_id)
        lineage.append(
            {
                "model_id": candidate.model_id,
                "parent_model_id": parent.model_id,
                "operator": "independent_gaussian_whole_genome",
                "scale": scale,
                "probability": probability,
                "generation_rng_seed": rng_seed,
            }
        )
    return models, lineage


_BACKEND: LoadedEvanGambitBackend | None = None
_WORKER_POLICIES: dict[str, FullRunPolicy] = {}


def _episode_worker(request: dict[str, Any]) -> dict[str, Any]:
    global _BACKEND
    config = load_evolution_config(Path(request["config_path"]))
    partition = request["partition"]
    expected_split = {"train": SplitName.TRAIN, "development": SplitName.VALIDATION}.get(partition)
    if expected_split is None or config.splits.split_for_seed(request["seed"]) != expected_split:
        raise ValueError("Worker request crosses complete-run split ownership")
    model_path = Path(request["model_path"])
    policy = _WORKER_POLICIES.get(str(model_path))
    if policy is None:
        policy = FullRunPolicy(config.ruleset, load_full_run_model(model_path))
        _WORKER_POLICIES[str(model_path)] = policy
    if _BACKEND is None:
        inputs = config.document["inputs"]
        _BACKEND = load_evangambit_backend(
            Path(inputs["upstream_root"]),
            Path(inputs["ruleset_manifest"]["path"]),
            # The adapter raises on native truncation. Leave one extra native step so
            # our explicit decision cap records a truncation instead of a runtime error.
            max_episode_steps=config.document["maximum_decisions"] + 1,
        )
    case, trace = collect_episode(
        _BACKEND.factory,
        config.ruleset,
        policy,
        config.score,
        seed=request["seed"],
        partition=request["partition"],
        split_id=config.splits.manifest_id,
        maximum_decisions=config.document["maximum_decisions"],
    )
    save_episode(Path(request["case_path"]), case, trace)
    return case


class EpisodeStore:
    def __init__(
        self, config: EvolutionConfig, path: Path, config_path: Path, executor: ProcessPoolExecutor
    ) -> None:
        self.config, self.path, self.config_path, self.executor = (
            config,
            path,
            config_path,
            executor,
        )
        self.new_episodes = self.new_transitions = 0
        self.cases: dict[str, dict[str, Any]] = {}
        self.case_paths: dict[str, Path] = {}

    def evaluate(
        self, models: list[FullRunModel], seeds: list[int], partition: str, label: str
    ) -> dict[str, dict[str, Any]]:
        expected_split = {"train": SplitName.TRAIN, "development": SplitName.VALIDATION}.get(
            partition
        )
        if expected_split is None or any(
            self.config.splits.split_for_seed(s) != expected_split for s in seeds
        ):
            raise ValueError("Episode panel crosses complete-run split ownership")
        futures = {}
        all_keys: dict[str, list[str]] = {}
        for model in models:
            model_path = self.path / "models" / f"{model.model_id[7:]}.json"
            if model_path.exists():
                if load_full_run_model(model_path).model_id != model.model_id:
                    raise ValueError("Saved population model differs")
            else:
                atomic_json(model_path, model.as_dict())
            policy = FullRunPolicy(self.config.ruleset, model)
            all_keys[model.model_id] = []
            for seed in seeds:
                binding = case_binding(
                    self.config.ruleset,
                    policy,
                    self.config.score,
                    seed,
                    partition,
                    self.config.splits.manifest_id,
                    self.config.document["maximum_decisions"],
                )
                key = manifest_identifier(binding)[7:]
                all_keys[model.model_id].append(key)
                if key in self.cases:
                    continue
                directory = self.path / "cases" / key
                completed = sorted(directory.glob("attempt-*/case.json"))
                failed_workers = sorted(directory.glob("attempt-*/worker-failure.json"))
                if failed_workers:
                    if len(failed_workers) != 1 or completed:
                        raise ValueError("Duplicate recorded worker failures")
                    failure = _mapping(json.loads(failed_workers[0].read_text()), "worker failure")
                    if failure["binding"] != binding or failure["case_id"] != manifest_identifier(
                        {k: v for k, v in failure.items() if k != "case_id"}
                    ):
                        raise ValueError("Saved worker failure identity differs")
                    self.cases[key] = failure
                    self.case_paths[key] = failed_workers[0]
                    continue
                if len(completed) > 1:
                    raise ValueError("Duplicate completed full-run episode attempts")
                if completed:
                    self.cases[key] = load_episode(completed[0], binding)
                    self.case_paths[key] = completed[0]
                    continue
                attempts = sorted(directory.glob("attempt-*/started.json"))
                attempt = directory / f"attempt-{len(attempts) + 1:04d}"
                request = {
                    "config_path": str(self.config_path.resolve()),
                    "model_path": str(model_path.resolve()),
                    "seed": seed,
                    "partition": partition,
                    "case_path": str((attempt / "case.json").resolve()),
                }
                atomic_json(
                    attempt / "started.json",
                    {"binding": binding, "request_id": key, "attempt": len(attempts) + 1},
                )
                futures[self.executor.submit(_episode_worker, request)] = (
                    key,
                    binding,
                    attempt / "case.json",
                )
        total = len(models) * len(seeds)
        done = total - len(futures)
        print(
            f"{label}: {done}/{total} saved games; {len(futures)} new attempts queued.", flush=True
        )
        for future in as_completed(futures):
            key, binding, case_path = futures[future]
            try:
                case = future.result()
            except Exception as exc:
                # Preserve worker/import/native failures in the planned denominator;
                # unknown CPU cannot become a misleading zero-cost benchmark claim.
                body = {
                    "schema_version": "unified-worker-failure-v1",
                    "binding": binding,
                    "error": f"{type(exc).__name__}: {exc}",
                    "cpu_seconds_known": False,
                    "outcome": {
                        "seed": binding["seed"],
                        "status": "runtime_error",
                        "completed_acts": 0,
                        "maximum_floor": 0,
                        "decisions": 0,
                        "cpu_seconds": 0.0,
                    },
                }
                case = {**body, "case_id": manifest_identifier(body)}
                atomic_json(case_path.with_name("worker-failure.json"), case)
            self.cases[key] = case
            self.case_paths[key] = (
                case_path if case_path.exists() else case_path.with_name("worker-failure.json")
            )
            self.new_episodes += 1
            self.new_transitions += case["outcome"]["decisions"]
            update_experiment_metrics(
                ExperimentMetrics(
                    trajectories=self.new_episodes, simulations=0, transitions=self.new_transitions
                )
            )
            done += 1
            if done % 8 == 0 or done == total:
                print(f"{label}: {done}/{total} games recorded.", flush=True)
        summaries = {}
        for model in models:
            keys = all_keys[model.model_id]
            outcomes = tuple(TrainingOutcome.from_mapping(self.cases[k]["outcome"]) for k in keys)
            panel = TrainingPanel(partition, tuple(seeds), outcomes)
            scored = score_training_panel(self.config.score, panel)
            summaries[model.model_id] = {
                "model_id": model.model_id,
                "seeds": seeds,
                "case_ids": [self.cases[k]["case_id"] for k in keys],
                "summary": {
                    **scored["summary"],
                    "mean_maximum_floor": sum(o.maximum_floor for o in outcomes) / len(seeds),
                    "mean_completed_acts": sum(o.completed_acts for o in outcomes) / len(seeds),
                },
            }
        return summaries


def _identified(path: Path, body: dict[str, Any], field: str) -> dict[str, Any]:
    result = {**body, field: manifest_identifier(body)}
    if path.exists():
        if json.loads(path.read_text()) != result:
            raise ValueError(f"Frozen evolution checkpoint differs: {path}")
    else:
        atomic_json(path, result)
    return result


def evolution_protocol(config: EvolutionConfig) -> dict[str, Any]:
    return {
        "config_id": config.config_id,
        "episode_implementation_id": implementation_id(),
        "evolution_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "training_spec_id": config.score.spec_id,
        "split_manifest_id": config.splits.manifest_id,
        "ruleset_manifest_id": config.ruleset.manifest_id,
        "claim_scope": "train_direct_neural_evolution_with_final_development_comparison",
        "automatic_followup": False,
        "adaptive_controller_allowed": False,
        "checkpoint_promoted": False,
        "final_test_opened": False,
    }


def run_full_run_evolution(
    config_path: Path, output: Path, *, resume: bool = False
) -> dict[str, Any]:
    config = load_evolution_config(config_path)
    protocol = evolution_protocol(config)
    if output.exists() and not resume:
        raise FileExistsError(f"Use explicit --resume for existing evolution results: {output}")
    output.mkdir(parents=True, exist_ok=True)
    _identified(output / "protocol.json", protocol, "protocol_id")
    final_path = output / "evolution-report.json"
    if final_path.exists():
        return inspect_evolution(config_path, output)
    # An advisory lock prevents two owner launches from writing the same population.
    import fcntl

    with (output / ".owner-run.lock").open("a") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("This full-run pilot is already active in another terminal") from exc
        return _run_locked(config, config_path, output, protocol)


def _run_locked(
    config: EvolutionConfig, config_path: Path, output: Path, protocol: dict[str, Any]
) -> dict[str, Any]:
    inputs, network, e = (config.document[name] for name in ("inputs", "network", "evolution"))
    catalog = load_printed_card_catalog(
        Path(inputs["upstream_root"]), network["card_source_sha256"]
    )
    initial = initial_full_run_model(
        config.ruleset,
        catalog,
        network["card_source_sha256"],
        dimension=network["dimension"],
        hidden_units=network["hidden_units"],
        initialization_seed=network["initialization_seed"],
    )
    champion, parents, stages, plateau = initial, [initial], [], 0
    write_experiment_metrics(ExperimentMetrics(trajectories=0, simulations=0, transitions=0))
    with ProcessPoolExecutor(
        max_workers=config.document["workers"], mp_context=multiprocessing.get_context("spawn")
    ) as executor:
        store = EpisodeStore(config, output, config_path, executor)
        for generation in range(e["maximum_generations"]):
            models, lineage = population_models(config, initial, champion, parents, generation)
            _identified(
                output / f"population-{generation:03d}.json",
                {
                    "protocol": protocol,
                    "generation": generation,
                    "lineage": lineage,
                    "models": [m.model_id for m in models],
                    "generation_train_seeds": e["generation_train_seeds"][generation],
                    "confirmation_train_seeds": e["confirmation_train_seeds"][generation],
                },
                "population_id",
            )
            evaluated = store.evaluate(
                models,
                e["generation_train_seeds"][generation],
                "train",
                f"Generation {generation + 1}/{e['maximum_generations']}",
            )
            ranked = sorted(
                models,
                key=lambda m: (tuple(evaluated[m.model_id]["summary"]["fitness_rank"]), m.model_id),
                reverse=True,
            )
            parents = ranked[: e["elite_count"]]
            finalists = list({m.model_id: m for m in [champion, *ranked[:2]]}.values())
            confirmation = store.evaluate(
                finalists,
                e["confirmation_train_seeds"][generation],
                "train",
                f"Generation {generation + 1} independent train confirmation",
            )
            incumbent_id = champion.model_id
            contender = max(
                finalists, key=lambda m: tuple(confirmation[m.model_id]["summary"]["fitness_rank"])
            )
            improved = tuple(confirmation[contender.model_id]["summary"]["fitness_rank"]) > tuple(
                confirmation[champion.model_id]["summary"]["fitness_rank"]
            )
            if improved:
                champion, plateau = contender, 0
            else:
                plateau += 1
            stage = _identified(
                output / f"generation-{generation:03d}.json",
                {
                    "protocol": protocol,
                    "generation": generation,
                    "population_results": list(evaluated.values()),
                    "confirmation_results": list(confirmation.values()),
                    "previous_champion_id": incumbent_id,
                    "champion_id": champion.model_id,
                    "confirmed_improvement": improved,
                    "plateau_generations": plateau,
                },
                "generation_id",
            )
            stages.append(stage)
            print(
                f"Generation {generation + 1} complete. Confirmed improvement: {improved}; "
                f"champion {champion.model_id[:23]}.",
                flush=True,
            )
            if plateau >= e["plateau_generations"]:
                break
        # The chosen checkpoint is frozen before any development game is opened.
        _identified(
            output / "train-selection.json",
            {
                "protocol": protocol,
                "champion_id": champion.model_id,
                "initial_model_id": initial.model_id,
                "generations": len(stages),
            },
            "selection_id",
        )
        final_models = list({m.model_id: m for m in [initial, champion]}.values())
        development = store.evaluate(
            final_models,
            e["development_seeds"],
            "development",
            "Final paired development comparison",
        )
        last_train_seeds = e["confirmation_train_seeds"][len(stages) - 1]

        def panel(model: FullRunModel, seeds: list[int], partition: str) -> TrainingPanel:
            policy = FullRunPolicy(config.ruleset, model)
            outcomes = []
            for seed in seeds:
                binding = case_binding(
                    config.ruleset,
                    policy,
                    config.score,
                    seed,
                    partition,
                    config.splits.manifest_id,
                    config.document["maximum_decisions"],
                )
                outcomes.append(
                    TrainingOutcome.from_mapping(
                        store.cases[manifest_identifier(binding)[7:]]["outcome"]
                    )
                )
            return TrainingPanel(partition, tuple(seeds), tuple(outcomes))

        graduation = assess_training_graduation(
            config.score,
            panel(champion, last_train_seeds, "train"),
            panel(champion, e["development_seeds"], "development"),
        )
        initial_outcomes = {
            o.seed: o for o in panel(initial, e["development_seeds"], "development").outcomes
        }
        champion_outcomes = {
            o.seed: o for o in panel(champion, e["development_seeds"], "development").outcomes
        }
        pairs = [
            {
                "seed": seed,
                "initial_status": initial_outcomes[seed].status.value,
                "champion_status": champion_outcomes[seed].status.value,
                "maximum_floor_difference": champion_outcomes[seed].maximum_floor
                - initial_outcomes[seed].maximum_floor,
            }
            for seed in e["development_seeds"]
        ]
        incomplete = [
            p
            for p in (output / "cases").glob("*/attempt-*/started.json")
            if not p.with_name("case.json").exists()
        ]
        unique_cases = list(store.cases.values())
        experience_indices = {}
        for partition in ("train", "development"):
            references = [
                {
                    "path": str(store.case_paths[key].relative_to(output)),
                    "sha256": hashlib.sha256(store.case_paths[key].read_bytes()).hexdigest(),
                    "case_id": c["case_id"],
                    "model_id": c["binding"]["model_id"],
                    "run_seed": c["binding"]["seed"],
                    "status": c["outcome"]["status"],
                    "trace_available": store.case_paths[key].name == "case.json",
                }
                for key, c in sorted(store.cases.items())
                if c["binding"]["partition"] == partition
            ]
            index = _identified(
                output / "experience" / f"{partition}-index.json",
                {
                    "schema_version": "unified-full-run-experience-index-v1",
                    "protocol": protocol,
                    "partition": partition,
                    "independent_unit": "complete_run_seed",
                    "cases": references,
                    "unique_run_seeds": sorted({r["run_seed"] for r in references}),
                    "permitted_use": "actual_returns_or_explicit_elite_imitation"
                    if partition == "train"
                    else "evaluation_only",
                    "per_action_causal_labels": False,
                    "softmax_is_behavior_probability": False,
                },
                "index_id",
            )
            experience_indices[partition] = index["index_id"]
        body = {
            "schema_version": REPORT_SCHEMA,
            "protocol": protocol,
            "initial_model_id": initial.model_id,
            "champion_model_id": champion.model_id,
            "champion_checkpoint": f"models/{champion.model_id[7:]}.json",
            "generations_completed": len(stages),
            "stop_reason": "plateau" if plateau >= e["plateau_generations"] else "generation_limit",
            "generation_ids": [s["generation_id"] for s in stages],
            "development": development,
            "paired_development": {
                "planned_pairs": len(pairs),
                "same_checkpoint": initial.model_id == champion.model_id,
                "pairs": pairs,
                "mean_maximum_floor_difference": sum(p["maximum_floor_difference"] for p in pairs)
                / len(pairs),
            },
            "graduation": graduation,
            "experience_cases": len(unique_cases),
            "experience_indices": experience_indices,
            "public_decisions": sum(c["outcome"]["decisions"] for c in unique_cases),
            "recorded_episode_cpu_seconds": sum(c["outcome"]["cpu_seconds"] for c in unique_cases),
            "interrupted_or_worker_failed_attempts": len(incomplete),
            "all_episode_costs_known": not incomplete,
            "total_job_cost_source": "owner_resource_reports_include_all_processes_and_attempts",
            "current_launch_games": store.new_episodes,
            "checkpoint_promoted": False,
            "foundation_readiness_established": False,
            "automatic_followup": False,
        }
        result = {**body, "report_id": manifest_identifier(body)}
        atomic_json(output / "evolution-report.json", result)
        return result


def inspect_evolution(config_path: Path, output: Path) -> dict[str, Any]:
    config = load_evolution_config(config_path)
    result = _mapping(
        json.loads((output / "evolution-report.json").read_text()), "evolution report"
    )
    if result["schema_version"] != REPORT_SCHEMA or result["protocol"] != evolution_protocol(
        config
    ):
        raise ValueError("Saved evolution report protocol differs")
    if result["report_id"] != manifest_identifier(
        {k: v for k, v in result.items() if k != "report_id"}
    ):
        raise ValueError("Saved evolution report identity differs")
    model = load_full_run_model(output / result["champion_checkpoint"])
    if model.model_id != result["champion_model_id"]:
        raise ValueError("Saved champion checkpoint differs")
    return result
