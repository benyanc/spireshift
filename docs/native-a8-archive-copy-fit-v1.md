# Fit checkpoint copies on the verified A8 replays

The [qualification](native-a8-archive-transitions-v6.md) admitted three complete
normal-start Ironclad/A8 victories for a separate fitting experiment. This
recipe pins all three winning worlds, their 2,380 decisions and the independent
learner input audit. Only the three sealed winning worlds supply answers.

Each update draws eight complete answers per world. The fixed schedule uses
896 draws from each world, cycling through shorter runs in shuffled order and
visiting every admitted decision. Both copies use the same 112 updates and
start from their exact original actor, critic and full Adam state. The actor
learns from the complete menu. A selection with local steps and a native
confirmation contributes one answer with a joint likelihood. The critic weights
are held fixed for this imitation fit.

The final copy from each initializer is frozen before development play. Each
of the 12 declared development worlds runs from Neow with both originals and
both fitted copies, for 48 games. All policies sample from the full legal menu
with the same temperature and matched draws for corresponding decisions.
Verified native terminal wins determine the primary comparison. Act 1 clears
and later progress help diagnose the result. Capped, failed and unattempted
games stay in the planned denominator. The final-test worlds remain reserved.

The short control passed with two updates on each disposable copy, four
matched native opening checks, and one verified terminal loss on floor 14.
It checked the full state reload and every native delivery. Its report is
`sha256:bbedbad4cb8d55c628f0c30b5e60e1926d1ccdb533f0020932bfab3b47786218`.
The main run requires that control and the exact frozen game, adapter, runtime,
archive and original states.

Both full fits completed and were sealed with 112 updates apiece. The mean
loss on demonstrated answers fell from 2.349 to 1.066 for player 2 and from
2.146 to 1.074 for player 3. The fitting report is
`sha256:e2d8d659e8f32736ee495a7f2c456690220759678ae671dab6c99a2996f34b37`.

## Saved development result

All 48 games ended in native losses. Both fits reached zero full-run wins
and zero Act 1 clears on the 12 fresh worlds. Player 3 reached the same
Lagavulin Matriarch boss on one world in both arms.

| Initializer and arm | A8 wins | Act 1 clears | Act 1 bosses reached | Mean maximum floor |
| --- | ---: | ---: | ---: | ---: |
| Player 2 original | 0/12 | 0/12 | 0/12 | 8.92 |
| Player 2 fitted | 0/12 | 0/12 | 0/12 | 7.83 |
| Player 3 original | 0/12 | 0/12 | 1/12 | 9.75 |
| Player 3 fitted | 0/12 | 0/12 | 1/12 | 9.58 |

The fits reached a higher floor in six of 24 matched pairs, tied in nine
and finished lower in nine. Twenty-seven losses were in ordinary fights,
19 in elites and two at the Act 1 boss. The fitted players ended a turn
with a card play offered in 33 of 1,463 such menus. The originals did so
in three of 1,872. These rates describe the different states each policy
visited. They do not identify which choice caused a loss.

The saved audit reconstructed 6,813 native deliveries and checked 2,934
sealed files, including the two exact fitted states and their complete
Adam. Each world had the same opening menu across all four arms. The
frozen build and all original and reference full states verified. Zero
updates occurred during evaluation. The final-test worlds remain reserved.
[Saved audit](evidence/native-a8-archive-copy-fit-result-v1.json).

The three demonstrations improved agreement on their own menus. The
fresh results prioritize additional successful, independent early-game
worlds before another fit. The [Act 1 archive qualification](native-a8-archive-act1-v1.md)
uses uninterrupted prefixes of separate published journals and checks
their actual native Act 2 entry.
