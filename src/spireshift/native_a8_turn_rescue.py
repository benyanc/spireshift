"""Generate native, same-menu combat preferences from verified training losses."""

from __future__ import annotations

from typing import Any, cast

from spireshift.full_run_policy import score_features
from spireshift.native_a8_action_credit_policy import alternate
from spireshift.native_a8_coverage_policy import Root
from spireshift.native_a8_coverage_session import Collection
from spireshift.native_a8_own_policy import AllActions
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_rescue_game import TRACE, decisions
from spireshift.native_a8_sampling_roots import SamplingContinuation, menu_facts, source_game
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_structured_policy import Chooser
from spireshift.training_objective import TrainingScoreSpec

ENCOUNTERS = ("boss", "elite", "normal")
PROBE = "turn_rescue_probe_v1"


class RescueChooser(Chooser):
    def __init__(self, model: CachedContextModel, score: TrainingScoreSpec, root: Root) -> None:
        super().__init__(model, score, root.spec["source_task"]["seed"], training=True)
        self.navigation = AllActions()
        self.root = root
        self.armed = False

    def __call__(self, public: dict[str, Any]) -> dict[str, Any]:
        choice = super().__call__(public)
        if not self.armed:
            return choice
        self.armed = False
        assert self.last is not None
        rows, _, effective, forced = self.last
        if (
            choice["public_input_id"] != self.root.spec["root_input_id"]
            or effective != public
            or forced
        ):
            raise ValueError("A rescue probe requires the verified complete menu")
        reference = self.root.spec["reference_action_index"]
        selected, conditional, original = alternate(
            score_features(cast(Any, self.model.actor), rows),
            [candidate["label"] for candidate in public["candidates"]],
            reference,
            choice["temperature"],
            choice["draw"],
        )
        choice.update(
            action_index=selected,
            effective_action_index=selected,
            log_probability=conditional,
            policy_log_probability=original,
            turn_rescue_probe={"contract": PROBE, "reference_action_index": reference},
        )
        return choice


class RescueContinuation(SamplingContinuation):
    def __init__(
        self,
        model: CachedContextModel,
        score: TrainingScoreSpec,
        root: Root,
        draw_seed: str,
        arm: str,
    ) -> None:
        super().__init__(model, score, root, draw_seed, arm)
        self.core.chooser = RescueChooser(model, score, root)

    def choose(self, frame: dict[str, Any]) -> dict[str, Any]:
        if self.decisions + self.local_factors == len(self.root.prefix):
            cast(RescueChooser, self.core.chooser).armed = True
        return super().choose(frame)


def source_root(
    coverage: Collection, owner: dict[str, Any], task: dict[str, Any]
) -> dict[str, Any] | None:
    """Find a choice-bearing decision at the start of one of the final two turns."""
    path, seal_id = source_game(coverage, owner, task)
    if owner["games"][task["key"]]["outcome"] != "loss":
        return None
    turns: dict[tuple[int, int, int], dict[str, Any] | None] = {}
    index = 0
    last = None
    ending = None
    for _, frame, delivered in decisions(path / TRACE):
        if delivered is None:
            ending = frame
            break
        if delivered["receipt"]["delivery_domain"] != "native":
            continue
        context = frame["public_input"]["context"]
        run = context["persistent"]["run"]
        last = None
        if frame["source_family"] == "combat_turn":
            combat = context["interaction"]["content"]["context"]
            last = run["act"], run["floor"], combat["round"]
            if last not in turns:
                labels = {candidate["label"] for candidate in frame["public_input"]["candidates"]}
                turns[last] = (
                    {
                        **menu_facts(frame),
                        "round": last[2],
                        "source_task": task,
                        "source_seal_id": seal_id,
                        "prefix_native_deliveries": index,
                        "reference_action_index": delivered["choice"]["action_index"],
                    }
                    if len(labels) > 1
                    else None
                )
        index += 1
    if last is None or last[0] != 1 or ending is None or not ending["terminal"]:
        return None
    terminal = ending["public_input"]["context"]["persistent"]
    if (
        ending["ending"]["victory"] is not False
        or terminal["player"]["hp"] != 0
        or (terminal["run"]["act"], terminal["run"]["floor"]) != last[:2]
    ):
        return None
    act, floor, last_round = last
    return turns.get((act, floor, last_round - 1)) or turns.get(last)


def select(coverage: Collection, owner: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = []
    for task in coverage.cfg["study"]:
        if task["partition"] == "train":
            root = source_root(coverage, owner, task)
            if root is not None:
                candidates.append(root)
    used = set()
    roots = []
    slots = [(p, encounter, i, False) for encounter in ENCOUNTERS for p in PLAYERS for i in (1, 2)]
    slots.extend((p, "normal", 1, True) for p in PLAYERS)
    for p, encounter, i, control in slots:
        root = next(
            (
                r
                for r in candidates
                if r["source_task"]["player"] == p
                and r["encounter"] == encounter
                and r["source_task"]["seed"] not in used
            ),
            None,
        )
        if root is None:
            raise ValueError(f"Need a distinct player {p} {encounter} turn with alternatives")
        used.add(root["source_task"]["seed"])
        prefix = "control" if control else "train"
        roots.append({**root, "id": f"{prefix}-p{p}-{encounter}-{i}", "control": control})
    return roots


def summarize(plan: list[dict[str, Any]], rows: dict[str, Any]) -> dict[str, Any]:
    successes = {
        row["task"]["root"]: row
        for row in rows.values()
        if row["outcome"] in {"win", "loss"} and row["observed_room_outcome"] == "reward"
    }
    worlds = {
        p: {row["task"]["seed"] for row in successes.values() if row["task"]["player"] == p}
        for p in PLAYERS
    }
    types = sorted({row["encounter"] for row in successes.values()})
    complete = sum(row["outcome"] in {"win", "loss"} for row in rows.values())
    resolved = sum(
        row["outcome"] in {"win", "loss"} and row["observed_room_outcome"] in {"loss", "reward"}
        for row in rows.values()
    )
    return {
        "planned_probes": len(plan),
        "terminal_probes": complete,
        "resolved_room_outcomes": resolved,
        "reward_successes": sum(row["observed_room_outcome"] == "reward" for row in rows.values()),
        "distinct_rescued_roots": len(successes),
        "rescued_worlds_by_initializer": {str(p): len(worlds[p]) for p in PLAYERS},
        "rescued_encounter_types": types,
        "candidate_for_separate_preference_admission": (
            resolved == len(plan) and all(len(worlds[p]) >= 2 for p in PLAYERS) and len(types) >= 2
        ),
    }
