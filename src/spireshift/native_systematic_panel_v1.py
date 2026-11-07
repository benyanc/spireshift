"""Owner-launched finite transition coverage; each case is independently sealed."""

from __future__ import annotations

import argparse
import json
import runpy
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games
from spireshift.engine_qualification import _sha_file
from spireshift.engine_working_app import preflight_working_app
from spireshift.full_run_experience import atomic_json
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_systematic_inputs_v1 import load
from spireshift.native_systematic_live_v1 import run_case


def checked_result(root: Path, ref: dict[str, Any]) -> dict[str, Any]:
    report = identified(verified(root, ref))
    check_sources(root, report["sources"])
    check_sources(root, report["evidence"])
    return report


def preflight(root: Path, recipe: Path) -> dict[str, Any]:
    ctx = load(root, recipe)
    cfg = ctx["config"]
    if cfg["stage"] != "owner_transition_panel" or len(cfg["cases"]) != 4:
        raise ValueError("Use the finite owner transition panel")
    audit = checked_result(root, cfg["short_audit"])
    if audit["status"] != "short_comparison_checks_pass" or audit["problems"]:
        raise ValueError("Complete the source/schema and saved-record checks first")
    for ref in cfg["short_controls"]:
        control = checked_result(root, ref)
        if (
            control["status"] != "transition_comparison_pass"
            or not control["clean_reset"]
            or control["environment_id"] != ctx["environment"]["manifest_id"]
            or control["verification_errors"]
            or control["effect_errors"]
        ):
            raise ValueError("Exact short transition controls are not qualified")
    if len(cfg["short_controls"]) != 2:
        raise ValueError("Require both rest and Happy Flower short controls")
    if _running_games():
        raise ValueError("Close STS2 before the transition panel")
    preflight_working_app(ctx["working_app"])
    return ctx


def run(root: Path, recipe: Path) -> dict[str, Any]:
    ctx = preflight(root, recipe)
    cfg = ctx["config"]
    output = root / cfg["workspace"]
    if (output / "report.json").exists():
        report = identified(output / "report.json")
        check_sources(root, report["sources"])
        check_sources(root, report["evidence"])
        return report
    if (output / "active.json").exists():
        raise ValueError("Preserve the interrupted panel; no automatic restart")
    output.mkdir(parents=True, exist_ok=True)
    atomic_json(output / "active.json", {"config_id": manifest_identifier(cfg)})
    started = time.monotonic()
    cases = []
    for case in cfg["cases"]:
        directory = output / case["key"]
        if directory.exists():
            raise ValueError("Preserve an existing attempt; do not replay its seed")
        result = run_case(root, ctx, case, directory)
        cases.append(
            {
                "key": case["key"],
                "status": result["status"],
                "report_id": result["report_id"],
                "wall_seconds": result["wall_seconds"],
            }
        )
        print(f"Transition {len(cases)}/4: {case['key']}: {result['status']}", flush=True)
        if not result["clean_reset"]:
            raise ValueError("Unverified worker/app reset; no next case")
    result = {
        "schema_version": "native-systematic-transition-panel-v1",
        "config_id": manifest_identifier(cfg),
        "environment_id": ctx["environment"]["manifest_id"],
        "status": "transition_panel_pass"
        if all(c["status"] == "transition_comparison_pass" for c in cases)
        else "transition_panel_blocked",
        "cases": cases,
        "sources": ctx["sources"],
        "evidence": {
            str(p.relative_to(root)): _sha_file(p)
            for p in output.rglob("*")
            if p.is_file() and p.name != "active.json"
        },
        "privileged_fixture": True,
        "training_allowed": False,
        "optimizer_updates": 0,
        "all_possible_interactions_proved": False,
        "automatic_follow_up": False,
        "full_game_playing_strength_evaluated": False,
        "wall_seconds": time.monotonic() - started,
    }
    result["report_id"] = manifest_identifier(result)
    atomic_json(output / "report.json", result)
    (output / "active.json").rename(output / "complete.json")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    root, recipe = Path.cwd(), args.recipe.resolve()
    if args.preflight:
        preflight(root, recipe)
        print(json.dumps({"valid": True, "new_games": 0, "optimizer_updates": 0}))
        return 0
    checker = runpy.run_path(str(root / "scripts/selection-flows-session-v12.py"))
    checker["check_repository"](root)
    result = run(root, recipe)
    print(
        json.dumps({k: v for k, v in result.items() if k not in {"sources", "evidence"}}, indent=2)
    )
    return 0 if result["status"] == "transition_panel_pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
