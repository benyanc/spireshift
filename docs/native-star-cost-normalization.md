# Current card-cost types before view joining

The owner's selection-flows v9 command stopped after 14.65 seconds because two
public views of one Particle Wall used different types for its two-star cost.
The combat hand exported the number `2`; the card selector exported the text
`"2"`. Converter v13 joined those views before layout v10 converted the numeric
cost. Its conflict check therefore rejected the same cost. This is an input
representation bug within the adapter, not evidence of a different game rule.

The interrupted canary v6 contains 97 native observations and 96 acknowledged
choices. A saved-only review reconstructs all 96 original choices and reproduces
the rejection. Converter v14 accepts the rejected observation while preserving
the first 96 public inputs and choices exactly. No official game started. Preserve
both active markers, stopped-process evidence and the complete source snapshot;
this prefix is not a clean episode, qualification pass or learning data. Reserve
worlds 409/410 as historical and do not replay them to complete this comparison.

The repair normalizes only the declared VisibleCard star-cost field before
sorting reads or joining views of the same entity. Nonnegative safe integers
become decimal text. Zero, no star cost and `X` remain different. Different costs
still conflict. Unknown fields, current energy cost, ownership, target permissions,
hand order, separate physical copies and raw action bindings remain intact.
Unsupported typed costs stop explicitly; arbitrary dictionaries are not rewritten.

A separate reversible journal records each scalar conversion outside the model
input. The saved audit verifies both exact raw scalar restoration and the existing
pre-layout graph restoration, including inputs that previously failed at the join.
Both original full players and all Adam weights, moments and counters remain
unchanged. The source tuple is CLI v51 / official connector v20 / worker v21 /
converter v14 / layout v11 / shared environment v37. No game-rule, actor or critic
change is part of this repair.

The targeted native fixture offers three distinct Particle Wall copies through
Gambler's Brew, preserves their two-star costs and combat/pile context, then
confirms one choice and returns to combat. It finishes cleanly in 7.02 seconds.
This fixture is privileged source-delivery evidence, never a full run or PPO sample.
Preserve its earlier harness failure: the first check omitted the converter's
acknowledgement before reading the successor. That attempt is stopped and is not
retried. The corrected diagnostic uses a separate seed and workspace.

Seven new scalar regressions and fifteen existing selection-flow regressions pass
against the repaired converter. The expanded saved audit passes all 4,861 frames
and 20 artificial envelopes,
9,728 frozen-policy probes, and exact raw scalar and pre-layout reconstruction.
All three matched regressions pass full inputs and menus: 8 relic-preview,
8 generated-choice and 64 merchant decisions (47.55/49.79/119.96 seconds). Independent
verification reconstructs all 160 choices. App/profile/archive restoration passes,
with all 11,594 protected prior files unchanged.

The next command is `scripts/compare-selection-flows-v10.sh`, now preflighted
and unstarted:
four matched pairs on fresh worlds 411/412, both unchanged players, up to 128
choices per host, six minutes per pair and 30 minutes for the whole comparison.
Repository checks have a separate cached 10-minute allowance. One fixed app is
reused with isolated profiles. No fitting, promotion, controller or next experiment
follows automatically. Finite input checks do not prove all mechanics or playing
strength. See the current backlog and
[the evidence record](evidence/native-star-cost-normalization-v1.json).
