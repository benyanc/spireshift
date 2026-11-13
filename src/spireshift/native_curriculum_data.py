"""Outcome-blind roots and public labels from new fitting worlds, never evaluations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.native_curriculum_config import ARMS
from spireshift.native_curriculum_policy import action_logs
from spireshift.native_flow_verification_v12 import records
from spireshift.native_natural_data import ending, improves, resources
from spireshift.native_situation_features import describe
from spireshift.native_teaching_data import public_step
from spireshift.native_turn_teacher_policy import room


def roots(context: dict[str, Any], case: dict[str, Any], directory: Path) -> list[dict[str, Any]]:
    rows = list(records(directory / "shared-public.jsonl.gz"))
    frames = [r["frame"] for r in rows if r["kind"] in {"policy_input", "final_observation"}]
    choices = [r["choice"] for r in rows if r["kind"] == "policy_choice"]
    if len(frames) != len(choices) + 1 or not frames[-1]["terminal"]:
        raise ValueError("Only a complete naturally collected game can provide roots")
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[int, int, str]] = set()
    for i, frame in enumerate(frames[:-1]):
        public = frame["public_input"]
        c = public["context"]["interaction"]["content"]["context"]
        if (
            frame["source_family"] != "combat_turn"
            or c.get("round", 0) < 2
            or len(public["candidates"]) < 2
        ):
            continue
        owner = room(public)
        if owner in seen:
            continue
        seen.add(owner)
        candidates.append({"decision": i, "descriptor": describe(public), "room": owner})
    if not candidates:
        return []
    chosen = [candidates[0]]
    if case["partition"] != "heldout" and context["config"]["plan"]["roots_per_fit_world"] == 2:
        first = chosen[0]["descriptor"]
        later = [c for c in candidates[1:] if c["descriptor"]["floor"] > first["floor"]]
        if later:

            def novelty(c: dict[str, Any]) -> tuple[Any, ...]:
                d = c["descriptor"]
                return (
                    sum(
                        d[k] != first[k]
                        for k in [
                            "deck_signature",
                            "enemy_definitions",
                            "hp_band",
                            "relic_signature",
                        ]
                    ),
                    len(set(d["tags"]) - set(first["tags"])),
                    d["floor"],
                    -c["decision"],
                )

            chosen.append(max(later, key=novelty))
    result: list[dict[str, Any]] = []
    model = context["models"][case["player"]]
    for selected in chosen:
        i = selected["decision"]
        initial = frames[i]["public_input"]
        steps, outcome, finish = [], None, None
        for j in range(i, len(frames)):
            public = frames[j]["public_input"]
            outcome = ending(initial, public)
            if outcome is not None:
                finish = resources(public)
                break
            steps.append(
                {
                    "public_input": public,
                    "public_input_id": manifest_identifier(public),
                    "action_index": choices[j]["action_index"],
                    "log_probabilities": action_logs(model, public, context["score"]),
                }
            )
        if finish is None:
            raise ValueError("A complete source game has an unclassified encounter ending")
        body = {
            "world": case["seed"],
            "player": case["player"],
            "partition": case["partition"],
            "entry": "early" if not result else "later",
            "public_input": initial,
            "prefix": [
                {
                    "public_input_id": manifest_identifier(frames[k]["public_input"]),
                    "action_index": choices[k]["action_index"],
                }
                for k in range(i)
            ],
            "descriptor": selected["descriptor"],
            "reference": {
                "status": "complete",
                "outcome": outcome,
                "resources": finish,
                "steps": steps,
                "candidate": 0,
            },
        }
        result.append({**body, "root_id": manifest_identifier(body)})
    return result


def choose_reference_or_teacher(
    reference: dict[str, Any], candidates: list[dict[str, Any]]
) -> dict[str, Any]:
    good = [c for c in candidates if improves(c, reference)]
    return max(good, key=lambda c: (c["resources"]["hp"], -c["candidate"])) if good else reference


def bank(
    root_rows: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    criteria: dict[str, Any],
    *,
    control: bool,
) -> dict[str, Any]:
    by_id = {r["root_id"]: r for r in root_rows}
    usable = []
    for cell in cells:
        r = by_id[cell["root_id"]]
        if r["partition"] not in ({"control"} if control else {"fit"}):
            raise ValueError("Withheld worlds cannot supply teacher search or fitting labels")
        selected = cell["selected"]
        if (
            selected["status"] == "complete"
            and (selected["outcome"] == "win" or control)
            and len([s for s in selected["steps"] if len(s["public_input"]["candidates"]) > 1])
            >= (1 if control else 4)
            and cell["confirmation_verified"] is True
        ):
            usable.append((r, cell))
    worlds = {r["world"] for r, _ in usable}
    improved = {r["world"] for r, c in usable if improves(c["selected"], r["reference"])}
    checks = {
        "independent_fitting_worlds": len(worlds) >= criteria["independent_fitting_worlds"],
        "both_source_players": len({r["player"] for r, _ in usable}) >= criteria["source_players"],
        "strictly_improved_worlds": len(improved) >= criteria["strictly_improved_worlds"],
        "enemy_compositions": len({tuple(r["descriptor"]["enemy_definitions"]) for r, _ in usable})
        >= criteria["enemy_compositions"],
        "deck_compositions": len({r["descriptor"]["deck_signature"] for r, _ in usable})
        >= criteria["deck_compositions"],
    }
    lessons = []
    for r, cell in usable:
        plans = {}
        for arm, source in zip(ARMS, [r["reference"], cell["selected"]], strict=True):
            steps = [
                public_step(s) for s in source["steps"] if len(s["public_input"]["candidates"]) > 1
            ]
            plans[arm] = {"root_id": r["root_id"], "world": r["world"], "steps": steps}
        lessons.append(
            {
                "root_id": r["root_id"],
                "world": r["world"],
                "source_player": r["player"],
                "partition": r["partition"],
                "plans": plans,
            }
        )
    body = {
        "schema_version": "native-varied-public-lesson-bank-v1",
        "lessons": lessons,
        "quality": {
            "passed": all(checks.values()),
            "checks": checks,
            "fitting_worlds": len(worlds),
            "strictly_improved_worlds": len(improved),
        },
        "control_only": control,
        "student_inputs_public_only": True,
        "heldout_labels_or_outcomes_used": False,
        "privileged_fixed_world_teacher": True,
        "ordinary_PPO_eligible": False,
    }
    return {**body, "bank_id": manifest_identifier(body)}
