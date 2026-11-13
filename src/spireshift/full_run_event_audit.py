"""Versioned event repair replays, preserving the original 89-case failed audit."""

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
    public_choice_manifest,
)
from spireshift.core.manifest import PatchManifest, load_patch_manifest, manifest_identifier
from spireshift.core.objective import ObjectiveSpec
from spireshift.full_run_backend_repair import load_repair_recipe, show_backend_repair
from spireshift.full_run_experience import PublicProgress, atomic_json, load_episode
from spireshift.full_run_public_audit import (
    IntegrationRecipe,
    _checked,
    audit_replay_case,
    integration_implementation_id,
    load_integration_recipe,
    show_integration_audit,
)
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

CONFIG_SCHEMA = "event-public-integration-audit-config-v1"
REPORT_SCHEMA = "event-public-integration-audit-v1"
CAPS = {
    "wall_seconds": 240,
    "cpu_seconds": 240,
    "memory_bytes": 8000000000,
    "storage_bytes": 2000000000,
}
NO_LEARNING = {
    "live_game_conformance_verified": False,
    "admitted": False,
    "training_allowed": False,
    "optimizer_steps": 0,
    "checkpoint_promoted": False,
    "final_test_opened": False,
    "automatic_followup": False,
}


@dataclass(frozen=True)
class EventIntegrationRecipe:
    document: dict[str, Any]
    base: IntegrationRecipe
    manifest: PatchManifest

    @property
    def output(self) -> Path:
        return self.base.path(self.document["output_dir"])


def load_event_integration_recipe(
    path: Path, *, root: Path | None = None
) -> EventIntegrationRecipe:
    root = (root or Path.cwd()).resolve()
    d = _checked(path, "config_id")
    if (
        set(d)
        != {
            "schema_version",
            "config_id",
            "base_config",
            "previous_audit",
            "backend_config",
            "integration_manifest",
            "event_endpoints",
            "output_dir",
            "resource_limits",
            "automatic_training",
            "automatic_admission",
        }
        or d["schema_version"] != CONFIG_SCHEMA
    ):
        raise ValueError("Unknown event integration audit configuration")
    if d["automatic_training"] is not False or d["automatic_admission"] is not False:
        raise ValueError("Compatibility evidence cannot authorize learning or admission")
    if d["resource_limits"] != CAPS:
        raise ValueError("The short event audit requires its four-minute resource caps")
    for key in ("base_config", "previous_audit", "backend_config", "integration_manifest"):
        if set(d[key]) != {"path", "id"}:
            raise ValueError(f"Event audit {key} fields differ")
    base = load_integration_recipe(root / d["base_config"]["path"], root=root)
    previous = show_integration_audit(base)
    if (
        base.document["config_id"] != d["base_config"]["id"]
        or (root / d["previous_audit"]["path"]).resolve() != base.output / "integration-audit.json"
        or previous["report_id"] != d["previous_audit"]["id"]
    ):
        raise ValueError("The preserved 89-case source audit differs")
    endpoints = d["event_endpoints"]
    if not isinstance(endpoints, list) or not endpoints:
        raise ValueError("Event endpoints must retain every previous failed case")
    ids = []
    for endpoint in endpoints:
        if set(endpoint) != {
            "source_case_id",
            "event_id",
            "expected_encounter_id",
            "source_floor",
            "first_invalid_decision",
            "skipped_noop_actions",
        } or (
            (endpoint["event_id"], endpoint["expected_encounter_id"]) not in {(12, 55), (23, 56)}
            or any(
                type(endpoint[k]) is not int or endpoint[k] <= 0
                for k in ("source_floor", "first_invalid_decision", "skipped_noop_actions")
            )
            or endpoint["skipped_noop_actions"] != 3
        ):
            raise ValueError("Event endpoint exceeds the diagnosed three-noop repair scope")
        ids.append(endpoint["source_case_id"])
    failed_ids = [e["source_case_id"] for e in previous["cases"] if e["status"] == "failed"]
    if len(set(ids)) != len(ids) or sorted(ids) != sorted(failed_ids):
        raise ValueError("Every previous failed case must remain in the event audit")
    backend = load_repair_recipe(root / d["backend_config"]["path"], root=root)
    if backend.document["config_id"] != d["backend_config"]["id"]:
        raise ValueError("Event repair build configuration changed")
    built = show_backend_repair(backend)
    manifest = load_patch_manifest(root / d["integration_manifest"]["path"])
    expected = public_choice_manifest(
        load_patch_manifest(backend.output / "candidate-manifest.json")
    )
    if (
        manifest.as_dict() != expected.as_dict()
        or manifest.manifest_id != d["integration_manifest"]["id"]
        or built["regression_tests"] != {"executed": 32, "failed": 0, "passed": 32, "total": 32}
    ):
        raise ValueError("Event audit requires the verified new native and public adapter identity")
    output = (root / d["output_dir"]).resolve()
    if not output.is_relative_to(root / "artifacts") or any(
        output.is_relative_to(p) or p.is_relative_to(output)
        for p in (base.output, base.source_root, backend.output, backend.candidate)
    ):
        raise ValueError("The new audit must preserve all historical and backend artifacts")
    return EventIntegrationRecipe(d, base, manifest)


def _selected(row: dict[str, Any]) -> dict[str, Any]:
    return dict(row["legal_candidates"][row["selected_index"]]["payload"])


def _event_tail(trace: list[dict[str, Any]], endpoint: dict[str, Any]) -> None:
    """Only the frozen, demonstrably ineffective action suffix may be replaced."""
    first = endpoint["first_invalid_decision"]
    if len(trace) != first + endpoint["skipped_noop_actions"] or any(
        row["decision_index"] != i for i, row in enumerate(trace)
    ):
        raise ValueError("Original event action ordering or suffix length differs")
    commit, tail = trace[first - 1], trace[first:]
    if _selected(commit) != {"phase": "event", "action_index": 1}:
        raise ValueError("Saved event prefix did not commit to the fight")
    state_hash = tail[0]["observation"]["state_hash"]
    if commit["next_state_hash"] != state_hash:
        raise ValueError("Saved event commit does not lead to the diagnosed suffix")
    for row in tail:
        state = row["observation"]["public_state"]
        if (
            _selected(row) != {"phase": "event", "action_index": 3}
            or sorted(a["payload"]["action_index"] for a in row["legal_candidates"]) != [0, 3]
            or any(a["payload"]["phase"] != "event" for a in row["legal_candidates"])
            or state["phase_id"] != 7
            or state["event_id"] != endpoint["event_id"]
            or state["floor"] != endpoint["source_floor"]
            or row["observation"]["state_hash"] != state_hash
            or row["next_state_hash"] != state_hash
            or row["environment_reward"] != 0
            or row["terminal"] is not False
            or row["victory"] is not False
        ):
            raise ValueError("Saved suffix is not exactly the diagnosed rejected event noops")


def audit_event_case(
    source: Path,
    entry: dict[str, Any],
    endpoint: dict[str, Any],
    factory: Callable[[], PublicChoiceEnvironment],
    policy: PublicFullRunPolicy,
    objective: ObjectiveSpec,
) -> dict[str, Any]:
    cpu_start = time.process_time()
    env: PublicChoiceEnvironment | None = None
    observations = transitions = games = skipped = 0
    progress = PublicProgress()
    checks: Counter[str] = Counter()
    status, error = "failed", None
    try:
        if hashlib.sha256(source.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("Original source case bytes changed")
        raw = json.loads(source.read_text())
        case = load_episode(source, raw["binding"])
        if (
            case["case_id"] != entry["case_id"]
            or entry["case_id"] != endpoint["source_case_id"]
            or case["binding"]["seed"] != entry["run_seed"]
            or case["binding"]["partition"] != "train"
            or case["outcome"]["status"] != "liveness_failure"
        ):
            raise ValueError("Event source episode ownership or failure scope differs")
        with gzip.open(source.with_suffix(".jsonl.gz"), "rt") as handle:
            trace = [json.loads(line) for line in handle]
        if (
            len(trace) != case["outcome"]["decisions"]
            or manifest_identifier(trace) != case["trace_digest"]
        ):
            raise ValueError("Original saved event trace differs")
        _event_tail(trace, endpoint)
        env = factory()
        if env.ruleset != policy.ruleset:
            raise ValueError("Event compatibility environment differs from the player's ruleset")
        games += 1
        observation = env.reset(entry["run_seed"])

        def predict() -> Any:
            nonlocal observations
            if time.process_time() - cpu_start >= objective.whole_run_budget:
                raise ValueError("Event replay reached its frozen whole-run CPU cap")
            progress.observe(observation, transitions)
            if observation.public_state.get("terminal"):
                raise ValueError("Event repair unexpectedly terminated the run")
            actions = env.legal_actions()  # Every action comes from the corrected engine mask.
            decision = policy.predict(observation, actions)
            if len(decision.inputs.bindings) != len(actions):
                raise ValueError("Event player discarded a legal candidate")
            observations += 1
            return decision

        for row in trace[: endpoint["first_invalid_decision"]]:
            predict()
            payload = _selected(row)
            # Complete combat menus have one public locator, without hand-card targets.
            target = (
                -1 if choice_view(observation).combat_selection else payload.get("target_index", -1)
            )
            matched = [
                a
                for a in env.legal_actions()
                if a.payload["action_index"] == payload["action_index"]
                and a.payload.get("target_index", -1) == target
                and a.payload["phase"] == payload["phase"]
            ]
            if len(matched) != 1:
                raise ValueError("Saved prefix action drift is outside the event suffix repair")
            result = env.step(matched[0])
            transitions += 1
            if result.reward != 0 or result.terminal or result.victory:
                raise ValueError("Event prefix changed the terminal-only reward contract")
            observation = result.next_observation
        decision = predict()
        state = observation.public_state
        source_state = trace[endpoint["first_invalid_decision"]]["observation"]["public_state"]
        if (
            any(
                state.get(k) != source_state.get(k)
                for k in ("event_id", "floor", "act", "player_hp", "player_max_hp", "gold", "deck")
            )
            or state["phase"] != "event"
        ):
            raise ValueError("Repaired prefix did not reach the saved public event endpoint")
        legal = env.legal_actions()
        if len(legal) != 1 or legal[0].payload != {"phase": "event", "action_index": 0}:
            raise ValueError(
                "Committed event page still offers a rejected action or lost continuation"
            )
        if decision.selected_action != legal[0]:
            raise ValueError("Player did not select the sole advertised event continuation")
        before_hash = observation.state_hash
        result = env.step(decision.selected_action)
        transitions += 1
        observation = result.next_observation
        if (
            result.reward != 0
            or result.terminal
            or result.victory
            or observation.state_hash == before_hash
            or observation.public_state["phase"] != "combat"
            or observation.public_state["encounter_id"] != endpoint["expected_encounter_id"]
            or any(
                observation.public_state.get(k) != state.get(k)
                for k in ("player_hp", "player_max_hp", "gold", "deck", "floor", "act")
            )
            or not env.legal_actions()
        ):
            raise ValueError(
                "Accepted event continuation did not start the expected playable combat"
            )
        predict()
        skipped = endpoint["skipped_noop_actions"]
        checks["event_continuation_progress"] = 1
        checks["rejected_event_action_absent"] = 1
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
        "status": status,
        "error": error,
        "replay_method": "saved_prefix_then_corrected_event_continuation",
        "event_endpoint": endpoint,
        "skipped_historical_noop_actions": skipped,
        "scored_observations": observations,
        "transitions": transitions,
        "game_prefixes_started": games,
        "checks": dict(checks),
        "observed_acts": progress.acts,
        "cpu_seconds": time.process_time() - cpu_start,
    }


def _protocol(recipe: EventIntegrationRecipe) -> dict[str, Any]:
    return {
        "config_id": recipe.document["config_id"],
        "implementation_id": manifest_identifier(
            {
                "preserved_integration_implementation_id": integration_implementation_id(),
                "event_audit_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            }
        ),
        "ruleset_manifest_id": recipe.manifest.manifest_id,
        "source_index_id": recipe.base.document["source_index"]["id"],
        "previous_audit_id": recipe.document["previous_audit"]["id"],
        "objective": recipe.base.objective.as_dict(),
        "source_declared_ascension_level": 8,
        "historical_claimed_ascension_level": 0,
        "historical_difficulty_claim_valid": False,
    }


def show_event_integration(recipe: EventIntegrationRecipe) -> dict[str, Any]:
    report = _checked(recipe.output / "integration-audit.json")
    if (
        report["schema_version"] != REPORT_SCHEMA
        or report["protocol"] != _protocol(recipe)
        or any(report.get(k) != v for k, v in NO_LEARNING.items())
    ):
        raise ValueError("Event integration result belongs to changed inputs or scope")
    cases = []
    for entry in report["cases"]:
        path = (recipe.output / entry["path"]).resolve()
        if not path.is_relative_to(recipe.output):
            raise ValueError("Event result path escapes its private audit")
        case = _checked(path)
        if any(case[k] != entry[k] for k in ("report_id", "source_case_id", "status")) or (
            case["protocol"] != report["protocol"] or case["status"] not in {"passed", "failed"}
        ):
            raise ValueError("Saved event compatibility case differs")
        cases.append(case)
    passed = sum(c["status"] == "passed" for c in cases)
    checks: Counter[str] = Counter()
    for case in cases:
        checks.update(case["checks"])
    model = load_public_full_run_model(recipe.output / "untrained-player.json")
    if (
        sorted(c["source_case_id"] for c in cases) != recipe.base.document["source_case_ids"]
        or report["benchmark_denominator"] != len(recipe.base.entries)
        or report["completed_cases"] != len(cases)
        or report["passed_cases"] != passed
        or report["failed_cases"] != len(cases) - passed
        or report["compatibility_passed"] is not (passed == len(cases))
        or report["checks"] != dict(checks)
        or report["transitions"] != sum(c["transitions"] for c in cases)
        or report["game_prefixes_started"] != sum(c["game_prefixes_started"] for c in cases)
        or report["skipped_historical_noop_actions"]
        != sum(c["skipped_historical_noop_actions"] for c in cases)
        or report["untrained_model_id"] != model.model_id
        or model.ruleset_manifest_id != recipe.manifest.manifest_id
    ):
        raise ValueError("Saved event audit discarded failures or changed its aggregates/player")
    return report


def run_event_integration(recipe: EventIntegrationRecipe) -> dict[str, Any]:
    if not os.environ.get(EXPERIMENT_METRICS_ENV):
        raise ValueError("Use the short event-audit script for job-wide resource caps")
    recipe.output.mkdir(parents=True, exist_ok=True)
    with (recipe.output / "audit.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (recipe.output / "integration-audit.json").exists():
            return show_event_integration(recipe)
        backend = load_repair_recipe(
            recipe.base.path(recipe.document["backend_config"]["path"]), root=recipe.base.root
        )
        loaded = load_public_choice_backend(
            backend.candidate,
            recipe.base.path(recipe.document["integration_manifest"]["path"]),
            allow_pending=True,
        )
        card_sha = hashlib.sha256((backend.candidate / CARD_SOURCE).read_bytes()).hexdigest()
        model = initial_public_full_run_model(
            recipe.manifest.ruleset_identity(),
            load_printed_card_catalog(backend.candidate, card_sha),
            card_sha,
            **recipe.base.document["network"],
        )
        policy = PublicFullRunPolicy(recipe.manifest.ruleset_identity(), model)
        model_path = recipe.output / "untrained-player.json"
        if model_path.exists():
            if json.loads(model_path.read_text()) != model.as_dict():
                raise ValueError("Partial event audit player differs; refusing to overwrite")
        else:
            atomic_json(model_path, model.as_dict())
        protocol = _protocol(recipe)
        endpoints = {e["source_case_id"]: e for e in recipe.document["event_endpoints"]}
        cases, results = [], []
        new_games = new_steps = 0
        write_experiment_metrics(ExperimentMetrics(trajectories=0, simulations=0, transitions=0))
        for number, entry in enumerate(recipe.base.entries, 1):
            relative = f"cases/{entry['case_id'][7:]}.json"
            path = recipe.output / relative
            if path.exists():
                result = _checked(path)
                if result["protocol"] != protocol or result["source_case_id"] != entry["case_id"]:
                    raise ValueError("Partial event compatibility results differ")
            else:
                source = recipe.base.source_root / entry["path"]
                if entry["case_id"] in endpoints:
                    result = audit_event_case(
                        source,
                        entry,
                        endpoints[entry["case_id"]],
                        loaded.factory,
                        policy,
                        recipe.base.objective,
                    )
                else:
                    result = {
                        **audit_replay_case(
                            source, entry, loaded.factory, policy, recipe.base.objective
                        ),
                        "replay_method": "exact_saved_actions_and_new_endpoint",
                        "skipped_historical_noop_actions": 0,
                    }
                result = {"protocol": protocol, **result}
                result["report_id"] = manifest_identifier(result)
                atomic_json(path, result)
                new_games += result["game_prefixes_started"]
                new_steps += result["transitions"]
                update_experiment_metrics(
                    ExperimentMetrics(trajectories=new_games, simulations=0, transitions=new_steps)
                )
            results.append(result)
            cases.append(
                {
                    "source_case_id": entry["case_id"],
                    "path": relative,
                    "report_id": result["report_id"],
                    "status": result["status"],
                }
            )
            if number % 8 == 0 or number == len(recipe.base.entries):
                print(
                    f"Compatibility cases checked: {number}/{len(recipe.base.entries)}.", flush=True
                )
        checks: Counter[str] = Counter()
        for result in results:
            checks.update(result["checks"])
        passed = sum(c["status"] == "passed" for c in cases)
        body = {
            "schema_version": REPORT_SCHEMA,
            "protocol": protocol,
            "untrained_model_id": model.model_id,
            "benchmark_denominator": len(cases),
            "completed_cases": len(cases),
            "passed_cases": passed,
            "failed_cases": len(cases) - passed,
            "compatibility_passed": passed == len(cases),
            "game_prefixes_started": sum(r["game_prefixes_started"] for r in results),
            "transitions": sum(r["transitions"] for r in results),
            "checks": dict(checks),
            "skipped_historical_noop_actions": sum(
                r["skipped_historical_noop_actions"] for r in results
            ),
            "cases": cases,
            **NO_LEARNING,
            "claim_scope": (
                "inspected_training_prefixes_and_corrected_event_endpoints_"
                "not_playing_strength_or_live_conformance"
            ),
        }
        atomic_json(
            recipe.output / "integration-audit.json",
            {**body, "report_id": manifest_identifier(body)},
        )
        return show_event_integration(recipe)
