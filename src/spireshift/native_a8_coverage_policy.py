"""Restore a training decision by regenerating its model-owned native prefix."""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.native_a8_own_experience import FrameChoice, groups
from spireshift.native_a8_own_policy import OwnPolicy
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_temporal_credit_session import Session
from spireshift.native_a8_world_credit import sampler_seed
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_win4_plan import AnswerPolicy
from spireshift.training_objective import TrainingScoreSpec

STRATA = (
    ("late", 10, 17, "combat_turn"),
    ("late", 10, 17, "map_navigation"),
    ("middle", 5, 9, "combat_turn"),
    ("middle", 5, 9, "map_navigation"),
)
Sample = tuple[str, int, str, float]


def sample(choice: dict[str, Any]) -> Sample:
    return (
        choice["public_input_id"],
        choice["action_index"],
        choice["draw_key"],
        choice["log_probability"],
    )


@dataclass(frozen=True)
class Root:
    spec: dict[str, Any]
    prefix: tuple[Sample, ...]


class Continuation(AnswerPolicy):
    def __init__(
        self, model: CachedContextModel, score: TrainingScoreSpec, root: Root, draw_seed: str
    ) -> None:
        task = root.spec["source_task"]
        super().__init__(OwnPolicy(model, score, sampler_seed(task["seed"], task["draw"])))
        self.root, self.draw_seed = root, draw_seed

    def choose(self, frame: dict[str, Any]) -> dict[str, Any]:
        index = self.decisions + self.local_factors
        prefix = self.root.prefix
        if index == len(prefix):
            if (
                self.planning
                or self.decisions != self.root.spec["prefix_native_deliveries"]
                or manifest_identifier(frame["public_input"]) != self.root.spec["root_input_id"]
            ):
                raise ValueError("Regenerated prefix did not reach the exact native training root")
            self.core.chooser.seed = self.draw_seed
        choice = super().choose(frame)
        if index < len(prefix) and sample(choice) != prefix[index]:
            raise ValueError("Regenerated model sample differs from the sealed training prefix")
        return choice


def training_source(session: Session, task: dict[str, Any]) -> tuple[Path, str]:
    model, _, state_id = session.references[task["player"], "original"]
    key = task["key"]
    seal = session.source.completed(key, {"task": task, "state_id": state_id})
    if (
        task["partition"] != "train"
        or task not in session.source.recipe["study"]["training"]
        or seal is None
        or seal["report_id"] != session.owner["seals"][key]
        or seal["result"] != session.owner["games"][key]
        or seal["result"]["outcome"] not in {"win", "loss"}
        or seal["result"]["model_id"] != model.model_id
    ):
        raise ValueError("A continuation requires a sealed model-owned training-only source")
    return session.source.path(key), seal["report_id"]


def eligible_menus(
    records: Iterator[list[FrameChoice]],
) -> Iterator[tuple[int, dict[str, Any]]]:
    opened = set()
    for index, group in enumerate(records):
        frame = group[0][0]
        context = frame["public_input"]["context"]
        run = context["persistent"]["run"]
        family, floor = frame["source_family"], run["floor"]
        if family == "combat_turn":
            key = run["act"], floor
            if key in opened:
                continue
            opened.add(key)
            if context["interaction"]["content"]["context"].get("round") != 1:
                continue
        if (
            run["act"] == 1
            and 5 <= floor <= 17
            and family in {"map_navigation", "combat_turn"}
            and len(frame["actions"]) > 1
        ):
            yield index, frame


def root_spec(
    task: dict[str, Any], seal_id: str, index: int, frame: dict[str, Any]
) -> dict[str, Any]:
    floor = frame["public_input"]["context"]["persistent"]["run"]["floor"]
    family = frame["source_family"]
    band = "late" if floor >= 10 else "middle"
    role = "combat" if family == "combat_turn" else "map"
    return {
        "id": f"p{task['player']}-{band}-{role}",
        "source_task": task,
        "source_seal_id": seal_id,
        "root_input_id": manifest_identifier(frame["public_input"]),
        "prefix_native_deliveries": index,
        "floor": floor,
        "family": family,
    }


def select_roots(session: Session) -> list[dict[str, Any]]:
    """Choose by public depth and coverage without looking at alternative outcomes."""
    roots = []
    for p in PLAYERS:
        model = session.references[p, "original"][0]
        candidates = []
        for task in session.source.recipe["study"]["training"]:
            if task["player"] != p:
                continue
            path, seal_id = training_source(session, task)
            for index, frame in eligible_menus(groups(path, model.model_id)):
                candidates.append(root_spec(task, seal_id, index, frame))
        candidates.sort(
            key=lambda row: (
                -row["floor"],
                row["prefix_native_deliveries"],
                row["source_task"]["key"],
            )
        )
        used = set()
        for _, lo, hi, family in STRATA:
            chosen = next(
                (
                    row
                    for row in candidates
                    if lo <= row["floor"] <= hi
                    and row["family"] == family
                    and row["source_task"]["seed"] not in used
                ),
                None,
            )
            if chosen is None:
                raise ValueError(
                    f"Require an independent player {p} training root for {family} {lo}–{hi}"
                )
            roots.append(chosen)
            used.add(chosen["source_task"]["seed"])
    return roots


def resolve_root(session: Session, spec: dict[str, Any]) -> Root:
    task = spec["source_task"]
    path, seal_id = training_source(session, task)
    model = session.references[task["player"], "original"][0]
    prefix: list[Sample] = []
    records = cast(Generator[list[FrameChoice], None, None], groups(path, model.model_id))
    with closing(records):
        for i, group in enumerate(records):
            if i == spec["prefix_native_deliveries"]:
                if root_spec(task, seal_id, i, group[0][0]) != spec or not prefix:
                    raise ValueError("The training-only root does not match its source seal")
                return Root(spec, tuple(prefix))
            prefix.extend(sample(choice) for _, choice in group)
    raise ValueError("The declared training-only root was never reached")
