# Reward-belt repair and curriculum continuation

The first #152 collection stopped during `fit-007/reference`, after six completed
cases. This is an observation-adapter failure, not a resource cap or optimizer
failure. The saved audit verifies 35 sealed units, 29 complete gameplay episodes
and 1,148 actual deliveries. Five confirmed lessons and three complete-reference-
failure-to-teacher-success rescues remain available. The main bank is incomplete;
there have been zero main optimizer updates.

## Cause and repair

At floor 5, the reference claims Beetle Juice while another potion reward remains.
The belt becomes full. The legacy reward projection registers the owned potions
for its full-belt discard controls; the global belt extension registers the same
instances again. The old adapter suppresses duplicate discard actions but leaves
the duplicate referents. The unchanged strict SDK correctly rejects the successor
with `referent ids must be unique`.

`engine-reward-belt-surface-v1.mjs` projects this specific full-belt reward case
with one registration per native owned potion. It retains disabled potion claims,
other available rewards, actual discard/use permissions and native slot/copy/target
operands, plus current Skip/Proceed ownership. Other surfaces delegate to the
unchanged qualified projection. The strict decoder and converter16 stay enabled.
An exact saved-response regression reproduces the old failure and passes on the
repair; no failing-world command is executed by that regression.

The game v0.111.0 / 41cef1ea, CLI56, Connector31, ordinary worker24, converter16,
layout12 and environment48 remain frozen. Original/fitted full weights and Adam,
the earlier compatibility studies and their markers remain unchanged. Only the
separately versioned curriculum wrapper uses the repaired projection, through
both native mount and loaded-start paths. No official qualification is inherited.

## Explicit recovery, without replay

The original `study-v1`, its config/source snapshot, all 36 completed units
(including the interrupted world's setup), unfinished unit, raw files and active
markers remain preserved. The failed worker's termination is verified. Its first
26 acknowledged deliveries reconstruct as diagnostic evidence; the next native
action was sent without a valid decoded successor/receipt. That incomplete prefix
provides no labels, and its world/profile is not retried.

The new v2 recipe imports only the 35 verified units belonging to the six fully
completed cases. Imports check the exact original request, seal and files and
write compact linked receipts; they never launch games. The failed `fit-007`
case stays in the report, while `fit-007-replacement-1` uses a fresh, disjoint seed
pool. The 61 original unattempted cases remain unchanged. Development/final-test
ownership, teacher logic, objectives, operational caps and quality thresholds
stay unchanged.

The linked denominator is **69 case slots**: six completed original cases, one
historical failed case, 61 unattempted original cases and one fresh replacement.
The executable current recipe contains 68 cases including the six imports. A
complete bank still needs all declared act/boss/decision-family successes, strict
rescues and independent development successes. Earlier losses remain losses;
neither the failed prefix nor branch counts inflate useful experience.

The old collection command remains blocked by its unfinished marker. Use the
new continuation command from any directory after closing STS2:

```bash
bash "/Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/continue-win-curriculum-v2.sh"
```

Allow roughly 45–90 minutes per invocation under the same 90-minute session cap.
Clean new seals resume with this command; uncertain new attempts remain preserved
without retry. The continuation collects and audits only, then stops at its quality
report. It performs zero optimizer updates and starts no automatic learning,
promotion, full-game evaluation or follow-up experiment. The v2 main workspace is
unstarted by this repair.

## Checks and remaining scope

The saved recovery audit starts zero games and reconstructs every completed
original delivery/confirmation. The exact failed raw response passes the repaired
strict SDK and shared public-input projection. Four reward-belt regressions cover
owned identity, locked discards, native targets, mixed rewards and terminal
proceed; recovery regressions cover exact imports, no game replay, fresh ownership,
failure denominators and stale guards. Fresh short checks exercise two normal
starts and two loaded starts, delivering eight acknowledged actions. The earlier
copied learn/reload/held-world control remains valid for its unchanged numerical
and teacher source; this repair adds no fitting updates.

All 2,816 repository tests, lint/format/strict types, C# build/contracts and commit
hooks pass. The zero-game continuation preflight verifies every one of the 35
actual original import requests and confirms that the new main workspace is
unstarted. The initial type-check annotation failures and provisional repair
control remain preserved with exact source snapshots; the final receipt binds
the corrected implementation and separate fresh short-check worlds.

The separately documented Architect completion failure is still unresolved.
Prepared final-boss success stops at native completed-boss reward ownership after
actual combat. It remains distinct from a normal-start terminal victory. No A8
playing-strength or official-game victory claim is made here.

See [versioned evidence](evidence/native-win-curriculum-recovery-v1.json), the
[original preparation](native-win-curriculum.md) and [ADR 0008](decisions/0008-native-win-curriculum-admission.md).
