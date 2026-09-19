# SpireShift.Mod

This directory is reserved for the thin read-only STS2 integration.

The mod will:

- read player-observable state;
- enumerate legal decisions;
- send versioned snapshots to the local SpireShift service;
- render recommendations;
- never execute actions in the initial release.

The game-dependent project will be generated only after the environment bakeoff chooses the bridge
and confirms its license and supported game version. This avoids introducing proprietary assembly
references or committing to a fragile integration prematurely.
