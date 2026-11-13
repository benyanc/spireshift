# Act 1 loss audit and the next training change

The saved comparison covers 24 original/fitted pairs, with both numerical
initializers on the same 12 fresh Ironclad/A8 worlds. The audit matched all 48
sealed journals and checked 6,873 delivered Act 1 actions.

| Act 1 observation | Original | Update 200 |
| --- | ---: | ---: |
| Death before reaching the boss | 17/24 | 20/24 |
| Deaths in ordinary fights | 7 | 9 |
| Deaths in elite fights | 9 | 11 |
| Deaths in boss fights | 7 | 3 |
| Deaths on an event choice | 1 | 0 |
| Mean HP after the opening fight | 58.0 | 57.0 |
| Mean HP entering an observed elite fight | 56.4 | 43.3 |
| Mean HP entering an observed boss fight | 65.4 | 27.0 |
| Deaths immediately after spending lethal HP on a card | 0 | 4 |
| Combats with a legal potion use offered | 25 | 1 |
| Combat potion use actions | 24 | 1 |
| Potion discards that emptied the belt | 37 | 47 |
| Bought a potion into an empty belt, then discarded it on the next action | 6 | 4 |
| Cards purchased | 16 | 27 |
| Potions purchased | 15 | 6 |
| Smith selected with Rest offered at half HP or below | 0/17 | 12/20 |
| Act 1 clears | 0/24 | 1/24 |

The elite HP rows describe encounters that each policy reached. Fitted players
died in 11 of their 16 elite fights. Originals died in 9 of 20. The fitted
players also used the only combat potion they were offered, so most of the
observed difference was in buying, keeping, and carrying potions into fights.
The originals also discarded resources, including six newly purchased
potions. Both groups can improve on this behavior.

## What the paired journals show

The first different selected action in every pair came on floor 1 or 2, with
identical public inputs and menus up to that decision. Thirteen first
differences were strategic choices, six were visibly different combat
actions, and five selected different slots with the same displayed combat
label. Routes, decks, and HP subsequently diverged. The aggregate comparisons
describe the observed trajectories. They leave the outcome of unchosen
alternatives open.

Four direct losses have stronger evidence. Each card's visible HP cost was at
least the player's current HP, each menu also offered Defend, and the immediate
native successor was terminal at zero HP.

| World | Fitted player | Floor | Selected card | Current HP | Card HP cost |
| --- | ---: | ---: | --- | ---: | ---: |
| 04 | 2 | 5 | Blood Wall+ | 1 | 2 |
| 08 | 2 | 17 | Bloodletting | 2 | 3 |
| 10 | 2 | 9 | Bloodletting | 2 | 3 |
| 10 | 3 | 9 | Hemokinesis | 1 | 2 |

In world 10, both fitted players bought a Vulnerable Potion at floor 7 and
immediately discarded it from an otherwise empty belt. Both died to a
lethal card play against Skulking Colony at floor 9. In world 8, original
player 3 rested at 38 HP and entered Vantom at 62 HP. Fitted player 3
selected Smith at 12 HP and entered the same boss at 12 HP. Both lost.
World 7 also shows the fitted player's useful exception. Both player 2
policies rested at the last camp. The fitted policy entered Ceremonial
Beast at 51 HP and cleared with 10 HP. The original entered at 34 HP and
died. Their earlier routes and decks differed.

## Next training change

For the next copied-checkpoint fit, use verified Act 1 rescues from fresh
normal starts as the lesson source. Keep the current encoder and fitting
method fixed for the first comparison so the change tests the data. The
existing curriculum has 25 prepared-start lessons and zero wins from its 32
normal-start attempts. Qualify the teacher on new starts before fitting.

Target decisions where the journals show clear gaps. Include low-HP
card choices with an immediate safe alternative, potion choices that
preserve or spend a usable resource, and Rest versus Smith before a
dangerous fight. Compare legal alternatives from the same verified public
state and inspect the resulting native continuations. Record immediate
survival separately from an Act 1 clear. Admit Act 1 rescues only when
the better continuation actually clears the act and the paired reference
fails. The four historical lethal plays identify the decision pattern for
new training cases.

Keep the 12 audited worlds for development diagnosis. Collect and qualify
lessons on a separate seed set, and test copies against the frozen originals
and update-200 checkpoints on fresh matched starts. More Act 1 clears are
the first development milestone. Full-run A8 wins remain the primary result.

The audit launched zero games and performed zero optimizer updates. It
verified the frozen host, game archive, runtime, SDK, and the four full
checkpoint states including Adam before and after reading the journals.
[Verification record](evidence/native-a8-act1-loss-audit-v1.json).
