from __future__ import annotations

import copy
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import save_native_episode
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_situation_bank import coverage, extract_case
from spireshift.native_situation_coverage import select as coverage_select
from spireshift.native_situation_features import describe
from spireshift.native_situation_resolve import resolve
from spireshift.native_situation_selection import LIMITS, select, split_worlds
from spireshift.native_situation_sources import protected_sources
from spireshift.native_structured_policy import CONTRACT


def action(verb: str, role: str | None = None, **props: Any) -> dict[str, Any]:
    return {
        "verb": verb,
        "label": verb,
        "arguments": [],
        "subject": {"role": role, "properties": props} if role else None,
    }


def public(family: str = "card_reward_selection", floor: int = 5) -> dict[str, Any]:
    return {
        "schema_version": "actual-engine-public-entity-graph-v1",
        "context": {
            "persistent": {
                "run": {"act": 1, "floor": floor, "ascension": 8},
                "player": {
                    "hp": 40,
                    "max_hp": 80,
                    "gold": 99,
                    "character_definition_id": "IRONCLAD",
                    "relics": [{"definition_id": "A"}],
                    "potions": [],
                },
            },
            "interaction": {"kind": family, "content": {"context": {}}},
            "reads": [
                {
                    "kind": "run_deck",
                    "content": {
                        "card_count": 2,
                        "cards": [
                            {"definition_id": "CARD_A", "cost": "1", "is_upgraded": False},
                            {
                                "definition_id": "CROSS_CHARACTER_CARD",
                                "cost": "0",
                                "is_upgraded": True,
                            },
                        ],
                    },
                }
            ],
        },
        "candidates": [action("skip"), action("select", "card", definition_id="CARD_C")],
    }


def game() -> dict[str, Any]:
    return {
        "cohort": "fit-p2-unchanged-r01",
        "source_ref": "artifacts/source/episode.json",
        "world": "WORLDONE",
        "seed_id": 1,
        "model_id": "model",
        "player": 2,
        "arm": "unchanged",
        "round": 1,
    }


def case() -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "terminal",
        "seed": "WORLDONE",
        "ordinary_PPO_eligible": True,
        "recovered": False,
        "privileged_fixture": False,
        "privileged_fixed_world_teacher": False,
        "native_ending_evidence_agrees": True,
        "policy_contract": CONTRACT,
        "decisions": [],
        "victory": False,
        "maximum_floor": 8,
    }
    for floor in (5, 6):
        p = public(floor=floor)
        result["decisions"].append(
            {
                "public_input": p,
                "choice": {
                    "public_input_id": manifest_identifier(p),
                    "effective_input_id": manifest_identifier(p),
                    "action_index": 0,
                    "effective_action_index": 0,
                    "navigation_only": False,
                    "model_id": "model",
                    "training": True,
                    "policy_contract": CONTRACT,
                    "temperature": 0.8,
                    "behavior": "sampled_softmax",
                    "log_probability": -0.69,
                },
            }
        )
    return result


def rows(c: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return extract_case(c or case(), game(), "case-id", time.monotonic() + 10)[0]


def test_outcome_and_current_chosen_action_do_not_supply_selection_labels() -> None:
    before = rows()
    changed = case()
    changed.update(victory=True, maximum_floor=99)
    changed["decisions"][-1]["choice"].update(action_index=1, effective_action_index=1)
    assert rows(changed) == before
    assert all("chosen_action" not in r and "target" not in r for r in before)


def test_historical_prefix_changes_only_replay_metadata_not_public_selection() -> None:
    before = rows()
    changed = case()
    changed["decisions"][0]["choice"].update(action_index=1, effective_action_index=1)
    after = rows(changed)
    assert {r["public_input_id"] for r in before} == {r["public_input_id"] for r in after}
    prior = {r["decision_index"]: r for r in before}
    assert (
        next(r for r in after if r["decision_index"] == 1)["replay_prefix_sha256"]
        != prior[1]["replay_prefix_sha256"]
    )


@pytest.mark.parametrize(
    "fault", ["partial", "recovered", "fixture", "private", "stale", "world", "menu", "greedy"]
)
def test_unusable_or_corrupt_sources_are_rejected(fault: str) -> None:
    c = case()
    if fault == "partial":
        c["status"] = "truncated"
    elif fault == "recovered":
        c["recovered"] = True
    elif fault == "fixture":
        c["privileged_fixed_world_teacher"] = True
    elif fault == "private":
        c["decisions"][0]["public_input"]["context"]["seed"] = "SECRET"
    elif fault == "stale":
        c["decisions"][0]["choice"]["model_id"] = "foreign-model"
    elif fault == "world":
        c["seed"] = "OTHERWORLD"
    elif fault == "menu":
        c["decisions"][0]["choice"]["effective_action_index"] = 1
    else:
        c["decisions"][0]["choice"]["behavior"] = "greedy"
    with pytest.raises(ValueError):
        rows(c)


def test_optional_skip_and_extra_rest_choices_are_retained_as_opportunities() -> None:
    p = public()
    assert "card_reward_take_or_skip_offered" in describe(p)["tags"]
    p["context"]["interaction"]["kind"] = "rest_site"
    p["candidates"] = [
        action("activate", "rest_option", option_id=option) for option in ("Heal", "Smith", "Hatch")
    ]
    p["candidates"].append(action("close"))
    assert describe(p)["choices"] == 4
    assert "healing_and_smith_offered" in describe(p)["tags"]
    assert len(p["candidates"]) == 4  # Sampling never filters the player's legal actions.


def test_public_card_and_relic_ownership_changes_are_not_pooled_away() -> None:
    p = public()
    a = describe(p)
    cards = p["context"]["reads"][0]["content"]["cards"]
    cards[0]["cost"], cards[1]["cost"] = cards[1]["cost"], cards[0]["cost"]
    assert describe(p)["deck_signature"] != a["deck_signature"]
    p["context"]["persistent"]["player"]["relics"][0]["definition_id"] = "OTHER"
    assert describe(p)["relic_signature"] != a["relic_signature"]


def test_zero_current_cost_and_unavailable_counter_are_not_inferred_discounts_or_zeros() -> None:
    p = public("combat_turn")
    p["candidates"] = [
        action("play", "playable_card", definition_id="A", cost="0", is_upgraded=True),
        action("end_turn"),
    ]
    before = describe(p)
    assert "zero_current_cost_play_offered" in before["tags"]
    assert before["relic_counters_available"] is False
    p["context"]["interaction"]["content"]["context"]["player"] = {
        "relics": [{"id": "A", "counter": 0}]
    }
    assert describe(p)["relic_counters_available"] is True
    assert describe(p)["relic_signature"] != before["relic_signature"]


def candidate(i: int, world: str, family: str = "combat_turn") -> dict[str, Any]:
    row = copy.deepcopy(rows()[0])
    row.update(world=world, source_ref=f"artifacts/{world}-{i}.json", public_input_id=f"state-{i}")
    row["description"].update(
        family=family, bucket=[family, i % 3], inventory_signature=f"deck-{i % 11}"
    )
    return row


def test_selection_is_deterministic_world_grouped_and_caps_long_combat_games() -> None:
    worlds = [f"WORLD{i}" for i in range(32)]
    splits = split_worlds(worlds)
    candidates = [candidate(i, worlds[i % len(worlds)]) for i in range(500)]
    candidates += [candidate(1000 + i, world, "rest_site") for i, world in enumerate(worlds)]
    a, report = select(candidates, splits)
    b, _ = select(list(reversed(candidates)), split_worlds(list(reversed(worlds))))
    assert a == b
    assert report["selection_uses_saved_actions_or_final_outcomes"] is False
    assert Counter(r["split"] for r in a)["validation"] > 0
    assert {r["description"]["family"] for r in a} == {"rest_site", "combat_turn"}
    assert max(Counter(r["world"] for r in a).values()) <= LIMITS["per_world"]
    assert (
        max(Counter((r["world"], r["description"]["family"]) for r in a).values())
        <= LIMITS["per_world_family"]
    )
    assert (
        max(Counter((r["split"], r["description"]["family"]) for r in a).values())
        <= LIMITS["per_split_family"]
    )


def test_exact_duplicates_across_policy_cohorts_and_worlds_never_cross_splits() -> None:
    splits = split_worlds(["A", "B", "C", "D"])
    duplicate = [candidate(1, world) for world in splits]
    a, report = select(duplicate, splits)
    assert len(a) == 1
    assert report["exact_duplicate_references_removed"] == 3
    assert report["selected_situations"] == 1  # Shortage is not padded to the quota.


def test_all_policies_on_the_same_native_world_share_the_split() -> None:
    splits = split_worlds(["A", "B", "C", "D"])
    candidates = [candidate(i, "A", f"family-{i}") for i in range(3)]
    a, _ = select(candidates, splits)
    assert {r["split"] for r in a} == {splits["A"]}


def test_coverage_distinguishes_available_counter_view_from_card_identity() -> None:
    report = coverage([candidate(1, "A")])
    assert report["distinct_card_definitions"] == 2
    assert report["combat_roots_without_public_relic_counter_view"] == 1


def sealed_resolver_fixture(root: Path) -> tuple[Path, str]:
    c, g = case(), game()
    source = {"id": "environment", "path": "manifests/environment.json"}
    binding = {
        "partition": "train",
        "panel_purpose": "training",
        "native_seed": g["world"],
        "seed_id": 1,
        "model_id": "model",
        "config_id": "config",
        "environment_id": "environment",
        "seed_manifest_id": "seeds",
        "training_spec_id": "score",
    }
    episode_path = root / g["source_ref"]
    episode_path.parent.mkdir(parents=True)
    header = save_native_episode(episode_path, c, binding)
    picked = rows(c)
    for row in picked:
        row.update(case_id=header["case_id"], split="fit")
        row["situation_id"] = manifest_identifier(row)
    bank = {
        "config_id": "bank-config",
        "source_environment": source,
        "source_config_id": "config",
        "source_seed_manifest": {"id": "seeds"},
        "training_spec": {"id": "score"},
        "situations": picked,
        "world_splits": {g["world"]: "fit"},
    }
    bank["bank_id"] = manifest_identifier(bank)
    directory = root / "artifacts/bank"
    directory.mkdir()
    atomic_json(directory / "bank.json", bank)
    report = {
        "status": "native_situation_bank_complete",
        "config_id": "bank-config",
        "summary": {"bank_id": bank["bank_id"]},
        "sources": {
            str(p.relative_to(root)): _sha_file(p)
            for p in (directory / "bank.json", episode_path, episode_path.with_suffix(".jsonl.gz"))
        },
    }
    report["report_id"] = manifest_identifier(report)
    atomic_json(directory / "report.json", report)
    return directory / "report.json", next(
        r["situation_id"] for r in picked if r["decision_index"] == 1
    )


def test_resolved_inputs_match_original_menu_and_keep_seed_prefix_outside_student_input(
    tmp_path: Path,
) -> None:
    report, key = sealed_resolver_fixture(tmp_path)
    result = resolve(tmp_path, report, key)
    assert result["student_input"] == public(floor=6)
    assert result["replay_metadata_not_student_input"]["action_indices_before_root"] == [0]
    assert result["replay_metadata_not_student_input"]["root_action_label"] is None
    assert result["ordinary_PPO_eligible"] is False
    assert "native_seed" not in result["student_input"]


def test_changed_bank_or_source_stops_resolution(tmp_path: Path) -> None:
    report, key = sealed_resolver_fixture(tmp_path)
    path = tmp_path / game()["source_ref"]
    path.write_text(path.read_text() + "\n")
    with pytest.raises(ValueError, match="changed"):
        resolve(tmp_path, report, key)


def test_protected_recipe_verification_does_not_follow_its_live_workspace(tmp_path: Path) -> None:
    cfg: dict[str, Any] = {
        "workspace": "artifacts/currently-running",
        "implementation_sha256": {},
        "entry_sha256": {},
        "helpers_sha256": {},
    }
    p = tmp_path / "recipe.json"
    p.write_text(json.dumps(cfg))
    ref = {"path": "recipe.json", "sha256": _sha_file(p)}
    assert protected_sources(tmp_path, ref) == {"recipe.json": ref["sha256"]}
    assert not (tmp_path / cfg["workspace"]).exists()


def test_coverage_reservation_keeps_available_later_boss_and_optional_decisions() -> None:
    splits = {f"WORLD{i}": "validation" for i in range(16)}
    candidates = [candidate(i, f"WORLD{i % 16}") for i in range(200)]
    late = candidate(1000, "WORLD0")
    late["description"].update(
        act=2,
        floor=19,
        floor_band="17+",
        encounter_type="boss",
        hp_band="low",
        bucket=["combat_turn", 2, "17+", "low", "boss"],
    )
    rare = candidate(1001, "WORLD1", "rest_site")
    rare["description"]["tags"] = ["healing_and_smith_offered"]
    selected, report = coverage_select([*candidates, late, rare], splits)
    assert late["public_input_id"] in {r["public_input_id"] for r in selected}
    assert rare["public_input_id"] in {r["public_input_id"] for r in selected}
    assert report["coverage_by_split"]["validation"]["all_available_strata_covered"]
    again, _ = coverage_select([rare, late, *reversed(candidates)], splits)
    assert selected == again


def test_coverage_reservation_reports_impossible_requirements_without_relaxing_caps() -> None:
    candidates = [candidate(i, "WORLD0", "combat_turn") for i in range(6)]
    for i, row in enumerate(candidates):
        row["description"].update(act=i + 1, floor_band=f"band-{i}")
    selected, report = coverage_select(candidates, {"WORLD0": "fit"})
    assert len(selected) == LIMITS["per_world_family"]
    assert report["coverage_by_split"]["fit"]["uncovered_available_strata"]
    assert not report["coverage_by_split"]["fit"]["all_available_strata_covered"]


def test_coverage_sampler_deduplicates_across_worlds_and_keeps_the_declared_split() -> None:
    splits = split_worlds(["A", "B", "C", "D"])
    selected, report = coverage_select([candidate(1, w) for w in splits], splits)
    assert len(selected) == 1
    assert selected[0]["split"] == splits[selected[0]["world"]]
    assert report["exact_duplicate_references_removed"] == 3
