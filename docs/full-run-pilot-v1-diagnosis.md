# First unified evolution pilot: result and simulator repair

The latest completed step is the [captured event-choice repair](../backend-patches/event-choices-v1/README.md):
109 real-game choice lists match, 4,942 native tests pass, and eight fresh untrained-player
compatibility attempts finish without crashes or stalls. All eight lose; no learning or playing
strength improvement is claimed. The current decision is whether to add genuine normal-difficulty
A0 support before restarting learning or retain the existing fixed A8.

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

## Public-choice repair and completed owner audit

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

The owner completed the full audit: 85 of 89 previously failed training attempts passed, across
42 training seeds. It replayed 11,947 transitions in 92.495 wall / 91.416 CPU seconds. Successful
endpoints were 65 overflow menus, seven premature endings, 12 bundle confirmations and one reward.
Four event stalls remain failed, so `compatibility_passed` is false. Report:
`sha256:eaaa0e1a239b0fe14ac6b0a8aca3dd3cefcc47df5fc303e292366992e0ffec3a`;
resources: `sha256:c4b83eb5d6085a85478ebaadbbd76ff06bc85eb202b79be9b82ab4ec8c8b1611`.
The report and original cases remain unchanged. This audit measures failure-prefix compatibility;
it does not measure player win rate or rewrite experience.

The result remains **pending conformance**, with training/admission/promotion disabled. Synthetic
fixtures use direct test state and cannot count as real agent wins. Compatibility replay coverage,
real-game difficulty and act-boundary checks, and re-admission are still required before a
new training recipe. The audit launched no policy training or automatic follow-up.

## Event continuation correction and native integration

The remaining four cases used training seeds 100058, 100083, 100088 and 100056. Dense Vegetation and
Punch Off had already committed to a fight. Their handlers accept only action 0 on the next page,
but `WriteEventActionMask` unconditionally advertised fallback skip action 3. Repeating that
rejected action left the observation unchanged. The same source defect exists on the Lantern Key
fight page. Existing `EventCombatTests.Offered` enumerated `Range(0, EventSkipAction)`, missing slot 3.

The third candidate changes only that mask on the three committed pages. It preserves all accepted
continuations and the existing initial event surface. It adds no policy filter and changes no model
weights or public input schema. Initial-page action parity remains a separate real-game check;
preserving a historical action surface does not prove that surface matches the UI.

The candidate revision is `d49c550a400ee6e6e96aaca2fbf88ef090f79ebd`. All 32 targeted managed C#
regressions passed in a 6.753-second check capped at 45 seconds: the prior 23 plus nine new tests.
The new tests enumerate every action slot, verify rejected skip leaves state unchanged, and verify
the sole continuation starts the expected playable encounter with the run's HP, deck and gold.
An initial test compile failure was corrected by using `RunEngine.ActiveEncounterId`; that failed
candidate, logs, configuration and resource record remain preserved. No native library, game
attempts, training or admission were produced by either short check.

The owner subsequently published the candidate in 7.393 wall / 8.581 CPU seconds. All 32 tests
passed and its actual public exports were checked with an empty handle and zero game attempts.
Native SHA-256: `3cfcd92924135fdb5fa0d27c7667ef94aec5458a1d66a623ac32becdcaabcc92`.
Build report: `sha256:13fda11c656807cb53b0191c99dd0290472c03b844f39b419c4102cde4254a49`.

[Event correction evidence](evidence/event-continuation-repair-v1-evidence.json) records the owner
audit, all four verified source traces, isolated source/test identities and both short-check attempts.
Codex derived the new pending public-adapter manifest
`sha256:46dfcf7480d7eebda430f067a8257a5f400f62eab64443ab6ef6d9952c9db255` and ran the separate
event integration audit under a four-minute cap. **All 89 cases passed**, in 89.677 wall / 88.861
CPU seconds, with 11,939 transitions. The four event cases first verify the original three rejected
noops and unchanged public states, replay the exact preceding prefix, and require the corrected
engine to advertise solely action 0. The fresh player scores every offered action and uses that
continuation to enter the expected playable fight while preserving run resources. The 12 historical
noops are explicitly replaced; no other action drift is accepted. All original cases stay counted.
The old 85/89 report remains unchanged, and there were no optimizer steps or model promotions.

Audit: `sha256:565998a3e6fe5ace1ac138033f152de69d8c3a1ffcdf8df742f2e77eae6b67bf`.
Resources: `sha256:17cd55d853d81a8db99d875c15c0493b949ae8caf7d8b22c32878b69ffb7b110`.
[New evidence](evidence/event-native-integration-v1-evidence.json) freezes identities, endpoint
checks, denominators, compute and the original failed report. This audit is compatibility evidence
over inspected training prefixes, not model playing strength or complete real-game fidelity.
Difficulty, complete event action sets and later-act ending parity still precede re-admission.

All ten environment interface checks also passed through this native/adapter identity in a
0.825-second job capped at 45 seconds, on inspected training seeds 100058 and 100083. These cover
identity, reset, complete legal enumeration at tested states, steps, illegal actions, faithful and
resampled clones, replay, public-state isolation and terminal-only rewards. A reporting error after
the initial probes is preserved separately; a corrected report reads the checked manifest directly.
[Interface/reference evidence](evidence/event-native-contract-v1-evidence.json) records both jobs.

The saved live references identify remaining gaps precisely. The three repaired events' initial
pages contain enabled options 0 and 1; the source still advertises historical skip action 3 there.
Dense Vegetation's option-1 after-state was captured mid-transition and cannot serve as a settled
continuation-page oracle. All 32 existing full-run traces observe only Act 1, so none verifies a
later-act ending or terminal full victory. These gaps remain open before a new learning recipe.

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

Codex may run short builds, audits, tests and jobs autonomously. Jobs expected to take five minutes
or more are launched and monitored by the owner. Continue #141 with real-game conformance;
scaling #135 or fitting the #35 comparator does not precede the remaining admission checks.
The competent whole-game player and adaptive thinking objective remain unchanged.

## Captured event choices and frozen game rules: latest status

The fourth isolated candidate removes the invented skip on event screens and rejects locked or
nonexistent choices before changing state. All 109 captured choice lists match: 52 initial screens
and 57 settled later event screens, checking every action slot. Genuine Leave choices remain.
The Dense Vegetation mid-transition capture stays explicitly excluded from settled-page comparison;
other screen types and uncaptured events remain outside this new mask coverage.

All 240 targeted native checks passed, and the full native suite passed 4,942 tests with one optional
timing probe skipped. Ten public environment interface checks also passed. Eight short attempts by
a fresh untrained public player ended cleanly in losses, with no crashes or stalls. These checks
do not establish playing strength. No optimizer steps, admission, promotion or final-test use
followed. [Event choice evidence](evidence/event-choice-repair-v1-evidence.json) preserves the
active candidate, failed earlier attempts and resource reports. The old 89/89 prefix audit remains
bound to its original candidate, whose initial action surface differs from this repair.

A bounded source audit of the frozen game confirms that earlier bosses advance acts, total floor
and current-act floor are distinct, and A8 enables harder rules; Double Boss begins at A10. The real
game ends through forced Architect dialogue after the final boss. Each settled dialogue page has
one continuation, so collapsing it is an explicit simulator abstraction; live playback still needs
to drive those UI steps. [Frozen-rule evidence](evidence/frozen-run-rule-audit-v1-evidence.json)
records the pinned assembly, private extracted-type hashes and findings. It is not empirical
later-act coverage or proof of complete A8 fidelity.

The next learning difficulty needs a decision: implement genuine normal difficulty (A0), recommended
for the first strong player, or retain the current fixed A8. A0 requires actual rule support rather
than changing a label. Later-act conformance and re-admission still precede a fresh training recipe.
