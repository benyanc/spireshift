# ADR 0006: Recurring checkpoint compatibility with the shipped game

Accepted 2026-10-23 following the owner's request to reconcile the engine discussion,
update the backlog and implement the automated compatibility gate. This extends
ADR 0005. It changes neither terminal-victory optimization, the whole-run compute
constraint, fixed Ironclad/A8 nor the readiness requirement before adaptive thinking.

## Decision

Use the separately frozen official v0.111.0 app as the reference and retain the
fast patched CLI as a candidate training host. The community headless/CLI bridges
are interfaces, not official Mega Crit distributions. Common game-assembly bytes
and successful narrow mechanics comparisons do not prove interchangeable inputs
or full policy execution. Do not mix historical EvanGambit experience into the
current native lineage or migrate to official-only training on an unmeasured claim.

Bind recurring evidence to the exact game, runtime, host/patches, connector, worker,
public projection/encoder, suite and complete checkpoint/Adam identity. Require
environment verification on batch start/resume, recorded policy-input regressions
on checkpoint changes, and actual checkpoint delivery canaries for the current
execution tuple and declared learning milestones. Final promotion/scaling also
needs a fresh paired original/trained official-game evaluation. A compatibility
pass is not proof of a competent player or a controller-readiness pass.

Compare matched gameplay decisions and successors. Allow documented transport-ID
and presentation-step normalization; preserve costs, owners, card zones, meaningful
descriptions, complete public reads and every genuine action including Skip and
repeatable options. Never infer an unrecorded read, silently filter a legal action,
retry uncertain delivery or use held-out official outcomes to fit/select players.
Count normal losses separately from execution incompatibility. Fix drift in a new
versioned lineage and mark affected old evidence without erasing it.

## Implementation boundary

The first gate reconstructs four historical paired sequences and evaluates six
frozen checkpoints on 36 public observations without gameplay or fitting. It finds
a v34/v35 environment-label mismatch, differing historical input schemas/menus and
incomplete retained reads. It blocks qualification, preserving every saved player,
optimizer and frozen experiment. It cannot issue a live-delivery receipt. New
guarded commands stop before their child process until all required scopes pass;
old immutable entry points are not retroactively rewritten.

Next qualify the common public contract/current-format official policy adapter,
explicitly align the environment label, then collect bounded live canaries. Keep
this finite and representative; do not make exhaustive content combinations a
prerequisite to useful learning. Continue to share the app/runtime/SDK, isolate
profiles, retain immutable reports and leave jobs expected to take five minutes
or more to the owner. No training or live collection follows a saved audit.

See [implementation/result](../native-compatibility-gate.md) and
[portable evidence](../evidence/native-compatibility-gate-v1.json).
