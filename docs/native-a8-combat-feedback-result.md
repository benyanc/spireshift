# Matched A8 combat feedback result

All 48 normal-start Ironclad/A8 games ended in native losses. All eight
worlds matched their initial public input across the three arms and both
initializers. The saved audit reconstructed 8,641 model choices and their
native deliveries from 48 seals and 2,880 files. The frozen game, host,
converter, runtime, original checkpoints, and all six comparison states
passed verification. [Result evidence](evidence/native-a8-combat-feedback-result-v1.json).

| Arm | Full-run wins | Act 1 boss reached | Act 1 clears | Mean maximum floor |
| --- | ---: | ---: | ---: | ---: |
| Original | 0/16 | 4/16 | 0/16 | 10.69 |
| Floor-only PPO | 0/16 | 4/16 | 0/16 | 10.94 |
| PPO with combat feedback | 0/16 | 4/16 | 1/16 | 10.69 |

The room-feedback arm chose differently from floor-only in 15 of 16
matched games. Every first divergence occurred on an identical public
menu, at a median of floor 3. It reached a higher floor twice, the same
floor eleven times, and a lower floor three times. Player 2 beat
Lagavulin Matriarch with 8 HP on world 8 and died on floor 23 in Act 2.
This is one observed Act 1 clear and zero additional wins.

## Decision framework and learning coverage

The saved menus and deliveries reconstruct through the full-menu learner.
The panel exercised the repaired native loss verifier, including the Act 2
loss. Trial Double Down and compact ordered answers were absent from these
games. The separate short controls still own those targeted cases.

Ordinary combat accounted for 21 terminal losses, elites for 16, and bosses
for 11. Across the three arms, the model reached native rewards after
212 ordinary fights, 10 elites, and one boss. Only 109 delivered decisions
occurred in Act 2, with no Act 2 boss reached. Both earlier training rounds
also had zero Act 1 clears across their 48 training games. The first
room-feedback comparison mainly changes credit within this early-game data.

The model chose to open or close shop inventory 1,014 times across 29
visits. These are genuine legal actions. They are evidence of repeated
navigation and are useful to count separately when assessing the mix
of experience. All visits eventually progressed in this panel.

## Next learning stage

Change what the model gets to practice. Use a mixture of normal starts
and varied prepared training starts so the model can collect its own
complete successes and failures across the acts. Use attainable native
room goals first, and broaden to harder elite and boss states as useful
outcomes become available. Preserve the complete legal menu and learn
from the model's sampled choices. Compare any resulting fixed candidates
on fresh normal starts with full-run wins as the primary outcome.

The eight comparison worlds stay development-only, and the final-test
seeds stay reserved. The run and saved audit made zero optimizer updates.
See the [prepared practice collection](native-a8-practice-mix.md).
