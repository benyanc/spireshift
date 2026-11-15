"""Identity-compatible cached model; historical pinned implementations stay unchanged."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import Any, cast

from spireshift.native_action_context import ActionContextModel


@dataclass(frozen=True)
class CachedContextModel(ActionContextModel):
    """Cache only metadata of an immutable checkpoint, never observations or outputs.

    dataclasses.replace/with_weights construct a new instance with an empty cache.
    The inherited serialization, model ID and numerical policy remain identical.
    """

    @cached_property
    def model_id(self) -> str:
        return super().model_id

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> CachedContextModel:
        return cast(CachedContextModel, super().from_mapping(value))


def cached_model(model: ActionContextModel) -> CachedContextModel:
    result = CachedContextModel(model.native, model.mode, model.feature_spec_id)
    # Warm once before sharing the model across collection lanes, including on
    # Python versions where cached_property itself does not serialize first access.
    _ = result.model_id
    return result
