# Matched A8 combat feedback

The comparison uses the frozen Slay the Spire 2 v0.111.0 build
(`41cef1ea`), the original headless executable, runtime and public input
converter. A separately built startup adapter adds Trial's abandon
confirmation to the headless learner. The original checkpoints, full Adam
state, and saved first-round fits remain the references.

## Decision framework

The ending verifier gives a completed native victory precedence over
the player-dead flag. The saved Architect diagnostic sets both flags.
The new verifier accepted that victory and all 72 saved losses, and
rejected a flipped label on every case.

Trial's Double Down opens the frozen game's localized Yes/No prompt.
While it is open, the modal owns the two choices. The Trial event and
potion belt regain ownership on No. Yes waits for the game's
single-player abandon task and requires a native loss. A short fixture
reconstructed all five deliveries and verified clean shutdown. The
fixture is separate from learning and strength evaluation.

## Matched fitting

Each initializer starts from its original weights and full Adam state.
Both fits use its same 12 verified first-round normal-start training
games in the same order. The floor-only replay reproduced the saved
actor, critic and full Adam state exactly. The room-feedback arm adds
a fixed auxiliary term to the raw actor advantage. A living transition
to native room rewards supplies a success and a native death in that
combat supplies a failure. The expected success rate uses other
training worlds of the same encounter type. Only choice-bearing combat
decisions in encounter types with both outcomes receive the term.
The term is centered and scaled to half the floor-only raw advantage
standard deviation. Both fits use the same PPO settings, shuffle,
full-run returns and critic targets.

| Initializer | Saved games | Matched decisions | Decisions with room feedback | Adam steps per fitted arm |
| --- | ---: | ---: | ---: | ---: |
| Player 2 | 12 | 1,427 | 705 | 36 |
| Player 3 | 12 | 1,799 | 1,068 | 45 |

Both room-feedback actors changed, and the corresponding critic weights
match the floor-only copies. All six full states reloaded and delivered
the exact four-choice control prefixes. The shared profile and all
frozen inputs passed their integrity checks. [Preparation evidence](evidence/native-a8-combat-feedback-v1.json).

## Owner comparison

Run from the checkout after closing STS2. Allow about 10–25 minutes
with a 90-minute outer cap.

```bash
bash scripts/compare-a8-combat-feedback-v1.sh
```

Eight fresh development worlds pair the original, first-round floor-only
and room-feedback checkpoints for each initializer, for 48 normal-start
Ironclad/A8 games. The model scores the full legal menu in every arm.
The main comparison is room feedback versus floor-only feedback.
Native full-run wins are the primary endpoint. Completed acts, boss
reach and floors diagnose progress. Caps, failures and unattempted
games stay in the denominator. Clean sealed games are reused on resume.
Uncertain deliveries are preserved for inspection.

The comparison performs zero optimizer updates. The eight worlds are
development worlds. Final confirmation, official delivery and promotion
remain separate work.
