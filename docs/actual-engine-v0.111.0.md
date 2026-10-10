# Actual-engine v0.111.0 qualification

The current owner direction is [ADR 0005](decisions/0005-actual-engine-v0.111.0-qualification.md).
The first package is [#144](https://github.com/benyanc/spireshift/issues/144): identify and preserve
the exact build. Public mechanics qualification [#145](https://github.com/benyanc/spireshift/issues/145)
and speed/neural integration [#146](https://github.com/benyanc/spireshift/issues/146) follow.

## Run this stage only

The first Steam-console request failed. The owner's local Steam content log reports
**Access Denied** for the exact manifest with an empty branch; the console's **No connection**
message was less specific. The cache associates this manifest with `public-beta`. Missing branch
context is a supported explanation to test, not proof that Steam will grant access with it.

In Terminal, run this replacement helper only:

```bash
bash scripts/acquire-headless-game-v0.111.0-v2.sh
```

This uses the pinned official **DepotDownloader 3.4.0** macOS arm64 release with explicit
`public-beta` branch context and the same exact manifest. Enter your Steam **login name** when
prompted, then enter your password into the downloader's local prompt and approve Steam Guard.
The password is not placed in the command arguments or captured by SpireShift. If using the Steam
mobile app's QR login, this same helper accepts `--qr` instead of an account-name prompt.
DepotDownloader has its own local .NET authentication storage; no Steam client credentials are
read or copied. The tool source supports branch-specific manifest requests and interactive login:
[pinned README](https://github.com/SteamRE/DepotDownloader/blob/c553ef4d60c00a4f5fd16c9fe017f569001589ff/README.md).

Only the owner starts and monitors the download. It goes under ignored
`artifacts/engine-downloads/sts2-v0.111.0-41cef1ea-macos-arm64-v1/game`, separate from Steam's
installation and the frozen archives. It has a **one-hour cap**. Ctrl+C stops it; repeating the
same helper validates and resumes the exact manifest. There is no fallback to the current beta,
branch switch, game launch, freezing or training. The earlier v1 console helper remains historical.

The request is for app `2868840`, macOS depot `2868842`, manifest `5045320271505434676`.
Steam's local cache associates it with beta build `24724944`, about **1.29 GB downloaded /
2.41 GB extracted**. That is cached evidence; server access and actual file identity remain
unverified. Expect download time to depend on the network. After a successful download, the helper
checks the required file fingerprints and prints **downloaded_identity_matches** or an explicit
mismatch. Send that final result back. If authentication/download fails, send the error instead;
do not substitute another manifest. Even a branch-correct request can fail if Steam does not grant
this account access to that manifest; a manifest-only cache record never establishes access.

The downloader executable is prepared and its version/commit have been checked without a Steam
login. Its archive/executable digests are locally observed fingerprints of the official release
asset, not publisher-signed checksums. The helper verifies the pinned executable before execution.

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

The CLI exposes `engine preflight`, `engine freeze`, `engine verify-archive` and the historical
`engine download-command`, each taking the checked-in qualification configuration.
`engine download-plan` prints the replacement request without authentication, tool preparation
or game content requests. `engine download-game` requires a terminal and takes the separate
downloader configuration, which binds the unchanged qualification config digest. Its child process
uses explicit argument lists and a wall-time cap; the Steam login is interactive in the owner's
terminal. Tool setup, if needed, is size/time bounded and verifies the pinned archive and executable.
Preflight automatically inspects the target archive, known Steam console download directories,
the isolated downloader directory and the installed game; `--game-dir` selects a different source
explicitly. It checks pinned source
commits and a clean checkout. Missing inputs return a nonzero status with a readable next step.
Reports use content digests and optional write-once `--output` paths.

`scripts/freeze-headless-game-v0.111.0-v1.sh` is a separate later preservation helper. It may take
the completed depot directory as its sole argument, otherwise it detects known download paths.
It does not download, install mods, touch saves, launch games or start a follow-up experiment.

The pinned community sources live under ignored `artifacts/engine-sources`. Their licenses,
fingerprints and pending connector/host requirements do not constitute runtime qualification.
The exact existing v0.107.1 launcher remains documented in [frozen-live-game.md](frozen-live-game.md).
