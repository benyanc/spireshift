# ADR 0004: Scoped A8 simulator learning admission

Status: Accepted, 2026-10-09. Implements the owner's fixed-A8 learning priority in ADR 0003.

## Decision

Admit the repaired public-menu simulator for explicitly labelled **policy-only A8 learning**.
Keep complete simulator-to-live parity as a separate requirement for live playback and public
exact-engine claims. This is an evidence-scope decision, not a change to the primary objective.
Terminal full-run victory under the whole-run CPU allowance remains primary; the separate
versioned bootstrap return supports learning before wins are available.

Admission binds candidate revision `65ddaa0a7fa870bcdb72d6df3c22fd8345c3a037`, native SHA-256
`eb40927a87c3ddb5d54b56a1808fd7d6dfa5651e465a6c64e0f5756b090c2a96`, the complete public adapter,
and a source-declared fixed Ironclad/A8 profile. The old engine, falsely labelled A0 pilot and
old greedy experiences remain historical; they are not migrated into PPO training.

## Evidence and limits

The candidate passed all 240 targeted native checks (including 109 captured choice lists and
99 captured outcomes), 4,942 complete-suite native checks, 31 original Python interface checks,
420 original real-game fixture checks and all ten public environment contract checks. One native
timing probe and six legacy combat fixtures without per-turn hands are recorded as skipped.
The unchanged authoritative fixture tree is pinned, and native/source/log hashes are verified.

The frozen real-game source audit corroborates act advancement, separate total and current-act
floor, final-boss ending and the A8 versus A10 rules distinction. It does **not** establish all A8
mechanics or empirical Act 2/3 UI parity. Closing Architect dialogue has one continuation per
settled page and is collapsed by the simulator; live playback must complete those UI steps.
Uncaptured cards, later ancient relics and generation odds retain the original emulator's
coverage limitations. We do not claim they are exact because the interface checks passed.

These limits are carried in [admission evidence](../evidence/public-a8-policy-admission-v1.json).
Existing source-audit evidence remains unchanged. #141 stays open for broader parity work; #37
retains the matching frozen app and playback fidelity requirements. Hidden-world search has its
own #105 qualification and is not enabled by this policy-only admission.

## Consequences

A new A8 actor/critic, score, fresh complete-run split and finite sampled-outcome training recipe
can proceed. Every supplied legal decision family and actor parameter can change. The critic
estimates the declared bootstrap return, not a calibrated win probability or foundation readiness.

Training attempts must retain stalls, errors, caps and unknown interrupted cost. Independent
development is opened only after the player is frozen; the final test remains sealed. No training
result automatically promotes a checkpoint or starts adaptive thinking. #5/#78 readiness and a
useful base player still precede adaptive search; simulator successes alone cannot establish live
game performance or the final exact-engine benchmark.
