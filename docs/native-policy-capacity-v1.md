# Controlled shared-policy capacity comparison

The [completed sustained study](native-qualified-model-only-result-v1.md) has
zero fresh A8 wins, 6/64 trained Act 1 clears versus 3/64 for its starts, and no
Act 2 clears. The next experiment tests a larger policy rather than prescribing
solutions to individual encounters or repeating unchanged training alone.

## One model change, common starting behavior

Both methods start from copies of the exact two assessed round-64 finals,
including full independent actor and critic Adam state. The source finals,
all historical original/fitted states and the game stay frozen.

| Property | Continued policy | Expanded policy |
| --- | --- | --- |
| Scoring heads | One shared head for all action families | Same |
| Hidden units | 32 | 128 |
| Actor parameters | 18,676 | 73,012 |
| Public input dimensions | 564, including current card display and total intents | Same |
| Critic | Existing 565-parameter critic | Initially identical |
| Initial decisions and likelihoods | Frozen final policy | Identical, checked to numerical tolerance |
| Inherited weights and Adam | Retained exactly | Retained exactly in their corresponding coordinates |

The added units have deterministic random input weights and zero output
coefficients. They initially contribute nothing to logits, preserving all
starting probabilities. New Adam moments are zero; inherited actor/critic clocks
are retained. New units use the restored global actor clock. Every parameter
remains learnable. This tests the larger model under the fixed learning process,
not a theorem about width independent of initialization or optimization.

Both methods use the same stochastic sampling contract and common native worlds.
Sampling keys do not depend on model identity. Each scores the full current legal
menu, including skips, targets, potion controls and compound answers. No fixture
choices, replay imitation labels, teacher takeover, fight rules or action masks
are introduced. The game and adapters remain unchanged.

## Fixed learning and evaluation

| Stage | Declared work |
| --- | --- |
| Fresh training | 64 rounds × 16 worlds × two initializers × two methods = **4,096 games** |
| Learning | Same PPO, critic update, training score and objective; both methods learn all decision families |
| Method ordering | Alternates by round and initializer |
| Candidate selection | Fixed round 64 for each method, before opening development |
| Fresh evaluation | 128 disjoint worlds × two initializers × reference/continued/expanded = **768 games** |
| Reference | The newly completed study's exact frozen finals, not a selected intermediate checkpoint |
| Primary outcome | Genuine native full-run Ironclad/A8 victory |
| Diagnostics | Act 1/2 clears and terminal floor; failed/capped/missing cells stay in denominators |

Equal fresh world counts and fixed learning settings are intentional. Trajectories
and optimizer-step counts may differ as the models learn; no equal-compute or
matched-optimizer-work claim is made. The standard method controls for simply
continuing training. The frozen reference measures whether either method improves
over the current finals. Three paired comparisons use world-clustered intervals
across the two fixed initializers. A positive development result still needs
independent confirmation and official validation. The old evaluation worlds and
reserved final-test worlds are never fitting labels.

## Admission controls

The short phase checks all 114 qualified mixed menus for both initializers,
including the actual inference and PPO encoders. Every paired initial likelihood,
sampled choice and critic value must match. It then collects two fresh normal
worlds per method and initializer: eight full games, with four exact matching
native trajectory pairs before learning. Each disposable copy receives two
actual PPO updates, is saved/reloaded with its full Adam, then completes a new
normal-start game. The main study starts from the original prepared copies,
not the short phase's updated copies.

The controls require twelve genuine endings, eight disposable copy updates,
clean shutdown/reset, unchanged personal profile and exact frozen inputs. Missing
or inconsistent evidence fails closed. Existing complete units can be rechecked;
unsealed or uncertain gameplay is preserved without retry or silent replacement.
Saved fixture states are used only for compatibility, never as reward labels.

The controls passed: 114 mixed menus, 228 paired likelihood checks (maximum error
3.55×10⁻¹⁵), four matching native trajectory pairs with 1,040 matching choices,
and all twelve full games. There were 2,516 native deliveries and zero local
factors. Each of four disposable copies received exactly two updates and
completed its post-reload game. All control endings were losses; this is an
integration result, not evidence of playing strength. A clean pause before the
four unstarted reload games is preserved. The second short invocation reused
all collection/fit seals and performed only those four games. Nothing repeated.
Control report: `sha256:529f15117b3aed6b3fdf72f5e357cde119b2862a5db586623edf54690ebefef5`.
The compact [evidence](evidence/native-policy-capacity-v1.json) links the source.

## Owner command

Close STS2, then run:

```bash
bash "/Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/compare-a8-policy-capacity-v1.sh"
```

Allow **14–24 hours**, estimated from the completed sustained run and short
controls. The outer cap is 48 hours, with the pinned numerical runtime,
24 GB output-storage cap and 4 GB memory cap. Per-game safeguards and the
128-native-CPU-second objective remain unchanged. These are operating limits,
not the research goal. Code, native build, source full weights/Adam and recipe
must remain fixed while the run is active.

The launcher verifies the exact passing controls before starting. Clean sealed
units can resume after a clean pause; interrupted or changed units stop for
inspection. No automatic next experiment, promotion, A10 validation or adaptive
controller follows. Source history is preserved under
`artifacts/native-qualified-learning`; new source copies, controls and results
are under `artifacts/native-policy-capacity`. Resource tracking reports only the
new workspace; the immutable prior study is an input and is excluded from that
new-output cap. No extra working-game app is created.
