# A8 Act 1 teacher qualification and rescue curriculum

This study follows the [saved Act 1 loss audit](native-a8-act1-loss-audit.md)
under [#134](https://github.com/benyanc/spireshift/issues/134) and
[#35](https://github.com/benyanc/spireshift/issues/35). It prepares better
lesson data for a copied-checkpoint fit. The primary evaluation goal remains
genuine A8 full-run wins on fresh normal starts.

## Teacher and matched starts

Each seed starts three isolated native Ironclad/A8 runs at Neow for its
assigned initializer. The original and update-200 policies use their saved
weights and existing behavior. The teacher starts with the same fitted
policy proposal on each current public menu. It uses visible card HP costs,
combat scoring, the potion belt, the Rest option and map choices to choose a
legal alternative where its rules apply. Compact ordered answers keep the
existing policy. Profiles are fresh, and the runner uses the actual game
choices from the first Neow menu.

The runner checks the exact public inputs, legal menus, policy choices,
native receipts and successor snapshots against the compressed worker
journals. It records native loss when the game confirms death in Act 1.
It records a clear when a living player enters Act 2 after observed Act 1
boss combat and a delivered Continue from the native boss rewards. Time,
CPU, round and choice limits are separate incomplete outcomes. The complete
case denominator stays visible.

A strict rescue requires a loss from each reference and a teacher clear on
their shared seed. The first different teacher action must be verified
against the fitted action on the identical public menu after a common
choice prefix. A new isolated worker then reproduces the teacher's
successful public trajectory and Act 2 entry. This shows a successful
teacher continuation. The teacher can make several changes along that
continuation.

## Gates and data ownership

| Stage | Fresh worlds | Gate |
| --- | ---: | --- |
| Qualification | 8, four per initializer | Complete every arm, clear more often than each reference, and reproduce at least two strict rescues with both initializers represented. |
| Collection | 12, six per initializer | Finish the declared panel and reproduce at least three strict rescues with eligible labels, both initializers and all three target reasons represented. |

The recipe declares all seeds and thresholds before gameplay. The qualification
gate must pass before any collection world starts. The thresholds are admission
rules for this pilot. The audited development worlds, the qualification seeds
and the separate short-control seed supply zero fitting labels.

Each eligible collection world supplies only delivered teacher overrides for
HP spending, potion choices or Rest. Labels contain the legal public input and
selected action. The fitted proposal and intervention reason accompany each label
as provenance. Each admitted world contributes total label weight one. The
other choices remain in the trajectory evidence. Collection can preserve capped
cases in its denominator while admitting lessons from verified clears on other
worlds. Only a passing collection produces a bank manifest for separately
reviewed fitting.

## Frozen execution and owner run

The [versioned recipe](../configs/native-curriculum/sts2-v0.111.0-a8-act1-rescue-v1.json)
binds STS2 v0.111.0 / 41cef1ea, support build 60, the worker and converter,
the SDK, runtime and localization. It verifies the two originals, two
update-200 checkpoints and all four full Adam states. Execution-source
hashes are separate from CI and work-item text.

Close STS2 before running the command from this checkout.

```bash
bash scripts/collect-act1-rescues-v1.sh
```

The command verifies or prepares the three capped native prefix controls
before starting qualification. Allow about 15–35 minutes if both stages
run. The outer session cap is 90 minutes. Each game has a 90-second
wall guard and retains the frozen 128-native-CPU-second constraint.
The runner resumes clean sealed worlds and preserves uncertain deliveries
for inspection. Reports and the conditional bank live under
`artifacts/native-a8-act1-rescue/study-v1`. All stages perform zero optimizer
updates and stop after the declared work.

## Preparation checks

All 20 saved decision regressions passed. The new verifier reconstructed
321 saved native deliveries, covering one real Act 1 loss and one real
Act 2 entry. All 2,846 repository tests and the .NET protocol check passed.
The fresh native prefix check is pending. The first attempt stopped at
the open-game guard before starting a worker. The owner command runs
the short check before any qualification worlds if a passing receipt
is still absent. [Verification record](evidence/native-a8-act1-rescue-preparation-v1.json).
