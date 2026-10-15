from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from spireshift.engine_coverage import (
    TARGETS,
    _read_sealed,
    _sealed,
    coverage_summary,
    generate_plan,
)
from spireshift.full_run_experience import atomic_json


def inventory() -> tuple[dict[str, Any], dict[str, Any]]:
    names = ["Foreign", "Token", "Mock", "Unknown", "Relic"]
    registry = {
        "registry_id": "registry",
        "models": [
            {"type": name, "family": "Cards" if name != "Relic" else "Relics"} for name in names
        ],
    }
    catalog = {
        "report_id": "catalog",
        "target_types": list(TARGETS),
        "models": [
            {
                "class": name,
                "id": f"CARD.{name.upper()}",
                "metadata_complete": name != "Unknown",
                "is_mock": name == "Mock",
                "pool_is_mock": False,
                "maximum_upgrade": 1,
                "in_native_card_pool": name != "Token",
            }
            for name in names
        ],
    }
    return catalog, registry


def test_generated_plan_covers_foreign_and_token_cards_and_preserves_noncard_gaps() -> None:
    catalog, registry = inventory()
    plan = generate_plan(catalog, registry)
    generated = [c for c in plan["cases"] if c["kind"] == "generated_card"]
    assert len(generated) == 6
    assert {c["fixture"]["card_id"] for c in generated} == {"FOREIGN", "TOKEN"}
    assert {tuple((c["fixture"]["upgrade"], c["fixture"]["funded"])) for c in generated} == {
        (0, False),
        (0, True),
        (1, True),
    }
    assert {m["status"] for m in plan["models"]} >= {
        "metadata_incomplete",
        "inventoried_only",
        "native_mock_excluded",
    }
    assert plan["training_allowed"] is False
    assert plan["all_interactions_proven"] is False


def test_new_runtime_types_targets_and_missing_registered_classes_are_visible() -> None:
    catalog, registry = inventory()
    catalog["models"].pop()
    catalog["target_types"].append("NewTarget")
    plan = generate_plan(catalog, registry)
    assert plan["runtime_missing_classes"] == ["Relic"]
    assert plan["unknown_target_types"] == ["NewTarget"]
    assert plan["target_types"]["NewTarget"] == "unsupported_unknown"
    catalog["models"].append(copy.deepcopy(catalog["models"][0]))
    with pytest.raises(ValueError, match="Duplicate"):
        generate_plan(catalog, registry)


def test_blocked_effect_is_not_a_pass_and_smoke_does_not_admit_training() -> None:
    catalog, registry = inventory()
    plan = generate_plan(catalog, registry)
    result = {
        "spec": {"case_id": "cold-snap", "kind": "named_regression"},
        "status": "required_effect_not_exercised",
        "error": "Prerequisite",
    }
    report = coverage_summary(plan, [result], 6)
    assert report["not_attempted_cases"] == 5
    assert report["known_gaps"][0]["case_id"] == "cold-snap"
    assert report["requirements"]["foreign_orbs"]["status"] == "unverified"
    assert report["training_allowed"] is False
    result["status"] = "effect_exercised"
    report = coverage_summary(plan, [result], 6)
    assert report["requirements"]["foreign_orbs"]["status"] == "exercised_native_diagnostic"
    assert report["requirements"]["non_creature_potion_target"]["status"] == "unsupported"
    assert report["shipped_cross_host_parity"] is False


def test_saved_evidence_is_not_silently_accepted_after_changes(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    atomic_json(path, _sealed({"cases": 1, "training_allowed": False}))
    assert _read_sealed(path)["cases"] == 1
    text = path.read_text().replace('"cases": 1', '"cases": 2')
    path.write_text(text)
    with pytest.raises(ValueError, match="identity changed"):
        _read_sealed(path)


def test_names_do_not_exclude_foreign_or_mock_named_real_cards() -> None:
    catalog, registry = inventory()
    catalog["models"][2]["is_mock"] = False
    plan = generate_plan(catalog, registry)
    assert any(c.get("model_class") == "Mock" for c in plan["cases"])
    catalog["models"][0]["maximum_upgrade"] = 2_147_483_647
    plan = generate_plan(catalog, registry)
    assert max(c["fixture"]["upgrade"] for c in plan["cases"]) == 1
    assert plan["unbounded_upgrade_combinations_exhausted"] is False


def test_generated_observations_are_separate_from_effect_coverage() -> None:
    catalog, registry = inventory()
    for row in catalog["models"]:
        row["metadata_complete"] = True
    plan = generate_plan(catalog, registry)
    results = [
        {"spec": case, "status": "observed_prerequisite_blocked"}
        for case in plan["cases"]
        if case["kind"] == "generated_card"
    ]
    report = coverage_summary(plan, results, len(plan["cases"]))
    assert (
        report["requirements"]["all_pool_current_card_facts"]["status"]
        == "observed_all_planned_contexts"
    )
    assert report["requirements"]["foreign_orbs"]["status"] == "unverified"
    assert report["all_interactions_proven"] is False
    assert report["training_allowed"] is False


def test_saved_case_reuse_requires_same_plan_spec_and_trace_bytes(tmp_path: Path) -> None:
    from spireshift.engine_coverage import _saved_case
    from spireshift.engine_qualification import _sha_file

    trace = tmp_path / "public.jsonl"
    trace.write_text("original")
    spec = {"case_id": "one"}
    record = _sealed(
        {
            "spec": spec,
            "plan_id": "plan",
            "evidence_files": [{"path": "public.jsonl", "sha256": _sha_file(trace)}],
        }
    )
    output = tmp_path / "result.json"
    atomic_json(output, record)
    assert _saved_case(output, spec, "plan") == record
    with pytest.raises(ValueError, match="another plan"):
        _saved_case(output, spec, "other")
    trace.write_text("changed")
    with pytest.raises(ValueError, match="trace changed"):
        _saved_case(output, spec, "plan")


def test_new_all_pool_learning_requires_explicit_coverage_even_after_a_smoke() -> None:
    from types import SimpleNamespace

    from spireshift.engine_coverage import require_mechanics_coverage

    q = SimpleNamespace(root=Path("/unused"))
    with pytest.raises(ValueError, match="frozen mechanics coverage gate"):
        require_mechanics_coverage(q, {"inputs": {"combat_surface_revision": "v3"}}, None)  # type: ignore[arg-type]
    # Historical contracts keep their own original gates and are not retroactively relabelled.
    require_mechanics_coverage(q, {"inputs": {"combat_surface_revision": "v2"}}, None)  # type: ignore[arg-type]
