# Entry/text ending panel: one pass, one potion-completion gap

The completed E2E605/E2E606 panel has one fully matching ending pair. Player 3
passes all 206 playable decisions, terminal persistent state and every public
read, plus official Continue and the native summary. Player 2 reaches a real
ending in both hosts but remains blocked by two premature post-potion inputs.
Overall compatibility qualification remains ungranted.

The original game v0.111.0 / 41cef1ea and CLI56 / Connector27 / worker24 /
converter16 / layout12 / environment44 remain unchanged. The owner run takes
685.70 outer wall seconds / 246.31 CPU seconds, with no outer cap. Both official
hosts stay below their 128 gameplay CPU-second guard: 72.89 seconds for player 2,
99.39 for player 3. No choice/time/compute limit causes this failure.

## What blocked player 2

The first 43 observed playable inputs match. The next difference is index 43
(the 44th input), immediately after the original player chooses Use Blood Potion
on The Ironclad at index 42. Both hosts start at 54/80 HP. The same potion is
consumed, but the official receipt reports only that native use was enqueued.
It publishes an interactive successor with the bottle gone and HP still 54.

| Zero-based input | State | Native HP | Official HP |
| --- | --- | --- | --- |
| 42 | Choose Blood Potion use | 54 | 54 |
| 43 | Reward Continue available after use | 70 | 54 |
| 44 | Map decision | 70 | 54 |
| 45 | Next combat | 70 | 70 |

The receipt-successor and first post-use policy observations are about 21 ms
apart; the map input follows roughly 51 ms later. The next combat snapshot is about
five seconds later, after healing has appeared. Only those two nonterminal
inputs differ, solely at `/context/persistent/player/hp`; all menu keys and all
104 selected action indices agree in this diagnostic comparison. Both terminal
fact sets also compare equal independently. These later matches do not repair
the earlier input mismatch or permit trace realignment. The player was asked
to choose twice with different HP, so the original blocked result is correct.

The frozen source explains the ordering. `PotionModel.OnUseWrapper` removes the
bottle before awaiting hooks and starting the effect. Its conditional combat
presentation path waits 0.5 seconds before the effect, even though a completed
combat can still supply the combat state. Blood Potion then heals 20% of max HP:
16 here, consistent with both observed final HP values. The Connector's
noncombat use path returns `native_noncombat_potion_use_enqueued`; its explicit
pending-action tracking covers discards, not uses. This is an effect-completion
readiness gap, not evidence of a different healing amount or gameplay rule.
Exact internal action state at each saved snapshot was not logged.

The source also allows potion effects to pause for a child player choice.
The repair must wait for actual completion before unrelated successor decisions
while leaving any effect-owned selection usable. A blanket wait that blocks the
required selector would deadlock. Do not hardcode a healing amount or delay,
rewrite public HP, change game rules, or resubmit the historical action.

## What is now verified

- All 620 acknowledged deliveries independently reconstruct from the original
  raw observations, exact menus, frozen-player choices/probabilities and receipts:
  104 per host for player 2 and 206 per host for player 3.
- All four hosts reach explicit losses. Both official native summaries verify:
  standard loss, score 144, floor 8, ascension 8; no policy actions follow terminal.
- Both map tutorials dismiss once with delivered receipts and no rejection or
  retry. Across their 45 settling snapshots, published mutation actions are empty
  (24 player 2, 21 player 3). This adds live evidence for the tutorial repair.
- Neither pair encounters Aroma of Chaos or a chest. The earlier text
  source/saved qualification and short chest effects retain their existing scope;
  this panel adds no live Aroma or chest coverage.
- All four shutdowns and both official app/profile/archive resets pass. No app
  copy or optimizer update occurs. Both original players, every numerical weight
  and full Adam state, the frozen archive and idle working app verify unchanged.
- All 20,569 protected prior source/configuration/evidence files verify exact.
  Original reports, captures and worlds remain unchanged. A first offline source
  probe expected a direct effect await; the actual source delegates through its
  branching choice context. That failed probe is preserved. The corrected
  saved-only assessment passes in 44.70 seconds without replaying any game.

The full assessment, raw verification logs, exact potion receipt/timeline and
source diagnosis are under
`artifacts/native-entry-text-repair/owner-assessment-v2/`. See the compact
[evidence record](evidence/native-entry-text-ending-result-v1.json).

## Next work

First repair and qualify noncombat potion-use completion readiness with the
saved failure and frozen source. Cover accepted-but-unfinished use, completed
effects, cancellation/unknown states, exact ownership and required child choices;
retain the qualified discard behavior. Use focused fresh transition controls
before proposing another natural ending panel.

Do not rerun `compare-entry-text-endings-v1.sh`, E2E605/E2E606, or any older world
or action. No replacement owner command is prepared by this assessment. Live
compatibility stays blocked overall. After the required finite qualification,
return to varied fitting-only teaching and the separate interference comparison;
no automatic training, promotion, adaptive controller, exhaustive matrix or
playing-strength claim follows this result.
