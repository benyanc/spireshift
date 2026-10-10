# Evolve the complete A8 neural player

**Completed; negative result.** The owner finished 16 generations / 5,248 attempts, with zero
full wins. The selected player is the unchanged initializer: mean development floor 11.296875
versus PPO 12.125, and four versus two Act 1 clears on 128 fresh paired seeds. No model is
promoted. [Outcome evidence](evidence/public-a8-actor-evolution-owner-v1-assessment.json) preserves
all costs and failures. The current next command is in the [repaired-input pilot guide](full-run-relational-a8-v3.md).
The following recipe is historical; its launcher now displays the saved result.

The completed PPO experiment changed the player, but its unseen-game improvement is too small
to establish useful progress: **11.66 to 11.99 mean floor, three to two first-act clears, zero
full wins**, on 128 paired games. The
[saved outcome assessment](evidence/public-a8-ppo-pilot-v2-assessment.json) preserves the exact
result and both resource launches. We will test a different way of changing the same network.

## Run this one command

Run from any directory:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/evolve-full-run-a8-v1.sh
```

Allow roughly **20–40 minutes** on the inspected M4 Pro. This is an estimate from saved episode
timings; longer survival or stalled games can take longer. The whole additional stage has hard
caps of **60 elapsed minutes, 12,000 CPU seconds, 12 GB memory and 4 GB artifacts**. The owner
launches and monitors it. Paste its final summary or cap/error result into the chat. No other
discovery, build or training command is needed first.

An explicit rerun resumes identical saved work and subtracts all previous numbered launch costs
from the same total budget. It never resets the time allowance or overwrites reports. A completed
experiment displays its identified outcome metadata without new games or evolution. Saved games,
including failures and interrupted attempts, are retained; there are no free retries. A changed
recipe or implementation requires a separate experiment. This stage does not automatically start
another training job or promote a deployment checkpoint.

## What changes

We start with the saved PPO player and create variants by adding random changes to its weights.
All **4,384 actor parameters** can change: the 256 candidate features feed 16 tanh hidden units,
one scalar action score, and a learnable direct linear path. The model scores every supplied
legal action in combat, card menus, potions, deck building, routes, rest, shops, events and starting
choices. There is no penalty for departing from the weak initializer or PPO player. Each mutated
weight has a 20% chance of receiving Gaussian noise at one of the frozen scales 0.01, 0.03 or 0.1.
Mutation can reach every layer; weights are bounded only for numerical stability.

The stage evaluates whole players by playing complete runs. It does not use policy gradients or
the 257-parameter critic to select actions, so the critic remains attached and unchanged.
Deployment stays greedy, using public observations and actual legal candidates, with the same
128-CPU-second whole-run decision budget. No hidden state or action-branch search is introduced.

## What the experiment does

1. Measure the PPO starting player on 128 separate training confirmation seeds.
2. Evaluate 16 players on the **same 16 complete-run seeds** within each generation. Retain the
   confirmed player, PPO, initializer and available elites; fill the population with mutations.
   Keep the four highest-ranking parents and rotate the common train panel each generation.
3. Every two generations, check the leading candidate on the separate 128-seed confirmation
   panel. Keep the existing champion unless the candidate improves its frozen win-first ranking.
4. Stop after six unsuccessful confirmation checks once 12 generations have completed, at
   16 generations, or at a resource cap. Freeze the selected player before development begins.
5. Compare initializer, PPO and evolved player on **128 fresh paired development seeds per
   distinct player**. These games do not choose the champion or change weights. If evolution
   keeps PPO, their self-comparison is explicitly invalid as evidence of improvement.

There are at most **5,632 planned attempts**, including confirmation and all three development
players, with eight disposable game processes. Reused identical player/seed attempts reduce
actual work. Failed/capped/unsupported games stay in their denominators. The generation display
shows wins, average floor, best completed game and failures for its best candidate, followed by
the separately confirmed player. One high floor on 16 games is not a reliable improvement claim.

The same versioned score ranks full-run wins first and uses bounded act/floor progress to
distinguish losing players. Auxiliary progress does not become a victory probability or a
foundation pass. Alternate ascensions remain deferred: this is fixed Ironclad / A8.

## How to interpret the result

This is **PPO followed by neural-weight evolution**. It tests whether an additional broader
search for policy weights helps the saved player. It is not a from-scratch GA comparison, and
it cannot establish superiority over PPO at matched total training cost. The frozen protocol
and report carry all **5,504 prior PPO attempts / 11,625.372 CPU seconds** as well as the separate
new launch reports. Discarded candidates, confirmations, failures and resumptions count.

Use full wins as the main result, then paired act/floor progress, failure counts and resource
costs. A meaningful repeatable gain would justify a further experiment; a weak result should
trigger a review of representation, credit assignment or score rather than automatic scaling.
Automatic alternation or neural fine-tuning after evolution is still conditional on evidence.
#140 retains the later matched-method experiment and terminal-only reference. The base-policy,
terminal value/risk/calibration and equal-compute search readiness requirements remain before
learning low/medium/high thinking budgets.

## What is verified

The [short actual-simulator check](evidence/public-a8-actor-evolution-pipeline-v1.json) completed
**16 attempts / 2,122 public decisions in 16.473 wall / 21.757 CPU seconds**, with no failures
and no wins. Its mutated candidate failed confirmation, so the champion remained PPO. This is
pipeline compatibility only. Both inspected development seeds are excluded from the owner
comparison, along with all prior PPO and disclosed implementation-check seeds.

Tests cover mutation of every actor layer, unchanged critic, common seed panels, reserved/test
ownership, prior-cost reconciliation, deterministic interrupted resume, failed-attempt retention,
frozen selection before development, and whole-stage budget subtraction. The original PPO,
experience, encoder, worker and admitted engine implementations stay unchanged, preserving
the completed experiment's identities. All **884 repository tests**, formatting/type checks
and the C# protocol build pass. The
[verification evidence](evidence/public-a8-actor-evolution-verification-v1.json) preserves two
initial new-test reference/isolation failures and the successful 49.045-second check. The
[scoped admission](evidence/public-a8-policy-admission-v2.json) still has
[explicit live-game fidelity limits](decisions/0004-scoped-a8-simulator-learning.md).

Recipe: `configs/full-run-evolution/sts2-v0.107.1-public-a8-ppo-seeded-v1.json`.
Results: `artifacts/full-run-evolution/sts2-v0.107.1-public-a8-ppo-seeded-v1/evolution-report.json`.
New resource reports: `artifacts/resources/a8-actor-evolution-v1-attempt-*.json`.
PPO originals: `artifacts/full-run-ppo/sts2-v0.107.1-public-a8-pilot-v2`.
