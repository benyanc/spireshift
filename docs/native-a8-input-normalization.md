# Native A8 input-normalization checks and next comparison

The fixed input-scaling candidate passes saved-TRAIN controls and short native integration.
It reduces saturation on the sampled old checkpoints without losing their encoded inputs.
Whether it improves full-run learning still requires the owner-run comparison below.

## Implemented change

`native-actor-hash-quarter-v1` multiplies hashed actor coordinates by exactly 0.25 **after the
original token encoding, hashing and clipping**. The 18 direct action signals and the entire
critic input remain unchanged. It keeps all supplied actions, field names, amounts, ownership,
current costs, selection limits and public memory. It removes no duplicated fields. Scaling is
the sole treatment; deleting repeated views would introduce another information-loss question.

On the checked game inputs, multiplying those coordinates back by four recovers the previous
encoded vectors exactly. This preserves what was already encoded; it does not recover any
information lost by the original hashing/clipping or prove exhaustive interaction coverage.
No new candidate-vector aliases appear in the tested menus. Unit controls retain Strength versus
Dexterity amounts, effective costs, targets/intents, optional Skip, multi-selection limits,
declined-card history and merchant memory, while rejecting private/RNG/opaque input fields.

The normalization spec is recorded in each new actor's serialization and model identity. Old
checkpoints keep their original bytes, identities and interpretation. The default initializer
still has ID `d0fabf…f4449`; the normalized initializer has a distinct ID despite identical
initial numerical weights. Inference and exact behavior verification both apply the recorded
transform once. PPO receives those same encoded rows. The original public-token encoder and
frozen game environment remain separately identified; this is an explicit actor transform,
not a new game version or a silent checkpoint conversion.

## Saved-data controls

The source audit checks v5's **256 TRAIN runs / 26,061 decisions** and frozen source/seed/score
seals. No confirmation or development episodes are opened. The finite probe takes at most one
choice-bearing state per run per family and 24 per family: **278 states, 1,175 candidates,
13 families**. It is an intentionally bounded, nonuniform probe, not all gameplay states.

With the **same frozen historical weights**, hidden saturation (`abs(tanh) > 0.99`) is:

| Checkpoint | Unscaled, all probe states | Scaled, all probe states | Unscaled combat subset | Scaled combat subset |
| --- | ---: | ---: | ---: | ---: |
| Initial | 4.22% | 0.00% | 13.60% | 0.00% |
| Round 4 | 18.04% | 0.00% | 42.33% | 0.00% |
| Round 8 | 21.48% | 0.00% | 66.70% | 0.00% |

Each number averages candidate/hidden activations within a state, then gives states equal
weight. These figures use sensitivity probes of old weights, **not a newly trained normalized
player**. Future weights can grow and saturate again. The runner now records bounded,
deterministic saturation samples before and after every real training update so that the next
experiment can test persistence of the benefit.

Artificial Rest/Smith controls use two HP-conditioned labels per saved menu, with **8 fitting
games / 16 examples** and **14 other TRAIN games / 28 held examples**. Labels test conditional
learning; they are not optimal-gameplay labels or native-legal counterfactual fixtures. Both
encodings reach 100% held accuracy after 300 small supervised updates from both initial and
round-8 weights. Removing the HP distinction creates identical inputs with opposite labels,
giving exactly 50% accuracy and 50% mean target probability.

A supplemental control also updates **all three mirrored public player-HP fields** coherently,
including the player referent. On its 28 held examples, original/normalized accuracy is
100%/100% from initial weights and 96.4%/100% from round-8 weights. Normalized target probability
is 97.8% and 97.5%; negative controls remain at 50%. This checks that the result does not depend
on conflicting copies of the player's health. Hypothetical menu legality is still not asserted.

The primary check takes **19.35 seconds**, the supplemental check **8.84 seconds**, and each
attempt has a three-minute cap. There are **2,400 in-memory diagnostic optimizer steps**, zero
new games and zero production checkpoints from these controls. They establish a numerical and
limited learnability result, not stronger gameplay, value calibration or base readiness.

## Native connection

Fresh unscaled and normalized controls each finish **four games** with zero failures, missing
cases, app copies or protected-input changes. Together they verify **456 training decisions**
and **12 PPO updates**. The actor, critic and checkpoint reload paths pass, and saved cross-fitted
credit reconstructs. The unscaled result exactly reproduces the previous short control's
checkpoint, confirming preservation of the old numerical path.

Including resource wrappers, the controls take **24.26 and 20.92 seconds**, retaining about
**14.48 MB combined**. All eight games are losses. Their two-game post-update floor differences
are pipeline observations, not estimates of which method is stronger.

The [evidence record](evidence/native-a8-input-normalization-v1.json) binds source hashes,
private probes, coherent controls, native controls, resources and scoped admissions. There is
no new mechanics sweep, new game build, larger network, reward change or action-family freeze.

## One owner command

Close any open game, then run:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/compare-native-a8-normalization-v1.sh
```

This runs unscaled and normalized methods sequentially: **336 attempts each, 672 total**, eight
rounds of 32 training games per method. Both use the same initial numerical weights, zero Adam
state, cross-fitted credit, objective/bootstrap score, training seeds, sampling rules, PPO
settings and caps. The only changed setting is hashed actor input scale.

Input scaling can change the starting policy despite identical numerical weights. Consequently,
each method evaluates **its own initializer and its own best trained checkpoint**. Confirmation
freezes trained candidates before development; the retained incumbent is recorded separately.
Both methods share fresh confirmation/development seeds, disjoint from the inspected v5 and
credit-comparison panels. Historical training seeds are deliberately reused for the controlled
development experiment. Actual trajectories, update counts and runtime can differ.

Expect **25–40 minutes total**, with a hard **30-minute cap per method**, two workers, 4 GB memory
and 4 GB output cap per method. Expected retained output is about 0.6 GB combined, not guaranteed.
Both use the frozen native game and shared support-code cache; no app is copied. Every batch
reports wins, average floor, best game and failures. Failed cases keep their denominator and
never supply ordinary training targets. Completed methods are preserved/skipped; unfinished
evidence stops for inspection. No promotion, adaptive controller or further experiment follows.

The complete repository checks pass: **1,477 tests**, formatting, types and the native build.
Controls, scoped admissions and read-only preflight pass. **Neither long method has started.**
One training replication per method and 16 development seeds are exploratory. After completion,
assess paired gameplay differences and actual before/after-update saturation; if improvement
is still unclear, prioritize independent-run gradient/batch-size controls rather than assuming
that numerical conditioning alone solves delayed credit.
