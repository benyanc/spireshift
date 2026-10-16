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
At that stage both prepared owner cases passed preflight. That capped prefix was not a completed
game or training admission.
[Short-check evidence](evidence/actual-engine-v0.111.0-shop-navigation-v1.json) preserves the
new capped prefix and the earlier navigation failure separately.

## Completed endings and targeted progression, 2026-10-14

The repaired owner seed completes **104 gameplay actions** and a genuine shipped **loss on
floor 5**, with no unsupported issues, recoveries, uncertain deliveries or caps. Saved auditing
and fixed-app reset verify. The earlier first seed's **144-action, floor-6 loss** remains valid;
it was not replayed. The original second-seed repeated-card-offer failure stays preserved.
These are two independent natural endings under recorded diagnostic policy revisions, not wins
or a policy-strength comparison. The old owner command now audits saved data only.

A bounded privileged fixture reaches each boss through the native debug map command, forces its
defeat, declines rewards and uses native Proceed. Native v22–v24 restore missing graphics/call bindings
and supply the absent audio singleton without skipping the boss's gameplay hooks or changing
the original rules DLL. A separately recorded v23 regression reaches endings but stalls on quit;
v24 fixes the missing call binding and explicitly checks native cleanup. The checker distinguishes unfinished Architect dialogue from official
run completion, and verifies explicit victory even though the native ending sets HP to zero.

The app passes **Act 1→2 and Act 2→3**, including each fresh map tutorial. Its final sequence also
reaches explicit native/public win; a new saved-only audit verifies that trace without another
game. The original final-check batch retains its JSON key-order verifier failure. A corrected
verifier compares values independently of object-key order. Earlier fixture/import/control/wait
failures and unattempted cases remain counted in their original batches.

One fixed app/inode serves every app check, with separate profiles, zero new copies and verified
reset. These assigned fixtures are **not ordinary runs, player wins or learning examples**.
Imported post-boss saves re-offer rewards; the scoped check declines them and compares act targets
and endings. It does not establish general checkpoint reward/RNG resume parity or exhaustive
mechanics equivalence. [Evidence](evidence/actual-engine-v0.111.0-progression-v1.json) binds every
result and source identity; [the guide](actual-engine-natural-runs.md) gives one saved-only audit.

The current v24 native panel passes eight clean endings and shutdowns: 775 decisions, ten
families and 25.855 summed case wall seconds. These are ordinary losses, not a quality comparison;
the earlier v21 panel and the failed v23 shutdown batch retain their own identities/denominators.

A saved-only renaming control exposes one concrete remaining input issue: `target_entity_ids`
influences the initializer's tie-break key, changing which enemy receives a potion despite identical
public game facts. Fix semantic reference handling and enforce renaming invariance before fair
comparisons/learning. This finding is not a claim that an old trained neural model used those IDs.
Then measure full-run costs and worker isolation, and integrate the public encoder/actor/critic/
experience stream with the existing learner. Pass the short learning control before the owner launches one finite A8 neural
pilot. No diagnostic automatically admits bulk training or adaptive thinking. Do not expand this
finish line into all content combinations or repeated fixture matrices.

## Worker and learning gate, 2026-10-14

The temporary-ID targeting defect is repaired with a separately versioned public entity graph
and diagnostic policy. Renaming controls pass 783 saved observations / 2,349 comparisons.
A source-pinned eight-seed serial plus two-worker repeated-seed panel completes all 12 games,
checks matching semantic traces across processes/resets, denies sibling profile access and
verifies protected inputs and shutdown. Managed simulations create no app copies.

The actual-engine neural encoder, compact actor/critic and sealed experience now use the
existing PPO numerical routines. A four-game control verifies 209 sampled decisions and six
updates, reloads the changed checkpoint and audits the saved public action/delivery chains.
All four games are ordinary losses; this is a pipeline pass, not a useful-player or readiness
claim. Complete-run seed ownership separates training, confirmation, control and development.

The bounded environment/integration finish line is reached. Admission permits one finite
Ironclad/A8 policy-only bootstrap pilot, with a frozen checkpoint before independent paired
development evaluation. [The pilot guide](actual-engine-neural-pilot.md) gives one owner command.
Strong-base readiness, adaptive control and broad mechanics/other-difficulty/GA work remain
separate. Within the declared pilot, retire and verify shutdown after an isolated failed game,
exclude its partial data and continue the next original seed. More than two failures per panel,
missing games, corrupt evidence or unverified shutdown still stop learning.

The owner's v2 pilot performed 222 updates over three rounds, then stopped at three event failures
in round 4, before independent evaluation. Host v28 repairs the shared missing event presentation
calls and a versioned worker policy permits bounded reward-menu exploration. Targeted event
replays, twelve worker games and the four-game learning control pass. Per the owner's choice,
v3 starts afresh from the original numerical initializer with zero Adam steps. Historical results
remain unchanged. No new broad qualification campaign is required before that owner-run pilot.


## Systematic coverage after the completed pilot, 2026-10-15

The owner completed v3 (336 attempts, 332 normal endings, four failures, zero wins). A saved
assessment verifies 627 updates and 26,416 clean sampled decisions; the independent progress
comparison is inconclusive. The first-pilot finish line above has been reached. Following the
owner's new request, the next finite package inventories every frozen native model, repairs
cross-character resources/targets and nested choices, and generates all-pool card/combat-potion
checks plus representative interaction regressions. Inventory does not prove effects; a blocked
prerequisite does not count as exercised. Shared frozen inputs and one interface cache avoid app
copies. Unknown and untested families remain explicit. See
[the coverage contract and one owner command](actual-engine-mechanics-coverage.md). This is not a
requirement to exhaust every card/relic/history combination or a change to Ironclad/A8 priority.

## Current handoff, 2026-10-15

The finite all-pool mechanics pass and the remaining outside-combat potion/merchant requirements
are complete. Host v33/new worker v8 pass 25 potion fixtures, two merchant purchase/exit checks,
native lifecycle fixtures and 12 natural serial/parallel/reset controls. The composed gate keeps
the old 1,849-case sweep labelled host v32 and rechecks its evidence before carrying forward only
unchanged game-model/combat-projection coverage. No exhaustive interaction or shipped parity claim
is added. All workers share frozen inputs and create zero app copies.

A four-game short neural control passes with 228 verified training decisions and six optimizer
steps. Its preceding failed greedy control is preserved. The next finite pilot explicitly uses
categorical policy evaluation at temperature 0.8 and fixed paired RNG streams, with all choices
still selectable; greedy robustness remains a model-quality limitation. The original seeded
network/zero optimizer initialize a fresh 336-game A8 pilot, which only the owner runs.
See [the single current command](actual-engine-outside-combat-potions.md).
