# Greedy versus sampled combat on fresh games

This finite evaluation isolates the cheapest explanation for the
[previous planner result](native-bounded-combat-planning-result.md). That planner
selected its original greedy continuation for 51 of 63 initial turns, but its
baseline sampled combat actions. We need a direct combat-behavior comparison before
attributing any gain to search or collecting a larger teacher dataset.

## What changes

Both arms load the same two preserved round-60 players, including their exact full
weights and Adam states. No update, checkpoint selection, reward change or promotion
occurs. The primary objective remains complete-run victory within 128 CPU seconds;
acts, floors and the existing bootstrap return remain separate diagnostics.

- **Sampled combat:** sample the unchanged policy at temperature 0.8.
- **Greedy combat:** choose its highest-scored currently advertised action, breaking
  exact ties by current menu order. Resolve combat-owned nested choices the same way.

An observed combat turn establishes ownership. Nested selections remain part of that
encounter until an observed public exit or a different public room. End-turn choices,
generated cards, targeting, potions, costs and effects use the qualified native bridge.
Unknown active-combat ownership fails that game rather than guessing or inventing
an action. Every current legal strategic option remains in the model's menu.

## Matched noncombat behavior

Both arms sample the same unchanged policy at temperature 0.8 outside combat. They
reuse the same qualified shop navigation, including merchant-potion reinspection.
Skip, rest, upgrades, purchases, rewards and optional exits remain selectable.

Random draws are deterministic functions of the game sampling seed, the public
act/floor/act definition, decision family, visit within that family and combat versus
noncombat ownership. No arm or model identity enters that key. Extra combat actions
cannot shift later noncombat draws; extra reward choices cannot shift another floor's
rest draw. Forced shop navigation consumes no sampling slot. The same draw is also
available for both fixed players at corresponding public decision slots.

**Matching behavior does not force identical choices in different states.** Combat
may change HP, potions, rewards or the route a player reaches. The same noncombat
policy can legitimately choose differently there. For identical effective public
inputs and matching slots, its choices and probabilities must match exactly.

This RNG namespace is separately versioned. It preserves the outside-combat policy
distribution; it does not reproduce the historical single-stream trajectories.
The experiment measures a public policy with no search or privileged future plans.
Its episodes are marked evaluation-only and cannot silently become ordinary PPO data.

## Frozen plan and statistics

Two fresh control seeds exercise both arms and both players: eight primary games
plus exact repeats of the four first-seed player/arm cells, **12 native attempts**.
The saved audit reconstructs every control choice, ownership transition, random
draw, probability, ending, score and paired table. The main recipe requires matching
successful native and saved-inference controls. These checks qualify implementation;
their outcomes are not playing-strength evidence or a reason to tune the treatment.

The longer comparison uses **64 fresh development game seeds**, shared by both
players and both arms: **256 complete-game attempts**. Those seeds exclude the
26 historical native seed manifests and the new control seeds. Both checkpoint
identities and all main parameters are fixed before the control; only passed
control/audit identities may be added afterward. Arm execution order is
counterbalanced by player and seed index without looking at outcomes.

Report wins, acts, floors, bootstrap returns, best floors, failures and actual CPU
for each fixed player. Show greedy-minus-sampled changes with paired intervals.
The pooled bootstrap resamples each complete-game seed jointly across both players;
128 player/seed pairs are not 128 independent worlds. There are 10,000 predeclared
resamples with numerical seed 20261020. These intervals do not cover a population
of training initializers. No result automatically grants base or adaptive readiness.
An all-zero paired bootstrap win difference does not establish zero true win
probability or prove that the methods are equivalent; rare wins need more evidence.

## Execution and storage

Use one isolated native worker at a time, sharing the frozen game, runtime, SDK and
support code, with **zero app copies**. Retain sealed episode paths and compact
results; reconstruct and audit at most one full episode at a time. Both original
checkpoint files and all earlier pinned experiment sources remain read-only.

Each game is capped at 4,096 decisions, 120 wall seconds and the original whole-run
CPU ceiling. A verified failed worker is retired; its partial episode supplies no
evaluation return. Continue other originally planned seeds, retaining failures and
unattempted games in the original denominator with zero evaluation value. More than
two failures in a player/arm group stops the longer stage; any failure stops control.
No failed seed is replaced. Evidence corruption, uncertain delivery/shutdown or an
uncommitted attempt stops for inspection and is never retried automatically.

The owner wrapper uses 15-minute sessions, 2 GB memory / 4 GB retained output and a
two-hour invocation bound. Each completed game is sealed independently. Clean pauses
resume only unfinished planned cells; an already completed command displays its
saved result. Progress shows accumulated wins, average floor and best floor per arm
after each four-game seed group. Actual resource reports remain per session; final
cumulative storage must not be summed across sessions.

## Preserved qualification and owner command

The owner completed the 256-game comparison on 2026-10-21. See the
[completed assessment](native-combat-behavior-result.md) and
[result evidence](evidence/native-combat-behavior-result-v1.json). The preparation
measurements and original command below are historical. No new run is required;
the command now verifies and displays its saved result.

The native control completes **12/12 games** with zero failures, app copies or
optimizer updates. All four exact repeats match. Its four primary player/seed pairs
share **207 matched noncombat draw slots**; **50 identical effective public inputs**
produce identical choices and probabilities. Controls include both combat-owned and
noncombat selections, generated card choices, rests, shops and rewards. The 13 nested
combat selections are included in the treatment. This is scoped observed coverage,
not proof of every possible game interaction or of stronger play.

The saved audit reconstructs **all 2,053 decisions**, ownership, draws, probabilities,
native ending scores, duplicates, noncombat matching and tables in **36.51 seconds**.
It verifies retained delivery-journal bytes; collection's delivery audits remain
preserved, without claiming a new independent semantic reaudit. Native control
uses **76.00 wall seconds / 56.05 CPU seconds**, 398.02 MB peak memory and 35.80 MB
cumulative retained output. The saved audit is separately measured.

The full repository check passes **2,058 tests (four skipped)**, strict types on
414 files, formatting/lint and C# protocol checks in **120.25 seconds**. The 33 new
tests cover ownership, RNG isolation, exact greedy probabilities, seed exclusions,
checkpoint integrity, resumable games, uncertain-work refusal, failure denominators
and paired seed-cluster statistics.

Final read-only preflight verifies **63,176 protected earlier files / 35,038
control-source files**, both exact full model/Adam byte seals, the cached control and
the 256-game main plan. Native hosts are explicitly disabled and no main workspace
is created. Only the two passed control/audit references change from the template
frozen before the control. Preflight takes **88.94 seconds**.

At qualification, the longer comparison had **not started**. Its owner command was:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/compare-native-combat-behavior-v1.sh
```

The original estimate was **20–35 minutes**, based on the short control, with 256
planned complete-game attempts and the resource/session limits above. Actual
collection took 19.16 wall minutes across two sessions. No training or further
experiment follows automatically.

See [portable qualification evidence](evidence/native-combat-behavior-comparison-v1.json).
