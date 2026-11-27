# Shared action lifecycle suite for frozen Ironclad/A8

The suite uses STS2 v0.111.0 / 41cef1ea with headless host v60 and
public converter v17. It verifies the frozen game, candidate, SDK,
runtime, localization and full checkpoint/Adam states before and after
each run. The headless processes use disposable profiles with writes
blocked to installed game files, personal saves and frozen inputs.

## Card plays that finish when their owner dies

The saved world-70 End Turn produced native game over at zero HP. Its
Stampede hook still had a Strike on the shared choice-context stack and
could not release its own frame. The original comparison preserves that
failed game and the associated unattempted cell.

A headless startup adapter binds to the exact frozen assembly. It moves
the existing card-frame release to the common successful completion of the
card wrapper. Ordinary and early successful returns both release the frame
after the native effects finish. Faulted tasks retain their native errors.
The adapter is independently built twice and its identity is checked in
the normal headless worker. Historical recipes retain their adapter versions.

| Diagnostic | Required observation |
| --- | --- |
| Unrepaired control | Lethal Stampede autoplay produces raw game over and reproduces the exact choice-stack error |
| Lethal autoplay | End Turn yields a verified native loss at zero HP, no gameplay actions and no pending operations |
| Nonlethal autoplay | The player takes five Thorns damage and the announced 23-damage attack, reaches round three at 12 HP and can play the next Strike |
| Lethal direct play | Playing the Strike from the same round-two boundary also yields a settled native loss |
| Normal-start check | The same patched worker opens a fresh playable Ironclad/A8 Neow decision |

The combat cases stage a two-card deck and HP in a private fixture.
The game plays Stampede, its autoplay, the monster's attacks and Thorns,
and determines the outcome through its native rules. The sealed diagnostics
carry zero optimizer updates and give no live official qualification.

## Extending coverage

Each fixture can pass its raw public snapshots, reconstructed learner menus,
selected indices and actual receipts to the same lifecycle checks. The checks
require every current legal binding and snapshot-bound read. Each delivery must
match its exact source action and a fresh successor in the same runtime. Attach
the case's independent effect assertions, such as HP changes or the restored
parent after cancel, to the receipt chain.

The short suite also reconstructs the saved Smith → potion use/discard →
cancel → rest options → map case. The full suite rechecks all 32 saved native
rest chains and the 128-game learner-input corpus. The report ties those
results to the frozen coverage inventory and lists the remaining obligations.
The interrupted official rest test copy remains recorded separately.

The short check reproduced the unrepaired failure and passed all three
repaired combat cases and the normal-start check. The separate saved pass
reconstructed 185 deliveries across all 32 rest cases. Both reports verified
the frozen game and all four full checkpoint and Adam states.

| Evidence in `artifacts/native-action-lifecycle-suite/v1` | Report ID |
| --- | --- |
| `short-1794770111008737000/report.json` | `sha256:823d91392185ed2184845e4bdf3d234782fcb40bae0f33cc37537b390c7233eb` |
| `saved-1794770126046388000/report.json` | `sha256:2fbea295dbefeb2214e97277ca1270508a5f29545f7628b51d64d364c39cac61` |

Run the broader suite from the repository. The outer cap is 15 minutes.
The results are written to the workspace declared in the recipe.

```bash
bash scripts/check-action-lifecycle-v1.sh full
```
