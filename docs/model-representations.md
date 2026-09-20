# Compositional model representations

SpireShift converts each public observation and its exact legal-action set into a versioned model
input before a policy, value model, or search procedure sees it. The v1 encoder is
`mechanics-compositional-v1`.

The contract has five channels:

- the decision type, such as combat, path, reward, or shop;
- global mechanics and progression fields;
- persistent run resources, including HP, gold, deck, relic, and potion properties;
- variable-length entity groups for the player, cards, enemies, statuses, rewards, and other
  objects; and
- one feature group per legal candidate action plus an aligned legality mask.

Every scalar has a normalized path, list-position indices, value type, and semantic role. Semantics
distinguish mechanics, persistent resources, status, capability, location, progression, and
identity. Persistent collection members appear in the resource channel and retain their natural
mechanic or identity semantic inside their entity. This gives a run-level model a direct resource
view without discarding card, relic, or potion structure.

Candidate position and action kind are model inputs. The adapter's `source_action_id` remains in the
serialized contract only as the output handle used to turn a selected candidate back into an exact
legal action. `CompositionalModelInput.model_dict()` and the vectorizer omit that handle. Renaming
action IDs therefore changes the provenance hash but cannot change model features or scores.

## Patch and information boundaries

The encoder accepts normalized fields it has not seen before instead of requiring a frozen card,
enemy, or action vocabulary. Known categorical identities remain available, while mechanical
properties such as cost, damage, HP, status amount, target location, and capability flags are
represented separately. New fields and categories can therefore produce useful features without a
code release.

Inputs must match the ruleset's patch and observation schema, and their public-state hash is
recomputed before encoding. Keys associated with hidden futures, RNG state, seeds, or draw order
fail closed in both state and action payloads. The representation never reads adapter-private or
simulator-private state.

The representation hash covers the full serialized contract, including ruleset identity,
predecessor state, and action handles. A separate model-feature digest covers only values allowed to
enter a model. This separation lets datasets audit provenance while tests verify that operational
handles do not leak into learning.

## Sparse reference vectorizer

`signed-sha256-feature-hash-v1` is a deterministic, dependency-free reference vectorizer. It hashes
typed feature tokens into a configurable sparse dimension, with 4,096 buckets by default. Numeric
features contribute both a presence marker and their value, so a real zero is distinguishable from
an absent field. Signed hashing reduces systematic collision bias and supports previously unseen
paths and categories.

The sparse vectorizer establishes an executable baseline and stable fixtures. Learned encoders may
replace it later, but they must consume the same public, candidate-aligned contract and preserve the
action-handle boundary. Collision rates and vector dimension must be reported with any benchmark
that uses the hashed baseline.

## Commands

Build the checked mock representation:

```bash
uv run spireshift represent mock --seed 7
uv run spireshift represent mock --seed 7 --vectorized --dimension 4096
```

Build a representation from a recorded STS2MCP payload without contacting the game:

```bash
uv run spireshift represent live recorded-state.json \
  --output artifacts/model-input.json
```

The JSON contracts are [model-input-v1.json](../schemas/model-input-v1.json) and
[vectorized-model-input-v1.json](../schemas/vectorized-model-input-v1.json). The checked live-corpus
evidence is summarized in [model-representation-v1.md](evidence/model-representation-v1.md).
