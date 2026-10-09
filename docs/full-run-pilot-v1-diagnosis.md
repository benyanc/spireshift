# First unified evolution pilot: result and simulator repair

The owner completed all 832 planned game attempts in 80.858 elapsed seconds and 592.289 total
CPU seconds. Four generations ran. There is no demonstrated playing improvement or promoted
model. Full-game evaluation is blocked by simulator and public-choice defects under
[#141](https://github.com/benyanc/spireshift/issues/141).

## Result in plain language

| Separate 64-seed development comparison | Starting player | Evolved player |
| --- | ---: | ---: |
| Full-game wins | 0 | 0 |
| Mean highest total floor | 11.00 | 9.47 |
| Attempts ending normally | 56 | 52 |
| Failed attempts, retained in the denominator | 8 | 12 |
| Attempts observed entering Act 2 | 0 | 1 |

The evolved player reaches 1.53 fewer floors on average on these paired seeds. Its one Act 2
attempt subsequently fails the terminal-consistency check; it is not a full win or normally
completed game. Improvements on the small training panels did not establish generalization.
This neither establishes a genetic-algorithm advantage nor proves that evolution cannot work.
More games cannot repair an environment that stops correctly progressing runs early.

## Blocking defects found

1. **Premature ending after Act 1.** The simulator compares the total run floor, which carries
   across acts, with a boss-row number local to the current act's map. It can therefore stop an
   early Hive room around total floor 19. It also leaves the previous combat's win flag set.
   Eight saved attempts report this impossible early victory. Our three-act check correctly
   rejects all eight, so reported full wins remain zero.
2. **Incomplete combat choices.** A training-seed reproduction exposes fifteen legal cards but
   only ten encoded card objects. There are 79 failures with this binding error across the pilot.
   Revealing the entire offered selection is needed; dropping the remaining actions or reading
   the hidden draw order is not an acceptable repair.
3. **Fourth card reward in the wrong block.** Lasting Candy's fourth reward is offered legally,
   but its encoded identity is zero. The engine writer omits the preceding combat-block offset.
   Two saved attempts hit this error. The proposed source patch repairs this write.
4. **Selection progress and difficulty.** Twenty attempts stall, including bundle highlight
   loops; selected-bundle/confirmation state needs an explicit public binding. Separately, the
   pinned sources include fixed higher-Ascension rules: two potion slots (explicitly described
   as A8), 64/80 initial HP, and Ascender's Bane. The reset API has no ascension argument. The
   historical recipe's Ascension-0 label is invalid; these results must not be advertised as A0.
   Declare/verify the actual profile before any new learning recipe.

These diagnoses preserve the original reports, failed cases, models and declared score. No
historical error is relabeled as a victory or successful loss. The final test remains sealed.

## Implementation and next owner task

A minimal source repair uses the current map row for the defensive ending, clears a stale win
flag on that ending, and writes the fourth reward after both observation blocks. Nine synthetic
C# regressions cover early rooms in all three acts, earlier/final boss reward transitions,
defensive false-win protection, and fourth-reward identity/upgrades/deck preservation.

The original admitted simulator remains intact. The candidate is prepared privately at
`artifacts/backend/evangambit-v0.107.1-full-run-repair-v1`, revision
`99fad6a73912e26af6872c2f0742ebeb5ffb3581`. The [patch and tests](../backend-patches/full-run-completion-v1/README.md)
are reviewable; no native build or sustained game batch was launched during implementation.

Run **only this next command**:

```bash
bash scripts/build-full-run-backend-repair-v1.sh
```

It checks the nine targeted C# regressions and builds a separate native library, with caps of
30 elapsed minutes, 7,200 CPU seconds, 12 GB memory and 4 GB artifacts. Build logs and numbered
resource reports are preserved. Repeating a completed command checks/displays its saved result
without rebuilding. Return the final report for assessment; no command needs to be chained.

The result remains **pending conformance**, with training/admission/promotion disabled. Synthetic
fixtures use direct test state and cannot count as real agent wins. Public choice completion,
actual difficulty, frozen-game act-boundary checks and re-admission are still required before a
new training recipe. The repair script launches no policy training or automatic follow-up.

## Evidence and scope

The [aggregate evidence](evidence/full-run-evolution-pilot-v1-diagnosis.json) checks the immutable
IDs of all 832 saved case metadata records and both source reports. It does not semantically
reverify every decision trace. Two bounded exact-action reproductions used training seeds only:
410 steps and approximately 0.21 replay CPU seconds. Their public observations stay under private
`artifacts/compatibility/full-run-pilot-v1-diagnosis/`; no raw game data enters Git.

- Evolution report: `sha256:76ac741a3a9c1d2968e0e08b4a0ef92ed93ce50c9311478c1aa882721c187136`.
- Total-job resource report: `sha256:65dcf3b401d3847fa8cf83419778116d24c4f9cca8dffb6e063f49f96cc10344`.
- Diagnosis: `sha256:b7336e621962076e8af9cd14a427bf1723725c86d910dce144b20efdcead279a`.
- Repair configuration: `sha256:214b5fdb1bc667b034d1417b0c3be2963f234a25533853707fcdee677c172cb1`.

Only the owner runs sustained builds, training and evaluation. The next implementation after
the build assesses its evidence and finishes #141; scaling #135 or fitting the #35 comparator
does not precede those repairs. The competent whole-game player and adaptive thinking objective
remain unchanged.
