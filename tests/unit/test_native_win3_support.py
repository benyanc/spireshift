from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from spireshift.engine_qualification import _sha_file
from spireshift.native_win3_inputs import AUDIT_SOURCE, binding, validate, verify_audit_sources
from spireshift.native_win3_recovery import continuation_plan
from spireshift.native_win3_session import inspect_resume

ROOT = Path(__file__).resolve().parents[2]


def config() -> tuple[dict[str, Any], dict[str, Any]]:
    old = dict(
        json.loads(
            (ROOT / "configs/native-curriculum/sts2-v0.111.0-a8-win-curriculum-v2.json").read_text()
        )
    )
    new = {
        **copy.deepcopy(old),
        "schema_version": "native-win-curriculum-config-v3",
        "workspace": "artifacts/native-win-curriculum/study-v3",
        "plan": continuation_plan(old),
        "historical_incomplete_cases": 2,
        "reused_original_cases": 30,
        "support_control_generation": 1,
    }
    return new, old


def test_only_runtime_error_world_changes_and_both_failures_stay_counted() -> None:
    cfg, old = config()
    before = copy.deepcopy(old)
    validate(cfg, old)
    assert old == before
    assert cfg["plan"]["fit"][:30] == old["plan"]["fit"][:30]
    assert cfg["plan"]["fit"][31:] == old["plan"]["fit"][31:]
    assert cfg["plan"]["heldout"] == old["plan"]["heldout"]
    assert cfg["plan"]["quality"] == old["plan"]["quality"]
    assert cfg["plan"]["fit"][30]["key"] == "fit-031-replacement-1"
    previous = {
        s for case in old["plan"]["fit"] + old["plan"]["heldout"] for s in case["seed_pool"]
    }
    assert previous.isdisjoint(cfg["plan"]["fit"][30]["seed_pool"])
    assert (
        len(cfg["plan"]["fit"]) + len(cfg["plan"]["heldout"]) + cfg["historical_incomplete_cases"]
        == 70
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("main_optimizer_updates", 1),
        ("ordinary_PPO_allowed", True),
        ("promotion_allowed", True),
        ("automatic_follow_up", True),
        ("historical_incomplete_cases", 1),
        ("official_live_qualification_inherited", True),
        ("support_control_generation", 0),
    ],
)
def test_support_recipe_cannot_grant_training_or_erase_failures(field: str, value: Any) -> None:
    cfg, old = config()
    cfg[field] = value
    with pytest.raises(ValueError):
        validate(cfg, old)


def test_receipt_binding_includes_support_version_but_not_its_own_receipt() -> None:
    cfg, _ = config()
    before = binding(cfg)
    cfg["support_control"] = {"report": "receipt"}
    assert binding(cfg) == before
    cfg["support_build"] = {"sha256": "changed"}
    assert binding(cfg) != before


def test_audit_archive_must_be_the_exact_original_source_and_cannot_hide_other_drift(
    tmp_path: Path,
) -> None:
    archived = tmp_path / "audit-source.py"
    archived.write_text("original audit source\n")
    other = tmp_path / "original.py"
    other.write_text("unchanged\n")
    ref = {"path": "audit-source.py", "sha256": _sha_file(archived)}
    report = {
        "sources": {AUDIT_SOURCE: ref["sha256"], "original.py": _sha_file(other)},
        "evidence": {},
    }
    verify_audit_sources(tmp_path, report, ref)
    other.write_text("modified\n")
    with pytest.raises(ValueError):
        verify_audit_sources(tmp_path, report, ref)
    other.write_text("unchanged\n")
    report["sources"][AUDIT_SOURCE] = "wrong"
    with pytest.raises(ValueError, match="archive differs"):
        verify_audit_sources(tmp_path, report, ref)


@pytest.mark.parametrize("version", [1, 2])
def test_interrupted_ancestors_stay_blocked_without_marker_mutation(
    version: int, tmp_path: Path
) -> None:
    cfg = {"workspace": f"artifacts/native-win-curriculum/study-v{version}"}
    base = tmp_path / cfg["workspace"]
    chunk = base / "chunks/failed-case"
    chunk.mkdir(parents=True)
    (base / "config-at-launch.json").write_text(json.dumps(cfg))
    (chunk / "active.json").write_text("preserved\n")
    with pytest.raises(FileExistsError):
        inspect_resume({"qualification": SimpleNamespace(root=tmp_path), "config": cfg})
    assert (chunk / "active.json").read_text() == "preserved\n"
