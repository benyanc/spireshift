# Shared Act 1 boss reward exit and continuation

The original ordinary-fight comparison sealed six matched Ironclad/A8
worlds. Both planners lost on all six. The ordinary-fight planner reached
Act 2 on world 7 after beating the Kin, claiming Bronze Scales and choosing
**Skip remaining rewards and continue**. The previous outcome check accepted
only the empty reward screen's **Continue from rewards** button. It stopped
after the game had already advanced.

## Shared outcome check

Both planners now use the same outcome check in the continuation. It
aligns the frozen worker's private decision journal with the indexed
public delivery. The recorded action must be a native `proceed` on the
current Act 1 boss reward room. Its bound successor must show a living
player at the Act 2 map. Pending and exhausted rewards use the same rule.
A card preview skip or a return to the map within Act 1 cannot satisfy it.
Private evidence stays in the outcome check. The planners still use their
existing public inputs and choose their own actions.

## Saved world 7 and short checks

The recovery reconstructed all 533 saved native deliveries, including
the ordinary arm's final `proceed`. The tactical arm lost in Act 1 and
the ordinary arm reached Act 2 at **19 HP**. The first policy difference
was an ordinary-fight lethal intervention on the same legal menu.
The recovery has a separate record. The original worker was stopped
without a clean close, so world 7 stays outside the sealed pair and
confirmed rescue counts. Its original interruption and receipts are
preserved.

The same check verified earlier empty-reward exits against the Kin and
Vantom. The fresh smoke pair reconstructed 321 native deliveries with
two clean Act 1 losses. The first smoke attempt exposed an episode-number
field difference between live replies and saved records. Its evidence
was preserved and the corrected smoke used a distinct world. The frozen
v0.111.0 / 41cef1ea build, native runtime, SDK, localization, all four full
checkpoint and Adam states, and the shared save profile passed verification.
The checks performed zero optimizer updates. [Verification record](evidence/native-a8-act1-ordinary-lethal-continuation-v1.json).

## Remaining nine worlds

Close STS2, then run from this checkout.

```bash
bash scripts/continue-act1-ordinary-lethal-v1.sh
```

Allow about 4–8 minutes. The launcher checks the saved recovery and smoke
receipts before starting only `ordinary-008` through `ordinary-016`.
It keeps the original six sealed pairs, the saved-only result for world 7,
and the new pair results separately identified. A new ordinary-only
clear needs a clean matching confirmation to count as a confirmed rescue.
An unsealed new world stops without retry. This stage is a native Act 1
diagnostic with zero updates.
