"""Resolve an immutable situation to original public inputs and separate replay metadata.

No native process starts. Recorded-seed prefix references are not qualified native
replays, optimal-action labels, fresh PPO episodes or public-belief counterfactuals.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_context_reuse import check_sources
from spireshift.native_shop_policy import ShopNavigation
from spireshift.native_situation_bank import extract_case, prefix_next, prefix_start


def resolve(root: Path, report_path: Path, situation_id: str) -> dict[str, Any]:
    """Reconstruct the exact historical menu; never infer missing legacy facts."""
    report = identified(report_path)
    if report["status"] != "native_situation_bank_complete":
        raise ValueError("Only a complete sealed bank can resolve a situation")
    path = report_path.parent / "bank.json"
    if report["sources"].get(str(path.relative_to(root))) != _sha_file(path):
        raise ValueError("The situation bank bytes changed")
    bank = identified(path, "bank_id")
    if bank["config_id"] != report["config_id"] or bank["bank_id"] != report["summary"]["bank_id"]:
        raise ValueError("The bank and its completion report disagree")
    matches = [r for r in bank["situations"] if r["situation_id"] == situation_id]
    if len(matches) != 1:
        raise ValueError("Require exactly one named bank situation")
    row = matches[0]
    if (
        row["situation_id"]
        != manifest_identifier({k: v for k, v in row.items() if k != "situation_id"})
        or bank["world_splits"][row["world"]] != row["split"]
    ):
        raise ValueError("Situation identity or whole-world split differs")
    episode_path = root / row["source_ref"]
    trace_name = str(episode_path.with_suffix(".jsonl.gz").relative_to(root))
    refs = (row["source_ref"], trace_name)
    check_sources(root, {name: report["sources"][name] for name in refs})
    # Native episode headers have a trace hash outside their case identity.
    header = json.loads(episode_path.read_text())
    binding = header["binding"]
    if (
        header["case_id"] != row["case_id"]
        or binding["partition"] != "train"
        or binding["panel_purpose"] != "training"
        or binding["native_seed"] != row["world"]
        or binding["seed_id"] != row["seed_id"]
        or binding["model_id"] != row["model_id"]
        or binding["config_id"] != bank["source_config_id"]
        or binding["environment_id"] != bank["source_environment"]["id"]
        or binding["seed_manifest_id"] != bank["source_seed_manifest"]["id"]
        or binding["training_spec_id"] != bank["training_spec"]["id"]
    ):
        raise ValueError("Situation replay provenance differs from its source TRAIN game")
    case = read_native_episode(episode_path, binding)
    rows, _ = extract_case(case, row, header["case_id"], time.monotonic() + 30)
    reproduced = next((r for r in rows if r["decision_index"] == row["decision_index"]), None)
    if reproduced != {k: v for k, v in row.items() if k not in {"situation_id", "split"}}:
        raise ValueError("The selected public situation or prefix does not reconstruct")
    navigation, prefix, actions = ShopNavigation(), prefix_start(), []
    for decision in case["decisions"][: row["decision_index"]]:
        public, chosen = decision["public_input"], decision["choice"]["action_index"]
        prefix = prefix_next(prefix, manifest_identifier(public), chosen)
        actions.append(chosen)
        navigation.advance(public, chosen)
    public = case["decisions"][row["decision_index"]]["public_input"]
    effective, indices, forced = navigation.view(public)
    if (
        forced
        or indices != row["effective_candidate_indices"]
        or prefix != row["replay_prefix_sha256"]
    ):
        raise ValueError("The root is not its advertised strategic choice")
    check_sources(root, {name: report["sources"][name] for name in refs})
    return {
        "student_input": public,
        "effective_student_input": effective,
        "provenance": {
            "situation_id": situation_id,
            "bank_id": bank["bank_id"],
            "split": row["split"],
            "description": row["description"],
            "source_environment": bank["source_environment"],
            "source_ref": row["source_ref"],
            "case_id": row["case_id"],
        },
        "replay_metadata_not_student_input": {
            "native_seed": row["world"],
            "action_indices_before_root": actions,
            "prefix_sha256": prefix,
            "root_action_label": None,
            "native_replay_qualified": False,
            "replay_scope": "exact_recorded_seed_prefix_not_public_belief",
        },
        "ordinary_PPO_eligible": False,
        "games_launched": 0,
        "optimizer_updates": 0,
    }
