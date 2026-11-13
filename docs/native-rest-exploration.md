# Rest exploration from both current Ironclad/A8 players

The preceding repaired-runtime continuation is complete: 960 attempts, 958 genuine terminal
endings, two failed games (one TRAIN, one development), zero full victories. Both failures hit
the old finite subset menu limit. All 256 final comparison attempts completed. On 128 paired
fresh test seeds, mean floor rose 10.6796875→11.3671875 (+0.6875; fixed-initializer seed-bootstrap
95% interval [-0.09375, 1.4609375]). This does **not** confirm improvement. Neither final trained
player cleared Act 1 on its final test; three clean TRAIN games cleared Act 1. Do not call these
floor scores victory probabilities or readiness. The new comparison changes exploration,
rather than automatically extending the same training unchanged.

## Selection repair

Pael's Tooth requested five of 21 deck cards: 20,349 subsets. Kifuda requested zero to three
of 15 cards: 576 subsets. The historical projector capped the materialized menu at 512 actions.
Increasing that cap merely moves the combinatorial problem.

The versioned v10 worker keeps small menus unchanged. Large menus expose one card addition at
a time, current selected cards **and their selection order**, explicit Confirm once the native
minimum is satisfied, and Cancel only when the native preferences permit it. Every valid native
subset and ordering remains reachable. Only Confirm/Cancel sends a game mutation; constructing
the prefix is a local public UI operation. Partial selections cannot produce training endings.
Empty confirmation remains distinct from cancellation. The game still owns costs, rewards,
card removal, enchantments, selection bounds and nested successor selections.

Each local delivery is recorded separately and independently replayed alongside the original
native/public streaming audit. A changed native selection instance, stale prefix, repeated card,
invalid confirmation or unbound UI command stops the worker. No frozen host, SDK, projection
cache, game assembly or existing helper is edited. No game app is copied.

Four privileged native checks cover two Pael removals (including reverse card order), Kifuda
three-card enchantment, and empty Kifuda confirmation. Prefix additions preserve the deck before
confirmation. These are scoped native effect checks, **not shipped UI parity, full games or
learning examples**. Failed development fixtures and their exact launch helpers remain private;
only `selection-effects-v4` is admitted for this comparison.

## One controlled learning change

The earlier clean TRAIN audit found 747 Rest choices versus two Smith choices, including 37
full-health rests while Smith was available. These observations motivate an experiment; they
do not prove every rest was a mistake or that forcing upgrades would be good.

Fork each current round-56 model **and its full Adam moments/counter** into two independent
learning arms. Player 2 starts at Adam 5268; player 3 at 5589. No weights are reset. No older
best checkpoint or control-trained checkpoint becomes the starting player.

- **Standard:** existing softmax sampling, temperature 0.8.
- **Rest exploration:** at native rest-site decisions only, sample from
  `q(a|s) = 0.8 × policy(a|s) + 0.2 / number_of_current_legal_actions`.

The mixture applies to **all** current legal rest choices, including additional relic-granted
options, Proceed and current potion controls when actually offered. Rest/Smith and potion or
Proceed counts are reported separately by their action labels. It imposes no health threshold,
fixed Smith action,
upgrade bonus, action mask or baseline-proximity penalty. Card selection, shops, deck building,
combat and every other strategic family keep learning. The same public encoder, architecture,
critic cross-fitting, return, optimizer settings, temperature and objective remain in both arms.

PPO records and verifies the actual mixed probabilities and differentiates the mixed distribution
in the likelihood ratio and entropy. A random exploratory choice is not mislabeled as ordinary
softmax behavior. Finite-difference checks cover the changed gradient. With zero mixture the
original gradient, optimizer updates and resulting model are exactly reproduced.

## Finite design and interpretation

Each arm receives **128 fresh TRAIN attempts per player**, four batches of 32, absolute rounds
57–60, three passes. Arms use matched seeds and per-seed random draws but retain their **own**
current-policy episodes and Adam states. Initializers 2 and 3 have disjoint seeds. Train/test
partitions and every previously reserved seed are excluded from overlap. Failed/partial/recovered
experience does not enter PPO. Failures stay in evaluation denominators as zero floor and wins.

Freeze all four final players after the fixed horizon. Then test each original and each final
player on 64 matched fresh seeds per initializer, with exploration **off** for every player.
There is no best-checkpoint selection, tuning, early test peeking or automatic extension.

Maximum **896 attempts**: 512 TRAIN plus 384 tests. Equal games/epochs and the same per-run CPU
budget do not imply equal total training CPU time; record actual computation and storage. Two
workers share immutable inputs and have separate profiles. Eight-game collection chunks and full
model/Adam commits resume after a clean pause. Failed/capped or uncertain work is preserved for
inspection, not automatically retried. Per-session caps: 15 minutes, 1,800 CPU seconds, 4 GB RAM
and 4 GB generated outputs; two-hour invocation cap. Expected duration: about 30–60 minutes,
subject to the actual run lengths and machine load. The owner runs the long comparison.

The primary comparison is rest-exploration-trained versus standard-trained on matched whole-run
seeds, reporting full wins, act clears, floors, failures and a seed-bootstrap interval. Each final
player versus its own original is secondary. Report TRAIN rest/Smith/other option counts to show
whether exploration happened, without presenting those counts as evidence of stronger play.
The uniform mixture increases coverage; it does not guarantee rapid reversal of an extremely
confident policy. If coverage improves without better play, investigate rest temperatures/entropy
or stronger action-credit/teacher signals rather than repeating the same batch unchanged.
Two initializers cannot establish generality across a population of training initializers. A floor
gain alone neither promotes a checkpoint nor admits adaptive search. A clear negative result is a
reason to revisit elite/boss combat or qualify a native teacher, not increase volume automatically.

## Provenance and execution

Import guards recheck the completed source report, final-state receipts, weights and all Adam
state, versioned numerical settings and objective, exact implementation, helper closure and native
effect evidence. Old raw game histories remain preserved provenance; the new learner does not
consume or repeatedly rehash all ancestral raw journals. Historical source/config/report bytes
stay unchanged. Each new collection retains bounded streaming audits, not all game histories in
memory.

The short integration control is a separate 20-attempt experiment. It checks both initializers,
both arms, four nonzero-Adam fits, ordinary final testing and safe resumption. Its updated weights
and seeds are excluded from the long comparison. See the evidence JSON for the completed control
and repository verification. The control completed **20/20 attempts**, zero failures,
four round-57 fits and 33 optimizer updates; its completed result reconstructs exactly.
It took 192.70 seconds over two clean sessions, peaked at 743 MB RAM and retained 40.98 MB
of outputs. This is an integration result, not a playing-strength result.

[Preparation evidence](evidence/native-rest-exploration-v1.json).

The long comparison remains unstarted when this handoff is prepared. Close any running STS2 game,
then run this single command:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/compare-native-a8-rest-exploration-v1.sh
```

A clean rerun resumes the same finite experiment. After completion it verifies saved results and
starts no more games. `--plan` and `--status` are read-only inspection modes.
