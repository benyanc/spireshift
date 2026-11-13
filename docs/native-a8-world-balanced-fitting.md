# World-balanced A8 fitting on two copied checkpoints

The first #134 and #35 fitting recipe binds the independently assessed #152
bank, the frozen v0.111.0 / 41cef1ea game and support build 60, and the exact
original checkpoints with their full Adam states. The bank contains 1,141
meaningful public decisions from 25 confirmed fitting worlds.

Each update takes one decision from each world. Within a world, the schedule
shuffles and visits each choice before starting another cycle. Both copies
follow the same schedule. The longest lesson has 200 choices, so 200 updates
cover every admitted choice at least once and give each world 200 draws.

| Copy | Starting Adam step | Updates | Decision draws | Final Adam step |
| --- | ---: | ---: | ---: | ---: |
| Player 2 | 5,658 | 200 | 5,000 | 5,858 |
| Player 3 | 6,045 | 200 | 5,000 | 6,245 |

The actor minimizes mean joint negative log probability at temperature 0.8,
with learning rate 0.001 and gradient norm limit 1. It uses the existing
public encoder and legal menu. A compact ordered answer contributes one draw
and sums its conditional factor losses through its native commit. The current
bank contains simple labels only. The critic weights stay fixed because this
bank supplies demonstrated actions. The copies advance their full Adam state.

The run reports world-averaged loss and top-one teacher agreement, broken out
by combat, strategic decisions and action family. The six successful teacher
traces from twelve held-out development cases supply offline diagnostics.
Both copies freeze at update 200 regardless of those metrics. The fitting
inputs come exclusively from the 25 admitted worlds.

The short control uses four updates per copy in a separate directory. It
seals both copies at update two, resumes them from disk, and checks the
result against an uninterrupted computation of all four updates, including
every Adam moment. Grouped loss, sampling and split ownership have focused
regressions. The saved check and fitting use zero game launches.

Run from Terminal.

```bash
bash "/Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/fit-win-curriculum-v1.sh"
```

The resource-tracked session has a 30-minute wall cap. Clean 20-update chunks
resume through the same command. An unfinished chunk stops for inspection.
The final report and candidate checkpoint paths are under
`artifacts/native-win-fitting/study-v1`. The next gameplay milestone is the
separate #146 normal-start comparison after #149 qualifies the victory
endpoint.

The [verification record](evidence/native-a8-world-balanced-fitting-v1.json)
contains the short results, frozen input checks and exact launch identity.
