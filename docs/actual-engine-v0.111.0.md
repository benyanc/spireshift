# Actual-engine v0.111.0 qualification

The current owner direction is [ADR 0005](decisions/0005-actual-engine-v0.111.0-qualification.md).
The first package is [#144](https://github.com/benyanc/spireshift/issues/144): identify and preserve
the exact build. Public mechanics qualification [#145](https://github.com/benyanc/spireshift/issues/145)
and speed/neural integration [#146](https://github.com/benyanc/spireshift/issues/146) follow.

## Run this stage only

In Terminal, run this one helper:

```bash
bash scripts/acquire-headless-game-v0.111.0-v1.sh
```

It opens Steam's Console tab and prints the single exact download request. Paste that printed
line into Steam's console and press Enter. This is the owner's explicit start of the download.
It uses the logged-in licensed Steam client; SpireShift does not read credentials, start the
download itself or monitor it. Keep the existing Steam game and frozen v0.107.1 archive intact.
Do not switch beta branches or overwrite the installation.

The request is for app `2868840`, macOS depot `2868842`, manifest `5045320271505434676`.
Steam's local cache associates it with beta build `24724944`, about **1.29 GB downloaded /
2.41 GB extracted**. That is cached evidence; server access and actual file identity remain
unverified. Expect download time to depend on the network. Wait for Steam to print
**Depot download complete** and send that line, including its directory, back to Codex.
If Steam reports an error, send that error instead; do not substitute another manifest.

## What happens after completion

Codex can perform the short identity check and freeze next. The configuration requires
macOS arm64 v0.111.0 / `41cef1ea` and the documented executable, rules assembly and GodotSharp
hashes, plus the app metadata, resource pack and runtime dependency file. The archive lives under
`~/Library/Application Support/SpireShift/frozen-games/sts2-v0.111.0-41cef1ea-macos-arm64-v1`.
Its game keeps the `steamapps/common/Slay the Spire 2` layout. No old app manifest is copied onto
the downloaded depot: that would falsely label it as the installed v0.107.1 game.

The implementation checks every copied file and permission, detects source changes while copying,
rejects symlinks/modded base copies, and refuses overwrites. A re-run verifies existing bytes;
it never prints a saved success without checking integrity. Failed partial copies remain with
explicit failure evidence. Required version/hash mismatches fail before a destination is created.
Archive metadata is private; nothing here redistributes game files.

The stage has **zero game launches, optimizer steps or training admission**. Freezing does not
establish profile isolation or a successful game launch. Those checks and actual-game/CLI
mechanics, refreshed legal menus, public inputs and full-run performance remain to implement.
Ironclad/A8 and terminal full-run victory stay fixed. New training uses new engine/input/data
identities; historical v0.107.1 models and traces are not silently migrated.

## Developer reference — not additional owner tasks

The CLI exposes `engine preflight`, `engine freeze`, `engine verify-archive` and
`engine download-command`, each taking the checked-in qualification configuration. Preflight
automatically inspects the target archive, known Steam console download directories and the
installed game; `--game-dir` selects a different source explicitly. It checks pinned source
commits and a clean checkout. Missing inputs return a nonzero status with a readable next step.
Reports use content digests and optional write-once `--output` paths.

`scripts/freeze-headless-game-v0.111.0-v1.sh` is a separate later preservation helper. It may take
the completed depot directory as its sole argument, otherwise it detects known download paths.
It does not download, install mods, touch saves, launch games or start a follow-up experiment.

The pinned community sources live under ignored `artifacts/engine-sources`. Their licenses,
fingerprints and pending connector/host requirements do not constitute runtime qualification.
The exact existing v0.107.1 launcher remains documented in [frozen-live-game.md](frozen-live-game.md).
