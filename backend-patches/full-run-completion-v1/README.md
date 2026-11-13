# Pinned simulator completion repair

This minimal patch targets EvanGambit/STS2 revision
`37e4264115546b6ac640d54aab3d7e2ac6983d2d`, game v0.107.1. It changes no game assets or card data.
The patch repairs the global-floor/local-map-row defensive ending and the fourth reward's missing
combat-block observation offset. It preserves the original final-boss completion path.

`SpireShiftFullRunCompletionTests.cs` supplies nine synthetic engine regressions. These are direct
engine fixtures, not demonstration games, training data or authoritative real-game conformance.
The owner runs the native build; short cached synthetic checks are allowed. All nine tests passed
on the owner's compiled files after correcting the test-host runtime mismatch. The launcher prefers
.NET 9.0 and permits the installed .NET 10.0 test host with a process-scoped runtime setting;
runtime/SDK evidence is saved. The native publish target remains net9.0. A successful build is
still a pending candidate, and public-choice/difficulty/live-conformance repairs remain outstanding.

Preparation applies the exact patch and copies the test into an isolated private checkout.
Tracked source hashes, the deterministic derived revision, patch/test hashes and a pending
manifest prevent silent reuse of the previous admitted ruleset. The old simulator is not edited.

Upstream: [EvanGambit/sts2](https://github.com/evangambit/sts2). Upstream code is MIT licensed,
Copyright (c) 2024 The Complete Contributors; its license is retained in `LICENSE` beside the patch.
See [the diagnosis and sole owner command](../../docs/full-run-pilot-v1-diagnosis.md).
