# Lifecycle ending panel: two public-fact projection gaps

E2E607/E2E608 both finish naturally in both hosts, with matching standalone
terminal persistent state and every public read. Both official Continue/native
summary proofs and clean shutdown/reset checks pass. Neither pair qualifies the
complete workflow because earlier player inputs differ. The original blocked
reports remain correct and unchanged.

The frozen original game is still v0.111.0 / 41cef1ea, with CLI56 / Connector29 /
worker24 / converter16 / layout12 / environment46. The owner run uses 556.26
wall seconds and 141.80 CPU seconds; no outer resource cap is hit. Official
gameplay CPU is 27.99 seconds for player 2 and 36.73 for player 3, below 128.

| Case | Actual decisions per host | First differing input, zero based | Difference |
| --- | --- | --- | --- |
| Player 2 / E2E607 | 106 | 47 | A locked Self-Help Book option has `is_enabled=false` in native and `true` in official. |
| Player 3 / E2E608 | 137 | 31 | An unpurchased Pendulum has no shop counter in native and `counter=0` in official. |

## Locked event enablement

Only player 2's input 47 differs, in three copies of the same fact: the option's
`is_enabled`, its referent properties and its referent enabled state. Both hosts
agree that option 2 is locked because there is no eligible Power card. The locked
option is absent from both legal menus. All 106 selected candidates match in the
diagnostic comparison; this does not admit the differing policy input.

The shipped `NEventOptionButton.OnRelease` returns immediately when the event
option is locked. Its button can nevertheless retain its generic enabled flag.
Connector29's `EventOptionSurfaceReader` exports that button flag independently
from `option.IsLocked`, although its action generation already requires both
button enablement and an unlocked option. This is inconsistent public enablement
in the Connector, rather than evidence of a different event effect in the CLI.

The next repair should derive public actionability consistently from the native
lock and button state, preserving disabled unlocked choices too. Verify the
surface, referent and legal-menu relationship together using the saved input and
source cases. Do not patch historical inputs or remove the comparison field.

## Shop relic counter visibility

Player 3 has six differing inputs, 31 through 36, all concerning the same
unowned shop Pendulum. At input 31 the difference exists only in the read-only
shop catalog; when inventory is open it also appears in the interaction surface
and referents. Every difference is an absent counter versus zero. The player's
owned relic facts agree, and Pendulum is not in either player's inventory.

The Connector's shop exporter reuses `VisibleEntityFacts.BuildRelic`, which adds
`DisplayAmount` whenever `ShowCounter` is true. Pendulum always reports that
model property as true. The shipped merchant renders an `NRelic` icon; the
separate `NRelicInventoryHolder` renders inventory counters. The CLI shop export
does not include an inventory counter. The source therefore supports a
context-specific visibility error in the Connector's shared exporter. These
captures do not demonstrate a disagreement about the value of an owned counter
or Pendulum's turn/draw mechanic.

The next repair should distinguish the actual shop renderer from owned inventory
rendering. Add source/saved cases for the same counter-bearing relic in both
contexts, including the catalog while inventory is closed. Review other shared
exporter callers against their renderer. Preserve legitimate owned counters;
do not globally strip counters, invent zeros, or change native relic rules.

## What the assessment establishes

Saved-only assessment passes in 46.24 seconds and independently reconstructs all 486 deliveries from raw
observations, full public reads, exact menus, original-player choices and
probabilities, and delivery receipts. It also rechecks both native summaries.
No game or historical action is replayed. All legal menus and selected
candidates agree diagnostically across both complete traces. Later matches are
not realigned to erase earlier differences.

Both standalone terminal fact sets compare equal. The panel comparison stops
at its first earlier mismatch, so its `explicit_ending_facts_equal=false` means
it did not reach that check; it does not establish an ending disagreement.
Official summaries are standard A8 losses: player 2 score 288/floor 11 and
player 3 score 144/floor 8. No policy actions follow terminal.

Neither pair exercises the repaired noncombat potion-use path or records a
noncombat-use lifecycle proof. Player 3 buys, discards and claims potions, then
uses Dexterity Potion in combat at input 66. The earlier focused noncombat use
and discard qualification retains its scope; this panel neither requalifies
noncombat use nor shows that repair failing.

The frozen archive, restored idle working app, original numerical weights and
full Adam states verify unchanged. All 20,590 previously protected files verify;
the expanded 21,012-file map also preserves the completed panel, raw captures and
prior preparation/qualification evidence. The first saved-only assessment completes
all four raw reconstructions but uses the wrong identity helper for the build
report's format. Its failure is preserved. The corrected assessment uses the
existing format-specific verifier without changing any original evidence.

See `artifacts/native-action-lifecycles/owner-assessment-v2/` for the sealed
assessment, exact difference timelines, source hashes and raw verification logs,
and the compact [evidence record](evidence/native-action-lifecycle-ending-result-v1.json).

## Next work and limits

Fix these two Connector projections using saved/source regressions before
another natural panel. Extend the systematic suite with semantic relationships
between fields and rendering context. The completed action-lifecycle inventory
enumerates delivery paths; it does not prove every public fact or content
interaction. Keep that distinction explicit.

The audit's separate shop purchase/removal background-task completion risk
remains open. A passed purchase in these traces does not qualify all delayed
pickup hooks. Assess that consequential lifecycle risk before broader admission.

Do not rerun `compare-action-lifecycle-endings-v1.sh` or E2E607/E2E608. No replacement
long command is prepared by this assessment. Compatibility remains blocked;
there is no training, promotion, adaptive controller, automatic follow-up or
playing-strength claim. Varied fitting-only teaching and the separate
interference comparison remain next after finite compatibility qualification.
