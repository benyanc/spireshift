# Mock tactical-to-run value evidence v1

Issue 45 adds the typed boundary between tactical search leaves and the terminal run-value model.
The checked benchmark uses a test-only public-information environment in which one combat action
preserves 70 of 80 HP, one accepts damage and leaves 42 HP in exchange for permanent power, and one
spends the only potion to secure a persistent relic.

The transparent fixture run-value model assigns continuation win probabilities of 0.35, 0.72, and
0.82 to those persistent successor states. Each reported estimate mixes a direct run-value bootstrap
with eight exact terminal rollout outcomes in each of two sampled worlds. Every seed uses 54
simulated transitions and six run-value inferences, or 60 of the declared 128 compute units.

| Seed | Preserve HP | Take damage for power | Spend potion for relic | Terminal-value choice | HP-greedy choice |
|---:|---:|---:|---:|---|---|
| 7 | 0.325000 | 0.781667 | 0.898333 | Spend potion | Preserve HP |
| 19 | 0.450000 | 0.823333 | 0.815000 | Take damage | Preserve HP |
| 41 | 0.450000 | 0.531667 | 0.898333 | Spend potion | Preserve HP |

The terminal-value and HP-greedy rankings disagree in all three seeded cases. Taking damage for
permanent power and spending the scarce potion both beat the HP-preserving action in every case.
The stochastic estimates can change which of the two long-term investments ranks first; the intended
claim is that the terminal-victory evaluator rejects the local HP proxy.

The report preserves model-input paths for HP, max HP, gold, potion identity and charges, every deck
card and upgrade, relic identity and counter, permanent power, act and floor, and revealed path
options. It also records every candidate's successor and representation hashes, sampled leaf values,
terminal and bootstrapped rollout counts, and compute usage.

The report identity is
`sha256:3dd4eae07297e726530b251d090bd142827b559f4bc5bde2a392b3a531f062fe`.
Tests regenerate it exactly, validate its strict JSON Schema, check the environment contract, exercise
exact terminal and truncated bootstrap paths, bind real base and calibrated checkpoints, reject an
objective or ruleset mismatch, enforce equal-sampling budget sufficiency, and reject tampering.

This evidence carries claim scope `mock_pipeline_validation`. It validates the tactical-to-run
handoff and ablation design, not useful STS2 search strength.
