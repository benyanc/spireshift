"""Rebuild sealed summaries/imports and match initial native traces; no policy fitting."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode, score_episode
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_context_reuse import check_sources
from spireshift.native_structured_inputs import load
from spireshift.native_structured_model import ARMS, extend
from spireshift.native_structured_plan import plan, request, summarize
from spireshift.native_structured_state import load as load_state


def trace(case: dict[str, Any]) -> str:
    return manifest_identifier(
        [
            [manifest_identifier(r["public_input"]), r["choice"]["action_index"]]
            for r in case["decisions"]
        ]
    )


def audit(root: Path, path: Path, output: Path) -> dict[str, Any]:
    started = time.monotonic()
    context = load(root, path)
    cfg = context["config"]
    store = ChunkJournal(root, cfg)
    source = store.workspace / "report.json"
    report = identified(source)
    if report["config_id"] != store.config_id or report["status"] not in {
        "native_structured_control_complete",
        "native_structured_comparison_complete",
    }:
        raise ValueError("Complete the finite matching representation experiment first")
    if output.exists():
        cached = identified(output)
        if cached["source_report_id"] != report["report_id"]:
            raise ValueError("Preserve the saved audit under its original report")
        check_sources(root, cached["sources"])
        return cached
    done: dict[str, dict[str, Any]] = {}
    initial: dict[tuple[int, int], dict[str, str]] = {}
    games = decisions = imports = 0
    for task in plan(cfg, context["seeds"]):
        if time.monotonic() - started > 180:
            raise TimeoutError("Saved-only audit reached its finite three-minute cap")
        sealed = store.completed(task["key"], request(task, done))
        if sealed is None:
            raise ValueError("A claimed completed unit is missing or unsealed")
        row = sealed["result"]
        done[task["key"]] = row
        if task["kind"] in {"import", "fit"}:
            model, adam, sid = load_state(root / row["state_path"])
            if (
                sid != row["state_id"]
                or model.model_id != row["model_id"]
                or adam.steps != row["optimizer_steps"]
            ):
                raise ValueError("A restored full model/Adam state differs")
            if task["kind"] == "import":
                expected, opt = extend(
                    context["models"][task["player"]],
                    context["adams"][task["player"]],
                    tuple(context["layout"]["columns"]),
                    task["arm"],
                )
                if model.as_dict() != expected.as_dict() or adam.as_dict() != opt.as_dict():
                    raise ValueError("An inherited original weight or Adam moment changed")
                imports += 1
            elif adam.steps - done[task["state"]]["optimizer_steps"] != row["new_optimizer_steps"]:
                raise ValueError("A fitting unit reset or skipped its preceding Adam counter")
        if task["kind"] in {"collect", "evaluate"}:
            outcomes = row["outcomes"] if task["kind"] == "collect" else [row]
            parent = done[task["state"]]
            for outcome in outcomes:
                ep = root / outcome["episode_path"]
                header = json.loads(ep.read_text())
                bound = header["binding"]
                if bound["model_id"] != parent["model_id"] or bound["config_id"] != store.config_id:
                    raise ValueError("A saved game belongs to another behavior or recipe")
                case = read_native_episode(ep, bound)
                scored = score_episode(case, bound["seed_id"], context["score"])
                for name in ("status", "victory", "maximum_floor", "completed_acts", "cpu_seconds"):
                    if case[name] != outcome[name]:
                        raise ValueError("A saved game outcome or compute amount changed")
                value = scored["training_return"] if scored["completed"] else 0.0
                if value != outcome["training_return"]:
                    raise ValueError("A full-game training score changed")
                native = identified(ep.parent / "native-audit.json")
                if not native["valid"] or not outcome["all_behavior_probabilities_reconstructed"]:
                    raise ValueError("Missing saved native/probability qualification")
                if (
                    task["kind"] == "collect"
                    and task["round"] == 1
                    and case["status"] == "terminal"
                ):
                    initial.setdefault((task["player"], bound["seed_id"]), {})[task["arm"]] = trace(
                        case
                    )
                games += 1
                decisions += len(case["decisions"])
                del case
    matched = [v for v in initial.values() if set(v) == set(ARMS)]
    if any(len(set(v.values())) != 1 for v in matched):
        raise ValueError(
            "Initially matched input arms produced different native action/public traces"
        )
    if (
        summarize(cfg, context["seeds"], done) != report["summary"]
        or games != report["planned_games"]
    ):
        raise ValueError("Saved paired tables or original attempt denominator do not rebuild")
    check_sources(root, report["sources"])
    body = {
        "schema_version": "native-structured-saved-audit-v1",
        "source_report_id": report["report_id"],
        "auditor_sha256": _sha_file(Path(__file__)),
        "verified_units": len(done),
        "verified_source_files": len(report["sources"]),
        "games_verified": games,
        "decisions_verified": decisions,
        "exact_full_state_imports": imports,
        "matched_initial_player_world_groups": len(matched),
        "initial_native_public_and_action_traces_identical": True,
        "paired_tables_and_scores_reconstructed": True,
        "native_and_probability_audits_reused_from_verified_seals": True,
        "native_delivery_or_policy_inference_replayed": False,
        "original_full_states_and_Adam_unchanged": True,
        "new_games": 0,
        "optimizer_steps": 0,
        "game_apps_created": 0,
        "wall_seconds": time.monotonic() - started,
        "sources": {**report["sources"], str(source.relative_to(root)): _sha_file(source)},
    }
    result = {**body, "report_id": manifest_identifier(body)}
    atomic_json(output, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    result = audit(root, root / args.recipe, root / args.output)
    print(json.dumps({k: v for k, v in result.items() if k != "sources"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
