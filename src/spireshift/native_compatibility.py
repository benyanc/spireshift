"""Recurring checkpoint compatibility regression and a fail-closed training command gate.

The first stage rechecks recorded native/official pairs with today's exact policy.
Historical mechanics matches never become current-host or live-policy qualification.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.full_run_experience import atomic_json
from spireshift.native_compatibility_contract import (
    CONTRACT,
    ENVIRONMENT_SCOPE,
    LIVE_SCOPE,
    RECORDED_CLAIM,
    REPLAY_SCOPE,
    SCHEMA,
    compare_inputs,
    local,
    require_receipt,
)
from spireshift.native_compatibility_inputs import check_sources, load, project


def audit(root: Path, context: dict[str, Any]) -> dict[str, Any]:
    cfg, binding, sources = (context[k] for k in ("config", "binding", "sources"))
    directory = local(root, cfg["workspace"]) / manifest_identifier(binding)[7:]
    final = directory / "report.json"
    if final.exists():
        saved = identified(final)
        if saved["binding"] != binding or saved["sources"] != sources:
            raise ValueError("A cached gate belongs to different evidence or checkpoints")
        check_sources(root, saved["sources"])
        return saved
    directory.mkdir(parents=True, exist_ok=False)
    atomic_json(directory / "in-progress.json", {"binding": binding, "contract": CONTRACT})
    started = time.monotonic()
    results: dict[str, list[dict[str, Any]]] = {k: [] for k in context["models"]}
    banks = []
    for case in cfg["cases"]:
        if time.monotonic() - started > 180:
            raise TimeoutError("Compatibility audit cap; preserve its incomplete directory")
        projected = project(root, cfg, case)
        for state, model in context["models"].items():
            results[state].extend(
                compare_inputs(model, context["score"], pair) for pair in projected["pairs"]
            )
        banks.append(
            {
                "key": case["key"],
                "native_build_report_id": projected["native_build_report_id"],
                "matches_current_native_build": projected["native_build_report_id"]
                == context["native_build_report_id"],
                "mechanics_reconstruction": projected["verified"],
                "observations": len(projected["pairs"]),
            }
        )
    check_sources(root, sources)
    replay_passed = bool(results) and all(
        rows and all(r["passed"] for r in rows) for rows in results.values()
    )
    summaries = []
    for state in context["states"]:
        rows = results[state["state_id"]]
        summaries.append(
            {
                **state,
                "observations": len(rows),
                "passed_observations": sum(r["passed"] for r in rows),
                "matching_menus": sum(
                    not r["missing_official_actions"] and not r["extra_official_actions"]
                    for r in rows
                ),
                "matching_contexts": sum(r["context_equal"] for r in rows),
                "matching_features": sum(r["features_equal_on_common_actions"] for r in rows),
                "matching_distributions": sum(r["distributions_equal"] for r in rows),
                "families": dict(Counter(r["family"] for r in rows)),
                "cases": rows,
            }
        )
    body = {
        "schema_version": SCHEMA,
        "contract": CONTRACT,
        "config_id": manifest_identifier(cfg),
        "binding": binding,
        "sources": sources,
        "gates": {
            ENVIRONMENT_SCOPE: context["environment_checks"]["passed"],
            REPLAY_SCOPE: replay_passed,
            LIVE_SCOPE: False,
        },
        "environment_checks": context["environment_checks"],
        "status": "recorded_inputs_match_live_gate_pending"
        if replay_passed and context["environment_checks"]["passed"]
        else "blocked",
        "checkpoints": summaries,
        "reference_cases": banks,
        "historical_reference_bank": True,
        "current_host_mechanics_qualified_by_this_audit": False,
        "official_checkpoint_action_delivery_exercised": False,
        "full_game_performance_evaluated": False,
        "new_games_launched": 0,
        "optimizer_steps": 0,
        "original_weights_and_all_Adam_unchanged": True,
        "checkpoint_promoted": False,
        "adaptive_controller_allowed": False,
        "training_allowed": False,
        "claim_scope": RECORDED_CLAIM,
        "required_next_step": "align_complete_official_inputs_then_current_host_policy_canary",
        "wall_seconds": time.monotonic() - started,
    }
    result = {**body, "report_id": manifest_identifier(body)}
    atomic_json(final, result)
    (directory / "in-progress.json").rename(directory / "complete.json")
    return result


def require(context: dict[str, Any], root: Path, report: dict[str, Any]) -> None:
    # A recipe/CLI cannot weaken these requirements to a historical or mechanics-only pass.
    require_receipt(root, report, context["binding"])


def run_guarded(
    root: Path, context: dict[str, Any], report: dict[str, Any], command: list[str]
) -> int:
    if not command or command[0] == "--":
        raise ValueError("Pass one explicit command after the gate; no shell interpretation")
    require(context, root, report)
    check_sources(root, context["sources"])
    return subprocess.run(command, cwd=root, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("audit", "require", "run"))
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--checkpoint", action="append", default=[])
    parser.add_argument("--command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    root = Path.cwd()
    try:
        context = load(root, args.recipe.resolve(), tuple(args.checkpoint))
        report = audit(root, context)
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "report_id": report["report_id"],
                    "gates": report["gates"],
                    "checkpoints": [
                        {k: v for k, v in s.items() if k != "cases"} for s in report["checkpoints"]
                    ],
                    "new_games_launched": 0,
                    "optimizer_steps": 0,
                    "training_allowed": False,
                },
                indent=2,
            ),
            flush=True,
        )
        if args.mode == "run":
            return run_guarded(root, context, report, args.command or [])
        if args.mode == "require":
            require(context, root, report)
        return 0
    except (ValueError, OSError, KeyError, TimeoutError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"status": "blocked_preserving_evidence", "error": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
