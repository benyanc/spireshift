from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from spireshift.core.types import BudgetTier, LegalAction, Observation, Transition


class EnvironmentAdapter(Protocol):
    patch_id: str

    def reset(self, seed: int) -> Observation: ...

    def legal_actions(self) -> Sequence[LegalAction]: ...

    def step(self, action: LegalAction) -> Transition: ...


class Policy(Protocol):
    policy_id: str

    def choose_action(
        self, observation: Observation, legal_actions: Sequence[LegalAction]
    ) -> LegalAction: ...


class BudgetController(Protocol):
    controller_id: str

    def choose_tier(self, observation: Observation, remaining_budget: int) -> BudgetTier: ...


class Recorder(Protocol):
    path: Path

    def record_header(self, payload: dict[str, object]) -> None: ...

    def record_step(self, payload: dict[str, object]) -> None: ...

    def record_summary(self, payload: dict[str, object]) -> None: ...
