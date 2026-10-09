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

The owner publishes the candidate with `scripts/build-event-continuation-backend-v1.sh`. It stops
before admission or training. The next compatibility replay must use the new native/adapter
identity and keep all original failed cases. [Evidence](../../docs/evidence/event-continuation-repair-v1-evidence.json)
records the audit, four verified failure traces, candidate and bounded test results.

Upstream context is [EvanGambit/sts2](https://github.com/evangambit/sts2), MIT licensed,
Copyright (c) 2024 The Complete Contributors. Its license is retained beside the patch.
