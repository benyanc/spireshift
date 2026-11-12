# Shared-head A8 training with later-act starts

The [round-64 comparison](native-a8-scoring-heads-holdout-resume-v1.md)
recorded zero A8 wins over 2,048 training games per method. The shared
head is the baseline for this experiment. Copies of the two sealed
round-64 shared checkpoints inherit the exact actor, critic and complete
Adam state.

The original run stopped in round 2. Use the
[save-load continuation](native-a8-shared-later-act-resume-v1.md)
for its verified results and the remaining work.

## Training

Each initializer plays eight rounds of 16 games. Each round has eight
normal starts, four Act 2 starts, and four Act 3 starts. A later-act
group includes one independently verified practice-bank save, a new
healthy act entry, a new lean act entry, and a new pre-boss rest site.
New saves use the existing curriculum profiles and native maps. The
first seed with the requested act definition is selected before any
model gameplay. Both initializers receive the same start per world.

The current shared head chooses every action from the native legal
menu. Only verified complete games contribute PPO samples. The
baseline for credit is fitted separately for each starting act.
All verified normal-start decisions enter the update. Each later act
contributes up to half the normal-start decision count. This limits
the influence of long prepared episodes on early-game learning.
Prepared games get credit for floors and acts cleared after loading
and for genuine native suffix victories. Prepared victories are
reported separately from full-run A8 wins.

The save admission checks native seed and difficulty, current
act and room owner, deck upgrades, HP, gold, relics, and potions.
A pre-boss save's constructed history uses the generated Ancient's
identity so the native ending can traverse it. The runtime startup
hook calls the same Crystal Sphere initialization used by normal
starts when loading a save. The pinned game, executable, and original
checkpoint files remain frozen. Both setup changes are scoped to
prepared training.

## Evaluation

After round eight the two fitted checkpoints are sealed. Each plays
32 fresh Ironclad/A8 normal starts alongside its frozen parent on the
same worlds. There are 128 planned games. Full-run native wins are
the primary outcome. The report includes Act 1 and Act 2 clears,
paired win counts, and capped, failed and unplayed games. The
development worlds stay outside training and the reserved project
confirmation panel stays unopened.

This compares the resulting policy with its frozen parent. A matched
normal-only training arm would be needed to attribute any improvement
specifically to later-act starts.

The earlier [mixed-practice comparison](native-a8-matched-practice-result.md)
used fixed two-room segments for an auxiliary update. This experiment
collects new on-policy play through native endings in every round.

## Short checks

The final control verified 772 native decisions in six complete
games. One prepared Act 3 game reached genuine native victory.
The disposable update used 199 normal-start decisions and 99 from
each later act, then reloaded after 12 Adam steps. The frozen and
updated copies each delivered eight choices from a matched normal
start. The saved-start Crystal Sphere control verified 242 grid
choices plus the potion control, completed rewards, and returned
to the map. The native, model and optimizer freeze checks passed.
The control report is under
`artifacts/native-a8-later-act-training/control-v4`.

## Run

Close STS2 and run from the repository.

```bash
bash scripts/train-a8-shared-later-acts-v1.sh
```

The schedule has 256 training games and 128 evaluation games. Allow
roughly 1.5–3 hours based on saved native run times. Prepared games
can go substantially deeper than normal starts. The launcher uses a
six-hour outer limit and the inherited 128-second per-game CPU guard.
It resumes sealed work at clean boundaries and preserves unfinished
native deliveries. The existing Stampede cleanup issue remains
tracked under [#149](https://github.com/benyanc/spireshift/issues/149).
The training and evaluation report is written
under `artifacts/native-a8-later-act-training/study-v1`.
