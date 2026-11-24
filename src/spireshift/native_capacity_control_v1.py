"""Check equal initial choices and exact native trajectories before capacity learning."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, cast

from spireshift import native_a8_own_experience as learner
from spireshift.engine_learning import identified
from spireshift.full_run_policy import score_features
from spireshift.full_run_ppo_math import log_softmax
from spireshift.native_a8_head_policy import HeadChooser
from spireshift.native_combat_intent_model import encode, using_intent_encoder
from spireshift.native_flow_verification_v12 import records
from spireshift.native_qualified_learning_inputs_v1 import MIXED


def saved_menus(
    root: Path, cfg: dict[str, Any], states: dict[str, Any], score: Any
) -> dict[str, Any]:
    mixed = json.loads((root / MIXED).read_text())
    proof = identified(root / cfg["mixed_assessment"]["path"])
    comparisons = seen = 0
    maximum_error = 0.0
    with using_intent_encoder():
        for row in proof["pairs"]:
            key = row["key"]
            area = root / mixed["workspace"] / "native" / key
            if not area.exists():
                area = (root / mixed["parent_result"]["path"]).parent / "native" / key
            choosers = {
                m: {
                    p: HeadChooser(states[m][p][0].model, score, f"capacity-{key}-p{p}")
                    for p in (2, 3)
                }
                for m in ("standard", "expanded")
            }
            for frame in records(area / "frames.jsonl.gz"):
                public = frame["public_input"]
                seen += 1
                for p in (2, 3):
                    views = {}
                    choices = {}
                    for method in ("standard", "expanded"):
                        model = states[method][p][0].model
                        rows, value = encode(public, model, score)
                        if learner.__dict__["encode"](public, model, score) != (rows, value):
                            raise ValueError("Inference and actual PPO reconstruction differ")
                        chooser = choosers[method][p]
                        choices[method] = chooser(public)
                        if chooser.last is None or chooser.last[:2] != (rows, value):
                            raise ValueError(
                                "The native chooser dropped its exact full-menu encoding"
                            )
                        logs = log_softmax(score_features(cast(Any, model.actor), rows), 0.8)
                        views[method] = rows, value, logs, model.value(value)
                    a, b = views["standard"], views["expanded"]
                    error = max(abs(x - y) for x, y in zip(a[2], b[2], strict=True))
                    maximum_error = max(maximum_error, error)
                    if (
                        a[:2] != b[:2]
                        or error > 1e-12
                        or a[3] != b[3]
                        or choices["standard"]["action_index"]
                        != choices["expanded"]["action_index"]
                        or choices["standard"]["draw"] != choices["expanded"]["draw"]
                    ):
                        raise ValueError(
                            "The wider copy changed a starting input, choice, likelihood or critic"
                        )
                    comparisons += 1
    if seen != 114 or comparisons != 228:
        raise ValueError("Require both initializers on every qualified mixed menu")
    return {
        "public_states": seen,
        "paired_policy_comparisons": comparisons,
        "maximum_log_probability_error": maximum_error,
        "fixture_choices_used_as_labels": False,
        "gameplay_deliveries": 0,
        "optimizer_updates": 0,
    }


def same_initial_games(left: Path, right: Path) -> dict[str, Any]:
    count = choices = 0
    for a, b in zip(
        records(left / "shared-public.jsonl.gz"),
        records(right / "shared-public.jsonl.gz"),
        strict=True,
    ):
        if a["kind"] != b["kind"]:
            raise ValueError("Initially equivalent policies produced different native trajectories")
        if a["kind"] in {"policy_input", "final_observation"}:
            if a["frame"]["public_input"] != b["frame"]["public_input"]:
                raise ValueError(
                    "Initially equivalent policies received different canonical public states"
                )
            count += 1
        else:
            for key in ("action_index", "draw_key", "draw"):
                if a["choice"][key] != b["choice"][key]:
                    raise ValueError(
                        "Initially equivalent policies delivered different model-owned choices"
                    )
            if not math.isclose(
                a["choice"]["log_probability"],
                b["choice"]["log_probability"],
                rel_tol=0,
                abs_tol=1e-10,
            ):
                raise ValueError("The initial native likelihood differs between model widths")
            choices += 1
    return {"matching_public_states": count, "matching_model_choices": choices}
