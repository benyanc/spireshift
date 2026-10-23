"""Freeze improved fitting plans from the completed search, never held-out labels."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_neural import validate_public_input
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_reuse import check_sources
from spireshift.native_coordinated_teacher import read_fight
from spireshift.native_natural_data import improves

CONTRACT = "native_verified_plan_student_transfer_v1"
ARMS = ("reference_clone", "teacher_clone")
VARIANTS = ("initial", *ARMS)
BANK = "artifacts/native-teaching/lessons-v1/bank.json"
TEACHER = "artifacts/native-coordinated/sts2-v0.111.0-a8-comparison-v2/report.json"
ASSESSMENT = "artifacts/native-coordinated/main-assessment-v2/report.json"
LEARNING = {
    "epochs": 16,
    "steps_per_epoch": 4,
    "batch_choices": 32,
    "actor_learning_rate": 0.001,
    "gradient_clip": 1.0,
    "temperature": 0.8,
}


def public_step(step: dict[str, Any]) -> dict[str, Any]:
    public, action = step["public_input"], step["action_index"]
    validate_public_input(public)
    if (
        step["public_input_id"] != manifest_identifier(public)
        or type(action) is not int
        or not 0 <= action < len(public["candidates"])
    ):
        raise ValueError("Bind a teaching label to its exact public legal menu")
    return {
        "public_input": public,
        "public_input_id": step["public_input_id"],
        "action_index": action,
    }


def lessons(
    root: Path, roots: list[dict[str, Any]], teacher: dict[str, Any]
) -> list[dict[str, Any]]:
    """Pick the best already-confirmed early plan per fitting world, stable on ties."""
    result = []
    for i, r in enumerate(roots):
        if r["partition"] != "fit":
            continue  # Do not inspect held-out choices or outcome rankings here.
        cells = [
            c for c in teacher["cells"] if c["root_id"] == r["root_id"] and c["entry"] == "early"
        ]
        if len(cells) != 2 or not all(c["verified"] and c["partition"] == "fit" for c in cells):
            raise ValueError("Require both verified fitting cells; never a forged held-out gate")
        by_id = {
            row["fight_id"]: row for row in teacher["fights"].values() if row["kind"] == "fight"
        }
        reference_ids = {c["reference_fight_id"] for c in cells}
        if len(reference_ids) != 1:
            raise ValueError("Both methods must share the original reference")
        reference = read_fight(root, by_id[reference_ids.pop()])
        choices = [
            (c, read_fight(root, by_id[c["selected_fight_id"]]))
            for c in sorted(cells, key=lambda c: c["arm"] != "single_change")
        ]
        choices = [(c, f) for c, f in choices if improves(f, reference)]
        if not choices:
            continue
        c, selected = max(choices, key=lambda pair: pair[1]["resources"]["hp"])
        confirmation = teacher["fights"][f"root-{i:02d}-early-confirm-{c['arm'].replace('_', '-')}"]
        confirmed = read_fight(root, confirmation)
        if (
            selected["root_id"] != r["root_id"]
            or reference["root_id"] != r["root_id"]
            or confirmed["status"] != "complete"
            or confirmed["steps"] != selected["steps"]
            or confirmed["resources"] != selected["resources"]
            or confirmed["outcome"] != selected["outcome"]
            or not selected["native_audit"]["valid"]
        ):
            raise ValueError("Teaching requires the complete confirmed natural path")
        plans = {}
        for arm, value in zip(ARMS, (reference, selected), strict=True):
            steps = [
                public_step(s) for s in value["steps"] if len(s["public_input"]["candidates"]) > 1
            ]
            if not steps:
                raise ValueError("Every fitting world requires actual choices")
            plans[arm] = {"root_id": r["root_id"], "world": r["world"], "steps": steps}
        changed = []
        for edit in selected["edits"]:
            s = public_step(selected["steps"][edit["decision"]])
            if (
                s["public_input_id"] != edit["public_input_id"]
                or s["action_index"] != edit["action"]
            ):
                raise ValueError("Changed-choice diagnostic lost its observed plan owner")
            changed.append(s)
        if not changed:
            raise ValueError("An improved teaching plan must contain an actual changed choice")
        result.append(
            {
                "root_id": r["root_id"],
                "world": r["world"],
                "source_player": r["player"],
                "partition": "fit",
                "chosen_search_arm": c["arm"],
                "reference_fight_id": reference["fight_id"],
                "teacher_fight_id": selected["fight_id"],
                "confirmation_fight_id": confirmed["fight_id"],
                "reference_outcome": reference["outcome"],
                "teacher_outcome": selected["outcome"],
                "reference_hp": reference["resources"]["hp"],
                "teacher_hp": selected["resources"]["hp"],
                "plans": plans,
                "changed_choices": {"root_id": r["root_id"], "world": r["world"], "steps": changed},
            }
        )
    if len(result) != len({r["world"] for r in result}):
        raise ValueError("Entry points cannot manufacture independent fitting worlds")
    return result


def prepare(root: Path) -> dict[str, Any]:
    from spireshift.native_coordinated_inputs import load

    output = root / BANK
    if output.exists():
        saved = identified(output, "bank_id")
        check_sources(root, saved["sources"])
        return saved
    context = load(root, root / "configs/native-coordinated/sts2-v0.111.0-a8-comparison-v2.json")
    teacher, audit = identified(root / TEACHER), identified(root / ASSESSMENT)
    if (
        teacher["report_id"]
        != "sha256:1b9adc8a9551d32728f8901c710bf59e1cb8060e884b23f7e030751a537794b7"
        or teacher["status"] != "coordinated_teacher_complete"
        or not all(teacher["control_checks"].values())
        or not audit["valid"]
        or audit["main_report_id"] != teacher["report_id"]
    ):
        raise ValueError("Bind the assessed completed comparison, never resume its collector")
    check_sources(root, teacher["sources"])
    chosen = lessons(root, context["roots"], teacher)
    if len(chosen) != 2 or {r["source_player"] for r in chosen} != {2}:
        raise ValueError("Preserve the explicitly limited two-world fitting bank")
    sources = {**context["sources"], **teacher["sources"]}
    sources.update({n: _sha_file(root / n) for n in (TEACHER, ASSESSMENT)})
    sources["src/spireshift/native_teaching_data.py"] = _sha_file(Path(__file__))
    body = {
        "schema_version": "native-plan-teaching-bank-v1",
        "contract": CONTRACT,
        "runtime": context["source"],
        "lessons": chosen,
        "roots": context["roots"],
        "teacher_report_id": teacher["report_id"],
        "sources": sources,
        "student_inputs_public_only": True,
        "fixed_hidden_world_teacher": True,
        "heldout_used_for_fitting": False,
        "optimizer_steps": 0,
        "native_attempts": 0,
    }
    result = {**body, "bank_id": manifest_identifier(body)}
    atomic_json(output, result)
    return result
