"""Explain a completed teaching test from saved evidence, with no new games or fits."""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_reuse import check_sources
from spireshift.native_teaching_data import ARMS, TEACHER, public_step
from spireshift.native_teaching_diagnostic_history import historical_probes
from spireshift.native_teaching_diagnostic_inputs import local, prepare
from spireshift.native_teaching_diagnostic_metrics import (
    changed_reach,
    departure,
    distribution,
    greedy,
    interference,
    lesson_details,
    remaining,
)
from spireshift.native_teaching_plan import summary


def saved_fight(root: Path, context: dict[str, Any], name: str, fight_id: str) -> dict[str, Any]:
    if context["sources"].get(name) != _sha_file(local(root, name)):
        raise ValueError("A fight must belong to the sealed completed source")
    value = identified(root / name, "fight_id")
    if value["fight_id"] != fight_id or value["student_inputs_public_only"] is not True:
        raise ValueError("Fight identity or public-input boundary changed")
    for s in value["steps"]:
        public_step(s)
    return value


def fight_details(root: Path, context: dict[str, Any], deadline: float) -> list[dict[str, Any]]:
    bank, report = context["bank"], context["report"]
    teacher = identified(local(root, TEACHER))
    if teacher["report_id"] != bank["teacher_report_id"]:
        raise ValueError("Original fight plans must come from the completed historical teacher")
    by_id = {r["fight_id"]: r for r in teacher["fights"].values() if r["kind"] == "fight"}
    lessons = {r["root_id"]: r for r in bank["lessons"]}
    references = {}
    teachers = {}
    for row in report["natural_fights"]:
        root_id = row["root_id"]
        if root_id in references:
            continue
        index, entry = next((i, r) for i, r in enumerate(bank["roots"]) if r["root_id"] == root_id)
        ref = teacher["fights"][f"root-{index:02d}-early-reference"]
        references[root_id] = saved_fight(root, context, ref["fight_path"], ref["fight_id"])
        if root_id in lessons:
            lesson = lessons[root_id]
            for arm, key in (
                ("reference_clone", "reference_fight_id"),
                ("teacher_clone", "teacher_fight_id"),
            ):
                data = by_id[lesson[key]]
                value = saved_fight(root, context, data["fight_path"], data["fight_id"])
                if (
                    value["root_id"] != root_id
                    or value["partition"] != "fit"
                    or value["status"] != "complete"
                    or not value["native_audit"]["valid"]
                    or [
                        public_step(s)
                        for s in value["steps"]
                        if len(s["public_input"]["candidates"]) > 1
                    ]
                    != lesson["plans"][arm]["steps"]
                ):
                    raise ValueError("Diagnostic plan differs from its confirmed public lesson")
                if arm == "teacher_clone":
                    teachers[root_id] = value
        if references[root_id]["root_id"] != entry["root_id"]:
            raise ValueError("The reference fight belongs to another root")
    results = []
    for key, row in context["done"].items():
        if row["kind"] != "fight":
            continue
        remaining(deadline)
        value = saved_fight(
            root,
            context,
            context["source"]["workspace"] + f"/chunks/{key}/fight.json",
            row["fight_id"],
        )
        if any(
            value[k] != row[k] for k in ("status", "outcome", "resources", "root_id", "model_id")
        ):
            raise ValueError("The saved fight result changed")
        result = {
            "key": key,
            "world": row["world"],
            "partition": row["partition"],
            "player": row["player"],
            "arm": row["arm"],
            "status": row["status"],
            "outcome": row["outcome"],
            "terminal_hp": row["resources"]["hp"] if row["resources"] else None,
            "fight_win_is_full_game_win": False,
        }
        if row["status"] == "complete":
            if not value["native_audit"]["valid"]:
                raise ValueError("A completed fight needs its original native delivery audit")
            model = context["models"][row["player"]][row["arm"]]
            if value["model_id"] != model.model_id:
                raise ValueError("The fight was played by another final")
            for step in value["steps"]:
                remaining(deadline)
                logs = distribution(model, step["public_input"], context["score"])
                if (
                    len(logs) != len(step["log_probabilities"])
                    or any(
                        not math.isclose(a, b, abs_tol=1e-10, rel_tol=0)
                        for a, b in zip(logs, step["log_probabilities"], strict=True)
                    )
                    or greedy(logs) != step["action_index"]
                ):
                    raise ValueError(
                        "Completed fight choices must reproduce the frozen greedy player"
                    )
            result["versus_original_source_reference"] = departure(
                references[row["root_id"]]["steps"], value["steps"]
            )
            result["reference_is_source_player_not_optimal_action_oracle"] = True
            result["public_choice_distributions_reconstructed"] = len(value["steps"])
            if row["root_id"] in teachers:
                result["versus_taught_plan"] = departure(
                    teachers[row["root_id"]]["steps"], value["steps"]
                )
                result["changed_target_reach"] = changed_reach(
                    lessons[row["root_id"]]["changed_choices"]["steps"], value["steps"]
                )
        results.append(result)
    return results


def render(report: dict[str, Any]) -> str:
    control = report["source_stage"] == "short_control"
    lines = [
        "# Completed teaching diagnosis",
        "",
        "Source: completed short integration control; this qualifies the report, not stronger play."
        if control
        else "Source: completed teaching and fresh-game comparison; all finals frozen first.",
        "No new games, fitting, optimizer updates, checkpoint selection or promotion.",
        "",
        "## Did the copies learn the saved actions?",
        "",
        "Full-plan cross-entropy (lower is better at imitation; it is not a gameplay score):",
        "",
        "| Player | Copy | Before | Final | Saved updates |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in report["fitting_curves"]:
        before = row["epochs"][0]["initial"]["root_equal_cross_entropy"]
        after = row["epochs"][-1]["final"]["root_equal_cross_entropy"]
        lines.append(
            f"| {row['player']} | {row['arm']} | {before:.4f} | {after:.4f} "
            f"| {row['saved_updates']} |"
        )
    lines += ["", "Changed-choice targets are separated from full-plan averages:", ""]
    for p, details in report["lesson_diagnostics"].items():
        for world in details["worlds"]:
            for target in world["changed_targets"]:
                versions = target["versions"]
                lines.append(
                    f"- Player {p}, {world['world']}, {target['target_label']}: "
                    + "; ".join(
                        f"{a} {v['probability']:.1%} / "
                        f"greedy {'matches' if v['greedy_matches'] else 'differs'}"
                        for a, v in versions.items()
                    )
                    + "."
                )
    lines += ["", "## Can the player execute the plan?", ""]
    for row in report["fight_diagnostics"]:
        v = row.get("versus_taught_plan")
        detail = "No taught plan for this held-out root."
        if v:
            first = v["first_departure"]
            detail = (
                "Exact complete taught trace."
                if first is None
                else f"First departure at action {first['position'] + 1}: "
                + (
                    f"{first['actual_label']} versus taught {first['expected_label']}."
                    if first["kind"] == "different_action_on_identical_public_state"
                    else f"{first['kind']}."
                )
            )
        lines.append(
            f"- Player {row['player']} / {row['arm']} / {row['world']} ({row['partition']}): "
            f"{row['status']}, fight {row['outcome']}, HP {row['terminal_hp']}. {detail}"
        )
    lines += [
        "",
        "A departure is not a proven mistake. Later states are not aligned by position "
        "after a different action.",
        "Local fight wins and HP do not establish full-game utility.",
        "",
        "## Did other choices change?",
        "",
        f"Probe: {report['historical_probe']['probe_states']} public menus from "
        f"{len(report['historical_probe']['games'])} historical TRAIN worlds. "
        "Family-balanced selection; these are not fresh evaluation games or optimal-action labels.",
        "",
        "| Player | Copy | Family | States | Worlds | Probability movement (TV) | Greedy changes |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for p, detail in report["unrelated_choice_movement"].items():
        for arm, data in detail["arms"].items():
            for row in data["by_family"]:
                lines.append(
                    f"| {p} | {arm} | {row['family']} | {row['states']} | {row['worlds']} "
                    f"| {row['total_variation']:.4f} | {row['greedy_action_changed']:.1%} |"
                )
    lines += [
        "",
        "TV measures softmax probability movement at temperature 0.8. Combat execution is greedy; "
        "its changed top choices are separate. Means give each world equal weight within a family.",
        "Changed probabilities alone do not establish quality. Rest/card-skip/potion/shop "
        "opportunity changes and the largest movements are in report.json.",
        "",
        "## Does it transfer to full games?",
        "",
        "| Player | Version | Saved games | Wins | Failures | Mean floor (auxiliary) |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for player in report["fresh_game_evidence"]["players"]:
        for arm, data in player["arms"].items():
            lines.append(
                f"| {player['player']} | {arm} | {data['recorded']}/{data['denominator']} "
                f"| {data['wins']} | {data['failed_games']} | {data['mean_floor']:.2f} |"
            )
    lines += [
        "",
        "The control's one evaluation world cannot establish strength or generalization."
        if control
        else "Use saved paired comparisons against reference copies and untouched originals. "
        "Thirty-two evaluation worlds are not 192 independent worlds; all-zero wins do not prove "
        "equal win probabilities.",
        "Terminal full-run victory under 128 CPU seconds is primary. No loss threshold, best epoch "
        "or new training decision is selected by this report.",
        "",
        "## Interpretation",
        "",
        "- Weak target learning: investigate learning these examples before requesting more.",
        "- Learned probabilities but failed execution: inspect departures and reached states.",
        "- Taught fights improve without game gains: inspect coverage and other choice changes.",
        "- Apparent game gains: retain controls, world uncertainty and two-world training limits.",
        "",
        "These are possibilities, not established causes or permission to change the experiment.",
        "Both parents, every saved Adam state and all frozen experiment inputs verified unchanged.",
    ]
    return "\n".join(lines) + "\n"


def run(root: Path, recipe: Path) -> dict[str, Any]:
    started = time.monotonic()
    context = prepare(root, recipe)
    cfg, source_report = context["config"], context["report"]
    deadline = started + cfg["session_limits"]["wall_seconds"] - 10
    output = local(root, cfg["workspace"])
    if (output / "report.json").exists():
        saved = identified(output / "report.json")
        if (
            saved["config_id"] != manifest_identifier(cfg)
            or saved["source_report_id"] != source_report["report_id"]
            or _sha_file(output / "summary.md") != saved["summary_sha256"]
        ):
            raise ValueError("Preserve the existing diagnostic and its exact source identity")
        check_sources(root, saved["sources"])
        return saved
    if output.exists():
        raise FileExistsError("Preserve an uncommitted diagnostic workspace; do not overwrite")
    situations, historical = historical_probes(root, context, deadline)
    details, changes, curves = {}, {}, []
    for p in (2, 3):
        details[str(p)] = lesson_details(
            context["models"][p], context["bank"], context["score"], deadline
        )
        changes[str(p)] = interference(context["models"][p], situations, context["score"], deadline)
        for arm in ARMS:
            fitted = [
                r
                for r in context["done"].values()
                if r["kind"] == "fit" and r["player"] == p and r["arm"] == arm
            ]
            curves.append(
                {
                    "player": p,
                    "arm": arm,
                    "saved_updates": sum(r["work"]["new_optimizer_steps"] for r in fitted),
                    "epochs": [{"epoch": r["epoch"], **r["work"]} for r in fitted],
                }
            )
    fights = fight_details(root, context, deadline)
    fresh = summary(context["source"], context["done"])
    if fresh != source_report["fresh_games"] or not fresh["complete"]:
        raise ValueError("Complete fresh-game denominators/comparisons must reconstruct")
    check_sources(root, context["sources"])
    remaining(deadline)
    body = {
        "schema_version": "native-teaching-diagnostic-report-v1",
        "config_id": manifest_identifier(cfg),
        "source_report_id": source_report["report_id"],
        "source_stage": context["source"]["stage"],
        "sources": context["sources"],
        "lesson_diagnostics": details,
        "fitting_curves": curves,
        "fight_diagnostics": fights,
        "historical_probe": historical,
        "unrelated_choice_movement": changes,
        "fresh_game_evidence": fresh,
        "diagnostic_scope": "completed_records_imitation_execution_transfer_and_behavior_movement",
        "full_run_objective": context["score"].evaluation_objective.as_dict(),
        "training_spec_id": context["score"].spec_id,
        "original_weights_and_all_Adam_unchanged": True,
        "all_saved_checkpoints_and_pinned_sources_unchanged": True,
        "running_experiment_workspace_opened": False,
        "source_session_or_worker_locks_acquired": False,
        "partial_results_used": False,
        "new_games": 0,
        "optimizer_steps": 0,
        "baseline_fits": 0,
        "game_apps_created": 0,
        "checkpoint_promoted": False,
        "adaptive_controller_allowed": False,
        "automatic_training_follows": False,
        "wall_seconds": time.monotonic() - started,
    }
    text = render(body)
    output.mkdir(parents=True)
    (output / "summary.md").write_text(text)
    body["summary_sha256"] = _sha_file(output / "summary.md")
    result = {**body, "report_id": manifest_identifier(body)}
    atomic_json(output / "report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    try:
        report = run(root, args.recipe.resolve())
    except (ValueError, OSError, TimeoutError, KeyError) as exc:
        print(json.dumps({"status": "stopped_preserving_sources", "error": str(exc)}, indent=2))
        return 1
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "report_id",
                    "source_stage",
                    "source_report_id",
                    "new_games",
                    "optimizer_steps",
                    "original_weights_and_all_Adam_unchanged",
                    "wall_seconds",
                )
            },
            indent=2,
        )
    )
    print(f"Saved diagnosis: {json.loads(args.recipe.read_text())['workspace']}/summary.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
