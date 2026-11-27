# Deferred potion acknowledgement and normalization recovery

The owner run stopped in round 63 at `train-0993-p2-normalized`, after about
12 hours 56 minutes. This is a framework acknowledgement failure. It is not a
training-budget stop or a completed strength comparison.

## Verified saved prefix

The independent audit checks every completed unit's real file hashes against its
seal and the aggregate stop, exact behavior-state requests, native ending/reset
evidence, all full actor/critic/Adam reloads and the embedded frozen reference.
It verifies **4,234 clean units: 3,984 training attempts and 249 complete fits**,
plus the initial-copy unit. There were **15,252 optimizer steps
on copies**, with zero original/source updates.

| Training lineage | Completed attempts | Losses | Capped | Act 1 clears | Act 2 clears | Fits |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Player 2 raw | 1,008 | 1,008 | 0 | 56 | 0 | 63 |
| Player 2 normalized | 992 | 991 | 1 | 48 | 1 | 62 |
| Player 3 raw | 992 | 992 | 0 | 48 | 2 | 62 |
| Player 3 normalized | 992 | 992 | 0 | 26 | 0 | 62 |

All completed terminal games are losses. The cap is
`train-0206-p2-normalized`. The failed game is a separate denominator cell.
There are **111 unstarted training games** and **768 unstarted development games**.
The training policies change each round; the 104 versus 74 Act 1 clears do not
establish which fixed final policy generalizes better. No winner is selected.

The failed game has 159 acknowledged deliveries, followed by one unknown discard
delivery with no accepted successor. Its saved native state is a Toolbox opening
generated-card selector, before the player's play phase. The interrupted profile,
marker, logs and receipts remain intact. Its prefix is diagnostic only. The
auditor's initial receipt-label check used `accepted` where this schema records
`delivered`; that failed audit receipt remains preserved. The corrected audit
changes no source game data.

## Why the discard was valid

The original game's `ActionQueueSynchronizer.RequestEnqueue` holds
combat-play-only actions in its native deferred list during `NotPlayPhase`.
It assigns the action ID later, when the original synchronizer enters play phase
and submits those exact actions in order. Its `PauseAllPlayerQueues` also clears
the player-driven cancellation flag. A deferred request is therefore different
from the End Turn cancellation branch checked by the prior adapter.

The frozen host's discard handler required an action ID immediately after the
request. The native game had accepted the request into its buffer, but the host
reported an unconfirmed enqueue. The game assembly does not need an update.

A separate support adapter accepts either the original assigned-ID proof or the
**exact newly submitted action object in the original synchronizer's buffer**.
It keeps the exact potion/slot binding in the host's pending-discard ledger,
retains the required child selector and suppresses duplicate submissions. The
original native synchronizer assigns IDs, resumes and executes the effects.
The adapter never invents an ID, marks a potion effect complete prematurely,
changes queue order, removes a legal choice or selects a card for the model.
Unknown, untracked or canceled acceptance remains an error.

The game v0.111.0 / 41cef1ea, host60, original weights/full Adam, source finals,
SDK, runtime and prior adapter artifacts stay fixed. The separately reproduced
new adapter has SHA-256
`810fbd16f988ca13867f589f55cd575f63442842f3e138c6f452c2573902c559`.
The original card cleanup, merchant overlay and cancellation guards remain
linked unchanged. Native pre-ID buffer evidence is private qualification data
and never enters policy inputs.

## Scoped qualification

| Control | Verified boundary/effect |
| --- | --- |
| Opening selector → discard + use | Both original action objects are natively buffered without IDs; the required selector stays current; both bottles disappear after the native handoff; Blood Potion heals exactly 16 HP once |
| Opening selector → two discards | Both distinct bottles are buffered in order, disappear after selection and leave no pending discard or deferred action |
| Duplicate/stale requests | Both requests are rejected before enqueue in each opening case; the native state and existing buffer remain unchanged |
| Player-turn card selector | Assigned-ID queued discard remains available before selection, is hidden after acceptance and executes after its child |
| End Turn card selector | Canceled use/discard requests are not offered and are rejected before enqueue with unchanged state |
| Noncombat belt | Native use/discard effects and clean reset still pass |
| Two fresh production games | Actual frozen normalized/raw correction states choose their own complete normal-start games, reconstruct 468 deliveries and finish as native losses; full source Adam stays exact |

The five isolated lifecycle cases verify 20 SDK deliveries plus six negative
probes. Both production games reach their natural Act 1 boss loss. These are
execution controls, not model-strength evidence or imitation labels. The game
and original/source full states are unchanged after every control.

The initial control harness stopped before a world because its parent output
directory was absent. A later prepared case used direct relic-list replacement
without assigning native relic ownership and failed before the opening choice.
Those attempts remain preserved; the final control uses native relic obtain
and fresh declared worlds. This fixture repair changes no production path.

This adds opening-selector × deferred discard/use/multiple-bottle coverage to
the shared lifecycle evidence. The earlier post-End-Turn cancellation repair
alone did not cover it. Broader mechanics combinations and official Connector
checks remain tracked under #149; this is not complete-mechanics or official
parity qualification.

## Continuation and owner command

The v2 journal imports the 4,234 verified seals from their original paths and
restores all four complete optimizer lineages. Imported and failed units cannot
be begun again. The failed world stays counted as failed and supplies no labels;
its remaining round has fifteen possible complete training worlds, still above
the unchanged twelve-world fit minimum. The cap remains excluded from fitting.
No failed-world replay, replacement, old-menu relabeling or duplicate PPO update
is allowed. Parent and continuation journals are locked through execution.

The actual restore control must reach `train-0994-p2-normalized` with the exact
unchanged round-62 normalized behavior state and stop **before** beginning it.
It launches zero games and makes zero updates. Original raw player 2 restores
round 63; the other three lineages restore round 62.

This restore passed and verified all four full-state IDs, with zero new games
or updates. The five native lifecycle controls took 28.15 seconds; the two
production controls took 39.73 seconds. All frozen game/source-state checks pass.

The model, input features, reference actor, normalization treatments, objective,
credit, rewards, PPO settings, world lists, fixed round-64 selection and per-game
limits remain unchanged. Only the native acknowledgement adapter and explicit
failed-cell continuation are new. Freeze finals before the fresh three-arm
development panel. No reserved final test, promotion, controller or next training
study follows automatically.

Close STS2 and run the new command:

```bash
bash scripts/continue-a8-hidden-normalization-v2.sh
```

Allow **3–5 hours** for 111 remaining training and 768 fresh comparison games,
with the original 48-hour outer cap. Output goes to
`artifacts/native-hidden-normalization/study-v2`; original data stays in `study-v1`.
The script sets the fixed numerical environment and resumes exact clean seals
only. If another request is uncertain, it stops and preserves evidence.

Exact source, audit, adapter, native-control and restoration receipts are linked
in the [evidence](evidence/native-hidden-normalization-recovery-v2.json).
