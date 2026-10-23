# Completed teaching diagnosis

This is a separate saved-record report prepared while the owner runs the controlled
teaching test. It does not monitor or resume that experiment, open its live workspace,
change its pinned implementation/recipe, launch a game or fit any model. Both original
players, every saved checkpoint and all Adam moments/counters remain read-only.

## What it explains

The report connects four questions without treating them as interchangeable:

1. **Did the copies learn the actions?** Display the existing per-epoch full-plan
   losses. Recompute legal-action probabilities, greedy matches and margins on the
   exact public lesson inputs for both originals and both trained versions. Show
   the three changed-choice targets separately from averages over the whole plan.
   The two fitting worlds receive equal weight; nominal target-position weight is
   reported without claiming that it equals actual gradient influence.
2. **Can they execute the lessons?** Read completed natural-fight traces. Recompute
   their saved greedy distributions under the exact frozen player. Compare only
   the exact common public-state/action prefix with the historical reference and,
   on fitting roots, the taught plan. Report the first departure, observed fight
   outcome and whether each changed target's exact public state was ever reached.
   A departure is not automatically a mistake. After an action changes the future
   state, the report does not compare later actions just because their positions
   in the two traces happen to match. An unreached target is missing, not wrong.
3. **Did unrelated choices change?** Run read-only inference on at most 128 public
   menus from sixteen predeclared, completed historical TRAIN games. Report
   distribution movement, changed greedy choices and offered card-skip, rest,
   potion and shop probability changes. These establish behavioral movement, not
   whether a different choice is better or worse.
4. **Does it transfer to full games?** Reproduce the completed source's original
   denominators and paired comparisons, retaining failed games as declared. Keep
   the untouched original and reference-clone controls. Full-run victory under
   the unchanged 128-CPU-second budget stays primary; floor/HP remain auxiliary.

The tool selects no epoch, checkpoint, training setting or automatic follow-up.
It does not generate imitation labels or a readiness/controller admission.

## Completed-source and public-input boundaries

The default source is the **completed short integration control**, not the active
main experiment. Its exact recipe/report identities are pinned. A separately
declared main-report recipe is prepared for later use, but is not executed while
the experiment is running. It requires `native_teaching_complete` in the final
report before any source chunks are opened; there is no session-file fallback,
partial-result analysis, automatic source discovery or polling.

Every expected work-unit request, warm-state predecessor and frozen-final barrier
must reconstruct from sealed receipts. Original full model/Adam imports are checked
against both numerical parents, with the declared observation-metadata migration
only. The critic, source implementation, original players and all source bytes
are verified unchanged. Source locks and native worker locks are never acquired.
Cached diagnostics verify their source and summary seals without new analysis.

The historical probe uses only `train-p2-batch128-r01-c00` and `c01` from the
completed experience-budget comparison: sixteen distinct first-round TRAIN worlds.
These worlds exclude every teacher root and both declared control/main fresh panels.
All sixteen planned games must be clean, complete, unprivileged own-policy sources
with sealed delivery/probability audits. Headers, compressed traces, model/environment,
training-score and native-seed bindings verify. Forced shop navigation is reconstructed
and excluded; effective current menus retain their actual optional actions.

Public-only deterministic ranking chooses at most two states per world/family,
deduplicates identical public inputs and balances decision families within the
128-state cap. The sampler never uses the chosen historical action, probability or
final outcome as a selection score. Detailed source counts and any missing families
remain visible. This is a deliberately balanced probe, not the natural gameplay
distribution or proof of exhaustive mechanics coverage. Each represented world
has equal weight within a family/opportunity; decisions are not independent games.

Teacher histories remain explicitly fixed-world privileged evidence. Only their
validated public inputs enter inference; hidden ending/debug fields do not. Held-out
fight traces can be described only after the entire selected source completes;
they never supply fitting labels or settings. Only fitting plans are taught-action
comparators. The source reference is not an optimal-action oracle.

## Execution and storage

The report runs with one numerical thread and **four-minute wall/CPU, 1-GB-memory,
100-MB-output** limits. The output path comes from its own pinned recipe. It retains
at most one raw historical episode at a time, references the original game evidence,
and stores compact metrics plus `summary.md` / `report.json`. It creates no app copies
or new trajectories. Existing or changed output is preserved rather than overwritten.

`bash scripts/diagnose-native-teaching-v1.sh` selects the completed control only.
After the owner's main test finishes, the same wrapper with `--main` explicitly
selects that completed result. This is saved-only analysis, not another owner-run
training stage; Codex can run it if the expected runtime remains under five minutes.
No main diagnostic command is required while the experiment runs.

The implementation adds tests for refusal of active/partial sources, exact receipt
ownership and denominators, changed checkpoint detection, read-only source access,
first-departure alignment, unreached/repeated targets, family/world-balanced sampling,
outcome-independent selection, model/Adam nonmutation, public-only inference,
path aliases, finite deadlines and verified cached reuse.

## Short saved-record qualification

The completed control diagnosis finishes in **90.74 seconds**, with **278.38 MB
peak RAM / 23.59 MB output**. It verifies **106,365 sources / 16 work receipts**,
reconstructs **79 saved fight distributions**, and checks exact original imports,
fixed critics, complete Adam states and frozen main inputs unchanged. It launches
zero games, makes zero optimizer/baseline updates and opens no live main workspace.

Historical extraction accounts for **16 games / 1,981 raw decisions**: 1,515 genuine
choices, 462 single-choice menus and four forced navigation controls. The bounded
probe contains **128 states / 14 observed families / 69 deck signatures / 24 relic
states**. Every observed source family is represented; that is not exhaustive
mechanics coverage. No raw trajectory is copied into the output.

All four one-epoch control copies reduce full-plan imitation loss. On the rescued
world 148, player 2's taught Body Slam probability increases from **25.2% to 28.1%**,
but Defend remains the greedy choice. All three saved control fight traces first
depart from the taught plan at action six, choose Defend and eventually lose.
On the other fitting world's saved states, another changed target becomes the
top choice for player 2; that fight was not part of the short control's native
execution checks. This demonstrates why fitting probabilities and execution
must be assessed separately. It does not predict the main 16-epoch result.

The historical probe also detects small noncombat probability changes from
combat teaching. The improved-plan copies' noncombat top choices remain unchanged
in these selected control menus; the reference copy changes one reward choice.
Such movement is not evidence of damage. The report retains all detailed
per-family/opportunity measurements rather than changing training restrictions.

Readable output:
`artifacts/native-teaching-diagnostics/sts2-v0.111.0-a8-control-v1/summary.md`.
The default command only reuses/verifies this completed diagnostic. No main
diagnostic or further owner job is required while the experiment runs.

Full repository verification passes **2,497 tests / five skips**, strict types
on **549 files**, formatting/lint and the C# protocol build in **165.13 seconds**.
The twelve new tests include the completed-only/source ownership boundary and
read-only diagnostics. See [portable evidence](evidence/native-teaching-diagnostics-v1.json).

A second **53.70-second** invocation verifies/reuses the identical report and summary
without repeating inference, extraction or analysis. It confirms all source seals
again after repository checks; no main workspace is opened, no output is changed,
and no additional games or optimizer steps occur. Its storage measurement is the
same existing 23.59 MB, not another copy of that output.
