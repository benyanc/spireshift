# Patch and ruleset manifests

A SpireShift patch manifest identifies the complete rule-producing stack for a run:

- official game version, commit, release, and Steam build;
- engine and adapter source revisions and checksums;
- checksums for the authoritative assembly, extracted mechanics, or simulator rules;
- observation/action schemas and the public-information policy; and
- conformance admission status.

The `manifest_id` is the SHA-256 digest of the canonical JSON body with the ID omitted. Changing any
field produces a new identity. `spireshift manifest verify` recomputes this identity and can also
compare a manifest with the non-proprietary installation identity produced by `spireshift doctor`.

## Freezing local mechanics

A manifest specification may replace a component or mechanics `digest` with a `local_path`.
`spireshift manifest freeze SPEC OUTPUT` hashes that file or directory and removes the path from the
frozen document. It never copies the source artifact. A directory digest includes every relative
file name and byte sequence in sorted order, so renames and content changes both produce new IDs.

Frozen output is write-once: the command accepts an existing byte-identical manifest and refuses to
replace a different one. Specs and frozen manifests must not contain game binaries, extracted game
content, saves, or decompiled source.

## Admission status

- `test_only` identifies synthetic fixtures such as the deterministic mock environment.
- `pending_conformance` identifies a pinned stack that cannot yet support training or reported
  evaluation results.
- `admitted` means the stack passed the environment conformance and public-state checks for that
  exact identity.

The checked-in STS2 v0.107.1/EvanGambit manifest is deliberately `pending_conformance`. External
live-fixture evidence passes on its captured surface, but the future SpireShift adapter must also
pass the public-state and differential contract before this status can change.

The STS2 v0.107.1/STS2MCP live manifest is also `pending_conformance`. It binds the installed
authoritative assembly to the pinned read bridge. Its snapshots can support integration work, while
full admission still requires the screen-by-screen public-state audit and exact differential traces.
