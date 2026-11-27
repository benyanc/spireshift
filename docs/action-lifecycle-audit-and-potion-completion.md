# Action lifecycle audit and potion completion

The audit now covers every declared action entry point in the pinned original
CLI, our CLI56 and the original/current official Connector sources. The potion
completion repair passes compiled tests, the saved failure regression and two
focused postcombat paired controls. The audit also records open source risks;
it does not certify every game-content interaction.

The game remains v0.111.0 / 41cef1ea, SHA-256
`9cb4f1ad8c9f284aa8fec3122ffd6d780bbf543d875c817abdd12ff63fbf12b4`.
CLI56, ordinary worker24, converter16 and layout12 are unchanged. The new official
adapter is Connector29 in environment46,
`sha256:c7f1b750a7c863a8aba837e8873f91b925de27ced45c8eaec41685e5b9675ace`.
Both original players and complete Adam states remain exact. There is no training,
promotion, adaptive controller or playing-strength evaluation.

## Audit scope and findings

The inventory uses the pinned compiler's C# syntax tree, with exact source hashes,
method bodies, dispatch branches, native calls, awaits and mutation sites. It
covers five source snapshots, including the original Connector for attribution.
The compiler inventory and per-entry lifecycle ledger are private artifacts under
`artifacts/native-action-lifecycles/source-audit-v4/`.

| Layer | Audited entry coverage | Meaning |
| --- | --- | --- |
| Original CLI, revision d11aa883 | All 17 gameplay commands and startup/save/load/debug/cleanup dispatch | Historical source review; not a fresh effect qualification of upstream |
| Our CLI56 | All 26 gameplay commands and control/support mutation sites | Original/current handler comparison, owner checks, waits, child choices, failures and cleanup |
| Original Connector | All 144 NativeInputResult methods | Includes routing helpers and receipt construction |
| Connector27 | All 156 NativeInputResult methods | Exact predecessor of the repair |
| Connector29 | All 157 NativeInputResult methods | New potion action tracking plus unchanged surrounding action families |

These method counts include validators, routers and helpers; they are not counts
of independently proven mechanics. Supporting mutation sites and legacy/admin
paths are listed separately from ordinary Player Environment actions. Unknown
CLI commands or new delivery-provider files fail the audit rather than silently
acquiring coverage. Every row retains its source location/hash, delivery boundary,
completion contract and qualification limit.

The review includes combat play/end-turn/potions, map travel, event choices,
rest, rewards, treasure, shop purchases/removal/presentation, all supported
selection providers and atomic orchestration, tutorials, startup, Continue,
summary, save/load and shutdown/reset. Delivery receipts establish input delivery;
each family still requires its declared effect or next-owner evidence.

| Finding | Attribution | Result |
| --- | --- | --- |
| Potion failure could trigger manual discard; direct enqueue bypassed manual-use hooks | Original CLI | Historical shortcut; already replaced in our CLI |
| Stalled event/selection/turn paths could force map/retry/reset behavior | Original CLI | Historical shortcut; replaced by native ownership/completion or explicit failure in our branch |
| Noncombat potion use acknowledged enqueue before async healing completed | Our Connector extension | Fixed in Connector29 |
| Pending discard expired when its bottle disappeared or its state label changed | Our Connector extension | Fixed in Connector29 |
| Shop purchase/removal starts a background task without retaining a completion barrier | Original and current Connector | Open source risk: existing passed effects do not establish every delayed pickup/hook |
| UI callback delivery alone cannot establish completion of every content interaction | Original/current Connector | Explicit qualification boundary; representative effect evidence is separate |

The open shop finding is not relabelled as a confirmed failed live case or fixed
by the potion work. It needs targeted task/child-choice qualification and, if
necessary, its own repair before broader admission. Two passing natural games
would not by themselves close that finding. Existing matched examples remain
valid within their declared scope.

## Potion repair

The Connector subscribes around the original `EnqueueManualUse` call and captures
its exact native UsePotionAction, owner, slot and acceptance ID. It preserves the
game's BeforeUse/IsQueued behavior. It does not construct a replacement use,
force HP, infer completion from bottle removal or add a sleep.

Normal successor authority is withheld until the native action and its
CompletionTask agree: Finished/RanToCompletion or Canceled/canceled. Missing,
duplicate, foreign-run or faulted acceptance remains blocked for inspection.
Discard tracking now uses the same terminal-task condition rather than the
inventory-removal shortcut.

Required native child choices remain usable only with an identified current
choice owner. A deferred potion behind an existing choice retains that parent
owner. The ownership audit caught the distinction between ScreenEntityId and
HandEntityId before live qualification; both are handled and compiled tests cover
them. Other selectors cannot borrow a completed room's identity.

The readiness gate runs before atomic selection advancement and before normal
or potion bindings are published. Intermediate public facts remain observable,
with settling status and zero actions. The controller does not receive private
action state as policy input. Separate authenticated diagnostic provenance records
native acceptance, observed action/task states and completion, and binds the use
receipt to its actual finished action. Native action IDs may change on resumption;
the original acceptance identity is retained.

Connector28 is a preserved development build. Connector29 is the final reproduced
candidate and includes the hand-owner correction. The original game/runtime and
CLI do not change. The compiler inventory tool uses the already-installed .NET10
SDK runtime; the game continues to use its frozen private .NET9 runtime.

## Short evidence

| Control | Actual deliveries per host | Matched states | Effect |
| --- | ---: | ---: | --- |
| Fresh battle, then Blood Potion | 2 | 3 | Postcombat HP 54 to 70; one bottle consumed |
| Fresh battle, then discard Blood Potion | 3 | 4 | Postcombat HP stays 54; one bottle discarded |

These are explicit privileged diagnostic saves with native subsequent effects,
not ordinary episodes, training examples or wins. Both hosts load the same fresh
save bytes. The setup uses five upgraded Dramatic Entrances and declared relics
to reach postcombat without damage; the game executes the actual battle and
potion operation. It reproduces the consequential postcombat asynchronous path,
rather than only testing an instantaneous potion use at rest.

All ten deliveries and all seven states reconstruct from original raw streams,
including final successors. The official use records WaitingForExecution,
Executing, then Finished/RanToCompletion. Every captured bottle-gone/HP54 state
after use has settling status and zero actions; the next complete state is HP70.
Both paired app/profile/archive resets and all successful host shutdowns pass.
There are no app copies or original-player updates.

All 244 compiled Host tests pass, including lifecycle state, cancellation/fault,
deferred/owned-choice and screen/hand ownership cases. Ten focused Python tests,
nine Node proof tests, type checks and the saved E2E605 negative regression pass.
Both fresh Connector builds reproduce the same artifact. Saved reconciliation
reverifies 728 historical actual deliveries and reproduces all 728 current inputs,
menus, original-player choices, draws, probabilities and values under environment46
in 78.87 seconds. Those old live effects keep their original source identity.
All 20,590 protected prior files and full original weights/Adam remain exact.

The first use collector's exact-eight footer incorrectly rejected its declared
early stop, despite matching complete captures. Its original blocked report stays
unchanged; the corrected verifier independently qualifies the complete two-action
effect and final successor, without replaying that world. An initial native-only
discard script used the wrong normalized verb and stopped before any potion
submission or official launch. Its process was verified absent and retired;
the marker/profile remain preserved. The corrected discard control uses a new
declared world. Development compile/inventory/seed checks are also retained.

The saved qualification is
`artifacts/native-action-lifecycles/short-qualification-v1/report.json`.
See [compact evidence](evidence/action-lifecycle-audit-and-potion-completion-v1.json).
The final exact repository check, archive/app verification and owner preflight
are recorded after source freeze under `artifacts/native-action-lifecycles/preparation-v1/`.

## One longer integration command

Close STS2, then run:

```bash
bash "/Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/compare-action-lifecycle-endings-v1.sh"
```

This is a finite integration check on fresh natural E2E607/E2E608, one pair for
each original player. It is unstarted and owner-run. Expect about 5–15 minutes;
the outer cap is 40 minutes including exact repository checks and raw verification.
Each pair has ten minutes, each host 128 gameplay CPU seconds and a 384-choice
guard. The same fixed app, fresh isolated profiles, 4 GB memory/storage limits,
exact playable inputs/menus, genuine endings, full terminal facts and native
Continue/summary proof remain mandatory. The wrapper derives its workspace from
the recipe; immutable shared build/runtime caches remain outside its per-run
storage accounting.

Do not repeat old worlds, submitted actions or completed fixtures. Uncertain
delivery stops without retry; limits remain incomplete. This command does not
certify the open shop risk or every card/relic interaction and grants no automatic
learning, promotion, controller or broader qualification. Assess its result and
the explicit remaining ledger entries before returning to fitting-only teaching
and the separate interference check.
