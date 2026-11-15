"""Versioned state restoration for original and named-input experimental copies."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_ppo_math import Adam
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_structured_model import SCHEMA, SupplementModel


def save(path: Path, model: CachedContextModel, adam: Adam) -> dict[str, Any]:
    if path.exists() or path.is_symlink():
        raise FileExistsError("Preserve every existing full model/Adam checkpoint")
    body = {
        "schema_version": "native-structured-model-optimizer-v1",
        "model": model.as_dict(),
        "optimizer": adam.as_dict(),
    }
    result = {**body, "state_id": manifest_identifier(body)}
    atomic_json(path, result)
    return result


def load(path: Path) -> tuple[CachedContextModel, Adam, str]:
    value = identified(path, "state_id")
    if value["schema_version"] != "native-structured-model-optimizer-v1":
        raise ValueError("Use the separately versioned structured comparison state")
    model = (
        SupplementModel.from_mapping(value["model"])
        if value["model"]["schema_version"] == SCHEMA
        else CachedContextModel.from_mapping(value["model"])
    )
    return model, Adam.from_mapping(value["optimizer"], model.parameter_count), value["state_id"]
