# Fresh-game combat behavior result

Choosing the existing policy's highest-scored combat action improves average floor
reached for both preserved players. The measured gain is modest: **10.52 → 11.30
floors**, with **zero full-run wins under either method**. This evaluates a change
in action selection; no model was trained or promoted.

The owner completed the finite comparison on 2026-10-21. The
[original design](native-combat-behavior-comparison.md) and
[qualification evidence](evidence/native-combat-behavior-comparison-v1.json) remain
preserved. Separate [result evidence](evidence/native-combat-behavior-result-v1.json)
records the finished collection and saved-only assessment.

## Outcomes

All **256/256 games** finish cleanly: 64 fresh development game seeds × two fixed
players × two combat methods. There are no failed, skipped or unattempted games,
app copies or optimizer updates. Both exact round-60 weights and every Adam moment
remain unchanged, including counters **5,658 / 6,045**.

| Outcome | Sample combat at temperature 0.8 | Highest-scored combat action |
| --- | ---: | ---: |
| Full-run wins | 0/128 | 0/128 |
| Games clearing the first act | 0/128 | 2/128 |
| Average maximum floor | 10.523 | 11.305 |
| Highest floor | 17 | 27 |
| Mean declared bootstrap return | 0.023875 | 0.025864 |
| Mean CPU seconds per game | 2.470 | 2.561 |

The original whole-run objective remains victory within **128 CPU seconds**. Acts,
floors and the unchanged bootstrap score are auxiliary measurements. Both methods
have the same ceiling, not identical actual CPU use. The greedy method uses about
3.7% more measured game CPU here, with different-length games included; this is a
descriptive cost comparison, not a separate randomized timing study. Neither method
uses search or future engine information.

| Fixed player | Sampled mean floor | Greedy mean floor | Paired gain, 95% interval |
| --- | ---: | ---: | --- |
| Numerical seed 2 | 11.141 | 11.875 | +0.734 [−0.078, +1.625] |
| Numerical seed 3 | 9.906 | 10.734 | +0.828 [+0.234, +1.469] |
| Both fixed players | 10.523 | 11.305 | +0.781 [+0.242, +1.344] |

Player 2 reaches a higher floor on **21** paired seeds, a lower floor on **8** and
the same floor on **35**. Player 3 has **16 higher / 5 lower / 43 tied**. Each has
one greedy game clear an act; their best floors are 27 and 25. The individual
player-2 floor interval still includes zero. The pooled bootstrap-return gain is
**0.001989**, with a 95% interval of **[0.000542, 0.003859]**.

Intervals use the predeclared 10,000 paired resamples of **64 complete-game seeds**,
jointly across both fixed players. The 128 player/seed pairs are not 128 independent
worlds. The result does not describe uncertainty across a population of training
initializers or prove that a different model would benefit. One behavior stream is
observed per player/method/world. Zero observed win differences, including the
reported [0, 0] bootstrap interval, do not prove equal true win probabilities.

As a separately labeled descriptive check, dropping any one whole world leaves
the mean floor change between **+0.651 and +0.889**. Excluding both worlds with an
act-clearing game leaves **+0.597 floors across 62 worlds**. These outcome-selected
checks do not replace the full-sample estimate or provide a new confirmatory test;
they show that the entire floor gain is not confined to the two longest games.

## What stayed matched

The sole treatment is sampled versus greedy combat, including combat-owned nested
choices. Both methods retain the same outside-combat policy and temperature, legal
menus, shop navigation and public room/family/visit random draws. No HP reward,
training score change, learned value change or future-plan input is introduced.

Across **128 paired player/seeds**, all **5,403 shared noncombat draw slots** match.
The **1,392 identical effective public inputs** produce identical choices and
probabilities. Combat can change health, resources and which states are reached;
matching does not require the same noncombat choice when those public inputs differ.

The sealed collection receipts cover **39,343 decisions**, including 252 nested
combat selections. Collection reconstructs each choice and its probability after
every game and audits native delivery. The main comparison has no new exact-repeat
games; its null duplicate field is not an additional repeat pass. The separate
12-game qualification control supplied the four exact repeats and full saved-choice
reconstruction before this comparison began.

## Saved verification and resources

The short saved-only assessment verifies **256 receipts / 45,281 source files**,
all episode bindings, genuine native ending evidence, declared scores, CPU charges,
RNG receipts, matching and paired summary tables. Both complete player/Adam byte
seals still match. It takes **42.46 seconds**, 18.26 CPU seconds and 148.28 MB peak
memory, launching no games and performing no optimizer updates.

This assessment verifies journal hashes and collection's delivery/inference audit
receipts. It does not repeat neural inference for all 39,343 decisions or claim an
independent semantic reaudit of native delivery. No full episode histories are
retained or decoded by this additional outcome check. The original collector,
recipes, source data and prior evidence are unchanged.

The two owner-run collection sessions total **19.16 wall minutes / 927.23 CPU
seconds**, with 437.03 MB peak memory and **421.91 MB final cumulative output**.
The final report's 393.85-second session time covers only its last session.
Cumulative storage is not summed across sessions. All shared native inputs and
the account profile remain unchanged, with no game-app copies.

Private assessment: `artifacts/native-combat-behavior/result-assessment-v1/report.json`.
Original report: `artifacts/native-combat-behavior/sts2-v0.111.0-a8-comparison-v1/report.json`.

The repository check passes **2,058 tests (four skipped)**, strict types on 414
files, formatting/lint and the C# protocol in **123.75 seconds**. Tracked changes
are documentation only. Both complete player/Adam files still match their seals.

## Next work

1. **Use greedy combat as the explicit cheap reference for new teacher work.**
   Prepare a separately frozen, bounded complete-turn teacher test on fresh TRAIN
   worlds. Compare alternative turns with greedy combat continuation and matched
   noncombat behavior. Keep a greedy-only, no-search reference and charge any extra
   search. This result supports the continuation choice, not the usefulness of
   additional search or the reliability of new teaching labels.
2. **Require useful final-outcome distinctions before distillation.** Measure
   ties, better/worse alternatives and coverage across independent whole worlds.
   Retain the declared preference rule and full-run objective. Do not tune on these
   inspected development seeds, scale the unchanged flat teacher, silently reward
   HP or reinterpret repeated policy streams as independent hidden worlds. Any
   fixed-hidden-world teacher remains explicitly privileged; student inputs stay
   public and teacher episodes are not ordinary PPO experience.
3. **Then test a bounded student update against its frozen parent.** Fork both
   complete weights and all Adam state. Keep all legal action families learnable
   and compare fresh complete games under the same CPU ceiling. Greedy evaluation
   is not a substitute for sampling from the actual behavior distribution during
   ordinary PPO training. No readiness, promotion or adaptive controller follows
   the present result.

**No owner command is needed for this completed comparison.** No new long run,
training, model promotion, push or GitHub Actions follows the saved assessment.
