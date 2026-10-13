# Finish the Ironclad/A8 environment and return to learning

Accepted by the owner on 2026-10-12. This tightens #145/#146's implementation finish line;
it does not change ADR 0005's game identity, ordering, objective or information boundary.

## Fixed scope

Use the separately frozen v0.111.0 / `41cef1ea` engine, Ironclad, Ascension 8 and the declared
`native_benchmark_full_v1` isolated profile. Terminal full-run victory remains primary under
the versioned whole-run CPU allowance. Floors, acts and HP are diagnostics. Preserve the old
v0.107.1 learning lineage and all earlier successes, failures and fixture results.

## Three packages before the next learning pilot

1. **Complete the unattended game interface (#145).** Implement a general public-observation /
   refreshed-legal-action loop and run from a normal native start to a genuine native ending.
   Handle starting options, paths, combat and potions, events, rest sites, shops, rewards,
   mandatory/optional/nested card or bundle choices, act transitions and death/victory.
   Verify shipped startup, later-act and ending semantics with targeted same-build checks;
   injected checks stay separate from naturally played runs and learning examples.
2. **Measure complete runs and worker isolation (#146).** Freeze a finite eight-seed, one-worker
   diagnostic panel after a short smoke check. Count every planned attempt, including crashes,
   unsupported states and caps. Measure full-run timing and retained bytes; then test a bounded
   two-worker panel with distinct profiles and no shared mutable state. Managed simulations
   share frozen game inputs; shipped comparisons reuse one fixed app per worker.
3. **Connect the existing learner (#146).** Version the actual-engine public encoder, actor/critic
   and experience stream. Preserve property ownership, per-copy costs and modifiers, statuses,
   counters, current intents, visible map/pile facts and selection bounds. Check collisions,
   missing information and a short learnability/pipeline control. Prepare one finite owner-run
   A8 neural/PPO pilot with independent development seeds and explicit resource caps.

## Admission checks

- Every in-scope decision family has a supported complete current menu, correct operand binding
  and meaningful public input coverage. Refresh after each action; repeated rest/shop/reward
  choices are ordinary successive states. Large selections cannot silently drop choices.
- Complete the frozen eight-seed natural-run panel without unsupported decisions, unknown
  delivery, liveness failures or unclassified endings. Normal losses are successful environment
  tests and remain losses in player metrics. A weak policy does not need to win before training.
- Cover later-act advancement and genuine native victory/death with targeted checks when a weak
  player cannot naturally reach them. Report fixture and natural-run denominators separately;
  fixtures never manufacture wins or become unmarked training experience.
- Existing representative cost/expiry, status ownership, relic-counter, potion-capacity,
  rest/shop/reward and selection checks must pass on the pinned implementation. Review known
  rule/RNG-changing shortcuts relevant to this scope and fix demonstrated gaps. Each newly
  encountered omission becomes a targeted regression plus an explicit admission blocker.
- Verify seed/reset behavior, isolated profiles, immutable game inputs, whole-run accounting
  and the short learning control before preparing bulk learning. Training admission is an
  explicit result of these checks; a diagnostic runner or passing fixture cannot grant it.

## Work that does not hold up the first pilot

Do not require exhaustive card × relic × enemy combinations, all characters, other ascensions,
every static mode reference, or repeated eight-case matrices for each previously passing fixture.
Additional coverage continues from encountered states and known risks. The prepared potion-discard
repeat recipe remains preserved as optional follow-up; its two passing exact-slot comparisons and
negative checks stand, and any new discard gap still blocks admission.

General interrupted-worker recovery and historical payload cleanup remain #147 follow-ups;
serial app reuse and verified reset are already demonstrated. GA expansion, patch-transfer
research, the final benchmark and adaptive thinking follow a useful base learner. These deferrals
do not permit hidden inputs, silent failures, omitted legal choices or unsupported ending claims.

## Implementation status, 2026-10-13

The complete native public loop now records eight natural candidate endings, 1,115 decisions
and 15 decision families without unsupported states or runtime errors in the frozen panel.
These are ordinary losses, not full-game fidelity or playing-strength evidence. Two natural
shipped menu starts match; a new Host prefix reaches 54 gameplay actions/two combats before
the short cap. The fixed app resets with zero new copies.

The first owner shipped attempt stops alive on an unsupported floor-5 screen after 73 gameplay
actions. Its evidence stays preserved. The four authorized repairs add exact tutorial controls,
reached-progress reporting, bounded issue collection/recovery and consistent take/skip/leave
semantics. A subsequent short probe finds and records the combat-reward tutorial; the final
separately built Host also implements its control and the remaining standard single-player
tutorial controls. These are implementation/short-check results, not complete shipped admission.

The final Host now handles the map and combat-reward tutorials in a normal shipped prefix.
That check exposes an open/close shop loop in the diagnostic initializer. A repaired public
navigation preference inspects a shop once, then chooses its advertised exit when returning;
all legal choices remain available to an external learned scorer. A fresh **101-action** prefix
reaches **floor 6** with no unsupported issues and stops at its short cap. Its saved actions,
navigation/progress counters and shared-app reset verify; **zero new app copies** are created.
Both prepared owner cases now pass preflight. This is not a completed game or training admission.
[Short-check evidence](evidence/actual-engine-v0.111.0-shop-navigation-v1.json) preserves the
new capped prefix and the earlier navigation failure separately.

The next owner stage is **two independent natural shipped discovery runs**, with serial app reuse,
complete failure denominators and verified reset between seeds. Unknown screens without current
controls still stop the affected game; a verified legal exit can continue diagnostic discovery.
Recovered runs cannot satisfy the clean environment gate or enter ordinary learning data.
[The guide](actual-engine-natural-runs.md) provides one command and explicit caps.
Later-act/victory checks, known input omissions, worker isolation, learner integration and the
short learning control remain required. Short jobs may run automatically; the owner launches
and monitors stages expected to take five minutes or more. No diagnostic automatically admits
bulk training or adaptive thinking.
