# Shop ending panel: generated-card context and rest text still differ

E2E609/E2E610 both remain blocked. All four hosts finish with genuine native
losses; both official Continue/native summaries and all clean reset checks pass.
The blockers are two Connector text projection inconsistencies. Player 2 takes
a different action at the first differing input and its subsequent play diverges.
Player 3 differs only in the line break of one rest description.

The original game v0.111.0 / 41cef1ea and CLI56 / Connector30 / worker24 /
converter16 / layout12 / environment47 are unchanged. The owner run takes
782.08 wall seconds and 292.43 CPU seconds, with no outer cap. Official gameplay
CPU is 81.12 seconds for player 2 and 122.62 for player 3, both below 128. These
are completed comparison failures, not choice/time/compute-limit endings.

| Case | Native / official decisions | First differing input, zero based | Blocker |
| --- | ---: | ---: | --- |
| Player 2 / E2E609 | 144 / 143 | 87 | A generated Body Slam offer gains a combat-only damage hint in the Connector. |
| Player 3 / E2E610 | 247 / 247 | 168 | The Regal Pillow rest bonus has a newline in official versus a space in native. |

## Generated card display context

After the same Attack Potion use at input 86, both hosts offer the same cards
and legal controls. At input 87, Body Slam's native text is
`Deal damage equal to your Block.` The Connector adds `(Deals 0 damage)`.
Only six copies of that description differ: the visible card, its linked detail
read, referents and candidate subject. All persistent/combat facts and menus
match up to that point.

The original frozen player chooses Body Slam in native and Skip in official.
Both choices have the same draw key; the text difference changes the policy's
scores and selected action. The differing value estimates are approximately
0.041733 versus 0.034767. The extra generated card then changes the native hand
and subsequent decisions. Later suffixes are different play; do not realign
them or diagnose every later mismatch as a new mechanic bug.

The frozen shipped widget is decisive: `NChooseACardSelectionScreen` calls
`nCard.UpdateVisuals(PileType.None, CardPreviewMode.Normal)`. `NCard` uses that
display pile for `GetDescriptionForPile`. The CLI's generated selection also
uses `PileType.None`. Our Connector's `NativeGeneratedCardChoice` calls the shared
`BuildCard` without a display-pile argument, inheriting its Hand default.
The game's formatter derives `OnTable` and `InCombat` arguments from that
context. The extra suffix therefore comes from the Connector using the wrong
display context; adding it to the CLI would copy the error.

Both eventually lose. Their standalone terminal facts differ only in run floor:
native 8 versus official 9. The official native summary reports score 162/floor 9.
This endpoint difference follows a divergent action history and does not by
itself establish a different damage rule. Neither a score nor floor comparison
is a playing-strength evaluation here.

## Rest description line break

At player 3's input 168, both hosts offer an enabled Rest option with the same
30%/24-HP base heal and 15-HP Regal Pillow bonus. Native exports the two sentences
on one line; the Connector keeps the game's newline before the bonus.
The description differs in three copies: surface, referent and candidate.
This is the only nonterminal public-input difference in the entire pair.

The frozen `HealRestSiteOption.Description` explicitly appends the extra text
with a newline. The CLI's visible-text helper replaces newline with space.
The Connector's card exporter already performs that replacement, while its
rest exporter calls `SafeGetText` without equivalent line-break handling.
This is an inconsistent visible-text convention across exporters, not a
different healing formula.

Both choose Rest and heal from 8 to 47 HP, exactly the same 39-HP effect. All
247 selected action indices and the standalone terminal persistent state and
every public read match diagnostically. The official summary reports score
273/floor 15. Value estimates still differ slightly at the text mismatch, so
the input cannot be silently ignored or the blocked pair relabelled as passing.

## Repairs exercised and assessment

Player 3 completes two native card purchases at inputs 29 and 30, before the
first text difference. Both retained wrapper tasks report successful completion;
their actual receipt/proof chains independently verify. Shop catalogs and the
surrounding public inputs match. This adds natural card-purchase evidence to
the earlier source, delayed-task and child confirm/cancel checks.

Neither run reaches a locked event option or a Pendulum offer. The prior
event-enablement and shop-counter controls keep their existing scope. Neither
run exercises repaired noncombat potion use; the Attack Potion choice above
is a combat path. No new evidence should be claimed for those unexercised cases.

Saved-only assessment independently reconstructs all **781 actual deliveries**:
144 native/143 official for player 2 and 247 per host for player 3. It verifies
full source observations, exact menus, frozen-player choices/probabilities,
actual receipts, both native summaries and both shop-task proof chains.
The assessment takes 56.03 seconds and launches no game.

All 21,031 previously protected files remain exact. The expanded 21,336-file
map also preserves current source/configuration/evidence, the completed panel
and original raw captures. Both original numerical players and full Adam
states, the frozen archive and restored idle working app verify unchanged.
No adapter source, old report, input, game rule or optimizer is modified by
this assessment. See
`artifacts/native-shop-readiness/owner-assessment-v1/` and the compact
[evidence record](evidence/native-shop-ending-result-v1.json).

## Next work

Audit every shared card-exporter call against the shipped widget's display
context, including generated/simple choices, hand selections, deck/shop/pile
views and upgrade previews. Make the context explicit so a new caller cannot
silently inherit Hand. Exercise conditional descriptions controlled by
`OnTable`/`InCombat`, including actual zero values, using source/saved regressions.
Do not fix Body Slam by name or invent a damage amount.

Use one consistent visible-text line-break convention across affected exporters,
preserving words, amounts, ordering, image glyphs and unfamiliar facts. Test
Regal Pillow and other multiline rest text through the actual surface/referent/
candidate path. Do not repair this in the comparison by discarding description
fields, masking numbers or ignoring whitespace differences.

These are the proposed next repairs, not a newly implemented adapter. Do not
rerun `compare-shop-endings-v1.sh`, E2E609/E2E610, or the completed short controls.
No replacement long command is prepared by this assessment. Broader workflow
qualification remains blocked; there is no training, promotion, adaptive
controller, automatic next experiment or full-game strength claim. Keep the
finite compatibility finish line before fitting-only teaching/interference.
