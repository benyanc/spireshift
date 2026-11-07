# ADR 0007: A8 base competence before compute and compatibility expansion

## Status

Accepted November 4, 2026 following the owner's request to prioritize a base model
that consistently beats the A8 final boss, consider A10 after that, and update
the work items. This decision changes work order and the planned scope of future
development recipes. It does not alter an existing ObjectiveSpec, numerical
budget, learner, compatibility guard or recorded result.

## Evidence

The earlier controlled teaching comparison learned its two examples but reported
0/64 fresh full-game wins for each version. The latest varied bank supplies
12 lessons from eight fitting worlds; its three confirmed improvements are
+1/+1/+5 HP in already-won floor-2 fights. All 256 fitting updates reconstruct,
but current-final playing-strength improvement is unproved.

The latest exact-final canaries retain three genuine matching losses, one
official CPU-limited incomplete pair and two unattempted routed cases. The saved
common prefix matches. Its official guard counts coordinator, game and SDK CPU;
that stop does not establish a policy-inference defect or game-mechanics mismatch.
These are useful execution/learning controls, not a competent base player.

See [teaching result](../native-plan-teaching-result.md),
[collection result](../native-varied-teaching-collection-result.md),
[fitting result](../native-varied-fitting-result.md) and
[canary result](../native-varied-final-canary-result.md).

## Decision

1. **Build consistent full-run A8 competence first.** Keep Ironclad and the frozen
   v0.111.0 / 41cef1ea game. Terminal victory from normal starts on unseen worlds
   is the primary outcome. Freeze the target win rate, sample/confirmation scope,
   uncertainty and failure rules before evaluating competence. Act/floor/HP and
   lesson metrics diagnose learning; they cannot satisfy this milestone.
2. **Prepare useful whole-game learning evidence.** New #152 covers early through
   late acts, diverse decks/resources, strategic decision families and bosses.
   Qualify stronger teacher/search continuations and explicitly marked training-only
   later-act/boss starts. Validate their state/reset semantics. Student inputs
   remain public; teacher-only branches and training starts are separately marked.
   No prepared-state victory becomes a normal-start benchmark win.
3. **Allow the base model to improve materially.** #134/#35 own the actual learning
   loop, with #143 supporting demonstrated representation/capacity needs. Preserve
   existing full weights/Adam as immutable baselines while allowing a new lineage
   to change architecture, policy/value learning and any legal decision family.
   Tiny weak-label cloning, exact warm-Adam inheritance and a fixed critic are not
   universal requirements. More unchanged PPO or a bigger network alone is not an
   established remedy. Training and held-world gameplay must show useful changes.
4. **Evaluate development progress in the native engine.** #146 uses new declared
   recipes, normal starts, disjoint train/development/confirmation/final-test
   ownership, frozen candidates, complete denominators and wins-first reporting.
   Iterate the curriculum/model from development evidence. Never tune on sealed
   final-test seeds or migrate historical held-out labels into training silently.
5. **Keep targeted correctness and milestone official verification.** Current
   source/public-input/action, known-gap, isolation and reset checks remain.
   New development recipes must explicitly version their admission/compatibility
   scope and test it before execution. Plan official checks for changed interface
   or consequential mechanisms and promising candidate milestones; verify real
   official full games before claiming official-game competence. Requiring six
   complete official endings for every numerical checkpoint is off the critical
   path. Known input/action/effect defects still block the affected scope.
6. **Treat compute as operational for this stage.** Keep practical declared wall,
   memory, storage and execution limits, with cost recorded secondarily. Defer CPU
   attribution, equal-budget algorithm comparisons and compute-allocation research.
   The old 128-second official-host guard is not a universal prerequisite for
   future native base learning. Any actual change to a numerical constraint,
   ObjectiveSpec or admission rule requires a new versioned recipe and explicit
   regression coverage before running it; this planning commit changes none.
7. **Advance to A10 after consistent A8.** #142 will validate genuine A10 rules,
   separate training/evaluation and a new lineage on the preserved build. Other
   difficulties do not displace A8 base development now. #5's broader policy/value/
   risk/search-readiness checks remain before adaptive controllers, separately
   from the immediate A8 competence milestone.

## Deferred and preserved work

CPU/budget research (#7, #28–#34, #36), GA/hybrid bakeoffs (#135/#139/#140), the
old full six-case canary panel, its same-final interference experiment, and
unrelated platform/patch/overlay work are not prerequisites for the new program.
Search that produces useful teaching examples is distinct from learning an
adaptive compute controller. Revisit supporting work only for a demonstrated
base-learning blocker or after the base milestone.

Preserve the incomplete VTV204 world and marker without replay; VTV205/206 remain
unattempted. Keep all three successes, exact dbcb5980... finals, original states,
full Adam, frozen build/runtime and historical recipes/results. The old gate
remains unpassed and its command blocked. Deferring it grants no retroactive
qualification. ADR 0006 and prior experiment contracts retain their historical
scope; this decision governs planning of a distinct new native-development scope.

The ordered [backlog](../backlog.md) and GitHub #78/#152 are the current handoff.
This decision authorizes work-item/planning updates only; it starts no game,
optimizer update, old-study retry, promotion, adaptive controller or long job.
