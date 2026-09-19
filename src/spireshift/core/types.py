from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class DecisionType(StrEnum):
    PATH = "path"
    COMBAT = "combat"
    TERMINAL = "terminal"


class BudgetTier(StrEnum):
    POLICY_ONLY = "policy_only"
    SHALLOW = "shallow"
    MEDIUM = "medium"
    EXPENSIVE = "expensive"

    @property
    def nominal_cost(self) -> int:
        return {
            BudgetTier.POLICY_ONLY: 1,
            BudgetTier.SHALLOW: 4,
            BudgetTier.MEDIUM: 16,
            BudgetTier.EXPENSIVE: 64,
        }[self]


@dataclass(frozen=True, slots=True)
class Observation:
    schema_version: str
    patch_id: str
    decision_type: DecisionType
    public_state: dict[str, Any]
    state_hash: str

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["decision_type"] = self.decision_type.value
        return result


@dataclass(frozen=True, slots=True)
class LegalAction:
    action_id: str
    kind: str
    payload: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Transition:
    observation: Observation
    action: LegalAction
    next_observation: Observation
    reward: float
    terminal: bool
    victory: bool

    def __post_init__(self) -> None:
        if self.reward not in (0.0, 1.0):
            raise ValueError("Environment reward must be binary terminal victory reward")
        if self.reward == 1.0 and not (self.terminal and self.victory):
            raise ValueError("Positive reward is valid only for terminal victory")
        if self.victory and not self.terminal:
            raise ValueError("Victory must be terminal")

    def as_dict(self) -> dict[str, Any]:
        return {
            "observation": self.observation.as_dict(),
            "action": self.action.as_dict(),
            "next_observation": self.next_observation.as_dict(),
            "reward": self.reward,
            "terminal": self.terminal,
            "victory": self.victory,
        }
