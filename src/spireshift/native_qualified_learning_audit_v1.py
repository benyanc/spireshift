"""Check inference/reconstruction on qualified menus without delivering their choices."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, cast

from spireshift import native_a8_own_experience as learner
from spireshift.engine_learning import identified
from spireshift.full_run_policy import score_features
from spireshift.full_run_ppo_math import log_softmax
from spireshift.native_a8_head_policy import HeadChooser, HeadState
from spireshift.native_combat_intent_model import encode, using_intent_encoder
from spireshift.native_flow_verification_v12 import records
from spireshift.training_objective import TrainingScoreSpec


def saved_menus(
    root: Path,
    cfg: dict[str, Any],
    states: dict[int, tuple[HeadState, str]],
    score: TrainingScoreSpec,
) -> dict[str, Any]:
    from spireshift.native_qualified_learning_inputs_v1 import MIXED

    mixed = json.loads((root / MIXED).read_text())
    proof = identified(root / cfg["mixed_assessment"]["path"])
    comparisons = states_seen = 0
    with using_intent_encoder():
        for row in proof["pairs"]:
            key = row["key"]
            area = root / mixed["workspace"] / "native" / key
            if not area.exists():
                area = (root / mixed["parent_result"]["path"]).parent / "native" / key
            choosers = {
                p: HeadChooser(saved[0].model, score, f"saved-{key}-p{p}")
                for p, saved in states.items()
            }
            for frame in records(area / "frames.jsonl.gz"):
                public = frame["public_input"]
                states_seen += 1
                for p, (state, _) in states.items():
                    rows, value = encode(public, state.model, score)
                    # Inspect the actual callback patched into PPO reconstruction.
                    rebuilt = learner.__dict__["encode"](public, state.model, score)
                    chooser = choosers[p]
                    chosen = chooser(public)
                    if (
                        rebuilt != (rows, value)
                        or chooser.last is None
                        or chooser.last[:2] != (rows, value)
                        or chooser.last[2] != public
                        or chooser.last[3] is not False
                        or len(rows) != len(public["candidates"])
                        or chosen["draw_used"] is not True
                        or chosen["navigation_only"] is not False
                        or chosen["effective_action_index"] != chosen["action_index"]
                    ):
                        raise ValueError(
                            "Inference and learner must use the same complete current menu"
                        )
                    logs = log_softmax(
                        score_features(cast(Any, state.model.actor), rows),
                        cfg["settings"]["temperature"],
                    )
                    if not math.isclose(
                        logs[chosen["action_index"]], chosen["log_probability"], abs_tol=1e-10
                    ):
                        raise ValueError(
                            "The behavior likelihood differs from its PPO reconstruction"
                        )
                    comparisons += 1
    if states_seen != 114 or comparisons != 228:
        raise ValueError("Require both model copies on every qualified mixed-menu state")
    return {
        "qualified_public_states": states_seen,
        "model_input_comparisons": comparisons,
        "games_launched": 0,
        "gameplay_deliveries": 0,
        "optimizer_updates": 0,
        "fixture_choices_used_as_labels": False,
    }
