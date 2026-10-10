# Actual-engine v0.111.0 qualification

The owner accepted [ADR 0005](decisions/0005-actual-engine-v0.111.0-qualification.md).
Exact acquisition and preservation [#144](https://github.com/benyanc/spireshift/issues/144) are
complete. Public control/mechanics [#145](https://github.com/benyanc/spireshift/issues/145) are current;
full-run speed and neural integration [#146](https://github.com/benyanc/spireshift/issues/146) follow.

## Current status — no acquisition command pending

The owner successfully downloaded the exact macOS depot using the pinned licensed
DepotDownloader route. The downloaded executable, rules DLL and GodotSharp match **v0.111.0 /
41cef1ea**. The request was app `2868840`, depot `2868842`, manifest `5045320271505434676`, with
explicit `public-beta` context. The owner reports **1,323,157,968 bytes downloaded /
2,406,415,347 bytes extracted**. The earlier Steam-cache transfer estimate remains historical;
the successful result does not prove which change resolved the earlier access failure.

Codex froze the copy at
`~/Library/Application Support/SpireShift/frozen-games/sts2-v0.111.0-41cef1ea-macos-arm64-v1`,
with the full game at `steamapps/common/Slay the Spire 2`. All **435 files / 2,406,594,686 bytes**
matched the source, including depot metadata. Freezing took **6.046 seconds**; a separate current
integrity check passed in **1.411 seconds**. No old Steam app manifest was borrowed or fabricated.
The download, frozen archive and existing v0.107.1 game remain distinct copies. Details:
[acquisition/preservation evidence](evidence/actual-engine-v0.111.0-acquired-and-frozen-v1.json).

## Completed first native prerequisite package

The repeatable `engine bootstrap-profile` command starts one unmodded shipped-game headless
process in a new disposable working copy and uses a fresh native profile. The depot's launcher
arrived with permission `0644`; the working copy alone changes it to `0755`. Its content hash,
all game rules DLLs and assets remain unchanged. The preserved source retains its original mode.

A small `override.cfg` beside the working executable selects a private save folder under
`~/Library/Application Support/SpireShift/engine-profiles`. Godot documents this exported-game
settings override; see [ProjectSettings](https://docs.godotengine.org/en/4.5/classes/class_projectsettings.html)
and its [4.5.1 loader](https://github.com/godotengine/godot/blob/4.5.1-stable/core/config/project_settings.cpp).
The game itself creates schema-8 settings, progress and preferences. The process keeps operating
system directory environment variables unchanged, disables Steam before platform initialization,
and has file-write restrictions over shared saves, Steam's managed directories and frozen archives.
This first unmodded boot also denies networking.

The canonical capped stage completed in **45.279 wall / 11.226 CPU seconds**; the native process
used **35.670 seconds**, exited naturally, and used the expected private save location. All eight
checks passed: native settings creation/schema, logged save path, Steam disabled, unchanged shared
saves, unchanged working payload, preserved archive integrity and natural exit. The shared save
sentinel covers 404 entries, including content, permissions and modification times. Every retry
gets a fresh attempt and profile; incomplete logs/markers stay private.

There were **1,090 error lines and two warnings**, including rendering/shutdown diagnostics.
They are retained rather than treated as clean runtime evidence. This is a **boot/profile pass**,
not a verdict about interactive menus, action completion, mechanics, full runs or model strength.
The earlier exploration's permission failure also remains recorded: the sandbox wrapper exited
before the game could start. Its old launcher-invocation count is not a completed game launch.

The separate `engine model-inventory` command verifies the frozen archive, pinned clean source
checkouts and local ILSpy launcher/command/decompiler fingerprints before targeted inspection.
It binds the game's generated `AbstractModelSubtypes.All` entries to exact declared types, checks
all indices/counts and refuses missing, duplicate or ambiguous entries. The command completed in
**3.821 wall / 2.808 CPU seconds** and resolved **all 1,660 types** with zero unresolved bindings.

The registry includes **603 card, 299 relic, 66 potion, 283 power, 98 encounter, 69 event, five act
and eight character type entries**, plus pools, monsters, enchantments and other families.
Those are declared type counts, including test and retired content; they are not counts of content
actually offered in normal play. In particular, eight character types are not eight selectable
heroes. The 65 mock/test/deprecated name or namespace hints are incomplete availability diagnostics.
Every offered-content flag stays unknown. This static registry is distinct from the lazily
instantiated live `ModelDb.All`, runtime effect properties and the reachable game state space.
No extracted inventory is a policy input. Raw inventories/decompiled sources remain under ignored
private artifacts; public evidence contains only counts, hashes and scoped conclusions.

The [native prerequisite evidence](evidence/actual-engine-v0.111.0-native-prerequisites-v1.json)
binds the configuration, archive, inspection, boot and resource reports. It includes the earlier
exploration and keeps zero full-run attempts, optimizer steps and training admission explicit.

## Next development work

Connect the pinned released Connector in a separate working copy and verify a fresh public menu,
loaded modset and completed native action. Then build the CLI candidate from the same verified
rules/assets, recording all patches/stubs. Qualify resets/seeds, actual A8 rules and final victory,
complete public observations and refreshed legal choices, and the targeted 25–30-scenario mechanics
panel. Costs/modifiers, status amounts, counters, secondary intents and repeated rest/shop/reward
choices must stay attached to their public owners. Add discovered gaps to the content-driven matrix.

Measure complete-run speed and failure rates only after those gates. New learning has new
engine/input/data identities; v0.107.1 weights, encoders and experience are not silently migrated.
Ironclad/A8 and terminal full-run victory remain fixed. Adaptive thinking waits for a useful base
player. Codex can do short checks with caps; jobs expected to take five minutes or more receive
one specific owner command and stop at that stage. These prerequisites launch no training or
automatic game campaign, and there is no new long owner task prepared by this package.

## Historical acquisition helpers and developer reference

The first Steam-console request failed with **No connection**; the local content log reported
**Access Denied** with an empty branch. The owner then reported two **InvalidPassword** attempts.
Those failures remain evidence, with no credentials copied into SpireShift records. The subsequent
licensed download passed the unchanged game fingerprints. DepotDownloader owns its local .NET
authentication storage; SpireShift does not read Steam client credentials.

The pinned 3.4.0 source supports branch-specific manifest requests and interactive password/Steam
Guard or mobile QR authentication; see the
[pinned README](https://github.com/SteamRE/DepotDownloader/blob/c553ef4d60c00a4f5fd16c9fe017f569001589ff/README.md).
`scripts/acquire-headless-game-v0.111.0-v2.sh` remains a historical/reconstruction helper with a
one-hour cap and exact-manifest validation/resumption. It has no latest-beta or branch-switch
fallback. Its release-asset digests are observed fingerprints, not publisher-signed checksums.
The v1 console helper and `scripts/freeze-headless-game-v0.111.0-v1.sh` also remain available.

Identity commands are `engine preflight`, `engine freeze` and `engine verify-archive`; acquisition
commands are `engine download-command`, `engine download-plan` and terminal-only `engine download-game`.
The new `engine bootstrap-profile` and `engine model-inventory` each take the unchanged identity
configuration and the separate `sts2-v0.111.0-native-bootstrap-v1.json` configuration. Output paths
are write-once. Native attempts are fresh, have private failure markers and do not reuse a cached
boot success. The game process has a 60-second cap plus bounded child-group cleanup, and registry
tool calls each have a 45-second cap. Actual canonical jobs also used the existing resource wrapper
with 240/180-second elapsed caps, explicit CPU/memory/storage limits and immutable reports.

The source/decompiler checks and file archive never admit a training backend. Profile bootstrap
is distinct from a supported GUI/offline launcher, and this check does not establish long-term
credential-independent playback. The older verified live-menu procedure remains in
[frozen-live-game.md](frozen-live-game.md).
