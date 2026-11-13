# Expanded A8 demonstration fit

The original comparison stopped after 31 sealed losses. All 16 games
in the separately reported continuation ended in native Act 1 losses.
[Saved continuation result](native-systematic-selectors-v1.md#saved-a8-continuation-result).

The [archive-initialized PPO run](native-a8-archive-own-training-v1.md)
had zero wins and Act 1 clears across 32 training and 48 development
games. The 96 updates received different floor scores from losing runs.
The next comparison uses more independently successful normal starts.

## Selector evidence

Two source journals recorded opening Smith, cancelling the upgrade
selector and then healing. The shared reader now binds the actual
cancellation, checks the complete selector, and verifies the restored
rest menu and unchanged deck, HP and gold before Heal. Both replays
recreated their saved prefixes and proceeded from the defeated boss's
native reward screen into Act 2. Vantom entered Act 2 at 55 HP and
Waterfall Giant at 34 HP. Their 264 and 269 verified deliveries retain
their declared training and holdout roles, respectively. The qualification
report is `sha256:2b155e23aa2d2faa3989addadb26fcc17be91db4c03c364454bdfd5ff3292b67`.

The separate Armaments check verified the automatic upgrade of the exact
card and the next upgraded play. It continued for 82 more deliveries in
total before a later combat-end mismatch. That replay supplies zero labels.
All prior stops, their source snapshots, and the original admission result
remain preserved.

## Matched fitting

Both candidates start from their exact original weights and full Adam.
The five-world fits use the original three full-run victories and two
verified normal-start Act 1 clears. They keep the original 112 updates
per initializer and the same draws per world per update. The two added
worlds contribute 513 verified decisions. Every answer retains its full
legal menu and any ordered selection factors.

Two other native Act 1 clears supply 454 choice-bearing held-out decisions.

| Initializer | Three-world agreement | Five-world agreement | Mean joint loss, three to five worlds |
| --- | ---: | ---: | ---: |
| Player 2 | 51.7% | 50.5% | 1.190 to 1.184 |
| Player 3 | 51.6% | 54.9% | 1.189 to 1.167 |

This is a small offline signal. The fit report is
`sha256:7f9533165c2ae9c174a9abe7d021681b30afc6d35ca3a755cc95dc06720e9676`.
The comparison tests both exact three-world and five-world fits from
Neow on 12 separate worlds for each initializer, for 48 games. The model
scores and chooses from the full legal menu throughout. Full-run A8
wins are primary and Act 1 clears and floor provide diagnostics. The
launcher makes zero optimizer updates. Final-test worlds stay reserved.

The short native check verified four exact reloaded prefixes and one
terminal loss on a separate control world. The build, both original
checkpoints and both sets of fitted copies passed their frozen checks.
The control report is
`sha256:30bb11ac1de5e4fe905ba4f9daf2cc874de90f520e7b1bcee9b7565051fad293`.

Close STS2 and allow about 8 to 15 minutes, with a 30-minute outer cap.

```bash
bash scripts/compare-a8-expanded-archive-v1.sh
```
