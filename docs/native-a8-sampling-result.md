# A8 paired sampling result

All 16 matched pairs completed as 32 genuine native losses. Sharper sampling
yielded zero Act 1 clears and missed the predeclared clear gate.
The subsequent turn-rescue collection completed with zero rescues.
[Turn rescue result](native-a8-turn-rescue-result.md).

| Sampling | Games | A8 wins | Act 1 clears | Bosses reached | Opening fight rewards reached |
| --- | ---: | ---: | ---: | ---: | ---: |
| Standard, temperature 0.8 | 16 | 0 | 0 | 9 | 5 |
| Sharper, temperature 0.4 | 16 | 0 | 0 | 9 | 5 |

The model made different choices in all 16 pairs. Sharper sampling reached one
additional floor in one pair and tied in 15. The two settings produced zero
verified opposite opening-fight outcomes. [Comparison design](native-a8-coverage-result.md#paired-sampling-qualification).

The saved audit verified 1,952 sealed files and reconstructed 6,847 native
deliveries, including 5,196 setup deliveries and 1,651 suffix deliveries. It
matched the source prefixes, root draws, sampling probabilities and endings.
The frozen game build, original checkpoints, full Adam, runtime and shared
profile passed verification. The games exercised zero local ordered-answer
factors. [Saved result](evidence/native-a8-sampling-result-v1.json).

## Collect action-scoring evidence from verified combat outcomes

In the previous 48 fresh training games, 47 losses ended in combat. In 44 of
those 47 cases, End Turn was the only legal choice on the fatal menu. The
remaining three menus with alternatives all belonged to player 3 elite fights.
The next comparison branches at an earlier choice-bearing menu and observes
the native result through the whole encounter. [Source bank](native-a8-coverage-result.md).

The [turn rescue recipe](../configs/native-learning/sts2-v0.111.0-a8-turn-rescue-v1.json)
uses 12 distinct training worlds, with two ordinary, two elite and two boss
losses per initializer. It takes the first offered menu of the penultimate
combat turn, falling back to the opening menu of the last turn if needed to
find a visible choice. The recorded loss is the reference for the exact
public state and original first action. Two other worlds supply short controls.

Each of the 24 training-only probes regenerates the exact original prefix
with the frozen model. At the root, it samples from the same scores conditional
on a legal action with a different visible label than the reference action.
The regular full-menu policy owns the continuation. A rescue requires the
actual native reward screen in the same fight, with the player alive. Each
success is evidence for a complete sequence of choices from the common menu.
The regenerated prefix serves as setup, and the conditional probe is excluded
from ordinary on-policy PPO.

The fixed gate requires all 24 probes to finish with verified room outcomes
and at least two rescued worlds per initializer across at least two encounter
types. A pass supports separate admission for a held-world action-ranking fit
on copies. Full-run victory on fresh normal starts remains the strength test.
The collector records incomplete games and performs zero optimizer updates.

Both short controls regenerated their exact roots, delivered a different legal
choice, and reached genuine losses with clean resets. They verified the
collection path. The 24-probe preflight passed.
[Control evidence](evidence/native-a8-sampling-result-v1.json).

Close STS2 and allow about 6–12 minutes.

```bash
bash scripts/collect-a8-turn-rescues-v1.sh
```
