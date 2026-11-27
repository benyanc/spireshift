# Completed hidden-normalization comparison

The owner's v2 continuation finished on November 27, 2026 (14:31–17:04 UTC,
2 h 33 min, exit 0, no resource cap). Normalizing hidden values inside the
shared correction did not improve full-run A8 play. No candidate is promoted.

## Independent saved-only verification

`spireshift.native_normalization_result_v1` re-derives the whole study from the
journals without launching a game or changing any optimizer state. It verifies:

- **5,120 sealed units**: the 4,234 imported clean v1 units plus 886 new v2 units.
  Each seal's real file hashes, its declared behavior-state request and its link to
  the aggregate report are checked.
- **All four complete actor/critic/Adam lineages**. All 256 fits reload and match
  their declared state/model IDs. Actor and value Adam step counts grow exactly by
  each fit's update count. Each correction keeps the frozen source reference actor
  and its declared normalization method. The total is 15,714 copy updates:
  15,252 inherited and 462 new.
- **Native endings for every training and development game**. Each episode report
  matches its sealed outcome, native game-over/death facts, seed, A8, clean
  shutdown, independently verified delivery count and zero in-game optimizer updates.
- **The preserved failure**. `train-0993-p2-normalized` is still unsealed in
  study-v1, with 159 acknowledged prefix deliveries and its unknown discard. The
  exact request is reached by the restored round-63 lineage, and the failure is
  counted as failed. It was never replayed or fitted.
- The round-64 final states, the paired comparison tables and the linked seal
  denominator reproduce the saved report exactly. The frozen game, runtime, SDK,
  localization, archive, all four original/source full states with Adam, and the
  personal profile are unchanged.

The audit took 175 s wall / 117 s CPU, with a 210 MB peak. Its report is
`artifacts/native-hidden-normalization/assessment-v1/report.json`
(`sha256:9cf24f8a0bab7c5a7b6e3f87e0f770234e720907169c13bd6c1f4e666c9dab53`).

## Fresh development panel (128 worlds × 2 initializers per arm)

| Frozen policy | Full A8 wins | Act 1 clears | Act 2 clears | Capped | Failed / missing |
| --- | ---: | ---: | ---: | ---: | ---: |
| Plain reference (source finals) | 0 / 256 | 11 / 256 | 0 | 0 | 0 |
| Raw correction, round 64 | 0 / 256 | 11 / 256 | 0 | 0 | 0 |
| Normalized correction, round 64 | 0 / 256 | 9 / 256 | 0 | 2 | 0 |

By initializer, Act 1 clears for reference / raw / normalized were 7 / 5 / 7
(player 2) and 4 / 6 / 2 (player 3). The two caps are both player-2 normalized
games. Caps count as no progress in the intervals below.

These are world-clustered 95% bootstrap intervals for Act 1 clear-rate
differences (10,000 resamples, descriptive for these worlds):

| Comparison | Difference | Interval | Discordant pairs (treatment-only / control-only) |
| --- | ---: | --- | --- |
| Raw − reference | 0.0 pp | −3.9 to +3.5 pp | 9 / 9 |
| Normalized − reference | −0.8 pp | −3.1 to +1.6 pp | 4 / 6 |
| Normalized − raw | −0.8 pp | −3.5 to +2.0 pp | 7 / 9 |

There are no wins in any arm, so every win interval is degenerate at zero. That
does not show the true win rates are equal or zero. With 0 / 256, a rough
one-sided 95% upper bound is about 1.2% per policy.

The training games use changing policies and are diagnostic only. Act 1 clears
were raw 56 and 50, normalized 48 and 27, out of 1,024 per lineage, with one
Act 2 clear for normalized player 2 and two for raw player 3. By 16-round quarter
there is no upward trend in any lineage (for example p2-raw 8/20/16/12, p3-normalized 6/9/6/6).

## Diagnostic finding: an effect-free shop navigation cycle

Final normalized player 2 spends **37.8% of its development decisions** toggling
`Open inventory` / `Close shop inventory`. It does this in 26 of 128 games with over
100 toggles. Both capped games hit the 2,048-decision cap almost entirely through
this cycle (962 and 979 opens). The other arms toggle in 0.3–4.7% of decisions,
and the training policies in 0.7–8.3%.

Opening and closing the merchant inventory changes no game state. The current
framework still offers each step as a separate model-owned decision. Terminal-only
credit gives almost no gradient against an unbounded cycle that has no effect.
This is a shared decision-framework defect, not a fight tactic. It wastes decisions
and compute, distorts per-decision PPO weighting, and can end evaluations without
an outcome. It does not explain the zero wins: excluding caps, normalized and the
other arms remain within noise.

## Conclusion and next priority

Across the qualified model-only study, the capacity study and this
study (about 39,000 copy updates in total), no learner change has produced
a fresh-game improvement. A8 wins are zero and Act 1 clears stay around
4%. Changes to representation and conditioning are not the bottleneck at this
level. The learner gets no positive terminal signal and little usable credit.

Recommended order (not started; needs owner approval):

1. **Framework repair (short, autonomous-scale).** Audit all saved journals for
   model-owned action sequences that return to an identical public state with no
   native effect. Then expose the merchant inventory as compound choices
   (open + buy card/potion/relic, open + remove, leave), keeping every distinct
   native outcome reachable. Do this in a new versioned adapter with native
   lifecycle controls. Existing evidence stays unchanged.
2. **Learning bottleneck (owner-run long stage).** Prepare a matched test of a
   general policy-improvement operator in place of another PPO variant. Use
   fixed-budget, model-guided lookahead over the native engine for model-owned
   combat decisions, scored by the declared training score, and distill it into
   copies. Compare it with continued PPO on fresh normal starts, with failure
   denominators retained. It uses no hand-written fight rules, and the adaptive
   controller stays gated.

Reserved final-test worlds stay sealed. All study finals remain immutable
experimental artifacts.

Evidence: [native-hidden-normalization-result-v1.json](evidence/native-hidden-normalization-result-v1.json).
