# Preserved real game for later model playback

[Issue #37](https://github.com/benyanc/spireshift/issues/37) tracks this component and the eventual
pre-patch experiment bundle. The private macOS archive was verified on 2026-10-08; game payloads
and local evidence remain outside Git.

## Verified installation

The preserved copy is under
`~/Library/Application Support/SpireShift/frozen-games/sts2-v0.107.1-build-23811903`.
It contains the full game at `steamapps/common/Slay the Spire 2`, the copied Steam app manifest,
the pinned bridge, and `Launch Frozen Spire.command` with its `launch-context` directory.

Its identity is v0.107.1, game commit `59260271`, Steam build `23811903`, macOS arm64.
The game assembly SHA-256 is
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
The live identity manifest is
[`sts2-v0.107.1-sts2mcp-55e0648.json`](../manifests/patches/sts2-v0.107.1-sts2mcp-55e0648.json).

The archive matched all 431 source files and had no symlinks. The owner launched it and saw the
main menu. The running executable and bridge listener belonged to this preserved copy; the
existing installation guard, bridge v0.4.0 check and public menu projection passed.

Private evidence in the archive is `archive-record.json`, `launch-verification.json` and
`verified-menu-snapshot.json`. The successful launch record supersedes the archive inventory's
initial `launch_verified: false`, recorded before the launch test.

## Existing owner launcher

With the normal Steam client running under the licensed account, the existing launcher is:

```bash
bash "$HOME/Library/Application Support/SpireShift/frozen-games/sts2-v0.107.1-build-23811903/Launch Frozen Spire.command"
```

It starts the preserved executable from a launch context containing App ID `2868840`. Direct
launch without that context failed Steam initialization during the first probe. This procedure
does not establish an offline or DRM-independent launch. Steam update settings were not changed.

For later SpireShift installation checks, set `SPIRESHIFT_GAME_DIR` to the preserved
`steamapps/common/Slay the Spire 2` directory. Otherwise automatic discovery can select the
Steam-managed installation. Preserve the archive's Steam directory layout and copied app
manifest, and verify that the bridge listener actually belongs to the archived executable.
Keep strict version/hash checks enabled. See the [live adapter](live-state-adapter.md).

## Remaining checks

- After a normal future Steam update, the owner retests this launcher and the executable/bridge
  identity. The successful test so far occurred before such an update.
- Before learned-policy playback, verify save/profile isolation, compatible model/action
  integration and relevant simulator-to-live behavior. The archive alone does not isolate saves.
- Use the existing [guarded live executor](live-action-execution.md) and retain unsupported,
  mismatch and failure accounting. The owner launches and monitors all game attempts.
- Freeze final model/data/split/objective/dependency/hardware metadata for the patch study when
  the foundation is ready. A menu test is not a full-run or model-quality benchmark.
