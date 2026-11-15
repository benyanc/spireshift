# Tutorial-entry readiness and native visible text

The source and saved regressions pass. The original game stays v0.111.0 /
41cef1ea, with assembly SHA-256
`9cb4f1ad8c9f284aa8fec3122ffd6d780bbf543d875c817abdd12ff63fbf12b4`.
The new adapter tuple is CLI56 / Connector27 / worker24 / converter16 / layout12 /
environment44. Both original players and their complete Adam states stay exact.
No game is launched by this preparation, and no training or promotion occurs.

## Repairs

The map-selection tutorial can mount after its 100 ms native delay while the
room behind it is changing. Combat's `IsInProgress` becomes true before
`BeforeCombatStart`, first-turn hooks, energy reset and the first hand complete.
The former Connector treated an enabled tutorial button as ready throughout
that transition. E2E603's unchanged Got it! action consequently received
`not_delivered / stale_snapshot` when its background changed from unknown to
initializing combat.

Connector27 withholds mutation authority for that map tutorial until travel is
finished and the native room entry is ready. For a closed map over combat this
requires the actual combat/room/hand objects and the local player's native Play
phase. Snapshot status is settling; normal actions, potion actions and atomic
advancement remain unavailable. The exact map-tutorial delivery handler also
rechecks readiness before clicking. It never resubmits an old action.

The guard allows an open map that still retains the completed combat room. It
does not require the public `is_play_phase` permission, because the modal itself
can disable player actions. Shuffle and other tutorials keep their own setup
controls. Native phase is used solely for readiness diagnostics and is not added
to player inputs. No counter or gameplay rule changes: Ornamental Fan's saved
counter remains absent before combat and visible at 2 during the observed setup.

CLI56 changes only `StripVisibleText`. It recognizes rainbow's supported numeric
`freq`, `sat` and `val` parameters, including spaces and decimal values. This
removes the non-visible opening token that survived in E2E604's Aroma of Chaos
body. Image filename glyphs, glyph order/multiplicity, numbers, spacing and
unfamiliar parameterized bracketed facts remain intact. Malformed image markup
still fails explicitly. The legacy simple-tag behavior remains unchanged.

These are adapter/export repairs. The frozen official game assembly, game
rules, worker, converter, input layout, chest repair and summary collector are
unchanged. Source comparisons bind every changed and unchanged production file.

## Short checks

The standalone probe loads the actual reproduced CLI55, CLI56 and Connector27
assemblies and calls their rendering/readiness methods. It starts no game or UI.

| Check | Result |
| --- | --- |
| Independent native builds | Two baseline and two repaired builds reproduce exactly |
| Independent Connector builds | Two fresh source builds reproduce exactly |
| Compiled Host tests | All 221 pass, including 12 new tutorial cases |
| Compiled entry vectors | All 142 pass; pending cases have no mutation authority |
| Frozen English localization | All 6,902 strings checked; exactly four expected changes |
| Text edge cases | All 18 pass, including glyphs, numbers and unknown markup |
| Saved Aroma mismatch | Repaired body and entire diagnostic public input match official exactly |
| Saved tutorial failure | Original rejected receipt preserved; unknown/initial combat remain settling |
| Prior source/configuration/evidence | All 20,380 protected files remain exact |

The four corrected localization entries are the Aroma of Chaos, Colossal Flower
and Crystal Sphere event text and the Defect epoch description. The other 6,898
strings retain their previous output. This is coverage of the frozen English
content and declared edge cases, not every future effect, language or game patch.

The source/saved check takes 23.37 seconds. Its raw diagnostic inputs, compiled
probe, outputs, test results and report are retained under
`artifacts/native-entry-text-repair/source-saved-v2/`. The report explicitly keeps
the historical pairs blocked. The saved phase vectors are source diagnostics;
they do not claim a newly captured live UI transition or repaired historical
delivery. Later observations in the old traces are never realigned for admission.

The initial development Connector artifact had different source-link metadata
from the canonical fresh clone. Its proposal, source and failed identity check
are preserved. The canonical artifact is frozen under the separately named
`connector-entry-readiness-reproduced-v27` configuration and reproduced twice.
The failed build attempt launched no game and submitted no action.

The first final type check caught two local variable-name collisions in the
offline audit. Its failed receipt and all 31 development source/configuration
files are preserved in `pre-type-fix-source-snapshot/`. The corrected harness
passes the type check and fresh source/saved qualification; both game-facing
assemblies remain the same reproduced bytes. New saved and owner recipes use
revision v2. Earlier source/saved results retain their development identity.

Saved reconciliation separately verifies all 728 historical actual deliveries
under their original source and reproduces all 728 current inputs, menus and
original-player choices under environment44. Full weights/Adam, draws,
probabilities and values stay exact; only declared binding/environment metadata
changes. Historical live effects retain their historical source identity.
See [evidence](evidence/native-tutorial-entry-text-repair-v1.json). Final exact
repository-check and preflight receipts are recorded after source freeze in
`artifacts/native-entry-text-repair/preparation-v1/final-handoff-v1.json`.

## One owner-run command

Close STS2, then run:

```bash
bash "/Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/compare-entry-text-endings-v1.sh"
```

This starts two fresh natural pairs, player 2 / E2E605 and player 3 / E2E606,
using the original players and one fixed working app with fresh isolated
profiles. Expect about 5–15 minutes; the outer cap is 40 minutes, including exact
repository checks and raw verification. Each pair has ten minutes, each host
128 gameplay CPU seconds and a 384-choice guard. Memory/storage caps remain
4 GB; the wrapper derives its workspace from the pinned recipe and counts the
single working app. Shared immutable build/runtime caches remain outside that
per-experiment storage measurement, as in the parent plan.

The plan requires ordered exact playable inputs/menus, genuine matching native
endings, all public terminal facts, official Continue/summary proof and clean
shutdown/reset. No fixture saves, forced outcomes, historical seeds/actions,
budget increase or retry is allowed. Limits remain incomplete; uncertain
delivery is preserved. This long run remains unstarted and owner-run.

Live workflow qualification remains pending. Assess the fresh result before
finishing finite compatibility and returning to varied fitting-only teaching
and the separate interference check. No automatic training, promotion, adaptive
controller, exhaustive matrix or playing-strength claim follows this command.
