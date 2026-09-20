# Model representation v1 evidence

Issue 22 introduces an executable representation boundary for the policy/value foundation and
future search agents.

The checked test suite projects every fixture in `public-state-corpus-v1.json` through the pinned
STS2MCP v0.4.0 adapter, builds a compositional input, and vectorizes it. The corpus covers 19
fixtures, 13 decision types, 28 action kinds, 46 entity instances, and 53 legal candidates. Every
fixture has a distinct content-addressed representation. Candidate order, masks, and source action
handles remain aligned, and every sparse index is checked against its configured dimension.

The committed combat fixture has representation hash
`sha256:46ca0e95d35d5a6f364a6ec73560a5f191375a5b434635df27610ed30a1c38f8` and model-feature
digest `5cdb3108bdbd446a97250196b3857f72f4e2d33fda93e5ac6da13417de520bb5`. It contains eight
entities and eight legal candidate actions. The 256-dimensional reference projection contains 29
nonzero state entries.

Additional synthetic coverage exercises persistent HP, maximum HP, gold, deck cards, relics,
potions, enemies, nested statuses, and previously unseen card, relic, potion, and enemy identities.
It verifies that these values are available as typed mechanics and entities rather than requiring a
fixed ID vocabulary. A metamorphic test renames every source action ID and proves that the model
digest and candidate vectors remain unchanged while the decode handles change.

Negative tests reject stale public-state hashes, duplicate action handles, privileged RNG/future
fields, and undersized hash spaces. Both committed fixture documents validate against their strict
JSON Schemas.

This evidence establishes representation coverage and information isolation. It does not establish
policy accuracy, value calibration, or patch robustness; those require learned-model training and
the frozen readiness benchmark.
