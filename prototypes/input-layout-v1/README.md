# Offline public-input layout prototype

This standalone prototype uses completed, sealed public policy records. Production
does not import this directory. It has no game launcher, checkpoint loader,
optimizer or action-delivery endpoint. The active interface diagnostic and all
of its pinned sources, recipes and player files stay unchanged.

## Conversion rules

`converter.mjs` accepts a completed shared public entity graph and returns a
separately versioned `offline-public-entity-graph-layout-v1` input, a reversible
rewrite journal and unresolved-fact witnesses. The production learner's existing
input validator rejects this prototype schema. Integration needs an explicit
new contract/environment and its own qualification.

The initial, deliberately narrow rules are:

- Canonicalize omitted nullable fields **only at registered VisibleCard and
  VisibleEventOptionTooltip paths**. The pinned SDK declares those nullable types
  and its connector omits null properties during serialization. Missing required
  booleans, including enablement and selection state, remain missing. Unknown
  card-shaped objects do not inherit the SDK schema.
- Collapse exact duplicate current-player/current-run scalar facts using explicit
  aliases from the pinned native projection. A conflicting fact or foreign owner
  remains represented and gets an unresolved witness. Extra inventory, counters,
  local run facts and other unfamiliar fields remain represented. In particular,
  native `total_floor` maps to persistent `floor`; act-local `floor` does not.
- Relabel local entity numbers with a bijection based on retained visible
  occurrences. Every declaration, pointer, action operand and owned copy keeps
  its relationship. Array order and multiplicity remain intact. Card definition
  IDs never serve as per-copy identity. Action referents and embedded entities
  may have different owners and stay distinct.

Every rewritten graph must reconstruct to the original public graph exactly,
including its original numeric labels, optional-field presence and unknown
properties. Capture bytes themselves are separately hash-checked. The journal
is reconstruction evidence; it is outside `canonical_input`.

The prototype never prunes a legal choice, including Skip, leave, potion use,
rest, smithing or repeated controls. It neither fills unavailable game facts nor
guesses whether two prices, previews or base/current card statistics mean the
same thing.

## Completed-record check

The current local receipt is
`artifacts/native-input-layout/offline-v1/results-v4/report.json` and its pinned
recipe is `artifacts/native-input-layout/offline-v1/plan-v4.json`.

The bank contains **495 recorded policy inputs**: eight from the repaired v36
short control and 487 from the historical v35 canary, reported as separate
cohorts. All 495 reconstruct exactly and preserve their legal choice sequences.
An additional **88 synthetic perturbations of saved inputs** retain deck
definitions, per-copy costs/upgrades and relic definitions as distinguishable
inputs. They measure representation sensitivity, not legal engine transitions,
action correctness or improved play. Numeric persistent-relic counter probes
are not available in these captures; the artificial preservation cases exercise
owned counters and named status amounts separately.

Only the first, pre-choice observations within each declared world/player pair
are compared across hosts. Later, divergent observations are checked independently
for preservation. No later frame is realigned into purported matched-state
evidence. All five initial pairs still differ; complete compatibility stays
blocked. The repaired initial pair's arbitrary entity-label differences disappear,
but event metadata, partial player/run views, option fields and extra referents
still require specific semantic/source evidence. These are retained in
`initial_comparisons[].remaining_paths`, not deleted to force equality.

The study streams compressed records, checks their completed reports and original
record counts, pins implementation and source declarations, and checks a separate
**1,638-file preservation receipt before and after**. This includes the running
diagnostic's 145 pinned source files and both complete original player/Adam files.
Outputs use a separate directory and never overwrite a prior study. Source
snapshots and earlier development receipts are retained. A finished study has
both its launch receipt (`active.json`) and `completed.json`; a launch receipt
alone records an incomplete attempt and must not be cleared automatically.

Limits are 512 policy inputs, 90 seconds of study work, 50 MB uncompressed output
and a 256 MB Node heap. The final saved pass takes 2.3 seconds. Zero games,
optimizer updates, app copies, model imports or promotions occur.

## Tests and follow-up

The isolated suites cover 36 cases: equivalent alternate layouts, exact
reconstruction, idempotence, arbitrary handle relabelling, individual card copies,
current costs, upgrades, zones, targets, owned counters, Strength versus Dexterity,
optional choices, unknown fields, typed nulls, foreign owners, conflicts, hidden
fields, corruption, compressed-line bounds and refusal to overwrite outputs.
The original shared-input/interface suites add 17 regression cases.

The current scoped receipt is
`artifacts/native-input-layout/offline-v1/verification-v3/report.json`.
`evidence.json` carries the portable summary without raw game records.

The scoped test invocation is:

```bash
node --max-old-space-size=256 --test \
  prototypes/input-layout-v1/converter.test.mjs \
  prototypes/input-layout-v1/study.test.mjs \
  scripts/engine-interface-contract-v1.test.mjs \
  scripts/engine-shared-input-v1.test.mjs
```

After the owner diagnostic finishes, use its completed gap report to extend the
explicit mapping table and targeted preservation tests. Distinguish extra layout
from unavailable facts and base-versus-current semantics. Then freeze a new live
adapter/environment, run the repository checks and qualify matched inputs/actions
and effects. Keep numeric weights and full Adam intact during any explicit import;
changed inputs can still change behavior. No automatic live integration, new
training, checkpoint selection or adaptive controller follows this prototype.

The global repository check is deferred while the diagnostic runs; these are
targeted offline checks, not a repository-wide release receipt.
