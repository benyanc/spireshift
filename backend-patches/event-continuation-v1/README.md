# Committed event continuation repair

This isolated correction builds on the owner-published public-choice candidate
`9d531713416ae8f29380ffa80c3ef99bb1ca39e5`, for frozen v0.107.1. Existing binaries, results and failed
cases remain intact.

The owner's compatibility audit completed 89 cases: 85 passed and four stayed failed. All four
stalled on the committed fight page of Dense Vegetation or Punch Off. The action mask offered
fallback skip action 3 even though the corresponding handler accepts only action 0 and rejects 3
without progress. The same mask/handler mismatch exists on the Lantern Key fight page.

The patch advertises only the accepted continuation on those three pages. It changes no handler,
initial-page action surface, public input schema, policy or binary reward. No actual legal fight
choice is removed. Other event surfaces still require live-game validation before admission.

Nine new synthetic tests enumerate the entire action mask, preserve the initial surface, check
skip rejection leaves public state unchanged, and verify the accepted continuation starts the
expected playable fight with the run's HP, gold and deck. All 32 targeted managed regressions
passed in a short check: these nine, fourteen public-menu tests and nine completion/reward tests.
This compiled managed tests but published no native library and made no agent game attempts.

The owner subsequently published the candidate in 7.393 seconds with all 32 regressions passing.
Codex connected its new public-adapter identity and completed the separate 89-case replay in
89.677 seconds under a four-minute cap; all 89 passed. The four event cases verify the rejected
suffix, retain its original prefix, and confirm that the corrected continuation starts the expected
playable fight. Twelve historical noops are explicitly replaced. The old 85/89 result stays intact.
[Source evidence](../../docs/evidence/event-continuation-repair-v1-evidence.json) records the four
verified failure traces and source checks; [native integration evidence](../../docs/evidence/event-native-integration-v1-evidence.json)
records publication and the new audit. This does not admit the backend or establish playing
strength. Difficulty, complete event-action parity and later-act endings remain real-game checks.

Upstream context is [EvanGambit/sts2](https://github.com/evangambit/sts2), MIT licensed,
Copyright (c) 2024 The Complete Contributors. Its license is retained beside the patch.
