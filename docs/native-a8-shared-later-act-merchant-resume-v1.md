# Shared-head A8 continuation after shop exit

The file-load continuation added 31 verified training games and
81 optimizer updates. Player 2 finished round 3 and player 3
finished round 2. The two saved attempts now have 87 completed
training games and 219 sealed updates.

| Start | Games | Native wins | Native losses |
| --- | ---: | ---: | ---: |
| Normal start | 48 | 0 | 48 |
| Prepared Act 2 | 19 | 0 | 19 |
| Prepared Act 3 | 20 | 5 | 15 |

One normal start cleared Act 1. The five prepared victories came
from three pre-boss worlds. All 128 fresh normal-start evaluation games are
pending, so this run has yet to measure a change in full-run win rate.

## Merchant target after leaving the shop

In `t03a2s-p3`, the file loaded and the model played into an Act 2
shop. The host delivered the model's exit and opened the map.
Its immediate reply still advertised the previous merchant as a
Foul Potion target. The next decision was blocked by the complete-menu
check. The interrupted chunk retains 54 choices acknowledged by
the coordinator and the additional native exit receipt. It supplies
zero training decisions.

The frozen host updates merchant presentation in its native
`observe` command. The new worker asks for that read once after a
merchant exit returns a map with the stale target. It accepts the
refreshed map only when the map choices, player facts and other
belt bindings match the exit response. The game still owns map travel,
potion use and discard. The same worker logic covers prepared and
normal starts.

The saved regression reproduced the failure and preserved three shop
menus. Four short native controls covered real and fake merchant exit,
discard and use. The map retained its choices and Blood Potion use.
Foul Potion still awarded the real merchant's gold or started the
fake merchant fight. The prepared and normal model controls matched
their prior 161 and 82 decisions and native endings. The game,
headless executable, SDK and all original weights and Adam states
passed their frozen checks. The controls made zero optimizer updates.

## Remaining run

The continuation carries forward both verified prefixes and five
fit seals. The two failed Act 2 slots remain in their original
training rounds. Only the other declared terminal games contribute
samples. The next untouched game is player 3's next round-3 Act 2
start. Evaluation uses the same 32 fresh normal-start worlds across
both initializers and both arms.

Close STS2, then run from the repository.

```bash
bash scripts/resume-a8-shared-later-acts-v2.sh
```

Allow roughly 1½–2½ hours for 167 training games and 128 evaluation
games. New output goes to
`artifacts/native-a8-later-act-training/resume-v2`. The prior attempts
and their raw evidence stay in `study-v1` and `resume-v1`.
