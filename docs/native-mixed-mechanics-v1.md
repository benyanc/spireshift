# Mixed rest-site mechanics and combat intent inputs

The diagnostics use frozen Slay the Spire 2 v0.111.0 / 41cef1ea, the current
Ironclad/A8 headless worker, and the separately identified Connector32 against
the same official game. The game assembly, original checkpoints and full Adam
states are verified before and after. Fixture actions are diagnostic, and
optimizer work is zero.

## Findings and repairs

- Connector31 could publish an incomplete rest menu. After a successful option
  enabled Proceed, a later choice temporarily disabled the other buttons while
  the game's UI rebuilt them. In a paired case, Dig had already granted a relic
  while the Connector published Proceed with Heal and Smith disabled. Connector32
  keeps the rest observation settling until every option the game marks enabled
  has its current actionable button. Smith after Cook removes every upgradeable
  card is correctly published as disabled in a ready menu.
- Potion descriptions now use the same single-line export as the CLI in owned
  belts, noncombat controls, shops and rewards. The saved Foul Potion difference
  was one native line break repeated through several public views.
- The new combat intent encoder reads total announced damage for each enemy
  bound to a legal action. It preserves the raw public observations, action
  choices, all other features and copied weights and Adam. Inference, PPO
  reconstruction and archive fitting share the new encoding. Old study
  checkpoints keep their recorded encoder.

## Coverage

The saved audit verified 17,317 model menus and native deliveries across 128
games, including 11,047 combat menus. It recorded 12 decision families, 43
observed combinations of decision owner, verb and subject, and 69 observed
transitions to a successor owner. The correction affects 3,821 rows in 1,659 menus,
including 725 actions the earlier policies sampled. Both copied fitted
checkpoints reloaded with their full Adam and produced the same corrected
candidate rows in inference and learner input preparation. Two fresh normal-start
prefixes then reconstructed 24 model-owned native deliveries each using the
corrected encoder.

The native rest matrix generates all 24 orders of Heal, Smith, Dig and Lift
under Miniature Tent. Each step checks the remaining exact options and bindings,
current owner, public HP, maximum HP, deck, relics, counters and potion slots.
Additional cases exercise cancel and reopen, potions inside a card selector,
early exit with options available, one choice without the Tent, Girya's cap,
disabled Smith, Cook's ordered card removal, Hatch, Clone and Kindle. The short
paired panel compares selected cases through the same learner converter with
the Connector's actual deliveries and clean game reset.

| Check | Verified coverage |
| --- | --- |
| Full native rest matrix | 32 cases, 185 native deliveries |
| Paired rest checks | Seven cases, 47 identical projected states and 80 deliveries across both hosts |
| Saved native audit | 128 games, 17,317 full menus and delivered choices |
| Corrected learner smoke | Two fresh 24-decision prefixes with exact reconstructed choices and receipts |
| Repository checks | 2,991 tests, clean .NET build and C# protocol check |

The first five paired cases completed before the original combined check hit
its wall limit at the next case's initial read. The two-case check verified
Clone and Kindle. A saved recheck validated the effects and exact projected
inputs of all seven completed pairs under the current assertions.

| Local artifact under `artifacts/native-mixed-mechanics` | Report ID |
| --- | --- |
| `native-1794761603156619000/report.json` | `sha256:3f624dde0f1d2a80978b8c1583df2fa302cc77e3a9209b60b05d0cf3eee0b182` |
| `paired-evidence-1794761752597252000.json` | `sha256:9970d0ee78d9aae98d89708a56485bd3a6f945fec4cd2137c97bb6400b5e5b78` |
| `saved-1794761655778369000/report.json` | `sha256:a7996d348f978dbbbeaf3e396e47357eb3bb9cbcbf2b9a8844c9b01148112c73` |
| Connector32 build in `connector-build-v32-mixed/report.json` | `sha256:449526443b2e8f276b41574108661bab1c754d423f18b98ceff02f24ea2b18a7` |

This scope covers single-player rest-site actions on the frozen build. Mend is
a multiplayer action. Larger official selectors and unobserved later-act
combinations remain separate open coverage. The saved observed transition
counts are a starting point for targeting such gaps with fixtures.

Use `scripts/check-mixed-mechanics-v1.sh` with `saved`, `native`, `paired`, or
`paired-extra` for the short checks. With STS2 closed, `paired-all` runs the full
paired rest matrix with a 30-minute outer cap. The results and journals go under
`artifacts/native-mixed-mechanics`, including the observed evidence from blocked cases.

## Full matrix launch correction

The first full paired attempt stopped with zero official deliveries. Its
fixture seed contained an `I`, which the official client rejected after the
game process started. The interrupted working app remains marked for inspection.
Every base game file matches the frozen archive. Only the executable mode and
the test Connector's installed files and profile override differ from baseline.

The full paired plan uses the verified short-control fixture seed for all 24
orders. The runner checks all paired seeds and the shared app's readiness before
preparing any fixture. Each prepared save must record its declared seed. All 32
cases and 185 native deliveries passed on the corrected plan. The native report
is `native-paired-plan-1794764334595140000/report.json` under the workspace above.
The full official run requires an inspected reset of the interrupted test copy.
