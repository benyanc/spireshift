# Native bundle synchronization checker

This .NET 9 tool checks the MIT wrapper's bundle interception against the licensed local
v0.111.0 assembly. It calls the original native choice synchronizer and observes its
`PlayerChoiceReceived` callback. Each requested seed exercises both pack indexes.

The bounded fixture checks exactly one reserved choice and callback per valid selection,
correct native card-object delivery, no early completion, rejected malformed/duplicate/overlapping
choices, cancellation during cleanup, and explicit failure without a simulator. Invalid input
must not change native RNG or pools. Global TestMode stays on. This is a privileged native
lifecycle fixture, not a shipped-game or full-run benchmark.

Build with `CandidateDirectory` pointing at the private qualified v12 candidate. Redirect all
intermediate and output files under ignored `artifacts/engine-tooling/`; no game dependencies
are copied or committed. Resolve native dependencies from that candidate before entering the
no-inline exercise method. Run using its separately pinned .NET 9.0.7 host and the existing
profile/archive isolation sandbox.

The saved two-seed result has 58 checks across four native starts. Public SDK action binding,
invalid/stale operands, natural reset and actual shipped preview/cancel/confirm are checked by
separate probes. See [bundle package evidence](../../docs/evidence/actual-engine-v0.111.0-bundle-choice-v12.json).
