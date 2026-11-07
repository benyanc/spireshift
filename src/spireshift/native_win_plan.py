"""Prospective, training-owned all-act curriculum on the frozen A8 engine."""

from __future__ import annotations

from typing import Any

CONTRACT = "native_A8_win_curriculum_training_only_v1"
ACTS = {
    "OVERGROWTH": (1, ("VANTOM_BOSS", "CEREMONIAL_BEAST_BOSS", "THE_KIN_BOSS")),
    "UNDERDOCKS": (1, ("WATERFALL_GIANT_BOSS", "SOUL_FYSH_BOSS", "LAGAVULIN_MATRIARCH_BOSS")),
    "HIVE": (2, ("THE_INSATIABLE_BOSS", "KNOWLEDGE_DEMON_BOSS", "KAISER_CRAB_BOSS")),
    "GLORY": (3, ("QUEEN_BOSS", "TEST_SUBJECT_BOSS", "AEONGLASS_BOSS")),
}
DECKS = {
    "strength": ["STRIKE_IRONCLAD"] * 3
    + ["DEFEND_IRONCLAD"] * 3
    + [
        "BASH",
        "POMMEL_STRIKE",
        "POMMEL_STRIKE",
        "SHRUG_IT_OFF",
        "SHRUG_IT_OFF",
        "INFLAME",
        "INFLAME",
        "DEMON_FORM",
        "WHIRLWIND",
        "UPPERCUT",
    ],
    "block": ["STRIKE_IRONCLAD"] * 2
    + ["DEFEND_IRONCLAD"] * 3
    + [
        "BASH",
        "SHRUG_IT_OFF",
        "SHRUG_IT_OFF",
        "IRON_WAVE",
        "IRON_WAVE",
        "BODY_SLAM",
        "BODY_SLAM",
        "BARRICADE",
        "ENTRENCH",
        "BATTLE_TRANCE",
    ],
    "exhaust": ["STRIKE_IRONCLAD"] * 2
    + ["DEFEND_IRONCLAD"] * 2
    + [
        "BASH",
        "SHRUG_IT_OFF",
        "SHRUG_IT_OFF",
        "POMMEL_STRIKE",
        "POMMEL_STRIKE",
        "SECOND_WIND",
        "FEEL_NO_PAIN",
        "DARK_EMBRACE",
        "BURNING_PACT",
        "FIEND_FIRE",
        "UPPERCUT",
    ],
}
TEACHERS = ("balanced", "defensive", "scaling")
ENTRIES = ("act_start", "preboss", "shop", "event", "treasure", "boss", "natural")
REQUIRED_FAMILIES = {
    "combat_turn",
    "map_navigation",
    "reward_claim",
    "card_reward_selection",
    "shop_inventory",
    "rest_site",
    "event_option",
}


def profile(archetype: str, act: int, variant: int = 0) -> dict[str, Any]:
    if archetype not in DECKS or act not in (1, 2, 3) or variant not in (0, 1):
        raise ValueError("Unknown fixed curriculum deck, act or resource variant")
    relics = ["BURNING_BLOOD", "ANCHOR"]
    if act >= 2:
        relics += ["VAJRA", "ODDLY_SMOOTH_STONE", "PHILOSOPHERS_STONE"]
    if act == 3:
        relics += ["BAG_OF_PREPARATION", "MUMMIFIED_HAND"]
    deck = DECKS[archetype]
    if act >= 2 and archetype == "block":
        deck = ["DEFEND_IRONCLAD"] * 2 + ["SHRUG_IT_OFF"] * 4 + ["IMPERVIOUS"] * 2
        deck += ["BARRICADE", "ENTRENCH", "ENTRENCH"] + ["BODY_SLAM"] * 3
        deck += ["BATTLE_TRANCE", "OFFERING"]
    elif act == 3:
        # Explicit constructed training decks, not claimed naturally acquired runs.
        deck = {
            "strength": ["STRIKE_IRONCLAD"] * 2
            + ["DEFEND_IRONCLAD"] * 2
            + [
                "BASH",
                "POMMEL_STRIKE",
                "POMMEL_STRIKE",
                "SHRUG_IT_OFF",
                "SHRUG_IT_OFF",
                "INFLAME",
                "DEMON_FORM",
                "WHIRLWIND",
                "SWORD_BOOMERANG",
                "SWORD_BOOMERANG",
                "UPPERCUT",
                "OFFERING",
                "IMPERVIOUS",
            ],
            "block": ["STRIKE_IRONCLAD", "DEFEND_IRONCLAD", "DEFEND_IRONCLAD"]
            + ["SHRUG_IT_OFF"] * 4
            + ["IMPERVIOUS"] * 2
            + ["BARRICADE", "ENTRENCH", "ENTRENCH"]
            + ["BODY_SLAM"] * 3
            + ["BATTLE_TRANCE", "OFFERING"],
            "exhaust": [
                "STRIKE_IRONCLAD",
                "DEFEND_IRONCLAD",
                "BASH",
                "SHRUG_IT_OFF",
                "SHRUG_IT_OFF",
                "POMMEL_STRIKE",
                "POMMEL_STRIKE",
                "SECOND_WIND",
                "FEEL_NO_PAIN",
                "DARK_EMBRACE",
                "BURNING_PACT",
                "FIEND_FIRE",
                "CORRUPTION",
                "IMPERVIOUS",
                "OFFERING",
                "UPPERCUT",
            ],
        }[archetype]
    return {
        "deck": deck,
        "upgrades": 2 * (act - 1),
        "max_hp": 80,
        "hp": 60 + 20 * variant,
        "gold": 100 + 60 * act,
        "relics": relics,
        "potions": ["FIRE_POTION"],
        "upgrade_priority": [
            "BARRICADE",
            "CORRUPTION",
            "DEMON_FORM",
            "INFLAME",
            "ENTRENCH",
            "BODY_SLAM",
            "WHIRLWIND",
            "FEEL_NO_PAIN",
            "DARK_EMBRACE",
            "IMPERVIOUS",
        ],
    }


def cases(partition: str, *, control: bool = False, generation: int = 1) -> list[dict[str, Any]]:
    if partition not in {"fit", "heldout", "control_fit", "control_heldout"}:
        raise ValueError("No evaluation/test partition may supply curriculum labels")
    if control != partition.startswith("control_"):
        raise ValueError("Control and main worlds are separate")
    specifications: list[tuple[str, str, str | None, str]] = []
    if control:
        for act, boss in [
            ("UNDERDOCKS", "WATERFALL_GIANT_BOSS"),
            ("HIVE", "KAISER_CRAB_BOSS"),
            ("GLORY", "QUEEN_BOSS"),
        ]:
            specifications.append(
                (act, "boss", boss, "strength" if act == "UNDERDOCKS" else "block")
            )
        if partition == "control_fit":
            specifications += [
                ("GLORY", "preboss", "QUEEN_BOSS", "block"),
                ("HIVE", "shop", None, "exhaust"),
            ]
    elif partition == "fit":
        for act, (_, bosses) in ACTS.items():
            for boss in bosses:
                for archetype in ("strength", "block"):
                    specifications.append((act, "boss", boss, archetype))
            for archetype in ("strength", "exhaust"):
                specifications.append((act, "act_start", None, archetype))
            for entry, archetype in zip(
                ("preboss", "shop", "event", "treasure"),
                ("block", "exhaust", "strength", "block"),
                strict=True,
            ):
                specifications.append((act, entry, None, archetype))
        specifications += [("ANY", "natural", None, "strength")] * 8
    else:
        for act, (_, bosses) in ACTS.items():
            specifications += [
                (act, "boss", bosses[-1], "exhaust"),
                (act, "act_start", None, "block"),
                (act, "preboss", bosses[0], "strength"),
            ]
    tag = {"fit": "F", "heldout": "H", "control_fit": "C", "control_heldout": "D"}[partition]
    result = []
    for i, (act, entry, boss_id, archetype) in enumerate(specifications, 1):
        number = 1 if act == "ANY" else ACTS[act][0]
        result.append(
            {
                "key": f"{partition.replace('_', '-')}-{i:03d}",
                "partition": partition,
                "act_definition": act,
                "act": number,
                "entry": entry,
                "boss": boss_id,
                "archetype": archetype,
                "player": 2 + (i - 1) % 2,
                "profile": None if entry == "natural" else profile(archetype, number, i % 2),
                "seed_pool": [
                    f"SP1RESH1FTW{generation if control else 1}{tag}{i:03d}P{j:02d}"
                    for j in range(1, 9)
                ],
            }
        )
    return result


def plan(control: bool = False) -> dict[str, Any]:
    return {
        "fit": cases("control_fit" if control else "fit", control=control),
        "heldout": cases("control_heldout" if control else "heldout", control=control),
        "reserved_evaluation_seeds": [f"SP1RESH1FTW1E{i:03d}" for i in range(1, 65)],
        "teacher_variants": list(TEACHERS),
        "heldout_teacher": "fixed_three_policy_search_v1",
        "heldout_teacher_variants": list(TEACHERS),
        "teacher_selection": "verified_goal_success_then_HP_fixed_candidates_v1",
        "maximum_decisions": 2048,
        "episode_wall_seconds": 90,
        "episode_cpu_seconds": 128,
        "maximum_rounds_per_fight": 30,
        "prepared_goal": "earlier_act_advance_or_native_final_boss_completed_reward_owner_v1",
        "known_gap": "headless_Architect_win_completion_unqualified_no_full_run_win_substitution",
        "quality": {
            "act_definitions": list(ACTS),
            "boss_definitions": [b for _, bs in ACTS.values() for b in bs],
            "final_boss_definitions": list(ACTS["GLORY"][1]),
            "families": sorted(REQUIRED_FAMILIES),
            "strict_improvement_worlds": 4,
            "final_boss_rescues": 1,
            "minimum_heldout_successes": 3,
        },
        "ordinary_PPO": False,
        "student_inputs_public_only": True,
        "training_start_wins_are_full_run_wins": False,
        "automatic_follow_up": False,
    }


def start_cases(generation: int = 1) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = [
        {"act_definition": act, "act": number, "entry": "boss", "boss": boss}
        for act, (number, bosses) in ACTS.items()
        for boss in bosses
    ]
    specs += [
        {"act_definition": "GLORY", "act": 3, "entry": "preboss", "boss": "QUEEN_BOSS"},
        {"act_definition": "HIVE", "act": 2, "entry": "shop", "boss": None},
    ]
    return [
        {
            **s,
            "key": f"start-control-{i:02d}",
            "partition": "control_fit",
            "player": 2,
            "archetype": "strength",
            "profile": profile("strength", s["act"]),
            "seed_pool": [f"SP1RESH1FTW{generation}S{i:03d}P{j:02d}" for j in range(1, 9)],
        }
        for i, s in enumerate(specs, 1)
    ]
