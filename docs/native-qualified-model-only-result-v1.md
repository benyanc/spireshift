# Completed sustained A8 learning: small Act 1 gain, no full wins

The fixed study completed 2,046 valid normal-start training games and 7,101
copy updates. Its two previously failed-verification cells remain failed and
diagnostic, preserving the 2,048-cell training denominator. There were 71
training Act 1 clears, no Act 2 clears and no full wins.

All **128 fresh development games** finished with genuine native losses,
clean shutdown and no capped, failed or unattempted evaluation cells.

| Fresh development outcome | Frozen study starts | Trained round-64 copies |
| --- | ---: | ---: |
| Full A8 wins | 0/64 | 0/64 |
| Act 1 clears | 3/64 | 6/64 |
| Act 2 clears | 0/64 | 0/64 |
| Mean terminal floor | 11.45 | 12.75 |

Player 2 clears changed 2/32 to 3/32; player 3 changed 1/32 to 3/32. The pooled
Act 1 increase is 4.69 percentage points, with a descriptive seed-clustered
95% interval of **−1.56 to +10.94 points**. It remains inconclusive. Zero-versus-zero
win bootstrap values describe these observations; they do not establish equal
underlying win rates or competence. Both fixed initializers share 32 development
worlds, so this is not a population-level replication across many independent
training runs. Final-test worlds remain unopened and official strength is unqualified.

## Independent saved audit

The saved-only audit rechecks all 2,302 clean collection/fit/evaluation seals,
restores every one of the 128 full actor/critic/Adam fits, validates each exact
optimizer-clock increment and reconstructs each development game's act/floor
facts from its public journal. The rebuilt paired comparison matches exactly.
Final selection remains fixed at round 64. No development game supplied a label.

The audit made zero gameplay deliveries and zero optimizer updates. All original
and reference full weights/Adam, the frozen game, host60, Connector36, converter17,
SDK/runtime/localization and the personal profile remain unchanged. Preserve the
historical stops and both excluded chunks; no game was replayed for this audit.

The current source report is
`sha256:7fb7ccd0ae45ece19adfec8efcd6b52be557656b6db7bb1f2e803eed6e72cf13`.
Independent assessment:
`sha256:1fe9e3c8cf8f68ab79d753ea8257867d0efdb6b41f1c29513d6768b05c596111`,
at `artifacts/native-qualified-learning/assessment-v1/report.json`.

## Learning diagnosis and next test

This run establishes an operating learning loop, with weak results. Another
unchanged enlargement is not justified as the only next step. The shared policy
has 32 hidden units and 18,676 actor parameters. On 128 bounded, hash-selected
saved combat states, roughly 68% of the trained hidden activations have absolute
value above 0.95. They were about 76% for the starts. Some learning occurred;
saturation improved, and action-dependent hidden variation increased. These
measurements suggest testing added usable representation, not that insufficient
width has been proved or that all other learning bottlenecks are resolved.

The [controlled capacity comparison](native-policy-capacity-v1.md) increases only
the scoring network from 32 to 128 units while preserving its initial function
and every inherited Adam entry. It retains the same public input, one shared
scoring head, model-owned choices, objective, training score and PPO settings.
It compares continued 32-unit learning with wider learning, then evaluates both
against the frozen new finals on a larger fresh panel. It uses no fight scripts,
manual action labels or new game-mechanic rules.

Broader mechanics inventory rows remain partial. Encountered input/effect/ending
defects still require targeted repair; this result does not qualify every
provider, child owner or later-act combination. Keep the focus on a capable A8
base policy, and verify promising candidates in the shipped game before claims.
