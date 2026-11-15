# Compare direct public card statistics in the A8 learner

The [Act 1 replay study](native-a8-act1-success-replay-result-v1.md)
fit saved decisions more closely. Each arm still won 0/64 new games.
The saved earlier games show that dedicated damage and block inputs
were empty even though the native combat menus exposed the numbers.

## Learner input

Bind every legal play to its physical card in the current public hand.
Read the active combat display for that card. A distinct input pair
records presence and the scaled displayed value of each numerical stat
seen in the fitting worlds. Presence distinguishes a visible zero from
an absent stat. The model can learn from block, damage, calculated
damage, repeat count, draw count, and other recorded public stats.
An upgrade preview or a card in another zone cannot supply the
current value. The general public encoding still carries all visible
fields and every legal choice. There are no scripted card plays.
Rewards, shops and card selections have distinct display contexts.
The direct columns in this comparison apply to plays from the hand.

The 38 fitting worlds supply 26 numerical stat names. The two
corrected copies inherit the round-64 parents and all
their weight and Adam coordinates. New input weights and moments
start at zero. The initial action scores match the old parents.
Both corrected copies use the same 38 fitting worlds, 256 actor
updates and per-update choice schedule as the already sealed legacy
fits. Each critic stays fixed. The 12 offline worlds supply no
updates and the fresh game comparison tests transfer.

## Fresh games

Run the two exact legacy replay fits and the two corrected fits
on the same 32 new normal-start Ironclad/A8 worlds. The build,
public framework, sampling and terminal objective are fixed. The
model chooses every action. Full A8 wins are primary, with Act 1
and Act 2 clears and floor progress as diagnostics. All planned
games remain in the denominator and the final-test seeds stay
reserved.

The short checks matched 578 inherited candidate scores across the
two parents, applied two updates per disposable copy, and verified
the reloaded states and native endings in all four control games.
The launcher's saved control verification passed with the frozen
game, runtime and original full checkpoint states. The control ID is
`sha256:896dbf370284e6914c9c9753ea1d7d295112ae7027b355e9d22cd96fa32463c4`.

Close STS2 before running. Allow about 20–30 minutes based on the
17-minute previous comparison and the new fitting path. The
launcher uses a one-hour cap, verifies the short controls, and
preserves unsealed attempts.

```bash
bash scripts/compare-a8-card-display-v1.sh
```
