# Test learning with repaired A8 inputs

The old player receives **2 Strength and 7 Dexterity** exactly as it receives **7 Strength
and 2 Dexterity**. It pools the two status IDs and two amounts separately, so their association
is gone before the neural network starts. Relic-counter and card-variant relationships have
the same structural defect. More games or genetic mutations cannot recover missing information.
This is a demonstrated input defect; it is not proof that it caused every previous loss.

The v3 player keeps each visible property attached to its owner. It uses the same printed-card
catalog, complete public menus, legal actions, **256-feature / 16-tanh-unit / 4,384-parameter**
actor and 257-weight bootstrap critic. Every actor layer and decision family can learn, with
no permanent penalty for departing from the initializer. No hidden engine facts are added.
PPO clipping, numerical gradients, score, fixed Ironclad/A8 rules and whole-run budget remain
the same. The new encoder, actor/critic, experience, worker and runner have separate identities;
old results remain bound to their old implementations. New training starts from the same
warm-start weights, not a silently converted historical trained player.

## Run this one command

Run from any directory:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/train-full-run-relational-a8-v3.sh
```

Allow roughly **20–40 minutes** on the inspected M4 Pro; longer surviving runs or optimizer
work may extend that estimate. The entire stage has hard caps of **60 elapsed minutes,
12,000 CPU seconds, 12 GB memory and 4 GB artifacts**. The owner launches and monitors it.
Paste its final summary, or any error/cap result, into the chat. No prerequisite command is
needed; the short checks are already complete.

The script performs at most **eight rounds of 128 sampled complete games**, confirms the initial
player and then every second round on 128 separate training seeds, freezes the selected player,
and compares it with the new initializer on 128 independent development seeds. There are at most
**1,920 planned attempts**, with eight disposable game processes. All supplied public choices
remain available, including combat, potions, rewards, deck building, routes, rest, shops, events
and starting options. Normal losses, liveness failures, unsupported actions, crashes and caps
stay counted. Whole-run decision compute remains 128 CPU seconds per player attempt.

Each completed round prints its best completed game, average floor, wins and failures, plus the
best sampled game so far. Separate confirmation checks print the selected greedy player's results.
The development seeds never choose a checkpoint or update its weights. Previously declared or
inspected development panels and the two tiny-check development seeds are excluded. The final
test remains sealed. An explicit rerun resumes identical completed work and deducts all numbered
launch costs from the same stage allowance; it does not reset the allowance or retry failures for
free. A finished experiment shows saved outcome metadata without fitting or new games.

## What is already checked

The [input audit](evidence/public-a8-entity-bound-input-repair-v3.json) checks 189 states from
four saved training runs, keeps the same action bindings, and demonstrates both information-loss
counterexamples and their repair. On an artificial two-state task with opposite preferences,
the actual repaired network learns both preferences to **98.37% / 98.42%** correct-action
probability after 250 short updates. The old indistinguishable inputs limit mean expected success
to 50% on that specific balanced task. These labels are synthetic; neither action is declared
optimal in the actual game, and the control's trained weights are discarded.

The [tiny real-simulator pipeline check](evidence/public-a8-relational-pipeline-v3.json) has two
small rounds, saved-input verification, separate selection/development and a functioning final
summary. It checks integration, not playing strength. Its initial summary-printing failure remains
preserved as a separate failed attempt. Historical PPO, GA, adapter and feature sources are unchanged.
All **897 repository tests**, formatting/type checks and the C# protocol build pass;
[verification evidence](evidence/public-a8-entity-bound-verification-v3.json) records the bounded check.

## What would count as progress

First inspect failures and whether the selected player differs from its initializer. Then compare
paired independent development games: **full-run wins first**, followed by Act 1 clears and floor
progress as supporting diagnostics. A useful gain should hold across games; a single high floor
or the two-game pipeline check cannot establish it. Bootstrap critic outputs are auxiliary returns,
not victory probabilities. This shorter repair pilot is not a matched-budget v2-versus-v3 ablation
or a comparison claiming PPO beats GA.

If useful learning is still absent, examine credit assignment, available card-effect information,
feature compression and model capacity before increasing batch volume. Do not automatically start
another job or repeat the unchanged GA. Foundation readiness, terminal-value/risk calibration and
equal-compute search benefit still precede low/medium/high thinking. Selectable ascensions remain
deferred; current difficulty remains A8.
