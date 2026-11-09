"""Replay verified normal-start combat openings with matched full-menu draws."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import closing
from fractions import Fraction
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from spireshift import native_structured_policy
from spireshift.core.manifest import manifest_identifier
from spireshift.native_a8_coverage_policy import Root, Sample, eligible_menus, sample
from spireshift.native_a8_coverage_session import Collection, journal, request
from spireshift.native_a8_own_experience import FrameChoice, groups
from spireshift.native_a8_own_policy import OwnPolicy
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_policy_updates import SETTINGS
from spireshift.native_win4_plan import AnswerPolicy
from spireshift.training_objective import TrainingScoreSpec

TEMPERATURES = {"standard": 0.8, "sharp": 0.4}


class SamplingContinuation(AnswerPolicy):
    def __init__(
        self,
        model: CachedContextModel,
        score: TrainingScoreSpec,
        root: Root,
        draw_seed: str,
        arm: str,
    ) -> None:
        super().__init__(OwnPolicy(model, score, root.spec["source_task"]["seed"]))
        self.root, self.draw_seed, self.temperature = root, draw_seed, TEMPERATURES[arm]

    def choose(self, frame: dict[str, Any]) -> dict[str, Any]:
        index = self.decisions + self.local_factors
        prefix = self.root.prefix
        if index < len(prefix):
            choice = super().choose(frame)
            if sample(choice) != prefix[index] or choice["temperature"] != TEMPERATURES["standard"]:
                raise ValueError("Replayed original choice differs from the sealed prefix")
            return choice
        if index == len(prefix):
            if (
                self.planning
                or self.decisions != self.root.spec["prefix_native_deliveries"]
                or manifest_identifier(frame["public_input"]) != self.root.spec["root_input_id"]
            ):
                raise ValueError(
                    "Require the exact verified combat opening before changing sampling"
                )
            self.core.chooser.seed = self.draw_seed
        with patch.object(
            native_structured_policy,
            "SETTINGS",
            {
                **SETTINGS,
                "temperature": self.temperature,
            },
        ):
            return super().choose(frame)


def source_game(
    coverage: Collection, owner: dict[str, Any], task: dict[str, Any]
) -> tuple[Path, str]:
    store = journal(coverage, False)
    key = task["key"]
    seal = store.completed(key, request(coverage, task))
    if (
        task["partition"] != "train"
        or task not in coverage.cfg["study"]
        or seal is None
        or seal["report_id"] != owner["seals"][key]
        or seal["result"] != owner["games"][key]
        or seal["result"]["task"] != task
        or seal["result"]["outcome"] not in {"win", "loss"}
    ):
        raise ValueError("A sampling root requires a sealed, normal-start training game")
    return store.path(key), seal["report_id"]


def menu_facts(frame: dict[str, Any]) -> dict[str, Any]:
    context = frame["public_input"]["context"]
    run, player = context["persistent"]["run"], context["persistent"]["player"]
    return {
        "root_input_id": manifest_identifier(frame["public_input"]),
        "floor": run["floor"],
        "encounter": context["interaction"]["content"]["context"]["encounter_type"],
        "hp": player["hp"],
        "max_hp": player["max_hp"],
    }


def select_roots(coverage: Collection, owner: dict[str, Any]) -> list[dict[str, Any]]:
    roots = []
    for p in PLAYERS:
        model = coverage.temporal.base.originals[p][0]
        candidates = []
        for task in coverage.cfg["study"]:
            if task["partition"] != "train" or task["player"] != p:
                continue
            path, seal_id = source_game(coverage, owner, task)
            for index, frame in eligible_menus(groups(path, model.model_id)):
                if frame["source_family"] != "combat_turn":
                    continue
                facts = menu_facts(frame)
                if facts["encounter"] in {"boss", "elite"} and 2 * facts["hp"] >= facts["max_hp"]:
                    candidates.append(
                        {
                            **facts,
                            "source_task": task,
                            "source_seal_id": seal_id,
                            "prefix_native_deliveries": index,
                        }
                    )
        candidates.sort(
            key=lambda row: (
                -Fraction(row["hp"], row["max_hp"]),
                -row["floor"],
                row["source_task"]["key"],
                row["prefix_native_deliveries"],
            )
        )
        used = set()
        for family in ("boss", "elite"):
            for i in (1, 2):
                chosen = next(
                    (
                        row
                        for row in candidates
                        if row["encounter"] == family and row["source_task"]["seed"] not in used
                    ),
                    None,
                )
                if chosen is None:
                    raise ValueError(f"Require two healthy player {p} {family} training roots")
                roots.append({**chosen, "id": f"p{p}-{family}-{i}"})
                used.add(chosen["source_task"]["seed"])
    return roots


def resolve(coverage: Collection, owner: dict[str, Any], spec: dict[str, Any]) -> Root:
    task = spec["source_task"]
    path, seal_id = source_game(coverage, owner, task)
    model = coverage.temporal.base.originals[task["player"]][0]
    records = cast(Generator[list[FrameChoice], None, None], groups(path, model.model_id))
    prefix: list[Sample] = []
    with closing(records):
        for i, group in enumerate(records):
            if i == spec["prefix_native_deliveries"]:
                facts = menu_facts(group[0][0])
                if (
                    seal_id != spec["source_seal_id"]
                    or any(spec[k] != v for k, v in facts.items())
                    or not prefix
                ):
                    raise ValueError("The sampling root differs from its source seal")
                return Root(spec, tuple(prefix))
            prefix.extend(sample(choice) for _, choice in group)
    raise ValueError("The verified source never reached the declared root")
