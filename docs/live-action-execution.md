# Guarded live-action execution

SpireShift delivers live actions through a transaction boundary around the pinned STS2MCP
connector. The connector applies actions on the game's main thread, but it does not accept request
IDs or bind a POST to the state that was observed by the caller. SpireShift supplies those guards
before any POST reaches the connector.

## Bound requests

A `bound-action-v1` request contains only:

- a unique canonical UUID request ID;
- the complete manifest identity and patch ID;
- the exact public-state hash from which the action was chosen; and
- one action ID from that snapshot's enumerated legal-action set.

The request does not accept caller-supplied action parameters. At execution time, SpireShift reads a
fresh live snapshot and resolves the action ID back to the connector payload advertised by that
snapshot. It rejects ruleset drift, stale state, incomplete action coverage, and actions that are no
longer legal.

Create a bound request from a captured snapshot:

```bash
uv run spireshift live bind \
  artifacts/live/current-snapshot.json \
  'menu_select:965cf53812a68c2b' \
  --output artifacts/live/request.json
```

## Dry run and application

Execution is a dry run unless `--apply` is present:

```bash
uv run spireshift live execute \
  artifacts/live/request.json \
  --output artifacts/live/dry-run-receipt.json

uv run spireshift live bind \
  artifacts/live/current-snapshot.json \
  'menu_select:965cf53812a68c2b' \
  --output artifacts/live/apply-request.json

uv run spireshift live execute \
  artifacts/live/apply-request.json \
  --apply \
  --output artifacts/live/applied-receipt.json
```

A dry-run request ID is consumed and cannot later be used to apply an action. Bind a new request for
the applied operation.

Immediately before delivery, SpireShift appends and synchronizes a `prepared` record. The connector
is called only after this record is durable. A completed request ID is never delivered again. If the
process stops after preparation or the acknowledgement is lost, the outcome remains uncertain and
that request is never retried automatically.

After an accepted action, SpireShift polls the public state until it sees a changed, `ready` snapshot
that remains stable across multiple reads and a minimum quiet interval. The resulting snapshot is
embedded in the durable receipt. Character selection is a narrow documented exception: STS2MCP
acknowledges the selected unlocked character but does not expose the selection in its state. For
that action alone, a matching connector acknowledgement plus stable public state is accepted and
recorded as having no public delta.

## Receipts

Every durable `action-receipt-v1` records the bound request, predecessor hash, delivery certainty,
connector response when available, and successor snapshot when proven. Status is one of:

- `applied`: connector acknowledgement and a stable successor were observed;
- `rejected`: a guard or the connector rejected the request;
- `duplicate`: the request ID already has a durable outcome and was not redelivered;
- `stale`: the public state changed after the action was bound;
- `unsupported`: the live adapter cannot enumerate a complete action set for this screen;
- `timeout`: delivery or successor settlement exceeded its deadline;
- `unknown_delivery`: acknowledgement or successor verification was lost; or
- `dry_run`: every guard passed without delivery.

`automatic_retry_safe` is always false. Recovery creates a new request from a freshly observed
state; it never replays an uncertain request.

## Ledger and safety controls

The default durable state directory is `$XDG_STATE_HOME/spireshift` when configured, otherwise
`~/.local/state/spireshift`. It contains an append-only action ledger, a single-writer lock, and the
local emergency-stop marker. Override it with `--state-dir` for isolated testing.

```bash
uv run spireshift live safety-status
uv run spireshift live stop
uv run spireshift live resume
```

`live stop` prevents the next delivery. A timeout or unknown-delivery receipt also blocks every new
request. After inspecting the visible game and current public snapshot, `live resume` clears the
emergency stop and records an explicit recovery acknowledgement. A live writer lock is never
silently removed; a leftover lock after a process crash requires operator inspection.

## Installed-game demonstration

On the manifest-declared STS2 v0.107.1 build, the guarded executor applied and verified:

- a noncombat `singleplayer` menu action from the main menu to character selection; and
- a combat `play_card` action that consumed one energy and changed the visible enemy HP from 46 to
  40.

Replaying both request IDs returned `duplicate`; the menu did not advance again and enemy HP stayed
at 40. Generated requests, receipts, ledgers, and live snapshots remain outside Git.
