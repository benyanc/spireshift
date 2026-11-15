# Current combat effects on the frozen actual game

This is finite mechanics qualification under [#145](https://github.com/benyanc/spireshift/issues/145),
with Ironclad/A8 and the separately frozen v0.111.0 game. Terminal full-run victory remains the
project objective. These privileged fixtures do not train a player or establish playing strength.

## Completed short checks

Both targeted native-versus-shipped comparisons and their saved audits pass. Corruption makes
both Defends playable at zero energy, reduces their displayed cost to zero and exhausts both.
The second fixture separates Strength 7 from Dexterity 5, keeps permanent Strength 2 after the
turn, removes temporary Dexterity, consumes both potions and advances Pen Nib's counter from
zero to one. Both prefixes reach the second turn through the actual game's reshuffle tutorial.

The checks compare current descriptions, costs, playability, owned player/enemy statuses,
HP/block/energy, piles, public deck reads, relic counters, potions and the offered play/use/end-turn
choices. Only whitespace is normalized in text; amounts, names, word order and glyph multiplicity
remain significant. Every action binds through the current public menu. The initial five-card
decks and two potions are assigned explicitly, and the native game obtains Pen Nib. Continue
imports the native checkpoint with the bound synthetic full-content/all-acts-seen profile and
fresh enabled tutorials. Real account history is untouched.

These are two distinct seed/scenario checks, **not the eight-case repeat panel**. They cover
18 observations, 16 effect decisions, 26 game/UI actions, six combat tutorial pages and two
reshuffle confirmations. Their wall times were **40.704 and 51.283 seconds**. Both reuse the same
app/inode with distinct profiles, zero new app copies and verified resets. Independent saved-only
reconstruction reproduces both audits without launching games.

## Repairs found by comparing with the game

The wrapper rendered a hand card's description after clearing the native effect preview. With
Weak active, it described Strike as 6 damage while the game displayed 4. V15 renders the actual
preview first and always clears it in `finally`, including formatter failures. Visible status
export now fails explicitly on an error instead of silently omitting the status. A native read
after fixture setup also replaces the stale initial observation.

The shipped Host did not expose the fresh reshuffle confirmation, which paused drawing the next
hand. Host v8 binds the exact visible enabled native `NShuffleFtue` button. That confirmation
resumes a pending draw; it is not treated as a tutorial with no game effects. Unknown modals stay
unsupported. Current costs/effects are calculated by the original game, not handwritten rules.

Two baseline/two repaired native builds reproduce in **16.014 seconds**. Two fresh Host builds
reproduce in **7.382 seconds**. The current wrapper also passes **841 subchecks across 28 native
combat/rest/shop fixtures**. Repository checks pass **1,209 tests**, formatting/lint/types and the
C# protocol contract. Fifteen synthetic public-action/reshuffle tests pass. Each saved case passes
one reconstruction and rejects fifteen deliberate corruptions of amounts, ownership, costs,
counters, receipts, runtime, seed, deck reads or the second-turn tutorial evidence.

Earlier failures remain saved. Superseded uncommitted development helper sources and recipes
are retained with an exact path/hash index under private artifacts; qualified helpers and recipes
stay in the repository. [Evidence](evidence/actual-engine-v0.111.0-combat-effects-v1.json) records
all current identities, successful checks, rejected attempts and limits.

## Completed owner repeat panel

The owner completed all eight planned cases: zero failures or unattempted cases, with identical
public prefixes for each repeat. Two independent seeds and both assigned fixtures were each
tested twice. Independent saved-only reconstruction exactly reproduces the recorded audit:
**72 observations, 64 effect decisions, 104 game/UI actions, 24 combat tutorial pages and eight
reshuffle confirmations**, with no games launched by the audit.

Resource wall time is **404.901 seconds** (6 minutes 45 seconds), CPU **182.310 seconds** and peak
memory **945,356,800 bytes**; no cap was hit. Eight distinct profiles reuse one app/inode with
zero new app copies and verified resets. Case evidence occupies 71,543,111 logical bytes and
external private profiles 1,461,424 bytes; final tracked storage includes the one existing app.
Logical APFS sizes do not measure independently allocated blocks.

The stage is complete and needs no rerun. `scripts/compare-combat-effects-v1.sh` displays and
audits the saved result without game replay. [Completed panel evidence](evidence/actual-engine-v0.111.0-combat-panel-v1.json)
records its identities and limits. The original implementation evidence retains its then-pending
owner panel. No full run or training followed.

## Remaining limits

The Host used in this completed panel omits combat potion discard. This comparison
explicitly excludes discard from its effect menu; it does **not** establish complete combat-action
parity. A separate [exact-slot discard package](actual-engine-combat-potion-discard.md) now passes short checks;
its repeat panel is pending before general training admission. Other selectors,
remaining modes, later acts, actual endings and startup through the shipped new-run lobby still
need qualification. Historical panels do not automatically qualify a changed Host binary.
Original headless diagnostics are preserved; a passing scoped result is not a clean-runtime claim.
Full-run throughput and a new A8 neural lineage remain [#146](https://github.com/benyanc/spireshift/issues/146)
work after the required mechanics checks. Adaptive thinking stays behind foundation readiness.
