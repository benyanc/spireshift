# Deterministic mechanics and public probabilities

`PublicMechanicsService` is the shared rule boundary for policy-only agents, learned policies,
search, and the future advisor. A snapshot binds one public observation to its legal actions, action
mask, and compositional model input. Teacher generation, selective DAgger, and full-run execution
therefore cannot construct a different legality mask or rule-derived representation for the same
state.

Outcome queries have three explicit methods:

- `exact_enumeration` uses deterministic code supplied by an engine when every public outcome and
  probability can be enumerated without inspecting hidden state.
- `public_resampling` clones the same public state into independently seeded hidden worlds and
  returns an empirical distribution. It is always marked approximate and records its sample count.
- `unavailable` is returned when neither exact enumeration nor requested public resampling is
  available. Missing mechanics are never silently replaced with invented probabilities.

Every resampled clone must preserve the source public observation and exact legal-action list before
it may be stepped. The service returns only public `Transition` values. Hidden RNG state, future draw
order, and engine seeds are absent from the result and remain outside model inputs.

The mock engine implements exact rules for its path and boss decisions. Audit those calculations
against the checked authoritative fixture:

```bash
uv run spireshift mechanics audit-mock \
  --output artifacts/mechanics/mock-audit.json
```

The report localizes legal-action and probability divergence by patch, case, and action, and records
total-variation and maximum probability error. The checked reference report is
`docs/evidence/mock-mechanics-audit-v1.json`.

The admitted EvanGambit backend currently exposes safe hidden-world cloning but no exact public
probability enumerator. Its mechanics queries therefore use `public_resampling` when seeds are
provided and report `unavailable` otherwise. Exact engine calculators can be added behind the same
optional protocol without changing policy, search, or model callers.
