# ADR 0005: Qualify a separately frozen actual-engine learning environment

Accepted 2026-10-10 following the owner's explicit choice. This changes the next environment
work and future training lineage. It does not change the terminal-victory objective, computation
constraint, fixed Ironclad/A8 priority or foundation requirement before adaptive thinking.

## Decision

Preserve the existing launchable v0.107.1 real game, admitted simulator tuples, repaired public
encoders, models, data and negative experiment results. Obtain a separate privately owned full
v0.111.0 game copy and qualify the actual-game headless reference and patched-assembly CLI against
that exact copy. Do not silently run old experiments or interpret emulator IDs on the new patch.

The documented macOS arm64 headless tuple is v0.111.0 / game commit `41cef1ea`, with explicit
executable, `sts2.dll` and `GodotSharp.dll` hashes. The CLI documents testing Steam public-beta
build `24724944`. These are separate upstream observations; equal display versions alone do not
prove identical engine bytes or assets. Exact fingerprints and common game-copy provenance must
join them before a same-build comparison. Both released headless tags and its initial preview
target v0.111.0; a documented v0.107.1 release was not found.

This supersedes ADR 0002's selection of EvanGambit as the immediate bulk-learning backend and
ADR 0003's v0.107.1 environment priority for future work. Their historical evidence remains intact.
The scoped admission in ADR 0004 remains bound to its original tuple; it does not qualify new
engine inputs or settle the newly identified observation/native mechanic gaps. The prepared v3
large emulator pilot is deferred. Its relational repair and synthetic controls remain useful code
and evidence; they do not repair mechanics or information never exported by an environment.

## Ordered packages

1. [#144](https://github.com/benyanc/spireshift/issues/144): pin identity and source revisions,
   implement no-launch preflight and immutable private archive tooling, and obtain the exact game.
   File integrity is not boot, profile isolation, mechanics or training admission.
2. [#145](https://github.com/benyanc/spireshift/issues/145): verify isolated profiles/modsets and
   reset/seed/terminal semantics, extract the game-owned content inventory privately, project
   complete public state/actions, and execute targeted same-build mechanics comparisons. Keep
   per-copy costs/modifiers, counters, secondary intents, full visible menus and repeated choices.
   Refresh legal choices after each action, including rest sites, shops, rewards and submenus.
3. [#146](https://github.com/benyanc/spireshift/issues/146): measure complete-run speed and failures
   first at one worker, then in a bounded parallel panel. Reuse existing outcome-trained PPO,
   disposable workers and resource tracking behind a separately versioned actual-engine interface.
   Prepare a finite owner pilot only after qualification and a short actual-engine learning check.

We do not assume the shipped host is too slow from unrelated published throughput. The CLI's
timing/queue patches and rendering stubs also need verification; using the real rules assembly
does not automatically prove equivalent execution or a complete public observation interface.

Keep EvanGambit as a v0.107.1 historical and possible later search candidate. A costly port is not
a prerequisite to direct PPO, which collects trajectories without cheap state cloning. A true
three-way fidelity comparison requires a common patch; cross-patch win rates cannot establish
engine fidelity. Choose a port or qualified older adapter only if later evidence justifies it.

## Acquisition and execution

The owner's local Steam cache associates macOS depot `2868842`, manifest
`5045320271505434676`, with beta build `24724944`. The cache is identification evidence, not
confirmation of present download access or of the downloaded bytes. The owner uses their licensed
Steam client to request that exact manifest; download failure is retained, and a later or different
beta is never substituted automatically. Hashes and assets are checked before archival/qualification.

Game payloads, inventories and extracted proprietary material stay outside Git. Preserve the full
app and resources outside Steam-managed `steamapps`, not only its rules DLL. Keep saves/profile
isolation and actual launch verification as distinct remaining checks. Do not install the old
v0.107.1 bridge into the new game or claim an offline/DRM-independent preserved launcher.

Codex may run short jobs. The owner launches and monitors jobs expected to take five minutes or
more, including the roughly 1.3 GB download. There is one clear next owner action, no automatic
large training job, difficulty change, GA scaling, controller, final-test opening or promotion.

Sources: [headless exact compatibility](https://github.com/rsgcsg/STS2-headless/blob/4961b52a587777277816bc4407108f6f4274f801/docs/COMPATIBILITY.md),
[CLI at its pinned revision](https://github.com/wuhao21/sts2-cli/tree/084d1aa3d8e118ca7ce8d8774ad16d6be9c92367),
and the owner's private `steam-cache-observation.json` under the qualification artifacts.
