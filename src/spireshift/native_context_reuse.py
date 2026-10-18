"""Read-only, explicitly scoped import of the capped context comparison.

Closed audited panels may supply saved comparisons or starting evaluations.
Interrupted prefixes are counted and sealed for diagnosis, never PPO samples.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode
from spireshift.engine_experience_stream import stopped_worker_evidence
from spireshift.engine_learning import identified
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_action_context import CROSSED, ORIGINAL, initialize
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_game import verified_samples
from spireshift.native_context_trial import load_trial
from spireshift.training_objective import load_training_score_spec


def check_sources(root: Path, sources: dict[str, str]) -> None:
    for name, sha in sources.items():
        p = root / name
        if (
            Path(name).is_absolute()
            or ".." in Path(name).parts
            or p.resolve() != root.resolve() / name
            or not p.is_file()
            or _sha_file(p) != sha
        ):
            raise ValueError(f"Preserved evidence changed: {name}")


def verified_panel(root: Path, panel: Path, count: int, model_id: str) -> dict[str, Any]:
    summary = json.loads((panel / "summary.json").read_text())
    paths = list(panel.glob("case-*.json"))
    audited: set[str] = set()
    for p in panel.glob("worker-*/experience-audit.json"):
        audit = identified(p)
        if not audit["valid"] or audit["interrupted_diagnostic_prefix"]:
            raise ValueError("Only closed audited panels may supply saved evaluations")
        check_sources(
            root,
            {str((p.parent / n).relative_to(root)): s for n, s in audit["source_sha256"].items()},
        )
        for case in audit["sealed_cases"]:
            header = Path(case["path"])
            if header.parent != panel or _sha_file(header) != case["sha256"]:
                raise ValueError("Saved audit binds another panel or changed case")
            if _sha_file(header.with_suffix(".jsonl.gz")) != case["trace_sha256"]:
                raise ValueError("Saved audited trace changed")
            if str(header) in audited:
                raise ValueError("Saved case is audited twice")
            audited.add(str(header))
    if (
        summary["planned_games"] != count
        or summary["completed_games"] != count
        or summary["failed_games"]
        or summary["not_attempted_games"]
        or summary["worker_failures"]
        or summary["model_id"] != model_id
        or len(paths) != count
        or {str(p) for p in paths} != audited
    ):
        raise ValueError("Saved panel denominator, model or closure differs")
    outcomes = {c["seed_id"]: c for c in summary["outcomes"]}
    if len(outcomes) != count:
        raise ValueError("Saved evaluation repeats a complete-run seed")
    for p in paths:
        header = json.loads(p.read_text())
        body = {k: v for k, v in header.items() if k not in {"case_id", "trace_file_sha256"}}
        c, b = header["episode"], header["binding"]
        o = outcomes[b["seed_id"]]
        if (
            header["case_id"] != manifest_identifier(body)
            or header["trace_file_sha256"] != _sha_file(p.with_suffix(".jsonl.gz"))
            or b["model_id"] != model_id
            or c["status"] != "terminal"
            or not c["native_ending_evidence_agrees"]
            or c["privileged_fixture"]
            or c["recovered"]
            or any(
                o[k] != c[k]
                for k in ("seed", "status", "victory", "maximum_floor", "completed_acts")
            )
            or o["decision_count"] != header["decision_count"]
        ):
            raise ValueError("Saved case seal, ending or summary differs")
    return dict(summary)


def capture(
    q: EngineQualificationConfig, recipe: Path, resource: Path, output: Path
) -> dict[str, Any]:
    if output.exists():
        saved = identified(output)
        check_sources(q.root, saved["sources"])
        return saved
    cfg, parent, seeds = load_trial(q, recipe)
    workspace = q.root / cfg["workspace"]
    cap = identified(resource)
    if (
        cap["status"] != "capped"
        or (workspace / "report.json").exists()
        or json.loads((workspace / "config-at-launch.json").read_text()) != cfg
    ):
        raise ValueError("Import requires the preserved capped, incomplete original trial")
    for name, sha in cfg["implementation_sha256"].items():
        if _sha_file(workspace / "source-at-launch" / name) != sha:
            raise ValueError("Legacy launch source changed")
    score = load_training_score_spec(q.root / parent["training_spec"]["path"])
    completed, initial = [], {}
    for mode, rep in ((ORIGINAL, 0), (CROSSED, 0), (ORIGINAL, 1), (CROSSED, 1)):
        arm = workspace / f"{mode}-seed-{rep}"
        model = CachedContextModel.from_mapping(
            json.loads((arm / "initial-model.json").read_text())
        )
        expected = initialize(parent["environment_manifest"]["id"], score.spec_id, rep, mode)
        if model.as_dict() != expected.as_dict():
            raise ValueError("Saved initializer differs from the fresh matched player")
        starting = verified_panel(q.root, arm / "development-initial", 16, model.model_id)
        if rep == 1:
            own = [s for s in seeds["seeds"] if s["partition"] == "development"][16:32]
            if {c["seed_id"] for c in starting["outcomes"]} != {s["id"] for s in own}:
                raise ValueError("Reused starting evaluation has different reserved seeds")
            # Check all saved behavior probabilities using the identity-compatible cache.
            for p in (arm / "development-initial").glob("case-*.json"):
                header = json.loads(p.read_text())
                case = read_native_episode(p, header["binding"])
                verified_samples(case, model, score, 0, parent["learning"]["ppo"]["temperature"])
            initial[mode] = {"model_id": model.model_id, "summary": starting}
        result_path = arm / "result.json"
        if not result_path.exists():
            continue
        result = json.loads(result_path.read_text())
        if result["training_seed"] != rep or result["mode"] != mode or len(result["rounds"]) != 4:
            raise ValueError("Legacy completed arm extent differs")
        for i in range(1, 5):
            row = result["rounds"][i - 1]
            panel = verified_panel(q.root, arm / f"round-{i:03d}", 32, model.model_id)
            after = CachedContextModel.from_mapping(
                json.loads((arm / f"round-{i:03d}-model.json").read_text())
            )
            if (
                row["before_model_id"] != model.model_id
                or row["after_model_id"] != after.model_id
                or panel not in result["panels"]
            ):
                raise ValueError("Legacy model/round chain differs")
            model = after
        final = verified_panel(q.root, arm / "development-final", 16, model.model_id)
        if (
            final not in result["panels"]
            or starting not in result["panels"]
            or result["final_model_id"] != model.model_id
        ):
            raise ValueError("Legacy result differs from sealed final evaluation")
        completed.append(result)
    if len(completed) != 3:
        raise ValueError("Expected three completed legacy players and one interrupted player")
    stopped = {
        str(p.parent.relative_to(q.root)): stopped_worker_evidence(p.parent)
        for p in workspace.rglob("active.json")
    }
    if len(stopped) != 2:
        raise ValueError("Expected two retained interrupted-worker markers")
    headers = list(workspace.glob("*/*/case-*.json"))
    diagnostic = [
        p
        for p in headers
        if p.parent.name == "round-001" and p.parent.parent.name == f"{CROSSED}-seed-1"
    ]
    if len(headers) != 520 or len(diagnostic) != 24:
        raise ValueError("Original interrupted denominator changed")
    for p in diagnostic:
        header = json.loads(p.read_text())
        body = {k: v for k, v in header.items() if k not in {"case_id", "trace_file_sha256"}}
        if header["case_id"] != manifest_identifier(body) or header[
            "trace_file_sha256"
        ] != _sha_file(p.with_suffix(".jsonl.gz")):
            raise ValueError("Interrupted diagnostic prefix seal changed")
    sources = {
        str(p.relative_to(q.root)): _sha_file(p)
        for p in workspace.rglob("*")
        if p.is_file() and not p.is_symlink()
    }
    sources.update(
        {
            str(p.relative_to(q.root)): _sha_file(p)
            for p in (recipe, resource, q.root / cfg["seed_manifest"]["path"])
        }
    )
    body = {
        "schema_version": "native-context-legacy-import-v2",
        "original_config_id": manifest_identifier(cfg),
        "resource_report_id": cap["report_id"],
        "original_planned_games": 640,
        "sealed_games": 520,
        "closed_audited_games": 496,
        "excluded_interrupted_prefix_games": 24,
        "unsealed_original_slots": 120,
        "unsealed_attempt_count_unknown": True,
        "completed_arms": completed,
        "reused_initial_panels": initial,
        "primary_complete_pair_seed": 0,
        "diagnostic_unpaired_baseline_seed": 1,
        "replacement_protocol": "fresh_matched_pair_training_seed_1",
        "stopped_worker_evidence": stopped,
        "sources": sources,
        "games_replayed": 0,
        "optimizer_steps": 0,
        "interrupted_prefix_admitted_for_training": False,
        "claim_scope": "sealed_historical_results_and_reserved_initial_evaluations_only",
    }
    report = {**body, "report_id": manifest_identifier(body)}
    atomic_json(output, report)
    return report
