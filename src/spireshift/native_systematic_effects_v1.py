"""Compose scoped compatibility evidence and check actual Smith/counter effects."""

from __future__ import annotations

import argparse
import gzip
import json
import runpy
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_systematic_live_v1 import select_action
from spireshift.native_systematic_panel_v1 import checked_result, preflight, run


def frames(directory: Path, host: str) -> list[dict[str, Any]]:
    file = (
        directory
        / host
        / ("shared-public.jsonl.gz" if host == "native" else "live-public.jsonl.gz")
    )
    with gzip.open(file, "rt") as stream:
        return [
            row["frame"]
            for line in stream
            if (row := json.loads(line)).get("kind") in {"policy_input", "diagnostic_successor"}
        ]


def upgrade_effect(case: dict[str, Any], observations: list[dict[str, Any]]) -> dict[str, Any]:
    if "SMITH" not in case["instructions"]:
        return {"smith_exercised": False}

    def deck(frame: dict[str, Any]) -> Counter[tuple[str, bool]]:
        reads = frame["public_input"]["context"]["reads"]
        decks = [read["content"]["cards"] for read in reads if read["kind"] == "run_deck"]
        if len(decks) != 1 or any(type(card.get("is_upgraded")) is not bool for card in decks[0]):
            raise ValueError("Missing exact current deck upgrade facts")
        return Counter((card["definition_id"], card["is_upgraded"]) for card in decks[0])

    before, after = deck(observations[0]), deck(observations[-1])
    added, removed = list((after - before).elements()), list((before - after).elements())
    if (
        len(added) != 1
        or len(removed) != 1
        or not added[0][1]
        or removed[0][1]
        or added[0][0] != removed[0][0]
    ):
        raise ValueError("Smith must upgrade exactly one existing physical card")
    index = case["instructions"].index("confirm_card")
    chosen_frame = observations[index]
    candidate = chosen_frame["public_input"]["candidates"][
        select_action(chosen_frame, "confirm_card")
    ]
    chosen = candidate["arguments"][0]["entity"]["properties"]["definition_id"]
    if chosen != added[0][0]:
        raise ValueError("Smith upgraded a different card from the delivered selection")
    return {
        "smith_exercised": True,
        "upgraded_definition": chosen,
        "physical_card_count_unchanged": True,
    }


def counter_boundary(directory: Path) -> dict[str, Any]:
    seen = 0
    with gzip.open(directory / "official/live-public.jsonl.gz", "rt") as stream:
        for line in stream:
            row = json.loads(line)
            if row.get("kind") != "observed":
                continue
            snapshot = row["snapshot"]
            persistent = (snapshot.get("persistent") or {}).get("content") or {}
            relics = (persistent.get("player") or {}).get("relics", [])
            if any(
                relic.get("definition_id") == "HAPPY_FLOWER" and relic.get("counter") == 3
                for relic in relics
            ):
                seen += 1
                if snapshot["status"] != "settling" or snapshot["bound_actions"]["actions"]:
                    raise ValueError("Activation counter published actionable authority")
    return {"activation_frames_observed": seen, "activation_frames_have_no_authority": True}


def qualify_short(root: Path, recipe: Path) -> dict[str, Any]:
    ctx = preflight(root, recipe)
    output = root / "artifacts/native-systematic-comparison/short-qualification-v1"
    final = output / "report.json"
    if final.exists():
        report = identified(final)
        if report["config_id"] != manifest_identifier(ctx["config"]):
            raise ValueError("Preserve another short qualification")
        check_sources(root, report["sources"])
        check_sources(root, report["evidence"])
        return report
    output.mkdir(parents=True, exist_ok=False)
    audit = checked_result(root, ctx["config"]["short_audit"])
    controls = [checked_result(root, ref) for ref in ctx["config"]["short_controls"]]
    by_family = {control["case"]["family"]: control for control in controls}
    if set(by_family) != {"rest_site", "combat_turn"}:
        raise ValueError("Require one short control for each repaired family")
    flower = by_family["combat_turn"]
    flower_directory = root / flower["case"]["fixture_save"]["path"]
    boundary = counter_boundary(flower_directory.parent)
    if boundary["activation_frames_observed"] == 0:
        raise ValueError("Short control did not observe the transient activation boundary")
    audit_directory = (root / ctx["config"]["short_audit"]["path"]).parent
    ledger = json.loads((audit_directory / "coverage-ledger.json").read_text())
    for row in ledger:
        control = by_family.get(row["surface"])
        if control:
            row["live_effects_qualified"] = True
            row["live_qualification_scope"] = control["case"]["instructions"]
            row["live_source_report_id"] = control["report_id"]
            row["remaining"] = ["other transitions and content combinations"]
    atomic_json(output / "coverage-ledger.json", ledger)
    report = {
        "schema_version": "native-systematic-short-qualification-v1",
        "status": "systematic_short_checks_pass",
        "config_id": manifest_identifier(ctx["config"]),
        "environment_id": ctx["environment"]["manifest_id"],
        "sources": ctx["sources"],
        "evidence": {
            str((output / "coverage-ledger.json").relative_to(root)): _sha_file(
                output / "coverage-ledger.json"
            )
        },
        "audit_report_id": audit["report_id"],
        "short_control_ids": [c["report_id"] for c in controls],
        "counter_boundary": boundary,
        "saved_frames": audit["saved_frames"],
        "generated_checks": audit["generated_checks"],
        "frozen_actor_probes": audit["frozen_actor_probes"],
        "verified_deliveries": sum(
            sum(c["independently_reconstructed_deliveries"].values()) for c in controls
        ),
        "all_possible_interactions_proved": False,
        "training_allowed": False,
        "optimizer_updates": 0,
        "checkpoint_promoted": False,
        "automatic_follow_up": False,
    }
    report["report_id"] = manifest_identifier(report)
    atomic_json(final, report)
    return report


def owner(root: Path, recipe: Path) -> dict[str, Any]:
    short = qualify_short(root, recipe)
    checker = runpy.run_path(str(root / "scripts/selection-flows-session-v12.py"))
    checker["check_repository"](root)
    panel = run(root, recipe)
    cfg = json.loads(recipe.read_text())
    output = root / cfg["workspace"]
    checks, errors = [], []
    for case in cfg["cases"]:
        directory = output / case["key"]
        report = checked_result(
            root,
            {
                "path": str((directory / "report.json").relative_to(root)),
                "sha256": _sha_file(directory / "report.json"),
            },
        )
        try:
            upgrades = [
                upgrade_effect(case, frames(directory, host)) for host in ("native", "official")
            ]
            if upgrades[0] != upgrades[1]:
                raise ValueError("Paired Smith effects differ")
            boundary = counter_boundary(directory)
            if case["family"] == "combat_turn" and boundary["activation_frames_observed"] == 0:
                raise ValueError("No observed native counter transition")
            checks.append(
                {
                    "key": case["key"],
                    "report_id": report["report_id"],
                    "upgrade_effect": upgrades[0],
                    "counter_boundary": boundary,
                }
            )
        except (ValueError, KeyError) as error:
            errors.append({"key": case["key"], "error": str(error)})
    result = {
        "schema_version": "native-systematic-compatibility-result-v1",
        "status": "systematic_transition_checks_pass"
        if not errors and panel["status"] == "transition_panel_pass"
        else "systematic_transition_checks_blocked",
        "source_panel_id": panel["report_id"],
        "short_qualification_id": short["report_id"],
        "checks": checks,
        "errors": errors,
        "sources": panel["sources"],
        "evidence": panel["evidence"],
        "optimizer_updates": 0,
        "training_allowed": False,
        "full_game_playing_strength_evaluated": False,
        "broader_live_qualification_granted": False,
        "automatic_follow_up": False,
    }
    result["report_id"] = manifest_identifier(result)
    final = output / "semantic-effects-report.json"
    if final.exists():
        if identified(final) != result:
            raise ValueError("Preserve a different saved semantic effect result")
    else:
        atomic_json(final, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--short", action="store_true")
    args = parser.parse_args()
    result = (
        qualify_short(Path.cwd(), args.recipe.resolve())
        if args.short
        else owner(Path.cwd(), args.recipe.resolve())
    )
    print(
        json.dumps({k: v for k, v in result.items() if k not in {"sources", "evidence"}}, indent=2)
    )
    return 0 if result["status"].endswith("pass") else 2


if __name__ == "__main__":
    raise SystemExit(main())
