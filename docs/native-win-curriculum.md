# Win-focused A8 curriculum preparation

Issue [#152](https://github.com/benyanc/spireshift/issues/152) implements the next
step toward a base player that consistently wins A8, followed by A10. This
stage prepares useful training evidence; it does not claim improved full-game
play. [ADR 0008](decisions/0008-native-win-curriculum-admission.md) defines its
separate native-development admission.

## Frozen inputs and scope

The game remains v0.111.0 / 41cef1ea, CLI56 / Connector31 / ordinary worker24 /
converter16 / layout12 / environment48. Both original full checkpoints and
all Adam moments/counters remain unchanged at 5,658 and 6,045. The four earlier
epoch-16 finals and all historical reports also remain fixed. The old canary
panel remains three passes, one incomplete and two unattempted, with VTV204
preserved and its command blocked.

The new files implement a separate wrapper and recipe; they do not patch the
game assembly, original CLI, Connector or old pinned Python/JavaScript modules.
Admission checks exact sources/runtime, prior assessed public/action/reset
evidence, current native model identities, original states and new short-control
receipts. Ordinary PPO, promotion, new official qualification and automatic
follow-up remain disabled.

## Declared experience

The recipe is
`configs/native-curriculum/sts2-v0.111.0-a8-win-curriculum-v1.json`.
It declares 56 fitting and 12 independent development cases, with separate
unlaunched final-test seeds. Seed pools for native act discovery, controls and
every partition are disjoint. Act discovery selects the first declared seed
with the required native act, without looking at teacher outcomes. Unavailable
cases remain in the report.

| Coverage | Declared situations |
| --- | --- |
| Early game | Overgrowth and Underdocks, native act entries and every boss |
| Middle game | Hive entry, strategic rooms and all three bosses |
| Late game | Glory entry, pre-boss rest and Queen, Test Subject and Aeonglass |
| Deck/resource variation | Strength, retained-block and exhaust decks; native obtainable cards/relics/potions, declared upgrades and HP/gold variants |
| Whole-game decisions | Combat, paths, rewards, shops, rest, events, treasure and potion use; eight additional normal-start fitting worlds |

Constructed starts are **training only**. The engine generates the actual map;
the wrapper selects a connected native route and loads its room using native
save/load. The current-act route history is synthetic setup. Deck/relic/potion
effects use native model hooks, including actual energy-relic drawbacks. No
enemy HP, combat energy or RNG is edited. A successful earlier-act continuation
must finish that act alive; a final-act success requires an observed boss-combat
prefix followed by the engine's `completed_boss_combat` reward owner. Every
prepared success remains separate from natural full-run wins.

The short checks reached a previously untested winning path: the frozen headless
Architect completion fails before recording terminal victory. Prepared final-boss
goals stop at the verified post-boss reward boundary. Normal-start terminal-win
rules stay unchanged; this known gap must be repaired/qualified under #149/#146
before claiming genuine native full-run victory. The build remains frozen, and
the failure and its earlier provisional state-history failures are preserved.

## Teacher and bank quality

Each main case runs the original reference and three fixed public-state
teachers: balanced, defensive and scaling. The method uses current legal menus,
visible target HP, native card numbers, incoming damage, powers, deck/resources
and public navigation history. It handles retained block and card ordering;
it is a bounded heuristic candidate search, not an optimal solver. The same
prospectively fixed selection method is applied to development probes.

Select only a complete successful teacher continuation, then independently
confirm its entire ordered public/action sequence on a fresh native worker.
All raw deliveries and public projections must reconstruct. A strict improvement
is a complete reference failure changed into a complete goal success; tiny HP
gains in an already-won fight do not meet that requirement. A capped reference
is not counted as a demonstrated rescue. Caps, losses, unavailable starts and
uncertain attempts remain visible. Incomplete or uncertain units are never
retried automatically.

The admitted bank must contain successful experience for all four act
definitions and all twelve bosses, including all three final bosses. It also
requires meaningful choices in combat, map, reward, card reward, shop, rest and
event families; four independent strict goal rescues including one final-boss
rescue; and at least three independent successful development probes. Actual
coverage is measured from verified continuations, not promised by the case list.
Failure to meet any requirement produces `curriculum_quality_blocked`.

Only confirmed fitting-world paths supply labels. Forced shop navigation and
single-option menus do not inflate meaningful label counts. Branches on the
same world are not independent experience. Development labels never enter the
bank or copied fitting; final-test seeds are not launched. Setup saves, native
RNG, future outcomes and private metadata are rejected at the student boundary.
Teacher-selected demonstrations are excluded from ordinary on-policy PPO.

## Verification and handoff

The short controls cover all native boss starts, later-act rest/shop entry,
raw action reconstruction and clean shutdown. A separate real-data control
collects fitting and unseen-world successful continuations, fits two disposable
copies for sixteen updates each, checks full warm-Adam reload and the exact
next update, then delivers four actions from each reloaded copy. The unseen-world
loss check uses no held-out fitting labels. These are diagnostics, not a measured
win rate. Failed provisional controls are retained with exact source snapshots
and fresh-world replacements; they grant no admission.

Exact check counts, receipt identities and original/build checks are recorded
in `docs/evidence/native-win-curriculum-v1.json`.

The final exact-source control verifies 621 actual gameplay deliveries: 28 start
checks, 358 fitting-world teacher choices, 227 independent-world teacher choices
and eight reloaded-student choices. Two successful fitting worlds supply 57
meaningful labels; three unseen worlds supply 58 separate probe labels. Both
copies improve their held-world imitation loss (1.9641 to 1.1332 and 1.9904 to
1.0492) after sixteen updates each. The two extra next-update reconstructions
are counted separately. These figures establish bounded transfer, not stronger
full-game play. All 2,804 repository tests, formatting, strict types, C# checks,
six native-save regressions, commit hooks and zero-game launch preflight pass.

Close STS2 and run the single owner command from any directory:

```bash
bash "/Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/prepare-win-curriculum-v1.sh"
```

Allow roughly 45–90 minutes per invocation. One serial native worker runs under
a 90-minute / 4-GB memory and output cap; each continuation retains 128 gameplay
CPU seconds, a 90-second wall limit, 2,048 choices and a thirty-round fight guard.
These limits bound execution, not algorithm-comparison objectives. At a clean
boundary the command can pause and resume its exact seals with the same command;
an unfinished unit stops for inspection without replay. Logs, raw compressed
receipts, saves and compact outcomes remain outside Git under
`artifacts/native-win-curriculum/study-v1`.

The command performs **zero main optimizer updates** and stops after collection
and the quality report. Assess that bank before preparing #134/#35 learning.
Then freeze a candidate for #146 normal-start evaluation on disjoint worlds.
Target official checks to changed mechanisms and promising milestones under
#149; claim official competence only after real official full-game validation.
