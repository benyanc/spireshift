# World-balanced A8 fitting result

Both copies froze at update 200 on the admitted 25-world bank. The saved
audit checked 22 seals and independently reconstructed all 400 optimizer
updates, the two full checkpoint states and their offline metrics. Each
copy received 5,000 draws, 200 from each world. The original weights and
full Adam states, game and runtime hashes verify.

| World-averaged offline metric | Player 2 original → final | Player 3 original → final |
| --- | ---: | ---: |
| Fitting teacher-action loss | 1.709 → 0.519 | 2.091 → 0.569 |
| Held-out teacher-action loss | 1.959 → 1.194 | 2.034 → 1.179 |
| Held-out top-one agreement | 33.6% → 54.0% | 27.9% → 52.7% |
| Held-out combat top-one agreement | 31.8% → 49.0% | 22.1% → 48.1% |
| Held-out strategic top-one agreement | 38.0% → 66.5% | 44.3% → 64.6% |

The held-out metrics use 1,026 decisions from the six successful teacher
traces among twelve development cases. Both finals improved overall.
Map top-one agreement fell for both on 21 choices from four worlds.
Shop loss rose for both on seven choices from two worlds. Those small
strategic samples are diagnostics to track in gameplay.

The owner run used saved decisions. The audit reconstructed its numerical
work in memory, with zero new persisted updates or game launches. Both
finals are available for a separate gameplay comparison.

| Candidate | Adam step | Full state identity |
| --- | ---: | --- |
| Player 2 update 200 | 5,858 | `sha256:b2c65a650598711ecf4902341cd8d771976d010a2d52056e47f2240a99fd472b` |
| Player 3 update 200 | 6,245 | `sha256:cf25b32625fb71e1f356182ad97a6664f6de5b9e5d7f61738d4f904a38d7503c` |

## Gameplay handoff

Qualify the Architect terminal transition with valid native run history
under [#149](https://github.com/benyanc/spireshift/issues/149). The saved
prepared control loaded an Ancient map visit with an empty room list.
The victory progress code reads the Ancient event's model ID, and the
lookup returns null on that entry. The recorded run had already entered
the native victory persistence path. This fixture defect can explain
the observed crash. Confirm the ending, run history and persisted progress
on the current frozen build before deciding whether the host needs a repair.

Use both sealed finals and their corresponding originals in the separate
[#146](https://github.com/benyanc/spireshift/issues/146) paired normal-start
development comparison. Report genuine terminal victories and keep route
and shop outcomes visible alongside act and boss progress. Final-test
worlds remain reserved for a separately frozen confirmation.

See the [verification record](evidence/native-a8-world-balanced-fitting-result-v1.json).
