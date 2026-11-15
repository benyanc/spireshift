from __future__ import annotations

import copy
import time

import numpy as np
from test_native_action_context import score
from test_native_rest_exploration import rest

from spireshift.native_public_state import public_state_facts
from spireshift.native_public_value import fit_value
from spireshift.native_public_value_study import SETTINGS
from spireshift.native_public_vocabulary import PublicVocabulary, source_group
from spireshift.native_value_credit import public_value_features


def test_large_combat_subtree_cannot_evict_deck_relic_or_menu_fields() -> None:
    rows = []
    for i in range(4):
        row = {f"context/interaction/huge/{k}/number": float(i) for k in range(3000)}
        row.update(
            {
                f'context/{part}/identity/literal="CARD_{i}"': 1.0
                for part in ("persistent", "reads", "referents")
            }
        )
        row[f'menu/subject/cost/literal="{i}"'] = 1.0
        row["context/interaction/schema/literal=constant"] = 1.0
        rows.append(row)
    vocabulary = PublicVocabulary.fit([rows[:2], rows[2:]], 20)
    assert {source_group(name) for name in vocabulary.names} == {
        "interaction",
        "persistent",
        "inventory",
        "entities",
        "menu",
    }
    assert not any("constant" in name for name in vocabulary.names)
    _, counts = vocabulary.encode(rows[0])
    assert counts["inventory_represented_facts"] and counts["persistent_represented_facts"]
    assert counts["menu_represented_facts"] and counts["unrepresented_facts"] > 0


def test_encoder_and_value_fit_learn_an_identity_interaction_with_identical_counts() -> None:
    # Completely artificial returns establish numerical learnability, not card quality.
    publics = []
    for card, relic in (
        ("CARD_A", "RELIC_A"),
        ("CARD_A", "RELIC_B"),
        ("CARD_B", "RELIC_A"),
        ("CARD_B", "RELIC_B"),
    ):
        p = copy.deepcopy(rest())
        p["context"]["persistent"]["player"]["relics"] = [{"definition_id": relic}]
        p["context"]["reads"] = [
            {"kind": "run_deck", "content": {"card_count": 1, "cards": [{"definition_id": card}]}}
        ]
        publics.append(p)
    facts = [public_state_facts(p) for p in publics]
    vocabulary = PublicVocabulary.fit([facts] * 4, 1024)
    coarse = np.asarray([public_value_features(p, score())[0] for p in publics])
    assert all(np.array_equal(row, coarse[0]) for row in coarse)
    rich = np.asarray([(*c, *vocabulary.encode(f)[0]) for c, f in zip(coarse, facts, strict=True)])
    y = np.asarray([0.1, 0.3, 0.3, 0.1])
    model, _ = fit_value(
        np.tile(rich, (4, 1)),
        np.tile(coarse, (4, 1)),
        np.zeros(16),
        np.tile(y, 4),
        list(range(16)),
        (0.2, *((0.0,) * 19)),
        {**SETTINGS, "epochs": 240, "learning_rate": 0.02, "l2": 0.000001},
        0,
        time.monotonic() + 10,
    )
    predicted = model.predict(rich, coarse, np.zeros(4), [21, 22, 23, 24])
    assert np.square(predicted - y).mean() < 0.00001
