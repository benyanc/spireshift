# Public-menu repair candidate

This append-only sidecar builds on the separately verified completion/reward repair
`99fad6a73912e26af6872c2f0742ebeb5ffb3581`, for the same frozen v0.107.1 game.
The original simulator and first candidate remain intact. The new candidate is private under
`artifacts/backend/evangambit-v0.107.1-full-run-repair-v2`.

State lists 22/23/24 expose only the open combat menu, selected-bundle/confirmation state, and a
versioned source declaration of fixed Ascension 8. Existing state-list IDs, observation offsets,
action meanings and binary rewards remain unchanged. The normal vector's first ten menu slots
now use the same projection, including correct draw-pile selection kinds and generated upgrades.
Consumers query required length before reading list 22; silently truncating it is an error.

The Python sidecar decoder binds every offered action, rejects absent/extra choices and retains
both bundle choices alongside the enabled confirmation. It never queries private lists or exposes
raw pile indices. Historical adapter/encoder/model files are unchanged. A separately versioned
adapter and unified player now consume these readouts; this patch alone does not improve strength.

All 23 targeted synthetic C# tests (the earlier nine plus fourteen menu/profile tests) passed in
a five-second check capped at 45 seconds, with no native publish, game attempts or training.
The owner subsequently built the native library in 9.588 seconds, again passing all 23 regressions,
and checked the actual sidecar exports. Two short real native replay prefixes then passed the
previously reproduced reward and overflow-menu errors. The next owner command is
`scripts/audit-full-run-public-integration-v1.sh`, which checks all 89 failed training attempts and
stops before training. [Saved evidence](../../docs/evidence/public-choice-integration-v2-evidence.json)
records these separate stages. Results remain pending conformance.

The run source defaults to A8 and exposes no difficulty argument. Reset resources, potion slots,
starter curse and combat default are tested. This is a source profile, not proof of full live-game
A8 conformance and not support for A0. Real-game checks and re-admission still precede learning.

Upstream patch context is from [EvanGambit/sts2](https://github.com/evangambit/sts2), MIT licensed,
Copyright (c) 2024 The Complete Contributors. Its license is retained beside this patch.
