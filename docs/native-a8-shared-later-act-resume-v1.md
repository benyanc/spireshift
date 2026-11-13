# Shared-head A8 continuation after a prepared save timeout

This run resumed successfully and later stopped at a merchant-map
observation. Use the [merchant-map continuation](native-a8-shared-later-act-merchant-resume-v1.md)
for the latest result and remaining command.

The first run verified 56 training games and sealed 138 optimizer
updates. Both initializers finished round 1. Player 2 also finished
round 2. Player 3 was collecting round 2 when the worker timed out.

| Start | Verified games | Native wins | Native losses |
| --- | ---: | ---: | ---: |
| Normal start | 32 | 0 | 32 |
| Prepared Act 2 | 12 | 0 | 12 |
| Prepared Act 3 | 12 | 3 | 9 |

None of the 32 normal training starts cleared Act 1. The three
prepared victories came from two pre-boss worlds and measure suffix
play. All 128 fresh normal-start evaluation games are still unplayed.

## Save loading and evidence

Player 3 timed out in `t02a2s-p3`, before any public observation
or model decision. The worker had completed its startup identity
checks. Its journal contains no native reply to the load request.
Player 2 had already completed a verified game using the same
save. The missing reply leaves the exact timeout cause unresolved.

The new prepared worker stages the verified save in its private
profile and uses the frozen host's file-load command. The request
records the save digest, byte count and 20-second response deadline
before dispatch. A reply or timeout gets its own receipt. The game
and decision limits stay fixed. Two previously qualified
short controls matched their original public starts, delivered
decision counts and native endings. The Act 2 control ended in a
loss and the Act 3 control in a genuine suffix victory. The file
loader uses the same game, headless executable and public decision
adapter. Normal-start evaluation uses the original worker.

## Continue the same training plan

The continuation checks the 56 prior game seals, the three fit
seals and their full Adam states, and the original study report.
The timed-out slot stays failed and contributes zero decisions.
Player 3 keeps three scheduled Act 2 worlds in round 2. Verified
terminal outcomes from at least two of those worlds are required
by the existing credit estimator.

Close STS2, then run from the repository.

```bash
bash scripts/resume-a8-shared-later-acts-v1.sh
```

The command has 199 new training games and 128 fresh normal-start
evaluation games. Allow roughly 1.5–2.5 hours at the observed pace.
The original study, interrupted worker, sealed games and checkpoints
remain under `artifacts/native-a8-later-act-training/study-v1`.
New seals and reports go to
`artifacts/native-a8-later-act-training/resume-v1`.
