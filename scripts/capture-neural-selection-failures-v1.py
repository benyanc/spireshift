"""Reproduce only the two inspected failures; keep public menus and immutable evidence.

Saved captures are checked without replay. New captures require the resource wrapper;
the implementation diagnostic used a 15-second wall/CPU cap. This is not a benchmark.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from spireshift.adapters.evangambit import load_evangambit_backend
from spireshift.agents.learned import ProductionCheckpointPolicy
from spireshift.combat_confirmation import (
    load_combat_confirmation_config,
    load_confirmation_policies,
)
from spireshift.combat_replay_diagnostic import _actions, _observation
from spireshift.core.manifest import load_patch_manifest, manifest_identifier
from spireshift.core.objective import load_objective
from spireshift.core.types import LegalAction, Observation
from spireshift.neural_selection import CAPTURE_CLAIM
from spireshift.production_evaluation import (
    FRESH_PRODUCTION_POLICY_CASE_SCHEMA_VERSION,
    LEARNED_POLICY_KIND,
    _evaluate_case,
    load_production_policy_evaluation,
)
from spireshift.representations import build_model_input
from spireshift.resource_tracking import (
    EXPERIMENT_METRICS_ENV,
    ExperimentMetrics,
    update_experiment_metrics,
    write_experiment_metrics,
)
from spireshift.splits import SplitName, load_split_manifest
from spireshift.starting_evidence import _publish_json
from spireshift.trajectory_policy import _identified

PLAN = "configs/combat-confirmation/sts2-v0.107.1-base-v11-neural-selection-repair-v2.json"
SPLIT = "manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json"
MANIFEST = "artifacts/backend/evangambit-v0.107.1-admitted.json"


class PublicRecorder:
    def __init__(self, policy: ProductionCheckpointPolicy) -> None:
        self.policy = policy
        self.policy_id = policy.policy_id
        self.rows: list[dict[str, Any]] = []

    def choose_action(
        self, observation: Observation, legal_actions: tuple[LegalAction, ...]
    ) -> LegalAction:
        build_model_input(self.policy.ruleset, observation, legal_actions)
        row = {
            "observation": observation.as_dict(),
            "legal_actions": [a.as_dict() for a in legal_actions],
            "selected_action_id": None,
        }
        self.rows.append(row)
        selected = self.policy.choose_action(observation, legal_actions)
        row["selected_action_id"] = selected.action_id
        return selected


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    os.chdir(root)
    config = load_combat_confirmation_config(Path(PLAN))
    repair = config.document["selection_repair"]
    split = load_split_manifest(Path(SPLIT))
    ruleset = load_patch_manifest(Path(MANIFEST)).ruleset_identity()
    objective = load_objective(Path("configs/default.toml"))
    collection_path = Path(repair["capture_collection_path"])
    if collection_path.exists():
        # The corrective preflight validates every saved public row, case and identity
        # without predictions or backend creation. Do not retry a completed capture.
        load_confirmation_policies(
            config=config,
            project_root=root,
            split=split,
            ruleset=ruleset,
            objective=objective,
        )
        saved = json.loads(collection_path.read_text())
        print(
            json.dumps(
                {
                    "valid": True,
                    "capture_collection_id": saved["report_id"],
                    "games_replayed": 0,
                    "source_failures": saved["games"],
                },
                indent=2,
            )
        )
        return
    if EXPERIMENT_METRICS_ENV not in os.environ:
        raise ValueError("New capture requires resources run with explicit wall/CPU caps")
    write_experiment_metrics(ExperimentMetrics(trajectories=0, simulations=0, transitions=0))
    original = load_combat_confirmation_config(Path(repair["source_confirmation_path"]))
    candidate, reference = load_confirmation_policies(
        config=original,
        project_root=root,
        split=split,
        ruleset=ruleset,
        objective=objective,
    )
    source_path = Path(repair["source_comparison_path"])
    source = load_production_policy_evaluation(
        source_path,
        model_id=candidate.model_id,
        training_report_id=original.document["candidate"]["report_id"],
        reference_model_id=reference.model_id,
        reference_training_report_id=original.document["reference"]["report_id"],
        split_manifest=split,
    )
    failures = []
    for entry in source["cases"]:
        case = json.loads((source_path.parent / entry["path"]).read_text())
        if case["status"] == "failed" and case["policy_kind"] == LEARNED_POLICY_KIND:
            failures.append(case)
    if source["report_id"] != repair["source_comparison_report_id"] or sorted(
        c["seed"] for c in failures
    ) != [686, 689]:
        raise ValueError("The frozen two-failure inventory differs")
    backend = None
    entries = []
    new_runs = new_transitions = 0
    out = collection_path.parent
    out.mkdir(parents=True, exist_ok=True)
    for expected in sorted(failures, key=lambda c: c["seed"]):
        path = out / f"seed-{expected['seed']:06d}.json"
        if path.exists():
            capture = json.loads(path.read_text())
            _identified(capture, "capture_id")
        else:
            if backend is None:
                backend = load_evangambit_backend(
                    Path(repair["engine_source_root"]),
                    Path(MANIFEST),
                    max_episode_steps=original.document["maximum_decisions_per_run"] + 1,
                )
            recorder = PublicRecorder(candidate)
            actual = _evaluate_case(
                environment_factory=backend.factory,
                ruleset=ruleset,
                seed=expected["seed"],
                policy_kind=LEARNED_POLICY_KIND,
                policy=recorder,
                model_id=candidate.model_id,
                maximum_decisions=original.document["maximum_decisions_per_run"],
                partition=SplitName.TRAIN,
                cycle_repetition_threshold=original.document["cycle_repetition_threshold"],
                liveness_tail_length=original.document["liveness_tail_length"],
                no_op_fallback_threshold=original.document["no_op_fallback_threshold"],
                schema_version=FRESH_PRODUCTION_POLICY_CASE_SCHEMA_VERSION,
                confirmation=original,
            )
            body = {
                "schema_version": "public-combat-menu-failure-capture-v1",
                "source_report_id": source["report_id"],
                "source_case_id": expected["case_id"],
                "model_id": candidate.model_id,
                "ruleset_manifest_id": ruleset.manifest_id,
                "objective": original.document["objective"],
                "seed": expected["seed"],
                "claim_scope": CAPTURE_CLAIM,
                "public_rows": recorder.rows,
                "replay_result": actual,
                "optimizer_steps": 0,
            }
            capture = {**body, "capture_id": manifest_identifier(body)}
            _publish_json(path, capture)
            new_runs += 1
            new_transitions += actual["activity"]["completed_transitions"]
            update_experiment_metrics(
                ExperimentMetrics(
                    trajectories=new_runs,
                    simulations=0,
                    transitions=new_transitions,
                )
            )
        replay, rows = capture["replay_result"], capture["public_rows"]
        if (
            capture["source_report_id"] != source["report_id"]
            or capture["source_case_id"] != expected["case_id"]
            or any(replay[k] != expected[k] for k in ("status", "error", "public_progress"))
            or any(
                replay["activity"][k] != expected["activity"][k]
                for k in ("attempted_decisions", "completed_transitions")
            )
            or len(rows) != expected["activity"]["attempted_decisions"]
            or not rows
            or rows[-1]["selected_action_id"] is not None
        ):
            raise ValueError("Reproduction differs; saved capture is preserved for review")
        for row in rows:
            build_model_input(
                ruleset, _observation(row["observation"]), _actions(row["legal_actions"])
            )
        vector = rows[-1]["observation"]["public_state"]["observation_vector"]
        entries.append(
            {
                "seed": expected["seed"],
                "path": path.name,
                "capture_id": capture["capture_id"],
                "selection_kind": vector[183],
                "visible_choices": vector[184],
                "legal_action_count": len(rows[-1]["legal_actions"]),
                "source_case_reproduced": True,
            }
        )
    body = {
        "schema_version": "public-combat-menu-failure-capture-collection-v1",
        "source_report_id": source["report_id"],
        "cases": entries,
        "games": len(entries),
        "transitions": sum(c["activity"]["completed_transitions"] for c in failures),
        "new_runs": new_runs,
        "new_transitions": new_transitions,
        "simulations": 0,
        "optimizer_steps": 0,
        "claim_scope": CAPTURE_CLAIM,
    }
    _publish_json(collection_path, {**body, "report_id": manifest_identifier(body)})
    print("Capture saved. Reconstructed captures require explicit identity review before use.")


if __name__ == "__main__":
    main()
