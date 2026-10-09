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

## First repair: native build complete

A minimal source repair uses the current map row for the defensive ending, clears a stale win
flag on that ending, and writes the fourth reward after both observation blocks. Nine synthetic
C# regressions cover early rooms in all three acts, earlier/final boss reward transitions,
defensive false-win protection, and fourth-reward identity/upgrades/deck preservation.

The original admitted simulator remains intact. The candidate is prepared privately at
`artifacts/backend/evangambit-v0.107.1-full-run-repair-v1`, revision
`99fad6a73912e26af6872c2f0742ebeb5ffb3581`. The [patch and tests](../backend-patches/full-run-completion-v1/README.md)
are reviewable; no native build or sustained game batch was launched during implementation.

The owner's first repair attempt compiled successfully, then aborted before executing any tests:
the project targets .NET 9, while the machine has only .NET 10.0.12 (SDK 10.0.401). This was a
test-host setup failure, not a failed regression. A subsequent short check of the owner's already
compiled files, with `--no-build --no-restore` and a 30-second timeout, passed all nine targeted
regressions using .NET 10. At that stage the native library had not been published. The
[runtime evidence](evidence/full-run-repair-runtime-check-v1.json) records both attempts and the
saved test-result digest; neither check played a game or trained a player.

The launcher now checks installed runtimes before invoking test/build stages. It prefers stable
.NET 9.0; on the inspected .NET 10.0 fallback it sets `DOTNET_ROLL_FORWARD=Major` only for the test
process and records the runtime inventory, selected policy and SDK in the build evidence. Other
major versions and preview-only installations fail before compilation. The native publish target
and pinned repair source remain unchanged. The setting follows
[Microsoft's runtime selection policy](https://learn.microsoft.com/en-us/dotnet/core/versions/selection).
No runtime installation or machine-wide setting is required on this machine.

The owner subsequently completed the native build in 10.284 elapsed / 16.481 CPU seconds, with
all nine regressions passing. Its library SHA is
`cc08d7e9c75e2f86cfd84a52e5fd106b16986448f72f860848fb84f9be8b1eb0` and its pending manifest is
`sha256:4f49cbbbcbbc58cafa91680efc0980745086ce0ac8ad432e9bd2d485daf62bcd`. Build/resource IDs and
the checked test digest are preserved in [repair evidence](evidence/public-choice-repair-v1-evidence.json).
It remains pending conformance, with no player games, training or admission.

## Public-choice repair and next owner task

A second isolated candidate builds on the first repair at
`artifacts/backend/evangambit-v0.107.1-full-run-repair-v2`, revision
`9d531713416ae8f29380ffa80c3ef99bb1ca39e5`. Its
[patch and tests](../backend-patches/public-choices-v1/README.md) add complete combat-menu readouts,
correct draw/discard/generated candidate mapping and upgrades, bundle highlight/confirmation
state, and a source declaration of fixed Ascension 8. This does not add selectable A0 or prove
that all implemented rules match live-game A8.

The owner published this native candidate in 9.588 elapsed / 16.661 CPU seconds. All 23 targeted C#
regressions passed, including the earlier nine and fourteen new menu/profile cases. The actual
public-list exports were checked on an empty handle with zero reset/step calls. Native SHA:
`f88014084daeb50e17399e67b2a4807120cd07c9fcb2de74dbd2161f23e22c1f`.

A new versioned adapter and unified player now consume the complete readouts. Every offered card
and skip is bound, normal combat targeting is preserved, and selected bundle contents plus the
confirmation capability are inputs. All 4,384 parameters remain mutable. Historical adapter,
encoder, policies, checkpoints and recipe identities remain unchanged; old genomes are not
silently migrated to the new inputs.

A short native check replayed the two previously inspected training failure prefixes: both the
fourth-reward identity and the 15-card menu now bind successfully. It made 410 transitions and
scored 412 observations in 3.387 seconds under a 45-second cap. No training, model promotion or
admission followed. Its initial path-root preflight failure made zero game attempts and is retained
alongside the successful retry in [integration evidence](evidence/public-choice-integration-v2-evidence.json).

Run **only this next command**:

```bash
bash scripts/audit-full-run-public-integration-v1.sh
```

It checks all 89 previously failed training attempts across 42 training seeds against the owner-built
candidate. It replays saved action locators, scores every current legal choice, and checks the
overflow/reward/premature-ending/bundle-confirmation endpoints. Errors outside this repair's scope
remain failed cases. This does not measure win rate or rewrite old experience.

Caps are one worker, 30 elapsed minutes, 3,600 CPU seconds, 8 GB memory and 2 GB artifacts. Exact
partial cases resume; numbered resource reports preserve launches. Repeating a completed command
checks/displays its saved result without replaying games. Return the final report for assessment;
no command needs to be chained. The full audit has not been launched by Codex.

The result remains **pending conformance**, with training/admission/promotion disabled. Synthetic
fixtures use direct test state and cannot count as real agent wins. Compatibility replay coverage,
real-game difficulty and act-boundary checks, and re-admission are still required before a
new training recipe. The audit script launches no policy training or automatic follow-up.

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

Only the owner runs sustained builds, training and evaluation; short synthetic checks are
allowed. Continue #141 after assessing the owner compatibility audit; scaling #135 or fitting the
#35 comparator does not precede the remaining conformance/admission checks. The competent whole-game
player and adaptive thinking objective remain unchanged.
