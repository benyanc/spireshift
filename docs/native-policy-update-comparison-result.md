# Completed controlled PPO comparison

All **256/256 planned attempts** finished cleanly: 128 sampled training games and
128 independent original-versus-updated evaluation games. There were **zero failed
games and zero app copies**. Both original player files and every Adam moment/counter
remain unchanged. Copies received **450 optimizer steps**; training was not skipped.

| Fixed player | Original average floor | Updated average floor | Change | Paired 95% interval |
| --- | ---: | ---: | ---: | --- |
| 2 | 12.15625 | 11.59375 | -0.5625 | [-1.875, 0.84375] |
| 3 | 11.125 | 10.75 | -0.375 | [-1.75, 0.9375] |
| Equal-player pooled | 11.640625 | 11.171875 | -0.46875 | [-1.375, 0.4375] |

Every evaluation arm has **0/32 wins and zero completed acts**. The pooled interval
resamples the 32 shared native worlds jointly across the two fixed initializers;
it does not describe a population of possible trained networks. All-zero observed
win differences do not establish zero true win probability or policy equivalence.

The point estimates are lower, but the intervals include improvement and decline.
This trial establishes **no useful improvement and no statistically clear regression**.
It cannot identify whether limited independent experience, actor representation,
the coarse baseline, optimization or delayed action credit caused the result.
Do not infer that PPO cannot learn the game, or that another two rounds will repair it.

Each updated player received only 64 additional training games, not 256. Across the
four fitting batches there are **18,953 decisions / 14,299 choice-bearing decisions**,
128 complete training games and 450 actual updates. These decision rows are related
within games; they are not 18,953 independent full-run outcomes. Final behavior KL
is 0.0055–0.0078; all four fits reach the fixed three-epoch limit. The state-only
baseline's cross-fitted explained variance is 0.24–0.32. It explains some return
variation but still omits card composition/relic identity. Neither the positive
explained variance nor correct signed-gradient tests establish good action credit.

The saved-only assessment verifies **151 sealed units / 7,021 source files** and
reconstructs the paired result. It reuses the sealed native delivery/probability
audits; it does not rerun games, refit weights or independently simulate effects.
See [portable evidence](evidence/native-policy-update-comparison-result-v1.json).

## Agreed follow-up order

1. **Small understandable native A8 decision-learning controls.** Use finite
   actual-engine branches to establish answers, then compare sampled-reward learning
   and direct teaching on isolated copies. Separate fitting from held-out whole
   seeds and report duplicate public states. A short-horizon diagnostic is neither
   a new full-run reward nor ordinary PPO experience. Target choice and discounted
   card sequences remain additional cases, not prerequisites for the first controls.
2. **Structured public inputs versus hashing.** Keep the engine, score and complete
   legal action menu fixed. Give identities, current quantities/costs and their owners
   explicit representations; preserve targeting relationships. Separate representation
   changes from network-capacity changes and report parameter counts/CPU costs.
3. **Richer state-only value baseline and actual learning comparison.** Validate on
   whole games, with independent fitting/selection, regularization and error curves.
   Keep the action-conditional predictor separate; a better MSE is not a better player.
   Shorter-trace TD/GAE is a separate controlled option only after value evidence.
4. **Larger and more varied bounded experience.** Declare fresh seed/compute budgets,
   measure independent games as well as decisions and updates, retain failure counts,
   and freeze a fresh evaluation. No automatic thousand-game or larger-batch launch.
5. **Stronger qualified teachers.** Compare competent native planning/demonstrations
   and imitation followed by full-run RL when labels distinguish useful alternatives.
   Fixed-world privileged evidence must not become public-belief search or ordinary PPO.

Keep progress bootstrap separate from win-first evaluation. Check sampled/greedy
behavior consistently, learning signal per decision family and changes in actual action
probabilities. Do not add health/upgrading rewards or retune on these development seeds.
Other difficulties, larger unchanged GA, adaptive thinking and checkpoint promotion stay
deferred. Each material change needs its own bounded comparison before another is layered on.

The earlier [preparation and owner command](native-policy-update-comparison.md) is
historical. Re-running it displays the completed result; no repeat is needed.
