# Saved result of the paired A8 development comparison

All 48 declared normal-start Ironclad/A8 games reached a verified terminal
loss. Each checkpoint played the same 12 fresh worlds. The saved audit
verified the seals, same-world starting menus, native endings, clean worker
exits, and 6,948 delivered choices.

| Player | Checkpoint | Full wins | Act 1 boss reached | Act 1 cleared | Mean farthest floor |
| --- | --- | ---: | ---: | ---: | ---: |
| 2 | Original | 0/12 | 4/12 | 0/12 | 11.75 |
| 2 | Update 200 | 0/12 | 2/12 | 1/12 | 10.75 |
| 3 | Original | 0/12 | 3/12 | 0/12 | 11.58 |
| 3 | Update 200 | 0/12 | 2/12 | 0/12 | 10.08 |

The fitted player 2 cleared Ceremonial Beast in world 7 and reached floor 21
in Act 2. The other 47 games ended in Act 1. The originals reached seven Act 1
bosses across 24 games, and the fitted checkpoints reached four. The earlier
offline agreement gains yielded no wins on this development panel. The
per-game map, shop, and combat records remain available for diagnosing Act 1.
Final-test worlds stay reserved.

## Recovery and provenance

The owner process sealed every game, then failed while checking the inherited
protection manifest. The Windows CI matrix edit changed its pinned
`.github/workflows/ci.yml` while the process was active. The failed resource
receipt and all 48 original seals are preserved. The process stopped before
its final shared-profile comparison.

The saved-only audit loaded the original execution commit `da63b75` in a
detached checkout with copy-on-write copies of the private artifacts. The
historical checks ran against the original workflow bytes. The audit verified
every other protected file in the active checkout and matched the raw start,
ending and delivery evidence against each sealed cell. A separate check
verified the active game build, runtime, and all four full checkpoints with
Adam. The successful CI change `761a7ce` remains the current workflow.

Recovery launched zero games and performed zero optimizer updates. Its report
has a separate identity from the failed owner attempt. Use a separate checkout
for repository edits during future active runs, and bind new experiment
manifests to their execution inputs. See the
[saved verification record](evidence/native-a8-paired-finals-result-v1.json).
