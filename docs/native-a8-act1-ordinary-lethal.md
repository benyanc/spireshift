# Ordinary fight lethal planning

The preceding eight-world comparison gave the tactical teacher and
reward-safe v2 one Act 1 clear and four boss reaches each. The Sewer Clam
loss in `diagnostic-004` exposed a missed
kill in an ordinary fight. On floor 7, round 5, the player had 16 HP and
3 energy. The Clam had 38 HP and 6 block and threatened 18 damage. The
saved Bash and Strike left it at 5 HP.

The isolated native branch reproduced the exact 77-choice prefix and
played three legal one-energy Strikes. The Clam's HP went 38 → 29 → 14,
then the third hit opened combat rewards with 22 player HP. Raw
reconstruction verified all 80 native deliveries. The new policy also
selected each of the three delivered Strikes when replayed against those
verified menus and receipts.

The extension uses the existing bounded lethal search for supported
ordinary fights. It retains current Strength in the public damage
previews and counts current block. Demon Form and Plating are turn
boundary effects in the frozen build. Other unsupported effects use
the inherited teacher. Elite and boss planning use their existing
paths.

The separate fresh smoke pair verified the first different ordinary
action on an identical legal menu and four delivered ordinary lethal
choices. Both arms recorded native Act 1 losses on floor 13. The verifier
reconstructed 297 deliveries across the pair. All four full checkpoint
and Adam files, the build, runtime, SDK, localization and shared save
profile passed verification. Optimizer updates and admitted lessons
were both zero. [Verification record](evidence/native-a8-act1-ordinary-lethal-v1.json).

## Fresh matched comparison

With STS2 closed, run this command from the checkout. It compares the
previous tactical teacher with the ordinary-fight extension on sixteen
fresh normal-start Ironclad/A8 worlds.

```bash
bash scripts/compare-act1-ordinary-lethal-v1.sh
```

Allow about 5–10 minutes. The launcher requires the sealed Clam proof
and passing smoke pair. It records boss reaches, Act 1 clears and the
first same-menu intervention on each changed world. Candidate-only
clears receive a fresh confirmation. The comparison is diagnostic and
performs zero optimizer updates. Uncertain attempts retain their
evidence for inspection.
