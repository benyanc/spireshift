from typing import Any

from spireshift.native_a8_tactical_policy import (
    DYING_HP,
    GIANT,
    block_plan,
    lethal_plan,
    tactical_choice,
)


def card(
    identity: str, slot: int, energy: int, *, target: int | None = None, **stats: int
) -> dict[str, Any]:
    return {
        "verb": "play",
        "subject": {
            "properties": {
                "definition_id": identity,
                "cost": str(energy),
                "entity_id": {"public_slot": slot},
                "stats": stats,
            }
        },
        "arguments": []
        if target is None
        else [{"role": "target", "entity": {"properties": {"entity_id": {"public_slot": target}}}}],
    }


def enemy(identity: str, hp: int, slot: int, **powers: int) -> dict[str, Any]:
    return {
        "definition_id": identity,
        "hp": hp,
        "max_hp": hp,
        "block": 0,
        "entity_id": {"public_slot": slot},
        "statuses": [{"definition_id": k, "amount": v} for k, v in powers.items()],
        "intents": [],
    }


def menu(
    encounter: str, foe: dict[str, Any], hp: int, actions: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any], list[int]]:
    combat = {
        "encounter_type": encounter,
        "enemies": [foe],
        "player": {"energy": 3, "block": 0, "statuses": []},
    }
    candidates = [{"verb": "end_turn"}, *actions]
    public = {
        "context": {
            "interaction": {"kind": "combat_turn", "content": {"context": combat}},
            "persistent": {"player": {"hp": hp, "relics": []}},
            "reads": [],
        },
        "candidates": candidates,
    }
    return public, combat, list(range(len(candidates)))


def test_eel_lethal_uses_two_distinct_cards_with_vulnerable_and_exact_energy() -> None:
    foe = enemy("TERROR_EEL", 25, 12, VULNERABLE_POWER=2)
    public, combat, indices = menu(
        "elite",
        foe,
        3,
        [
            card("DEFEND_IRONCLAD", 1, 1, block=5),
            card("THUNDERCLAP", 2, 1, damage=7, vulnerablepower=1),
            card("STRIKE_IRONCLAD", 3, 1, target=12, damage=6),
            card("STRIKE_IRONCLAD", 4, 1, target=12, damage=6),
        ],
    )
    assert lethal_plan(public, indices, combat) == (2, 3, 4)
    assert tactical_choice(public, indices) == (2, "elite_lethal_turn")
    combat["player"]["energy"] = 2
    assert tactical_choice(public, indices) is None
    combat["player"]["energy"] = 3
    foe["block"] = 4
    assert tactical_choice(public, indices) is None
    foe["block"] = 0
    public["candidates"][4] = public["candidates"][3]
    assert tactical_choice(public, indices) is None


def test_lethal_requires_all_targets_and_supported_enemy_effects() -> None:
    foe = enemy("WRIGGLER", 6, 11)
    public, combat, indices = menu(
        "elite",
        foe,
        4,
        [
            card("STRIKE_IRONCLAD", 1, 1, target=11, damage=6),
            card("STRIKE_IRONCLAD", 1, 1, target=12, damage=6),
        ],
    )
    other = enemy("WRIGGLER", 6, 12)
    combat["enemies"].append(other)
    assert not lethal_plan(public, indices, combat)
    public["candidates"][2] = card("STRIKE_IRONCLAD", 2, 1, target=12, damage=6)
    assert lethal_plan(public, indices, combat) == (1, 2)
    other["statuses"].append({"definition_id": "HARDENED_SHELL_POWER", "amount": 1})
    assert not lethal_plan(public, indices, combat)


def test_giant_lethal_transition_resolves_before_block_and_keeps_death_blow_separate() -> None:
    foe = enemy(GIANT, 36, 12, STEAM_ERUPTION_POWER=30, DEMISE_POWER=9)
    foe["intents"] = [{"type": "Attack", "damage": 15}]
    public, combat, indices = menu(
        "boss",
        foe,
        17,
        [
            card("DEFEND_IRONCLAD", 1, 1, block=5),
            card("ANGER", 2, 0, target=12, damage=10),
            card("BASH", 3, 2, target=12, damage=12, vulnerablepower=2),
            card("STRIKE_IRONCLAD", 4, 1, target=12, damage=10),
        ],
    )
    assert lethal_plan(public, indices, combat) == (3, 2, 4)
    assert tactical_choice(public, indices) == (3, "giant_trigger_death_blow")
    foe.update(hp=DYING_HP, max_hp=DYING_HP, intents=[{"type": "Stun"}])
    assert tactical_choice(public, indices) == (0, "giant_wait_for_death_blow")
    foe["intents"] = [{"type": "DeathBlow", "damage": 30}]
    combat["player"]["block"] = 13
    assert tactical_choice(public, indices) == (1, "giant_block_death_blow")
    assert tactical_choice(public, [0, 2, 3, 4]) == (0, "giant_death_blow_end_turn")
    combat["player"]["block"] = 14
    assert tactical_choice(public, [0, 2, 3, 4]) == (0, "giant_survive_death_blow")


def test_giant_death_blow_budgets_the_full_hand() -> None:
    foe = enemy(GIANT, DYING_HP, 12)
    foe["intents"] = [{"type": "DeathBlow", "damage": 30}]
    public, combat, indices = menu(
        "boss",
        foe,
        18,
        [
            card("FLAME_BARRIER", 1, 2, block=10),
            card("DEFEND_IRONCLAD", 2, 1, block=7),
            card("DEFEND_IRONCLAD", 3, 1, block=7),
        ],
    )
    combat["player"]["energy"] = 2
    assert tactical_choice(public, indices) == (2, "giant_block_death_blow")
    offered = {i: public["candidates"][i]["subject"]["properties"] for i in (1, 2, 3)}
    assert block_plan(offered, 2, 30) == (14, (2, 3))


def test_giant_stun_prepares_block_for_the_next_turn() -> None:
    foe = enemy(GIANT, DYING_HP, 12, STEAM_ERUPTION_POWER=30)
    foe["intents"] = [{"type": "Stun"}]
    public, _, indices = menu(
        "boss",
        foe,
        22,
        [card("HEADBUTT", 1, 1, target=12, damage=9)],
    )
    public["context"]["reads"] = [
        {
            "kind": "combat_piles",
            "content": {
                "zones": [
                    {"zone": "discard", "cards": [{"definition_id": "DEFEND_IRONCLAD"}]},
                ]
            },
        },
    ]
    assert tactical_choice(public, indices) == (1, "giant_prepare_block")
