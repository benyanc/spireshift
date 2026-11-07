# Static mode-reference inventory

This standalone .NET 10 inspection tool reads PE metadata and managed IL bytes. It has no
reference to the game assembly and never loads or executes it. Its target scope is direct
references to the exact `TestMode` and `NonInteractiveMode` types. Results are qualification
debugging data, never player observations, training examples or runtime-fidelity certification.

The decoder handles operand sizes, two-byte opcodes and variable switch tables. Token-looking
bytes inside integer, string and branch operands do not become references. Unknown/reserved
opcodes and truncated bodies fail rather than silently skipping a method. Nested state-machine
declaring types remain in the raw ledger; the Python review layer binds an async `MoveNext` to
its source method. Reflection and additional indirect aliases are explicitly outside this scope.

Portable synthetic validation requires no proprietary files:

```bash
dotnet build mod/SpireShift.ModeInventory/SpireShift.ModeInventory.csproj -c Release --nologo --output artifacts/engine-tooling/mode-reference-inventory-v1/bin
dotnet artifacts/engine-tooling/mode-reference-inventory-v1/bin/SpireShift.ModeInventory.dll --self-test
uv run pytest tests/unit/test_engine_mode_audit.py
```

For an actual private audit, use the frozen `engine audit-mode-references` configuration. It
checks the inspector source/binary, runtime host, original game archive, wrapper build and
private decompiled-source inventory before inspection. It rechecks source/game/wrapper inputs
afterward. Outputs and the complete raw reference ledger remain under ignored `artifacts/`.
Existing audit workspaces/results are never overwritten or resumed after a source/tool change.

Reviews require exact method IL hashes, a category and an explanation. Unreviewed methods and
stale/duplicate reviews stay visible or fail validation. A complete reference inventory is
distinct from complete semantic review, and even a fully reviewed static list cannot admit
training. Runtime differentials, public-action contracts and mechanics coverage remain separate.
