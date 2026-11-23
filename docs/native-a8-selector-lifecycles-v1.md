# Shop and reward selector lifecycle checks

The [subsequent official comparison](native-a8-official-selectors-result-v1.md)
supersedes the complete-menu claims for Kifuda below: the frozen official screen
cannot confirm zero cards. The historical native effects remain recorded, while
the corrected adapter publishes a minimum of one. Six revised official/native
controls now pass. These historical native checks alone grant no official parity.

The six native checks passed on frozen STS2 v0.111.0 / 41cef1ea with
host v60, public converter v17 and the verified card cleanup adapter.
They use the shared lifecycle contract to check complete menus, public reads,
exact action receipts and fresh successors. The frozen game, runtime, SDK,
localization, checkpoints and complete Adam states verified before and after.
The panel made zero optimizer updates.

| Fixture | Verified behavior |
| --- | --- |
| Removal with thirteen physical cards | Use Blood Potion and discard Foul Potion while selecting, cancel without spending gold or consuming the service, reopen, then remove exactly one selected copy for 100 gold |
| Three-card Kifuda | Discard and heal during the child, confirm two ordered cards, charge once and apply Adroit 3 to those physical copies |
| Thirteen-card Kifuda | Preserve all ordered choices, construct two local answer steps, then make one native answer commit and return to the shop |
| Empty Kifuda answer | The native zero-card answer consumes the purchased relic offer with the full deck preserved |
| Card reward taken | Finish a native combat, heal and discard during the reward child, add the selected card once, preserve the gold offer and collect its exact amount |
| Card reward skipped | Preserve the deck and the skipped offer under its native parent, collect the sibling gold and leave through a legal map vote |

The panel verified 46 native deliveries and two local answer factors in
33 seconds. Card copies retain distinct physical identities even when names
match. The menu assertions independently enumerate direct answers and the
legal next steps of larger ordered answers. Catalog purchases remain disabled
while a selector owns input. After belt space is freed and the shop returns,
its potion purchases become available again with their original stock and prices.

The map vote owns departure from the reward room. Reward tests follow it into
the next playable combat and require the prior reward task and selectors to
have settled. Snapshot-specific player and offer identifiers are rebound on
each observation. Separate native references establish that potion actions
preserve the actual pending child and offered cards.

These are private diagnostic fixtures. Native combat produces the reward
set. A separately declared shop save funds the test and places Kifuda in
its existing shop-tier bag. All effects and choices use the native action
path, and every case retains its evidence with file hashes.

The source-derived inventory keeps the broader combined branches open,
including official large selectors, other child owners and later-act
transitions. The interrupted official rest-test failure remains recorded. Its
separately inspected pre-controller reset restored the test copy without replay.

The completed report is
`artifacts/native-selector-lifecycles/v1/full-1795401726303382000/report.json`,
with ID
`sha256:5633f608082f85be4819dec9f90d8fa50ef72a501169eb1533ebf8e0349874a0`.

Run the complete native panel manually with the command below. It allows
four minutes and writes each attempt under the workspace in the recipe.

```bash
bash scripts/check-selector-lifecycles-v1.sh full
```
