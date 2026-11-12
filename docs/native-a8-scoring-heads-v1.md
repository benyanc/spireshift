# Sustained A8 scoring-head comparison

The shared actor and the combat-and-strategy actor start from the same
five-world archive fit for each of the two initializers. The split version
copies the parent actor's weights and Adam moments into both heads. Both
versions use the same public encoder and value estimator architecture.
The split version shares its critic across the two heads. The original
checkpoint files and full Adam states are verified throughout.

The current public decision owner selects the head. Combat turns and
combat-owned selections use the combat head. Rewards, routes, shops,
and other owners use the strategy head. The repaired native adapter
exposes the complete legal menu and verifies actual delivery. An
ordered answer stays together in one PPO decision. Each policy makes
all of its own choices from the first Neow menu through the native ending.

| Stage | Independent worlds | Games |
| --- | ---: | ---: |
| Training, 64 rounds of 16 new worlds | 1,024 | 4,096 |
| Progress at rounds 0, 16, 32, 48 and 64 | 16 reused across checkpoints | 320 |
| Final comparison of the round 64 checkpoints | 128 | 512 |

Each world runs both methods for both initializers. The 1,024 training
worlds per method and initializer are 64 times the 16 games in the
earlier archive-initialized PPO run. The game build v0.111.0 / 41cef1ea
and the existing whole-run victory objective and PPO settings are pinned.
[Earlier PPO result](native-a8-archive-own-training-v1.md).

Within each initializer and round, every paired terminal game supplies
credit. The shorter verified decision stream fixes the number of
training decisions per method. Each method receives the same number
of PPO minibatch updates and both stop the epoch sequence when either
reaches the declared KL limit. The two split heads advance their own
Adam state when their decisions appear. The study records actual
admitted games, decision counts, optimizer steps and trained rounds.
Capped games retain their outcome and both members of an incomplete
pair stay outside that round's learner input.

The 16 progress worlds measure the learning curves. The 128 final
worlds stay separate from training, progress and the reserved project
confirmation set. The final comparison uses A8 wins, with Act 1 clears
and floor as diagnostics. The report keeps capped, failed and unattempted
games in the denominator and resamples paired outcomes by world across
both initializers. A zero-win result stays inconclusive.

## Short checks and launch

The short control verifies identical initial choices on three fresh
worlds per initializer. Both methods train on those independently
verified episodes, reload their saved weights and complete Adam state,
and deliver an eight-choice prefix on a separate world. Unit checks
cover head isolation, matched optimizer work, clean resume and the
evaluation denominator. The saved Kifuda and short native selector
controls qualify both selector formats used by the adapter.

Close STS2 before starting. Allow roughly 14–20 hours at recent game
lengths. Progress may take longer as games reach later acts. The
launcher uses a 24-hour session cap and a 72 GB evidence cap. At the
observed early-game lengths, sealed evidence should take roughly
10–15 GB. Full runs retain longer journals.

```bash
bash scripts/compare-a8-scoring-heads-v1.sh
```

The same command resumes from verified game and checkpoint seals.
Use `--until-round N` for a planned stop at a round boundary, then use
the default command to continue. The launcher preserves an unsealed
attempt for inspection. Session and final reports are under
`artifacts/native-a8-scoring-heads/study-v1`.

[Prior scoring-head screen](native-a8-temporal-credit-result.md#decision-coverage-and-shared-updates)
· [Native selector verification](native-systematic-selectors-v1.md).
