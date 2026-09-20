# Public-state fixture audit: STS2 v0.107.1

This audit freezes the action-enumeration boundary for the pinned STS2 v0.107.1 game build and
STS2MCP v0.4.0 at revision `55e064850a68f3b4cde7e5fd525bf9b2dec4e885`.

The checked corpus contains 19 minimal fixtures covering all 18 actionable single-player state
types emitted by that bridge. It includes combat and in-combat selection, map choices, combat and
card rewards, event options and dialogue, rest sites, shops and the fake merchant, treasure and boss
relic choices, card and bundle overlays, the Crystal Sphere, menus, and terminal state. `unknown`
and `overlay` are deliberately excluded because the bridge defines them as unsupported manual
states rather than actionable screens.

Fifteen fixtures preserve shapes observed in the successful unattended menu-to-terminal acceptance
run and an earlier merchant capture. They contain only the fields needed to distinguish legal
choices; card and relic text, profile data, run seeds, timestamps, and irrelevant game values were
removed. Four rare shapes (boss combat, fake merchant, boss relic overlay, and Crystal Sphere) come
from the state builder and documentation at the exact pinned bridge revision. Their provenance is
explicit in the corpus instead of being presented as live observations.

Every fixture includes an independently written, ordered oracle of legal action kinds and public
parameters. The audit reprojects each source twice and requires:

- the selected manifest, patch, bridge version, and bridge revision to match the corpus;
- every actionable state type and required decision family to be present;
- deterministic projection without mutating the source;
- the declared decision type and `ready` action-coverage status;
- exact equality with the legal-action oracle, including target expansion and disabled-choice
  filtering; and
- exact accounting for every field transformed or omitted at the information boundary.

The projector still fails closed on unaudited top-level fields and forbidden RNG, future-state, and
draw-order fields. A regression test injects privileged state into the corpus and confirms that the
audit fails.

Run the reproducible audit without launching the game:

```bash
uv run spireshift live audit-fixtures
```

The checked machine-readable result is
[`live-fixture-audit-v0.107.1.json`](live-fixture-audit-v0.107.1.json). It records 19 passes, zero
failures, all 18 actionable state types, and all required decision families.

This is a projection and legal-action coverage audit. It does not prove that every advertised action
succeeds in the game or that all mutually exclusive variants have been exercised live. The full-run
action-delivery and explicit unsupported-decision gate remains issue #18.
