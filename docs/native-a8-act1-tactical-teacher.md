# Act 1 tactical teacher

The tactical teacher extends the reward-safe v2 policy on the frozen
Ironclad/A8 build. It uses the existing legal action bindings and commits
policy memory after native delivery.

For elites, it checks whether the current hand can finish every enemy
before spending energy on defense. The bounded search tracks energy, HP
cost, target block, Vulnerable and distinct physical card copies. It
models supported public attack previews and rechecks the native menu
after each play. Unsupported interactions use the existing teacher.

For Waterfall Giant, the planner separates the ordinary HP pool from the
dying phase. Before the transition it preserves affordable block and
prioritizes a supported direct lethal sequence that skips the ordinary
attack and another Steam Eruption increase. During the stun it can
retrieve a visible blocking card for the next turn. During Death Blow it
budgets the full legal hand against the visible damage and checks potions
or draw options when the planned block is insufficient. Survival requires
HP plus block to exceed the incoming damage.

## Native short checks

Four branches matched their saved public menus before diverging. The
fresh smoke case exercised the normal-start tactical teacher. Independent
raw reconstruction verified all 1,115 native deliveries in the final
short run.

| Case | Verified outcome |
| --- | --- |
| Terror Eel at 25 HP | Thunderclap+ and two distinct Strikes reached native rewards at 10 player HP. |
| Giant with earlier round-two defense | Bash, Anger and Strike triggered the dying phase before the ordinary attack. The player died at 17 HP plus 13 block against 30 damage. |
| Giant with earlier round-three defense | Reached Death Blow with 12 HP plus 13 block against 30 and died. |
| Giant at 36 HP on round seven | The three-attack sequence avoided the ordinary attack and lowered Death Blow from the saved 33 to 30. The player died with exactly 30 combined HP and block. |
| Fresh normal-start smoke | Completed a native Act 1 loss at floor 9. |

The first two development controls are retained with their exact launch
sources. One tested using Headbutt to carry a free attack into the earlier
draw cycle. It saved five HP against the round-five attack, then delayed
the transition and reached Death Blow with 17 HP and 8 block against 33.
The default planner uses the earlier transition and whole-hand defense
behavior verified in the final control.

The short qualification gate remains blocked on a genuine Giant rescue.
The build, runtime, SDK, localization, shared save profile and all four
full checkpoint and Adam files passed frozen verification. Optimizer
updates and admitted lessons were both zero.
[Verification record](evidence/native-a8-act1-tactical-teacher-v1.json).

One separate fresh world tested the matched comparison path through all
five arms. All five recorded native Act 1 losses. The first difference
between the tactical and v2 teachers was an earlier Giant block on the
same legal menu. Raw reconstruction verified 997 deliveries. All 2,860
repository tests and the .NET protocol check passed.

## Fresh diagnostic comparison

Close the game and run the following command from the checkout to compare
the tactical teacher with the original, fitted, survival and reward-safe
v2 references on eight disjoint normal-start worlds.

```bash
bash scripts/qualify-act1-tactical-teacher-v1.sh --diagnostic
```

Allow about 6–15 minutes. This comparison records Act 1 outcomes and
confirms any clears from a fresh mount. It has a separate seed namespace
and workspace. The launcher verified the saved short-check gate for this
diagnostic. Qualification still requires a verified Giant rescue. The
comparison starts zero fitting steps and grants zero qualification.
