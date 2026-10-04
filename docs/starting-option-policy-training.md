# Starting-option policy learning

Issue #125 tests the representation gap found in the rejected base-v6 update: every changed
starting Ancient choice switched from option 2 to option 0, with 15 harmful changes on development
validation. Accepted base-v2 remains the production model. This implementation is ready for the
owner-run experiment; no real-data training or game evaluation has been launched by the coding agent.

## Public candidate identity

The separate `starting-ancient-public-option-v1` encoder binds each legal action's execution index
to its visible `neow_options` ID. The ID is a category in the `ancient_option_id` namespace, rather
than a numerical amount or strength. The encoder consumes the existing verified public model
representation. The backend, admitted manifest, original encoder and all parent checkpoint fields
stay unchanged.

The new head applies to Ancient choices on floor 1 with at least two legal candidates. Later
Ancients, forced proceed actions and other decision phases retain the parent policy. An invalid
starting menu, mixed phases, missing visible resources, duplicate execution indices, or action/option
misalignment fails closed. Actions still dispatch by their original IDs and indices.

Candidate features cross the option category with visible context:

- act as a category and a unit bias;
- HP divided by maximum HP;
- maximum HP divided by 100, capped at 2;
- `log(1 + gold) / log(1001)`, capped at 1;
- deck size divided by 100, capped at 1;
- a bag of categorical card IDs and upgrade flags, normalized by deck size;
- a bag of categorical relic IDs and used-up flags, with counts divided by 10 and capped at 1.

The signed SHA-256 feature hash has 4,096 coordinates in the frozen experiment, separate from the
parent's feature coordinates. Menu positions, deck/relic slot order, opaque observation-vector
values, state hashes, run seeds and source identifiers are absent from these residual features.
Option and inventory IDs identify visible objects; this first version adds no rule-effect lookup.
Hash collisions remain possible and the IDs are bound to the frozen ruleset.

The known-option vocabulary comes only from legal candidates in fitting anchor states and eligible
fitting preferences. IDs absent from that fitting vocabulary share an explicit `unknown` category.
Selection and validation inputs do not extend it. Coverage reports preserve every input record,
the number of scoped records and complete runs, unique IDs, and unknown candidates by subfold.
The small number of starting-choice preference runs remains visible.

Simultaneously permuting the public menu and execution mapping preserves each option's new
features and residual score. This property belongs to the residual. The frozen parent may retain
its existing position bias.

## Frozen experiment and unchanged checks

`configs/starting-option-policy/sts2-v0.107.1-base-v2-frontier-preferences-v1.json` has identity
`sha256:c751f9cdf41ce3267620e6748f219aa3de810ea1d0fc6f56683a42c3017c9f30`. It embeds the unchanged
trajectory recipe `sha256:e774e71b33497e74ea759c36884e2b065a82c66745d164640a73f3a47a545055` and the
same parent, collection, curricula, search provenance, split, ruleset and objective identities.

The residual starts with zero weights and adds a correction to the original policy logits.
Initialization exactly reproduces the parent prediction. Only residual coordinates receive
optimizer updates; the entire original checkpoint, including its policy, terminal-value,
tactical-risk and floor-distribution heads, is immutable and checked against its original content
identity. The checkpoint/report use v7 with explicit residual encoder, config, vocabulary and head
identities. Older checkpoint formats remain supported.

The same 40 full-batch AdaGrad epochs, learning rate 0.0005, parent-policy anchoring strength 2,
preference strength 1, proximal penalty 0.1, gradient clip 1 and epsilon 1e-8 apply. The proximal
penalty centers the residual at zero. All 68 eligible comparisons remain in training/selection
metrics and run normalization, including decisions the phase-local residual cannot change; the
11 activity-only comparisons remain excluded. The same complete-run subfolds and rank weights apply.

Checkpoint selection uses complete-run selection data and the original preference and strong
advancement criteria. The selected epoch is assessed once on **all 204 original development-validation
states**, with the same auxiliary-policy gate, pair-loss limit 0.01, accuracy-drop limit 0.02,
regret-increase limit 0.0002 and mean policy-drift limit 0.05. Validation does not choose another
epoch, blend, mask or threshold. Report and checkpoint loading verify selection and rejection.
Direct production-policy construction also validates the v7 report rather than trusting an
eligibility flag alone.

A rejected or non-advancing experiment is a normal completed result. If no epoch qualifies, the
saved residual is zero. A passing candidate is still unpromoted and requires a separately frozen
full-run comparison. Reused development validation is not an untouched final test. Starting-choice
improvement alone cannot establish combat competence or foundation readiness. Terminal full-game
victory under the whole-run compute budget remains primary; positive terminal labels are still
zero and adaptive-controller training remains blocked.

## One owner-run command

From the repository directory, run only:

```bash
bash scripts/train-starting-option-policy-v1.sh
```

The script verifies the saved inputs, audits option coverage, trains the residual and checks the
selected candidate. It launches no game, replay, data collection or follow-up evaluation. It uses
one worker with maximum 600 wall seconds, 1,200 CPU seconds, 4 GB memory and 1 GB output. Ten wall
minutes is a cap, not an expected duration. Existing result files are refused before work begins.
The owner starts and monitors this experiment.

The terminal prints candidate eligibility, selected epoch, unchanged validation checks, broad policy
metrics and option coverage. Share that terminal summary when it completes. The new checkpoint and
report are under `artifacts/models/sts2-v0.107.1-base-v7/`; the resource report is
`artifacts/resources/starting-option-policy-base-v7-train-v1.json`. Raw data and models stay outside Git.

Short tests cover categorical IDs, unknown fallback, menu and inventory permutations, malformed
dispatch, public-state boundaries, zero-initialization parity, unchanged parent heads, vocabulary
ownership, artifact tampering, v7 schema/loader compatibility and rejection. A bounded inspection
of one saved real starting screen also verified zero-residual parity with the actual base-v2
checkpoint and v7 schema/loader compatibility, without optimization or replay. The complete
owner-run coverage and quality result is pending.
