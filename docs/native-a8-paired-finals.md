# Paired A8 gameplay comparison

The [saved development result](native-a8-paired-finals-result.md) verifies all
48 terminal games and records the original final-check failure.

## Architect persistence

The short check used a fresh private profile on frozen STS2 v0.111.0 / 41cef1ea
with headless support build 60. It enabled native saving in the diagnostic
process and used the game's own map entry to create Ancient and boss room
history in each act. The checker jumped to the boss coordinates and forced
three boss defeats to reach Architect quickly. It then used the ordinary
Architect options.

The game returned explicit victory, removed its active run save and wrote
exactly one winning history record. A new native save manager reloaded that
record and the profile without repair. The saved history contains an Ancient
event and boss room in each act, and Ironclad's profile wins went from zero to
one. The frozen files and shared game profile passed before-and-after checks.
The diagnostic contributes zero gameplay evaluation wins. The two preliminary
attempts remain recorded. One stopped in checkpoint preflight and one stopped
at a stale member lookup in the checker before the first boss.

## Development panel

Compare the two [update-200 finals](native-a8-world-balanced-fitting-result.md)
with their respective originals on 12 predeclared, fresh normal-start worlds.
All four policies play each world, for 48 games. Original and fitted launch
order alternates across worlds and initializers. Each world has the same
verified starting public inputs and uses the existing policy-only adapter with
greedy combat and world-coupled sampled noncombat choices. Each game uses a new
isolated benchmark profile.

Explicit native victory is the primary outcome. The report retains wins,
losses, caps, failures and unattempted cells in the planned denominator, plus
matched outcomes for each initializer. It records act and floor progress,
bosses reached and cleared, map destinations, and delivered shop choices and
gold observations. Fully observed outcomes receive a descriptive 95% bootstrap
interval resampling worlds jointly across both initializers. If a game has an
unresolved outcome, the report gives win-rate difference bounds over the
planned worlds. This is a development comparison. Final-test worlds stay
reserved for a separate confirmation.

The owner run uses the frozen 128 gameplay CPU-second objective and the
inherited 90-second, 2,048-choice and 30-round guards. Clean sealed games can
resume. A failed or uncertain delivery stops the launch and preserves the
unsealed evidence. The run uses the original and fitted full states read-only,
with zero optimizer updates. The isolated Architect fixture enables saving
only inside its diagnostic process. The owner panel uses ordinary native
benchmark starts and its terminal facts.

The short control used a separate world. All four checkpoints had the same
initial public input and menu. The verifier reconstructed all 24 delivered
choices from the raw observations and receipts, and every worker shut down
cleanly. At preflight the 48 main games were unstarted. See the
[saved verification record](evidence/native-a8-paired-finals-preflight-v1.json).

The historical owner launch used the following command.

```bash
bash scripts/compare-a8-fitted-v1.sh
```
