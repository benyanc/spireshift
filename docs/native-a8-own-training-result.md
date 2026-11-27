# Model-only A8 training result

The first full-menu PPO run completed all 72 planned games and all four
training rounds. Both copies changed and advanced their full Adam states,
from 5,658 to 5,742 for player 2 and from 6,045 to 6,135 for player 3.
The frozen build, runtime, localization, shared profile and all four
reference checkpoints passed verification.

| Partition | Native wins | Act 1 clears | Act 1 bosses reached | Mean maximum floor |
| --- | ---: | ---: | ---: | ---: |
| Training | 0/48 | 0/48 | 7/48 | 8.85 |
| Development originals | 0/12 | 0/12 | 0/12 | 9.75 |
| Development PPO finals | 0/12 | 0/12 | 0/12 | 9.08 |

The 24 development games cover six matched worlds, with both policies
and both initializers on each world. Player 2's mean floor fell from
10.17 to 8.83. Player 3 held at 9.33. These differences describe this
panel. Every game was an explicit native loss, with zero caps,
failures or unattempted cells. The observed win and act-clear counts
provide no basis for promoting either final.

## Decision framework

The saved audit checked 78 seals and 4,188 files. It matched 10,937
model-owned choices to the complete advertised menus, raw receipts
and successor snapshots. All observed games ended in Act 1. The
coverage applies to the menus and endings reached in these games.
Later-act interactions, compound answers and a natural victory remain
separate coverage checks. There were zero launches and optimizer
updates in the audit.

The focused follow-up reproduced an advertised Trial Double Down
action that fails in headless before the abandon confirmation.
The 72 game journals never offered that action. The matched Architect
fixture produced an explicit native victory with run saving disabled
and valid map history. Its three forced boss defeats place it in
diagnostic scope. The same saved victory identity also passed the
ending verifier with a deliberately contradictory loss label.
The native dead flag is true at that victory endpoint, so the loss
fallback must defer to a completed native victory. All 72 study
identities independently show game over outside a victory room.
Use the [focused mechanics evidence](evidence/native-a8-own-mechanics-v1.json)
for the two regressions and the preserved preliminary fixture stops.

## Learning signal

All 7,089 training decisions came from 48 losses. The declared return
therefore depended entirely on final floor, with only five to seven
distinct returns per 12-game batch. On the saved training paths, 197 of
245 observed combat floors reached native rewards. That supplies
verified intermediate success evidence even when the full run is lost.

The audit reconstructed the cross-fitted credit and measured the actor's
data gradient at each round's behavior checkpoint. Comparing the two
halves of a batch gave opposing directions in 323/462, 9/462, 210/462
and 349/462 possible splits, in player and round order. These splits
share the same 12 games in each round. They show uneven agreement across
batches and do not isolate the cause of the development result.

## Priority after the result

Four fresh prepared practice starts exercised Overgrowth, Underdocks,
Hive and Glory. The model chose all 226 delivered actions. One Act 1
start cleared and the other three cases ended in losses. This checks
the prepared-start path across the three acts. The positive example is
a training-only result.

The saved training set has 185 ordinary combat floors and 12 elite
floors that reached native rewards. The corresponding losses are 22
and 19, with seven more losses in boss fights. A saved probe compared
floor-only and room-outcome actor feedback on 3,694 of the same
choice-bearing normal and elite combat menus. The room baseline used
only other training games of the same encounter type. Median
agreement between halves of a batch improved in three rounds and
worsened in one.

| Round | Floor-only median cosine | Room-outcome median cosine |
| --- | ---: | ---: |
| Player 2, round 1 | −0.245 | +0.075 |
| Player 2, round 2 | −0.011 | +0.005 |
| Player 3, round 1 | +0.044 | +0.090 |
| Player 3, round 2 | +0.003 | −0.092 |

The next comparison should isolate one change to actor feedback.
Start both initializers from their frozen originals and use their 24
verified first-round training games. These were sampled by those same
originals. Compare the exact first-round floor-only updates with
copies that add a fixed auxiliary signal for verified combat room
outcomes. Preserve the full-run return, action menus and model
architecture. Keep the 24 development games and the prepared probe
outside training. Evaluate the originals and both fixed update
variants on fresh matched normal starts. Use terminal wins first and
act clears and boss reach as development diagnostics. The probes
made zero optimizer updates and measured coverage and feedback
agreement.

If later-state exposure becomes the next blocker, test a separate
model-owned practice mix. Start with attainable native rooms across
different acts and resource states. The boss-heavy probe delivered
later decisions and no successful later-act goals.

Use [the result evidence](evidence/native-a8-own-training-result-v1.json)
and the [original recipe](native-a8-own-policy.md) to trace the audit.
The [matched combat-feedback follow-up](native-a8-combat-feedback.md)
contains the fixed ending and Trial controls and the prepared owner run.
