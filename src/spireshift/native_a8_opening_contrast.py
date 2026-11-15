"""Choose early combat comparisons with known native reward and loss anchors."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from copy import copy
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_turn_rescue
from spireshift.native_a8_action_credit_policy import alternate
from spireshift.native_a8_coverage_policy import Root
from spireshift.native_a8_coverage_session import Collection
from spireshift.native_a8_mix_data import room_evidence
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_rescue_game import TRACE, decisions
from spireshift.native_a8_sampling_roots import menu_facts, source_game
from spireshift.native_a8_turn_rescue import RescueChooser, RescueContinuation
from spireshift.native_context_cache import CachedContextModel
from spireshift.training_objective import TrainingScoreSpec

OUTCOMES = {"reward", "loss"}
TERMINAL = {"win", "loss"}
ENCOUNTERS = ("elite", "normal")


class DistinctChooser(RescueChooser):
    draw: int = 0

    def __call__(self, public: dict[str, Any]) -> dict[str, Any]:
        if not self.armed or self.draw == 0:
            return super().__call__(public)
        if self.draw != 1 or not self.seed.endswith("/1"):
            raise ValueError("Require the second declared draw from the matched opening")
        first = copy(self)
        first.seed = self.seed.removesuffix("/1") + "/0"
        first.draw = 0
        first.visits = self.visits.copy()
        previous = first(public)["action_index"]
        excluded = public["candidates"][previous]["label"]

        def without_first(
            scores: Sequence[float],
            labels: Sequence[str],
            reference: int,
            temperature: float,
            draw: float,
        ) -> tuple[int, float, float]:
            filtered = [labels[reference] if label == excluded else label for label in labels]
            return alternate(scores, filtered, reference, temperature, draw)

        with patch.object(native_a8_turn_rescue, "alternate", without_first):
            choice = super().__call__(public)
        choice["previous_alternative_index"] = previous
        return choice


class DistinctContinuation(RescueContinuation):
    def __init__(
        self,
        model: CachedContextModel,
        score: TrainingScoreSpec,
        root: Root,
        draw_seed: str,
        arm: str,
        *,
        draw: int,
    ) -> None:
        super().__init__(model, score, root, draw_seed, arm)
        chooser = DistinctChooser(model, score, root)
        chooser.draw = draw
        self.core.chooser = chooser


def openings(path: Path, task: dict[str, Any], seal: str) -> list[dict[str, Any]]:
    native: list[dict[str, Any]] = []
    first: dict[tuple[int, int], dict[str, Any] | None] = {}
    ending = None
    for _, frame, delivered in decisions(path / TRACE):
        if delivered is None:
            ending = frame
            break
        if delivered["receipt"]["delivery_domain"] != "native":
            continue
        public = frame["public_input"]
        if frame["source_family"] == "combat_turn":
            run = public["context"]["persistent"]["run"]
            room = run["act"], run["floor"]
            if room not in first:
                first[room] = None
                facts = menu_facts(frame)
                labels = {candidate["label"] for candidate in public["candidates"]}
                round_number = public["context"]["interaction"]["content"]["context"]["round"]
                if (
                    room[0] == 1
                    and round_number == 1
                    and facts["encounter"] in ENCOUNTERS
                    and 2 * facts["hp"] >= facts["max_hp"]
                    and len(labels) >= 3
                ):
                    first[room] = {
                        **facts,
                        "round": round_number,
                        "source_task": task,
                        "source_seal_id": seal,
                        "prefix_native_deliveries": len(native),
                        "reference_action_index": delivered["choice"]["action_index"],
                    }
        native.append(public)
    if ending is None or not ending["terminal"]:
        raise ValueError("Opening anchors require a complete native game")
    results = room_evidence(native, ending, len(native)).outcomes
    return [
        {**spec, "reference_room_outcome": "reward" if results[room][1] else "loss"}
        for room, spec in first.items()
        if spec is not None and room in results and results[room][0] == spec["encounter"]
    ]


def roots_from_source(
    coverage: Collection, owner: dict[str, Any], task: dict[str, Any]
) -> list[dict[str, Any]]:
    path, seal = source_game(coverage, owner, task)
    return openings(path, task, seal)


def select(
    coverage: Collection,
    owner: dict[str, Any],
    previous_menus: set[str],
    diagnostic_worlds: set[str],
) -> list[dict[str, Any]]:
    candidates: dict[tuple[int, str, str], list[dict[str, Any]]] = defaultdict(list)
    for task in coverage.cfg["study"]:
        if task["partition"] != "train" or task["seed"] in diagnostic_worlds:
            continue
        for spec in roots_from_source(coverage, owner, task):
            if spec["root_input_id"] not in previous_menus:
                key = task["player"], spec["encounter"], spec["reference_room_outcome"]
                candidates[key].append(spec)
    slots = [
        (p, kind, result, i, False)
        for p in PLAYERS
        for kind in ENCOUNTERS
        for result in sorted(OUTCOMES)
        for i in (1, 2)
    ] + [(p, "normal", "reward", 1, True) for p in PLAYERS]
    slots.sort(key=lambda slot: len({s["source_task"]["seed"] for s in candidates[slot[:3]]}))
    chosen = []
    used = set()
    for p, kind, result, i, control in slots:
        anchor = next(
            (row for row in candidates[p, kind, result] if row["source_task"]["seed"] not in used),
            None,
        )
        if anchor is None:
            raise ValueError(f"Need an independent player {p} {kind} {result} anchor")
        used.add(anchor["source_task"]["seed"])
        part = "control" if control else "train"
        chosen.append({**anchor, "id": f"{part}-p{p}-{kind}-{result}-{i}", "control": control})
    return sorted(chosen, key=lambda spec: spec["id"])


def summarize(
    plan: list[dict[str, Any]], rows: dict[str, Any], roots: dict[str, Root]
) -> dict[str, Any]:
    by_root: dict[str, list[dict[str, Any]]] = defaultdict(list)
    contrasts: dict[str, dict[str, Any]] = {}
    resolved = 0
    for task in plan:
        row = rows.get(task["key"])
        if row is None or row["outcome"] not in TERMINAL:
            continue
        outcome = row["observed_room_outcome"]
        if outcome not in OUTCOMES:
            continue
        resolved += 1
        root = task["root"]
        by_root[root].append(row)
        spec = roots[root].spec
        if outcome != spec["reference_room_outcome"]:
            contrasts[root] = {
                "player": task["player"],
                "seed": task["seed"],
                "encounter": spec["encounter"],
                "reference_outcome": spec["reference_room_outcome"],
            }
    for alternatives in by_root.values():
        if len({row["alternative_action_index"] for row in alternatives}) != len(alternatives):
            raise ValueError("Two opening probes delivered the same first choice")
    worlds = {
        str(p): len({s["seed"] for s in contrasts.values() if s["player"] == p}) for p in PLAYERS
    }
    directions = Counter(s["reference_outcome"] for s in contrasts.values())
    types = sorted({s["encounter"] for s in contrasts.values()})
    return {
        "planned_probes": len(plan),
        "resolved_room_outcomes": resolved,
        "contrast_worlds_by_initializer": worlds,
        "reference_outcomes_with_a_contrast": dict(directions),
        "encounter_types_with_a_contrast": types,
        "candidate_for_separate_preference_admission": (
            resolved == len(plan)
            and all(n >= 3 for n in worlds.values())
            and set(directions) == OUTCOMES
            and set(types) == set(ENCOUNTERS)
        ),
    }
