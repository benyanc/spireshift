# Common public inputs and exact comparison worlds

The owner requested resolution of the remaining official-game/CLI input layouts,
targeted compatibility checks, and preservation of both complete players and all
optimizer state. The old experiments, negative results and original checkpoints
remain unchanged. No fitting or automatic training follows this work.

## Repairs

The new CLI exports v37/v38 publish the current event's actual model ID, displayed
name and ancient/ready-option flags. These are supplied by the current native
event, not inferred from a localization key or filled into historical captures.
The frozen game assembly is unchanged.

CLI v38 also supplies current card keywords in pile/hover views. Official connector
v14/v15 exports visible card preview numbers/keywords, selection upgrade previews,
afflictions, star-resource visibility and announced enemy attack numbers. Card
preview values belong to their current display view: a base pile preview and a
combat-modified hand preview are both retained, rather than merged or discarded.
Upgrade previews use a detached clone; no live card is upgraded by observation.
The actual engine still supplies costs, legality and rules. Connector v15 adds
the normal noncombat potion-HUD use/discard controls, exact slot/owner/target
checks and a settling boundary while a requested discard is queued. The frozen
game DLL stays unchanged. Native belt and persistent HUD views now identify the
same physical potion and player, avoiding a second invented copy. Eleven C#
permission tests and four binding regressions pass; current shipped potion
effects still require a targeted live check. Worker v13 explicitly
publishes ordinary hand/pile cards as unselected and retains currently discardable
potion slots. Required selection booleans in old missing captures are never guessed.

Card star costs have a declared text representation shared by both hosts: numeric
zero becomes `"0"`, while `"X"` remains different. HP, energy, stars and numeric
preview amounts stay numeric. The separate v4 layout/helper-v7 tuple preserves all earlier successful and
blocked tuples and their exact source snapshots. Duplicate raw potion facts
collapse only when every field already matches the same public inventory slot
and current belt; unknown or conflicting fields remain represented. Two fresh baseline builds and two fresh
repaired builds reproduce their complete binary/dependency pins. The first local
build attempt lacked the existing build tool's runtime roll-forward setting; its
failure is preserved separately from the successful reproductions.

The versioned shared input helper v7 maps both current public graphs through a
typed layout normalizer. It:

- Moves event text to its declared owner, normalizes operational ready labels,
  and treats a localization lookup key as provenance. Nonempty formatting
  variables and unfamiliar fields remain represented.
- Collapses duplicate single-player HUD/run/inventory facts only when their
  values and ownership agree. Explicit foreign owners remain separate; conflicting
  duplicated HP/gold/progress facts reject the decision. A shop interface can be
  owned by an ordinary shop or an event; differing underlying room types stay.
- Preserves current card costs, physical copies, upgrades, zones, scoped selection
  and legality, owned relic counters, named status amounts and unknown public facts.
  Only declared nullable card/tooltip fields receive explicit nulls. Required
  enablement/selection flags are never invented.
- Relabels local entity slots through a bijection and preserves every original
  action binding. Skip/leave, potion targets, repeated rest controls, card-selection
  bounds and other current choices remain available.
- Keeps a reversible rewrite journal outside the learner input. Reconstructing
  each original public graph must succeed exactly. This is graph preservation,
  not recovery of hidden engine state or proof of stronger play.

The inert zero block value in the CLI's noncombat PlayerSummary is not rendered
outside combat and is classified explicitly. A nonzero value stays represented.
First-act local/global floor aliases are verified; later-act local floors remain
explicit pending a visible-map ownership relation. Unknown facts are not dropped
to manufacture equality.

## A genuine setup mismatch

The saved `SCOPECTRL003` control started different bonus options because the official
game canonicalizes `O` to `0` and `I` to `1`, while the CLI used the literal string.
The exact frozen SeedHelper and connector HostRunSeedControl establish the rule.
Previous results retain their original seeds and scope; they are not relabelled.

New comparison recipes require already canonical ASCII seeds before any app
launch. The official client additionally checks the actual mounted seed through
the existing authenticated provenance route. That diagnostic response stays
outside model inputs. An alias of a previous world is excluded as well.

The new observer recognizes the pinned `visible_unsupported` status immediately,
waits through explicit settling, and accepts only complete fresh public snapshots
from the original runtime. A separate 45-second startup-loading window remains
inside the whole-case cap. Gameplay delivery and stale-read refresh retain their
15-second local window. Submitted/uncertain actions are never retried.

## Completed-record checks

The current saved bank has **823** immutable observations from the completed owner
panel and completed short controls. Every capture has an expected record count, preventing
a record-kind filter from silently skipping a host. There are also **20** generated
policy/terminal envelopes. All **843** convert, reconstruct exactly and preserve
their complete raw action bindings. Both frozen players pass **1,676** independent
input probes, with zero game launches or optimizer updates.

The targeted Node suites also cover typed star costs, distinct base/current
card previews, detached upgrade information, modifier/affliction fields and
capability-set ordering. They also cover equivalent complete layouts; contradictory and
foreign ownership; arbitrary runtime handles; two identical-definition cards with
different current costs; optional Skip; repeated rest choices; Foul Potion's exact
merchant target; later-act local floors; unfamiliar facts; native seed aliases;
actual-seed mismatches; unsupported/settling states; and separate startup/read
deadlines. These are contract/preservation tests, not new native-effects evidence.

The first development bank mistakenly selected only 332 observations because its
native record label did not match the captured envelope; it is preserved as a
scoped development result. The corrected full-bank sweep caught ten shop-room
enum assumptions before live use. Both the failed sweep and its source snapshot
remain preserved. The active bank checks counts and retains event-owned shop facts.

Both original complete weights and every Adam moment/counter remain exact,
including counters 5,658 and 6,045. The source/data preservation receipt covers
**3,018** pre-existing files. New environment metadata labels changed inputs;
unchanged numerical weights do not imply unchanged action probabilities.

## Qualification boundary

The broad comparison remains diagnostic until complete input/action/successor
compatibility is established. Historical missing event metadata is not synthesized;
later observations from divergent games are never realigned into matched pairs.
Full-game strength, promotion and adaptive thinking remain unqualified. More
whole games are not the primary mechanism for discovering schema bugs: use source
inventories, recorded frames, reversible mappings and targeted transition tests.

The first short live control stopped during asset loading before a policy input,
with natural shutdown and app/profile/archive reset verified. Its seed and evidence
remain preserved; the longer startup window uses a fresh world. The v3 short control delivered four choices per host with **identical complete
public inputs and action keys** at the bonus, Proceed, map and first combat
choice. All eight choices and actual receipts independently reconstruct from
saved records in **4.93 seconds**, without gameplay. All app/profile/archive
checks pass.

The next fresh world acquired potions and exposed the official connector's
missing noncombat belt controls. V15 implements their source repair and targeted
permission tests; that original blocked capture is retained. Another fresh world
then selected Precise Scissors: the compared card-definition/cost/ordinary-description/numeric-preview
multisets match, but full selection
contexts also differ in per-copy identity, missing source selected flags and
selection-specific ownership/layout. Upgrade-preview descriptions also retain
different line-break formatting. The CLI's `Confirm Strike` is an atomic committed choice while the
shipped game offers `Select Strike`, a preview and a separate confirmation. All
deliveries/shutdown checks pass; full prefix equivalence correctly remains blocked.
Neither the star-cost normalization nor hiding card fields can repair that
**decision-boundary difference**. Those source/layout repairs accompany the
selected common protocol; meaningful flags and ownership must not be discarded.

## Pending selection-contract choice

The owner is choosing whether a model decision means a complete committed card
choice, with the adapter performing the exact required native UI steps, or whether
the model learns each selection/preview/confirmation step itself. The recommended
semantic choice keeps UI confirmation out of the strategic decision space while
retaining every legal card subset/order and genuine cancel/decline option. It
requires a separately qualified executor with current-owner checks at every step,
verified cancellation and no uncertain action retry. The alternative requires
an explicitly versioned native UI cursor matching the shipped transitions.

A broader canary must remain blocked until that choice is implemented and its
targeted short transition checks pass. Do not run the historical canary wrappers
or continue learning to work around the mismatch. Both complete players/all Adam
and all attempted worlds remain preserved. No full-game strength or exhaustive
compatibility claim follows these tests.

Further targeted work uses source inventories, schema mutations and saved states
rather than bulk gameplay to discover interface omissions. Important unobserved
effects/protocol transitions still need specific fixtures, and complete
original/trained official-game evaluation remains required before promotion or
major scaling. Final check identities are recorded in the current evidence.

## Final saved checks

Repository checks pass **2,562 tests**, strict types on **599 files**, format/lint
and the C# protocol, in **150.17 seconds**. Targeted Node suites cover **163**
contracts/preservation cases; the local official-connector suite passes **11**
potion permission cases. The latest independent verifier reconstructs all **eight**
actual choices/receipts in **5.37 seconds**, correctly retaining the input-parity
failure. The current helper also preserves all four input/action equalities in
the earlier completed matched control, using saved records and zero new games.
All **3,018** protected earlier files remain byte-exact.

[Portable evidence](evidence/native-input-layout-v1.json) records source/build,
report, objective, preservation and resource identities plus the remaining gaps.
The atomic/UI selection mismatch is a blocker, rather than a compatibility pass.
