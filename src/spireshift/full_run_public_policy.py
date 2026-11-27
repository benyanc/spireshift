"""Versioned whole-run player with complete public menus and observable confirmation."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from spireshift.adapters.evangambit_public_choices import choice_view
from spireshift.core.manifest import RulesetIdentity, manifest_identifier
from spireshift.core.types import LegalAction, Observation
from spireshift.full_run_features import (
    DIRECT_FEATURES as LEGACY_DIRECT_FEATURES,
)
from spireshift.full_run_features import (
    ENCODER_ID as LEGACY_ENCODER_ID,
)
from spireshift.full_run_features import FullRunInput, _tokens, full_run_input, printed_card
from spireshift.full_run_policy import (
    SCHEMA as LEGACY_SCHEMA,
)
from spireshift.full_run_policy import (
    FullRunDecision,
    FullRunModel,
    FullRunPolicy,
    initial_full_run_model,
    score_features,
)
from spireshift.public_run_choices import bind_public_choice_actions
from spireshift.representations import build_model_input

ENCODER_ID = "public-full-run-complete-choices-v2"
SCHEMA = "unified-full-run-public-policy-v2"
DIRECT_FEATURES = (*LEGACY_DIRECT_FEATURES, "select_bundle", "already_selected_bundle")


def _printed(binding: dict[str, Any], catalog: dict[str, dict[str, Any]]) -> dict[str, Any]:
    value = dict(binding)
    if "card" in value:
        value["card"] = printed_card(value["card"], catalog)
    if "cards" in value:
        value["cards"] = [printed_card(c, catalog) for c in value["cards"]]
    return value


def public_full_run_input(
    ruleset: RulesetIdentity,
    observation: Observation,
    actions: tuple[LegalAction, ...],
    catalog: dict[str, dict[str, Any]],
    dimension: int,
) -> FullRunInput:
    representation = build_model_input(ruleset, observation, actions)
    view = choice_view(observation)
    menu_open = view.combat_selection is not None or view.bundle_selection is not None
    # Reuse the frozen ordinary phase bindings. For menus, obtain public context
    # with no candidates, then replace its truncated menu before any model scoring.
    base = full_run_input(ruleset, observation, () if menu_open else actions, catalog, dimension)
    context = {**base.context, "difficulty": view.fixed_profile}
    raw = observation.public_state["observation_vector"]
    if view.phase == "combat":
        menu = view.combat_selection
        if menu is None and (raw[183] or raw[184]):
            raise ValueError("Combat vector reports a menu missing from the public readout")
        if menu is not None:
            cards = menu["cards"]
            prefix = [
                v
                for c in cards[:10]
                for v in (
                    c["card_id"],
                    int(c["upgraded"]),
                    c["enchantment_id"],
                    c["enchantment_amount"],
                )
            ]
            if (
                raw[183] != menu["selection_kind_id"]
                or raw[184] != len(cards)
                or raw[185 : 185 + len(prefix)] != prefix
            ):
                raise ValueError("Combat vector and complete public menu disagree")
            context["combat"] = {
                **context["combat"],
                "selection_cards": [printed_card(c, catalog) for c in cards],
                "selection_metadata": {k: v for k, v in menu.items() if k != "cards"},
            }
    bundle_cards = []
    if view.bundle_selection is not None:
        offer = observation.public_state.get("bundle_offer", [])
        selected = view.bundle_selection["selected_bundle"]
        bundle_cards = [
            printed_card({"card_id": i, "upgraded": False}, catalog)
            for i in (offer[selected * 3 : selected * 3 + 3] if selected >= 0 else [])
        ]
        # Selected bundle index is only a locator. Learn the shown contents and
        # confirmation capability, rather than assigning quality to index 0 or 1.
        context["bundle_selection"] = {
            "confirmation_enabled": view.bundle_selection["confirmation_enabled"],
            "selected_cards": bundle_cards,
        }
    bindings = (
        bind_public_choice_actions(
            view, actions, bundle_offer=observation.public_state.get("bundle_offer", [])
        )
        if menu_open
        else base.bindings
    )
    shared: dict[str, float] = {}
    _tokens(context, "state", shared)
    rows = []
    for i, binding in enumerate(bindings):
        printed = _printed(binding, catalog)
        direct = (
            {j: v for j, v in base.vectors[i].items() if j < len(LEGACY_DIRECT_FEATURES)}
            if not menu_open
            else {0: 1.0}
        )
        if menu_open:
            kind = binding["kind"]
            if kind in DIRECT_FEATURES:
                direct[DIRECT_FEATURES.index(kind)] = 1.0
            if kind == "confirm_bundle":
                direct[DIRECT_FEATURES.index("confirm")] = 1.0
                printed.pop("selected_bundle")
                printed["selected_cards"] = bundle_cards
            if kind == "select_bundle" and binding["already_selected"]:
                direct[DIRECT_FEATURES.index("already_selected_bundle")] = 1.0
            card = printed.get("card", {})
            if card:
                direct[DIRECT_FEATURES.index("card_quality")] = (
                    card.get("damage", 0) + card.get("block", 0)
                ) / (10 * max(1, card.get("cost", 0)))
                direct[DIRECT_FEATURES.index("card_is_power")] = float(card.get("type") == "Power")
                direct[DIRECT_FEATURES.index("card_is_curse")] = float(
                    card.get("type") in {"Curse", "Status"}
                )
        tokens = dict(shared)
        _tokens(printed, "candidate", tokens)
        values = dict(direct)
        for token, amount in sorted(tokens.items()):
            digest = hashlib.sha256(f"{ENCODER_ID}|{token}".encode()).digest()
            index = len(DIRECT_FEATURES) + int.from_bytes(digest[:8], "big") % (
                dimension - len(DIRECT_FEATURES)
            )
            values[index] = values.get(index, 0.0) + (1 if digest[8] & 1 else -1) * amount
        rows.append({j: max(-5.0, min(5.0, v)) for j, v in sorted(values.items()) if v})
    return FullRunInput(
        representation.representation_hash,
        tuple(a.action_id for a in actions),
        bindings,
        tuple(rows),
        context,
    )


class PublicFullRunModel(FullRunModel):
    def body_dict(self) -> dict[str, Any]:
        return {**super().body_dict(), "schema_version": SCHEMA, "encoder_id": ENCODER_ID}

    def with_genome(self, genome: Sequence[float]) -> PublicFullRunModel:
        return cast(PublicFullRunModel, super().with_genome(genome))

    @classmethod
    def _from_base(cls, model: FullRunModel) -> PublicFullRunModel:
        return cls(
            model.ruleset_manifest_id,
            model.patch_id,
            model.dimension,
            model.hidden_units,
            model.catalog,
            model.card_source_sha256,
            model.genome,
        )

    @classmethod
    def from_mapping(cls, value: object) -> PublicFullRunModel:
        if (
            not isinstance(value, dict)
            or value.get("schema_version") != SCHEMA
            or value.get("encoder_id") != ENCODER_ID
        ):
            raise ValueError("A repaired player requires the new public-menu model format")
        body = {k: v for k, v in value.items() if k != "model_id"}
        if value.get("model_id") != manifest_identifier(body):
            raise ValueError("Repaired full-run model identity differs")
        # Reuse the original numerical/catalog validator after checking the new
        # schema. This is decoding, not migration or promotion of an old model.
        legacy = {**body, "schema_version": LEGACY_SCHEMA, "encoder_id": LEGACY_ENCODER_ID}
        return cls._from_base(
            FullRunModel.from_mapping({**legacy, "model_id": manifest_identifier(legacy)})
        )


def load_public_full_run_model(path: Path) -> PublicFullRunModel:
    return PublicFullRunModel.from_mapping(json.loads(path.read_text()))


def initial_public_full_run_model(
    ruleset: RulesetIdentity,
    catalog: dict[str, dict[str, Any]],
    card_source_sha256: str,
    *,
    dimension: int = 256,
    hidden_units: int = 16,
    initialization_seed: int = 0,
) -> PublicFullRunModel:
    model = PublicFullRunModel._from_base(
        initial_full_run_model(
            ruleset,
            catalog,
            card_source_sha256,
            dimension=dimension,
            hidden_units=hidden_units,
            initialization_seed=initialization_seed,
        )
    )
    genes = list(model.genome)
    linear_at = len(genes) - dimension
    genes[linear_at + DIRECT_FEATURES.index("select_bundle")] = 0.2
    genes[linear_at + DIRECT_FEATURES.index("already_selected_bundle")] = -1.0
    return model.with_genome(genes)


class PublicFullRunPolicy(FullRunPolicy):
    def __init__(self, ruleset: RulesetIdentity, model: PublicFullRunModel) -> None:
        if not isinstance(model, PublicFullRunModel):
            raise ValueError("Historical genomes must not silently use repaired inputs")
        super().__init__(ruleset, model)
        self.policy_id = f"unified-full-run-public-v2:{model.model_id}"

    def predict(
        self, observation: Observation, legal_actions: Sequence[LegalAction]
    ) -> FullRunDecision:
        actions = tuple(legal_actions)
        if not actions:
            raise ValueError("Repaired policy requires all supplied legal candidates")
        inputs = public_full_run_input(
            self.ruleset, observation, actions, self.model.catalog, self.model.dimension
        )
        logits = score_features(self.model, inputs.vectors)
        weights = tuple(math.exp(v - max(logits)) for v in logits)
        probabilities = tuple(v / math.fsum(weights) for v in weights)
        index = max(range(len(actions)), key=lambda i: (logits[i], -i))
        return FullRunDecision(inputs, logits, probabilities, index, actions[index])
