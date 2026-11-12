# Round-64 scoring heads and remaining A8 holdout

Both methods completed 64 training rounds for both initializers. Each
method saw 2,048 training games and recorded zero A8 wins. The matched
optimizer work totals 3,108 steps per method for player 2 and 3,027 per
method for player 3. The round-64 development panel recorded zero
wins in 32 games per method. Shared cleared Act 1 once and split
recorded zero clears.

The fixed holdout has 128 worlds, with both methods and both initializers
per world. The owner run sealed 278 of the 512 planned games.

| Method | Verified holdout games | A8 wins | Act 1 clears | Mean terminal floor |
| --- | ---: | ---: | ---: | ---: |
| Shared | 139 | 0 | 5 | 11.12 |
| Split combat and strategy | 139 | 0 | 2 | 10.80 |

The current result supports keeping the shared head as the default.
The planned win-rate comparison is still inconclusive.

## Native end-turn failure on world 70

The player-3 shared checkpoint dropped to 5 HP in its second turn
against Spiny Toad in Act 2. Before End Turn it had zero block, Stampede,
and one Strike left in hand. The enemy had 5 Thorns. The saved native
response reports a dead player and `game_over`. The runtime also reports
a stack mismatch while unwinding the Stampede hook, with Strike still
on the player-choice stack.

The frozen card wrapper pushes the card onto the choice context before
playing it. A return on player death skips the matching pop. This
matches the saved autoplay sequence and the error from the enclosing
Stampede hook. The worker preserved the error and stopped before
sealing a verified terminal observation and run identity. The raw
game-over response remains diagnostic. Track the native choice-context
cleanup issue under [#149](https://github.com/benyanc/spireshift/issues/149).

World 70 retains two verified player-2 losses, one failed player-3
shared game, and one unattempted player-3 split game. Its two
unresolved cells remain in the original denominator.

## Finish the untouched worlds

Close STS2 and run this command from the repository. Allow about
35–60 minutes for the 232 games on worlds 71–128.

```bash
bash scripts/finish-a8-scoring-heads-holdout-v1.sh
```

The launcher verifies the training lineage, complete round-64 Adam
states, fixed development panel, and all 278 prior holdout seals
before launching. It uses the same frozen native worker, game build,
models and per-game limits. It performs zero optimizer updates and
retains the original 512-game denominator. The original round-64
attempt stays in `artifacts/native-a8-scoring-heads/grid-resume-v1`.
The remaining schedule writes to
`artifacts/native-a8-scoring-heads/holdout-resume-v1`.

The session allows two hours. A clean pause can resume from sealed
games. A new unsealed attempt stops for inspection and preserves
its evidence. The final report records bounds for the win-rate
difference with unresolved cells included.
