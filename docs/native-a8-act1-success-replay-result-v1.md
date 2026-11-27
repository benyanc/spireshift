# A8 Act 1 success replay result

All 128 planned native games finished from Neow on 32 fresh worlds.
Both comparison arms lost all 64 games. Fitting produced one additional
Act 1 clear and no additional Act 2 clears.

| Initializer and arm | A8 wins | Act 1 clears | Act 1 bosses reached | Mean maximum floor |
| --- | ---: | ---: | ---: | ---: |
| Player 2 parent | 0/32 | 0/32 | 4/32 | 9.91 |
| Player 2 fitted | 0/32 | 0/32 | 5/32 | 10.22 |
| Player 3 parent | 0/32 | 0/32 | 8/32 | 10.78 |
| Player 3 fitted | 0/32 | 1/32 | 4/32 | 10.59 |

The fitted arm reached a higher floor in 15 of 64 pairs, tied in 32,
and reached a lower floor in 17. Its pooled mean moved from 10.34 to
10.41. The single Act 1 clear, by player 3, ended in a genuine loss
on floor 21. Neither initializer shows a repeatable gameplay gain in
this panel.

The fit took 256 updates per copy. On the 12 worlds held out from
this fit, average per-world choice loss decreased for both copies.
Highest-score agreement went from 57.6% to 59.3% for player 2 and
60.1% to 61.1% for player 3. This measures agreement with saved
decisions. Both fresh gameplay arms recorded zero wins.

The read-only audit reloaded both fitted states and their full Adam
state, verified 128 game seals and 17,036 native decisions, and
matched the initial public observations across all four games on
each world. The frozen game, runtime, SDK, localization and original
checkpoints and Adam verified. There were no failed, capped or
unattempted games and the audit made zero optimizer updates. The
result ID is
`sha256:82d5f75d90ab14595b4c01a84faa21bf9e636f5a7a6a7622e7e3982ca2209223`.

## Public card display input

The game supplied current card damage, calculated damage or block in
8,215 of 10,884 recorded combat menus. The dedicated damage and block
columns still read an older flat card field. It was empty on all 37,652
offered card plays in the evaluation. The public numbers were present
under the hand card's display view and reached the general compressed
input. Dedicated columns missed 24,136 damage and 12,185 block values.
The affected scope is the model's encoding of a legal combat play.

The [card display comparison](native-a8-card-display-v1.md) tests an
input path that connects each legal play to the current displayed
values of its physical card. It uses the exact completed replay fits
as matched comparators on new worlds.
