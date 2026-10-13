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

## One next owner command

Close STS2, then run from the repository:

```bash
bash scripts/compare-combat-effects-v1.sh
```

Expected duration is **6–9 minutes**, based on the short cases, with a 15-minute elapsed cap,
1,800 CPU seconds, 8 GB memory and 6 GB tracked files including the shared app pool. Read-only
preflight checks the native build, runtime, localization, SDK, Host, benchmark policy and idle
worker before allocating the batch workspace. Eight cases test two independent seeds and both
fixtures, each twice. All run serially on the one shared app, with a fresh profile per case.

Each case reports progress. The first disagreement stops the batch and keeps failed evidence;
missing cases remain in the denominator. Repeated public facts/action semantics must match.
Success is followed only by saved-result verification. Reinvoking a completed batch displays
and audits it without playing again; an incomplete attempt is preserved and requires inspection.
No full run, training, adaptive controller or next experiment follows automatically.

## Remaining limits

Native combat exposes potion discard while the shipped Host currently omits it. This comparison
explicitly excludes discard from its effect menu; it does **not** establish complete combat-action
parity. Fix and test that gap under #145 before general training admission. Other selectors,
remaining modes, later acts, actual endings and startup through the shipped new-run lobby still
need qualification. Historical panels do not automatically qualify a changed Host binary.
Original headless diagnostics are preserved; a passing scoped result is not a clean-runtime claim.
Full-run throughput and a new A8 neural lineage remain [#146](https://github.com/benyanc/spireshift/issues/146)
work after the required mechanics checks. Adaptive thinking stays behind foundation readiness.
