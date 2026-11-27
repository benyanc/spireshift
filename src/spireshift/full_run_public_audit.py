"""Owner-run compatibility replays; never training, admission, or a win-rate benchmark."""

from __future__ import annotations

import fcntl
import gzip
import hashlib
import json
import os
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spireshift.adapters.evangambit_public_choices import (
    PublicChoiceEnvironment,
    choice_view,
    load_public_choice_backend,
    public_adapter_digest,
)
from spireshift.core.manifest import PatchManifest, load_patch_manifest, manifest_identifier
from spireshift.core.objective import ObjectiveSpec, load_objective
from spireshift.full_run_backend_repair import load_repair_recipe, show_backend_repair
from spireshift.full_run_experience import PublicProgress, atomic_json, load_episode
from spireshift.full_run_public_policy import (
    PublicFullRunPolicy,
    initial_public_full_run_model,
    load_public_full_run_model,
)
from spireshift.neural_combat_features import CARD_SOURCE, load_printed_card_catalog
from spireshift.resource_tracking import (
    EXPERIMENT_METRICS_ENV,
    ExperimentMetrics,
    update_experiment_metrics,
    write_experiment_metrics,
)
from spireshift.splits import SplitName, load_split_manifest

CONFIG_SCHEMA = "public-full-run-integration-audit-config-v1"
REPORT_SCHEMA = "public-full-run-integration-audit-v1"


def _checked(path: Path, id_key: str = "report_id") -> dict[str, Any]:
    value: dict[str, Any] = json.loads(path.read_text())
    if value[id_key] != manifest_identifier({k: v for k, v in value.items() if k != id_key}):
        raise ValueError(f"Saved integration input identity differs: {path}")
    return value


def integration_implementation_id() -> str:
    root = Path(__file__).parent
    return manifest_identifier(
        {
            "adapter_digest": public_adapter_digest(),
            "sources": {
                name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                for name in (
                    "full_run_public_policy.py",
                    "full_run_public_audit.py",
                    "full_run_features.py",
                    "full_run_policy.py",
                    "full_run_experience.py",
                    "representations.py",
                    "combat_features.py",
                    "neural_combat_features.py",
                    "core/objective.py",
                )
            },
        }
    )


@dataclass(frozen=True)
class IntegrationRecipe:
    document: dict[str, Any]
    root: Path
    manifest: PatchManifest
    objective: ObjectiveSpec
    entries: tuple[dict[str, Any], ...]

    def path(self, value: str) -> Path:
        return (self.root / value).resolve()

    @property
    def output(self) -> Path:
        return self.path(self.document["output_dir"])

    @property
    def source_root(self) -> Path:
        return self.path(self.document["source_index"]["case_root"])


def load_integration_recipe(path: Path, *, root: Path | None = None) -> IntegrationRecipe:
    root = (root or Path.cwd()).resolve()
    d = _checked(path, "config_id")
    expected = {
        "schema_version",
        "config_id",
        "backend_config",
        "integration_manifest",
        "source_index",
        "split_manifest",
        "objective",
        "source_case_ids",
        "network",
        "output_dir",
        "resource_limits",
        "automatic_training",
        "automatic_admission",
    }
    if set(d) != expected or d["schema_version"] != CONFIG_SCHEMA:
        raise ValueError("Unknown public integration audit configuration")
    if d["automatic_training"] is not False or d["automatic_admission"] is not False:
        raise ValueError("Compatibility replays do not authorize training or admission")
    if d["network"] != {"dimension": 256, "hidden_units": 16, "initialization_seed": 0}:
        raise ValueError("The integration audit uses one frozen, untrained player")
    if d["resource_limits"] != {
        "wall_seconds": 1800,
        "cpu_seconds": 3600,
        "memory_bytes": 8000000000,
        "storage_bytes": 2000000000,
    }:
        raise ValueError("Integration audit resource caps differ")
    for key in ("backend_config", "integration_manifest", "split_manifest"):
        if set(d[key]) != {"path", "id"}:
            raise ValueError(f"Integration {key} fields differ")
    if set(d["source_index"]) != {"path", "id", "case_root"}:
        raise ValueError("Integration source index must declare its case path root")
    if set(d["objective"]) != {"path", "id", "sha256"}:
        raise ValueError("Integration objective fields differ")
    objective_path = root / d["objective"]["path"]
    objective = load_objective(objective_path)
    if (
        objective.objective_id != d["objective"]["id"]
        or hashlib.sha256(objective_path.read_bytes()).hexdigest() != d["objective"]["sha256"]
    ):
        raise ValueError("Integration objective changed")
    manifest = load_patch_manifest(root / d["integration_manifest"]["path"])
    if (
        manifest.manifest_id != d["integration_manifest"]["id"]
        or manifest.admission_status != "pending_conformance"
    ):
        raise ValueError("Integration manifest is not the frozen pending candidate")
    splits = load_split_manifest(root / d["split_manifest"]["path"])
    index = _checked(root / d["source_index"]["path"], "index_id")
    if (
        splits.manifest_id != d["split_manifest"]["id"]
        or index["index_id"] != d["source_index"]["id"]
        or index["partition"] != "train"
        or index["protocol"]["split_manifest_id"] != splits.manifest_id
    ):
        raise ValueError("Compatibility sources must be the frozen training-only index")
    entries = tuple(
        e
        for e in index["cases"]
        if e["status"] in {"unsupported", "liveness_failure"} and e["trace_available"]
    )
    if (
        not entries
        or len({e["case_id"] for e in entries}) != len(entries)
        or sorted(e["case_id"] for e in entries) != d["source_case_ids"]
        or any(splits.split_for_seed(e["run_seed"]) != SplitName.TRAIN for e in entries)
    ):
        raise ValueError("Every frozen failed training case must remain in the audit denominator")
    if not (root / d["output_dir"]).resolve().is_relative_to(root / "artifacts"):
        raise ValueError("Integration audit outputs must remain private")
    source_root = (root / d["source_index"]["case_root"]).resolve()
    output = (root / d["output_dir"]).resolve()
    if not source_root.is_relative_to(root / "artifacts") or not (
        root / d["source_index"]["path"]
    ).resolve().is_relative_to(source_root):
        raise ValueError("The source index and its episodes must remain in original artifacts")
    if output.is_relative_to(source_root) or source_root.is_relative_to(output):
        raise ValueError("Replay outputs must be separate from original experience")
    if any(not (source_root / e["path"]).resolve().is_relative_to(source_root) for e in entries):
        raise ValueError("A source episode escapes the frozen training index")
    return IntegrationRecipe(d, root, manifest, objective, entries)


def audit_replay_case(
    source: Path,
    entry: dict[str, Any],
    factory: Callable[[], PublicChoiceEnvironment],
    policy: PublicFullRunPolicy,
    objective: ObjectiveSpec,
) -> dict[str, Any]:
    """Replay saved actions, score current legal choices, and test the failure endpoint."""
    cpu_start = time.process_time()
    env: PublicChoiceEnvironment | None = None
    observations, transitions, games = 0, 0, 0
    checks: Counter[str] = Counter()
    progress = PublicProgress()
    original_error: str | None = None
    status, error = "failed", None
    try:
        if hashlib.sha256(source.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("Original source case bytes changed")
        raw_case = json.loads(source.read_text())
        case = load_episode(source, raw_case["binding"])
        if (
            case["case_id"] != entry["case_id"]
            or case["binding"]["partition"] != "train"
            or case["binding"]["seed"] != entry["run_seed"]
        ):
            raise ValueError("Original source episode ownership differs")
        original_error = case["error"]
        with gzip.open(source.with_suffix(".jsonl.gz"), "rt") as handle:
            trace = [json.loads(line) for line in handle]
        if len(trace) != case["outcome"]["decisions"] or case[
            "trace_digest"
        ] != manifest_identifier(trace):
            raise ValueError("Original saved trace content differs")
        env = factory()
        if env.ruleset != policy.ruleset:
            raise ValueError("Compatibility environment differs from its player's ruleset")
        games += 1
        observation = env.reset(entry["run_seed"])

        def predict() -> Any:
            nonlocal observations
            if time.process_time() - cpu_start >= objective.whole_run_budget:
                raise ValueError("Compatibility case reached its frozen whole-run CPU cap")
            progress.observe(observation, transitions)
            if observation.public_state.get("terminal"):
                victory = bool(observation.public_state.get("victory"))
                progress.completed_acts(victory)
                return None
            view = choice_view(observation)
            if view.combat_selection is not None:
                checks["combat_menu"] += 1
                if len(view.combat_selection["cards"]) > 10:
                    checks["overflow_menu"] += 1
            if view.bundle_selection is not None:
                checks["bundle_menu"] += 1
            decision = policy.predict(observation, env.legal_actions())
            if len(decision.inputs.bindings) != len(env.legal_actions()):
                raise ValueError("New player discarded a legal candidate")
            observations += 1
            return decision

        for index, row in enumerate(trace):
            if row["decision_index"] != index:
                raise ValueError("Original action prefix ordering differs")
            if predict() is None:
                raise ValueError("Repaired replay terminated before the saved failure endpoint")
            payload = row["legal_candidates"][row["selected_index"]]["payload"]
            target = (
                -1
                if choice_view(observation).combat_selection is not None
                else payload.get("target_index", -1)
            )
            legal = [
                a
                for a in env.legal_actions()
                if a.payload["action_index"] == payload["action_index"]
                and a.payload.get("target_index", -1) == target
                and a.payload["phase"] == payload["phase"]
            ]
            if len(legal) != 1:
                raise ValueError("Saved action locator is no longer unambiguously legal")
            transition = env.step(legal[0])
            transitions += 1
            if transition.reward not in (0, 1) or transition.reward != float(
                transition.terminal and transition.victory
            ):
                raise ValueError(
                    "Compatibility replay changed the terminal-only environment reward"
                )
            observation = transition.next_observation
        decision = predict()
        if original_error and "combat selection exceeds visible cards" in original_error:
            view = choice_view(observation)
            if view.combat_selection is None or len(view.combat_selection["cards"]) <= 10:
                raise ValueError("The saved overflow failure was not reached")
            checks["overflow_endpoint_bound"] += 1
        elif original_error and "Public card identity must be positive" in original_error:
            if decision is None or not any(
                b.get("card", {}).get("card_id", 0) > 0 for b in decision.inputs.bindings
            ):
                raise ValueError("The saved reward-identity failure was not bound")
            checks["reward_endpoint_bound"] += 1
        elif original_error and "Terminal victory did not traverse" in original_error:
            if observation.public_state.get("terminal"):
                raise ValueError("The saved premature ending still terminates the run")
            checks["premature_ending_removed"] += 1
        elif case["outcome"]["status"] == "liveness_failure":
            view = choice_view(observation)
            if view.bundle_selection is None or decision is None:
                raise ValueError("Saved stall is outside the bundle-confirmation repair")
            if decision.inputs.bindings[decision.candidate_index]["kind"] != "confirm_bundle":
                raise ValueError("Untrained repaired player did not confirm the selected bundle")
            observation = env.step(decision.selected_action).next_observation
            transitions += 1
            if choice_view(observation).bundle_selection is not None:
                raise ValueError("Bundle confirmation did not exit its menu")
            checks["bundle_confirmation_progress"] += 1
        else:
            raise ValueError("Saved failure is outside this repair's declared scope")
        status = "passed"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if env is not None:
            try:
                env.close()
            except Exception as exc:
                status, error = "failed", f"Environment close failed: {exc}"
    return {
        "source_case_id": entry["case_id"],
        "source_error": original_error,
        "status": status,
        "error": error,
        "scored_observations": observations,
        "transitions": transitions,
        "game_prefixes_started": games,
        "checks": dict(checks),
        "observed_acts": progress.acts,
        "cpu_seconds": time.process_time() - cpu_start,
    }


def _protocol(recipe: IntegrationRecipe) -> dict[str, Any]:
    return {
        "config_id": recipe.document["config_id"],
        "implementation_id": integration_implementation_id(),
        "ruleset_manifest_id": recipe.manifest.manifest_id,
        "source_index_id": recipe.document["source_index"]["id"],
        "objective": recipe.objective.as_dict(),
        "source_declared_ascension_level": 8,
        "historical_claimed_ascension_level": 0,
        "historical_difficulty_claim_valid": False,
    }


def show_integration_audit(recipe: IntegrationRecipe) -> dict[str, Any]:
    report = _checked(recipe.output / "integration-audit.json")
    if report["protocol"] != _protocol(recipe) or report["benchmark_denominator"] != len(
        recipe.entries
    ):
        raise ValueError("Saved integration audit belongs to changed inputs or implementation")
    for entry in report["cases"]:
        case = _checked(recipe.output / entry["path"])
        if (
            case["report_id"] != entry["report_id"]
            or case["protocol"] != report["protocol"]
            or case["status"] != entry["status"]
            or case["source_case_id"] != entry["source_case_id"]
            or case["status"] not in {"passed", "failed"}
        ):
            raise ValueError("Saved compatibility case identity differs")
    if (
        len(report["cases"]) != len(recipe.entries)
        or sorted(c["source_case_id"] for c in report["cases"])
        != recipe.document["source_case_ids"]
    ):
        raise ValueError("Saved audit discarded source failures")
    passed = sum(c["status"] == "passed" for c in report["cases"])
    if (
        report["completed_cases"] != len(recipe.entries)
        or report["passed_cases"] != passed
        or report["failed_cases"] != len(recipe.entries) - passed
        or report["compatibility_passed"] is not (passed == len(recipe.entries))
        or load_public_full_run_model(recipe.output / "untrained-player.json").model_id
        != report["untrained_model_id"]
    ):
        raise ValueError("Saved audit aggregates or untrained player changed")
    return report


def run_integration_audit(recipe: IntegrationRecipe) -> dict[str, Any]:
    if not os.environ.get(EXPERIMENT_METRICS_ENV):
        raise ValueError("Use the owner integration-audit script for batch resource caps")
    recipe.output.mkdir(parents=True, exist_ok=True)
    with (recipe.output / "owner.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (recipe.output / "integration-audit.json").exists():
            return show_integration_audit(recipe)
        backend_recipe = load_repair_recipe(
            recipe.path(recipe.document["backend_config"]["path"]), root=recipe.root
        )
        if backend_recipe.document["config_id"] != recipe.document["backend_config"]["id"]:
            raise ValueError("Integration native build configuration differs")
        built = show_backend_repair(backend_recipe)
        if not built.get("public_choice_export_check"):
            raise ValueError("Owner native public-choice capability check is missing")
        loaded = load_public_choice_backend(
            backend_recipe.candidate,
            recipe.path(recipe.document["integration_manifest"]["path"]),
            allow_pending=True,
        )
        if loaded.evidence.native_sha256 != built["native_sha256"]:
            raise ValueError("Integration library differs from its owner build")
        card_sha = hashlib.sha256((backend_recipe.candidate / CARD_SOURCE).read_bytes()).hexdigest()
        model = initial_public_full_run_model(
            recipe.manifest.ruleset_identity(),
            load_printed_card_catalog(backend_recipe.candidate, card_sha),
            card_sha,
            **recipe.document["network"],
        )
        policy = PublicFullRunPolicy(recipe.manifest.ruleset_identity(), model)
        model_path = recipe.output / "untrained-player.json"
        if model_path.exists():
            if json.loads(model_path.read_text()) != model.as_dict():
                raise ValueError("Saved integration player differs")
        else:
            atomic_json(model_path, model.as_dict())
        protocol = _protocol(recipe)
        write_experiment_metrics(ExperimentMetrics(trajectories=0, simulations=0, transitions=0))
        new_games = new_steps = 0
        cases = []
        for number, entry in enumerate(recipe.entries, 1):
            relative = f"cases/{entry['case_id'][7:]}.json"
            output = recipe.output / relative
            if output.exists():
                result = _checked(output)
                if result["protocol"] != protocol or result["source_case_id"] != entry["case_id"]:
                    raise ValueError("Partial compatibility results differ; refusing to overwrite")
            else:
                result = {
                    "protocol": protocol,
                    **audit_replay_case(
                        recipe.source_root / entry["path"],
                        entry,
                        loaded.factory,
                        policy,
                        recipe.objective,
                    ),
                }
                result["report_id"] = manifest_identifier(result)
                atomic_json(output, result)
                new_games += result["game_prefixes_started"]
                new_steps += result["transitions"]
                update_experiment_metrics(
                    ExperimentMetrics(trajectories=new_games, simulations=0, transitions=new_steps)
                )
            cases.append(
                {
                    "source_case_id": entry["case_id"],
                    "path": relative,
                    "report_id": result["report_id"],
                    "status": result["status"],
                }
            )
            if number % 8 == 0 or number == len(recipe.entries):
                print(
                    f"Compatibility replays checked: {number}/{len(recipe.entries)}. "
                    "No training follows.",
                    flush=True,
                )
        passed = sum(c["status"] == "passed" for c in cases)
        body = {
            "schema_version": REPORT_SCHEMA,
            "protocol": protocol,
            "untrained_model_id": model.model_id,
            "benchmark_denominator": len(recipe.entries),
            "completed_cases": len(cases),
            "passed_cases": passed,
            "failed_cases": len(cases) - passed,
            "compatibility_passed": passed == len(recipe.entries),
            "cases": cases,
            "live_game_conformance_verified": False,
            "admitted": False,
            "training_allowed": False,
            "optimizer_steps": 0,
            "checkpoint_promoted": False,
            "final_test_opened": False,
            "automatic_followup": False,
            "claim_scope": (
                "replayed_inspected_training_failure_prefixes_"
                "not_playing_strength_or_live_conformance"
            ),
        }
        report = {**body, "report_id": manifest_identifier(body)}
        atomic_json(recipe.output / "integration-audit.json", report)
        return report
