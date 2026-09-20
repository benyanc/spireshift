# SpireShift.Mod

This directory is reserved for SpireShift-owned game integration code.

The first read-only integration uses the pinned, MIT-licensed STS2MCP bridge as an external local
dependency. SpireShift does not vendor its DLL or proprietary game assemblies. The Python adapter:

- reads player-observable state;
- enumerates legal decisions;
- emits versioned snapshots to the local SpireShift service; and
- exposes no action-delivery method.

Future guarded execution belongs behind a separate exactly-once action contract. Any SpireShift mod
code added here must remain thin, patch-bound, and independently auditable.
