"""Bind optional actor scaling to passed, saved TRAIN-only representation controls."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_native import _private_path
from spireshift.engine_qualification import _sha_file
from spireshift.native_input_normalization import NONE, QUARTER, normalization_spec

CHECKS = {
    "all_sampled_vectors_recover_exactly",
    "critic_input_unchanged",
    "candidate_aliases_not_increased",
    "late_saturation_reduced_at_least_half",
    "held_conditional_accuracy_preserved",
    "normalized_held_conditional_signal",
    "negative_control_chance_only",
    "all_diagnostic_actors_changed",
}


def require_normalization_checks(root: Path, network: dict[str, Any], ref: object) -> str:
    mode = network.get("input_normalization", NONE)
    normalization_spec(mode)
    if mode == NONE:
        if ref is not None:
            raise ValueError("Unscaled actor cannot claim a normalization treatment")
        return NONE
    if not isinstance(ref, dict) or set(ref) != {"path", "id"}:
        raise ValueError("Normalized actor requires its separate passed representation checks")
    path = _private_path(root, ref["path"])
    report = json.loads(path.read_text())
    cfg = json.loads(path.with_name("config-at-launch.json").read_text())
    if (
        report.get("schema_version") != "native-input-normalization-checks-v1"
        or report.get("report_id") != ref["id"]
        or report["report_id"]
        != manifest_identifier({k: v for k, v in report.items() if k != "report_id"})
        or report.get("config_id") != manifest_identifier(cfg)
        or cfg.get("normalization") != QUARTER
        or report.get("normalization_control_pass") is not True
        or set(report.get("checks", {})) != CHECKS
        or any(v is not True for v in report["checks"].values())
        or report.get("training_runs_audited") != 256
        or report.get("probe_states", 0) < 100
        or report.get("confirmation_or_development_episodes_opened") != 0
        or report.get("games_launched") != 0
        or report.get("production_checkpoints_written") != 0
        or len(report.get("conditional_fit_runs", [])) != 8
        or len(report.get("conditional_held_runs", [])) < 4
        or set(report["conditional_fit_runs"]) & set(report["conditional_held_runs"])
    ):
        raise ValueError("Normalization checks are failed, incomplete or from another scope")
    for name, digest in report["sources"].items():
        if _sha_file(root / name) != digest:
            raise ValueError("Normalization control source evidence changed")
    for name, digest in cfg["implementation_sha256"].items():
        if _sha_file(root / "src/spireshift" / name) != digest:
            raise ValueError("Normalization implementation changed since its controls")
    return QUARTER
