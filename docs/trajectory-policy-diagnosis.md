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

A bounded 30-second saved-data smoke reached its cap before writing a diagnostic report. Repeated
preference-vector construction and both orientations of anchor-pair indexing have subsequently
been removed. The coding agent did not restart the audit with a larger budget. Mock diagnosis,
integrity, alignment, deterministic output, and exact regret-attribution checks cover the new path.

The complete owner-run audit is pending. Its evidence will determine one next intervention in
representation, learning constraints, or training evidence. Freeze that intervention's recipe,
resource cap, and unchanged non-regression/advancement criteria before owner-run training.
Do not loosen the failed threshold or choose another epoch or blend against this validation result.
This is reused development evidence and cannot become an untouched final-test claim.

## One owner-run command

From the repository directory, run only:

```bash
bash scripts/diagnose-trajectory-policy-v1.sh
```

The cap is ten wall minutes, ten CPU minutes, 2 GB memory, and 50 MB output, with one worker.
The ten-minute value is a maximum, not a predicted duration. The script launches no follow-up job.
The terminal prints the reconciled summary, decision-type attribution, coverage, and original
rejection checks. Full details are saved in
`artifacts/diagnostics/sts2-v0.107.1-base-v6-policy-v1/diagnostic.json`; resource measurements are in
`artifacts/resources/trajectory-policy-base-v6-diagnostic-v2.json`. Share the terminal summary after
it completes so the next intervention can be based on the observed failures.
