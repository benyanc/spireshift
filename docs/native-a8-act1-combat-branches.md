# Act 1 combat branches

Three isolated native branches replayed the recorded boss-teacher choices
from normal starts to exact public menus in the
[completed v2 panel](native-a8-act1-boss-v2-result.md). The verifier matched
642 prefix menus and independently reconstructed all 702 native deliveries
from raw observations, action bindings and successor receipts. Each branch
ended in native combat rewards or a verified loss.

| Branch | First change at the saved menu | Native result |
| --- | --- | --- |
| Terror Eel, round 9 | Thunderclap+ replaced Second Wind+ | Won the fight. Eel HP went 25 → 15 → 6, then the second Strike opened combat rewards with 10 player HP. |
| Waterfall Giant, round 3 | Defend before Bash | Lost at Death Blow with 12 HP and 13 block against 30 damage. |
| Waterfall Giant, round 2 | Second Defend replaced Strike | Lost at Death Blow with 7 HP and 5 block against 33 damage. |

The Eel proof used three one-energy attacks from the same turn. The saved
menu contained two distinct Strikes, and the replay still offered one
after the first was delivered. This gives the elite planner a concrete
regression for choosing a complete legal lethal sequence before spending
energy on block.

The round-three Giant branch reduced damage in that round by five. The
changed draw cycle exposed zero Defends against its 20-damage round-five
attack. Headbutt recovered Defend+ for the following turn, and the branch
blocked all 13 damage there. It still needed six more points of HP or
block to survive Death Blow. The round-two branch conserved five more HP
early and left the Giant at 6 HP on round seven. Its attack landed before
Demise moved it into the dying phase and the eruption grew to 33.

At that round-seven menu, the earlier defense branch had an alternative
with Bash, Anger and Strike against 36 remaining boss HP. A legal lethal
sequence there could avoid the ordinary attack and the extra eruption
growth. Its successor hand and Death Blow survival still need native
verification. The defense planner needs to account for both the turn
that triggers the dying phase and the block available when it resolves.

## Reconstruct the saved checks

The native run took about 31 seconds. Use this command from the checkout
to independently reconstruct the saved observations and deliveries.

```bash
bash scripts/check-act1-combat-branches-v1.sh --verify
```

The original v2 seals and all three branch seals are retained. The build,
runtime, SDK, localization, shared profile and four full checkpoint and
Adam files passed the frozen checks. The branch evidence is local to
these fights. The run admitted zero lessons and performed zero optimizer
updates. [Verification record](evidence/native-a8-act1-combat-branches-v1.json).
