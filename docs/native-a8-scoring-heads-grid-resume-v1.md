# A8 scoring-head comparison after round 57

The resumed run finished training through round 64 and stopped during
holdout world 70. Follow the [evaluation-only continuation](native-a8-scoring-heads-holdout-resume-v1.md)
for the saved round-64 results and the 58 untouched holdout worlds.

The original run sealed 57 rounds for both initializers before stopping
after 9 hours 40 minutes. Each method completed 912 training worlds per
initializer with matched PPO work. That was 2,736 optimizer steps per
method for player 2 and 2,685 per method for player 3. Both methods recorded
zero wins in 1,824 sealed training games each. Shared cleared Act 1 in
25 of those games and split cleared it in 22.

The 16 development worlds ran both initializers for each method at every
progress checkpoint. All 32 games per method at each checkpoint ended
in losses. The 128 final comparison worlds are still unstarted.

| Round | Shared mean terminal floor | Split mean terminal floor | Shared Act 1 clears | Split Act 1 clears |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 7.91 | 7.91 | 0 | 0 |
| 16 | 9.59 | 9.94 | 0 | 0 |
| 32 | 9.75 | 11.09 | 0 | 1 |
| 48 | 10.25 | 10.81 | 0 | 0 |

Floor progress improved for both methods on these fixed development
worlds. The saved wins do not distinguish the methods.

## Crystal Sphere decision coverage

In round 58, the player-2 split arm chose Payment Plan in Act 2. The
frozen host returned a Debt card and a grid with six divinations.
The generic event decoder expected ordinary option fields and rejected
the successor. The stopped game retains its raw native response and
unsealed delivery. The saved-only check reproduces that failure and
verifies the unchanged opening offer under the repaired projector.

The projector exposes the native visible board, current divination
count, and all 242 choices for two tools across 121 cells. Every choice
keeps its native tool and coordinate binding, including visible cells.
Other event pages and the potion belt still use their existing contracts.
The shared head and the split strategy head can score and sample the
entire menu.

Two fresh diagnostic fixtures verify the exact gold payment and Debt
payment, both tools, charge depletion, native reward handling, and
return to the map. The four round-57 models also deliver verified
eight-choice prefixes from the same fresh normal start. The controls
perform zero optimizer updates. The fixtures supply no learning data.

## Continue the study

The continuation restores the exact round-57 model and complete Adam
state for both methods and both initializers. It retains 3,904 games
through the last sealed round and four more games from the first two
round-58 player-2 pairs. The failed world and its sealed shared sibling
stay in the original record. The fresh world `SP1RESH1FTA8HDT1025`
replaces that slot for both methods and both initializers, including the
two cells that were unstarted. The original failed world supplies no
learning samples to the resumed round.

The new recipe pins the saved reports, interrupted evidence and
continuation sources. The frozen game build, original weights and
complete Adam states, learner settings and native ending checks stay
fixed. The main comparison uses normal starts and model-owned choices.

Close STS2, then run this command from the repository. Allow about
2.5–4 hours at the observed game lengths. The launcher allows six
hours per session and resumes from clean seals.

```bash
bash scripts/resume-a8-scoring-heads-v1.sh
```

The command has 1,020 new games to run. That includes 444 training
games in rounds 58–64, 64 games on the round-64 progress panel, and
512 on the original 128 final comparison worlds. It records capped,
failed, and unattempted evaluation games in the planned denominator
and stops after the comparison. It preserves any unsealed attempt.

The original reports and journals remain under
`artifacts/native-a8-scoring-heads/study-v1`. The continuation writes
to `artifacts/native-a8-scoring-heads/grid-resume-v1` and the controls
to `artifacts/native-a8-scoring-heads/grid-control-v1`.
