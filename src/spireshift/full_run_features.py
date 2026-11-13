"""Public, candidate-bound features for the frozen full-run simulator.

Indices locate offered objects; they are not card/relic quality. Printed card numbers
are descriptors, not resolved damage or an oracle for unobserved outcomes.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any

from spireshift.combat_features import _buffs, _cards
from spireshift.core.manifest import RulesetIdentity
from spireshift.core.types import LegalAction, Observation
from spireshift.neural_combat_features import CARD_FLAGS
from spireshift.representations import build_model_input

ENCODER_ID = "public-full-run-candidate-properties-v1"
OBSERVATION_SIZE = 682
COMBAT_SIZE = 276
PHASE_NAMES = dict(
    enumerate(
        (
            "combat",
            "card_reward",
            "map",
            "rest_site",
            "shop",
            "relic_reward",
            "complete",
            "event",
            "ancient",
            "card_selection",
            "treasure",
            "crystal_sphere",
            "bundle_selection",
            "phase-13",
        )
    )
)
# Explicit, learnable starting features occupy stable coordinates. All other semantic
# tokens use a separate hashed region, so collisions cannot change their meaning.
DIRECT_FEATURES = (
    "bias",
    "play_card",
    "printed_damage",
    "printed_useful_damage",
    "printed_kill",
    "printed_needed_block",
    "printed_excess_block",
    "printed_cost",
    "end_turn",
    "use_potion",
    "heal_missing_hp",
    "upgrade",
    "take_card",
    "card_quality",
    "skip_card",
    "remove_bad_card",
    "shop_price",
    "buy_relic",
    "buy_potion",
    "claim_reward",
    "skip_reward",
    "route_rest_missing_hp",
    "route_elite",
    "route_treasure",
    "confirm",
    "card_is_power",
    "card_is_curse",
    "duplicate",
    "transform_bad_card",
    "select_card",
    "route_event",
    "route_shop",
)


def _integer(value: object, label: str) -> int:
    if type(value) is not int:
        raise ValueError(f"Public {label} must be an integer")
    return value


def _item(values: object, index: int, label: str) -> Any:
    if not isinstance(values, list) or not 0 <= index < len(values):
        raise ValueError(f"Public {label} does not expose choice {index}")
    return values[index]


def printed_card(card: dict[str, Any], catalog: dict[str, dict[str, Any]]) -> dict[str, Any]:
    identity = _integer(card.get("card_id"), "card ID")
    if identity <= 0:
        raise ValueError("Public card identity must be positive")
    upgraded = card.get("upgraded", False)
    if upgraded not in (False, True, 0, 1):
        raise ValueError("Invalid public upgrade state")
    definition = catalog.get(str(identity))
    card = {
        **card,
        "enchantment_id": card.get("enchantment_id", card.get("enchantment", 0)),
        "enchantment_amount": card.get("enchantment_amount", card.get("enchant_amount", 0)),
    }
    card.pop("enchantment", None)
    card.pop("enchant_amount", None)
    if definition is None:
        # Some synthetic/curse definitions have no printed record. Preserve the visible
        # identity and report missing metadata rather than invent damage or discard it.
        return {**card, "metadata_missing": True}
    return {
        **card,
        "cost": definition["Cost"] + int(upgraded) * definition["UpgradeCost"],
        "damage": definition["BaseDamage"] + int(upgraded) * definition["UpgradeDamage"],
        "block": definition["BaseBlock"] + int(upgraded) * definition["UpgradeBlock"],
        "type": definition["Type"],
        "target_type": definition["Target"],
        **{name: definition[name] for name in CARD_FLAGS},
    }


def _offered_card(identity: object, upgraded: object = False) -> dict[str, Any]:
    return {"card_id": _integer(identity, "offered card ID"), "upgraded": upgraded}


def _combat(state: dict[str, Any], vector: tuple[int, ...]) -> dict[str, Any]:
    if state.get("player_hp") != vector[0] or state.get("player_max_hp") != vector[1]:
        raise ValueError("Public player resources disagree with the combat vector")
    enemies = []
    for slot in range(6):
        at = 80 + slot * 15
        if vector[at] > 0:
            enemies.append(
                {
                    "position": slot,
                    "enemy_id": _item(state.get("enemy_def_ids"), slot, "enemy identities"),
                    "hp": vector[at],
                    "max_hp": vector[at + 1],
                    "block": vector[at + 2],
                    "intent_id": vector[at + 3],
                    "intent_magnitude": vector[at + 4],
                    "secondary_intent_id": vector[170 + slot * 2],
                    "secondary_intent_magnitude": vector[171 + slot * 2],
                    "statuses": _buffs(vector, at + 5, 5),
                }
            )
    return {
        "player": dict(
            zip(
                (
                    "hp",
                    "max_hp",
                    "block",
                    "energy",
                    "max_energy",
                    "draw_count",
                    "discard_count",
                    "exhaust_count",
                ),
                vector[:8],
                strict=True,
            )
        ),
        "statuses": _buffs(vector, 60, 10),
        "hand": list(_cards(vector, 8, 10)),
        "enemies": enemies,
        "selection_kind_id": vector[183],
        "selection_count": vector[184],
        "selection_cards": list(_cards(vector, 185, 10)) if vector[183] else [],
        "orb_capacity": vector[225],
        "orbs": [list(vector[226 + i * 3 : 229 + i * 3]) for i in range(10) if vector[226 + i * 3]],
        "promised_cards": list(_cards(vector, 256, 5)),
    }


def _bind(
    state: dict[str, Any],
    vector: tuple[int, ...],
    action: LegalAction,
    combat: dict[str, Any] | None,
) -> dict[str, Any]:
    phase = state["phase"]
    if action.kind != f"evangambit_{phase}" or action.payload.get("phase") != phase:
        raise ValueError("Legal candidate belongs to another public phase")
    if set(action.payload) - {"phase", "action_index", "target_index"}:
        raise ValueError("Unsupported full-run candidate payload")
    index = _integer(action.payload.get("action_index"), "action index")
    target = _integer(action.payload.get("target_index", -1), "target index")
    if index < 0 or target < -1:
        raise ValueError("Invalid full-run action locator")
    if phase == "combat":
        assert combat is not None
        if combat["selection_kind_id"]:
            choices = combat["selection_cards"]
            if combat["selection_count"] != len(choices):
                raise ValueError("Public combat selection exceeds visible cards")
            # Selection resolution ignores historical adapter target decorations.
            if index == len(choices):
                return {
                    "kind": "skip_combat_selection",
                    "selection_kind_id": combat["selection_kind_id"],
                }
            return {
                "kind": "select_card",
                "card": _item(choices, index, "combat selection"),
                "selection_kind_id": combat["selection_kind_id"],
            }
        hand = combat["hand"]
        if index < len(hand):
            enemy = next((e for e in combat["enemies"] if e["position"] == target), None)
            if target >= 0 and enemy is None:
                raise ValueError("Public candidate targets an absent enemy")
            return {"kind": "play_card", "card": hand[index], "target": enemy}
        if index == len(hand):
            if target >= 0:
                raise ValueError("End turn cannot target an enemy")
            return {"kind": "end_turn"}
        potion = _item(state.get("potions"), index - len(hand) - 1, "potion belt")
        if not potion:
            raise ValueError("Potion candidate points to an empty slot")
        enemy = next((e for e in combat["enemies"] if e["position"] == target), None)
        if target >= 0 and enemy is None:
            raise ValueError("Public potion targets an absent enemy")
        return {"kind": "use_potion", "potion_id": potion, "target": enemy}
    if target >= 0:
        raise ValueError("Noncombat action unexpectedly targets an enemy")
    if phase == "card_reward":
        if index < 3:
            return {
                "kind": "take_card",
                "card": _offered_card(
                    _item(state.get("card_rewards"), index, "card rewards"),
                    _item(state.get("card_reward_upgraded"), index, "reward upgrades"),
                ),
            }
        if index == 5:
            return {"kind": "take_card", "card": _offered_card(vector[680], vector[681])}
        return {"kind": {3: "skip_card", 4: "sacrifice_card_reward", 6: "reroll_cards"}[index]}
    if phase == "shop":
        if index == 14:
            return {"kind": "leave_shop"}
        price = _item(state.get("shop_costs"), index, "shop prices")
        if index < 7:
            return {
                "kind": "buy_card",
                "price": price,
                "card": _offered_card(_item(state.get("shop_cards"), index, "shop cards")),
            }
        if index < 10:
            return {
                "kind": "buy_relic",
                "price": price,
                "relic_id": _item(state.get("shop_relics"), index - 7, "shop relics"),
            }
        if index < 13:
            return {
                "kind": "buy_potion",
                "price": price,
                "potion_id": _item(state.get("shop_potions"), index - 10, "shop potions"),
            }
        if index == 13:
            return {"kind": "buy_removal", "price": price}
    if phase == "map":
        if index >= 7:
            raise ValueError("Map candidate exceeds the frozen visible row")
        node_type = vector[COMBAT_SIZE + 12 + index]
        choices = state.get("map_choices")
        if not isinstance(choices, list):
            raise ValueError("Public map choices are missing")
        # Info compacts absent slots; locate by the ordinal of nonempty vector slots.
        ordinal = sum(bool(v) for v in vector[COMBAT_SIZE + 12 : COMBAT_SIZE + 12 + index])
        node = _item(choices, ordinal, "map choices")
        if not node_type or node.get("node_type") != node_type:
            raise ValueError("Public map candidate differs from its visible node")
        graph = state.get("map", {})
        children = [
            edge["to"]
            for edge in graph.get("edges", [])
            if edge["from"] == {"x": node["x"], "y": node["y"]}
        ]
        descendants = [n for n in graph.get("nodes", []) if {"x": n["x"], "y": n["y"]} in children]
        return {"kind": "route", "node": node, "visible_children": descendants}
    if phase == "rest_site":
        names = {
            0: "heal",
            1: "upgrade",
            2: "duplicate",
            3: "leave_rest",
            4: "lift",
            5: "dig",
            6: "hatch",
            7: "cook",
            8: "kindle",
        }
        return {"kind": names[index]}
    if phase == "ancient":
        return {
            "kind": "ancient_option",
            "relic_id": _item(state.get("neow_options"), index, "ancient options"),
        }
    if phase == "card_selection":
        offers = state.get("offer_cards", [])
        if offers:
            if index == len(offers):
                return {"kind": "confirm"}
            return {
                "kind": "take_card",
                "card": _offered_card(_item(offers, index, "offered cards")),
            }
        return {
            "kind": "select_card",
            "card": _item(state.get("deck"), index, "deck"),
            "selection": state.get("deck_selection", []),
        }
    if phase == "bundle_selection":
        if index == 2:
            return {"kind": "confirm"}
        return {
            "kind": "take_bundle",
            "cards": [
                _offered_card(_item(state.get("bundle_offer"), index * 3 + i, "bundle cards"))
                for i in range(3)
            ],
        }
    if phase == "relic_reward":
        if index == 3:
            return {"kind": "skip_reward"}
        if 4 <= index <= 6:
            return {
                "kind": "discard_potion",
                "potion_id": _item(state.get("potions"), index - 4, "potion belt"),
            }
        rewards = state.get("pending_rewards")
        if not isinstance(rewards, list) or len(rewards) != 4:
            raise ValueError("Public pending rewards are missing")
        # Claims are compacted in gold/potion/relic/card order; option 3 also means
        # proceed in the pinned mask. Preserve this engine ambiguity explicitly.
        visible = [
            {"kind": "claim_reward", "reward_type": name, "amount_or_id": value}
            for name, value in zip(("gold", "potion", "relic", "card"), rewards, strict=True)
            if value
        ]
        if index < len(visible):
            return visible[index]
        return {"kind": "reward_option", "option_id": index, "pending_rewards": rewards}
    if phase == "treasure":
        return {"kind": "open_treasure"}
    if phase == "event":
        # The current adapter exposes event identity and enabled options, not text or
        # resolved costs. This honest categorical binding learns event-specific choices.
        return {"kind": "event_option", "event_id": state.get("event_id"), "option_id": index}
    if phase == "crystal_sphere":
        # The adapter does not expose the revealed board. Only enabled cells and the
        # chosen tool are observable here; do not manufacture board contents.
        return {
            "kind": "crystal_choice",
            "tool_id": index // 121,
            "x": (index % 121) // 11,
            "y": index % 11,
        }
    if phase == "phase-13":
        # Frozen adapter does not expose Fake Merchant stock. Learn enabled choices
        # categorically, honestly marking their unobserved item contents.
        return {
            "kind": "fake_merchant_option",
            "option_id": index,
            "item_metadata_available": False,
        }
    raise ValueError(f"Unsupported full-run public phase: {phase}")


def _tokens(value: object, prefix: str, output: dict[str, float]) -> None:
    if isinstance(value, dict):
        for key, item in sorted(value.items()):
            _tokens(item, f"{prefix}/{key}", output)
    elif isinstance(value, list):
        # Sets of deck/hand/options are pooled; no hidden draw order or menu slot enters.
        for item in value:
            _tokens(item, f"{prefix}/item", output)
        output[f"{prefix}/count"] = math.log1p(len(value)) / 4
    elif isinstance(value, (bool, str)) or prefix.endswith(("_id", "/position", "/node_type")):
        output[f"{prefix}={value}"] = output.get(f"{prefix}={value}", 0.0) + 1
    elif isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise ValueError("Nonfinite public feature")
        output[prefix] = output.get(prefix, 0.0) + math.asinh(value) / 5
    elif value is None:
        output[f"{prefix}=absent"] = 1.0
    else:
        raise ValueError("Unsupported public feature type")


@dataclass(frozen=True, slots=True)
class FullRunInput:
    representation_hash: str
    source_action_ids: tuple[str, ...]
    bindings: tuple[dict[str, Any], ...]
    vectors: tuple[dict[int, float], ...]
    context: dict[str, Any]


def full_run_input(
    ruleset: RulesetIdentity,
    observation: Observation,
    actions: tuple[LegalAction, ...],
    catalog: dict[str, dict[str, Any]],
    dimension: int,
) -> FullRunInput:
    if not 128 <= dimension <= 4096:
        raise ValueError("Full-run feature dimension must be in [128,4096]")
    representation = build_model_input(ruleset, observation, actions)  # boundary/hash/patch check
    state = observation.public_state
    raw = state.get("observation_vector")
    if not isinstance(raw, list) or len(raw) != OBSERVATION_SIZE:
        raise ValueError("Full-run public observation layout differs")
    vector = tuple(_integer(v, "observation vector") for v in raw)
    phase_value = state.get("phase")
    phase = PHASE_NAMES.get(phase_value) if type(phase_value) is int else phase_value
    if not isinstance(phase, str) or phase not in PHASE_NAMES.values():
        raise ValueError("Unknown public full-run phase")
    if PHASE_NAMES.get(vector[COMBAT_SIZE]) != phase:
        raise ValueError("Public phase differs from the frozen observation vector")
    # The admitted adapter's info loop leaves phase as an integer. Normalize only
    # our internal copy; never change the adapter or its content identity.
    state = {**state, "phase": phase}
    combat = _combat(state, vector) if state.get("phase") == "combat" else None
    context = {
        key: state.get(key)
        for key in (
            "phase",
            "floor",
            "act",
            "gold",
            "player_hp",
            "player_max_hp",
            "deck_size",
            "relic_slots",
            "potions",
            "current_node_type",
            "deck_selection",
            "event_id",
        )
    }
    deck = state.get("deck", [])
    if not isinstance(deck, list):
        raise ValueError("Public deck is missing")
    context["deck"] = [printed_card(c, catalog) for c in deck]
    context["potions"] = [{"potion_id": p} for p in state.get("potions", []) if p]
    if combat is not None:
        combat = {
            **combat,
            "hand": [printed_card(c, catalog) for c in combat["hand"]],
            "selection_cards": [printed_card(c, catalog) for c in combat["selection_cards"]],
        }
        context["combat"] = combat
    hp = _integer(state.get("player_hp"), "HP")
    max_hp = _integer(state.get("player_max_hp"), "max HP")
    if not 0 <= hp <= max_hp or max_hp <= 0:
        raise ValueError("Invalid public player HP")
    missing = 1 - hp / max_hp
    context["hp_fraction"] = 1 - missing
    shared: dict[str, float] = {}
    _tokens(context, "state", shared)
    bindings = tuple(_bind(state, vector, a, combat) for a in actions)
    rows = []
    for binding in bindings:
        binding = dict(binding)
        if "card" in binding:
            binding["card"] = printed_card(binding["card"], catalog)
        if "cards" in binding:
            binding["cards"] = [printed_card(c, catalog) for c in binding["cards"]]
        tokens = dict(shared)
        _tokens(binding, "candidate", tokens)
        direct = dict.fromkeys(DIRECT_FEATURES, 0.0)
        direct["bias"] = 1
        kind = binding["kind"]
        if kind in direct:
            direct[kind] = 1
        card = binding.get("card", {})
        damage, block, cost = card.get("damage", 0), card.get("block", 0), card.get("cost", 0)
        direct["card_is_power"] = float(card.get("type") == "Power")
        direct["card_is_curse"] = float(card.get("type") in {"Curse", "Status"})
        if kind == "play_card":
            target = binding.get("target")
            direct["printed_damage"] = damage / 10
            direct["printed_cost"] = max(0, cost) / 3
            if target:
                direct["printed_useful_damage"] = (
                    max(0, min(damage - target["block"], target["hp"])) / 10
                )
                direct["printed_kill"] = float(damage >= target["hp"] + target["block"])
            if combat is not None:
                incoming = sum(
                    (e["intent_magnitude"] if e["intent_id"] == 0 else 0)
                    + (e["secondary_intent_magnitude"] if e["secondary_intent_id"] == 0 else 0)
                    for e in combat["enemies"]
                )
                needed = max(0, incoming - combat["player"]["block"])
                direct["printed_needed_block"] = min(needed, block) / 10
                direct["printed_excess_block"] = max(0, block - needed) / 10
        direct["heal_missing_hp"] = missing if kind == "heal" else 0
        if kind in {"take_card", "buy_card", "select_card"}:
            direct["card_quality"] = (damage + block) / (10 * max(1, cost))
            if kind == "select_card":
                selection = binding.get("selection", [0])
                direct["remove_bad_card"] = float(bool(selection) and selection[0] in {7, 8, 9}) * (
                    direct["card_is_curse"] + float(card.get("StrikeTag", False))
                )
        direct["shop_price"] = binding.get("price", 0) / max(1, state.get("gold", 0))
        if kind == "route":
            node_type = binding["node"]["node_type"]
            direct["route_rest_missing_hp"] = missing if node_type == 3 else 0
            direct["route_elite"] = float(node_type == 2)
            direct["route_treasure"] = float(node_type == 5)
            direct["route_event"] = float(node_type == 7)
            direct["route_shop"] = float(node_type == 4)
        values = {i: float(direct[name]) for i, name in enumerate(DIRECT_FEATURES) if direct[name]}
        for token, amount in sorted(tokens.items()):
            digest = hashlib.sha256(f"{ENCODER_ID}|{token}".encode()).digest()
            index = len(DIRECT_FEATURES) + int.from_bytes(digest[:8], "big") % (
                dimension - len(DIRECT_FEATURES)
            )
            values[index] = values.get(index, 0.0) + (1 if digest[8] & 1 else -1) * amount
        rows.append({i: max(-5.0, min(5.0, v)) for i, v in sorted(values.items()) if v})
    return FullRunInput(
        representation.representation_hash,
        tuple(a.action_id for a in actions),
        bindings,
        tuple(rows),
        context,
    )
