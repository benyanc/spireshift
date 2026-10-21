## Current handoff — fresh TRAIN complete-turn teacher implemented; owner collection next

**The bounded teacher now uses greedy combat continuation and fresh TRAIN worlds.**
Both exact round-60 weights, every Adam moment and counters **5,658 / 6,045** remain
unchanged. The long collection has not started. See the
[design and single owner command](native-greedy-complete-turn-teacher.md) and
[portable qualification evidence](evidence/native-greedy-complete-turn-teacher-v1.json).

Completed (#35 / #143 / #146):

- [x] Freeze **eight distinct new TRAIN worlds**, alternating four per player,
  excluding all 28 earlier native seed manifests and two separate control worlds.
  Capture at most one publicly eligible later combat root per source; seal it before
  later outcomes. Failed/no-root sources remain in the eight-world denominator and
  are never replaced. Preserve the inspected development comparison separately.
- [x] Generate one greedy reference turn and a sampled remainder for **every legal
  first move**, including end turn and current potion controls. Keep native nested
  choices/costs/targets; freeze exact plans before continuations. Deduplicate only
  identical traces in fixed order. No final-return, HP or winning-plan selection.
- [x] Replay frozen turns exactly, then use greedy combat, including owned nested
  selections, and matched temperature-0.8 noncombat decisions. Root/repeat/room/family
  draw slots isolate future choices from different combat lengths and proposals.
- [x] Bound proposal CPU at **64 seconds per root / 32 per attempt**. Charge every
  alternative all proposal episode CPU, without amortization, plus its own episode;
  the greedy-only reference pays no proposal overhead. Preserve the original
  whole-run victory / 128-CPU-second objective and bootstrap score. Stop/record
  exhausted budgets and incomplete turns; block failed roots, never retry uncertain
  delivery, retain original source counts and stop beyond two pilot failures.
- [x] Complete **16/16 native controls** in **90.79 seconds**, with zero failures,
  skipped branches, app copies or updates. Both exact repeats match. Verify **28
  shared noncombat draws / 12 identical-input choices** across four candidate/reference
  pairs. Four unique turns contain 13 steps; this short native sample has no nested
  turn steps. Nested behavior is covered by unit tests and preserved earlier native
  qualification, not newly observed in these four turns.
- [x] Saved audit reconstructs **all 1,792 decisions**, first-root sampling, complete
  plans/boundaries, draws/probabilities, CPU charges, repeats and lesson tables in
  **53.29 seconds**, without games or fitting. Journal hashes verify; native delivery
  is not independently semantically reaudited. These are correctness controls,
  not strength evidence or a readiness pass.
- [x] Host-disabled main preflight verifies **75,022 protected old files** and both
  full player/Adam seals, creates no main workspace, and fills only the two passed
  control/audit references in the template frozen before native controls. Runtime
  is **72.96 seconds**, with no games or updates.
- [x] Pass **2,110 tests (52 new; four skipped)**, strict types on 424 files,
  formatting/lint and the C# protocol in **122.76 seconds**. Source checks and both
  complete player files still match; the long teacher remains unstarted.

Next work, in order:

1. **Owner runs the finite eight-world teacher — NOT STARTED.** The upper bound is
   **944 native attempts** before menu/trace deduplication: eight sources, up to
   104 proposals and 832 comparisons. Use one worker, shared frozen inputs, zero app
   copies and 15-minute sessions; 2 GB memory / 4 GB cumulative output. Completed
   attempts resume; uncertain evidence remains preserved. No automatic next stage.
2. **Assess useful lessons before fitting.** Report wins first, then acts/floors/
   bootstrap returns, ties, reliable better/worse turns, CPU and whole-world coverage.
   Keep the eight-source denominator, fixed-world scope and original preference
   rule. Eight streams vary noncombat policy actions, not independent hidden worlds;
   they may be identical under greedy combat. Do not tune on inspected development
   worlds, loosen admission or silently add HP rewards.
3. **Prepare a bounded student test only if targets support it.** Fork both complete
   saved states, preserve every Adam moment, keep legal families learnable and test
   fresh full games against frozen parents. Privileged teacher branches are not
   ordinary PPO data. Base readiness still precedes promotion and adaptive thinking.

Single owner command, from any directory with STS2 closed:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/collect-native-greedy-turn-teacher-v1.sh
```

Codex runs only short controls, saved audits and checks. No long collection,
training, promotion, push or GitHub Actions has started.

### Preserved fresh combat comparison result handoff (commands below are historical)

## Current handoff — fresh combat comparison complete; improve teacher continuation next

**Greedy combat improves average progress for both fixed players, with no full wins.**
The owner completed all 256 fresh-game attempts. Both exact round-60 weights and
every Adam moment/counter **5,658 / 6,045** remain unchanged. See the
[completed assessment](native-combat-behavior-result.md) and
[portable result evidence](evidence/native-combat-behavior-result-v1.json).

Completed (#35 / #143 / #146):

- [x] Complete **64 fresh development worlds × two players × two arms = 256/256
  games**, with zero failures, unattempted games, app copies or optimizer updates.
  The sole change is combat sampling at temperature 0.8 versus exact argmax,
  including nested combat choices. Preserve all legal menus and noncombat behavior.
- [x] Measure **0/128 wins in both arms**, **0 → 2 act-clearing games**, mean floor
  **10.523 → 11.305**, best floor **17 → 27**, mean bootstrap return
  **0.023875 → 0.025864**. Mean game CPU is **2.470 → 2.561 seconds**, under the
  unchanged 128-second whole-run ceiling. This is behavior benefit, not a learned
  weight improvement, search benefit or readiness pass.
- [x] Rebuild the predeclared whole-world paired bootstrap: pooled floor gain
  **+0.781 [95%: +0.242, +1.344]**. Individual gains: player 2 **+0.734
  [−0.078, +1.625]**, player 3 **+0.828 [+0.234, +1.469]**. Resample 64 worlds
  jointly across both fixed players; zero observed wins do not prove equivalence.
- [x] Verify **5,403 shared noncombat draws / 1,392 identical-input choices** across
  128 paired player/seeds. Saved audit checks **256 receipts / 45,281 files**, all
  bindings/endings/returns/CPU, compact RNG receipts and tables in **42.46 seconds**.
  Both full player/Adam seals match. Collection audited every decision; this short
  outcome check does not repeat neural inference or semantic delivery auditing.
- [x] Record **39,343 decisions / 252 nested combat selections** and two collection
  sessions totaling **19.16 wall minutes / 927.23 CPU seconds**, 437.03 MB peak RAM
  and **421.91 MB final cumulative output**. Do not sum cumulative storage or use
  only the last session's time as the entire experiment.
- [x] Pass **2,058 tests (four skipped)**, strict types on 414 files, formatting/lint
  and the C# protocol in **123.75 seconds**. Tracked changes are documentation only;
  the private audit uses saved evidence and both complete player files still match.

Next work, in order:

1. **Prepare a bounded complete-turn teacher test with greedy combat continuation.**
   Use fresh TRAIN worlds and matched noncombat behavior. Compare alternative turns
   against the cheap greedy-only reference; charge any search separately. This
   result supports the continuation choice, not additional search or useful labels.
2. **Check teaching signal before another student update.** Count ties, reliable
   better/worse turns and independent-world coverage under the original rule. Keep
   fixed-hidden-world teacher data explicitly privileged and separate from ordinary
   PPO. Do not tune on these inspected development worlds, enlarge the old flat
   teacher, loosen admission or silently add HP rewards.
3. **Test supported targets in a bounded student comparison.** Fork both full
   weights and every Adam moment, keep all legal action families learnable and
   evaluate fresh complete games against the frozen parents at equal CPU ceilings.
   Greedy evaluation does not replace the actual sampled behavior required for
   ordinary PPO. Foundation readiness still precedes promotion and adaptive thinking.

**No owner command is needed for this completed comparison.** No new long task,
training, promotion, push or GitHub Actions follows this saved assessment.

### Preserved combat-behavior preparation handoff (commands below are historical)

## Current handoff — fresh greedy-versus-sampled combat comparison qualified; owner run next

**The requested combat-only comparison is implemented and qualified.** Both exact
round-60 players, full weights, every Adam moment and counters **5,658 / 6,045** remain
unchanged. The long comparison has not started. See
[design and single owner command](native-combat-behavior-comparison.md) and
[portable evidence](evidence/native-combat-behavior-comparison-v1.json).

Completed (#35 / #143 / #146):

- [x] Change only combat behavior: temperature-0.8 sampling versus the current
  policy's exact argmax, including combat-owned nested selections. Preserve every
  advertised strategic option and existing shop navigation. Use observed public
  ownership/exits; unknown owners fail instead of inventing actions. No search,
  privileged future plans, HP reward, model fitting or automatic promotion.
- [x] Match outside-combat policy, temperature and RNG by game seed, public room,
  family and visit. Combat choices do not advance noncombat streams; an extra reward
  cannot shift another floor's rest draw. Same public inputs/slots produce identical
  choices; differing HP/resources can legitimately change noncombat decisions.
- [x] Freeze **64 fresh development game seeds × two players × two arms = 256
  attempts**, excluding all 26 historical native seed manifests and two new control
  seeds. Counterbalance arm order without outcomes. Summarize both players and
  bootstrap paired complete-game seeds jointly across them; do not treat 128
  player/seed pairs as independent worlds or infer true win equality from zero wins.
- [x] Complete **12/12 native control games** with zero failures/app copies/updates:
  eight primary cells plus four matching exact repeats. Verify **207 shared
  noncombat draw slots / 50 identical-input choices**. Observe 13 nested combat
  selections plus noncombat selections, generated cards, rests, shops and rewards.
  Scoped correctness coverage, not playing-strength evidence.
- [x] Reconstruct **all 2,053 saved decisions**, ownership, draws/probabilities,
  endings, scores, repeat traces and paired tables in **36.51 seconds**. Native
  control takes **76.00 seconds**, 56.05 CPU seconds, 398.02 MB peak memory and
  35.80 MB retained. Collection audits delivery; saved recheck verifies journal bytes.
- [x] Pass **2,058 tests (33 new; four skipped)**, strict types on 414 files,
  formatting/lint and C# protocol in **120.25 seconds**. Verify **63,176 protected
  old files / 35,038 control-source files** and both full player/Adam byte seals.
  Main preflight passes with native hosts disabled and creates no comparison
  workspace. Only passed control/audit references change from the frozen template.

Next work, in order:

1. **Owner runs the finite fresh-game comparison — NOT STARTED.** Allow **20–35
   minutes**; one native process, shared frozen files, zero app copies, 15-minute
   sessions, 2 GB memory / 4 GB cumulative outputs. Resume sealed games at clean
   boundaries. Preserve uncertain work, never retry it automatically or replace seeds.
2. **Assess playing benefit before more teacher collection or fitting.** Compare
   full wins first, then acts/floors/declared bootstrap returns, failures and actual
   CPU. Keep each player's result and whole-seed uncertainty. Verified failures and
   unattempted games retain the original denominator and zero evaluation value.
3. **Choose the next bounded learning change from that evidence.** Better combat
   continuation or candidate quality remains the goal; do not scale the prior flat
   teacher, loosen its preference rule, silently reward HP or tune on the old eight
   inspected worlds. Preserve both full states and require fresh complete-game
   evaluation. Foundation readiness still precedes adaptive thinking.

Single owner command, from any directory with STS2 closed:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/compare-native-combat-behavior-v1.sh
```

Codex ran only short controls, saved audits and checks. No long comparison, training,
promotion, push or GitHub Actions was started. No next experiment follows the command.

### Preserved combat-planning result handoff (commands below are historical)

## Current handoff — combat-planning pilot complete; isolate cheap greedy behavior next

**The finite planner comparison finished cleanly, with mixed strategic results and
no reliable new better-turn labels.** Neither player was trained. Both exact weights,
all Adam state and counters **5,658 / 6,045** remain unchanged. See
[completed assessment](native-bounded-combat-planning-result.md) and
[portable result evidence](evidence/native-bounded-combat-planning-result-v1.json).

Completed (#35 / #143 / #146):

- [x] Finish **756/756 native attempts**: 252 combat proposals + 504 selected-plan
  evaluations, reusing 504 verified old baselines. Zero failures/skips/blocked turns,
  app copies, full wins or optimizer updates. Eight original TRAIN worlds / 63 turns;
  dependent branches are not independent fresh games or ordinary PPO experience.
- [x] Measure the mixed outcome: tested encounter exits alive **332 → 344 / 504**,
  average floor **11.377 → 11.784**, act-clearing branches **5 → 3**, best floor
  **22 → 22**, mean bootstrap return **0.025742 → 0.026040**. Planning versus its
  paired baseline gives **96 higher / 34 lower / 374 tied returns**. Four worlds
  have identical paired returns; three have positive mean changes and one negative.
- [x] Rebuild alternative-turn feedback: **25/65/350 higher/lower/tied** becomes
  **39/84/317** (79.5% → 72.0% ties). The unchanged rule admits **zero** better-turn
  preferences; smallest positive-mean sign p remains **0.1445**. No readiness pass.
- [x] Decompose proposals: **51/63 selections use the greedy remainder**. Twelve
  choose another sample: one survival rescue, eleven higher-HP alive exits. Eleven
  turns have four identical proposals; all four die for twenty turns. The original
  comparator samples actions, so the benefit of search over cheap greedy combat
  remains unmeasured. Do not equate surviving with better full-run play.
- [x] Verify **756 receipts / 63,175 source files**, all bindings, endings, returns,
  CPU charges, selection and tables in **130.06 seconds**. Decode 38,460 proposal
  decisions / 252 exits and reconstruct 2,453 remainder steps. Preserve both full
  states. Scored continuation probabilities are not independently reconstructed;
  retained native journals and collection delivery audits remain verified.
- [x] Reconcile all sessions: **37.76 wall minutes**, 1,842.17 CPU seconds,
  465.16 MB peak RAM / 1.282 GB cumulative output. Mean charged case CPU is
  **2.125 → 10.464 seconds**, inside the same 128-second ceiling. Repeated search
  accounting charges are separate from physical experiment CPU.
- [x] Pass **2,025 tests (four skipped)**, strict types on 406 files,
  formatting/lint and C# protocol in **119.54 seconds**. Tracked changes are
  documentation only; both complete player/Adam byte seals still match afterward.

Next work, in order:

1. **Prepare a small matched sampled-versus-greedy combat control.** Use both
   preserved players, identical noncombat behavior, explicit RNG streams and fresh
   whole-game seeds. If reusing the old roots to compare search, include an
   always-greedy remainder arm. Measure wins, acts, floors, failures and actual CPU;
   do not tune against these already inspected eight worlds.
2. **Improve continuation or candidate quality from that evidence.** Do not expand
   the unchanged four-proposal teacher, loosen its preference rule, silently reward
   HP or launch another critic grid. Local survival alone has not supplied reliable
   strategic targets. Freeze any changed teacher/student method separately and
   validate across whole worlds.
3. **Use supported targets for a bounded student test.** Fork both exact full
   weights and every Adam moment, keep all legal action families learnable, separate
   privileged teacher data from ordinary PPO and evaluate fresh complete games.
   Foundation readiness still precedes model promotion and adaptive thinking.

**No owner command is needed for this completed comparison.** No new long task,
training, promotion, push or GitHub Actions follows the saved assessment.

### Preserved bounded-combat preparation handoff (commands below are historical)

## Current handoff — bounded combat-planning comparison qualified; owner pilot next

**The bounded native planner comparison is implemented and qualified.** It preserves
both exact players and all Adam state, reuses the complete-turn pilot's baseline,
and tests whether completing a fight with sampled planning improves full-run feedback.
See [design and owner command](native-bounded-combat-planning.md) and
[portable evidence](evidence/native-bounded-combat-planning-v1.json).

Completed (#35 / #143 / #146):

- [x] Generate four combat remainders per original initial turn: one greedy and
  three sampled continuations. Native transitions handle subsequent turns and nested
  choices. Seal each encounter exit before later decisions; reject unknown ownership,
  incomplete traces, changed observations/costs/targets and decision/storage caps.
- [x] Select by observed alive exit, remaining public HP and fixed proposal order.
  The selector accepts no later run scores, floors or wins. This is an explicit
  tactical heuristic, not a new HP reward. Original full-run victory and bootstrap
  score remain unchanged; fixed-world teacher branches are not ordinary PPO.
- [x] Charge every evaluation for all four search episodes plus its own execution,
  without amortization, inside the original 128-CPU-second whole-run ceiling. Search
  is capped at 64 CPU seconds total / 32 per proposal. Retain actual resource usage
  separately; equal ceilings do not mean equal CPU spending.
- [x] Complete **28/28 native control attempts** with zero failures/skips/blocked
  turns or app copies. Exact duplicate selected traces and two fresh original
  baseline traces match. Eight old baseline episodes are reused. Two sessions use
  **247.23 wall seconds**, 158.20 CPU seconds, 372.93 MB peak memory and 56.26 MB
  cumulative output. The two-world control is a correctness check, not better play.
- [x] Reconstruct all **4,338 saved public decisions**, probabilities, plans,
  encounter exits, tactical selection, charged costs and tables in **60.92 seconds**.
  Native delivery is audited during collection; saved verification checks those
  journal bytes without claiming a new independent delivery semantic reaudit.
- [x] Pass **2,029 tests (50 new)**, strict types on 406 files, formatting/lint and
  C# protocol in **129.17 seconds**. Verify **51,213 original evidence files** and
  **34,547 control-source files**, preserving both full player/Adam byte seals and
  counters **5,658 / 6,045**. Main preflight passes with native hosts disabled and
  creates no pilot workspace. Only control/audit IDs change from the predeclared
  main template; roots, proposals, ranking and budgets stay fixed.

Next work, in order:

1. **Owner runs the finite comparison — NOT STARTED.** Reuse all 504 old baseline
   episodes. Eight original TRAIN worlds / 63 initial turns require 252 search
   attempts plus 504 selected-plan evaluations: **at most 756 new attempts**. Allow
   roughly 60–90 minutes, shared immutable game/runtime/support files, one process,
   15-minute sessions, 2 GB memory / 4 GB outputs. Clean pauses resume sealed work;
   uncertain or changed evidence stops for inspection. No automatic retry/repair.
2. **Assess actual benefit before more collection or fitting.** Compare full-run
   wins, floor/return changes, encounter exits, failures, actual/charged CPU and how
   often initial turns still tie. One hidden world per root; conditional streams
   are not independent seeds. Keep the original preference rule and uncertainty.
   HP selection can spend scarce resources; it is not proof of strategic improvement.
3. **Choose a bounded student intervention from the evidence.** Keep public-only
   current inputs and whole-world fitting/selection, fork both exact full states
   and every Adam moment, keep all legal families learnable, and test fresh complete
   games at equal declared compute. No future plan observations in student features.
4. **Keep the foundation priority.** No new critic grid, other difficulties, large
   GA, model promotion or adaptive controller follows this collector. Readiness
   still precedes variable thinking budgets. Revise a flat method rather than
   automatically scaling it.

Single owner command, from any directory with STS2 closed:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/compare-native-combat-planning-v1.sh
```

Codex ran only the short control, saved audits and repository checks. No long pilot,
training, promotion, push or GitHub Actions was started. The command resumes only
this finite comparison; no subsequent experiment or fitting follows completion.

### Preserved complete-turn result handoff (commands below are historical)

## Current handoff — complete-turn pilot finished; test combat continuation before scaling

**The finite complete-turn teacher completed cleanly, but it has not established
better play or reliable better-turn labels.** Both exact players and all Adam state
remain intact. See [completed result](native-complete-turn-teacher-result.md),
[portable evidence](evidence/native-complete-turn-teacher-result-v1.json) and the
[preserved collection design](native-complete-turn-teacher.md).

Completed (#35 / #143 / #146):

- [x] Finish **569/569 native attempts**: 65 proposals become 63 unique plans,
  followed by 504 scored branches across eight original TRAIN worlds. Zero
  failures/skips/full wins/app copies or optimizer updates. Five dependent branches
  clear an act; best floor 22. No nested-selection decisions occur in this pilot.
- [x] Reconstruct all outcome tables: **25 higher / 65 lower / 350 tied paired
  returns (79.5% ties)**. Greedy reference has the highest sampled mean, including
  ties, in six of eight positions. No alternative passes the unchanged preference
  rule; smallest positive-mean improvement sign p is 0.1445. Two positions are flat.
- [x] Check why turns tie: **40 alternatives change the exact public boundary; 18
  still have identical paired final returns**. An elite turn leaves 28 HP against
  53 enemy HP, another 20 against 84, yet both lose every continuation on floor 7.
  This is a feedback limitation, not proof that HP alone should become a reward
  or that stronger continuation will necessarily recover these source positions.
- [x] Verify **569 receipts / 33,426 source files**, terminal evidence, bindings,
  returns, candidate freeze and all tables in **33.56 seconds**. Decode 9,942
  proposal decisions and verify 65 proposal boundaries / 225 turn steps. Preserve
  both complete model/Adam seals and counters **5,658 / 6,045**. Scored continuation
  probabilities are not independently reconstructed by this saved-only assessment;
  native journal bytes verify and collection delivery audits remain preserved.
- [x] Reconcile all three collection sessions: **28.71 wall minutes**, 1,391.65 CPU
  seconds, 425.44 MB peak memory and 850.26 MB cumulative output. Do not add
  cumulative storage or mistake the final-session duration for the experiment total.
- [x] Pass **1,979 tests**, strict types on 396 source files, formatting/lint and C#
  protocol checks in **119.65 seconds**; tracked changes are documentation only.

Next work, in order:

1. **Qualify a bounded combat planner as continuation and candidate source.** Keep
   frozen public roots/plans, native transitions, outcome-blind proposals and equal
   declared compute. Start with a short correctness/cost control, then freeze one
   finite owner-run comparison. Record fight completion, postfight health and loss
   location as diagnostics alongside genuine complete-run outcomes and the explicit
   bootstrap score. No silent HP reward, outcome-selected positions or claim of
   stronger play before measurement. Weak continuation, limited candidates and
   already difficult source positions remain competing explanations.
2. **Declare a bounded student intervention only if feedback supports it.** Preserve
   uncertainty and whole-source-world validation; fork both players and every Adam
   moment, keep every legal decision family learnable, and test fresh complete games
   at equal compute. Teacher counterfactuals remain separate from ordinary PPO.
3. **Do not scale the unchanged teacher or loosen its preference rule.** No further
   critic grid, other difficulty, large GA or adaptive controller is required here.
   Foundation readiness still precedes variable thinking budgets.

**No owner command is needed for this completed collection.** No new game, fitting,
model promotion, push or GitHub Actions follows the saved assessment. Long tasks stay
owner-run; the next command will accompany a separately implemented and qualified plan.

### Preserved complete-turn preparation handoff (commands below are historical)

## Current handoff — complete-turn teacher ready; owner-run pilot next

**The complete-turn comparison teacher is implemented and qualified.** It compares
complete remaining-turn sequences through an observed native boundary. Both players,
full Adam states and the coarse predictor remain unchanged. No new fitting or model
promotion occurs. See [design, evidence and owner command](native-complete-turn-teacher.md)
and [portable metrics](evidence/native-complete-turn-teacher-v1.json).

Completed (#35 / #143 / #146):

- [x] Preserve the eight public TRAIN roots, both continuation players, native A8
  rules, full-run objective and score. Propose one greedy reference turn and one
  sampled complete turn for every legal first action; all offered moves remain in
  scope. Include nested choices and native early endings; reject unknown ownership
  and truncated/capped turns. Bound plans to 64 decisions / 1 MB each.
- [x] Seal proposals before their continuation choices and freeze all candidate sets
  before scored comparisons. Exact trace deduplication retains aliases/reference;
  selection accepts no final-return/floor/win fields. Native proposal games finish
  for clean closure, but their outcomes do not rank or filter candidates.
- [x] Complete **39/39 native control branches** (13 proposals, 12 distinct plans,
  26 comparisons), including exact duplicate reference traces. All public turn
  boundaries match; zero failures/skips/wins/app copies or optimizer updates.
  Two sessions total **142.37 seconds**, 390.59 MB peak RAM / 66.46 MB cumulative
  output. This control has no native nested selection; unit regressions cover those
  paths and the existing bridge's qualification remains separate.
- [x] Reconstruct **6,077 saved public decisions**, proposal sampling, forced choices,
  boundaries, continuation probabilities, returns, candidate sets and all tables.
  Saved audit takes **32.52 seconds**; main admission requires this exact control
  and audit. Fixed-world streams remain ineligible for ordinary PPO/public-belief
  optimality claims. Native delivery is audited during collection; saved recheck
  verifies journal bytes, not an independent native-delivery semantic reaudit.
- [x] Pass **1,979 tests (52 new)**, strict types on 396 files, formatting/lint and C#
  protocol checks in **118.44 seconds**. Verify **30,487 protected original/control
  files** and both exact full model/Adam checkpoints unchanged (counters 5,658 / 6,045).
  Cached control reuse and main preflight pass with native hosts explicitly disabled.
- [x] Freeze the main recipe and one owner wrapper: eight original worlds, 65 proposals
  plus at most 520 comparisons (**585 total attempts**), eight matched continuation
  streams per unique plan. Proposal temperature 1.2, continuation temperature 0.8;
  independent namespaces avoid consuming continuation randomness during generation.

Next work, in order:

1. **Owner runs the finite pilot — NOT STARTED.** Allow roughly 30–45 minutes from
   current timing, one process, shared immutable game/runtime/support files, zero
   app copies, 15-minute sessions, 2 GB memory / 4 GB outputs. Clean resumption reuses
   sealed attempts; uncertain evidence is preserved and never retried automatically.
   Verified failed workers block their root while other planned worlds may continue.
   All source worlds, failures and skipped work remain reported.
2. **Assess whether coherent turns provide useful lessons.** Reconstruct tables,
   examine uncertainty, ties, rare outcomes and source diversity. Original worlds
   stay the independent units; 585 attempts do not mean 585 independent seeds.
   Retain the original preference rule and full wins as primary. Do not manufacture
   winning labels, choose a convenient outcome subset or treat a best sample as a
   stronger player. If still flat, assess stronger continuation before scaling.
3. **Declare a bounded student/credit experiment only if feedback supports it.**
   Future student inputs are only the public state at the decision being taught,
   never later plan observations. Fork both players and complete Adam state, keep
   all legal families learnable, and test fresh complete games at equal compute.
   Teacher counterfactuals are separate supervision, not ordinary PPO episodes.
4. **Keep foundation work focused.** No new critic grid, other difficulties, large
   GA or adaptive controller is required for this pilot. Source/world-aware input
   or continuation improvements remain conditional. Readiness precedes adaptive
   thinking; no automatic training or next experiment follows collection.

Single next command (from any directory, with STS2 closed):

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/collect-native-complete-turn-teacher-v1.sh
```

No long collection, new fitting, model promotion, push or GitHub Actions is started
by Codex. Historical teacher/value results and implementation bytes remain preserved.

### Preserved completed later-turn teacher assessment

## Current handoff — later-turn teacher complete; improve the feedback before more training

The owner completed **456/456 native branches**, with zero failures/skips/wins or app
copies. The saved assessment reconstructs terminal returns and action tables, verifies
all receipts / 28,943 source files, and preserves both players and complete Adam states.
No fitting, model promotion or adaptive-controller work occurred.
See [result and evidence](native-later-combat-teacher-result.md) and
[original collection design](native-later-combat-teacher.md).

Completed (#35 / #143 / #146):

- [x] Collect all 57 actions across eight later combat menus with eight continuation
  streams each. Eight original hidden worlds are the independent source units;
  the 456 fixed-world branches are not ordinary PPO games or 456 independent seeds.
- [x] Rebuild the full paired comparison: **23 higher, 79 lower and 290 tied returns**
  (74.0% ties), six varied menus / two flat. Zero alternatives pass the unchanged
  improvement rule; the smallest improvement sign p-value is 0.3633. Three dependent
  branches clear an act and reach floor 21; no full-run wins or policy gain established.
- [x] Inspect negative examples and rare gains. Ending the turn is clearly worse in
  two menus, but its current policy probability is already only 0.0066% / 0.1011%.
  Some apparent better choices depend heavily on one continuation or rare act clear.
  Post-hoc reverse tests and leave-one-out checks do not admit new trusted labels.
- [x] Verify exact bindings, sealed headers/traces, native ending fields, whole-run
  scores, uncertainty and tables in a **17.49-second saved-only check**. Both full
  player/Adam byte seals and counters (5,658 / 6,045) agree. Eight current public-root
  policy distributions reproduce the reference choices. Full continuation probabilities
  across 68,524 declared decisions are not rerun by this assessment; the prior 24-branch
  control reconstructed all of its 3,950 choices. Do not imply a full behavior reaudit.
- [x] Reconcile both collection resource sessions: **23.01 minutes total wall time**,
  1,127.77 CPU seconds, 391.79 MB peak RAM, 674.54 MB cumulative output. The main report's
  wall-time field covers the final collector session only. Do not add cumulative storage.

Next work, in order:

1. **Implement a small coherent-turn comparison teacher.** Compare bounded legal move
   sequences through end turn, instead of forcing one card and immediately reverting
   to the same continuation. Freeze generation, roots and budgets before outcomes.
   Preserve the existing teacher and all results; this is a hypothesis, not a proven
   improvement. No larger repeat of the unchanged one-action batch is the next task.
2. **Qualify the changed feedback and run one finite owner pilot.** Native transitions,
   public-only student inputs, fixed-world ownership, repeated continuations and the
   declared full-run outcomes/auxiliary score remain explicit. No handwritten HP or
   upgrade rewards. If turns remain flat, assess stronger continuation before scaling.
3. **Test a declared numerical learning intervention only when useful signal exists.**
   Use uncertain sequence/action targets, whole-source-world fitting/selection and
   fresh complete games at equal compute. Fork both players and every Adam moment;
   all legal decision families remain learnable. Do not manufacture confidence labels
   or treat hindsight branches as on-policy PPO. Wins remain primary.
4. **Keep the current critic and difficulty.** No new critic grid, other ascensions,
   large GA or adaptive budget controller is required here. Rich shared representation
   and independent outcome coverage remain conditional follow-ups. Foundation readiness
   still precedes adaptive thinking.

**No owner command is needed for this completed collection.** Long collection/fitting
remains owner-run. No new games, training, push or GitHub Actions follows automatically.
Result documentation passes formatting/lint and strict types. The full repository
suite stops at its 240-second cap; this is not a new full pass. Preserve the capped
resource receipt rather than automatically launching a longer check. Learner code
and all player/optimizer files remain unchanged.

### Preserved completed rich-correction handoff

## Current handoff — baseline-preserving rich correction completed; retain the current predictor

**The controlled correction test is implemented and complete.** It reuses 128 saved
ordinary TRAIN games in 16 outer whole-game folds, preserving both players and every
Adam state. The original 20-feature ridge keeps lambda 0.001; only extra rich slopes
receive a separately selected penalty. No correction is an explicit candidate.
Each inner split refits its own coarse offset, without validation-return leakage.
See [design and result](native-residual-value.md) and
[portable evidence](evidence/native-residual-value-v1.json).

- **No useful gain:** equal-game withheld MSE is **5.512797865e-5 baseline** versus
  **5.532921364e-5 correction** (+0.365%). No correction is selected in 10/16 folds;
  four choose lambda 100, two choose 10. Two cohorts improve slightly, two worsen.
- **Baseline preservation passes:** all 16 original coarse coefficient arrays and
  forecasts match bit-for-bit. Saved-only verification reconstructs all selected
  models, choices, predictions, pure fitting errors and separate penalties.
- **All 128 games remain in the official result.** The rare act clear and ordinary
  127-game sensitivity both fail to reveal a useful gain. Do not remove rare successes
  or reinterpret reused development evidence as untouched confirmation.
- **Short execution only:** control 24.97 seconds, complete comparison 44.27 seconds,
  saved verification 27.62 seconds; zero new games, app copies or actor/Adam steps.
  The main comparison uses 730.07 MB peak RAM and 4.49 MB new output. Source checks
  protect 11,755 files including the two full model/optimizer checkpoints.

Next work, in order (#35 / #143 / #146):

1. **Keep the current predictor; return to informative action learning.** Do not
   integrate this correction, repeat unchanged PPO at greater scale or search another
   critic grid on these same outer targets. The negative result does not prove that
   rich information is useless or that regularization alone caused the earlier gap.
2. **Predeclare a revised finite action-comparison pilot.** The completed first native
   combat teacher has 78.1% ties and zero admitted preferences from fight-entry roots.
   Use more consequential later-turn positions or coherent turn choices, retaining
   whole-run outcome labels, uncertainty and source/policy/world ownership. Keep
   confidence thresholds intact; dependent fixed-world branches are not new ordinary
   PPO games or public-belief-optimal labels. Use existing diagnosis rather than
   another general audit with no proposed change. Long collection remains owner-run.
3. **Test whether useful lessons change the actor and improve fresh games.** Preserve
   both players and full Adam in separate forks. Declare any auxiliary supervision
   separately, keep all legal decision families learnable, and compare gameplay on
   fresh whole-game seeds at equal compute. Forecast MSE alone is not the goal.
4. **Representation/data follow-ups remain conditional.** A compact shared entity/field
   encoder or additional independent act-clear coverage may help, but are not a new
   mandatory critic-tuning sequence before action learning. Qualify policy conditioning
   before pooling different players' outcomes. No strategic reward redesign is implied.
   Full wins remain primary, readiness precedes adaptive thinking, GA/other difficulties
   remain deferred.

**No owner rerun is needed for this completed test.** No new learning, collection,
promotion, push or GitHub Actions follows automatically.

**Verification passes:** 1,904 repository tests (18 new controls), formatting/lint,
strict types on 381 files and the C# protocol contract in **113.76 seconds**, with
399.16 MB peak RAM and no cap hit. The post-check audit verifies all protected source
bytes and both full model/Adam checkpoints unchanged. Their optimizer counters remain
5,658 and 6,045, with every first and second moment preserved.

### Preserved completed prediction-error diagnosis

## Current handoff — saved errors show rare outcomes, dictionary omissions and coupled shrinkage

**Saved prediction-error diagnosis is complete.** All 128 ordinary TRAIN games and
13,793 choice-bearing public inputs reconstruct exactly; published held-game errors
match, with no refits, game attempts, actor/Adam changes or promotion. The current
ridge remains the best tested baseline. See [diagnosis](native-value-error-diagnosis.md)
and [portable evidence](evidence/native-value-error-diagnosis-v1.json).

Material findings (#143 / #35 / #146):

- **One Act 1 clear contributes 54.75% of current-ridge squared error.** Its own fitting
  fold has no act clears. Most error is before the eventual advancement; after entering
  Act 2 its progress-aware prediction is close to the observed auxiliary return. This
  does not prove the rare outcome was predictable from early public information.
- **The rich models also lose on the other 127 games:** rich linear +30.05% MSE;
  rich neural +65.21%. Removing the rare game is a sensitivity analysis, never a new
  official denominator or a reason to reduce successful outcomes' weight.
- **Unfamiliar content is only part of the picture.** About 6.34% of public fact
  occurrences are new to the fitting games; 74.01% are familiar, varying facts omitted
  by the bounded dictionary. These are redundant encoder-fact counts, not semantic
  information percentages. Unseen entity definitions correlate with baseline error,
  but weakly with the rich model's excess error; causality is not established.
- **One penalty also suppresses the simple features.** The rich arm's simple-feature
  coefficient norm is a median 2.63% of the coarse-only arm's. Removing its rich term
  makes its own forecast worse; the issue is not evidence that all rich information
  is useless. Correlated columns can redistribute coefficients too: this motivates a
  controlled test, not a causal conclusion or a validated alternative predictor.
- **Broader saved TRAIN coverage is still sparse:** five act-clearing trajectories,
  zero wins in 512 games across different behavior policies. Do not pool them as one
  unchanged player's on-policy data or count exploration-arm repeats as independent
  successful seeds. Critic dictionary omissions do not imply missing engine mechanics.

Next work, in order:

1. **Implement one coarse-baseline-preserving rich correction comparison.** Refit the
   current coarse baseline separately within each inner fitting set; learn a rich
   residual with its own regularization, including no correction as a candidate. Select
   only on inner whole games, then refit outer train and test outer held games. Preserve
   the current predictor, both actors and all Adam state. An outer-fitted baseline must
   never supply inner-fold offsets. This tests coupled shrinkage without another
   large architecture change or any new actor restriction.
2. **If needed, test a compact shared entity/field representation.** Keep identity,
   ownership and current numeric values; measure coverage and generalization instead
   of enlarging the owner/full-text dictionary blindly. No exhaustive mechanics sweep
   or alternate ascension support is a prerequisite for this A8 learning work.
3. **Plan additional independent outcome coverage only with a declared purpose.**
   Measure learning curves and act-clear coverage, retain policy ownership or qualify
   policy conditioning, and consider an explicit curriculum if weak play cannot
   generate informative outcomes. Leave long collection/training to the owner. Do not
   silently alter the victory objective, add strategic rewards or relabel historical
   counterfactual games as fresh PPO experience.
4. **Fresh confirmation, then useful action credit.** Freeze a supported recipe before
   untouched whole-game forecasts and bounded equal-compute learning from both saved
   players/full Adam. If the one controlled correction test has no useful signal,
   return to the actor/action-learning bottleneck rather than endlessly tuning critics.
   Adaptive thinking remains behind base readiness; GA and other difficulties deferred.

All diagnostic jobs finished within short caps (10–77 seconds each); zero app copies,
optimizer updates and game attempts. Existing model reports/code remain immutable.
All **1,886 repository tests**, formatting/lint, strict types and the C# protocol
contract pass in **124.02 seconds** (105.77 CPU seconds, 388.92 MB peak RAM). The
post-check audit verifies **11,842 source files**, including both players and every
Adam moment/counter, unchanged. The diagnosis is ready for local commit; no push,
GitHub Actions, new training or owner-run task follows this inspection.

### Preserved completed linear-comparison handoff

## Current handoff — regularized public linear values with whole-game validation

The **matched-input neural study is complete**, 16 encoded folds / 48 paired fits,
128 saved TRAIN games, three numerical initializers. At the fixed primary update 24,
held MSE is **5.5128e-5 current ridge**, **5.5841e-5 coarse masked neural** and
**7.1256e-5 rich neural**. Rich is **29.3% worse** than ridge, in all four cohorts and
all three initializer summaries. Fitting error falls as held error rises; 99.4% of the
combined fitting-loss decrease is a smaller weight penalty. This supports testing
regularization and generalization, not adopting this network or assuming more games
alone will fix it. Existing reports/code and both players/full Adam states are preserved.

Ordered work (#143 / #35 / #146):

1. **Regularized rich-input linear value — implemented and benchmarked.**
   Compare current ridge, tuned coarse linear and tuned rich linear on the sealed input
   cache. Closed-form ridge removes neural initialization, Adam and epoch count. Keep
   separate pure prediction errors and penalties; do not tune on outer-held targets.
2. **Whole-game nested selection.** Each outer fold fits on 24 games and holds eight.
   Select ridge strength using three 16-fit/eight-validation inner splits, separately
   for each arm; refit all 24 and score the untouched outer eight. Each game has equal
   mass. Keep the four player/round cohorts separate. The progress offset is fixed;
   never reuse the old outer-fit ridge as an inner offset, which leaks validation returns.
3. **Freeze the cached dictionary honestly.** It was selected using outer-fitting inputs
   in the previous study; it excludes outer-held inputs but is not rebuilt within inner
   folds. Means/scales/centering and coefficients fit only the current fitting games.
   Reused development games cannot provide untouched confirmation, and overlapping folds
   or numerical repeats cannot be counted as independent games/players.
4. **Require fresh confirmation before credit integration.** Only a supported frozen
   value recipe advances to fresh whole-game forecast validation and then bounded
   learning from both saved players/full Adam states. Measure gameplay at equal compute;
   wins remain primary and auxiliary floor/acts secondary. No automatic adoption, PPO
   expansion, reward redesign, adaptive controller or game attempts follow this study.
5. **Later follow-ups remain evidence-driven.** More informative combat teacher roots,
   policy-conditioned values, additional independent games or another model are separate
   choices. GA/direct evolution, other difficulties and large sequence models remain
   deferred; useful base play/readiness precedes adaptive thinking.

The short control uses one real cached 24/8 outer fold; the main comparison has 16
independently sealed restartable folds. It reuses public inputs without decoding histories,
never touches the saved actors/optimizers, and verifies source bytes before and after.
See [design, validation boundaries and execution guide](native-linear-value.md).

**Completed result:** all 16 folds / 128 whole-game predictions, **896 closed-form
ridge solutions**, in **84.96 seconds** (495.50 MB peak RAM, 5.30 MB output). Current
ridge MSE is **5.5128e-5**; tuned coarse linear **5.5328e-5** (+0.36%); tuned rich linear
**6.3903e-5** (+15.92%). Rich remains worse in every cohort. Most rich folds select
strong shrinkage (lambda 10; three choose 1, two choose 100). **No replacement is adopted.**
All 32 saved models and chosen lambdas reconstruct; forecasts agree bit-for-bit, separate
fitting error and penalty terms agree, and **11,681 source seals** verify unchanged.
The saved-only audit takes 10.00 seconds, no refits or games.

**Next evidence-driven item:** inspect whether remaining errors concentrate in rare long
runs and unseen public facts before selecting a new data/representation intervention.
Do not search another grid on outer targets or blindly expand PPO. More independent
whole games, stronger interaction features or better training lessons remain hypotheses;
none is established as the fix by this negative study. Any new collection is separately
bounded and owner-run when long. Keep both players and all Adam state as starting points.

**Final repository verification passed on 2026-10-20.** The owner completed the full
formatting/lint, strict typing, test suite and C# protocol check in **116.07 seconds**,
with **99.39 CPU seconds** and **385.27 MB** peak RAM. Receipt:
`sha256:bf55e76c5586d10008893d30f0aaf68c3bcbfd7aae4b5d188f7f937efc80ee33`.
The earlier four-minute capped check remains preserved as incomplete historical evidence;
the completed owner receipt supersedes its pending handoff. All **11,681 protected source
files**, including both players and full Adam states, verify unchanged after the check.
The 17 focused regression tests also pass. The implementation is ready for a local commit;
no push, GitHub Actions or long follow-up is started by Codex.
[Portable results, receipts and limitations](evidence/native-linear-value-v1.json).

**No rerun is needed.** The comparison and final verification are complete. The next
work item is the saved-prediction diagnosis above, not another unchanged training run.

### Preserved teacher preparation (completed above)

## Current handoff: collect native combat comparisons, then test numerical lessons

The owner completed the **512-TRAIN-game / 71,293-decision** feedback audit. All 16
behavior and credit reports reconstruct exactly; 96 finite input probes, 16 order checks
and all disposable teaching controls pass. The actual credit predictor beats the
other-fold constant in every batch. Training changes probabilities with assigned credit,
but the prior fresh-game comparisons still do **not** confirm stronger play. This supports
testing better action-level lessons rather than repeating an unchanged PPO recipe.

Implemented the separately versioned **native combat comparison teacher**. It replays a
sealed TRAIN prefix in a fresh isolated native worker, verifies the exact public root,
forces one offered action, then continues with the unchanged round-60 player to a genuine
full-run ending. Eight distinct seeds cover four ordinary fights, two elites and two
bosses across both players. Every action in each selected menu is compared: **48 actions
× eight continuation-policy streams = 384 planned branches**. All original and final
weights, Adam moments/counters, runtime, SDK, frozen game and account profile are preserved.

The short native control passes **24/24 terminal branches**, zero failures/skips/wins/app
copies, both duplicate public traces identical. It takes **75.04 seconds**, **373.26 MB**
peak RAM and **34.01 MB** private outputs. It verifies exact prefix/root delivery and
complete menus; two policy samples per action do not qualify training targets. No optimizer
updates or checkpoint promotion occur. The main pilot is preflighted and remains unstarted.

This first teacher is explicitly **privileged fixed-world evidence**: each root keeps its
original native seed/hidden world. Only continuation-policy sampling varies; it does not
resample unknown draw orders. Student inputs remain public. It is not an optimal-action
oracle, a public-belief search result or ordinary on-policy PPO experience. All failures
remain visible; a failed root supplies no lessons and its remaining branches are skipped
after verified worker retirement. Prefix drift or uncertain delivery stops for inspection.

Next, in order:

1. **Owner runs the finite teacher pilot.** Collect full-run wins and declared auxiliary
   floor/act returns, with matched policy streams, native delivery audit, complete candidate
   coverage, sampling uncertainty and source provenance. No HP/Smith rewards or strategic
   masks. Eight roots are a feasibility pilot, not enough diversity to establish good play.
2. **Audit lesson quality and feed numerical targets into a separate training fork.** Check
   action binding, signal/uncertainty and behavior across independent roots. Use an explicitly
   privileged-teacher supervised value/ranking loss; preserve both players' full Adam state.
   Historical/counterfactual data must never be relabeled fresh PPO. A pilot with no reliable
   preferences is a result to inspect, not a reason to loosen its gate after seeing outcomes.
3. **Compare fresh full-run learning with matched compute.** Test teacher-assisted versus
   unchanged training from both saved players, with untouched evaluation seeds. Judge wins
   first, then auxiliary floor/act progress, failures and compute. Expand root diversity or
   revise the teacher only in a new predeclared study. No automatic follow-up or promotion.
4. **Qualify public-consistent hidden-world sampling before public-belief search claims.**
   More policy samples in one original world do not solve hidden-information bias. Separate
   this experimental teacher from the eventual low/medium/high thinking controller.
5. **Readiness before adaptive thinking.** Strong base play, value/calibration and equal-compute
   search benefits remain unmet. GA/direct evolution and other difficulties remain deferred.

**One next owner command (approximately 20–30 minutes):**

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/collect-native-combat-teacher-v1.sh
```

One native worker, 15-minute sessions, 2 GB RAM / 4 GB generated-output caps. Clean reruns
reuse sealed branches; an interrupted uncommitted branch is preserved for inspection.
No app copies, optimizer updates, adaptive controller or automatic next experiment.
See [design and limits](native-combat-teacher.md),
[completed audit](evidence/native-learning-feedback-result-v1.json) and
[teacher evidence](evidence/native-combat-teacher-v1.json).
Full local verification passes **1,830 tests**, formatting/lint, strict types and C#
contracts. GitHub #143 / #35 / #146 reflect this handoff with prior history retained.
No push or GitHub Actions.

### Preserved feedback-audit preparation (the owner completed it above)

# SpireShift backlog

Updated 2026-10-19 after the completed rest-exploration comparison and owner discussion.
Codex runs short checks; the owner launches/monitors tasks expected to take ≥5 minutes.

## Current handoff: turn completed-game diagnosis into numerical learning improvements

The rest-exploration experiment is complete: **896/896 genuine terminal attempts, zero
technical failures, zero full wins, zero app copies**. Its 512 TRAIN attempts and 384 final
test attempts remain distinct. The final 128-game/version test means are **11.0859375 original,
11.453125 standard, 11.3203125 exploration**. Exploration minus standard is **−0.1328125**,
95% paired-seed interval **[−0.8125, 0.546875]**. Neither training arm establishes stronger play.
All four round-60 forks, their original round-56 states and every Adam moment/counter are kept.

Smith is card upgrading. Its rarity is **not an error or failure criterion**: poor earlier
combat can make healing necessary. Training Smith counts rise 1→30 under exploration, but
this alone supplies neither an optimal-action label nor a reason to reward upgrades.
The correct mixture gradient can give very unlikely exploratory actions weak direct feedback;
this is a mechanism to measure, not proof that changing it would win games.

The next work must produce a corrected input/learning mechanism or trustworthy numerical
lessons. Written assessments do not train a neural network. Do not launch another unchanged
large continuation, invent HP/Smith bonuses, or treat old-policy records as fresh PPO data.

Ordered work (#143 / #35 / #146):

1. **Current completed-TRAIN feedback and learning controls.** Reconstruct the exact 16 saved
   32-game batches (512 attempts), their behavior likelihoods, whole-game cross-fitted credit,
   and before/after probabilities. Compare prediction errors against same-fold constant and
   current-progress references, expose game/menu weighting, rest health context and observed
   final combat encounters. Check finite public-fact perturbations and candidate order, then
   teach an explicitly invented numerical label to a disposable full model/Adam copy. Reuse the
   earlier successful conditional-input controls; do not repeat an exhaustive mechanics gate.
   No evaluation histories, native game attempts, production updates or causal action labels.
   Run a short control first; leave the complete audit to the owner if ≥5 minutes.
2. **Repair a measured defect or qualify native action comparisons.** If actual inputs or
   arithmetic fail, fix and verify them before collecting again. Otherwise qualify bounded,
   public-information native combat branches and produce state/action/return comparisons with
   exact seeds, budgets, uncertainty and provenance. A single losing trajectory does not identify
   the bad action. Native short-horizon targets remain auxiliary to full-run victory.
3. **Feed verified lessons into training and test fresh play.** Use a declared supervised
   action-ranking/imitation or value loss; keep historical/off-policy lessons separate from
   fresh on-policy PPO. Verify target binding, loss/gradient direction and generalization before
   a bounded teacher-versus-PPO comparison with preserved weights/Adam and independent seeds.
   Measure wins first, floor/act progress, failures and compute; no forced strategic choices.
4. **Readiness before adaptive thinking.** Strong base play, value/calibration and equal-compute
   search benefits remain unmet. GA/direct evolution and other difficulties remain deferred.

The completed source experiment is immutable. New diagnostics live in their own workspace.
The short control and full-audit handoff are documented in [learning feedback](native-learning-feedback.md).
The short control passes on **64 saved TRAIN games / 9,462 decisions** in 81.92 seconds,
320.52 MB peak RAM. Both actual credit reports reconstruct exactly; finite health, energy,
cost, damage, block, target-health and candidate-order checks pass. Both disposable actors
memorize their artificial numerical targets (>99.8% after 64 steps); this is not native
action-quality or PPO-discovery evidence. The actor's credit predictor beats a same-fold
constant in both batches. The complete 16-batch audit is preflighted and remains unstarted.

**One next owner command (saved-data analysis only, approximately 8–12 minutes):**

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/diagnose-native-learning-feedback-v1.sh
```

One numerical thread, 15-minute launch cap, 2 GB RAM / 100 MB generated outputs. Completed
32-game analyses are reused on a clean rerun. No games, production training or automatic follow-up.
Full local verification passes **1,822 tests**, formatting/lint, strict types and C# contracts.
GitHub #143 / #35 / #146 reflect this handoff with prior history preserved. No push or GitHub Actions.

### Preserved selection repair and exploration preparation (main run now completed above)

# SpireShift backlog

Updated 2026-10-19 after the completed round-56 continuation and selection-menu repair.
Codex runs short checks; the owner launches/monitors tasks expected to take ≥5 minutes.

## Current handoff: selection repair and matched rest-exploration comparison

The repaired-runtime run finished **960 attempts / 958 terminal / two failed**, zero full wins.
One TRAIN and one development game exceeded the old subset-menu limit. The failed TRAIN game
was excluded. All final comparison games completed. On 128 paired fresh test seeds, mean floor
rose **10.6796875→11.3671875**, gain **0.6875**, 95% fixed-initializer seed-bootstrap interval
**[-0.09375, 1.4609375]**. This does **not** confirm stronger play. Three clean TRAIN games
cleared Act 1; neither final trained player cleared it on the final test. Both current round-56
states remain intact, **1,792 scheduled TRAIN slots/player; Adam 5268 / 5589**.

Implemented: large card subsets now use an ordered public selection cursor instead of enumerating
every combination. All subsets/orders, true native cancellation and allowed empty confirmation
remain available. Only final confirmation/cancellation reaches the game. Small menus stay
unchanged. Four scoped native checks pass: Pael five-of-21 removal twice (including reverse
order), Kifuda up-to-three enchantment and empty confirmation. Native host, game/SDK/runtime and
existing helpers stay unchanged. UI prefixes have a separate exact streaming replay audit.
No app copies or changes to the Steam account profile.

Prepared **standard versus rest-only 20% uniform exploration** from BOTH same round-56 states,
including every Adam moment/counter. Every current legal strategic action stays learnable;
there are no Smith/HP bonuses, forced upgrades or permanent baseline-proximity guards.
Rest exploration includes any currently offered potion/Proceed controls. All other sampling
stays unchanged. PPO differentiates and verifies the actual mixture; zero-mixture updates
match the existing trainer exactly. Final tests turn exploration off for all players.

The bounded comparison has four 32-game batches per method/player, **rounds 57–60**. Same fresh
TRAIN seeds across methods, independent players, separate matched final tests, final states
only. At most **896 attempts: 512 TRAIN + 384 tests**, with exact state/chunk resumption,
worker retirement, streaming memory bounds and 4 GB generated-output/RAM caps. The separate
control passes **20/20 attempts**, zero failures, four round-57 fits and 33
optimizer updates. Adam: player 2 standard **5274**, exploration **5277**; player 3 both
**5598**. Resumption reconstructs exactly; original states are unchanged. The main comparison
uses the original round-56 states and excludes control seeds/weights. It remains unstarted.

[Design, qualification and next command](native-rest-exploration.md).

**One next owner command (integration control passed; the runner verifies local checks):**

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/compare-native-a8-rest-exploration-v1.sh
```

Expected **30–60 minutes**, two-hour launch cap and clean 15-minute sessions; two private-profile
workers share immutable inputs. Close STS2. A clean rerun resumes completed work; a failed or
uncertain session stops for inspection. No automatic extension/promotion/adaptive controller.

Ordered remaining work:

1. **Assess the frozen exploration comparison.** Wins first, act clears, paired floors and
   uncertainty, failures, both initializers and computation. Check TRAIN Rest/Smith/other counts
   to establish whether exploration actually happened; counts alone do not prove better play.
2. **Improve elite/boss decisions if this remains weak.** Test a declared combat/deck exploration
   intervention or qualify a native search teacher. Preserve the current models/Adam states;
   use fresh paired evaluation. Do not replace learning with arbitrary health or upgrade rewards.
3. **Pass policy/value/calibration/search readiness before adaptive thinking.** Full-run victories
   remain missing. GA/direct evolution and other difficulties remain deferred.

#143 / #35 / #146 remain open. Local checks precede the commit; no push or GitHub Actions.

### Preserved runtime-repair preparation (before the now-completed owner run)

# SpireShift backlog

Updated 2026-10-19 after the completed shop continuation and native runtime repairs.
Codex runs short checks; the owner launches/monitors tasks expected to take ≥5 minutes.

## Current handoff: repaired native mechanics and bounded round-48 continuation

The shop run finished **1,344 attempts / 1,342 terminal / two failed TRAIN**, zero full wins.
The 128-pair fresh holdout improved **9.484375→10.3671875** mean floor (+0.8828125,
95% seed-bootstrap interval [0.2734375, 1.5078125]); no held-out Act 1 clears. This is
modest auxiliary progress, not strong play or victory readiness. Both current round-48
states remain intact, **1,536 scheduled training slots/player, Adam 4470 / 4692**.

Implemented: native **Crystal Sphere** grid/tools/payment/curse/rewards and missing Godot
ABI for **Rolling Boulder**. New v35 builds reproduce; six scoped native effect checks pass.
Covered grid contents stay hidden; native models own all game effects. Old binaries/results
are preserved, no app copies, and old coverage is not relabeled as new-host parity.

Read-only TRAIN audit: **830 clean games**, no evaluation histories. Only 51 of 17,823 end
turns still had a playable card. Terminal fights: 352 elite / 107 boss / 368 ordinary;
boss losses began at 73.7% average health. **747 Rest versus two Smith**, including 37
full-health rests with Smith available. Optional card Skip remains available and was used
377 times. These observations prioritize exploration/deck/combat strength, not hard-coded
health rewards, forced cards, or a claim that simply adding volume must work.

Next bounded step preserves BOTH latest weights and all Adam moments/counters; first fit
**round 49**, same 32-game batches / three passes / temperature / credit / objective.
At most **256 new TRAIN attempts/player** to 1,792 each, development at 1536/1664/1792,
then a separate 64-seed/player paired holdout versus imported states on the repaired host.
Maximum **960 attempts**, including 512 TRAIN, 192 development and 256 holdout attempts.
All old consumed/reserved seeds and the integration control are excluded. No failed or
recovered episode enters PPO; existing retirement/failure/session caps stay enforced.

The live integration control passes **12/12 attempts**, zero failures, two round-49
fits; Adam **4470→4476 / 4692→4698**. Originals remain unchanged; clean resumption
reuses both fits, with zero app copies.

[Repair, loss findings and next run](native-runtime-continuation.md) /
[evidence](evidence/native-runtime-continuation-v1.json).

**One next owner command; main continuation remains unstarted:**

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/continue-native-a8-runtime-v1.sh
```

Close STS2. Expect **60–90 minutes**, two-hour invocation cap, clean 15-minute sessions,
two workers, **4 GB RAM / 4 GB generated outputs**, shared immutable inputs, zero app copies.
Clean reruns retain committed games/fits/full Adam; uncertain or failed work is preserved.
No automatic promotion/readiness/adaptive controller or further extension follows.

Ordered remaining work:

1. **Assess this finite repaired continuation.** Full wins, paired final holdout, both players,
   failures, optimizer continuity and resources; do not treat development as independent test.
2. **Improve exploration and action quality if progress remains weak.** Prioritize the strong
   Rest-over-Smith skew and weak elite/boss play. Test a declared exploration intervention or
   qualify a native combat teacher; preserve both players and use fresh paired evaluation.
   Measure the effects instead of imposing arbitrary HP rewards or fixed strategic masks.
3. **Prove policy/value/calibration/search readiness before adaptive thinking.** Full victories
   remain missing. GA/direct evolution and other difficulties remain deferred.

#143 / #35 / #146 remain open. Full local checks precede the commit; no push or GitHub Actions.

### Preserved shop-repair preparation (before its now-completed owner run)


Updated 2026-10-19 after the stopped extension is audited and shop repair is implemented.
Codex runs short checks; the owner launches and monitors tasks expected to take five minutes
or more. Keep prior scientific evidence, source files, seeds and numerical states unchanged.

## Current handoff and direction

**Shop navigation repair and bounded continuation prepared (#143 / #35 / #146).**
The old extension stops after 1,440 attempts / three shop loops. Its 221 completed units and
both latest round-35 full model/Adam states are verified. Preserve the uncommitted eight-game
collection (seven terminal, one failed) diagnostically, and exclude the whole unfitted 32-game
round. No fabricated completion, worker reset, uncertain seed replay or old-policy PPO follows.
All three recorded loop states now choose Leave shop under the repaired public contract,
without replaying a game. Original states/markers/records remain unchanged.

Automatically inspect inventory once. Purchases, removal, potion use/discard, closing and
leaving remain real current choices; redundant reopening after closing is navigation rather
than a learned action. Foul Potion still targets the closed merchant and permits fresh
inspection after use. Keep every raw delivery; exclude automatic opening from PPO and verify
exact effective-menu probabilities under a separate behavior contract. Other menus and
optional card skipping are unchanged. No arbitrary HP rewards or strategic item rankings.

Restore BOTH latest states: 1,120 scheduled training games/player, Adam counters **3216 / 3261**.
Continue absolute round **36** with fresh seeds, 32-game batches / three passes and the same
native v0.111.0 / 41cef1ea Ironclad/A8 inputs, model, numerical kernel, temperature and objective.
At most **416 new TRAIN attempts/player**, preserving the original 1,536-game ceiling. Evaluate
32 development seeds/player at 1120/1248/1376/1536 under the repaired contract. Wins first then
floor; stop both after two stale checks once 256 new attempts/player finish, or at the horizon.
Keep current states, not best-seen. Then open a separate 64-seed/player paired holdout comparing
round-35 starters with stopped players under the same repair. No evaluation data enters PPO.
Maximum **1,344 attempts / 199 units**, on 1,024 distinct fresh seeds. Every old reserved seed,
including unfinished/unused reservations, plus the new control is excluded.

[Repair, audit and continuation](native-shop-continuation.md) /
[evidence](evidence/native-shop-continuation-v1.json).

The live control passes **12/12 attempts**, zero failures, seven automatic shop openings and
15 optimizer updates: **3216→3225 / 3261→3267**. It resumes cleanly across two launches without
repeating a fit. Total 287.45 s / 764.25 MB peak RAM / 56.71 MB output; zero app copies.
All **1,770 tests** pass. This is an integration check, not a strength claim; its trained
weights never start the main continuation.

**One next owner command; main continuation remains unstarted:**

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/continue-native-a8-shop-v1.sh
```

Close STS2. Expect **1–2 hours** at horizon, possibly less at plateau. Three-hour invocation
cap; clean 15-minute sessions, two workers, **4 GB RAM / 4 GB generated output**. Shared frozen
game/runtime/SDK/cache and zero app copies. Clean reruns resume games/fits/full Adam state;
failed/capped sessions stop without automatic retry. Do not resume the old stopped launcher.
No automatic promotion, readiness pass, adaptive controller or further experiment follows.

Ordered remaining work:

1. **Assess the owner-run repaired continuation.** Genuine wins, paired final holdout,
   per-player curves, failures/navigation counts, resource use and full Adam/round continuity.
   Starting and stopping players use the same repair; do not attribute their difference solely
   to navigation or reuse the old development results as a fresh holdout.
2. **If progress remains weak, improve action credit or qualify actual-engine teachers.**
   Do not blindly scale a stalled recipe, add arbitrary health rewards or permanently constrain
   strategic actions. The old extension's development gains became mixed; zero full wins remain.
3. **Full policy/value/calibration/search readiness before adaptive thinking.**
   GA/direct evolution and other difficulties remain later work.

The old fresh confirmation remains preserved: mean floor 7.2890625→8.859375, zero full wins.
The stopped continuation's pooled development mean is 8.34375→9.15625→8.75 at 512/768/1024;
its final holdout was never opened. These are auxiliary observations, not strong play or a
readiness pass. #143/#35/#146 stay open; no push or GitHub Actions.

### Preserved initial continuation preparation

**Bounded standard continuation implemented; owner launch is next (#143 / #35 / #146).**
Restore BOTH confirmed final 512-game players, original weights and all Adam moments/counters.
First continued fit is absolute **round 17**, with source counters **1,353 / 1,413**; no reset,
new initializer, selecting one player or permanent baseline-proximity/action restriction.
Keep native v0.111.0 / 41cef1ea Ironclad/A8, original public inputs/objective/bootstrap score,
temperature 0.8, **32-game batches / three passes**, qualified collector/worker and compact kernel.

Finite extent: **up to 1,024 new TRAIN games/player**, reaching at most 1,536 total each. Collect
in eight-game chunks; evaluate on 32 separate development seeds/player at 512/768/1024/1280/1536.
At each check pool wins first, then floor; stop BOTH after two checks without exceeding the best
previous pooled result, once at least 512 new games/player complete, or at the horizon. Keep the
current stopping states, never the earlier best checkpoint. Then open a separate 64-seed/player
holdout comparing the 512-game starters to their stopping states. No holdout result affects
training duration. Maximum **2,624 attempts / 398 units** (2,048 TRAIN + 320 development + 256
holdout attempts; 2,240 distinct seeds). All 18 prior native manifests and the new control are
excluded from every new partition; evaluation games never supply PPO samples.

The short continuation control **passes 12/12 attempts**, zero failures, two fits at round 17,
15 updates: Adam **1353→1362 / 1413→1419**. Original states/shared inputs remain unchanged;
zero app copies. Measured resource time **140.10 s**, peak RAM **754.55 MB**, retained **37.70 MB**.
It proves delivery/restoration/fit integration, not strength. Its two-game batches/updated states
never replace the original 512-game starting states for the main extension. Unit tests prove
exact uninterrupted-versus-restored nonzero-Adam parity and reject seed leakage/reset/corruption,
uncertain replay and holdout peeking. Full repository checks pass before the local commit.
[Plan and execution](native-policy-continuation.md) /
[evidence](evidence/native-policy-continuation-v1.json).

**One next owner command; main extension has not started:**

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/continue-native-a8-policy-v1.sh
```

Close STS2. Expected **2–3 hours** at the horizon; plateau may end it earlier. Four-hour invocation
cap, clean 15-minute sessions, two workers, **4 GB RAM / 8 GB generated output**, shared frozen
game/runtime/SDK/cache and no app copies. Re-running resumes clean committed work; once complete
it only verifies results. Uncertain/uncommitted units or a failed/capped session stop without
replay/reset/automatic retry. Inherited failure allowance spans the whole 256-game/player TRAIN
stage, 32-game development panel or 64-game holdout/version panel, not individual chunks.
The owner runs and monitors this long task. No further experiment/promotion follows automatically.

Ordered remaining work:

1. **Assess the bounded continuation.** Review genuine wins first, independent final holdout
   paired floors/failures, individual curves, actual endpoint and plateau reason. Confirm
   optimizer-state/absolute-round continuity, budgets and source/worker isolation. Repeated
   development checks are not independent holdout seeds. No automatic base-readiness claim.
2. **Respond to the evidence.** Continue a measured positive trend only under another declared
   finite plan. If improvement stalls, prioritize action-credit or qualified actual-engine teachers;
   do not blindly scale the same recipe. No arbitrary HP rewards or permanent action masks.
3. **Full readiness before adaptive thinking.** Establish full wins and policy/value/calibration/
   search quality. GA/direct evolution and other difficulties remain deferred.

The prior confirmation remains preserved: 256 clean attempts, originals **7.2890625** versus
trained **8.859375** mean floor; paired gain **1.5703125**, 95% seed-bootstrap interval
**[0.9296875, 2.2265625]**. Both players improve; 66 pairs higher, 34 tied, 28 lower. Still zero
full wins / completed acts in that confirmation, trained best floor 17. It supports testing this
finite continuation, not strong play or population-level algorithm superiority. See
[fresh confirmation result](native-policy-confirmation-result.md). Original optimizer study and
completed-TRAIN diagnostic remain intact. No push or GitHub Actions; #143/#35/#146 remain open.

### Preserved optimizer preparation and parallel diagnostic (completed above)

**Parallel saved-record diagnostic complete; owner reports the learning curve running.**
The new tool analyzes only the two completed historical TRAIN cohorts: 64 games / 6,995
records, in 45.81 seconds / 291.23 MB, with zero games, policy updates or running-record reads.
All 36 protected experiment files remain unchanged. Reopening its sealed result reuses it.
Mandatory menus are 24.3% of records, but excluding them from advantage normalization alone
changes the sign on only 9/5,297 real choices. Combat supplies 75.2% of real choices; rest sites
only 19 and shops 88. Card skipping occurs 30/181 times; end turns with plays remaining are
39/1,254 chosen end turns. These are observed behaviors, not proven mistakes or optimal actions.
The actor changes probabilities on saved inputs; useful new-game learning is still unproven.
[Method and first interpretation](native-completed-training-diagnostics.md) /
[evidence](evidence/native-completed-training-diagnostics-v1.json). No new owner command or
additional learning gate is introduced. Complete the current comparison unchanged; then assess
its fresh results before choosing a credit/teacher change. Do not tune the running recipe.

**Optimizer study and compact learning-curve runner implemented; owner comparison awaiting results
(#143 / #35 / #146).** The previous input comparison remains flat: original combined mean floor
7.1250→6.9375, crossed 7.1250→7.1250; both 0/32 final wins over two numerical replicates.
Its 46 units / 288 new games and historical results are unchanged. Useful native learning,
full wins and base/adaptive readiness remain unproven.

A frozen TRAIN-only study reuses two clean 32-game first-round cohorts. Standard updates exactly
reproduce both historical model IDs. Nine passes fit the assigned in-sample training signal
2.4–2.6× more than three passes; higher-rate fits are also preserved. None reaches the existing
per-update KL cap. Separate 16-game halves suggest weakly related directions (cosine −0.1019 and
+0.0057); these single-split diagnostics do not establish causality, optimal batch size or stronger
play. Study: 88.42 s, 723 MB peak RAM, 825 numerical updates, zero new games or promotions.

Compact sparse inputs preserve float64 values, loss, gradients, credit, model weights and complete
Adam state. A saved 32-game batch exactly reproduces its historical model after 81 updates with
about 168 MB additional preparation memory. The short native control passes 8/8 games / 24 updates
across three launches: 54.45 s, 681 MB peak RAM, 11.55 MB output, zero failures or app copies. Its
two-game batches prove integration and resumption, not actual 128-game memory or learning quality.

**One next owner command:** `bash scripts/train-native-a8-optimizer-v1.sh`.
Close the Steam game. Expected 2–3 hours; three-hour invocation budget, two workers, 4 GB RAM,
6 GB retained output. Clean 15-minute sessions continue within the same finite plan; failed/capped
sessions stop without automatic retries. The same command resumes a clean pause and verifies
complete results on repeat. Required complete repository checks precede any game collection.
The owner reports this comparison running; Codex has not launched or monitored it.
[Protocol](native-optimizer-learning.md) /
[evidence](evidence/native-optimizer-learning-v1.json).

Ordered remaining work:

1. **Assess the frozen learning curve, owner-run:** standard 32-game batches / three passes versus
   candidate 128-game batches / up to nine passes. Each player gets 512 fresh training games;
   two new numerical initializers, paired seed plans, 16 reserved development games at
   0/128/256/384/512. Total 2,368 attempts, 340 sealed units. This deliberately bundles larger
   independent batches and reuse, has equal game budgets but different fitting compute, and
   cannot attribute a gain to either component alone. Final-only comparison; no promotion.
2. **Improve action credit if fresh play remains flat:** stop at the fixed horizon; do not
   automatically extend unchanged PPO. Test better return/action-value estimates or qualified
   search/demonstration lessons. The earlier full-trace score timing change was numerically
   identical; arbitrary HP bonuses are not a repair. Diagnose noise versus fitting with saved
   evidence before changing the objective or adding restrictions.
3. **Better lessons and practice:** qualify actual-engine action branches before fixed-budget
   search/demonstrations become teachers. Keep hidden information out of policy inputs, quantify
   label noise and retain full-run A8 evaluation. Saved diagnostic fits are not fresh PPO data.
4. **Scale only after repeatable progress:** confirm a promising method on fresh seeds, then
   justify larger owner-run learning curves. Count games, decisions, updates, failures and CPU
   separately. The current two-replicate development comparison cannot certify strong win rate.

Keep fixed Ironclad/A8, all public legal choices, the declared floor/act bootstrap score and
primary terminal-victory objective. No arbitrary health rewards, permanent action restrictions,
automatic adaptive thinking or difficulty expansion. GA/direct evolution remains a separate
later comparison. Shared frozen game/runtime/SDK/support code are reused with isolated workers;
no app copies. Interrupted prefixes remain diagnostic only; original denominators and historical
source/config/result bytes stay preserved. #143/#35/#146 remain open. Full repository checks are
required before a local commit; no push or GitHub Actions is needed.

### Preserved completed input comparison

**Comparison complete; useful native learning remains unproven (#143 / #35 / #146).**
The fresh matched pair finishes all 46 units / 288 new games, with zero failed games and no app
copies. Both successful sessions total 861.35 seconds (14 min 21 s), peak RAM 1.07 GB and new-workspace
storage 280.21 MB. One refused launch while Steam's game was open is retained separately. There is
no pending owner command for this completed comparison; rerunning its launcher only verifies it.

| Method, two numerical seeds | Initial mean floor | Final mean floor | Final wins |
| --- | ---: | ---: | ---: |
| Original encoding | 7.1250 | 6.9375 | 0/32 |
| Public numeric-by-candidate features | 7.1250 | 7.1250 | 0/32 |

The crossed method is ahead by only 0.1875 floor in each replicate and has no aggregate improvement
over its own initializer. Both methods improve slightly in replicate 0 and regress in replicate 1.
These are exploratory development results, not a significance claim or a useful base player. Each
player has only 128 training games; the result does not prove more data cannot help. Preserve the
successful synthetic control as synthetic evidence, without claiming it fixed actual-game learning.

A read-only assessment verifies all 46 unit receipts / 5,567 source seals and reconstructs the
reported comparison. It launches no games and performs no fitting. All fresh fits reach their epoch
limit, gradients are nonzero and policies change: these records do not support a completely frozen
optimizer. They also do not establish that larger steps or more epochs improve gameplay.
[Results and method](native-context-restart.md) / [evidence](evidence/native-context-comparison-v2.json).

The old 640-game attempt and its 520 sealed games remain unchanged: 496 closed audited games,
24 interrupted-prefix games excluded from PPO, and 120 original slots without sealed headers.
The primary completed comparison uses the old seed-0 pair, the 32 verified old seed-1 starting
panels and the fresh matched seed-1 pair. The extra old seed-1 baseline stays diagnostic. No unsafe
worker/profile reset, uncertain seed replay, checkpoint promotion or readiness/adaptive pass occurs.

Ordered remaining work:

1. **Optimizer efficiency, next implementation:** reconstruct the saved TRAIN-only batches and
   measure probability movement against their assigned advantages, losses and independent-game
   gradient evidence. Compare predeclared step sizes or update counts with matched initialization,
   game budget and whole-game ordering. Numerical fitting success is not stronger play. Use new
   reserved development seeds for the next frozen native experiment; do not tune on these final
   panels. Record every attempted setting and actual work. Leave long experiments owner-run.
2. **Action credit:** if updates fit their noisy lessons without improving independent play, test
   better return/action-value estimates and narrower credit only when prediction evidence supports
   them. Moving the same score earlier under full-trace credit already leaves the update unchanged.
3. **Better lessons and practice:** qualify actual-engine action branches before fixed-budget
   search/demonstrations become teachers. Keep hidden information out of policy inputs, quantify
   label noise and retain full-run A8 evaluation. Separate supervised studies from ordinary PPO.
4. **Measured scaling:** use owner-run learning curves and larger independent batches after the
   next bounded check, with a declared stop/plateau rule. More games are a testable intervention,
   not an assumed cure. Count games, decisions, updates, failures and CPU separately.

Keep fixed Ironclad/A8, the declared floor/act bootstrap score and primary terminal-victory
objective. No arbitrary health rewards, permanent action restrictions, automatic adaptive thinking
or difficulty expansion. GA/direct evolution remains a separate deferred comparison. The cache,
restart mechanism, short control and native comparison work are complete; broader learning issues
remain open. Run the full repository check before committing changes; no push/Actions is needed.

### Preserved restart preparation (completed above)

**Implemented: immutable model-ID cache and restartable comparison; owner fresh matched pair next
(#143 / #35 / #146).** The original one-hour attempt did not complete. Keep the declared floor/act
bootstrap score, terminal-victory evaluation, all legal choices and existing PPO settings unchanged.
No health rewards, action masks or adaptive controller are added. Stronger native play is unproven.

The old 640-game plan retains **520 sealed games**: 496 in closed audited panels, 24 in interrupted
workers (diagnostic only), and 120 original slots without sealed headers. Unsealed attempt count is
unknown. Its capped report's zero exit code is not experiment completion. Original and crossed
seed-0 players change mean floor 6.4375→6.5625 and 6.4375→6.7500; the extra old baseline seed-1
changes 7.8125→7.2500. All have zero wins in their 16-game final development panels. This is weak,
exploratory evidence, not success of the synthetic repair in the actual game.

The owner chose a **fresh matched seed-1 pair**. Preserve the completed seed-0 pair in the primary
comparison and the old extra baseline as diagnostic evidence. Reuse both verified seed-1 starting
panels (32 games), including reconstruction of saved behavior probabilities. Collect 128 fresh TRAIN
seeds per method, paired across methods and disjoint from legacy TRAIN/uncertain seeds, then 16 final
reserved development games each: **288 new games**. Never admit the interrupted prefix as PPO data.
The primary comparison has two numerical replicates, with final-only evaluation and no promotion.

IDs, serialized models, probabilities and draws are unchanged by the cache; new weights get a new
cache. Saved-decision processing is 5.10–6.76× faster in a small profile, not a whole-game speed claim.
The new runner commits eight-game collections and complete model/Adam checkpoints separately; the
training batch remains 32, with historical two-lane ordering restored before deterministic fitting.
Each launch lasts at most 15 minutes, two workers, 4 GB RAM / 4 GB new-workspace cap. Pauses happen
between committed units. Abruptly interrupted units remain preserved and require inspection; no seed
replay, profile clearing or pretending partial work is complete. The two-failure allowance applies to
an entire logical round/evaluation. Shared frozen game inputs/cache are reused; no app copies.

The short native restart control passes **8/8 games, 12 updates**, across three launches paused after
units 3 and 6: **63.04 total resource-tracked seconds / 697.30 MB** peak RAM, no failures or shared-input
changes. Reopening it performs no new games or updates. A read-only import seals every historical
file and verifies saved models, case/trace seals, worker audits and stopped interrupted processes.
Targeted checks plus repository lint/types pass; the complete release check is still pending.
[Protocol, evidence and limits](native-context-restart.md). Historical pinned sources stay unchanged.

**One next owner command:** `bash scripts/continue-native-a8-context-v2.sh`.
It first runs the required full repository checks (about 5–6 minutes, ten-minute cap), then one bounded
comparison session if they pass. Reuse the same command after a clean pause; completed collections,
fits, Adam state and the exact-file release-check receipt are verified and reused. The long comparison
has **not** been launched. No commit/push or GitHub Actions run before the complete check passes.

Ordered remaining work:

1. **Representation and execution repairs, implemented:** the earlier synthetic context-by-action
   control passes 3/3 seeds (68.68–69.32% versus 48.07–54.26%, 70% optimum). Its native bridge/projection
   and this cache/restart control pass. Synthetic learning and plumbing are not native strength.
2. **Finish and assess the controlled native comparison:** owner runs the new fresh-pair command.
   Compare paired final-minus-initial floors, terminal wins, failures and actual optimizer work;
   preserve the original interruption and the extra unpaired baseline. Do not select on final panels.
3. **Optimizer efficiency:** if the method remains flat, bounded tests of initialization, learning
   rate and updates per collected game; retain every attempted setting and negative control.
4. **Earlier action credit:** improve action-value/return estimates when prediction evidence supports
   them. Moving the same score earlier with full-trace credit already leaves the update unchanged;
   no arbitrary HP rewards. The previous improved baseline did not establish better gameplay.
5. **Better lessons and practice:** qualify actual-engine action branches before fixed-budget search
   or demonstrations become teachers. Keep hidden information out of policy inputs and preserve
   full-run A8 evaluation. Recovered/stale episodes may serve separate supervised studies, not PPO.
6. **Measured scaling:** after repeatable improvement, owner-run thousands-game learning curves and
   larger budgets if justified. Count games, decisions, updates, failures and CPU separately.

Selectable difficulties, larger unchanged GA and adaptive thinking remain deferred. The complete
repository check followed by a bounded fresh-pair session is the sole pending owner command.

### Preserved conditional comparison (interaction follow-up now being implemented)

**Direct teaching versus PPO implemented and assessed (#35 / #146): conditional learning remains weak.**
The same synthetic HP task, initial numerical weights, public inputs and actual optimizer
work are paired across three seeds. Each primary method uses 288 updates / 36,864 decision
presentations / 6,144 choice presentations. PPO receives terminal outcomes only; the
teacher gets separate oracle action labels. All three PPO final IDs/evaluations exactly
reproduce the historical control. Frozen-actor and missing-HP controls pass. All 96 round
records / 99 round-and-pair file seals verify. No native input or checkpoint is opened.

Neither method meets the frozen learning criterion in any seed. The teacher's expected
victory is 51.49–51.66% against a 70% optimum; it learns a small HP-dependent preference.
One seed has 100% greedy accuracy but only about 50–52% optimal-action probabilities,
well below the 75% criterion. This does not prove inadequate model capacity or a unique
PPO defect. It shows that sampled reward noise alone does not explain this control's gap.
The comparison completes in **37.43 seconds / 166.07 MB** peak RAM, retaining 1.56 MB,
with 6,144 sampled synthetic episodes / 2,052 synthetic updates including controls;
zero native games, production updates, app copies or promotions.

The initialization probe retains HP correctly, but the shared linear context cancels
between these candidate scores. The hidden branch's conditional-contrast gradient norm
is only 0.027–0.040% of the ordinary preference gradient norm. This is a local sensitivity
measurement, not an Adam speed ratio or proof of native causality. **Next implementation:**
a finite, separately versioned public context-by-candidate interaction control at the same
network size and controlled work/initial policies. Test this measured representation gap
before another native learning change; do not retune or extend the completed comparison.
[Method, results and limits](native-conditional-teaching.md). No owner command is pending.
Stronger play, full wins and base/adaptive readiness remain unmet.

### Preserved recovered-pool result (conditional comparison now complete)

**Recovered-pool analysis complete (#35 / #146); larger batches alone are not an established repair.**
The owner analysis finishes in **114.20 seconds / 3.917 GB** peak RAM with no cap, no new
games, optimizer steps or app copies. All 256 diagnostic games' saved likelihoods verify;
the independent numerical gradient reference passes on four games / 549 decisions only.
A separate saved-result check verifies 596 source seals and recomputes recorded partition
summaries without differentiating again. [Results, evidence and limits](native-a8-recovered-gradient-result.md).

At 32 / 64 / 128 games per disjoint group, median game-driven direction agreement is
-0.017 / +0.020 / +0.061, with 53.1% / 50.0% / 37.5% opposing pairs. Agreement remains
near zero; the trend is not uniformly improving. Including exploration at 128 games gives
-0.093 median agreement and 65.6% opposing pairs. Its full-pool norm is 35.8% of the
game-driven norm; this does not prove domination or a cause of weak learning. Partitions
reuse one finite frozen-player pool, not independent training replications. No optimal
batch size, actual learning benefit or impossibility of improvement is established.

**Completed follow-up above:** a bounded direct-teaching versus PPO conditional-HP control on
the same public inputs, with matched/reportable actual optimizer work and all attempted
settings preserved. The earlier learner misses the conditional rule while learning a
constant delayed choice; distinguish available capacity/optimization from reward-driven
conditioning before another native training change. This is a short synthetic diagnostic,
not a new mechanics gate. No owner command is pending. Stronger play, full wins and
base/adaptive readiness remain unmet; no larger unchanged PPO/GA or difficulty work follows.

### Preserved memory-repair handoff (analysis now complete)

**Memory repair and diagnostic recovery complete (#35 / #146).**
The owner collection hit its 4 GB RAM cap in 399.52 seconds. It saved 254 terminal records,
left seed 700253 interrupted and 700255 unstarted, and produced no final audit/summary.
The old collector retained full histories and its auditor loaded whole journals. The
new streaming implementation retains sealed paths/compact outcomes, releases each trace,
and verifies logs in order. Historical pinned sources and the original failure remain.

All 254 saved delivery/ending chains now verify in **25.15 seconds / 116.33 MB** peak RAM,
with zero replays, marker edits or worker reuse. Four repeated-control-seed games pass
the new collector/auditor and exact numerical reference; two short workers complete only
the unstarted 700255 and explicitly added fresh 700257. Seed 700253 is never retried.
The union contains **256 clean diagnostic games from 257 actual diagnostic attempts**;
the original interruption stays counted. Four control starts are separate. The old
collection is not relabelled clean, and recovered inputs are not ordinary PPO admission.
Mixed-origin saved verification passes on two recovered/two new games, 422 decisions.
No optimizer steps, promotions or app copies; the full native 256-game collection was not replayed.

**Completed owner command:** `bash scripts/analyze-native-a8-recovered-pool-v1.sh` from the repository.
Saved-data analysis only; up to ten minutes, one numerical thread, 8 GB memory, 2 GB output.
It is complete; its wrapper now shows saved results. Do not rerun/clear the capped
folder. [Recovery, measurements and accounting](native-a8-memory-recovery.md).
The full-pool findings are assessed above. The toy conditional-learning follow-up is next;
stronger play and base/adaptive readiness
remain unmet. No new action masks, model changes, larger GA or difficulty work is added.

### Preserved synthetic-control and earlier batch handoffs

**Synthetic end-to-end learning controls implemented and assessed (#35 / #146).**
The unchanged native numerical learner runs three tiny known-solution tasks, three training
seeds each, using fresh sampled binary terminal outcomes and no supervised action labels.
The delayed task learns from about 7.6% to 99.3–99.6% expected victory in all three seeds.
Immediate choice improves to 46.3–50.9% but misses the frozen 75% action-probability criterion;
it receives only 96 optimizer steps, versus 288 with continuation menus. Contextual risk
stays at 48.1–54.2%, below its 70% optimum; every final greedy player makes the same choice
at both HP levels. Frozen-actor and missing-HP negative controls behave as expected.
The overall learning check **does not pass**. This is not native skill/readiness evidence
or proof of a unique causal defect. Preserve the result; do not tune the frozen experiment
or increase its budget just to get a pass. [Method, measurements and limits](native-ppo-known-task-controls.md).

The control finishes in 34.09 seconds, 121.37 MB peak RAM and 4.11 MB retained output:
18,688 synthetic episodes / 2,052 synthetic updates, zero real games or production updates.
All 24 Python inputs pinned by the owner's running gradient study remain unchanged.
At that point the owner reported the larger pool running; Codex did not monitor it.
Its later capped outcome and recovery are assessed above; that handoff supersedes the
historical batch command below.
Independent next follow-up: a bounded direct-teaching-versus-PPO conditional control on the
same synthetic inputs, matching/reporting optimizer work and preserving every attempted
setting. Assess the larger pool before freezing any new native training comparison.

**Independent-game gradient and batch-size checks are implemented and pass (#35 / #146).**
The study reconstructs the production actor gradient at behavior to at most 2.15e-16 error,
including the full cross-fitted return baseline, all menus, normalization and entropy. Four
separate 32-game TRAIN cohorts verify 128 trajectories / 12,741 decisions from 64 native seeds;
cohorts/models are never pooled. No reserved evaluation episode is opened, no actor is updated.

Every pair uses disjoint games, separately fitted predictors and its own advantage moments.
Repeated partitions are correlated finite-pool descriptions, not independent replications.
At 16 games/group, median game-driven cosine is 0.200 / 0.039 / -0.035 / 0.322 for unscaled
rounds 1/8 and normalized rounds 1/8; opposing pairs range 12.5–53.1%. The full-batch entropy
term is 3.53–9.77% of the data-gradient norm and does not dominate these initial gradients.
These observations do not identify the best batch size or prove a cause of weak gameplay.
The saved-only study takes 58.01 seconds and 1.150 GB peak memory. Sizes 32/64/128 per independent
group remain unmeasured because the saved pool contains only 32 games per behavior model.

**Historical owner command:** `bash scripts/check-native-a8-batch-sizes-v1.sh` from the repository.
It collects 256 fresh TRAIN games with one frozen normalized pre-round-eight model, then
compares genuinely disjoint 32/64/128-game groups. This player is fixed by training phase,
not chosen from development rankings. It never updates/promotes a player. Expected 15–25
minutes; collection cap 20 minutes / two workers / 4 GB RAM, analysis cap 10 minutes / one
worker / 8 GB RAM, 2 GB retained-output cap per stage. One shared frozen game/code cache;
zero app copies. It reports batch progress, preserves source failures and requires every
planned clean game for analysis. The collection later hit its RAM cap; use the recovery above.

The four-game / 360-decision native collector/analysis control passes with zero failures,
missing games, optimizer steps or protected-input changes. A memory bound retains sparse
menus for only four numeric reference games while verifying behavior and retaining derivatives
for every game. The v1 control/preparation stays preserved; the launch script selects v2.
These four control seeds repeat across the two short source versions, not eight independent
outcomes. Collection control and preflight pass. [Method, evidence, caps and exact command](native-a8-independent-gradients.md).
Strong-base readiness, full wins and adaptive thinking remain unmet. After the larger pool,
freeze an equal-game-budget learning comparison only if the TRAIN evidence justifies it.

### Preserved completed normalization comparison

**The owner-run normalization comparison is complete: numerical conditioning improves,
but stronger play remains unproven (#143 / #146 / #35).** Both methods finish 336/336 normal
endings: 672 total, zero failed/missing games, wins, completed acts or app copies. On the
same 16 fresh development seeds, the unscaled player rises from 6.5 to 7.25 average floors;
normalized rises from 6.5 to 7.0625. Both gain intervals include zero. Normalized-minus-unscaled
is -0.1875 floors, interval [-1.625, +0.875]; its nonlinear auxiliary score is slightly higher,
also uncertain. No demonstrated superiority, inferiority or equivalence; one training replicate
per method. Both real round-eight trained models were frozen on confirmation before evaluation.

Normalization remains at **0% saturation in all recorded before/after training probes**;
unscaled reaches **52.36%** after round eight. The saved-only assessment reconstructs all probes
and verifies 672 episodes, 67,963 decisions and 2,878 source files in 33.62 seconds. Actual work
is 25,917 / 25,883 TRAIN decisions and 615 / 618 updates; identical collection rules are not
identical realized work. Owner runtime is 32.16 minutes combined; 599.37 MB retained, peak
memory 1.976 GB, protected inputs unchanged. See [results and limits](native-a8-normalization-comparison-result.md).

**Follow-up implemented above: #35's independent-run gradient/batch-size controls**, beginning with bounded
saved-TRAIN checks of whether different complete games recommend consistent changes. Do not
pool rounds from different behavior policies, count correlated decisions as independent games,
or treat resampling as new evidence. A justified larger-batch comparison must fix total games,
score and method, use fresh reserved evaluation seeds and report actual work. The owner
frozen-pool command above is now prepared. Keep both candidates/results frozen; do not promote or
choose normalization from this inspected development panel. Base readiness/adaptive thinking
remain unmet. #143's normalization ablation is complete under this finite scope; broader
representation changes need a demonstrated gap, not another saturation-only test.

### Preserved normalization launch handoff (completed)

**Input-normalization checks and native integration pass (#143 / #146).**
The explicit `native-actor-hash-quarter-v1` transform scales hashed actor coordinates by 0.25,
preserving direct action signals, critic inputs, all actions and every existing encoded fact.
All 278 sampled TRAIN states / 1,175 candidate vectors recover exactly; zero new aliases.
With old round-8 weights, probe saturation falls from 21.48% overall / 66.70% in combat to zero;
this is a sensitivity result, not a newly trained player. Artificial conditional learning passes
on 28 examples from 14 held TRAIN games; removing HP information gives chance performance.
A coherent three-view HP supplement also passes. Both four-game native controls pass, with
456 verified training decisions / 12 updates, zero failures or app copies. The unscaled
checkpoint exactly reproduces its prior control. Legacy model identities remain intact.

**Completed owner command:** `bash scripts/compare-native-a8-normalization-v1.sh` from the repository.
One scaling factor changes; both methods keep the cross-fitted credit estimator and all other
training settings. Each has 336 attempts, 672 total, run sequentially; expected 25–40 minutes,
30-minute cap per method. Fresh confirmation/development seeds, each method's own initializer
and best trained player, plus per-update saturation measurements. Admissions/preflight pass;
both methods have now completed. See [the original checks, limits and launch command](native-a8-input-normalization.md).

### Preserved completed credit experiment

**The owner-run credit comparison is complete: no clear gameplay gain (#35 / #146).**
Both methods finish 336/336 ordinary endings: 672 attempts total, zero failures, missing games,
wins, completed acts or app copies. On the same 16 independent development seeds, both trained
players average **7.1875 floors**, versus **7.0625 initially**. Their +0.125-floor differences
have paired intervals including zero. The new predictor improves its training return estimates,
but this does not establish a better policy. Best-trained checkpoints were actually evaluated;
neither comparison silently repeated the initializer. All 64 shared initial-policy traces match.
The saved-only audit checks every episode, 68,929 decisions and 2,866 files without new play.
See [the results and limitations](native-a8-credit-comparison-result.md).

**Follow-up now implemented above:** #143's short saved-TRAIN normalization and conditional
controls preserve public entity/amount relations and every legal action family. No fields are
deduplicated by this scaling treatment. #35's independent-run batch-size/gradient-agreement
control remains important; lower prediction error alone does not justify short-trace GAE or
a larger unchanged run. Both the credit comparison and the scaling comparison above are now
complete. Base readiness/adaptive thinking remain unmet.

### Preserved pre-comparison handoff

**Native A8 pilot v5 completed reliably but retained no trained improvement (#146 / #143).**
All 336 attempts ended normally: zero failures, missing games, wins or completed acts. It ran
eight training rounds, 627 updates and 26,061 verified training decisions in 14.82 minutes,
retaining 300 MB with zero app copies. All unchanged-input checks passed. Worker v9 and host
v34's cache/queued-discard repairs worked throughout this panel.

The starting player scored 7.5625 average floors on confirmation seeds; checkpoints after
rounds four and eight scored 6.8125 and 7.1875. Both also lost under the exact declared auxiliary
score. Selection correctly retained the initializer. The final two development panels therefore
used the same original player and RNG, each averaging 7.375 floors. They do not independently
evaluate a trained checkpoint. The best recorded game reached floor 17. The saved-only audit
verified every case and 1,427 source files; no games or updates followed.

**Diagnosis completed; next is a controlled learning repair (#35 / #143 / #146 / #134).**
The critic increases choice-bearing target variance in six of seven rounds after its first fit;
round-8 actor-gradient trace variance is 18.5% above a centered-constant reference. Thirty-two
independent runs per update produce weakly agreeing gradients; 26,061 decisions are only 256
whole-run outcome lessons. A sampled combat probe shows hidden saturation rising from 10.2%
to 58.9%, but no exact candidate-vector aliases and little hard clipping. Both initial/trained
networks learn an artificial HP-conditioned rest choice on 18 held-aside training examples.
Gradient derivatives pass real-state checks. No unique causal explanation or native ablation
is claimed. See [the measured diagnosis](native-a8-pilot-v5-learning-diagnosis.md).

**Historical pre-comparison state: value/credit implementation complete (#35 / #146).**
The integer-zero optimizer edge case is fixed. A small public-state predictor is cross-fitted
by whole games, with equal-game fitting weights and no self-outcome leakage. Using only v5's
256 TRAIN runs, its later-round squared error is 31.7% below a fitted constant and 61.6% below
the old critic; it improves all four audit rounds. Gradient agreement improves in round 1 but
worsens in round 8, so lower prediction error is not yet a demonstrated learning improvement.
Objective-preserving credit telescopes on all saved runs; lambda=1 recovers the original
return-minus-value credit exactly. Shorter-trace GAE stays disabled. Both new four-game pipeline
controls and saved-credit reconstruction pass, with zero failures or app copies.

**Completed owner command:** `bash scripts/compare-native-a8-credit-v1.sh` from the repository.
This is a matched old/new credit comparison: 672 planned attempts, two sequential methods,
the same actor/training seeds/RNG/score/update budget, and fresh confirmation/development seeds.
Both explicitly evaluate the best trained player, keeping the incumbent separate. Expect
25–40 minutes total; 30-minute cap per method. The owner has now finished both arms in 30.84
minutes. The [implementation guide](native-a8-value-credit.md) preserves the launch contract.

Remaining ordered work:
1. #35 / #146: completed comparison and saved outcome audit above; retain as exploratory evidence.
2. #143: test representation normalization/reduced duplication against saturation and conditional
   learning controls if needed after this one-factor comparison. Preserve every action family
   and public entity/amount relation; do not enlarge the model without demonstrated need.
3. #35 / #134: address remaining run-level gradient noise using measured independent-batch-size
   controls and/or shorter-trace credit only if value evidence supports it. Do not assume either
   method helps from prediction error alone. No larger unchanged PPO/GA, sweep or controller now.

All v5 sources, checkpoints, optimizer states and results remain preserved. Re-running its
training script only shows the saved result; both comparison methods are also now complete. V4 remains
stopped with five training rounds, 191 normal losses, one failure and 144 unplayed; do not
restart it under repaired sources. [Repair evidence](native-a8-worker-potion-repairs.md) and the
[v4 stop report](native-a8-pilot-v4-stop.md) retain the earlier chronology.

Base readiness and adaptive thinking remain unpassed. Patch transfer, other difficulties and
larger unchanged GA/PPO batches stay later work.

### Preserved pre-v4 handoff

The finite native mechanics package was completed under its declared scope (#148).
Host v33 supports all five AnyTime potions outside combat, exact real/fake merchant targets for
Foul Potion, inventory open/close and current-slot discard. Native effects and game rules remain
in the original DLL. Twenty-five potion controls, two merchant purchase/exit checks, new lifecycle
fixtures and a 12-game isolated worker panel pass with zero app copies.

The composed gate retains the **host-v32** 1,849-case sweep and its true scope, rechecks saved
hashes, binds the reviewed presentation delta and requires new controls. A first short greedy
learning check failed on legal loops and stays preserved. Merchant inspection now reaches the
learner's public memory; the new explicitly stochastic control passes **4/4 games, 228 verified
training decisions and six updates**. Fixed evaluation RNG streams are shared across checkpoints;
every action remains selectable. These are four losses and pipeline evidence, not stronger play.

**Earlier handoff, superseded by the stopped result above:** let the pilot finish, then use the
[saved-only assessment](native-a8-pilot-assessment.md). Pilot v4 starts from the original seeded
network and zero optimizer state: eight rounds, 336 planned games, independent development
evaluation and bounded failed-worker continuation. The assessment checks ownership, ending
evidence and the original confirmation selection, reports paired uncertainty, and keeps failed
games in the denominator with zero progress in the main comparison. It reads no partial games
before the final summary and launches nothing. No live results were inspected during its
implementation; all pinned pilot inputs remain unchanged. A historical v3 regression reproduces
its inconclusive result. Assess generalization and failure types before scaling; restore
greedy-quality checks before base readiness. Adaptive thinking, cross-patch work and larger GA
batches stay later.

### Preserved earlier milestones

**The actual-engine v3 pilot and first mechanics sweep are complete (#148 / #146, 2026-10-15).**
The owner finished all 336 attempts: **332 normal endings, four failures, 627 PPO updates and
26,416 verified sampled training decisions**. There are no wins. Independent average floor is
8.75 selected versus 7.4375 initial (8.625 selected with its failed game scored zero); the paired
interval includes zero. Preserve every checkpoint, the four failures and the inspected development
panel. This is inconclusive quality evidence, not base readiness or permission to scale blindly.

The new private inventory joins all **1,660 native model types** without missing/extra classes.
Host v31 and public combat v3 remove hero-only resource assumptions, preserve foreign orbs,
companions and current star costs, and fix reentrant choices plus reward-to-bundle waiting.
The owner finished **1,824/1,824 contexts** in **44 minutes**: 1,691 native effects,
83 observed prerequisite blocks and 50 failures. The failures share three causes: 45 disabled
multiplayer-card geometry checks, three invalid uninitialized Mad Science fixtures, and two
Particle Wall plays incorrectly marked undelivered after returning to hand. Original results stay
unchanged. Host v32/public combat v4 repair these causes; native Tinker Time previews supply nine
valid card forms, and exact new manual-play history confirms return-to-hand delivery. The expanded
plan has **1,849 cases**, including a same-card repeat check. Shared frozen inputs/cache created
zero apps and retained about **357 MB** for the original sweep.

**The repaired controls pass 90/90:** 44 effects and 46 native prerequisite blocks, zero failures,
127.81 seconds, 19.08 MB retained evidence. Same physical Particle Wall replay and nine distinct
configured card forms verify. All original and repaired case hashes verify; 1,339 repository tests
and 19 focused new Node checks pass.

**The repaired sweep passes 1,849/1,849 checks:** 1,721 native effects, 128 observed prerequisite
blocks and zero failures/unattempted cases. All saved case hashes and the original denominator
verify. The owner finished it in **45m30s**, retaining **353.07 MB**, with **379.31 MB** peak memory
and zero app copies. The original failed sweep remains preserved.

**The [short follow-ups](actual-engine-mechanics-followups.md) also pass.** Codex ran all nine
random-action games: **522 decisions**, nine observed decision families, zero interface failures
or truncations, and an identical exact-repeat trace. Skip and offered shop choices were exercised.
Privileged act-transition/Architect/zero-HP-victory fixtures pass on the same v32 build; these
are zero player wins and zero PPO examples. Combined wall time **33.83s**, peak memory
**302.87 MB**, retained evidence **7.20 MB**, zero app copies. Saved-only verification passes.
The earlier blocked launch reports remain intact. [Current evidence](evidence/actual-engine-mechanics-sweep-and-followups-v1.json)
binds the sweep, follow-ups, native build and resources.

**Historical pre-potion handoff, now completed above:** outside-combat potion controls and
Foul Potion's merchant target were the remaining declared requirements. Do not repeat completed
batches, reinterpret random play as model quality or automatically migrate old models.
Strong-base readiness still comes before adaptive thinking.

The following paragraphs describe the earlier pre-potion handoff. Other cases continue only after a failed worker is proved stopped; keep unsupported/prerequisite-
blocked/untested mechanics explicit. Resolve the remaining potion requirements before a new
environment/worker/neural admission.
The new all-pool path has a coverage gate; historical pilot results are not retroactively upgraded.
The earlier v1/v2 stops and their event-presentation repairs remain preserved.

**The owner's repaired second seed is complete (#145).** It plays **104 actions** and ends in a
native **loss on floor 5**, with no unsupported states, recovery, delivery failures or caps.
Its saved trace and shared-app reset verify. Together with the original first seed's **144-action,
floor-6 loss**, we have two independent naturally played shipped endings. They use explicitly
recorded diagnostic policy revisions; this is environment evidence, not a common-policy strength
estimate. The old repeated-card-offer failure remains unchanged. The old command now audits saved
results; no new game is required.

**Targeted later-act, victory and cleanup handling is implemented.** Native v22–v24 restore missing
graphics/call bindings and the absent test-mode audio service used by a boss death hook, retaining
the original game rules DLL. A new explicit cleanup gate catches shutdown failures.
A separately marked fixture reaches all three transitions through native Proceed and the final
Architect dialogue. The shipped app verifies Act 1→2 and Act 2→3, including the fresh map tutorial.
A saved-only supplemental audit verifies the already played final sequence through explicit win;
its original batch still records the JSON key-order verifier failure. Zero HP alone is not loss,
and entering the Architect's victory room alone is not yet a completed win.

All targeted app checks reuse the same app/inode with fresh profiles, zero new copies and verified
reset. Forced boss defeats are privileged fixtures: **zero player victories and zero learning
examples**. Imported boss saves re-offer rewards, so these checks compare act targets/endings,
not full reward/RNG resume parity. Unknown states, missing fields and uncertain delivery remain
failures. [Current evidence](evidence/actual-engine-v0.111.0-progression-v1.json) retains the owner
result, new repairs, passing checks and every preceding failed diagnostic.

**The current native regression passes 8/8 clean endings and shutdowns:** 775 decisions across
10 decision families, 25.855 seconds of summed case wall time, zero failed/unattempted cases or
new app copies. One saved successful case is reused and seven new games finish in the final
collection. All are losses; the old v21 1,115-decision/15-family panel stays separate. A capped
v23 cleanup failure and a private collector error remain preserved.

**The temporary target-ID bug is fixed (#146).** New diagnostic policy v5 and the actual-engine
public entity graph replace runtime handles with visible local occurrences and retain target
HP/statuses/intents, ownership and per-copy facts. All **783 saved observations** pass **2,349**
renaming comparisons. Old helpers, recipes and results remain unchanged. The weak diagnostic
initializer's historical floor differences were not learned-model comparisons.

**Worker isolation and the neural connection now pass.** The final versioned panel completes
**12/12 games and 1,214 decisions**, including eight serial seeds and two parallel workers each
repeating its seed after reset. Semantic traces match; profiles/processes are separate, sibling
profile access is denied, protected inputs stay unchanged and shutdown verifies. It takes
**19.07 seconds including the resource wrapper**, retains **66.57 MB**, and creates **zero app
copies**. Earlier startup/sandbox/controller failures stay preserved and are not admitted.

The final actual-engine learning control completes **four games**, verifies **209 sampled
decisions**, applies **six PPO updates**, changes both actor and critic, reloads the checkpoint
and checks saved public input/action/delivery/ending chains. Its two greedy control games reach
floors 17 and 14; **all four games are losses**. Their different seeds/behaviors do not establish
improvement. The workflow reuses the tested PPO mathematics with a new public encoder and model;
no old v0.107.1 input or trained weights are silently migrated. Every decision family remains
learnable, including Skip and public memory of previously declined offers.

**The v3 neural pilot is now historical, not the next command.** Its finite learning and
independent comparison are complete. Use the coverage guide for the current owner handoff.
Strong-base readiness and adaptive thinking remain unpassed. GA, other difficulties and patch
transfer remain later; a useful native checkpoint still needs its new schema connected to the
reused shipped-app runner before a neural UI demonstration.

**Current finish line:** [the bounded Ironclad/A8 contract](actual-engine-a8-finish-line.md)
supersedes the open-ended mechanics queue below. Build the complete unattended public-action
loop, qualify normal startup/later acts/endings and representative consequential interactions,
then complete an eight-seed natural-run panel. Normal deaths count as completed environment
tests; wins are not required for training admission. Known encountered gaps require repair.
During the bounded learning pilot, isolate newly failed games under the explicit two-per-panel
allowance without training on partial data; unknown delivery is never retried. Speed/isolation
and the short neural/PPO connection checks are complete. Exhaustive combinations,
every static mode reference, other heroes/difficulties and repeated fixture matrices are later
coverage work. Historical evidence below keeps its original scope.

**Current work: #146 owner pilot and assessment; #145's bounded Ironclad/A8 environment gate is complete.** The separately frozen v0.111.0 / `41cef1ea` game and #144 preservation are complete. Ironclad/A8 stays fixed;
full-run victory stays primary. Preserve all v0.107.1 archives, models, encoders and results.
[ADR 0005](decisions/0005-actual-engine-v0.111.0-qualification.md) orders public/mechanics
qualification, complete-run speed, then a separately versioned neural pilot. Emulator porting,
other difficulties and larger unchanged PPO/GA batches remain deferred.

## Historical qualification notes

**The v21 natural headless loop completes 8/8 candidate endings**, with zero unsupported states,
unknown actions, liveness failures or runtime errors in this frozen panel. It records **1,115
decisions across 15 decision families** and takes **28.813 seconds** in total case wall time,
including launches/integrity checks. All eight ordinary losses retain their original native death
evidence; no wins, later-act coverage, playing-strength claim or training admission follow.
Saved-only reconstruction verifies advertised actions, reads, delivery chains, counts and native
ending flags. Managed simulations share frozen inputs and create **zero app copies**.

The short diagnostics repaired native event text, per-card modifiers, generated-card selection
permissions, upgrade-preview text and missing Godot math APIs. Two fresh native builds reproduce.
The original game DLL remains unchanged; earlier failed and literal-seed runs stay preserved.
New seeds explicitly use the game's canonical `1`/`0` alphabet; old `I`/`O` runs are not relabeled.

**Two normal shipped starts pass** through Single Player/Standard/Embark, without imported runs.
Their initial deck, HP/resources, act, starting offers, A8 and seed match the native references.
The new Host also gets through **54 gameplay actions and two combats** before the short cap;
the exact Power-card tutorial and a partial-hand reshuffle are supported. A saved-only audit
reconstructs all five startup actions and 54 gameplay actions. This partial run has not reached
a shipped ending. One fixed app/inode is reused, with zero copies and verified reset.

**Historical owner stage:** `scripts/check-natural-a8-run-v1.sh` has the saved 73-action incomplete
attempt described above and now audits it without replay. Its original 15/16-minute caps, failures
and [foundation evidence](evidence/actual-engine-v0.111.0-natural-run-foundation-v1.json) stay unchanged.
The two-seed discovery command above supersedes that handoff; no old recipe is retried or relabeled.

**Remaining before the new neural pilot:** close the current-build environment checklist and
encountered public-input/selection omissions; measure bounded
worker isolation and whole-run costs; connect the new public experience/encoder to the existing
learner and pass a short learning control. Broader combinations and repeat matrices stay deferred.

**Completed profile stage:** the owner profile/description panel passes **8/8 cases**, zero failures or
unattempted cases. Four independent fixed-A8 seeds were each repeated twice with identical public
prefixes. Independent saved reconstruction verifies eight initial observations/Continue actions,
88 deck descriptions, 16 potion descriptions, eight relic descriptions and 24 starting options.
The native initial-context catalogue passes 1,517 descriptions per case, with one native mock
potion explicitly excluded. Overgrowth and Underdocks appear as the first act; normal act
selection/RNG agrees with the original method for the declared all-acts-seen profile. Tutorials
remain enabled/unseen and real account history is untouched.

Resource wall time is **258.689 seconds** (about 4 minutes 19 seconds), CPU **152.970 seconds**,
peak memory **975,060,992 bytes**; no cap was hit. All eight cases use one app/inode, eight private
profiles, **zero new app copies** and verified resets. The idle worker and frozen master remain
intact. **The stage is complete; no rerun is needed.** Its helper displays and audits saved results
only. [Completed panel evidence](evidence/actual-engine-v0.111.0-profile-panel-v1.json) preserves
counts, identities, storage scope and remaining gaps; the
[implementation evidence](evidence/actual-engine-v0.111.0-profile-descriptions-v13.json) stays unchanged.

**Completed combat stage:** all eight owner comparisons and an independent saved-only audit
pass, zero failed or unattempted cases. Two independent seeds × both fixtures × two repeats have
identical public prefixes. The audit verifies 72 observations, 64 effect decisions, 104 game/UI
actions, 24 combat tutorial pages and eight reshuffle confirmations. Corruption cost/exhaust,
Strength/Dexterity expiry, potion consumption, Pen Nib and the second turn agree in this scope.

Resource wall/CPU is **404.901/182.310 seconds**, peak memory **945,356,800 bytes**, with no cap hit.
One app/inode, eight fresh profiles and **zero new copies** have verified reset receipts. Evidence
retains 71,543,111 logical bytes of case records and 1,461,424 bytes of external profiles; tracked
storage includes the one shared app. **This stage is complete; no rerun is needed.** Its helper only
displays/audits saved results on repeat invocation. These assigned fixtures are not training data
or player-strength evidence. [Completed panel evidence](evidence/actual-engine-v0.111.0-combat-panel-v1.json)
preserves all counts/identities; the earlier short-check evidence remains unchanged.

**Current implementation under #145:** exact-slot combat potion discard is implemented in
separately identified Host v9 and passes two short native/shipped checks plus saved audits.
An automatic potion is discardable without a manual-use choice; two identical Strength Potions
retain distinct slots. Discarding one leaves the other unchanged, and using the second gives
exactly one Strength bonus. The new menu compares all offered play/use/discard/end-turn choices.
Seven Host checks, five identity/menu tests and 1,213 repository tests pass. The original game DLL,
older recipes and completed eight-case audit remain unchanged.

**Prepared optional follow-up:** `scripts/compare-combat-potion-discard-v1.sh` retains its
original eight-case recipe, preflight and 6–9-minute estimate. It has not been launched. The
owner's tighter finish line prioritizes a complete-run diagnostic over another repeat matrix;
the two passing exact-slot comparisons and negative checks remain evidence. New discard gaps
still block admission. [Guide](actual-engine-combat-potion-discard.md) and
[evidence](evidence/actual-engine-v0.111.0-combat-discard-v1.json) preserve its original scope.

**Historical queue before the bounded diagnostic:** broader current-wrapper/Host mechanics and complete public
facts: transient costs/effects/relic counters, mandatory/optional/nested selectors, consequential
mode references, shipped new-run initialization, later-act advancement and actual terminal
endings. Initial checkpoint inspection does not test the shipped lobby or act progression.
After required qualification, #146 measures full-run speed and connects a separate A8 neural
lineage. The current diagnostic results and owner handoff above supersede this queue's ordering.

**The owner startup panel passes: 12/12 cases, zero failures.** Six independent native A8 seeds
were imported through normal Continue twice each. Starting titles/availability match and repeated
choices are identical. The batch took 454.073 seconds; all case/config/report, save and snapshot
bindings were subsequently reverified from saved files without game attempts. Cost rates remain
unknown. This is a startup check, not player quality or full mechanics parity.

**First actual actions found and repaired a skipped Proceed step.** The reproducible v7 wrapper
now exposes the native finished-event Proceed button before opening the map. Native effects/map
voting and the official rules DLL remain unchanged. Its new binary has separate source, patch,
build and runtime identities. All **841 subchecks across 28 combat/rest/shop native fixtures**
were rerun on v7 and pass, with **85 SDK snapshots**, 60 delivered actions and 34 invalid inputs
refused. These privileged regressions are not training examples or shipped parity evidence.

**The owner first-combat panel passes: 8/8 cases, zero failures.** Two seeds, Winged Boots and
Dowsing Rod, each repeated twice: **two independent seeds and four seed/choice pairs**. The
60 compared observations, 52 gameplay actions and 24 tutorial steps were independently checked
against raw saved observations and delivery records without launching games. The batch took
406.247 seconds. Starting reward, Proceed, first combat, card plays, End Turn and the next hand/
enemy state agree within the frozen scope. Historical one-seed smoke results remain preserved.

Winged Boots and Dowsing Rod prefixes
match through Proceed, first combat, card plays, End Turn and the next hand/enemy state. Current
legal actions, costs, HP, energy, owned statuses, intents and pile counts match; incomplete/unknown
public fields fail. The three native tutorial buttons are separately counted and must leave the
underlying game facts unchanged. Shipped processes took 41.531 and 36.915 seconds. Effect text,
preview stats, relic counters, full map/pile information and later families/turns remain outside
this scope. Successful copies were removed after verification; all failures and private evidence
remain. [Current evidence](evidence/actual-engine-v0.111.0-starting-and-first-combat-v1.json) preserves
historical identities and results.

**Rest save loading repaired; two shipped rest comparisons pass.** The old wrapper used
`EnterAct` when loading a save, losing the saved room/history. The separately pinned combined
v8 patch uses the official saved-run entry sequence; the game DLL stays unchanged. Two fresh
baseline/two repaired builds reproduce in 16.160 seconds. All 841 combat/rest/shop subchecks
were rerun on v8 and pass. This does not qualify every saved-run resume state.

An explicit single-card/25-HP/Miniature Tent fixture heals, cancels/reopens Smith, upgrades and
uses Proceed. Healing reaches 49 HP; both action orders preserve the correct remaining choices
and upgraded-card flag. Seven observations and six effect decisions agree per smoke; the shipped
UI takes seven actions because selecting a card opens a separate confirmation preview. That
extra step is recorded and checked for unchanged game facts before committing. The two shipped
processes took 55.886 and 51.425 seconds. This is injected mechanics evidence, not natural room
reach or player quality. The fresh rest tutorial is unsupported by the released Host; the test
uses isolated native-generated progress that has seen only that tutorial. Other tutorials remain
enabled, and its source profile/report/copy are bound and verified. Unknown controls and stale
actions remain failures. [New evidence](evidence/actual-engine-v0.111.0-first-combat-and-rest-v1.json)
records these scopes, repairs and preserved failures.

**The owner rest panel passes: 8/8 cases, zero failures or unattempted cases.** Two independent
seeds, both action orders, each repeated twice. Its 383.715-second batch and 383.922 wall /
133.795 CPU-second resource record remain separate. A pure saved-data audit verifies
**56 observations, 48 rest decisions, 56 game/UI actions and eight upgrade preview steps**.
It checks current action operands, delivery, cancellation, preview invariants, healing/upgrades,
save/report/config bindings and repeated prefixes without launching games. This historical panel
used the isolated already-seen rest tutorial baseline; it does not qualify fresh-profile control.

**The fresh rest tutorial now works in two short shipped checks.** A separate MIT Connector Host
patch exposes only the exact current rest popup's visible confirmation button. Unknown popups
stay unsupported. Two fresh builds reproduce the separately pinned binary in 7.711 seconds;
the game DLL, original Host and original seal stay untouched. Each settings-only profile has
no copied tutorial progress. Both rest orders pass popup dismissal, unchanged underlying facts,
heal/cancel/reopen/upgrade/Proceed; the shipped processes take **36.164 and 35.118 seconds**.
Independent raw audits pass both cases. These are privileged single-card fixtures, not naturally
reached rooms, a full-game test or training admission. The changed Host needs its own subsequent
startup/combat regression evidence; old Host results do not qualify the new binary automatically.
[Current evidence](evidence/actual-engine-v0.111.0-rest-panel-and-tutorial-v1.json) preserves all
historical identities, failed attempts and new scopes.

**The owner fresh-profile rest panel passes: 8/8, no failures or unattempted cases.** Two independent
seeds and four seed/order pairs, each repeated twice. All eight fresh popups were clicked with
no copied tutorial progress. The saved audit checks **56 observations, 48 rest decisions,
56 game/UI actions, eight upgrade previews and eight popup clicks** without new games.
Batch/resource wall time is **428.762/428.978 seconds**, CPU **149.838 seconds**. Repeated native
prefixes match. This qualifies the named injected fixture, not full runs or model strength.
Two targeted startup/combat checks also pass on that rest-patched Host; they are not a new repeated panel.

**Shop comparisons found a rules-relevant TestMode shortcut.** The v8 managed wrapper omitted
the game's random potion-price adjustment and its RNG calls. The combined v9 MIT wrapper patch
restores the original calculation for that method alone; the official DLL's stored bytes and
global TestMode setting stay unchanged. Two baseline/two repaired builds reproduce. V9's 28
native fixtures again pass all **841 subchecks**. Audit other rule/RNG-changing TestMode branches
under #145; passing a local build does not establish complete rules fidelity.

**Two short shipped shop sequences pass and their raw saved audits pass.** Ordinary purchases
and Courier restocking agree on all current stock/prices, legal menus, gold, deck and occupied
potion slots through purchases, full potion capacity, cancel/reopen/confirm removal and map exit.
There are **19 compared observations, 17 effect decisions and 25 shipped game/UI actions** total,
including two first-potion tutorial clicks. The new cumulative MIT Host patch adds only the exact
obtain-potion confirmation and keeps rest support. Single-card removal selects directly into a
preview, then confirms; it does not need a separate Open-preview control. Full raw menus and
all failed attempts remain private. Saved comparison handles object-key reordering and independent
read timestamps while preserving state/action/read bindings. The cumulative Host/native-v9 pair
also passes its own fresh rest and first-combat regressions and saved audits. These are finite
checks, not transferred repeat-panel results. **1,071 repository tests, 88 standalone Node tests,
four focused Host tutorial tests, formatting/types and the C# protocol contract pass.**

**The first repeated shop batch stopped: one pass, one failure, six unattempted cases.** The owner
explicitly authorized Codex to run and assess this otherwise owner-launched stage. It took
**52.596 batch / 52.754 resource wall seconds**, with **21.256 CPU seconds**. The first ordinary
case passes its independent saved audit: nine observations, eight effect decisions, twelve
game/UI actions and one fresh potion tutorial. The next Courier case fails in native effect
checking before the shipped game is launched; repeatability is not established.

The bought Whirlwind is present, deck size rises from two to three and its 57-gold quote is charged
correctly (961→904). The native shop exports its energy cost as **0**, while the deck correctly
exports **X**. The effect checker therefore reports a missing purchased card despite its presence.
The native shop exporter uses numeric resolved energy cost without the `CostsX` handling already
used for deck/hand observations. This is a public-information export defect, not a failed purchase.
All results/inputs remain preserved. The old script now displays its failed result; do not rerun
it expecting new comparisons.

The first batch identified the need for native X-cost display handling in shop offers,
retaining X as distinct from a free zero-cost card. Its source/build/config lineage and failed
results remain immutable; the repair and repeat panel below are separate.
[Shop panel assessment](evidence/actual-engine-v0.111.0-shop-panel-v1.json) records the denominator,
saved audit and exact cause; [earlier evidence](evidence/actual-engine-v0.111.0-fresh-rest-and-shop-v1.json)
retains the successful prior smokes and reconstruction metadata. No full runs or training follow.

**The X-cost repair and new repeated shop panel now pass.** The cumulative v10 MIT wrapper uses
the existing game-owned cost display helper used by deck/hand. It neither infers X from card IDs
nor changes game rules, prices/RNG or comparison tolerances. The energy-cost read is outside the
unrelated stats-preview exception fallback, so an error cannot invent a free zero-cost card.
Two baseline/two repaired builds reproduce in **15.147 seconds**. Its own 28 privileged native
fixtures pass **841 subchecks**. The previously failing Courier case passes ten native/shipped
observations and its raw saved audit; the shipped process takes **36.032 seconds**.

The owner-authorized same shop stage was repeated in a new v2 folder: **8/8 completed, zero failed
or unattempted, identical repeated prefixes**, two independent seeds/four scenario pairs repeated
twice. Independent saved auditing verifies **76 observations, 68 effect decisions, 100 game/UI
actions, 24 other UI steps and eight fresh potion tutorial clicks**, with no games launched by
the audit. Batch/resource wall time is **387.725/387.921 seconds**, CPU **140.186 seconds**;
peak memory/storage are **1.172/2.462 GB**. No cap was hit; cost rates remain unknown.
The failed v1 denominator stays separate. The unchanged Host/SDK and semantic verifiers retain
their original identities; new native source/build/config pins bind this panel.

[V10 repair and panel evidence](evidence/actual-engine-v0.111.0-shop-energy-v10-and-panel-v2.json)
records all reconstruction metadata and scopes. **1,071 repository tests, 90 standalone Node
tests, formatting/types and the C# protocol contract pass.** These are privileged finite shop
fixtures, not naturally reached shops, full-game qualification or model-strength results.
The completed v2 helper only displays saved results when run again. No new long stage, full
games or neural training follow automatically.

**The repeatable compiled mode inventory is implemented.** It reads metadata/IL without loading
or executing game code, covering all **50,816 game method bodies / 1,457,929 instructions**, with
zero undecoded bodies. There are **434 direct references** to `TestMode` and its
`NonInteractiveMode` alias in **383 source-method groups**. The audited v10 wrapper has two
direct references. The separate private source extraction, game/wrapper SHA/MVID, inspector
binary/source and local inspection runtime host are bound. The audit took **1.468 seconds**,
launched no games and preserves all raw source/reference rows under ignored artifacts.

This is complete direct-reference enumeration, **not a completed semantic or fidelity audit**.
The first **24 method-group reviews cover 25 references; 409 references remain unreviewed**.
Reviews bind the actual method IL hashes and need an explicit rationale. Unknown/changed rows
stay visible; neither a complete inventory nor a fully reviewed static list can admit training.
Reflection, other aliases, Godot stub behavior and runtime differences remain outside this scan.

The original native test branch returns **preset Calling Bell relics and Cauldron potions**,
replacing normal generated rewards/RNG paths. The bundle branch also defaults to bundle one,
but the wrapper already has a prefix that presents a choice. **Correction to the first review:**
unconditional first-bundle play was not established. Warning-only hook installation and
missing-simulator/invalid-index fallbacks still need explicit checks. Conditional selector cleanup
and an act-selection preference change when alternative acts remain undiscovered. Fully
unlocked content does not define act discovery. Reward selection is an existing wrapper control
seam; multiple rewards/capacity/cancel still need coverage. Rolling Boulder changes damage
dispatch from visual-hit callbacks to a batch; damage/death hook ordering needs a comparison.
The known potion-price branch is already restored by v9/v10 and retains its separate shop evidence;
it is not counted as another unfixed price bug.

**V11 restores the two normal reward-generation branches.** It checks exact method IL hashes
before replacing only their local test-mode predicates; game-owned constructors, population,
RNG and pools remain unchanged. Two fresh baseline/two repaired outputs reproduce in
**13.832 seconds**. A new bounded comparison passes **8/8 cases across two seeds/four pairs
repeated twice**, using **24 disposable native fixture starts**. It compares the original-normal,
legacy-test and repaired-test paths: starting RNG/pools match; generated rewards and complete
final RNG/pool state match the original-normal reference; old presets differ; repeats agree.
This takes **19.046 seconds** and does not test pickup, curse delivery, capacity, choices or UI.
The new v11 combat/rest/shop regressions also pass **841 subchecks across 28 native fixtures**.

The separately versioned **mode review v2** binds v11 and corrects the bundle-hook interpretation.
The game inventory and **409 unreviewed references** stay unchanged; v11 has three direct mode
references. **1,102 repository tests**, formatting/types, the standalone reward checker build
and C# protocol contract pass. No shipped v11 parity, full-run win, training admission or model
promotion follows. Previous shipped panels retain their own v10/Host scope. Details:
[reward repair and corrected review evidence](evidence/actual-engine-v0.111.0-reward-rng-v11-and-mode-review-v2.json).

**V12 bundle choice repair and short checks pass.** Hook installation now checks the exact native
method and fails explicitly. Current player/selection/pack bindings reject malformed, stale and
duplicate commands; no invalid input becomes pack one. Native reservation, synchronization and
logging precede task completion. Cleanup cancels the pending task and clears bindings.

Eight seed/pack/repeat cases pass with **12 native starts, 34 public SDK snapshots, 22 delivered
actions and 64 refused invalid inputs**. A separate synchronization fixture passes **58 subchecks
across four starts/two seeds**, including callback ownership, overlap, cancellation and missing
simulator behavior. V12's combat/rest/shop and reward-generation regressions also pass under new
identities. One natural Scroll Boxes shipped comparison passes second-pack selection,
preview/cancel/reopen/confirm and exact deck award: **three observations, two semantic decisions,
five game/UI actions**, in **31.915 shipped-process seconds**. Saved raw reconstruction passes
and rejects five intentionally corrupted action/source/runtime/award records without games.

Earlier helper-binding, public-role, serialization-order and low-space failures remain preserved.
Canonical multiset comparison keeps all card values/duplicates; JSON key order cannot invent a
game mismatch. Large private disposable assets now use independent APFS clones when available,
with ordinary-copy fallback and unchanged full inventory validation. No hard links are used.
Details: [v12 evidence](evidence/actual-engine-v0.111.0-bundle-choice-v12.json).

**The original bundle UI batch was blocked before any case:** v1 has zero completed/failed
cases and eight unattempted cases because its free-space guard stopped it. Its saved failure and
resource report remain immutable. Rerunning v1 displays that failure rather than restarting.

**Storage/reuse work under [#147](https://github.com/benyanc/spireshift/issues/147):** future serial
qualification uses one locked working app, bound to the unchanged frozen master. Every attempt
gets a fresh small profile and immutable evidence; app-local connector/settings additions are
removed after verified child exit, then the complete original file inventory is checked. Interrupted
setup or unknown mutation leaves that one worker blocked; another full app is not silently made
on retry. The managed pool is capped at two apps / 5 GB, with a read-only inventory covering both
managed workers and other existing `game` directories. It never deletes historical copies.

**Short real reuse checks pass:** two different A8 seeds/pack choices use the same app path and
inode, distinct profiles, and one total app copy. Both return to the frozen baseline and pass raw
saved-evidence checks. A separate short native startup passes using that same app. Parallel isolation/throughput and deliberate blocked-worker repair/retirement
remain later work; old recipes keep their original identities and retention policy.

**The owner completed the v3 bundle panel: 8/8 pass**, zero failures or unattempted cases, with
identical repeated public prefixes across two independent A8 seeds/four seed-pack pairs. The raw
saved audit verifies 24 observations, 16 effect decisions, 40 game/UI actions and 16 previews; an
independent saved-only recheck reproduces it without games. All eight attempts reuse the same app
path/inode with distinct profiles, zero new app copies and verified reset receipts. Both the frozen
master and current idle worker match the original inventory. No per-case `game` directories remain.
Resource wall/CPU is **319.079/193.116 seconds**, peak memory 850,165,760 bytes, with no cap hit.
Tracked final storage includes the existing working app; newly retained results are about 27 MB
and profiles about 0.9 MB. V1's zero-case space failure and unused v2 recipe remain immutable.
Details: [completed panel evidence](evidence/actual-engine-v0.111.0-bundle-panel-v3.json) and
[working app reuse](working-app-reuse.md). No rerun, full game or learning follows this result.

**Reward pickup implementation and four short shipped checks now pass:** Calling Bell claim-all
and claim-one/skip, Cauldron fill/discard/replace/skip and fill/skip. Raw reconstruction verifies
21 observations, 17 effect decisions, 23 game/UI actions and four real tutorial clicks. The cases
reuse one app/inode with four fresh profiles, zero new app copies and verified reset. They are
explicit serialized one-Strike/1,000-gold fixtures, not naturally reached rooms or full runs.
The missing first-relic tutorial is repaired in a separately pinned Host; two fresh builds and
three focused tests pass. Observed rendering/operand differences are normalized without changing
values or weakening current item/price/potion/slot bindings. Sixteen corrupted saved records
are refused. Original game/SDK/Host, failures and earlier proposals remain preserved.
Details: [reward pickup evidence](evidence/actual-engine-v0.111.0-reward-pickup-v1.json).

**The owner reward panel now passes 8/8**, with zero failures/unattempted cases and identical
repeat prefixes across four independent A8 seeds/scenario pairs, each twice. Saved re-auditing
checks **42 observations, 34 effect decisions, 46 game/UI actions and eight real tutorials**,
launching no games. Resource wall/CPU is **351.598/208.263 seconds**. Eight fresh profiles reuse
one app/inode with zero new copies and verified resets; the master and current idle worker are intact.
The historical wrapper tracked its output folder instead of the recipe-owned case folder, so its
storage figure is incomplete. Preserve the result and missing-peak limitation. The repaired helper
derives all cache/output/tracking paths from the recipe; completed invocation only displays/audits
saved data. Two runner regressions cover this mismatch without game launches. No rerun is needed.
[Completed panel evidence](evidence/actual-engine-v0.111.0-reward-panel-v8.json) records the scope.

The v13 profile/text package above implements the pending contract and exporter repair.
Its owner repeat panel is complete. The combat-effects repeat panel above is also complete; then
continue the remaining mode reviews alongside encountered mechanics coverage. Broader rest/relic options,
full public effects and remaining decision coverage follow. Remaining work includes
remaining modifier/expiry/relic-counter interactions beyond the two assigned turn-two fixtures,
remaining reward/selection families and large choice spaces, out-of-combat potions, native relic
purchases/discount interactions, skipping a merchant before opening its inventory, other public
decisions, later acts and actual endings. Inventory coverage is not exhaustive reachable-state
coverage. The new Host's finite prior-family checks remain separate from historical repeat panels.
The legacy persistent-potion fallback remains historical; v13 uses native formatted text.
Qualify the current Host's broader decision families and transient modifier/expiry states
before learning admission. Registry text and finite reward fixtures do not exhaust nested hooks.

[Mode audit evidence](evidence/actual-engine-v0.111.0-mode-audit-v1.json) records the exact scope,
findings and incomplete review denominator. **1,083 repository tests**, the inspector's synthetic
IL/async/string/switch/truncation checks, formatting/types and C# protocol contract pass. No long
stage, training or game launch follows this static audit. Both #145 and #146 remain open.

#146 then measures complete-run speed/failures at one worker before bounded parallel workers,
versions a new actual-engine public encoder/model/experience lineage and connects existing
neural/PPO machinery. Useful independent A8 full-run gains remain the aim. Adaptive budgets
stay behind foundation readiness. No larger PPO/GA, difficulty change or controller follows
automatically. Changes stay local; no push/PR/Actions run is required.

## Preserved v0.107.1 direction and evidence

**Historical prepared stage, now deferred:** [test learning with repaired public inputs](full-run-relational-a8-v3.md).
The v2 encoder pooled each list item's identity and numeric properties independently. It cannot
separate **2 Strength / 7 Dexterity** from **7 Strength / 2 Dexterity**, nor a swap of counters
between two relics. This is an exact information-loss counterexample, not a measured explanation
of every previous defeat. A separately versioned v3 encoder binds properties to their public
owners, including card upgrade/enchantment descriptors. Both actor and bootstrap critic use it.
It retains the same **256 inputs, 16 tanh units and 4,384 actor parameters**, public legal choices,
PPO algebra and terminal-victory/auxiliary score contracts. Historical sources and results remain
unchanged; new models and experience cannot silently load the old format.

The [bounded input audit](evidence/public-a8-entity-bound-input-repair-v3.json) checks 189 states
from four saved **training** runs, verifies all candidate bindings, and distinguishes both swaps.
The repaired actual network learns two opposite synthetic preferences to **98.37% / 98.42%**
correct-action probability after 250 short synthetic updates. Identical old inputs impose a 50%
mean expected success ceiling on that particular balanced task. These are artificial learning
controls, not optimal-gameplay labels, wins or model promotion. The sample also observes hard
feature clipping and hidden-unit saturation; their effect on game strength is not established.

The [tiny actual-simulator check](evidence/public-a8-relational-pipeline-v3.json) completes
**14 attempts / 2,125 public decisions / 10 optimizer steps in 26.676 wall / 31.289 CPU seconds**,
with no failed attempts and no full wins. All 14 saved traces and 305 sampled decisions verify.
Its two development pairs are integration evidence only, and their seeds are excluded from the
owner stage. The initial summary-printing failure is preserved separately. All **897 repository
tests**, formatting/type checks and the C# protocol build pass;
[verification evidence](evidence/public-a8-entity-bound-verification-v3.json) records the short check.

The next owner recipe has at most **eight rounds of 128 sampled games / 1,920 attempts**,
including separate 128-seed train confirmations every two rounds and a frozen paired 128-seed
independent development comparison. It excludes earlier declared/inspected seeds and the tiny
pipeline check. Each round shows wins, average floor, best game and failures. The whole stage
has one **60-minute elapsed / 12,000-CPU-second budget**, 12 GB memory and 4 GB artifacts;
explicit resumption subtracts previous launch costs. There is no automatic next job, deployment
promotion, adaptive controller or final-test opening. A real independent gain is still required.
The guide contains **one specific owner command**.

The owner completed the earlier PPO-seeded GA: **16 generations, 5,248 actual attempts and
757,944 public decisions in 1,987.806 wall / 8,628.793 CPU seconds**. There were zero full wins.
The selected player is **exactly the original initializer**, not a new successful mutation.
On 128 fresh development seeds, PPO reaches mean floor **12.125** and clears Act 1 twice;
the selected initializer reaches **11.296875** and clears Act 1 four times. No repeated useful
improvement is demonstrated. Across the stage, 22 liveness failures and four unsupported runs
remain counted. The [owner outcome assessment](evidence/public-a8-actor-evolution-owner-v1-assessment.json)
preserves the negative result; selected-versus-initializer is a self-comparison. #139's follow-up
fine-tuning/alternation is deferred, and #140's matched-total-cost methods experiment remains open.

The preceding PPO v2's **32 rounds, 5,504 attempts, 659,118 decisions and 14,696 optimizer steps**
selected round 24. Its original 128-seed development result remains inconclusive: **11.6641 /
11.9922 mean floor, three / two first-act clears, zero wins**, approximate paired auxiliary 95%
interval **−0.65 to +1.31 floors**. The two launches cost 5,938.579 wall / 11,625.372 CPU seconds.
All development pairs completed normally; 16 liveness failures and one unsupported training
attempt remain counted. The [original assessment](evidence/public-a8-ppo-pilot-v2-assessment.json)
is preserved. More unchanged PPO or GA batches are not the next step.

The repaired simulator remains admitted for scoped policy learning, with coverage limitations
in [ADR 0004](decisions/0004-scoped-a8-simulator-learning.md) and
[admission evidence](evidence/public-a8-policy-admission-v2.json). #141 retains empirical later-act
UI parity and broader mechanics; neither a clean pipeline nor simulator learning establishes
complete live-game fidelity. Foundation #78 remains unready. Keep adaptive thinking behind #5;
selectable ascensions stay deferred under #142.

The history below remains bound to its original engines, schemas and experiments. The current
handoff above supersedes earlier repair-before-training instructions.

The owner completed 832 unified evolution attempts in 80.858 elapsed / 592.289 total CPU seconds.
Both players have zero full wins on 64 paired development seeds. The evolved player reaches mean
floor 9.46875 versus 11.0 initially, with 12 versus 8 failed attempts. No model is promoted.
[The diagnosis](full-run-pilot-v1-diagnosis.md) identifies premature Act 2 endings around floor 19,
stale combat-win flags, truncated public selections, a fourth reward encoding defect and an invalid
Ascension-0 label. The full-run guard correctly refused the premature wins. These defects block
more sustained learning and prevent a valid A0/full-game claim; larger training is not the next step.

[#141](https://github.com/benyanc/spireshift/issues/141) owns the repairs. The owner successfully
published the separate ending/reward candidate in 10.284 seconds; all nine targeted regressions
passed. The earlier missing-runtime failure and cached check remain preserved in
[runtime evidence](evidence/full-run-repair-runtime-check-v1.json). The owner then published the
public-choice candidate in 9.588 seconds with all 23 native synthetic regressions passing and its
actual public-list exports checked. It exposes every offered combat card, correct pile/generated
card identities, selected bundle and confirmation state, plus a source declaration of fixed A8.
The new versioned adapter and unified player consume these readouts, retaining every legal choice
and normal enemy targeting. Its fresh 4,384-parameter model can change every decision family.
Two short real native replays passed the previously reproduced fourth-reward and overflow-menu
errors: 410 transitions and 412 scored observations in 3.387 seconds, with no optimizer steps.
[Integration evidence](evidence/public-choice-integration-v2-evidence.json) preserves build, model,
adapter, configuration and replay identities. This is compatibility evidence, not playing strength
or real-game parity. The owner subsequently checked all 89 failed training attempts in 92.495 wall
/ 91.416 CPU seconds, replaying 11,947 transitions. **85 passed; four remain failed.** The successful
endpoints cover 65 overflow menus, seven premature endings, 12 bundle confirmations and one reward.

All four remaining cases stalled at Dense Vegetation or Punch Off: an unconditional fallback
offered action 3 on a committed fight page, while its handler accepts only action 0. Existing event
tests inspected slots 0–2 and missed this extra action. A third isolated source correction offers
only the accepted continuation on those pages and the matching Lantern Key page. All 32 targeted
managed regressions passed in 6.753 seconds, including nine new full-mask/progress/resource checks.
[Event repair evidence](evidence/event-continuation-repair-v1-evidence.json) retains the owner's
85/89 failed audit and the initial short-check compile failure as separate records. The corrected
native library subsequently published in 7.393 wall / 8.581 CPU seconds with all 32 tests passing.
Codex derived its separate public-adapter manifest and completed a new audit under a four-minute
cap: **89/89 passed**, 11,939 transitions, 89.677 wall / 88.861 CPU seconds. The four event cases
replay the exact saved prefix to the first rejected action, verify the removed button, then score
and execute the engine's sole continuation into the correct playable fight. Their 12 historical
noops are explicitly recorded as replaced; other action drift fails. All 89 original attempts
remain in the denominator, and the old 85/89 result is unchanged.
[Native integration evidence](evidence/event-native-integration-v1-evidence.json) preserves the
new native, public adapter, fresh model, original cases, audit and resource identities. Real-game
difficulty, endings and broader event-action conformance, plus re-admission, remain before learning.
The new native/adapter also passes all ten environment interface checks in a 0.825-second job.
[Interface/reference evidence](evidence/event-native-contract-v1-evidence.json) preserves that
result and its initial reporting failure. Existing real-game captures show initial options 0 and 1
at the three repaired events, while the current source still offers an extra skip there. All 32
saved full-run reference traces observe Act 1 only. These are concrete remaining action-parity
and later-act evidence gaps; passing the 89 inspected prefixes does not settle them.
Those remaining captured event-choice differences are now repaired in a fourth isolated candidate.
It removes the invented fallback skip and rejects locked or nonexistent event choices before
changing state. **All 109 captured choice lists match**: 52 initial screens and 57 settled later
event screens. The full mask is compared; genuine Leave choices remain. The one unsettled Dense
Vegetation page is explicitly excluded from settled-mask comparison, and other screen types and
uncaptured events are not presented as new coverage.

The final candidate published in 17.641 seconds with all 240 targeted checks passing, including
99 captured outcomes and the prior 32 regressions. The complete native suite passed **4,942 tests**
with one optional timing probe skipped in 54.545 seconds. Ten public interface checks also passed.
A fresh untrained player completed eight training-seed attempts without crashes or stalls in
7.687 seconds; all eight lost. Zero optimizer steps, no admission or promoted model followed.
[Event choice evidence](evidence/event-choice-repair-v1-evidence.json) preserves these results and
all failed build, stale-assertion and preflight attempts. The old 89/89 replay result remains bound
to its earlier candidate; it is not reassigned to the changed initial choices.

A short audit of the preserved game assembly confirms that earlier bosses advance to the next
act and that total floor is distinct from current-act progress. It also identifies the real UI's
forced Architect dialogue after the last boss; the simulator collapses this closing sequence.
Each settled dialogue page has one continuation, so this adds UI steps without a strategic choice.
The assembly confirms A8 activates harder rules and that Double Boss begins at A10, not A8.
[Frozen-rule evidence](evidence/frozen-run-rule-audit-v1-evidence.json) records the private extracted
type hashes and source findings. It does not establish full A8 fidelity or add empirical Act 2/3
captures. The owner chose **fixed A8** for the next learning workflow. Selectable A0 and other
difficulties are deferred under [#142](https://github.com/benyanc/spireshift/issues/142); they do
not block A8 learning. Relabelling A8 would not implement A0. The original evidence snapshot's A0
recommendation is historical and is superseded by [ADR 0003](decisions/0003-fixed-a8-learning-priority.md).

All original engine binaries, results, recipes and failed cases are preserved; final test is sealed.

[#136](https://github.com/benyanc/spireshift/issues/136) supplies the versioned training score.
[#137](https://github.com/benyanc/spireshift/issues/137) now supplies a standalone whole-run neural
player with 4,384 mutable parameters and public candidate binding. [#138](https://github.com/benyanc/spireshift/issues/138)
has complete-run experience recording, separate train/development indices and saved-input checks.
The first direct neural-weight evolution pilot under [#135](https://github.com/benyanc/spireshift/issues/135)
has completed its owner pilot with rotating common training panels, independent elite confirmation
and a final 64-seed development comparison. That is infrastructure/negative evidence, not a
competent player, matched cross-method result or foundation readiness.

**Historical v0.107.1 priority, superseded by ADR 0005:** prove a useful learning loop on **Ironclad / A8**, using the repaired public
player and truthfully declared rules. Difficulty is decided; there is no A0 implementation prerequisite.
The new scoped admission and A8 PPO recipe are ready. The next owner stage collects complete
runs, updates all policy components, and compares the frozen player with its initializer on
independent development seeds. Broader live-game parity remains separate work under #141/#37;
neither old teacher imitation nor a larger population alone establishes a useful learning method.
Stop or revise a method if independent progress stalls.
Wins remain primary; intermediate act/floor gains support development without claiming competence.
The historical A0-labelled score/runner and its population remain preserved; the new path must bind
its actual A8 scope, public-model version, corrected native identity and new experience lineage.
No completed check needs rerunning. Codex handles short jobs; any stage expected to take five
minutes or more gets one specific owner command when it is ready. Additional ascension support
is later work after a useful A8 player, unless the owner explicitly changes priority.

Earlier foundation evidence remains: the separately versioned [neural discard-choice comparison](neural-selection-repair.md)
had 32 normal terminal losses per player, zero wins/first-boss reaches/Act 1 clears, mean floor
6.84375 each and 27 changed traces without demonstrated gain. This is inspected-seed compatibility
evidence, not a fresh/final benchmark. Historical base-v2 remains accepted; base-v11 is unpromoted.
Comparison: `sha256:2bc12a35ee21e5ac285424cab8e19bcb236bb650c88d51aaa9d91e7ea8843ce6`.
Resources: `sha256:c8e246e7455f5df0913bc55d6585b694643aba26eabcf5186004c76f9947786d`.

Build a player that wins complete runs, then teach it when to spend little, medium or substantial
thinking effort. The primary evaluation objective remains **terminal full-run victory probability
under a fixed whole-run computation budget**. [ADR 0002](decisions/0002-full-run-bootstrap-training.md)
explicitly declares auxiliary learner returns for new bootstrap experiments, separate from the
real win/loss result. A strong inexpensive base player remains the foundation.

New experimental recipes may learn all policy components and depart substantially from weak
base-v2. Strategic learning no longer waits for combat-only improvement. Old saved lessons are
optional warm starts rather than permanent behavior targets. Legal/public-input checks,
independent evaluation, numerical stability and historical evidence preservation remain.

## Ordered implementation work

| Order | Work | GitHub items |
| --- | --- | --- |
| Complete; exact download/archive independently verified | Preserve and preflight the v0.111.0 actual-game copy and pinned sources. Keep old v0.107.1 artifacts immutable; file identity alone does not admit gameplay. | [#144](https://github.com/benyanc/spireshift/issues/144), parent [#37](https://github.com/benyanc/spireshift/issues/37) |
| Serial reuse implemented and owner repeat panel verified; maintenance remains | Eight cases reuse one protected app with fresh profiles, zero new app copies and verified resets. Explicit blocked-worker repair/retirement remains; parallel reuse follows under #146. | [#147](https://github.com/benyanc/spireshift/issues/147), [#145](https://github.com/benyanc/spireshift/issues/145), [#146](https://github.com/benyanc/spireshift/issues/146) |
| Complete for the bounded Ironclad/A8 environment gate | Two ordinary shipped losses, explicit later-act/endings, the ID-safe public input and representative mechanics stand. Native serial/parallel/reset and short neural integration controls pass. Earlier failures stay preserved; new encountered omissions still require repair. | [#145](https://github.com/benyanc/spireshift/issues/145), [#141](https://github.com/benyanc/spireshift/issues/141), [#143](https://github.com/benyanc/spireshift/issues/143) |
| Finite mechanics package complete ([#148](https://github.com/benyanc/spireshift/issues/148)) | Preserve prior pilots and failed sweep. Repaired 1,849-case sweep, nine random-action games, act/endings, outside-combat potions and Foul Potion merchant controls pass. The composed gate preserves the sweep's host-v32 scope and binds new v33 controls. These are interface checks, not playing strength or base readiness. | [#146](https://github.com/benyanc/spireshift/issues/146), [#35](https://github.com/benyanc/spireshift/issues/35), [#78](https://github.com/benyanc/spireshift/issues/78) |
| V5 and scoped diagnoses complete; conditional representation control next | Preserve native pilots, completed credit/scaling comparisons, recovered-pool analysis and matched-work teaching/PPO negative result. Test explicit public context-by-candidate interactions on the synthetic task at the same network size before a native intervention. No larger unchanged training or automatic promotion. | [#35](https://github.com/benyanc/spireshift/issues/35), [#143](https://github.com/benyanc/spireshift/issues/143), [#146](https://github.com/benyanc/spireshift/issues/146), [#78](https://github.com/benyanc/spireshift/issues/78) |
| Scoped learning admission complete; broader parity open | Repaired A8 source/native/public adapter admitted with all captured evidence and explicit limitations. Empirical Act 2/3 UI parity and complete mechanic fidelity remain before exact/live claims. | [#141](https://github.com/benyanc/spireshift/issues/141), [#37](https://github.com/benyanc/spireshift/issues/37) |
| Implemented | Versioned bounded bootstrap score, win-first population ranking, failures/caps and terminal-only staging rules. | [#136](https://github.com/benyanc/spireshift/issues/136) |
| Implemented | Unified compact full-run neural policy, public features, legal candidate scoring and deterministic genome/gradients. | [#137](https://github.com/benyanc/spireshift/issues/137), parent [#78](https://github.com/benyanc/spireshift/issues/78), iteration [#134](https://github.com/benyanc/spireshift/issues/134) |
| Implemented; owner pilot saved | Complete-run public experience, actual returns, milestones, lineage, immutable split-specific indices and verification; original failures remain represented. | [#138](https://github.com/benyanc/spireshift/issues/138) |
| Completed owner PPO; inconclusive improvement | Preserve 32-round PPO v2 and its complete independent comparison; no larger PPO launch is automatic. The earlier evolution pilot remains negative/compatibility-compromised. | [#35](https://github.com/benyanc/spireshift/issues/35), [#135](https://github.com/benyanc/spireshift/issues/135) |
| Input repair implemented; large emulator pilot deferred | Retain the entity-bound v3 encoder and synthetic/short pipeline checks. Carry the relational design into qualified actual-engine inputs before another large run; review credit assignment/capacity if learning stalls. | [#143](https://github.com/benyanc/spireshift/issues/143), [#78](https://github.com/benyanc/spireshift/issues/78), [#35](https://github.com/benyanc/spireshift/issues/35) |
| Completed owner hybrid; negative result | Preserve the 16-generation result, all costs/failures and initializer self-comparison. No larger unchanged GA or automatic fine-tuning follows. | [#139](https://github.com/benyanc/spireshift/issues/139), [#140](https://github.com/benyanc/spireshift/issues/140) |
| Later; after a useful repaired-input learner | Freeze genuinely matched total costs and terminal-only reference before cross-method superiority claims. Existing incremental hybrid evidence is not that comparison. | [#140](https://github.com/benyanc/spireshift/issues/140) |
| Deferred; current hybrid did not help | Preserve originals; revisit neural fine-tuning/alternation only when evolution produces a useful independent gain. | [#139](https://github.com/benyanc/spireshift/issues/139) |
| When affected search is needed | Repair legal-action preservation during hidden-world resampling. Whole-run policy evolution does not require action-branch cloning. | [#105](https://github.com/benyanc/spireshift/issues/105) |
| Foundation milestone | Establish repeatable held-out progress, then wins and credible run-value/risk evidence. Apply the foundation scorecard before adaptive thinking. | [#78](https://github.com/benyanc/spireshift/issues/78), contract [#5](https://github.com/benyanc/spireshift/issues/5) |
| Deferred; after a useful A8 learning workflow | Implement genuine selectable ascension levels and separate per-difficulty validation. This does not block the current learning work. | [#142](https://github.com/benyanc/spireshift/issues/142) |
| After the foundation | Integrate strategic/full-run learned search and demonstrate gains at equal compute. | [#46](https://github.com/benyanc/spireshift/issues/46), [#27](https://github.com/benyanc/spireshift/issues/27), [#28](https://github.com/benyanc/spireshift/issues/28), [#7](https://github.com/benyanc/spireshift/issues/7) |
| After useful search | Measure value of additional thinking, enforce whole-run spending and learn low/medium/high allocation. | [#29](https://github.com/benyanc/spireshift/issues/29)–[#34](https://github.com/benyanc/spireshift/issues/34), [#36](https://github.com/benyanc/spireshift/issues/36) |
| Later research | Freeze the final pre-patch bundle; measure zero-shot behavior and fixed-budget recovery after rule changes. | [#37](https://github.com/benyanc/spireshift/issues/37)–[#40](https://github.com/benyanc/spireshift/issues/40) |
| Final evidence | Reproduce public baselines, refresh competition and publish the final paired benchmark/report/demo. | [#49](https://github.com/benyanc/spireshift/issues/49), [#50](https://github.com/benyanc/spireshift/issues/50), [#41](https://github.com/benyanc/spireshift/issues/41), [#44](https://github.com/benyanc/spireshift/issues/44) |
| Optional product | Recommendation overlay and packaged Advisor, after player quality. | [#16](https://github.com/benyanc/spireshift/issues/16), [#43](https://github.com/benyanc/spireshift/issues/43) |

[#42](https://github.com/benyanc/spireshift/issues/42) retains negative-result analysis. Existing
adapters, public binding, rollouts, splits, accounting and owner scripts are reused. Closed
historical issues/recipes are not retroactively reclassified as successes.

## Learning and evaluation rules

- Keep one character, frozen game version and fixed difficulty for initial experiments. Ascension
  chooses difficulty, not an additive reward; report different difficulties separately later.
  The owner selected Ironclad / A8; do not reprioritize A0 or other difficulty support before a
  useful A8 learning workflow. The neural player continues learning every decision family.
  The profile must match actual implemented engine rules, not just a configuration label. The
  first unified pilot's Ascension-0 claim is invalid and remains disclosed as historical evidence.
- Full-run wins remain primary in population ranking/evaluation. The versioned bootstrap learner
  score distinguishes losing runs. Floors/acts are intermediate progress, not a victory-value
  target, foundation pass or permission for adaptive thinking.
- Experimental policies may change every phase. Do not impose permanent proximity to base-v2,
  frozen strategic choices or improvement on every old teacher metric. Use new recipes and
  whole-run gameplay evidence rather than relax a failed historical gate.
- The current PPO-seeded stage is incremental and retains prior PPO cost; do not claim it beats
  from-scratch PPO or GA under matched total cost. Later compare gradient training and direct
  evolution of the same compact NN at genuinely matched total cost.
  Use common seed panels within generations, rotate train panels and confirm apparent elites.
  Preserve diversity and reevaluate fine-tuning before replacing an evolved player.
- Freeze panels, exploration, updates/generations, tuning, caps and plateau stops before launch.
  Training/development/final-test ownership is at the complete-run boundary. Inspected development
  results are disclosed; final-test seeds stay sealed.
- Keep failures/caps/truncations/missing outcomes in denominators and count all actual work,
  including discarded candidates and teacher/fine-tuning costs. Repeated actions earn no reward.
- Stages expected to take five minutes or more have one clear owner command, progress, immutable
  outputs, explicit resume and a definite stop. Only the owner launches and monitors those jobs.
  Codex may run shorter stages with explicit caps; the short audit does not authorize admission,
  promotion or a longer collection/training/evaluation job.

## Preserved real-game milestone

The owner launched the privately archived v0.107.1 app outside Steam's managed library. Its
executable, pinned bridge and read-only menu identity were verified. [The frozen-game guide](frozen-live-game.md)
records its launcher and location.

Retesting after a normal future Steam update, save/profile isolation and watching a useful trained
policy through the live adapter remain under [#37](https://github.com/benyanc/spireshift/issues/37).
A menu launch establishes neither model strength nor full simulator parity. The final pre-patch
model/data/protocol bundle remains unfinished.
