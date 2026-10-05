# Saved trajectory policy diagnosis

Issue #42's immediate foundation package explains the rejected base-v6 policy update. It verifies
the same frozen parent, curricula, preference collection, source-search artifacts, ruleset, complete
run split, and objective as the trainer. Parent and candidate checkpoints and reports are checked
against those inputs. Loading inputs performs no engine replay or optimization.

The report reconstructs every original development-validation choice, including unchanged and
utility-tied choices. Each row preserves the public state hash, candidate order, both selected
actions, teacher auxiliary utilities, and the change in regret. Harm and benefit are aggregated
by decision type and complete run. Counts, baseline metrics, candidate metrics, drift, preference
metrics, and the frozen rejection checks must reconcile with the saved training report. A report
whose content identity is valid but whose metrics disagree with the actual saved inputs is rejected.

For changed actions, the exact logit-margin change is decomposed into action coordinates and
state/action interaction coordinates. The largest parameter contributions are retained. Cosine
overlap with fitting preference contrasts and the preference gradient at the parent are diagnostic
associations; they do not prove that a specific label caused an error. The derivative is evaluated
analytically, with no optimizer step or new model produced. Initial parent-policy anchoring has zero
gradient because parent and candidate distributions are identical before the first update.

The audit also checks exact public-state/action overlap between new fitting comparisons and the
original anchor corpus. Exact opposing targets are reported directly. Identical hashed contrasts
at different states are reported as representation aliases; an alias alone does not establish an
accidental hash collision. Strong-label coverage is reported by decision type and complete run.
All 79 strict improvements remain visible, including the 11 excluded activity-only comparisons;
all 95 mutations are accounted for by the collection summary and exclusions.

The report is deterministic and content addressed. Raw public examples, choices, and preference
details stay in ignored `artifacts/`. Its JSON schema is `trajectory-policy-diagnostic-v1`.
No game is launched, no candidate is trained or selected, and no checkpoint is promoted.
Teacher utilities and preference ranks remain auxiliary evidence. The objective is terminal
full-game victory under the whole-run compute budget; terminal-value and adaptive readiness
remain blocked by zero positive terminal-victory evidence.

## Current result and next decision

The base-v6 training experiment completed in 51.143 seconds. Epoch 2 failed its frozen development
validation regret limit: an increase of 0.000303308823 versus the maximum allowed 0.0002. Choices
changed on 26/204 states. The selected update ranked the preferred action ahead in 1/18 selection
comparisons, including 1/5 strong floor comparisons. Accepted base-v2 remains in production.

The complete owner-run audit succeeded in 38.852 wall seconds and 31.115 CPU seconds, using
approximately 520 MB peak resident memory. Its counts and metrics reconcile with the rejected
training report. The saved report's content identity and JSON schema also pass verification.

| Decision type | Changed actions | Harmful | Beneficial | Utility ties |
| --- | ---: | ---: | ---: | ---: |
| Starting Ancient event | 24 | 15 | 8 | 1 |
| Path | 2 | 0 | 2 | 0 |
| Combat and all other types | 0 | 0 | 0 | 0 |

All 24 event changes switch from `evangambit:ancient:2` to `evangambit:ancient:0`. The event changes
add 0.085673076923 total auxiliary regret; the two path improvements remove 0.023798076923,
reconciling to the overall increase of 0.061875 across 204 states. None of the 69 combat choices
changes. These are teacher-utility comparisons on saved inputs, not measured changes in game wins.

No exact public-state/action overlap conflicts or identical hashed-contrast aliases were found
between the fitting preferences and original anchor corpus. Similar preference contrasts and
shared interaction-weight movement suggest overgeneralization across starting menus, but do not
establish individual label causation or an accidental hash collision.

Saved examples contain public `neow_options` IDs, while the current generic encoder treats integer
identifiers as numeric values. Legal-action payloads carry phase and action/target indices without
binding each candidate to its corresponding option's categorical identity. The next bounded
intervention is [issue #125](https://github.com/benyanc/spireshift/issues/125): add identity-aware
public option features through a separately versioned, zero-initialized starting-event residual
policy head over accepted base-v2. The parent and its non-policy heads stay immutable. This tests
a concrete representation hypothesis; success is not assumed, and combat competence remains
unfinished even if starting choices improve. The [starting-option trainer](starting-option-policy-training.md)
completed its frozen owner-run experiment with no accepted update. Starting-choice preference
coverage was only three fitting runs and one selection run; the evidence collector now expands it.

The follow-up preserves the original data ownership and all-204 non-regression checks. Its recipe
and identities must be frozen before an owner-run experiment, capped at one worker, 600 wall
seconds, 1,200 CPU seconds, 4 GB memory, and 1 GB output. Do not loosen the failed threshold or
choose another epoch, action mask, or blend against this validation result. This is reused
development evidence and cannot become an untouched final-test claim.

## Completed owner-run audit

`scripts/diagnose-trajectory-policy-v1.sh` has completed; do not repeat it as the next step.
The subsequent starting-option experiment also completed with no accepted update. Exhaustive
starting-option collection then passed its coverage gate with 172 eligible comparisons and no
victories. The next owner-run command is in the
[exhaustive-evidence training guide](starting-evidence-policy-training.md).
The diagnosis script launches no follow-up job. Full details are saved in
`artifacts/diagnostics/sts2-v0.107.1-base-v6-policy-v1/diagnostic.json`, identified by
`sha256:250a6afcbbce06527ec65012da8ad1ec69e8f91c2ee99cd2244045866030c4b4`.
Resource measurements are in `artifacts/resources/trajectory-policy-base-v6-diagnostic-v2.json`,
identified by `sha256:82992e8f9bedcdbe262f5d79cba7fd8d881ec19d0194b36c4d77214f8e32b8b3`.
Raw examples remain outside Git. Base-v6 remains rejected and base-v2 remains accepted.
