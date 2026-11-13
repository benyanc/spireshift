# Event facts, shop counters and native shop-task completion

The two public-fact fixes and the shop-task barrier are implemented and pass
source/saved checks and two fresh paired shop controls. The original game stays
v0.111.0 / 41cef1ea, assembly SHA-256
`9cb4f1ad8c9f284aa8fec3122ffd6d780bbf543d875c817abdd12ff63fbf12b4`.
CLI56 / ordinary worker24 / converter16 / layout12 are unchanged. The new
official adapter is Connector30, source `97c14e74bcb82ed6c0f231dce5ee3ecc45a3a676`,
in environment47,
`sha256:ee1008673da84267143e3fdecb4bd54b3484b3e10b20dfebc4bb05e5cf16beed`.

Both original numerical players and complete Adam states remain unchanged.
There is no training, promotion, controller or playing-strength claim. The
new natural ending panel is prepared and remains owner-run.

## Public facts

Event option enablement now combines the native button's enabled state with
the event model's lock, matching the shipped button's release guard and the
Connector's existing legal-action filtering. A locked option is observed as
disabled; a disabled unlocked option stays disabled. Surface and referent
enablement agree without changing the game model or legal event effects.

Shop relics now use an explicit merchant projection. The merchant's plain
`NRelic` icon does not render an inventory counter. Owned inventory relics use
their separate projection and retain actual visible counters, including zero.
The shop projection does not evaluate an invisible model counter. Card previews,
hover text, amounts and all unrelated facts remain intact. The reviewed shared
exporter has two callers, now explicitly shop and owned inventory; treasure
uses its existing separate projection.

The compiled production helpers pass 36 saved/source vectors. Diagnostic
reprojection changes only E2E607's input 47 and E2E608's inputs 31–36. All
repaired ordered public inputs/menus, frozen-player choices, draws,
probabilities, values and standalone endings then match. Independently,
all 486 actual historical deliveries reconstruct from their original raw
observations and receipts. This saved-only check takes 62.47 seconds.
The old blocked live results retain their original identities and status;
diagnostic reprojection does not turn them into new live passes.

## Shop-task completion

Card, relic and potion purchases retain their exact native
`MerchantEntry.OnTryPurchaseWrapper` task. Removal retains the concrete
`MerchantCardRemovalEntry` overload. Those tasks include the native effect and
awaited `AfterItemPurchased` hooks. Changed gold, stock or acquired items do not
release ordinary decisions while the task is unfinished. No game task, price,
effect or rule is replaced, and no timer supplies completion evidence.

The gate runs before atomic selection advancement and before ordinary/potion
bindings are published. A required child stays usable through its exact overlay
identity: the game's managed active-screen update records overlays opened
inside the retained task's execution context, including across awaits. Merely
visible, pre-existing, foreign or unready screens cannot claim ownership. Once
a child closes, the unfinished parent task continues to block ordinary input.
Run and merchant-inventory identity must still match when completion is observed.

Successful task completion permits native true or false results: canceling a
removal completes normally with false. Unknown acceptance, start exceptions,
faulted tasks, task cancellation and foreign identity remain blocked. The client
does not resubmit them. Authenticated task provenance is separate from policy
inputs; it binds the accepted task ID to completion or the exact required child.
Raw provenance is saved before proof validation.

All 257 exact-assembly Host tests pass, including asynchronous final-hook holds,
nested child ownership, cancellation, faults and identity drift. Eight independent
proof tests and four Python script-safety tests pass. The compiler inventory
finds 158 Connector delivery methods versus 157 before the repair, with exactly
one added tracker entry and no removed entries. Counts include helpers and
routers; they do not establish exhaustive game-content proof.

## Fresh short controls

| Fresh paired control | Deliveries per host | Matched states | Native effect |
| --- | ---: | ---: | --- |
| SH0P803, confirm removal | 3 | 4 | Gold 1,000 to 900; deck 3 to 2 |
| SH0P804, cancel removal | 3 | 4 | Gold stays 1,000; deck stays 3 |

All 12 actual deliveries and eight states independently verify from raw captures.
Both record a pending task with its exact child, then `RanToCompletion` and the
correct true/false result before returning to the shop. The captured settling
state during confirmation has zero actions. Both pairs use fresh declared
privileged saves and native subsequent effects; they are not ordinary episodes
or training data. Both official shutdowns and app/profile/archive resets pass.
No app copy or original model update occurs.

The first SH0P801 control reached its correct child but the diagnostic checker
rejected a pending nullable result omitted by the Connector's JSON serializer.
Its blocked report, partial captures and launch sources are preserved. The
format correction still rejects a boolean outcome without completion; SH0P801
was not replayed. SH0P802 was not attempted. The corrected controls use new worlds.
An initial read-only qualification driver reused a log name across cases; its
failure is preserved, and the corrected driver rechecks saved controls with
separate output folders without replaying games.

Development compile/runtime/cache failures and the build-preparation filename
mistake are also retained. The latter was caught before any game launch; the old
build recipe was restored byte for byte against its prior SHA-256. All 21,031
protected prior files verify exact. The compiler remains the installed pinned
.NET SDK10.0.401; the game still uses its frozen private .NET9 runtime. Both
fresh adapter builds reproduce the same artifact, and portable Connector checks pass.

The scoped awaited shop-task risk is now guarded and qualified by source,
compiled delayed-task tests and real child confirm/cancel effects. This does not
prove every unawaited animation, callback or content interaction. Existing potion,
entry, chest and counter-transition production sources remain unchanged.

See [compact evidence](evidence/native-shop-readiness-repair-v1.json),
`artifacts/native-shop-readiness/saved-checks-v1/`, and
`artifacts/native-shop-readiness/short-qualification-v2/`. Final exact repository
and idle-app/archive verification are recorded after source freeze in
`artifacts/native-shop-readiness/preparation-v1/final-handoff-v1.json`.

## One longer command

Close STS2, then run:

```bash
bash "/Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/compare-shop-endings-v1.sh"
```

This launches two fresh natural pairs, original player 2/E2E609 and player
3/E2E610, with the same fixed working app and fresh isolated profiles. It uses
no fixture saves or forced outcomes. Expect about 5–15 minutes; the outer cap
is 40 minutes including checks and raw verification. Each pair has ten minutes;
each host keeps 128 gameplay CPU seconds and 384 choices. Memory and managed
storage remain capped at 4 GB. The wrapper derives its workspace from its recipe;
shared immutable game/runtime/build caches remain outside per-run storage.

Exact playable inputs/menus, genuine native endings, terminal persistent state,
every public read, official Continue/native summary and clean resets remain
required. Shop task chains receive independent proof verification. Limits stay
incomplete and uncertain actions are preserved without retry. No historical
world or completed control is resubmitted. Broader workflow qualification remains
pending; no automatic learning, promotion, controller or next experiment follows.
