# A8 turn rescue result

All 24 alternatives ended in verified Act 1 losses. Eight ordinary,
eight elite and eight boss probes resolved. None reached the tested
room's rewards. There were no caps, failures or unattempted cases.
With zero rescued worlds for either initializer, the fitting gate failed.

The saved audit reconstructed the complete legal menus, model draws,
4,078 replayed setup deliveries, 209 alternative and continuation
deliveries, and all 24 native endings and clean resets. It checked
1,464 sealed files. The frozen game, runtime, localization, SDK,
shared profile, original weights and full Adam passed verification.
There were zero optimizer updates.
[Evidence](evidence/native-a8-turn-rescue-result-v1.json).

Eleven of the 12 menus started below half health, with starting HP
between 1 and 40. On eight menus the two draws selected the same first
alternative. The next collection starts earlier and guarantees
distinct first probes.

## Check existing positive and negative outcomes

A saved-data screen covered 248 training traces on 50 distinct worlds
from the action-credit, world-credit, coverage, sampling and turn-rescue
studies. It matched each pair's seed, recorded prefix and complete public
menu at the first differing choice. Requiring visibly different choices
and opposite native outcomes in the same room yielded five menus on
two worlds. Both were elite fights. Multiple menus from one world count
as one source of experience. Two worlds are too few for a fit that can
be checked on independent worlds. [Source audits](evidence/native-a8-turn-rescue-result-v1.json).

## Collect earlier matched combat outcomes

The [recipe](../configs/native-learning/sts2-v0.111.0-a8-opening-contrast-v1.json)
uses 16 distinct worlds from the verified normal-start training bank,
balanced across both initializers, ordinary and elite fights, and
reference room rewards and losses. Two additional worlds supply short
controls. The new menus exclude prior sampling and rescue roots and
the two worlds identified in the saved screen.

Each root is the first offered combat menu of round one, with the
player at half health or higher and at least three distinct visible
choices. The frozen model regenerates its exact prefix. The first
probe samples a different legal choice from the model's scores. The
second excludes the saved choice and the first probe's visible
choice. After the probe the model owns every choice from the complete
legal menus. All outcomes require a native loss or a living arrival
at the same room's reward screen.

The gate requires 32 resolved probes, an opposite outcome on at least
three distinct worlds per initializer, both encounter types, and
contrasts from both positive and negative references. A pass supports
a separately admitted sequence-ranking test on copies and held worlds.
The probes and regenerated prefixes are excluded from ordinary PPO.
Genuine full-run A8 wins on fresh normal starts remain the strength test.
The collection performs zero optimizer updates.

All four short probes reached native rewards in their tested room
and later completed as genuine losses. Each control replayed its exact
menu, delivered two distinct first alternatives across its pair, and
verified the native endings and clean resets. The 32-probe preflight
passed. [Control evidence](evidence/native-a8-turn-rescue-result-v1.json).

Close STS2 and allow about 8–15 minutes.

```bash
bash scripts/collect-a8-opening-contrasts-v1.sh
```
