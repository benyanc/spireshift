from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ObjectiveSpec:
    objective_id: str
    primary: str
    constraint: str
    whole_run_budget: int
    auxiliary: tuple[str, ...]
    auxiliary_reward_allowed: bool

    def __post_init__(self) -> None:
        if self.primary != "terminal_victory":
            raise ValueError("SpireShift's primary objective must be terminal_victory")
        if self.constraint != "cpu_time_per_run":
            raise ValueError("SpireShift requires a whole-run compute constraint")
        if self.whole_run_budget <= 0:
            raise ValueError("whole_run_budget must be positive")
        if self.auxiliary_reward_allowed:
            raise ValueError("Auxiliary metrics cannot contribute to environment reward")

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> ObjectiveSpec:
        return cls(
            objective_id=str(value["id"]),
            primary=str(value["primary"]),
            constraint=str(value["constraint"]),
            whole_run_budget=int(value["whole_run_budget"]),
            auxiliary=tuple(str(item) for item in value.get("auxiliary", [])),
            auxiliary_reward_allowed=bool(value.get("auxiliary_reward_allowed", False)),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.objective_id,
            "primary": self.primary,
            "constraint": self.constraint,
            "whole_run_budget": self.whole_run_budget,
            "auxiliary": list(self.auxiliary),
            "auxiliary_reward_allowed": self.auxiliary_reward_allowed,
        }


def load_objective(path: Path) -> ObjectiveSpec:
    with path.open("rb") as handle:
        document = tomllib.load(handle)
    objective = document.get("objective")
    if not isinstance(objective, dict):
        raise ValueError(f"Missing [objective] table in {path}")
    return ObjectiveSpec.from_mapping(objective)
