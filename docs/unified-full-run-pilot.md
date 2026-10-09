# Unified full-run player and first evolution pilot

## Owner handoff

Run **one command**, from the repository:

```bash
bash scripts/evolve-full-run-policy-v1.sh
```

The owner launches and monitors this sustained job. Implementation did not launch it. The script
starts with 16 candidate players, plays complete simulated games and changes their neural-network
weights over at most four generations. It saves the decisions as experience for subsequent
learning. There are at most 832 planned game attempts, eight worker processes and one numerical
thread per worker. The script stops after three generations without independently confirmed
training improvement, at the generation limit, or at a resource cap.

Per-launch caps are 60 minutes elapsed, 20,000 CPU seconds, 12 GB memory and 3 GB of artifacts. Each game
has the same 128-CPU-second allowance and a 4,096-decision safety limit. The elapsed limit is a
cap, not a predicted duration. Longer survival and more choices can increase the workload.
No Steam game needs to run during this job.

Progress appears after each eight completed game attempts and after each generation. The final
console summary reports wins, mean floor reached, failures and paired improvement. Return that
summary and its resource report for assessment. No automatic next experiment, promotion, neural
fine-tuning, adaptive-controller training, GitHub Actions job or publication follows.

If interrupted or capped, run the **same command** to resume the identical protocol. Completed
attempts and failures are reused; interrupted attempts are preserved and explicitly marked as
having unknown episode cost. Resource reports use new attempt names; total experiment cost includes
every launch, including interrupted launches. A completed pilot is read
without new games. A second concurrent launch is refused. A changed implementation or protocol
cannot quietly resume the old population. Do not edit learning code while the job is running.

## What changes from the historical player

This is a standalone whole-run player, not the historical combat-only adjustment to base-v2.
It scores every supplied legal candidate through shared features: 256 inputs, 16 tanh hidden
units, one scalar score per action, plus a fully learnable linear connection from inputs to the
score. It has **4,384 trainable parameters**, a deterministic genome representation and a
backpropagation function for the entire genome. All choices and all network/linear parameters
can change. There is no permanent proximity limit to base-v2 or frozen strategic component.

Simple printed-card tactics initialize learnable linear weights so a fresh player has some
direction. They do not remove legal options or remain fixed during training. Evolution mutates
the whole genome at several scales and retains candidate diversity. This first pilot implements
direct neural-weight evolution; PPO, outcome-based gradient updates and the comparative hybrid
experiment remain separate work. It starts from this new initializer, not an accepted old
checkpoint, so the immediate comparison is **evolved versus initial unified player**.

The network currently supplies policy scores only. It has no calibrated terminal-value or death
risk head, and does not decide how much to think. Those capabilities and the foundation readiness
checks remain required before adaptive search.

## Public information and choices

Candidate indices resolve to the actual visible hand card, target enemy, offered card, shop item
and price, ancient relic option, map node and visible children, or deck-selection card. Public
deck/hand collections are pooled; hidden draw order, seeds, state hashes and action handles do
not become model inputs. Card identity and other identifiers are categorical, with printed cost,
damage, block, upgrade and flag descriptors shared across decision families.

The admitted adapter leaves the top-level phase as an integer. This encoder normalizes its own
copy and verifies the native phase field; it does not change the pinned adapter or engine.
The decoder covers all thirteen nonterminal native phases, including public combat selections,
bundle confirmation and the adapter's otherwise unnamed Fake Merchant phase.

There are honest limitations: printed card numbers do not resolve all live modifiers or card
effects. Event options lack effect text in the current adapter. The Crystal Sphere's revealed
board and the Fake Merchant's item stock are also absent, so those choices use the exposed legal
options without pretending to observe their contents. Missing printed metadata is marked.
Unsupported/malformed decisions and cycles remain failed attempts in the denominator.

## Frozen training and comparison

The pilot uses Ironclad, Ascension 0 and the admitted v0.107.1 engine. Its new seed universe is
100000–100999, with 800 training, 100 development and 100 sealed final-test seeds. Earlier
experiments used 000000–000999. Short compatibility smoke used only training seeds; no real
development or final-test games ran during implementation.

Within each generation, all candidates receive the same eight training seeds. Up to two leading
candidates and the incumbent receive the same sixteen **different** training seeds for
confirmation. Both panels rotate each generation. A candidate replaces the incumbent only if
its confirmation rank improves. Ranking is win rate first, bounded bootstrap progress second,
completion rate third, using the separately versioned [training score](full-run-training-score.md).
Repeated actions, extra decisions and failed/capped runs receive no progress reward.

The selected checkpoint is frozen before opening the 64 development seeds. The initial and
selected player receive the same development games and decision allowance. Development does
not select a checkpoint or trigger more training. If they are identical, the report says so and
reuses those identical games. The sealed final-test panel is untouched. This pilot cannot establish
SOTA, a matched PPO/GA training-cost advantage, calibrated run value or foundation readiness.

## Saved experience and integrity

Results live under `artifacts/full-run-evolution/sts2-v0.107.1-unified-pilot-v1/`:

- `protocol.json`, population/generation records and `train-selection.json` bind code, score,
  splits, ruleset, checkpoint identities, seed panels, mutation lineage and deterministic RNG seeds.
- `models/` retains the initial, evolved and discarded parameter sets.
- `cases/` preserves per-attempt public decisions, supplied legal candidates, chosen actions,
  public act transitions, true binary environment rewards, learner returns and measured CPU.
- Separate immutable `experience/train-index.json` and `experience/development-index.json` keep
  development records unavailable for fitting. Losing games and failed attempts remain represented.
- `evolution-report.json` records the comparison, unique attempts, episode cost and all experience
  index identities. Outer resource reports include process startup, serialization, discarded
  candidates and interrupted launch cost; episode CPU is not advertised as total training cost.

The player acts greedily. Saved softmax scores are **not** sampled behavior probabilities; the
recorded behavior probability is 1. A future PPO collector must explicitly sample and record its
actual probabilities. Full-run success or progress does not prove every action in that game good.
These are actual-return records, not fabricated causal preference labels.

`verify_episode_trace` checks saved public inputs, candidate binding, selected behavior, state
chains, hashes and scoring against the original checkpoint without replaying games. It does not
prove a counterfactual action is better or reestablish simulator conformance.

## Implementation verification

Synthetic checks cover every exposed decision family, object/handle permutation, forbidden
inputs, patch mismatches, genome/checkpoint identity, gradients through every layer, run-owned
splits, resumed populations, failed workers, immutable experience and frozen script caps.
A short real simulator check traversed 25 decisions; a separate two-process check recorded and
verified two 25-decision traces. Those intentionally truncated smoke checks establish compatibility,
not playing strength. No sustained evolution or complete-run benchmark was launched.

The first short worker check exposed a native-limit boundary error. Its failed traces are preserved
separately under `artifacts/compatibility/unified-full-run-policy-v1/`. The corrected check is under
`artifacts/compatibility/unified-full-run-policy-v1-retry2/`; it recorded the intended truncations.
