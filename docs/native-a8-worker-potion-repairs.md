# Native A8 worker startup and queued-potion repairs

The v4 pilot remains stopped, with all checkpoints and failures preserved. Host v34 and worker
v9 repair its two observed infrastructure problems. The separately named v5 learning pilot is
ready for the owner to run; it has not been launched.

## What changed

Worker startup now prepares one immutable copy of the pinned local support code, with no Git
clone. Warm starts verify its bytes and existing SDK link without running Git. A bounded lock
handles simultaneous preparation. Changed, extra or interrupted cache files cause an explicit
failure and remain available for inspection. Each worker still owns its own Node process,
native game process, session, navigation state, ledger and profile. No game apps are copied.
Native startup errors now identify projection verification, native launch or runtime identity.

The shipped game's potion UI allows discard while a card action is gathering a selection.
Its native discard waits behind that action. The former host incorrectly required the potion
to disappear immediately and reported unknown delivery. Host v34 now records acceptance of
the exact native queued action, disables the already queued potion holder, rejects duplicate
or stale-slot submissions and lets the native queue remove it after the selection finishes.
It retains other current optional actions. Queue internals remain private diagnostic evidence;
they never become learner inputs. The licensed game DLL and game effects are unchanged.

## Checks completed by Codex

- The saved failed train-seed-106 public prefix was replayed twice per host: both old-host
  failures reproduced, and both repaired-host queued discards settled correctly. These are
  diagnostic prefixes and negative controls, with no full runs or PPO examples.
- Twelve natural diagnostic games completed with no failures. Serial, parallel and reset
  semantic traces agreed. All three native processes reused one support-code cache, while
  profile read/write and shared-code write sentinels enforced isolation.
- Twenty-five potion controls passed, covering native effects, real/fake merchant targets,
  inventory round trips and stale operands. The new host's act/ending fixture also passed;
  forced fixture endings do not count as player victories.
- A four-game neural control passed with no failures, 228 verified sampled decisions and six
  optimizer steps. Actor and critic parameters changed. These four losses demonstrate pipeline
  integration, not improved gameplay.
- A saved-only input audit passed 5,175 ID-renaming comparisons across 1,725 public observations.
  The repository check passed 1,413 tests, formatting, types and the C# build.

The build took 21 seconds; queued-potion controls 12 seconds; worker checks 18 seconds; potion
controls 26 seconds; lifecycle check 4 seconds; neural control 21 seconds including validation.
All were capped short jobs. Frozen candidate, runtime, SDK, game archive and account profile
checks passed. All checks created zero app copies. The unchanged 1,849-case mechanics inventory
was verified from saved evidence with its original host-v32 scope, not replayed or relabelled.

## Owner's next command

```bash
bash scripts/train-native-a8-ppo-v5.sh
```

Run from this repository, with any Steam game closed. Expect approximately 10–20 minutes;
limits remain 30 minutes, 3,600 CPU seconds, 4 GB memory and 4 GB generated output. This is a
fresh run from the original seeded numerical initializer and zero Adam state. It retains eight
rounds of 32 sampled games, 336 total planned attempts and fixed Ironclad/A8 rules. All decision
families remain learnable. Evaluation retains the frozen stochastic policy and paired RNG.

The script displays each completed batch's best game, average floor, wins and failures, chooses
its checkpoint on confirmation seeds, then compares on reserved development seeds. An isolated
failed game stays in the denominator and supplies no learning targets; its worker is retired.
It permits at most two failed games per panel. Evidence corruption or an uncertain worker
shutdown still stops the run. Re-running a completed script only displays its saved result;
an unfinished workspace is preserved without an automatic restart.

Share the final output before any next experiment. No controller training, checkpoint promotion,
GA batch, full mechanics sweep or next experiment follows automatically. Success here means an
auditable complete pilot; full-run victories and independent improvement remain unproven.

Machine-readable references: [repair evidence](evidence/native-a8-worker-potion-repairs-v1.json).
Work item: [#146](https://github.com/benyanc/spireshift/issues/146).
