# Reward, pack and merchant selection compatibility

This work repairs player-visible information and delivery of existing choices. Both
original players, their numerical weights and every Adam moment/counter stay fixed.
The previous four-pair canary is complete and preserved. It delivered 790 policy
choices across eight starts, but found reward/pack input differences and rejected a
legitimate merchant-removal catalog. Its result grants no compatibility or training
admission. The historical selection launcher is no longer the next command.

## Repaired flows

- Card rewards export actual physical card copies, current energy/star costs,
  previews and detail reads. Alternative buttons come from the native reward
  selector. Skip, reroll or relic alternatives remain distinct; a mandatory reward
  never gains an invented Skip. The same pending reward retains its identity when
  a card preview returns, so declining it can be remembered after other rows change.
- A pack choice means take the entire chosen pack. The CLI already commits that
  choice. The official adapter executes its advertised preview and confirmation,
  checks the exact owner and cards, and acknowledges the model only after delivery
  and completed transition. Preview/cancel UI does not become a second model choice.
  Uncertain inputs are never resubmitted. Reward Continue also waits until its
  screen owner has actually departed, without submitting another input during
  the brief UI delay.
- Merchant removal retains its merchant owner while the selector is open. The
  shop catalog is allowed there only under the explicit committed-card contract.
  Prices, stock, discounts, affordability and disabled controls stay visible;
  a read-only catalog cannot authorize purchases from the selection overlay.

The integration checks also found two source omissions. Boss names must come from
encounter titles, not a guessed member monster name (The Kin versus Kin Priest).
Combat pile descriptions must use the native public preview under current powers,
with preview variables cleared afterward. The official pile reader refreshes its
view before formatting as well, so a previous hand/target preview cannot leak
into a later pile read. A Strength bonus must not disappear just
because a card moves from the hand into a public pile. Status hover text uses the
same visible renderer as cards, retaining an energy image as an explicit glyph
rather than leaking its resource path.

Empty belt copies may collapse only when the same owned belt is actually empty.
Nonempty belts, unfamiliar facts, card-copy differences, legal alternatives and
view ownership remain explicit. The reversible layout retains original frames and
raw action bindings. It cannot turn later divergent states into matched evidence.

## Checks and qualification

The saved bank contains 1,642 completed public frames plus 20 generated envelopes.
Every conversion reconstructs its source and preserves its raw action menu; 3,306
frozen-player probes are diagnostic inference only. A protection receipt checks
3,609 earlier files, including both full original player states and old evidence.

Targeted tests cover mandatory and optional rewards, exact copies, missing flags,
zero/X star costs, stable reward identity, pack preview/commit ownership, wrong or
changed packs, uncertain confirmation and merchant-catalog ownership. A full decoder
check uses a recorded native pack view; lower-level surface tests alone were not
sufficient to catch missing completeness metadata. The blocked development
attempts and their source snapshots remain preserved, without uncertain-seed replay.

Earlier completed pack checks exercise preview and confirmation in the shipped
app and independently reconstruct their choices/receipts. Their boss-name, event
text and completed-reward discrepancies remain historical evidence. Only the
accepted current tuple listed in the portable evidence gates the next comparison.
The active source tuple is CLI v44 / official connector v19 / worker v15 / shared
helper v10 / typed layout v7 / shared environment v26.

Current offline v13 and targeted control v11 pass. The live check takes 88.16
seconds: all 32 complete inputs and action menus match in both hosts, including
a card reward, reward continuation and a committed pack. Independent saved-only
verification reconstructs all 64 choices and receipts. Both decks grow from 11
to 14 cards with exactly the chosen pack's three cards; every prior visible card
is unchanged. The check verifies exact app/profile/archive restoration and creates
no game-app copies. The broader comparison is preflighted and unstarted.

The focused suite passes 11 Python tests, 26 Node cases, strict typing on 632
source files, formatting and the local C# protocol contract. Full repository
checks on the final files remain for the owner launcher: the earlier capped
check does not grant a success receipt. See the portable
[implementation evidence](evidence/native-selection-flows-v1.json).

Completed combat rewards use the same empty reward list in both hosts. The public
boss-room fact is retained explicitly. A merchant catalog declares its read-only
slots before the diagnostic graph is built. In-combat card selectors retain hand
and enemy context as views while declaring each selectable card only once. This
repairs a captured Armaments selector with three physical Defend cards. Other
inspectable hand/enemy/player operands remain declared exactly once. Nested combat
selectors also retain the actual public draw/discard/exhaust pile reads, preserving
the connection between a selectable card and its pile copy. The repaired saved
Headbutt input and action menu match the official frame completely. No hidden draw
order is exposed.

Rendered event text uses one typed body name. Its text and named amounts are
unchanged, conflicting text views are rejected, and original field names remain
recoverable in the layout evidence.

These are finite input/delivery checks, not proof of every content interaction,
complete full-game parity or playing strength. Source changes invalidate the
corresponding qualification. No model training or promotion follows automatically.

## Next owner command and time allowance

Close STS2 and run this one command from any directory:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/compare-selection-flows-v1.sh
```

The next command first allows **10 minutes for full repository checks**, then
**30 minutes for the comparison**, with six minutes per pair. Successful checks
are cached against the exact files; a capped check cannot be mistaken for a pass.
It can therefore take up to **40 minutes altogether**. It checks both unchanged players on two fresh canonical worlds: four
paired prefixes, up to 128 model choices per host. One fixed app is reused with
isolated profiles; no app copies are created. The game count does not increase
when the launch allowance changes.

The launch budget has its own versioned file and receipt. It is separate from the
experiment identity used for saved units, so increasing an operational allowance
will not discard completed pairs or change the scientific plan. Each receipt keeps
the exact allowance and current-launch duration. Completed pairs are reused after
an interruption; incomplete or uncertain attempts remain preserved for inspection.
A stuck individual pair still stops at its own cap.
