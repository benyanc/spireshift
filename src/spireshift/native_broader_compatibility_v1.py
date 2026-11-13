"""Coordinate a finite broader canary using the unchanged, qualified v12 execution path."""

from __future__ import annotations

import argparse
import json
import runpy
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games
from spireshift.engine_qualification import _sha_file
from spireshift.engine_working_app import preflight_working_app
from spireshift.full_run_experience import atomic_json
from spireshift.native_compatibility_contract import local, verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_inputs_v12 import load
from spireshift.native_flow_verification_v12 import records
from spireshift.native_launch_limits import load_launch

VERIFIER = "src/spireshift/native_flow_verification_v12.py"
RESET_CHECKS = {
    "profile_path_logged",
    "Steam_disabled_observed",
    "personal_profile_unchanged",
    "working_app_unchanged",
    "frozen_archive_unchanged",
    "settings_template_unchanged",
    "natural_shutdown",
    "exact_delivery_count",
}


def reference(root: Path, path: Path) -> dict[str, str]:
    return {"path": str(path.relative_to(root)), "sha256": _sha_file(path)}


def check_resource(resource: dict[str, Any], *, diagnostic_exit: bool = False) -> None:
    valid = resource.get("status") == "completed" and resource.get("exit_code") == 0
    if diagnostic_exit:
        valid = valid or (resource.get("status") == "failed" and resource.get("exit_code") == 2)
    if not valid or resource.get("cap") is not None:
        raise ValueError("A failed or capped operation cannot qualify the broader canary")


def validate_report(context: dict[str, Any], report: dict[str, Any]) -> bool:
    cfg = context["config"]
    if (
        report.get("schema_version") != "native-live-checkpoint-adapter-result-v1"
        or report.get("config_id") != manifest_identifier(cfg)
        or report.get("environment_id") != context["environment"]["manifest_id"]
        or report.get("implementation_id") != manifest_identifier(cfg["implementation_sha256"])
        or report.get("helpers_id") != manifest_identifier(cfg["helpers_sha256"])
        or [{k: c[k] for k in ("key", "player", "seed")} for c in report.get("cases", [])]
        != cfg["cases"]
        or report.get("optimizer_updates") != 0
        or report.get("training_allowed") is not False
        or report.get("original_weights_and_all_Adam_unchanged") is not True
        or report.get("game_starts") != 2 * len(cfg["cases"])
    ):
        raise ValueError("Live result does not bind the exact broader recipe and full players")
    for case in report["cases"]:
        official = case["official"]
        checks = official.get("checks", {})
        if (
            case["native"]["shutdown"]["clean_exit"] is not True
            or not checks.keys() >= RESET_CHECKS
            or any(value is not True for value in checks.values())
        ):
            raise ValueError("Unverified worker reset; preserve the attempt without retry")
    return (
        all(
            c["native"]["status"] == "native_prefix_pass"
            and c["official"]["status"] == "official_prefix_pass"
            for c in report["cases"]
        )
        and report.get("checkpoint_delivery_exercised") is True
    )


def validate_verification(
    root: Path, context: dict[str, Any], report: dict[str, Any], witness: dict[str, Any]
) -> None:
    expected = [
        {
            "key": case["key"],
            "host": host,
            "verified_decisions": case[host]["policy_decisions"]
            if host == "native"
            else case[host]["probe"]["policy_decisions"],
        }
        for case in report["cases"]
        for host in ("native", "official")
    ]
    if (
        witness.get("schema_version") != "native-live-checkpoint-verification-v1"
        or witness.get("valid") is not True
        or witness.get("source_report_id") != report["report_id"]
        or witness.get("verifier_sha256") != _sha_file(root / VERIFIER)
        or witness.get("verifier_sha256") != context["config"]["implementation_sha256"][VERIFIER]
        or witness.get("cases") != expected
        or witness.get("games_launched") != 0
        or witness.get("optimizer_updates") != 0
        or witness.get("original_weights_and_all_Adam_unchanged") is not True
    ):
        raise ValueError("Saved reconstruction must bind every host, full count and exact verifier")


def frames(path: Path, maximum: int) -> list[dict[str, Any]]:
    result = []
    for row in records(path):
        if row.get("kind") == "policy_input":
            result.append(row["frame"])
            if len(result) > maximum + 1:
                raise ValueError("Public frame count exceeds the declared prefix and ending")
    return result


def coverage(root: Path, context: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    cfg = context["config"]
    paired_families: Counter[str] = Counter()
    paired_transitions: Counter[str] = Counter()
    results = []
    all_complete = True
    for case in report["cases"]:
        host_frames = {
            host: frames(
                root / cfg["workspace"] / case["key"] / host / filename,
                cfg["maximum_decisions"],
            )
            for host, filename in (
                ("native", "shared-public.jsonl.gz"),
                ("official", "live-public.jsonl.gz"),
            )
        }
        left, right = host_frames["native"], host_frames["official"]
        equal = case["comparison"]["equal_input_prefix"]
        terminal_equal = all(
            a["terminal"] == b["terminal"] and a.get("ending") == b.get("ending")
            for a, b in zip(left[:equal], right[:equal], strict=True)
        )
        counts = {
            "native": case["native"]["policy_decisions"],
            "official": case["official"]["probe"].get("policy_decisions", 0),
        }
        complete = True
        terminal = {}
        for host, observations in host_frames.items():
            ending_frames = [i for i, f in enumerate(observations) if f["terminal"]]
            if ending_frames and ending_frames != [len(observations) - 1]:
                raise ValueError("An ending must be the last public frame; no later policy actions")
            ended = bool(ending_frames)
            terminal[host] = observations[-1].get("ending") if ended else None
            complete = complete and 0 < counts[host] <= cfg["maximum_decisions"]
            complete = complete and len(observations) == counts[host] + int(ended)
            complete = complete and (ended or counts[host] == cfg["maximum_decisions"])
        matched = (
            complete
            and counts["native"] == counts["official"]
            and len(left) == len(right) == equal
            and terminal_equal
            and case["comparison"]["complete_prefix_input_equivalence"] is True
        )
        all_complete = all_complete and matched
        # Only the contiguous equal prefix supplies paired observations/effects.
        families = [str(f["source_family"]) for f in left[:equal]]
        paired_families.update(families)
        paired_transitions.update(
            f"{a} -> {b}" for a, b in zip(families, families[1:], strict=False)
        )
        results.append(
            {
                "key": case["key"],
                "verified_policy_decisions": counts,
                "matching_input_frames": equal,
                "declared_prefix_or_matching_ending": matched,
                "matching_successor_inputs_between_decisions": max(0, equal - 1),
                "terminal_outcomes": terminal,
                "terminal_controls_observed": terminal_equal
                and terminal["native"] is not None
                and terminal["official"] is not None,
                "official_delivery_counters": {
                    name: case["official"]["probe"].get(name, 0)
                    for name in (
                        "atomic_selections",
                        "committed_packs",
                        "reward_guidance_macros",
                        "reward_confirmation_steps",
                        "selection_ui_steps",
                    )
                },
            }
        )
    return {
        "all_declared_prefixes_or_endings_match": all_complete,
        "cases": results,
        "paired_observed_families": dict(sorted(paired_families.items())),
        "paired_observed_transitions": dict(sorted(paired_transitions.items())),
        "genuine_ending_pairs_observed": sum(c["terminal_controls_observed"] for c in results),
        "unobserved_families_and_endings_are_not_qualified": True,
        "final_uncaptured_successor_equivalence_granted": False,
        "later_divergent_states_realignable": False,
    }


def load_plan(root: Path, path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = json.loads(path.read_text())
    if (
        plan.get("schema_version") != "native-broader-compatibility-plan-v1"
        or plan.get("training_allowed") is not False
        or plan.get("automatic_follow_up") is not False
        or plan.get("maximum_new_game_starts") != 8
    ):
        raise ValueError("Use the separately frozen finite broader compatibility plan")
    workspace = local(root, plan["workspace"])
    if not workspace.is_relative_to(root / "artifacts/native-selection-flows"):
        raise ValueError("Keep coordination inside the isolated compatibility artifacts")
    check_sources(root, plan["sources"])
    recipe = verified(root, plan["recipe"])
    context = load(root, recipe)
    cfg = context["config"]
    worlds = plan["fresh_worlds"]
    if (
        cfg["stage"] != "bounded_live_checkpoint_canary"
        or cfg["maximum_decisions"] != 128
        or cfg["maximum_case_wall_seconds"] != 600
        or len(worlds) != 2
        or len(set(worlds)) != 2
        or {(c["player"], c["seed"]) for c in cfg["cases"]}
        != {(p, s) for p in (2, 3) for s in worlds}
        or context["environment"]["manifest_id"] != plan["environment_id"]
        or cfg["workspace"] == plan["workspace"]
    ):
        raise ValueError("Keep both original players, two fresh worlds and unchanged execution")
    load_launch(root, verified(root, plan["launch"]), recipe, cfg)
    panel = identified(verified(root, plan["qualified_targeted_panel"]))
    check_sources(root, panel["sources"])
    check_sources(root, panel["evidence"])
    if (
        panel.get("status") != "targeted_panel_pass"
        or panel.get("completed_controls") != 4
        or panel.get("remaining_controls") != 0
        or panel.get("error") is not None
        or not all(
            c["full_inputs_match"] and c["clean_worker_reset"] and c["target_prefix_reached"]
            for c in panel["controls"]
        )
    ):
        raise ValueError("The completed v15 panel must remain qualified and unchanged")
    inventory = json.loads(verified(root, plan["seed_inventory"]).read_text())
    check_sources(root, inventory["sources"])
    if (
        inventory.get("fresh_worlds") != worlds
        or inventory.get("selection_uses_outcomes") is not False
        or set(worlds) & set(inventory["canonical_prior_seeds"])
    ):
        raise ValueError("Do not replay prior, reserved or uncertain worlds")
    protection = json.loads(verified(root, plan["protection"]).read_text())
    check_sources(root, protection["files"])
    return plan, context


def save(root: Path, workspace: Path, body: dict[str, Any]) -> dict[str, Any]:
    result = {**body, "report_id": manifest_identifier(body)}
    atomic_json(workspace / "report.json", result)
    (workspace / "active.json").rename(workspace / "complete.json")
    return result


def run(root: Path, path: Path, plan: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    workspace = local(root, plan["workspace"])
    cfg = context["config"]
    live_workspace = root / cfg["workspace"]
    final = workspace / "report.json"
    if final.exists():
        saved = identified(final)
        if saved["plan_id"] != manifest_identifier(plan) or (workspace / "active.json").exists():
            raise ValueError("Preserve changed or interrupted coordination evidence")
        check_sources(root, saved["sources"])
        check_sources(root, saved["evidence"])
        return saved
    if (workspace / "active.json").exists() or (live_workspace / "active.json").exists():
        raise ValueError("Preserve the uncertain attempt; no automatic replay")
    if not (live_workspace / "report.json").exists() and _running_games():
        raise ValueError("Close STS2 before launching; no coordination marker created")
    workspace.mkdir(parents=True, exist_ok=True)
    atomic_json(workspace / "active.json", {"plan_id": manifest_identifier(plan)})
    source_copy = workspace / "source-at-launch"
    names = {
        "src/spireshift/native_broader_compatibility_v1.py",
        "tests/unit/test_native_broader_compatibility.py",
        "scripts/compare-broader-compatibility-v1.sh",
    } & plan["sources"].keys()
    names = names | {str(path.relative_to(root))}
    if not source_copy.exists():
        source_copy.mkdir()
        for name in sorted(names):
            destination = source_copy / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((root / name).read_bytes())
    if {str(p.relative_to(source_copy)) for p in source_copy.rglob("*") if p.is_file()} != names:
        raise ValueError("Preserve a changed coordination source snapshot")
    for name in names:
        if _sha_file(source_copy / name) != _sha_file(root / name):
            raise ValueError("Preserve changed source-at-launch evidence without retry")
    started = time.monotonic()
    live = live_workspace / "report.json"
    evidence: dict[str, str] = {}
    if not live.exists():
        pattern = f"{Path(plan['recipe']['path']).stem}-attempt-*.json"
        before = set((root / "artifacts/resources").glob(pattern))
        code = subprocess.call(
            [
                "bash",
                str(root / "scripts/check-selection-flows-v12.sh"),
                plan["recipe"]["path"],
                plan["launch"]["path"],
            ],
            cwd=root,
        )
        fresh = set((root / "artifacts/resources").glob(pattern)) - before
        if len(fresh) != 1:
            raise ValueError("Require the exact child launch resource receipt")
        resource = fresh.pop()
        check_resource(identified(resource), diagnostic_exit=live.exists())
        evidence[str(resource.relative_to(root))] = _sha_file(resource)
        if not live.exists():
            if code == 0 and not (live_workspace / "active.json").exists():
                pause_index = len(list(workspace.glob("clean-pause-*"))) + 1
                pause = workspace / f"clean-pause-{pause_index}.json"
                (workspace / "active.json").rename(pause)
                return {
                    "status": "clean_pause",
                    "repeat_same_command_to_resume": True,
                    "optimizer_updates": 0,
                }
            raise ValueError("No complete live report; preserve unfinished cases without retry")
    report = identified(live)
    check_sources(root, report["sources"])
    check_sources(root, report["evidence"])
    delivered = validate_report(context, report)
    witness_path = workspace / "verification-v1/report.json"
    resource = workspace / "verification-resources-v1.json"
    if delivered:
        if not witness_path.exists():
            if resource.exists():
                raise ValueError("Preserve incomplete verification rather than overwriting it")
            code = subprocess.call(
                [
                    "uv",
                    "run",
                    "--no-sync",
                    "spireshift",
                    "resources",
                    "run",
                    "--kind",
                    "other",
                    "--report",
                    str(resource),
                    "--artifact-root",
                    str(witness_path.parent),
                    "--workers",
                    "1",
                    "--max-wall-seconds",
                    "240",
                    "--max-cpu-seconds",
                    "720",
                    "--max-memory-bytes",
                    "4000000000",
                    "--max-storage-bytes",
                    "1000000000",
                    "--",
                    "uv",
                    "run",
                    "--no-sync",
                    "python",
                    "-m",
                    "spireshift.native_flow_verification_v12",
                    plan["recipe"]["path"],
                    str(witness_path.parent),
                ],
                cwd=root,
            )
            if code:
                raise ValueError("Saved reconstruction failed; preserve the completed games")
        check_resource(identified(resource))
        witness = identified(witness_path)
        validate_verification(root, context, report, witness)
        for item in (witness_path, resource):
            evidence[str(item.relative_to(root))] = _sha_file(item)
    observed = coverage(root, context, report)
    passed = delivered and observed["all_declared_prefixes_or_endings_match"]
    evidence.update(report["sources"])
    evidence.update(report["evidence"])
    evidence.update(
        {str(p.relative_to(root)): _sha_file(p) for p in source_copy.rglob("*") if p.is_file()}
    )
    evidence[str(live.relative_to(root))] = _sha_file(live)
    check_sources(root, plan["sources"])
    return save(
        root,
        workspace,
        {
            "schema_version": "native-broader-compatibility-result-v1",
            "plan_id": manifest_identifier(plan),
            "source_report_id": report["report_id"],
            "environment_id": context["environment"]["manifest_id"],
            "status": "broader_prefix_compatibility_pass" if passed else "broader_prefix_blocked",
            "coverage": observed,
            "raw_choices_and_receipts_independently_reconstructed": delivered,
            "sources": {**plan["sources"], str(path.relative_to(root)): _sha_file(path)},
            "evidence": evidence,
            "all_original_weights_and_Adam_unchanged": True,
            "optimizer_updates": 0,
            "training_allowed": False,
            "checkpoint_promoted": False,
            "broader_live_qualification_granted": False,
            "adaptive_controller_allowed": False,
            "automatic_follow_up": False,
            "full_game_playing_strength_evaluated": False,
            "claim_scope": "declared_current_checkpoint_prefixes_and_observed_endings_only",
            "wall_seconds_this_coordination_session": time.monotonic() - started,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--check-repository", action="store_true")
    mode.add_argument("--run", action="store_true")
    args = parser.parse_args()
    root = Path.cwd()
    try:
        path = args.plan.resolve()
        plan, context = load_plan(root, path)
        if args.preflight:
            preflight_working_app(context["working_app"])
            print(
                json.dumps(
                    {"valid": True, "planned_pairs": 4, "games_launched": 0, "optimizer_updates": 0}
                )
            )
            return 0
        checker = runpy.run_path(str(root / "scripts/selection-flows-session-v12.py"))
        checker["check_repository"](root)
        if args.check_repository:
            return 0
        report = run(root, path, plan, context)
        print(
            json.dumps(
                {k: v for k, v in report.items() if k not in {"sources", "evidence"}}, indent=2
            )
        )
        return 0 if report["status"] in {"broader_prefix_compatibility_pass", "clean_pause"} else 2
    except (ValueError, OSError, KeyError, TimeoutError) as error:
        print(json.dumps({"status": "blocked_preserving_evidence", "error": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
