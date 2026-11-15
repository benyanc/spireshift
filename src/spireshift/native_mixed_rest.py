"""Finite rest-site transition controls for the single-player frozen build."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from itertools import permutations
from typing import Any

REST = "rest_site"
SELECTOR = "card_selection"
MAP = "map_navigation"
BASE_OPTIONS = ("HEAL", "SMITH", "DIG", "LIFT")
BASE_RELICS = ("MINIATURE_TENT", "SHOVEL", "GIRYA")
SMITH_BASH = "confirm:BASH"
COOK_CARDS = "confirm:DEFEND_IRONCLAD,STRIKE_IRONCLAD"
BELT = ("BLOOD_POTION", "FOUL_POTION")
Card = tuple[str, bool, str | None, int | None]


@dataclass(frozen=True)
class Case:
    name: str
    seed: str
    steps: tuple[str, ...]
    options: tuple[str, ...] = BASE_OPTIONS
    relics: tuple[str, ...] = BASE_RELICS
    deck: tuple[str, ...] = ("STRIKE_IRONCLAD", "STRIKE_IRONCLAD", "BASH")
    belt: tuple[str, ...] = ()
    girya: int = 0
    clone: bool = False
    disabled: tuple[str, ...] = ()

    @property
    def tent(self) -> bool:
        return "MINIATURE_TENT" in self.relics


def cases() -> tuple[Case, ...]:
    orders = tuple(
        Case(
            "order-" + "-".join(order).lower(),
            "SP1RESH1FTM1XRSTMATRIX01",
            tuple(
                step
                for name in order
                for step in ((name, SMITH_BASH) if name == "SMITH" else (name,))
            )
            + ("proceed",),
        )
        for order in permutations(BASE_OPTIONS)
    )
    return orders + (
        Case(
            "smith-belt-cancel",
            "SP1RESH1FTM1XRSTBELT01",
            (
                "SMITH",
                "use:BLOOD_POTION",
                "discard:FOUL_POTION",
                "cancel",
                "LIFT",
                "DIG",
                "HEAL",
                "SMITH",
                SMITH_BASH,
                "proceed",
            ),
            belt=BELT,
        ),
        Case(
            "smith-cancel-after-heal",
            "SP1RESH1FTM1XRSTCANCEL01",
            ("HEAL", "SMITH", "cancel", "LIFT", "proceed"),
            girya=2,
        ),
        Case("no-tent", "SP1RESH1FTM1XRSTN0TENT01", ("DIG", "proceed"), relics=BASE_RELICS[1:]),
        Case(
            "spent-girya-disabled-smith",
            "SP1RESH1FTM1XRSTCAPPED01",
            ("DIG", "HEAL", "proceed"),
            options=("HEAL", "SMITH", "DIG"),
            deck=("ASCENDERS_BANE",),
            girya=3,
            disabled=("SMITH",),
        ),
        Case(
            "cook-disables-smith",
            "SP1RESH1FTM1XRSTC00K01",
            ("HEAL", "COOK", "cancel", "COOK", COOK_CARDS, "proceed"),
            options=("HEAL", "SMITH", "COOK"),
            relics=("MINIATURE_TENT", "MEAT_CLEAVER"),
            deck=("STRIKE_IRONCLAD", "DEFEND_IRONCLAD", "ASCENDERS_BANE"),
        ),
        Case(
            "hatch",
            "SP1RESH1FTM1XRSTHATCH01",
            ("SMITH", SMITH_BASH, "HATCH", "HEAL", "proceed"),
            options=("HEAL", "SMITH", "HATCH"),
            relics=("MINIATURE_TENT",),
            deck=("STRIKE_IRONCLAD", "BASH", "BYRDONIS_EGG"),
        ),
        Case(
            "clone",
            "SP1RESH1FTM1XRSTCL0NE01",
            ("CLONE", "SMITH", SMITH_BASH, "HEAL", "proceed"),
            options=("HEAL", "SMITH", "CLONE"),
            relics=("MINIATURE_TENT",),
            clone=True,
        ),
        Case(
            "kindle",
            "SP1RESH1FTM1XRSTK1NDLE01",
            ("HEAL", "KINDLE", "SMITH", SMITH_BASH, "proceed"),
            options=("HEAL", "SMITH", "KINDLE"),
            relics=("MINIATURE_TENT", "PUMPKIN_CANDLE"),
        ),
    )


def control(candidate: dict[str, Any], family: str) -> str:
    subject = candidate.get("subject") or {}
    properties = subject.get("properties", {})
    verb, label, arguments = candidate["verb"], candidate["label"], candidate["arguments"]
    if family == REST and "option_id" in properties and verb == "activate":
        return str(properties["option_id"])
    if subject.get("role") == "potion" and (verb == "use" or label.startswith("Discard ")):
        return ("use:" if verb == "use" else "discard:") + str(properties["definition_id"])
    if verb == "confirm" and arguments and all(arg["role"] == "selected_card" for arg in arguments):
        cards = [arg["entity"]["properties"]["definition_id"] for arg in arguments]
        return "confirm:" + ",".join(cards)
    if verb == "cancel" and not subject and not arguments:
        return "cancel"
    if family == REST and not subject and not arguments and label == "Proceed to map":
        return "proceed"
    return str(label)


@dataclass
class View:
    kind: str
    surface: dict[str, Any]
    controls: Counter[str]
    player: dict[str, Any]
    deck: Counter[Card]
    relics: dict[str, int | None]
    belt: dict[int, str]

    @classmethod
    def read(cls, frame: dict[str, Any]) -> View:
        public = frame["public_input"]
        owner = public["context"]["interaction"]
        kind = owner["kind"]
        player = public["context"]["persistent"]["player"]
        (read,) = [r["content"] for r in public["context"]["reads"] if r["kind"] == "run_deck"]
        if read["card_count"] != len(read["cards"]):
            raise ValueError("Rest diagnostics require a complete deck read")
        actions = frame["actions"]
        if (
            len(public["candidates"]) != len(actions)
            or len({a["bound_action_id"] for a in actions}) != len(actions)
            or sorted(a["raw_index"] for a in actions) != list(range(len(actions)))
        ):
            raise ValueError("The learner did not receive each exact current binding")
        return cls(
            kind,
            owner["content"]["surface"],
            Counter(control(c, kind) for c in public["candidates"]),
            player,
            Counter(
                (
                    c["definition_id"],
                    c["is_upgraded"],
                    (c.get("existing_enchantment") or {}).get("definition_id"),
                    (c.get("existing_enchantment") or {}).get("amount"),
                )
                for c in read["cards"]
            ),
            {r["definition_id"]: r.get("counter") for r in player["relics"]},
            {p["slot"]: p["definition_id"] for p in player["potions"]},
        )

    def rest_menu(self, remaining: dict[str, bool], proceed: bool) -> None:
        options = self.surface.get("options", [])
        observed = {row["option_id"]: row["enabled"] for row in options}
        expected = Counter(name for name, enabled in remaining.items() if enabled)
        if proceed:
            expected["proceed"] = 1
        actual = Counter({name: n for name, n in self.controls.items() if ":" not in name})
        if (
            self.kind != REST
            or len(options) != len(observed)
            or observed != remaining
            or self.surface.get("can_proceed") is not proceed
            or actual != expected
        ):
            raise ValueError(
                f"Rest menu differs from remaining native choices: {observed}, {actual}"
            )

    def selector_menu(self, frame: dict[str, Any], count: int) -> None:
        cards = {c["entity_id"]["public_slot"] for c in self.surface["cards"]}
        legal = Counter(permutations(cards, count))
        candidates = frame["public_input"]["candidates"]
        actual = Counter(
            tuple(a["entity"]["public_slot"] for a in candidate["arguments"])
            for candidate in candidates
            if candidate["verb"] == "confirm"
        )
        if (
            self.kind != SELECTOR
            or len(cards) != len(self.surface["cards"])
            or self.surface["min_select"] != count
            or self.surface["max_select"] != count
            or self.surface["cancelable"] is not True
            or self.controls["cancel"] != 1
            or actual != legal
            or any(":" not in name and name != "cancel" for name in self.controls)
        ):
            raise ValueError("The child must own every legal physical card answer and Cancel")

    def potion_menu(self) -> None:
        expected = Counter(f"discard:{name}" for name in self.belt.values())
        if "BLOOD_POTION" in self.belt.values():
            expected["use:BLOOD_POTION"] = 1
        actual = Counter(
            {name: n for name, n in self.controls.items() if name.startswith(("use:", "discard:"))}
        )
        if actual != expected:
            raise ValueError(f"Potion availability changed across rest and card owners: {actual}")


def verify(case: Case, frames: list[dict[str, Any]]) -> dict[str, Any]:
    if len(frames) != len(case.steps) + 1:
        raise ValueError("A rest control lacks its complete successor chain")
    remaining = {name: name not in case.disabled for name in case.options}
    views = [View.read(frame) for frame in frames]
    current = views[0]
    if current.relics.get("GIRYA", 0) != case.girya or list(current.belt.values()) != list(
        case.belt
    ):
        raise ValueError("Rest fixture began with a different Girya counter or potion belt")
    current.rest_menu(remaining, False)
    current.potion_menu()
    child = None
    proceed = False
    for before, after, frame, step in zip(
        views[:-1], views[1:], frames[1:], case.steps, strict=True
    ):
        checked_effect(case, before, after, step)
        commit = None
        if step in ("SMITH", "COOK"):
            child = step
        elif step == "cancel":
            child = None
        elif step.startswith("confirm:"):
            if child is None:
                raise ValueError("A card answer has no rest parent")
            commit, child = child, None
        elif step in remaining:
            commit = step
        if commit is not None:
            if not remaining.pop(commit):
                raise ValueError("A disabled native rest option was committed")
            if commit == "COOK" and "SMITH" in remaining:
                remaining["SMITH"] = False
            if not case.tent:
                remaining.clear()
            proceed = True
        if step == "proceed":
            if (
                not proceed
                or after.kind != MAP
                or not any(s.startswith("Choose ") for s in after.controls)
            ):
                raise ValueError("Proceed did not return a playable map")
        elif child is not None:
            after.selector_menu(frame, 1 if child == "SMITH" else 2)
        else:
            after.rest_menu(remaining, proceed)
        after.potion_menu()
    return {
        "decisions": len(case.steps),
        "owners": [view.kind for view in views],
        "final_hp": views[-1].player["hp"],
        "final_max_hp": views[-1].player["max_hp"],
        "final_deck": sorted([(*card, n) for card, n in views[-1].deck.items()], key=str),
        "final_relics": views[-1].relics,
        "final_potions": views[-1].belt,
    }


def checked_effect(case: Case, before: View, after: View, step: str) -> None:
    hp, max_hp = before.player["hp"], before.player["max_hp"]
    deck, relics, belt = before.deck.copy(), before.relics.copy(), before.belt.copy()
    if step == "HEAL":
        hp = min(max_hp, hp + max_hp * 30 // 100)
    elif step == "LIFT":
        count = int(relics["GIRYA"] or 0) + 1
        if count > 3:
            raise ValueError("Girya exceeded its three native lifts")
        relics["GIRYA"] = count
    elif step == "DIG":
        added = after.relics.keys() - relics.keys()
        if len(added) != 1:
            raise ValueError("Dig did not add exactly one native relic")
        relics.update((name, after.relics[name]) for name in added)
        if "MANGO" in added:
            max_hp += 14
            hp += 14
    elif step == SMITH_BASH:
        deck.subtract({("BASH", False, None, None): 1})
        deck[("BASH", True, None, None)] += 1
    elif step == COOK_CARDS:
        deck.subtract(
            {("DEFEND_IRONCLAD", False, None, None): 1, ("STRIKE_IRONCLAD", False, None, None): 1}
        )
        max_hp += 5
        hp += 5
    elif step == "HATCH":
        relics["BYRDPIP"] = after.relics.get("BYRDPIP")
        deck.subtract({("BYRDONIS_EGG", False, None, None): 1})
        deck[("BYRD_SWOOP", False, None, None)] += 1
    elif step == "CLONE":
        deck.update({card: n for card, n in deck.items() if card[2] == "CLONE"})
        if deck == before.deck:
            raise ValueError("Clone did not copy the declared enchanted card")
    elif step == "KINDLE":
        relics["PUMPKIN_CANDLE"] = int(relics["PUMPKIN_CANDLE"] or 0) + 5
    elif step.startswith(("use:", "discard:")):
        verb, name = step.split(":")
        (slot,) = [slot for slot, potion in belt.items() if potion == name]
        del belt[slot]
        if verb == "use":
            hp = min(max_hp, hp + max_hp // 5)
    if (
        min(deck.values(), default=0) < 0
        or after.deck != +deck
        or after.relics != relics
        or after.belt != belt
        or after.player["hp"] != hp
        or after.player["max_hp"] != max_hp
        or after.player["gold"] != before.player["gold"]
    ):
        raise ValueError(f"{case.name}: public outcome differed after {step}")


def paired_cases() -> tuple[Case, ...]:
    rows = cases()
    selected = (
        "order-dig-smith-lift-heal",
        "smith-belt-cancel",
        "spent-girya-disabled-smith",
        "cook-disables-smith",
        "hatch",
        "clone",
        "kindle",
    )
    return tuple(
        replace(next(row for row in rows if row.name == name), seed=f"SP1RESH1FTM1XRSTP{100 + i}")
        for i, name in enumerate(selected)
    )
