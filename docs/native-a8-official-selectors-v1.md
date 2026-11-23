# Official/native shop and reward selector comparisons

The six paired controls are prepared on frozen STS2 v0.111.0 / 41cef1ea.
The short native panel passed all six with 48 native deliveries and two local
answer factors. All four full checkpoint and Adam states, the game archive,
native host, localization, SDK and numerical runtime verified before and after.
There were zero optimizer updates. The official pairs await the open personal
game being closed. These controls measure adapter correctness, not playing strength.

| Shared fixture | Required paired behavior |
| --- | --- |
| Thirteen-card Kifuda | Preserve every ordered answer, interleave healing/discard at the empty prefix, append two local factors, commit once, enchant exactly those copies and charge once |
| Card reward taken | Win the fixture fight through legal card plays, heal/discard in the child, take one card, collect sibling gold and enter the next room |
| Removal canceled then confirmed | Preserve the service, gold and deck on Cancel, reopen, remove the exact selected copy, charge once and restore the shop |
| Three-card Kifuda | Expose all direct ordered answers, confirm the chosen order and return to the shop with exact stock and resource changes |
| Empty Kifuda answer | Confirm zero cards, preserve the deck and consume the purchased offer once |
| Card reward skipped | Preserve the deck and native skipped-offer state, collect sibling gold, exit through the map and enter the next room |

Every case loads the exact same serialized save on both hosts. The shop save
funds purchases, sets HP to 48/80, supplies Blood/Foul Potions and places the
existing Kifuda entry at the end of the shop relic bag. Reward saves load an
ordinary generated first-room fight with five Bludgeon+ cards and 20 maximum
energy. The game generates enemies, card draws, rewards and their effects.
These are explicitly privileged diagnostic fixtures and supply no training data.
They are separate from the earlier native-only reward fixture.

The runner compares the complete shared v17 public input and legal menu before
each choice. It binds that choice to the current official snapshot and checks
the actual SDK receipt. A first difference aborts the comparison without
realigning later states or choosing a fallback. Saved public reads independently
reconstruct every offered frame, selected action and final successor.
Native effect assertions cover physical card copies, exact gold and healing,
stock and service consumption, sibling rewards and task settlement. Equality
with those observations is required throughout the official chain.

## Connector change

Connector v32 enumerated complete ordered card answers and rejected domains
above 512. Thirteen cards with zero through three ordered selections have
1,886 answers. The separately identified Connector v33 uses the native learner's
existing `factorized_ordered_card_answer_v1` format for large domains.

Append updates only an adapter-local ordered prefix. The public prefix changes
the snapshot binding, so a stale append cannot be submitted against it. The
connector publishes no potion actions after an unfinished prefix has begun,
and rejects interleaved nonselection input. Confirm delivers the entire ordered
answer through the existing native selection transaction. Cancel remains
available only where the game's exact preferences allow it. Small domains
retain their complete direct-answer menus.

Authenticated completion evidence proves zero native card inputs for each
local factor. Final confirmation or cancellation must prove the selected
physical cards, their order, required UI controls and owner departure. Uncertain
delivery stays blocked without retry. The two fresh v33 builds are byte-identical.
Twelve targeted C# selector tests and the Python/Node regressions pass.
The frozen game assembly and headless host binaries are unchanged.

## Inspected test-copy reset

The earlier mixed-rest case remains a failed case with zero official pairs.
Its noncanonical seed was rejected before the client imported the SDK or
registered a controller. The exact failure log, empty game logs, absent action
journal, original lease and complete working-app inventory are sealed in a
separate inspection. No historical gameplay is retried.

After STS2 closes, this comparison may apply that specific inspected reset under
both app locks. It verifies every original file and permits only the executable's
added execute bits and the five recorded test-owned additions. It preserves those
additions and the active marker in the new comparison's `inspected-reset` folder,
then restores the same app to its frozen baseline. The original failed evidence
stays intact. Unknown files, changed game bytes, another lease or a running game
stop the reset. No replacement app copy is created, and no personal save files
are reset. Other historical interrupted workers remain blocked.

## Run

Close STS2, then run the command below. Allow roughly 8–15 minutes with a
20-minute outer limit. The recipe also caps CPU, memory and comparison storage.
The existing app pool retains its separate storage cap.

```bash
bash scripts/compare-official-selectors-v1.sh
```

The launcher uses the already sealed six native controls. It runs the six
official counterparts, verifies the personal save profile and frozen archive,
and requires natural child shutdown and app reset after each case. A clean
completed pair can resume only with matching recipe, native case seal and
reconstructed raw receipts. An incomplete pair is preserved and blocks retry.
The two-pair `short` mode is also available for local development. Nothing
automatically trains, promotes a checkpoint or launches another experiment.

The recipe is
`configs/native-compatibility/sts2-v0.111.0-a8-official-selectors-v1.json`.
Evidence is recorded under the workspace declared there. The compact committed
record is [the preparation evidence](evidence/native-a8-official-selectors-v1.json).
Broader combinations, other selection owners and full-game official competence
remain separate coverage obligations.
