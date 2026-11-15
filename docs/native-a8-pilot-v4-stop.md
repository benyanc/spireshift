# Native A8 pilot v4 stopped during worker setup

The owner-run pilot stopped before the first game in round 6. It saved five training rounds,
393 optimizer steps and 16,345 verified training decisions. Of 336 planned games, 192 were
recorded: 191 normal losses and one failed game. The remaining 144 were not played. There are
zero wins; the independent development comparison was never reached.

The 16-seed confirmation average changed from 7.5625 floors initially to 7.875 after round 4.
Those seeds select the checkpoint and do not provide independent evidence of generalization.
The training-round averages also use different seeds. Neither establishes a stronger player.

## What stopped it

Both `round-006-sampled/worker-*-failure.json` records say
`Native worker failed: spawnSync git ETIMEDOUT`, with zero recorded games. Their partial
`player-projection` directories contain Git metadata but lack the required environment module.
The worker's preparation helper clones the local shallow Headless checkout for every new
worker, under a ten-second Git timeout. These are support-code copies, not game-app copies.
The saved evidence locates the failure in local checkout setup; it does not establish an
internet outage or a failure of the trained model. Future failures should name the exact
setup command and phase instead of retaining only Git's generic timeout message.

The failure allowance covers isolated failed games whose worker shutdown and prior deliveries
can be audited. A worker that fails before initialization supplies no game record. The current
runner therefore stops the pilot rather than treating 32 missing games as completed or
silently replacing an uncertain worker.

A separate earlier failure occurred on training seed 106. Playing a card opened `card_select`;
the next sampled action tried to discard Heart of Iron. The native response reported that the
exact potion remained in slot 0. The game was excluded from PPO, its worker retired, and the
remaining planned games continued. This identifies a nested-choice/potion-delivery gap; native
queue ordering and actual UI availability still need a focused reproduction before choosing
the repair. Do not claim the discard succeeded or automatically resubmit it.

The original resource report records 655.70 seconds, 671.52 CPU seconds, 1.45 GB peak memory,
195.62 MB retained output and zero game-app copies. No resource cap fired. The master game,
runtime, SDK and account profile all passed their unchanged-input checks. A later disk check
showed approximately 52 GiB available; disk exhaustion is not indicated by these errors.

## Next work before another pilot

1. Remove repeated Git cloning from worker startup. Prepare and verify local projection code
   once, keep it immutable, and retain separate process-local sessions, ledgers and profiles.
   Qualify simultaneous cold startup, cache drift/interruption and reset behavior. Record setup
   phases and failure operands; do not solve this by allowing unbounded startup time or retries.
2. Reproduce and repair potion discard during a pending combat card selection. Check native
   availability, queue acceptance and delivery across completion of the choice, including stale
   slot/ID rejection. Preserve genuine optional actions; do not force a choice or infer delivery
   from an unchanged potion belt.
3. Bind a new recipe/admission to the repaired implementation, run bounded worker and neural
   integration controls, then prepare one separately named owner-run learning pilot. Preserve
   v4's failures, initial/round checkpoints and optimizer states; do not overwrite or silently
   resume v4 after changing its pinned inputs. A full unchanged mechanics sweep is not required
   by these targeted fixes.

The result checker now gives stopped pilots a readable summary plus original worker/game
errors, without a quality verdict. Its v2 selection audit also uses the learner's exact bounded
act/floor score. The historical v3 regression still selects the same checkpoint and remains
inconclusive. All checks in this follow-up read saved evidence only; no game or training was
launched. Evidence: `docs/evidence/native-a8-pilot-v4-stop-v1.json`; work item: #146.
