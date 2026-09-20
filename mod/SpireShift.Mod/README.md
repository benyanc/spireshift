# SpireShift.Mod

This directory is reserved for SpireShift-owned game integration code.

The first read-only integration uses the pinned, MIT-licensed STS2MCP bridge as an external local
dependency. SpireShift does not vendor its DLL or proprietary game assemblies. The Python adapter:

- reads player-observable state;
- enumerates legal decisions;
- emits versioned snapshots to the local SpireShift service; and
- keeps state capture on a GET-only transport.

A separate POST-only transport is reachable only through SpireShift's durable, state-bound action
ledger. The ledger provides at-most-once delivery per request ID, stale-state rejection, successor
verification, emergency stop, and fail-closed recovery. Any SpireShift mod code added here must
remain thin, patch-bound, and independently auditable.
