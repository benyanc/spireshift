# Boss-focused Act 1 teacher qualification

The v1 run sealed all eight worlds and recorded seven reward-loop caps
in the boss-teacher arm. Use the [verified v2 repair and owner command](native-a8-act1-boss-reward-lifecycle.md)
for fresh qualification.

The first teacher reproduced two Act 2 entries in qualification. It reached
three bosses in seven complete collection worlds and lost all three with
substantial enemy HP remaining. The new qualification compares a teacher
that prepares for those fights and plans how to spend energy during them.
[Prior result](native-a8-act1-rescue-result.md).

## What the teacher changes

The boss teacher starts from the survival teacher's legal proposal. It claims
available card and gold rewards before leaving the reward screen. It rates
card rewards using visible damage, block, cost, HP cost, scaling, and the
current deck's attack mix. It can skip weak additions. At an Act 1 boss, it
considers up to four visible card plays at a time and ranks sequences by
damage, enemy kills and projected incoming damage. It checks energy, each
physical card copy and cumulative HP cost. It can use an available potion
when the public boss state warrants it.

The planner estimates effects from public previews and intents. It commits
one current legal action, then replans on the native successor. Actual
draws, status effects, targets and selection owners come from that successor.
The survival teacher still supplies the behavior outside the new decision
rules. Full-run A8 victory remains the project's primary evaluation outcome.

The [versioned worker](../scripts/engine-act1-boss-worker-v1.mjs) uses the
saved-verified generated card-choice belt repair for every arm. It mounts
only fresh normal starts. It shares the exact frozen native game, support60,
SDK, localization and converter16 with the earlier study. All four checkpoint
files and their complete Adam states are checked before and after the run.
The previous study's receipts, interrupted world and launcher are preserved.

## Qualification gate

The [recipe](../configs/native-curriculum/sts2-v0.111.0-a8-act1-boss-qualification-v1.json)
declares eight fresh seeds, four for each initializer. Each seed has an
original, update-200, survival-teacher and boss-teacher arm with an identical
public start. The verifier reconstructs actual choices and receipts. A
clear requires a real Act 1 boss fight and a live Act 2 entry. The boss
teacher repeats each clear in a new isolated worker and must reproduce the
full public trajectory.

Qualification requires eight sealed worlds with complete arms, at least
three reproduced boss-teacher clears, and more clears than each reference.
Each initializer must contribute a reproduced clear on a world where all
three reference arms lost. The first different teacher choice is checked
on the identical public menu. A cap leaves the arm incomplete. An uncertain
world keeps its evidence and blocks replay.

Qualification ends at the declared panel. It admits zero fitting labels
and performs zero optimizer updates.

## Owner run

Close STS2 and run the command from this checkout.

```bash
bash scripts/qualify-act1-boss-teacher-v1.sh
```

Allow about 10–25 minutes. The outer session cap is 90 minutes. Per-run
limits and the terminal-victory objective follow the frozen prior recipe.
The launcher accepts the exact short-check receipts and resumes from
clean world seals.

## Short checks

Five recorded menus verify the two deck choices and three boss-turn changes.
The saved Attack Potion response passes the strict SDK and shared converter
with all five legal actions and all five public reads. Two fresh native
prefixes delivered 32 choices each through the repaired worker. On an
identical live reward menu, the survival teacher chose Uppercut and the
boss teacher chose Cinder. All 64 deliveries reconstructed and both
workers exited cleanly. Preflight verified the sealed short check and
frozen inputs. The eight qualification worlds are unstarted.
[Verification record](evidence/native-a8-act1-boss-preparation-v1.json).
