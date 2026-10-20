from __future__ import annotations

import copy
from typing import Any

import pytest
from test_native_action_context import model, score
from test_native_later_teacher import public

from spireshift.core.manifest import manifest_identifier
from spireshift.native_combat_teacher_data import CONTRACT, ReplayChooser
from spireshift.native_context_cache import cached_model
from spireshift.native_later_teacher_audit import reconstruct


def example() -> tuple[dict[str, Any], dict[str, Any]]:
    p = public()
    p["context"]["interaction"]["content"]["context"]["enemies"][0]["hp"] = 20
    prefix = copy.deepcopy(p)
    prefix["context"]["persistent"]["player"]["gold"] += 2
    r = {
        "root_id": "source-root",
        "native_seed": "SOURCE-WORLD",
        "public_input": p,
        "public_input_id": manifest_identifier(p),
        "prefix": [{"public_input_id": manifest_identifier(prefix), "action_index": 1}],
    }
    chooser = ReplayChooser(r, 0, 0, cached_model(model()), score(), 0.8)
    case = {
        "status": "terminal",
        "seed": r["native_seed"],
        "recovered": False,
        "privileged_fixture": False,
        "native_ending_evidence_agrees": True,
        "policy_contract": CONTRACT,
        "privileged_fixed_world_teacher": True,
        "ordinary_PPO_eligible": False,
        "decisions": [{"public_input": x, "choice": chooser(x)} for x in (prefix, p, p)],
    }
    return case, r


def test_saved_prefix_root_and_sampling_probabilities_reconstruct_without_games() -> None:
    case, root = example()
    before = copy.deepcopy(case)
    assert reconstruct(case, root, 0, 0, cached_model(model()), score(), 0.8) == 3
    assert case == before


@pytest.mark.parametrize("fault", ["action", "probability", "value", "PPO", "seed", "unreached"])
def test_false_teacher_bindings_choices_and_credit_are_refused(fault: str) -> None:
    case, root = example()
    if fault == "action":
        case["decisions"][1]["choice"]["action_index"] = 1
    elif fault == "probability":
        case["decisions"][2]["choice"]["log_probability"] += 0.01
    elif fault == "value":
        case["decisions"][2]["choice"]["value"] += 0.01
    elif fault == "PPO":
        case["ordinary_PPO_eligible"] = True
    elif fault == "seed":
        case["seed"] = "OTHER-WORLD"
    else:
        case["decisions"] = case["decisions"][:1]
    with pytest.raises(ValueError):
        reconstruct(case, root, 0, 0, cached_model(model()), score(), 0.8)
