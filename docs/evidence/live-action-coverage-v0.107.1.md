# Full-run legal-action coverage: STS2 v0.107.1

The first live-action coverage scope is frozen as **The Defect, Standard mode, Ascension 0** under
coverage contract `sts2-v0.107.1-defect-a0-live-coverage-v1`. The contract binds the exact ruleset
manifest and requires 18 actionable bridge state types, 13 SpireShift decision types, and 28 legal
action kinds. Shrinking any of those lists causes the gate to fail.

The coverage command combines two independent forms of evidence:

1. The public fixture corpus projects 19 decision shapes and compares the result with exact ordered
   action oracles. This covers every actionable single-player state emitted by pinned STS2MCP
   v0.4.0, including rare overlays not reached by the acceptance run.
2. A complete unattended live run proves that the same recorder and guarded action path can start at
   the main menu and reach a terminal result within the frozen character and difficulty scope.

The checked report records a `pass`:

- 19/19 fixture oracles passed;
- 18/18 actionable state types, 13/13 decision types, and 28/28 action kinds were enumerated;
- the live record contained 169 durable records and 167 action attempts;
- the run covered floors 1–12 and ended at confirmed defeat with zero HP;
- the run advertised 19 and selected 16 distinct action kinds; and
- no unsupported decision occurred.

The raw live record remains in ignored `artifacts/` storage because it contains extensive live game
state. The checked report binds it by SHA-256 digest
`4e932b92954cab3bfc7346d5fcae554091e7952b9d4697ac2df80052808d9b9c` and retains only aggregate
public evidence.

Run the gate against one or more complete records:

```bash
uv run spireshift live coverage \
  --run artifacts/live/runs/acceptance-menu-to-terminal-pass.jsonl
```

Unsupported decisions are now durable records rather than inferred failures. The loop emits an
`unsupported_decision` record before its summary when:

- the adapter reports unsupported or remains incomplete after the readiness deadline;
- the policy has no explicitly audited rule for an otherwise ready screen; or
- the guarded executor returns an unsupported receipt.

The record includes the source, reason, decision index, complete public snapshot, advertised legal
actions, coverage issues, and selected action when one existed. Verification requires exactly one
such record for an unsupported summary and rejects an unsupported record attached to any other
outcome. The policy's state handling is an explicit allowlist, so a new state cannot inherit a
first-action fallback silently.

The coverage verdict is `pass` when all gates pass with no unsupported decisions,
`conditional_pass` when every unsupported run is explicitly accounted for and terminal evidence
still exists, and `fail` for a corrupt record, wrong scope, unaccounted stop, missing terminal run,
or incomplete fixture contract.

This gate proves complete enumeration against the pinned bridge contract and clean unattended-run
accounting. The acceptance run exercised 12 of the 18 states live; boss combat, fake merchant, boss
relic selection, Crystal Sphere, hand selection, and ordinary shop behavior are covered by audited
fixtures or separate captures rather than all occurring in this one trajectory.
