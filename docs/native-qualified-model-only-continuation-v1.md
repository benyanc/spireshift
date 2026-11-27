# Sustained A8 training: saved assessment and continuation

**Superseded owner command:** the v3 run exposed a checker assumption that an
unused cursor file always exists. The [v4 handoff](native-qualified-model-only-continuation-v2.md)
handles the actual absent-file case, verifies it on saved and fresh normal-start
games, preserves both failed cells and resumes only the 900 unstarted games.
The assessment and original evidence below remain historical and unchanged.

The November 24 owner run stopped during saved card-answer verification. It did
not reach the fresh development comparison. The completed games and copy updates
are reusable; there is no evidence yet that this study improved full-run wins.

| Copy | Sealed training games | Full A8 wins | Act 1 clears | Act 2 clears | Completed fitting rounds | Copy updates |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Player 2 | 576 | 0 | 14 | 0 | 36 | 1,956 |
| Player 3 | 570 | 0 | 19 | 0 | 35 | 1,857 |
| Total | 1,146 | 0 | 33 | 0 | 71 | 3,813 |

These are changing-policy training outcomes, not a comparison with the frozen
starts. The training denominator remains 2,048: 1,146 sealed games, one preserved
failed-verification cell, and 901 unstarted games. All 128 development cells are
unattempted. The small number of Act 1 clears and absence of Act 2 clears show
that the player remains weak. Finish the fixed study and fresh comparison before
choosing another learning recipe; do not patch individual fights from this run.

## Cause and scoped repair

The production worker already uses `ExecutableCardAnswerPlanner`: an enchant
answer must select at least one card before native confirmation can finish.
The historical saved checker still used `OrderedAnswerPlanner`, which retained
the underlying stored minimum of zero. In the stopped Gnarled Hammer selection,
three correctly reconstructed local responses differed only in `min_select`
(old checker: zero; executable domain: one).

The new versioned saved checker uses the qualified executable domain. The saved
game reconstructs all **191 native deliveries**, three local factors, one exact
ordered native commit, every policy choice/probability, a genuine native loss,
and a clean shutdown. No game is replayed to obtain this proof. This is a checker
integration defect; no game, combat or menu implementation was changed.

The full source/hash audit verifies 1,217 completed collection/fit seals and
reloads all 71 copied states, including their separate actor/critic Adam and
exact step increments. Frozen build, runtime, SDK, localization and all original
full checkpoint/Adam checks pass. The shared personal profile is unchanged.
Both historical failed resource attempts and the unsealed chunk remain intact.

Conservatively, the failed-verification game remains diagnostic and supplies no
training label. The affected player-3 round uses its other 15 complete games,
which meets the original minimum of 12. Its failed cell remains in the round and
study outcomes. No replacement seed or extra optimizer replay is introduced.
Subprocess verifier failures now produce a durable stopped-study summary.

The tests cover corrected enchant minima, higher native minima, ordinary empty
answers, cancellation, small direct answers, changed physical ordering, altered
prefixes, wrong successors, false delivery domains, extra ledger entries,
immutable imported updates and exclusion of the failed cell from fitting.
The same complete public-frame and policy-probability reconstruction remains
required. Broader mechanics inventory rows remain partial; this checker repair
does not qualify unrelated providers, child owners or later-act combinations.

## Owner continuation

Close STS2, then run:

```bash
bash "/Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/continue-a8-qualified-model-only-v3.sh"
```

Allow **3–5 hours**, estimated from the saved run. The original 24-hour outer
limit remains. The command verifies the saved control and assessment, adopts
the 1,217 exact completed units under the predecessor lease, runs only 901
unstarted normal-start training games, and then runs the original 128-game
fresh comparison. It never opens the failed chunk, replays a completed game or
repeats a sealed fit. New uncertain/incomplete units stop for inspection.

The final round stays fixed at 64. Seeds, inputs, all legal model-owned choices,
PPO, bootstrap score, terminal-victory objective and per-game guards are unchanged.
Only copied checkpoints update. There are no replay labels, fight rules, teacher
takeovers, automatic promotion, final-test games or official-strength claims.

The old launcher and study-v2 evidence remain immutable. New results are stored
in `artifacts/native-qualified-learning/study-v3`; the saved-only assessment is
`artifacts/native-qualified-learning/recovery-v1/report.json`, report
`sha256:3574cfad0b3b2d6d0783fb504805454968bfa0c6ebcb2eb199a08b263d4f47b6`.
See the compact [evidence](evidence/native-qualified-model-only-continuation-v1.json)
and the original [study declaration](native-qualified-model-only-v1.md).
