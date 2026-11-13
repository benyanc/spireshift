"""Verify the exact fitted and original full states against the saved assessment."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_compatibility_contract import local, verified
from spireshift.native_structured_state import load as load_state
from spireshift.native_win7_inputs import frozen_checks
from spireshift.native_win7_inputs import load as load_native

FITTING_EVIDENCE = "docs/evidence/native-a8-world-balanced-fitting-result-v1.json"
FITTING_ID = "sha256:dd579215a6a25bb74a4e1436c6ffe628d3332bced89268ff2a0ea52b7842157c"
PLAYERS = (2, 3)


def load(root: Path) -> dict[str, Any]:
    ctx = load_native(root)
    evidence = identified(root / FITTING_EVIDENCE)
    assessment = identified(verified(root, evidence["assessment"]))
    if (
        evidence["report_id"] != FITTING_ID
        or evidence["environment_id"] != ctx["environment"]["manifest_id"]
        or evidence["status"] != "both_frozen_candidates_independently_verified"
        or assessment["report_id"] != evidence["assessment"]["report_id"]
        or assessment["status"] != "exact_update_200_candidates_and_offline_metrics_verified"
    ):
        raise ValueError("Use the exact assessed update-200 finals on their frozen host")
    finals = {}
    for player in PLAYERS:
        original = ctx["originals"][str(player)]
        final = evidence["candidates"][str(player)]
        saved = assessment["candidates"][str(player)]
        path = local(root, final["state_path"])
        if (
            _sha_file(path) != final["state_sha256"]
            or any(
                value != saved[key]
                for key, value in final.items()
                if key not in {"fit_diagnostics", "development_diagnostics"}
            )
            or final["initial_state_id"] != original["imported_state_id"]
            or final["initial_model_id"] != original["imported_model_id"]
            or final["initial_optimizer_steps"] != original["optimizer_steps"]
        ):
            raise ValueError("An assessed full state or its original changed")
        model, adam, state_id = load_state(path)
        if (
            state_id != final["state_id"]
            or model.model_id != final["model_id"]
            or manifest_identifier(adam.as_dict()) != final["optimizer_id"]
            or adam.steps != final["optimizer_steps"]
            or adam.steps != original["optimizer_steps"] + 200
        ):
            raise ValueError("Exact fitted weights and full Adam are required")
        finals[player] = model
    return {**ctx, "fitting_evidence": evidence, "finals": finals}


def freeze(root: Path, ctx: dict[str, Any]) -> dict[str, bool]:
    checks = frozen_checks(ctx)
    for final in ctx["fitting_evidence"]["candidates"].values():
        verified(root, {"path": final["state_path"], "sha256": final["state_sha256"]})
    for original in ctx["originals"].values():
        verified(root, {"path": original["imported_path"], "sha256": original["imported_sha256"]})
    return {**checks, "both_update_200_full_states_and_Adam_exact": True}
