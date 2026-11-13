from __future__ import annotations

import copy
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_native_action_context import model, score

import spireshift.engine_runtime_gaps as gaps
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _sha_file
from spireshift.native_action_context import policy
from spireshift.native_learning_control import TASKS, public_input


def test_new_grid_size_is_supported_by_the_existing_public_policy() -> None:
    p = public_input(TASKS[0], True)
    original = p["candidates"][0]
    p["candidates"] = [
        {**copy.deepcopy(original), "label": f"{tool} at ({x},{y})"}
        for tool in ("Small", "Big")
        for x in range(11)
        for y in range(11)
    ]
    rows, _, logs = policy(p, model(), score(), 0.8)
    assert len(rows) == len(logs) == 242
    assert all(math.isfinite(logp) for logp in logs)
    assert sum(math.exp(logp) for logp in logs) == pytest.approx(1.0)


def setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, ...]:
    inputs = []
    for version in ("old", "new"):
        root = tmp_path / version
        for n in (*gaps.CHANGED, "src/Other/Rules.cs"):
            p = root / n
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(version if n in gaps.CHANGED else "unchanged native semantics")
        inputs.append(
            {
                "candidate": root,
                "recipe": {"version": version},
                "build": {"runtime_sts2_sha256": "same native game"},
                "archive": "same archive",
                "objective": {"primary": "terminal victory"},
                "runtime": "same runtime",
                "projection": {"public": "same encoder"},
                "localization": "same localization",
            }
        )
    cfg: dict[str, Any] = {
        f"{v}_run": {"path": v, "id": manifest_identifier(inputs[i]["recipe"])}
        for i, v in enumerate(("old", "new"))
    }
    cfg["native_source_delta"] = {
        n: {v: _sha_file(tmp_path / v / n) for v in ("old", "new")} for n in gaps.CHANGED
    }
    monkeypatch.setattr(gaps, "_run_inputs", lambda _, p: inputs[int(p.name == "new")])
    return SimpleNamespace(root=tmp_path), cfg, inputs


def test_reviewed_source_delta_keeps_game_projection_and_objective_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    q, cfg, inputs = setup(tmp_path, monkeypatch)
    assert gaps.repair_inputs(q, cfg) == inputs[1]


@pytest.mark.parametrize(
    "fault", ["game", "projection", "objective", "extra_source", "changed_delta"]
)
def test_mechanics_transfer_rejects_unreviewed_rules_or_implementation_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    q, cfg, inputs = setup(tmp_path, monkeypatch)
    if fault == "game":
        inputs[1]["build"]["runtime_sts2_sha256"] = "changed game"
    elif fault in {"projection", "objective"}:
        inputs[1][fault] = {"changed": True}
    elif fault == "extra_source":
        (tmp_path / "new/src/Other/Rules.cs").write_text("Unreviewed replacement rules")
    else:
        cfg["native_source_delta"]["src/GodotStubs/Math.cs"]["new"] = "wrong hash"
    with pytest.raises(ValueError):
        gaps.repair_inputs(q, cfg)
