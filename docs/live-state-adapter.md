# Read-only live-state adapter

SpireShift's first live adapter reads the installed game through the pinned
[`Gennadiyev/STS2MCP@55e0648`](https://github.com/Gennadiyev/STS2MCP/commit/55e064850a68f3b4cde7e5fd525bf9b2dec4e885)
bridge. That revision identifies itself as version 0.4.0 and contains the upstream compatibility
change for STS2 v0.107.1.

The SpireShift transport is deliberately GET-only. It accepts only uncredentialed HTTP origins on
`localhost`, `127.0.0.1`, or `::1`, bounds response size and timeout, checks the running bridge
version before reading state, and exposes no action-delivery method. Guarded action execution is a
separate [durable, state-bound contract](live-action-execution.md).

## Installation

Build the pinned bridge against a legally installed copy of the matching game. Do not copy its DLL
or game assemblies into this repository.

```bash
git clone https://github.com/Gennadiyev/STS2MCP.git /tmp/sts2mcp
git -C /tmp/sts2mcp checkout 55e064850a68f3b4cde7e5fd525bf9b2dec4e885
dotnet build /tmp/sts2mcp/STS2_MCP.csproj -c Release \
  -o /tmp/sts2mcp/out/STS2_MCP \
  -p:STS2GameDir="$HOME/Library/Application Support/Steam/steamapps/common/Slay the Spire 2"
```

Copy `STS2_MCP.dll` and the upstream `mod_manifest.json` into the game's mod directory, renaming
the manifest to `STS2_MCP.json`. Launch the game and complete its mod consent flow. The bridge then
serves its local read API on port 15526.

## Capturing a snapshot

```bash
uv run spireshift live snapshot \
  --output artifacts/live/current-snapshot.json
```

Before contacting the bridge, the command verifies that the discovered installation matches the
version, commit, Steam build, platform, architecture, assembly size, and assembly digest in the
checked-in live manifest. It then verifies the bridge's reported version.

The resulting `live-snapshot-v1` document contains:

- the complete immutable ruleset identity;
- one `observation-v1` public observation and its canonical state hash;
- stable legal-action IDs and public parameters;
- bridge protocol/version metadata;
- `ready`, `partial`, `settling`, or `unsupported` action-coverage status; and
- source paths deliberately omitted by the information projection.

The adapter never silently absorbs a new top-level source field. A bridge update that adds one fails
closed until the field is audited. Seed-valued fields are omitted and recorded. Explicit RNG,
future-state, and draw-order fields fail projection. The bridge's public `is_hidden` cell marker is
renamed to `is_revealed`, so the public observation cannot be mistaken for privileged hidden state.

## Replaying a source fixture

Projection can be tested without running the game:

```bash
uv run spireshift live project \
  tests/fixtures/sts2mcp-menu-source-v0.4.0.json \
  --output artifacts/live/projected-menu.json
```

The checked source fixture is synthetic and contains no game asset, save, assembly, or raw captured
content. Projecting it repeatedly produces the same observation hash and legal-action IDs.

The current action enumeration implements the bridge's documented screen shapes but remains
provisional. [Issue #15](https://github.com/benyanc/spireshift/issues/15) audits real public fixtures
for every screen, and [issue #18](https://github.com/benyanc/spireshift/issues/18) is the gate for
complete full-run legal-action coverage. `partial`, `settling`, and `unsupported` states remain
visible rather than receiving a heuristic fallback.
