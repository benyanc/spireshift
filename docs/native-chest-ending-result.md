# Natural ending panel after the chest repair

The owner completed E2E603/E2E604 on 2026-11-03. Both workflow pairs remain
blocked. The official summary correction now passes a complete natural ending
and independent saved verification. Neither game reaches a chest, so this panel
adds no chest coverage and does not revoke the earlier qualified Take/Skip
controls. Preserve both new worlds and all historical failures; do not rerun the
completed launcher or replay a rejected action.

| Case | Matched policy inputs before the stop/first difference | Native result | Official result |
| --- | --- | --- | --- |
| Player 2 / E2E603 | All 36 observed inputs match | Explicit loss after 127 choices | 36 acknowledged choices, then rejected tutorial dismissal during combat entry |
| Player 3 / E2E604 | 45 inputs; first difference at zero-based index 45 | Explicit loss after 129 choices | Explicit loss after 129 choices; native Continue and summary proof pass |

All four host shutdowns and both official app/profile/archive resets pass. The
outer run takes 384.60 seconds and 162.34 CPU seconds, with no outer cap. Neither
official run exhausts its 128-gameplay-CPU-second budget. Frozen game v0.111.0 /
41cef1ea, CLI55 / Connector26 / worker24 / converter16 / layout12 / environment43
and both original complete players/Adam remain unchanged.

## Player 2: tutorial published during an incomplete background transition

The last acknowledged model choice selects the unknown room at map coordinate
(3,4). The official game then shows `map_select_ftue`, with the current enabled
`Got it!` presentation control. The first interactive snapshot still declares
the underlying context `unknown`, with the reason that a complete player-visible
projection is not yet available. Before delivery, that context becomes combat.
Reads, referents, hidden-information declarations and the visible HUD also change.
Ornamental Fan's counter changes from absent to visible at 2; it must not be
treated as zero, rewritten or diagnosed as a native-versus-official counter-rule
disagreement from this capture.

The tutorial surface and exact bound action themselves stay unchanged, but the
full expected snapshot becomes stale. The real receipt is
`not_delivered / stale_snapshot`. The generic "uncertain delivery" exception does
not establish that the click executed. No dismissal or gameplay action was
resubmitted. All 36 earlier gameplay acknowledgements remain independently
verifiable. The official game stays incomplete and blocked.

The next repair should qualify the tutorial's underlying context/entry readiness
before its first presentation submission. Preserve the complete raw transition
and actual HUD values. Keep the no-resubmission rule; do not conceal the change
through a counter alias, dropped facts or retry of E2E603. A source/state-transition
regression using this saved capture belongs before a new owner panel.

## Player 3: parameterized display markup leaks into the native event body

The first difference is Aroma of Chaos's body at input 46 (zero-based index 45).
The native text contains the opening display token
`[rainbow freq=0.3 sat=0.8 val=1]`; the official rendered body contains the same
words without that token. The complete menu keys agree at this first difference.
The CLI's current tag recognizer accepts only a restricted tag shape without
spaces or decimal parameter values. It removes the closing tag but retains the
parameterized opening tag. This is a public input export mismatch on the same
game build; the actual model input remains different and the report stays blocked.

Fix the native visible-text renderer against the frozen game's supported display
markup. Inventory the parameterized tag forms and add saved/source rendering
regressions, preserving image glyphs, amounts, multiplicity and unfamiliar facts.
Do not apply an arbitrary text filter solely to make the two logs equal. The
assessment's one-token removal is a diagnostic explanation, not modified raw
input, a repaired execution or an admitted new source tuple.

Despite that earlier input difference, the official path reaches an explicit
loss within 77.15 gameplay CPU seconds, delivers Continue once and reaches its
native summary. The complete proof was retained before validation. Independent
verification reconstructs all 129 choices/receipts and verifies the actual
`floor_reached` summary schema, terminal game facts, persistent state and summary
deck reads, with zero policy actions after termination. Both final ending fact
structures also compare equal as a separate diagnostic; this does not realign or
admit the earlier mismatched prefix as a complete workflow.

## Saved assessment and next work

The separate saved-only assessment takes 27.47 seconds and reconstructs all
421 acknowledged gameplay deliveries: native 127 + 129, official 36 + 129.
The three completed ending hosts account for 385 deliveries. The stopped official
36-choice prefix is checked in an explicitly labelled diagnostic copy with a
recovery manifest. Original recipes, 384-choice limits, reports, raw journals,
rejected tutorial receipt and incomplete attempt are unchanged. It is not ordinary
PPO experience or an ending qualification.

All 20,108 protected prior files, both complete original numerical players/Adam,
the frozen archive and restored shared app verify. No game is replayed, optimizer
updated, checkpoint promoted or automatic follow-up launched. Source and evidence
receipts are in `artifacts/native-chest-repair/owner-assessment-v1` and
[the result evidence](evidence/native-chest-ending-result-v1.json).

Next repair tutorial/combat-entry readiness and parameterized visible-text
rendering using targeted source/saved checks, then freeze any new short controls
and owner proposal. No next long command is prepared. Do not rerun
`scripts/compare-chest-endings-v1.sh` or E2E603/E2E604. The finite compatibility
gate remains blocked; preserve the already completed short chest qualification
and the newly verified summary proof. After the required workflow passes and is
assessed, return to the planned varied fitting-only teaching and separate
interference comparison, without an exhaustive content matrix.
