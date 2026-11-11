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
The development worlds measure whether the learned changes transfer to wins.

Close STS2 before launching the comparison. The launcher verifies and reuses
the sealed fitted copies. Allow about 12 to 25 minutes, with a 40-minute outer
cap.

```bash
bash scripts/fit-and-compare-a8-archive-v1.sh
```

The recipe declares the output directory and the process limits. The report
binds each fitted checkpoint and evaluated game to its seal. An interrupted
or uncertain case preserves its evidence and stops further play. This is a
development comparison, with candidate selection and confirmation reserved
for a separate assessment.
