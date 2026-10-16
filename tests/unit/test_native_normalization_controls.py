from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_engine_neural import public

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import activation_diagnostics
from spireshift.engine_neural import initial_actor, initialize_native_critic
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_ppo_math import Sample
from spireshift.native_input_normalization import NONE, QUARTER
from spireshift.native_normalization_admission import CHECKS, require_normalization_checks
from spireshift.native_normalization_checks import artificial_rest_examples


def test_artificial_hp_signal_and_negative_control_are_separate_from_game_labels() -> None:
    p = public("rest_site")
    p["context"]["player"]["max_hp"] = 80
    for c, label in zip(p["candidates"], ("Rest", "Smith"), strict=True):
        c["label"] = label
    anchor = {"public": p}
    data = artificial_rest_examples([anchor], QUARTER)
    negative = artificial_rest_examples([anchor], QUARTER, remove_hp_signal=True)
    assert data[0][0] != data[1][0] and data[0][1] != data[1][1]
    assert negative[0][0] == negative[1][0] and negative[0][1] != negative[1][1]
    assert p["context"]["player"]["hp"] == 20


def test_activation_probe_is_bounded_deterministic_and_does_not_mutate_weights() -> None:
    m = initialize_native_critic(initial_actor("sha256:" + "a" * 64, 128, 4))
    rows = ({0: 1.0, 30: 1.0}, {0: 1.0, 31: 1.0})
    samples = [Sample(rows, tuple([0.0] * 129), 0, -0.69, 0.1, 0.1)] * 200
    old = m.as_dict()
    a = activation_diagnostics(m, samples, 1)
    assert a == activation_diagnostics(m, samples, 1)
    assert a["states"] == 128 and a["candidate_rows"] == 256
    assert 0 <= a["mean_hidden_saturation"] <= 1 and m.as_dict() == old
    assert activation_diagnostics(m, [], 0)["states"] == 0


def make_control(root: Path, change: str | None = None) -> dict[str, str]:
    path = root / "artifacts/control/report.json"
    path.parent.mkdir(parents=True)
    source = root / "src/spireshift/native_input_normalization.py"
    source.parent.mkdir(parents=True)
    source.write_text("frozen synthetic normalization")
    cfg = {
        "normalization": QUARTER,
        "implementation_sha256": {"native_input_normalization.py": _sha_file(source)},
    }
    report: dict[str, Any] = {
        "schema_version": "native-input-normalization-checks-v1",
        "config_id": manifest_identifier(cfg),
        "normalization_control_pass": True,
        "checks": dict.fromkeys(CHECKS, True),
        "training_runs_audited": 256,
        "probe_states": 278,
        "confirmation_or_development_episodes_opened": 0,
        "games_launched": 0,
        "production_checkpoints_written": 0,
        "conditional_fit_runs": list(range(1, 9)),
        "conditional_held_runs": list(range(20, 24)),
        "sources": {},
    }
    if change == "failure":
        report["checks"]["negative_control_chance_only"] = False
    if change == "leak":
        report["conditional_held_runs"][0] = 1
    if change == "development":
        report["confirmation_or_development_episodes_opened"] = 1
    report["report_id"] = manifest_identifier(report)
    path.write_text(json.dumps(report))
    path.with_name("config-at-launch.json").write_text(json.dumps(cfg))
    if change == "code":
        source.write_text("changed normalization")
    return {"path": "artifacts/control/report.json", "id": report["report_id"]}


def test_scaling_requires_passed_checks_while_legacy_stays_explicit(tmp_path: Path) -> None:
    ref = make_control(tmp_path)
    assert require_normalization_checks(tmp_path, {}, None) == NONE
    assert require_normalization_checks(tmp_path, {"input_normalization": QUARTER}, ref) == QUARTER
    with pytest.raises(ValueError):
        require_normalization_checks(tmp_path, {}, ref)
    with pytest.raises(ValueError):
        require_normalization_checks(tmp_path, {"input_normalization": QUARTER}, None)


@pytest.mark.parametrize("change", ["failure", "leak", "development", "code"])
def test_failed_leaking_or_changed_controls_cannot_admit_scaling(
    tmp_path: Path, change: str
) -> None:
    ref = make_control(tmp_path, change)
    with pytest.raises(ValueError):
        require_normalization_checks(tmp_path, {"input_normalization": QUARTER}, ref)
