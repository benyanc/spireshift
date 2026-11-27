from __future__ import annotations

import copy
import gzip
import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_neural import INPUT_SCHEMA
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_flow_inputs_v12 import canonical_seed
from spireshift.native_win_bank import coverage, lesson, matching_confirmation, select
from spireshift.native_win_game import check_start, terminal
from spireshift.native_win_inputs import binding, validate
from spireshift.native_win_plan import (
    ACTS,
    CONTRACT,
    REQUIRED_FAMILIES,
    cases,
    plan,
    profile,
    start_cases,
)
from spireshift.native_win_session import inspect_resume
from spireshift.native_win_study import CleanPause, unit
from spireshift.native_win_teacher import TeacherPolicy, score_action


def config() -> dict[str, Any]:
    return {
        "schema_version": "native-win-curriculum-config-v1",
        "contract": CONTRACT,
        "operation": "collect_training_only_curriculum_then_stop",
        "plan": plan(),
        "workspace": "artifacts/native-win-curriculum/study-v1",
        "control_generation": 1,
        "ordinary_PPO_allowed": False,
        "native_development_only": True,
        "main_optimizer_updates": 0,
        "official_live_qualification_inherited": False,
        "promotion_allowed": False,
        "automatic_follow_up": False,
        "session_limits": {
            "wall_seconds": 5400,
            "cpu_seconds": 14400,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 4000000000,
        },
    }


def public(*, damage: int = 8, hp: int = 20) -> dict[str, Any]:
    return {
        "schema_version": INPUT_SCHEMA,
        "context": {
            "persistent": {"player": {"hp": hp, "max_hp": 80}},
            "interaction": {
                "kind": "combat_turn",
                "content": {
                    "context": {
                        "player": {"block": 0, "energy": 3},
                        "round": 1,
                        "enemies": [{"intents": [{"damage": damage}]}],
                    },
                    "surface": {},
                },
            },
        },
        "candidates": [
            {"verb": "end_turn", "subject": None, "arguments": []},
            {
                "verb": "play",
                "subject": {
                    "properties": {"definition_id": "DEFEND_IRONCLAD", "stats": {"block": 8}}
                },
                "arguments": [],
            },
        ],
    }


def test_declared_partitions_cover_acts_bosses_and_all_game_decisions() -> None:
    cfg = config()
    validate(cfg)
    assert len(cfg["plan"]["fit"]) == 56
    assert len(cfg["plan"]["heldout"]) == 12
    fitting = cfg["plan"]["fit"]
    assert {c["act_definition"] for c in fitting if c["entry"] != "natural"} == set(ACTS)
    assert {c["boss"] for c in fitting if c["entry"] == "boss"} == {
        b for _, bs in ACTS.values() for b in bs
    }

    assert {c["entry"] for c in fitting} == {
        "boss",
        "act_start",
        "preboss",
        "shop",
        "event",
        "treasure",
        "natural",
    }


def test_teacher_builds_retained_block_before_body_slam() -> None:
    p = public(damage=10)
    player = p["context"]["interaction"]["content"]["context"]["player"]
    player["block"] = 40
    player["statuses"] = [{"definition_id": "BARRICADE_POWER", "amount": 1}]
    p["candidates"] = [
        {
            "verb": "play",
            "subject": {"properties": {"definition_id": ident, "stats": stats}},
            "arguments": [],
        }
        for ident, stats in [("ENTRENCH", {}), ("BODY_SLAM", {"damage": 40})]
    ]
    assert score_action(p, 0, "scaling") > score_action(p, 1, "scaling")


def test_teacher_does_not_reopen_a_publicly_declined_card_reward() -> None:
    p = public()
    p["context"]["interaction"]["kind"] = "reward_claim"
    p["candidates"] = [
        {
            "verb": "activate",
            "subject": {"properties": {"kind": "card", "enabled": True}},
            "history": {"card_reward_declined": True},
        },
        {"verb": "activate", "subject": None},
    ]
    assert score_action(p, 1, "balanced") > score_action(p, 0, "balanced")


def test_final_boss_training_goal_requires_exact_native_completed_boss_owner() -> None:
    p = public()
    p["context"]["persistent"]["run"] = {"act": 3}
    p["context"]["interaction"] = {
        "kind": "reward_claim",
        "content": {"context": {"completed_boss_combat": True}},
    }
    frame = {"terminal": False, "public_input": p}
    start = {"kind": "prepared_training_only", "scenario": {"act": 3}}
    assert terminal(frame, start) == (True, True)
    assert terminal(frame, {"kind": "natural_training"}) == (False, False)
    p["context"]["interaction"]["content"]["context"]["completed_boss_combat"] = False
    assert terminal(frame, start) == (False, False)


def test_all_main_control_preparation_pools_and_evaluation_worlds_are_disjoint() -> None:
    groups = [
        cases("fit"),
        cases("heldout"),
        cases("control_fit", control=True),
        cases("control_heldout", control=True),
        start_cases(),
    ]
    seeds = [s for group in groups for c in group for s in c["seed_pool"]]
    seeds += plan()["reserved_evaluation_seeds"]
    assert len(seeds) == len(set(seeds))
    assert all(canonical_seed(s) == s for s in seeds)
    assert {s for c in start_cases(2) for s in c["seed_pool"]}.isdisjoint(seeds)


@pytest.mark.parametrize(
    "field,value",
    [
        ("ordinary_PPO_allowed", True),
        ("native_development_only", False),
        ("main_optimizer_updates", 1),
        ("official_live_qualification_inherited", True),
        ("promotion_allowed", True),
        ("automatic_follow_up", True),
        ("control_generation", 0),
    ],
)
def test_recipe_cannot_silently_admit_training_or_inherit_old_live_scope(
    field: str, value: Any
) -> None:
    cfg = config()
    cfg[field] = value
    with pytest.raises(ValueError):
        validate(cfg)


def test_short_receipt_can_be_attached_without_changing_its_binding() -> None:
    cfg = config()
    initial = binding(cfg)
    cfg["short_control"] = {"report": {"path": "report.json", "sha256": "0" * 64}}
    assert binding(cfg) == initial
    cfg["plan"]["fit"][0]["seed_pool"][0] = "CHANGED"
    assert binding(cfg) != initial
    with pytest.raises(ValueError):
        validate(cfg)


@pytest.mark.parametrize("archetype", ["strength", "block", "exhaust"])
def test_training_profiles_have_native_legitimate_resources_without_funded_energy(
    archetype: str,
) -> None:
    p = profile(archetype, 3)
    assert 0 < p["hp"] <= p["max_hp"] == 80
    assert 12 <= len(p["deck"]) <= 25
    assert "PHILOSOPHERS_STONE" in p["relics"]
    assert "energy" not in p and "enemy_hp" not in p and "rng" not in p


def test_only_confirmed_successful_fit_worlds_can_provide_labels() -> None:
    case = cases("heldout")[0]
    with pytest.raises(ValueError, match="Held-out"):
        lesson(case, {}, {}, {}, {})
    base = {
        "status": "complete",
        "curriculum_success": True,
        "initial_public_input_id": "a",
        "ending_hp": 1,
    }
    assert select(base, [{**base, "status": "capped", "ending_hp": 80}]) is None
    with pytest.raises(ValueError, match="same exact public state"):
        select(base, [{**base, "initial_public_input_id": "other"}])


def test_small_early_hp_bank_cannot_pass_the_win_focused_gate() -> None:
    tiny = [{"scenario": cases("fit")[0], "world": "one", "strict_goal_rescue": False}]
    quality = coverage(tiny, {"combat_turn"}, [], plan()["quality"])
    assert quality["passed"] is False
    assert quality["missing_bosses"]
    assert not quality["checks"]["independent_goal_rescues"]
    assert not quality["checks"]["final_boss_goal_rescue"]


def test_quality_requires_real_successes_across_every_declared_boss_and_family() -> None:
    fitting = [c for c in cases("fit") if c["entry"] == "boss"]
    lessons = [
        {"scenario": c, "world": c["seed_pool"][0], "strict_goal_rescue": True} for c in fitting
    ]
    held = [{"status": "complete", "curriculum_success": True}] * 3
    assert coverage(lessons, REQUIRED_FAMILIES, held, plan()["quality"])["passed"] is True
    assert not coverage(lessons, REQUIRED_FAMILIES - {"rest_site"}, held, plan()["quality"])[
        "passed"
    ]
    assert not coverage(lessons, REQUIRED_FAMILIES, [], plan()["quality"])["passed"]


def test_prepared_act_advancement_is_curriculum_success_but_not_terminal_game_win() -> None:
    frame = {"terminal": False, "public_input": {"context": {"persistent": {"run": {"act": 3}}}}}
    start = {"kind": "prepared_training_only", "scenario": {"act": 2}}
    assert terminal(frame, start) == (True, True)
    assert terminal(frame, {"kind": "natural_training"}) == (False, False)
    assert terminal({"terminal": True, "ending": {"victory": False}}, start) == (True, False)
    with pytest.raises(ValueError, match="native ending"):
        terminal({"terminal": True, "ending": {}}, start)


def test_boss_metadata_must_match_the_actual_public_native_boss() -> None:
    case = cases("fit")[0]
    cards = [{"definition_id": c} for c in case["profile"]["deck"]]
    frame = {
        "public_input": {
            "context": {
                "persistent": {
                    "run": {
                        "act": case["act"],
                        "act_definition_id": case["act_definition"],
                        "bosses": [{"definition_id": "WRONG"}],
                    }
                },
                "reads": [{"kind": "run_deck", "content": {"cards": cards}}],
                "interaction": {"content": {"context": {"encounter_type": "boss"}}},
            }
        }
    }
    with pytest.raises(ValueError, match="actual native boss"):
        check_start(
            frame,
            {
                "kind": "prepared_training_only",
                "scenario": case,
                "native_boss": "ENCOUNTER." + case["boss"],
            },
        )


def test_public_teacher_blocks_immediate_visible_lethal_damage() -> None:
    p = public(damage=8, hp=8)
    assert score_action(p, 1, "defensive") > score_action(p, 0, "defensive")
    with pytest.raises(ValueError, match="declared teacher"):
        score_action(p, 0, "private_oracle")


def test_zero_energy_whirlwind_is_not_scored_as_a_damage_action() -> None:
    p = public()
    p["context"]["interaction"]["content"]["context"]["player"]["energy"] = 0
    p["candidates"][1]["subject"]["properties"] = {
        "definition_id": "WHIRLWIND",
        "stats": {"damage": 20},
    }
    assert score_action(p, 1, "scaling") < score_action(p, 0, "scaling")


def test_private_future_field_is_rejected_before_teacher_inference() -> None:
    instance = TeacherPolicy.__new__(TeacherPolicy)
    instance.failed = False
    instance.pending = None
    p = public()
    p["context"]["rng_state"] = "secret"
    with pytest.raises(ValueError, match="Private"):
        instance.choose({"terminal": False, "public_input": p})


def test_confirmation_checks_complete_ordered_semantics_without_realigning(tmp_path: Path) -> None:
    for name, action in [("a", 0), ("b", 1)]:
        folder = tmp_path / name
        folder.mkdir()
        with gzip.open(folder / "shared-public.jsonl.gz", "wt") as h:
            h.write(
                json.dumps(
                    {"kind": "policy_input", "frame": {"public_input": public(), "terminal": False}}
                )
                + "\n"
            )
            h.write(
                json.dumps(
                    {
                        "kind": "policy_choice",
                        "choice": {
                            "action_index": action,
                            "navigation_only": False,
                            "behavior": "teacher",
                        },
                    }
                )
                + "\n"
            )
    assert not matching_confirmation(tmp_path, {"directory": "a"}, {"directory": "b"})


def test_incomplete_unit_is_never_replayed_or_cleared(tmp_path: Path) -> None:
    cfg = {"workspace": "artifacts/test-win"}
    store = ChunkJournal(tmp_path, cfg)
    with store.lock():
        path = store.begin("case-a", {"case": "a"})
    ctx = {"qualification": SimpleNamespace(root=tmp_path)}
    called = []
    with pytest.raises(FileExistsError):
        unit(
            ctx,
            store,
            "case-a",
            {"case": "a"},
            time.monotonic() + 500,
            lambda *_: called.append(True),
        )
    assert not called and (path / "active.json").exists()
    with pytest.raises(FileExistsError):
        inspect_resume({"qualification": SimpleNamespace(root=tmp_path), "config": cfg})


def test_clean_deadline_pause_does_not_start_a_unit(tmp_path: Path) -> None:
    cfg = {"workspace": "artifacts/test-win"}
    store = ChunkJournal(tmp_path, cfg)
    with pytest.raises(CleanPause):
        unit({"qualification": SimpleNamespace(root=tmp_path)}, store, "case", {}, 0, lambda *_: {})
    assert not store.path("case").exists()


def test_heldout_teacher_method_is_frozen_and_does_not_supply_fitting_labels() -> None:
    assert plan()["heldout_teacher"] == "fixed_three_policy_search_v1"
    assert plan()["heldout_teacher_variants"] == plan()["teacher_variants"]
    assert all(c["partition"] == "heldout" for c in cases("heldout"))
    assert {c["player"] for c in cases("fit")} == {2, 3}
    assert manifest_identifier(plan()) == manifest_identifier(copy.deepcopy(plan()))
