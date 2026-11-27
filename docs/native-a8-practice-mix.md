# Model-owned A8 practice mix

The [collection and continuation result](native-a8-practice-continuation.md)
records the original interruption and the completed matched practice
candidate.

The [matched combat-feedback result](native-a8-combat-feedback-result.md)
recorded one Act 1 clear and zero wins in 48 normal-start games. This
collection measures how much useful experience the original models can
produce from a wider range of starting states. Both models choose from
the full legal menu with the frozen game and current native confirmation
and ending checks.

## Collection design

The recipe declares 32 prepared worlds across Overgrowth, Underdocks,
Hive and Glory. Each definition has three worlds with the existing
healthy act-start profile, three with the lean profile, and two with the
pre-boss profile. Both original initializers play the identical saved
start for each world, producing 64 segments.

The act-start goal is two distinct living transitions from native
combat to its reward owner. The pre-boss goal is the native reward
transition after an observed boss fight. The game chooses the boss
for each fresh world. Native losses, caps, incomplete segments and
unattempted segments stay in the denominator. The report separates
early room coverage from later boss outcomes.

The runner takes the first seed in each declared pool that generates
the requested act definition. It uses the existing native preparation
method and the prior curriculum's training profiles. The prepared decks,
HP and resources are training setup. The model receives public input
from a live game, and the runner reconstructs each choice and receipt.
The prepared starts and control worlds are separate from the earlier
development games and reserved final-test worlds.

## Readiness and use

The first short check completed ten segments. Both policies lost the
single lean Glory start. One policy reached the native Hive boss rewards
and the other ended in a native loss. The complete check remains saved
as evidence. The balanced control uses both act-start resource tiers in
each definition and a separate Hive pre-boss start on fresh seeds.

The balanced control passed all 18 segments on nine worlds, with 13
practice goals and five native losses. Both policies reached the goal
from the healthy Glory start, and both lost the lean Glory start again.
The two Hive pre-boss segments ended in losses. The short check supports
collecting varied practice and records the harder outcomes separately.
The original states, Adam, game build and shared profile passed
verification. [Preparation evidence](evidence/native-a8-practice-mix-v1.json).

The original owner run used this command.

```bash
bash scripts/collect-a8-practice-mix-v1.sh
```

The command collects training-only experience and performs zero updates.
Clean sealed segments resume from their exact states. Uncertain deliveries
are preserved. A positive room or boss goal counts as practice evidence.
A subsequent fitting recipe can compare a mix of normal and prepared
experience with a normal-start control. Any fitted candidate still
needs separate fresh normal-start evaluation with full-run wins as
the primary outcome.
