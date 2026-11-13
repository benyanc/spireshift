from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from test_native_action_context import model, score
from test_native_structured_model import columns, public
from test_native_structured_trial import config, seeds

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import save_native_episode
from spireshift.full_run_ppo_math import Adam
from spireshift.native_context_cache import cached_model
from spireshift.native_structured_inputs import exclude_worlds, validate_worlds
from spireshift.native_structured_model import extend
from spireshift.native_structured_policy import CONTRACT, Chooser, reconstruct
from spireshift.native_structured_training import prepare


@pytest.mark.parametrize(
    "fault",
    [
        "duplicate_id",
        "duplicate_world",
        "wrong_partition",
        "noncanonical",
        "extra_field",
        "environment",
    ],
)
def test_fresh_worlds_have_exact_independent_seed_and_partition_ownership(fault: str) -> None:
    rows = seeds()
    manifest = {
        "schema_version": "native-structured-comparison-seeds-v1",
        "environment_id": "env",
        "seeds": rows,
    }
    assert validate_worlds(config(), manifest, "env") == rows
    if fault == "duplicate_id":
        rows[1]["id"] = rows[0]["id"]
    if fault == "duplicate_world":
        rows[1]["seed"] = rows[0]["seed"]
    if fault == "wrong_partition":
        rows[0]["partition"] = "development"
    if fault == "noncanonical":
        rows[0]["seed"] = "SEEDWITHI"
    if fault == "extra_field":
        rows[0]["hidden"] = 1
    if fault == "environment":
        manifest["environment_id"] = "other"
    with pytest.raises(ValueError):
        validate_worlds(config(), manifest, "env")


def test_canonical_aliases_and_old_logical_ids_are_excluded() -> None:
    rows = seeds()
    exclude_worlds(rows, [{"id": 99, "seed": "AN0THER"}])
    with pytest.raises(ValueError, match="reuse"):
        exclude_worlds(
            rows, [{"id": 99, "seed": rows[0]["seed"].replace("0", "O").replace("1", "I")}]
        )
    with pytest.raises(ValueError, match="reuse"):
        exclude_worlds(rows, [{"id": rows[0]["id"], "seed": "AN0THER"}])


def episodes(root: Path) -> tuple[list[Path], Any, Any, dict[str, Any], list[dict[str, Any]]]:
    parent = cached_model(model())
    m, _ = extend(parent, Adam.zero(parent.parameter_count), columns(public()), "named")
    cfg = {
        **config(),
        "seed_manifest": {"id": "manifest"},
        "credit": {
            "baseline": "public_residual_ridge",
            "regularization": 0.001,
            "folds": 2,
            "fold_salt": "test",
        },
    }
    rows = seeds()[:2]
    paths = []
    for row in rows:
        p = public()
        chosen = Chooser(m, score(), row["seed"], True)(p)
        case = {
            "seed": row["seed"],
            "status": "terminal",
            "victory": False,
            "maximum_floor": 4 + row["id"],
            "completed_acts": 0,
            "cpu_seconds": 0.1,
            "native_ending_evidence_agrees": True,
            "privileged_fixture": False,
            "privileged_fixed_world_teacher": False,
            "recovered": False,
            "ordinary_PPO_eligible": True,
            "policy_contract": CONTRACT,
            "decisions": [{"public_input": p, "choice": chosen}],
        }
        bound = {
            "config_id": manifest_identifier(cfg),
            "seed_manifest_id": "manifest",
            "seed_id": row["id"],
            "native_seed": row["seed"],
            "partition": "train",
            "panel_purpose": "training",
            "model_id": m.model_id,
            "environment_id": m.actor.environment_id,
            "training_spec_id": score().spec_id,
            "policy_contract": CONTRACT,
        }
        path = root / f"game-{row['id']}.json"
        save_native_episode(path, case, bound)
        paths.append(path)
    return paths, m, score(), cfg, rows


def test_own_sampled_games_receive_whole_game_credit_without_new_health_rewards(
    tmp_path: Path,
) -> None:
    paths, m, s, cfg, rows = episodes(tmp_path)
    samples, report = prepare(paths, m, s, cfg, rows, 1)
    assert len(samples) == 2 and report["clean_complete_training_games"] == 2
    assert report["credit_predictor_unchanged"] and report["oracle_labels"] == 0
    assert not report["hand_written_HP_rewards"]
    assert report["discount"] == report["trace_lambda"] == 1
    assert all(set(f["fitting_runs"]).isdisjoint(f["predicted_runs"]) for f in report["cross_fit"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("model_id", "other"),
        ("partition", "development"),
        ("config_id", "other"),
        ("seed_manifest_id", "other"),
        ("native_seed", "OTHER"),
    ],
)
def test_stale_foreign_or_development_records_are_rejected_before_fitting(
    tmp_path: Path, field: str, value: str
) -> None:
    paths, m, s, cfg, rows = episodes(tmp_path)
    doc = json.loads(paths[0].read_text())
    doc["binding"][field] = value
    paths[0].write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="Reject"):
        prepare(paths, m, s, cfg, rows, 1)


def test_replay_rejects_changed_probability_and_privileged_or_recovered_cases() -> None:
    parent = cached_model(model())
    p = public()
    chosen = Chooser(parent, score(), "CAN0N1CAL", True)(p)
    case: dict[str, Any] = {
        "status": "terminal",
        "policy_contract": CONTRACT,
        "privileged_fixture": False,
        "ordinary_PPO_eligible": True,
        "recovered": False,
        "decisions": [{"public_input": p, "choice": chosen}],
    }
    assert len(reconstruct(case, parent, score(), "CAN0N1CAL", True, 0.2)[0]) == 1
    changed = copy.deepcopy(case)
    changed["decisions"][0]["choice"]["log_probability"] += 0.1
    with pytest.raises(ValueError, match="changed"):
        reconstruct(changed, parent, score(), "CAN0N1CAL", True, 0.2)
    for field in ("privileged_fixture", "recovered"):
        with pytest.raises(ValueError, match="public-only"):
            reconstruct({**case, field: True}, parent, score(), "CAN0N1CAL", True, 0.2)
