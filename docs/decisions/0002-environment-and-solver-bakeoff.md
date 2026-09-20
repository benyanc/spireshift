# ADR 0002: Environment and solver bakeoff

- Status: Accepted
- Date: 2026-09-19
- Issue: [#2](https://github.com/benyanc/spireshift/issues/2)
- Evidence: [environment-candidates.json](../environment-candidates.json)

## Context

SpireShift needs two properties that no single public backend currently provides with adequate
evidence:

1. an authoritative, player-observable reference for exact evaluation; and
2. cheap cloning and high transition throughput for teacher generation and search.

Using only the installed game would make self-play prohibitively slow. Using only a reimplementation
would make it easy to train against silent simulator errors. The bakeoff therefore selects components
for distinct roles rather than assigning one aggregate score to unlike systems.

The mandatory gates were:

- an explicit reuse license for every dependency;
- a versioned game and dependency identity;
- full-run decisions or a clearly bounded combat-only role;
- observable failures and unsupported decisions rather than silent losses;
- a public-information interface for policy, search, and evaluation;
- deterministic replay or enough provenance to reconstruct a failed run;
- affordable parallelism for training and search.

A repository's MIT license covers its code. It does not grant rights to redistribute Mega Crit's
game assemblies, assets, decompiled source, saves, or other proprietary material. SpireShift will
require a legally installed copy for exact-engine work and will not commit those materials.

## Decision

SpireShift will use a **two-engine architecture with differential validation**.

```text
installed STS2 vP ──> exact reference adapter ──> public observation/action trace
       │                                                   │
       └──────── version/content identity ─────────────────┤ differential checks
                                                           │
EvanGambit emulator vP ──> cloneable training/search API ──┘
                                   │
                            policy, MCTS/PUCT,
                            teacher data, self-play
```

### Authoritative reference

Use [rsgcsg/STS2-headless v1.0.1](https://github.com/rsgcsg/STS2-headless/tree/v1.0.1)
with its pinned [STS2 Connector v1.1.0-rc.1](https://github.com/rsgcsg/STS2-Connector/releases/tag/v1.1.0-rc.1)
as the frozen reference adapter for the documented macOS arm64 STS2 `v0.111.0/41cef1ea` tuple.

This stack keeps rules, RNG, legality, effects, and action commitment in the installed game. Its
Snapshot/Read/BoundAction/Receipt contract explicitly rejects stale actions, incomplete action
catalogs, unknown delivery, missing successors, identity drift, and mid-episode runtime changes.
Those properties are more valuable for benchmark authority than raw speed.

The repositories are archived. We therefore treat `v1.0.1` as immutable evidence, not an
auto-updating dependency. New game versions receive no inherited authority. Porting to a new patch
requires a new manifest, the conformance suite from issue #13, and fresh differential evidence.

Use active [wuhao21/sts2-cli at `084d1aa`](https://github.com/wuhao21/sts2-cli/commit/084d1aa3d8e118ca7ce8d8774ad16d6be9c92367)
as the upstream for exact out-of-game workers. It runs the installed `sts2.dll` with documented IL
patches and Godot stubs, supports all five characters and full-run decision screens, and targets
STS2 `v0.111.0`. Its raw protocol is not automatically a fair-player interface; SpireShift must
project it through `observation-v1` and exclude hidden RNG or native operands before any policy can
consume it.

Exact workers are qualification and data-validation tools. They are not the default self-play
engine. Published measurements for the shipped reference process are roughly 0.5 normalized
decisions per second for one Windows worker. The managed route reports hundreds of decisions per
second per environment and low-thousands in parallel on an Apple M4, but its own documentation
labels the fast projection partial and not broadly qualified. We will reproduce measurements on our
workload before using them in a headline.

### Training and search backend

Use [evangambit/sts2 at `37e4264`](https://github.com/evangambit/sts2/commit/37e4264115546b6ac640d54aab3d7e2ac6983d2d)
as the starting full-run training and search backend.

It is the strongest licensed candidate for this role because it already provides:

- a C# NativeAOT rules engine and in-process Python/Gymnasium binding;
- full-run and combat environments with legal-action masks;
- cheap combat and run cloning;
- public-information determinization of unknown draw order;
- all five character pools, maps, rewards, shops, events, rests, potions, and broad relic coverage;
- source audits, live captures, differential traces, and an explicit divergence catalog;
- MaskablePPO, MCTS, learned policy/value experiments, and command-shaped replay tooling.

At the pinned commit it targets STS2 `v0.107.1`, while our exact candidate targets `v0.111.0`.
It is therefore **selected but not admitted** for training labels or evaluation until its content is
refreshed and issue #13 passes on the selected patch. Its README also records incomplete exact
Neow/shop/reward/event odds and 46 unimplemented later ancient relics. Unsupported states and
divergences must remain in benchmark denominators.

On this project's Apple M4 Pro host, a clean NativeAOT build at the pinned commit measured 23,187
environment steps/second and 133,491 clone-and-destroy operations/second using
`rl/agent_probe.py --steps 5000`. This is a local engineering measurement, not a cross-backend
comparison: an emulator step is not the same unit as the reference stack's normalized semantic
decision.

We will consume the emulator as a pinned external backend with attribution before considering a
maintained fork. SpireShift's research contribution remains terminal-victory learning, adaptive
inference compute, exact-engine validation, and cross-patch recovery; it will not claim the emulator
as original work.

### Live bridge and combat fallback

[Gennadiyev/STS2MCP at `55e0648`](https://github.com/Gennadiyev/STS2MCP/commit/55e064850a68f3b4cde7e5fd525bf9b2dec4e885)
is the live-game fallback and fixture-capture tool. It has the largest community, an MIT license,
cross-platform mod support, and broad menu/run control. Its release and documented test versions
lag the selected exact tuple, and its payload has not passed SpireShift's information-boundary
audit. It cannot be benchmark authority until it does.

[Torch1230/CombatSolver v0.43.0](https://github.com/Torch1230/CombatSolver/releases/tag/v0.43.0)
is the combat-only fallback and an external fixed-search comparator. It targets v0.111.0 combat,
uses isolated simulated branches, exposes adjustable search budgets, and stops at unsupported
boundaries. It optimizes survival, victory, combat damage, and resource use rather than terminal
full-run victory, so its recommendations are never a substitute for SpireShift's run-level target.
If full-run simulator admission slips, it can unblock the M3 combat-search infrastructure and
compute-quality curve. It cannot satisfy the final project claim.

## Candidate disposition

| Candidate | Strength | Blocking weakness | Disposition |
|---|---|---|---|
| STS2 Headless + Connector | Exact installed-game authority, strict identity and fair-player contract | Archived; narrow frozen tuple; slow shipped host | Reference authority |
| sts2-cli | Active exact-engine full-run CLI on v0.111.0 | Patched engine and raw protocol need qualification/projection | Exact-worker upstream |
| EvanGambit/sts2 | Broad full-run NativeAOT emulator, cloning, Gymnasium, measured search work | v0.107.1 and incomplete late content/parity | Training/search backend after admission |
| STS2MCP | Mature community live bridge and cross-platform mod | Patch lag, no clone, real-time speed, information audit pending | Capture/live fallback |
| CombatSolver | Current-patch combat search with parallel budgets | Combat-only objective and coverage | M3 fallback/comparator |
| lain-wood/sts2core | MIT pure Rust core, expectimax, paired act-level advisor | v0.107, incomplete content, different evaluation surface | Independent comparator later |
| BUCKFAE/headless-in-the-spire | Loads real assembly and emits native replay artifacts | Older, early development, large runtime patch surface | Not selected |
| Zamiell emulator | Licensed NativeAOT origin | Superseded by the more complete EvanGambit fork | Not selected directly |
| yizhang-dream/sts2-simulator | Full-run Python interface and high self-reported throughput | No detected license; private regeneration/override layer | Rejected |
| zhiyue/sts2-rl-agent | Simulator, PPO, and live bridge | No detected license and older parity surface | Rejected |

The complete evidence snapshot, including commits, coverage, replay, crash behavior, throughput, and
information-boundary notes, is stored in `docs/environment-candidates.json`.

## Admission and patch policy

Every backend must expose the same SpireShift contract and pass the following gates before its data
can support a result:

1. Record game build, assembly hash, backend commit, adapter version, objective version, seed, and
   information-policy version.
2. Convert only player-observable state into `Observation.public_state`; privileged diagnostic data
   remains separately marked and is excluded from model input.
3. Enumerate a complete legal-action set or fail the transition as unsupported.
4. Run paired public-state traces against the exact reference and report the first divergence.
5. Count crashes, stalls, unsupported decisions, settling timeouts, and version mismatches in the
   denominator.
6. Requalify after any game, backend, adapter, modset, schema, or information-policy change.

Training may use an admitted emulator patch. Final headline systems must also be evaluated through
the exact reference on a powered subset of complete runs. Emulator-only results must be labeled as
such.

## Local verification performed

- `evangambit/sts2@37e4264` built successfully as an `osx-arm64` NativeAOT library on Apple M4 Pro.
- Its `agent_probe` completed and produced the local throughput measurements above.
- `rsgcsg/STS2-headless@v1.0.1` passed 154 Node tests, six Python client tests, documentation-link
  checks, and its repository-boundary check; one proprietary integration test was skipped as
  designed.
- SpireShift now detects the installed macOS arm64 STS2 v0.107.1/build 23811903 and binds its
  assembly fingerprint to the pinned EvanGambit ruleset manifest.
- `STS2MCP@55e0648` builds with no warnings against that installed assembly. SpireShift's local
  adapter binds the same game fingerprint and bridge version before projecting public state. Its
  fixture audit covers all 18 actionable states and its Defect Ascension 0 full-run action gate
  passes with a 167-step terminal run and zero unsupported decisions.
- After the game's one-time mod consent, the adapter captured the real main-menu state through the
  local bridge and the resulting document conformed to `live-snapshot-v1`.
- The guarded action boundary applied one noncombat menu action and one combat card action in the
  visible installed game. Replaying either request ID returned `duplicate`; the combat replay left
  the enemy at the already-observed 40 HP.
- At `evangambit/sts2@37e4264`, 4,801 C# tests, 31 native-boundary tests, and 420 non-skipped
  live-fixture checks passed locally. Six legacy per-turn-hand checks were explicitly skipped. The
  fixture inventory and limitations are preserved in
  [the conformance evidence](../evidence/evangambit-v0.107.1-conformance.json).
- No divergence was observed over the executed v0.107.1 capture surface. The result is conditional:
  the captures are upstream evidence, incomplete mechanics remain documented, and the SpireShift
  public-state adapter does not exist yet. The backend therefore remains `pending_conformance`.
- The frozen Headless/Connector reference targets v0.111.0, so it cannot be run against the installed
  v0.107.1 assembly as though the builds were interchangeable.

## Consequences

- We avoid spending the first months rebuilding a simulator that already exists.
- Exact-engine and emulator results remain separate until differential evidence connects them.
- Patch updates have an explicit cost: refresh the fast backend, regenerate manifests, and rerun
  admission rather than silently treating old parity as current.
- Search and model code depend on SpireShift contracts rather than a third party's observation
  layout, allowing a backend to be replaced without rewriting the agent.
- A missing local game installation blocks live conformance, but it does not block adapter design,
  emulator integration, model work on admitted frozen fixtures, or the M3 combat fallback.
