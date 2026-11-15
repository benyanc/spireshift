# Act 1 boss teacher v2 result

All eight matched normal-start Ironclad/A8 worlds sealed. All 32 arms
ended in genuine native Act 1 losses. The run completed the panel and
returned the failed qualification status. No arm reached a cap, and
the boss teacher recorded zero reopens of declined rewards.

| Arm | Act 1 clears | Boss encounters reached | Native losses |
| --- | ---: | ---: | ---: |
| Original | 0/8 | 1 | 8 |
| Update 200 | 0/8 | 0 | 8 |
| Survival teacher | 0/8 | 2 | 8 |
| Boss teacher | 0/8 | 3 | 8 |

Against the survival teacher, the boss teacher reached the same floor
on six worlds, went farther on one, and died earlier on one. Their first
different choice was a card reward on all eight worlds. The resulting
routes, decks, and combat choices can all contribute to the outcomes.
Qualification admitted zero lessons and performed zero optimizer updates.

## Where the teacher lost

Five boss-teacher runs died in elites. Each final route menu before
those fights offered an elite as its only map destination. A route
change would need to act at an earlier fork.

The Terror Eel loss gives a concrete combat diagnostic. The round-nine
menu offered Thunderclap+ and two distinct Strikes for one energy each.
The teacher spent one of its three energy on Second Wind+ and played
Thunderclap+ and one Strike. Those attacks dealt 10 and 9 damage and
left the Eel at 6 HP. The second Strike has the same visible damage
preview as the one played. The three-attack sequence projects 28
damage against 25 HP. The native outcome of that sequence still needs
a branch check.

| Boss teacher fight | Entry HP | Evidence at the end |
| --- | ---: | --- |
| Lagavulin Matriarch | 73 | 82 of 233 boss HP remained. The teacher took 21 damage after spending the previous turn on three attacks with two Defends offered. On the final turn it had 18 HP and 3 block against a 22-damage intent. |
| Waterfall Giant | 47 | The teacher depleted the ordinary 250 HP pool. It then dealt 72 damage into the temporary 999,999,999 HP pool. The visible Death Blow threatened 30 damage. The player ended at 9 HP and 5 block. |
| Soul Fysh | 48 | The boss had 25 of 221 HP remaining. The player ended at 17 HP and 5 block with a 24-damage attack visible and three Beckon cards still in hand. The card text also shows an end-of-turn HP loss while held. |

Waterfall Giant's Steam Eruption status shows the coming damage before
the ordinary health pool is depleted. The planner continued valuing
damage during the dying phase, even though the immediate objective was
to survive the Death Blow. The final hand offered a single 5-block
Defend. A defense change needs to begin earlier.

## Next development step

Verify the Terror Eel three-attack sequence from its exact recorded
public menu at floor 8, round 9 of `boss-v2-006`. The branch must
reconstruct the current menu before trying Thunderclap+ and the two
distinct Strikes. Compare actual native fight completion with the saved
loss. Use a separate earlier Waterfall Giant branch at floor 17, round 3
of `boss-v2-003` to test saving HP for Steam Eruption and surviving the
Death Blow. Keep these branches diagnostic. Use their actual outcomes to
decide how to extend turn planning to elites and account for delayed
threats before another fresh panel.

The saved assessment checked all eight world seals and independently
reconstructed all 5,323 native deliveries. The game build, runtime, SDK,
localization and all four full checkpoint and Adam files passed frozen
verification. The assessment started zero games. Full-run A8 victory
remains the primary evaluation outcome.
[Verification record](evidence/native-a8-act1-boss-v2-result-v1.json).
