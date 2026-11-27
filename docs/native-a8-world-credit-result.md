# A8 world-credit study result

The study qualified both initializers for fitting. Training returns
varied on seven of eight worlds for player 2 and six for player 3,
against a minimum of four each. All 48 training games completed as
native Act 1 losses. The pooled and within-world copies took 29
updates each for player 2 and 28 each for player 3. Value weights
matched within each fitted pair.

| Arm | Full-run wins | Act 1 clears | Act 1 bosses reached | Mean maximum floor |
| --- | ---: | ---: | ---: | ---: |
| Original | 0/16 | 0/16 | 2/16 | 9.94 |
| Pooled | 0/16 | 0/16 | 2/16 | 9.50 |
| Within-world | 0/16 | 0/16 | 3/16 | 10.81 |

All 48 evaluation games completed on eight fresh worlds. Each arm
recorded zero wins and zero Act 1 clears. Against either comparison
arm, the within-world fit finished higher in six pairs, tied in eight,
and finished lower in two. It gained 1.31 floors over pooled and 0.88
over the originals on average. The descriptive interval for the
change against the originals was −0.25 to +2.13 floors, resampling
worlds jointly across both initializers.

## Saved verification

The audit checked 5,862 sealed files and 14,603 native deliveries
across training and evaluation. It verified the separate first
draws on each training world, exact checkpoint and Adam identities,
matched optimizer work, and raw evaluation menus, policy choices,
successors and endings. The game, runtime, and original full states
passed freeze checks. The audit made zero optimizer updates and
launched zero games. [Audit evidence](evidence/native-a8-world-credit-result-v3.json).

## Next priority

Keep the within-world copies as a reference and test an earlier
training signal. A [saved temporal credit screen](native-a8-temporal-credit.md)
showed better held-world forecasts and more consistent actor update
directions for the shorter trace. The follow-up compares exact matched
copies on fresh normal-start A8 worlds.
