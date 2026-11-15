# Shared archive replay owner matching

The versioned matcher reconstructs recorded shop purchases, removal
cancellation and opening hand replacement on the frozen Ironclad/A8 host.
The batch continues to use the terminal-victory objective and separate
training, development and final-test worlds. The historical pilot remains
available under its original matcher and declaration.

- A reward-tagged card acquisition at the merchant can share the following
  purchase when the current shop stock, card identity, slot, price, gold and
  new deck copy corroborate it. A current reward offer keeps its owner.
  Corroborated ordinary card purchases use the same checks.
  The native action must bind to the current stock and price. Its successor
  must have the recorded gold and deck.
- An empty human pick and the linked removal decline establish a cancellation.
  The reader orders the cancellation before later purchases, even when the
  decline is logged after them. Native must expose the matching removal
  service and a cancelable child with the recorded eligible cards. Cancel
  returns to the open shop with the same gold, deck and available service.
- An opening discard requires a first-turn pick and the recorded discard and
  replacement draws. The matcher checks the combat owner, starting enemy
  roster and current hand. It resolves exact card copies through the same
  atomic and ordered-answer matcher used for other selectors. The playable
  successor must have the recorded hand and discard pile.

## Verification

The saved audit reconstructed 993 existing deliveries, including all 896
Queen deliveries and four confirmed card purchase successors. The two
clean pilot stops now bind the merchant inventory action and the exact
three-card discard. Those two historical boundary actions were unsent.
A separate native shop control proves cancellation and return with all
three prior deliveries reconstructed. A saved ordered-answer control proves
two local factors, one native commit and the post-discard hand and pile.
The controls supply diagnostic evidence.

The previously source-rejected Aeonglass journal screened in and ran once
from a fresh Neow start. It cleared Act 1 and reached Act 2 floor 30 with
506 verified deliveries, including paid shop removal. It stopped cleanly
when two separate 15-gold claims were present. The journal records both
claims, and the matcher could only narrow the first claim to two native
bindings. The late Act 3 cancellation was reached in the source audit and
verified against the separate saved native control. The fresh prefix remains
diagnostic. The batch still has one verified winning world, below the
three-world fitting gate.

The frozen build, four full checkpoint and Adam states, and shared profile
verified exactly. This work made zero optimizer updates.
[Evidence](evidence/native-a8-archive-owners-v2.json)

## Commands

Reconstruct the saved checks from the private journals and receipts.

```bash
uv run --no-sync python scripts/verify-a8-archive-owners-v2.py
```

The [versioned runner](../scripts/qualify-a8-archive-batch-v2.sh) verifies the
sealed owner-matching batch on repeat. A new batch takes a separate pinned
declaration and fresh sources. The next replay gap is separating repeated
reward claims by their occurrences and native effects.

```bash
bash scripts/qualify-a8-archive-batch-v2.sh
```
