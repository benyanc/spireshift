# Matched A8 practice result

Mixed practice yielded zero full-run wins in 24 games. Normal-only
fitting and the frozen originals also yielded zero wins in 24 games
each. The 72 games completed on 12 matched normal-start worlds with
both initializers. Every loss occurred in Act 1.

| Arm | Full-run wins | Act 1 clears | Act 1 bosses reached | Mean maximum floor |
| --- | ---: | ---: | ---: | ---: |
| Original | 0/24 | 0/24 | 2/24 | 9.21 |
| Normal-only | 0/24 | 0/24 | 2/24 | 9.83 |
| Mixed practice | 0/24 | 0/24 | 2/24 | 9.63 |

Mixed practice finished above normal-only in two paired games, at the
same floor in 19, and below it in three. The fitted actors chose
differently in 23 of 24 pairs. Each first difference occurred on the
same public menu. Eight first differences selected bindings with
identical displayed labels. Neither fit produced an Act 1 clear, so
the panel has no evidence about how the added practice transfers to
normal-start play in Acts 2 and 3.

The saved audit reconstructed 11,591 native deliveries and checked
4,392 sealed files. All starts matched across the six games on each
world, and all endings and shutdowns passed. The terminal combat
owners were ordinary encounters in 44 games, elites in 22, and bosses
in six. Observed families included rewards, card selection, shops,
events, and combat. The panel exercised zero local ordered-answer
factors. Separate controls retain that coverage.

The build, existing weights, and all Adam states passed the freeze
checks. The audit launched no games and performed zero optimizer
updates. These worlds remain development-only.
[Saved verification](evidence/native-a8-matched-practice-result-v2.json).

## Next priority

Collect evidence about choices that affect early survival and progress.
The three-arm comparison changed choices and still produced 66 losses
before the boss. Its trajectories diverged after those choices. A
matched legal-action branch can compare two choices on the same
public state before any divergence, then observe their full native
continuations. The [action-credit pilot](native-a8-action-credit.md)
does this across combat, route, and resource decisions.
