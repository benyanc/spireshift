# Public combat diagnosis after the negative comparison

[Issue #133](https://github.com/benyanc/spireshift/issues/133) records this package. The owner
completed comparison #131: base-v10 and base-v2 both lose all 32 games and neither reaches the
first boss. Their mean maximum floors are 6.625 and 6.65625. There are no failures, truncations,
unsupported combat screens, cycles, CPU exhaustion or no-op fallback uses. This is a valid
negative development result, not evidence of improved play. Base-v2 remains accepted.

## Completed result, 2026-10-08

The owner completed all **64 original seed/model replays**. Source reconciliation and analysis
integrity pass, with zero failed or mismatched replays, binding failures, shadow failures or
non-combat score drift. Cached source/case/report verification passed with zero new games,
transitions or predictions. [Issue #133](https://github.com/benyanc/spireshift/issues/133) is complete.

The diagnostic report is
`sha256:cedac599325a05d92dd5deda8ec6a8cb3573a4b9cd75cf905451b330a5912398`, saved at
`artifacts/diagnostics/sts2-v0.107.1-base-v10-combat-confirmation-v1/diagnostic.json`.
The owner-run resource report is
`sha256:c3b764193d7a14b89fba20d460528f13b73cc576204901b4b5ce8990d328de22`: 144.493 wall /
143.426 CPU seconds, 64 replays, zero search simulations and 5,457 transitions, without a cap.

On the reference paths, shadow scoring changes 200 end-turn choices to potion choices and 35
card choices. On the candidate paths, those counts are 44 and 61. Public card coverage gaps
remain. These different path populations are descriptive evidence, not matched counterfactuals
or proof that an available action would prevent death. The original comparison still shows no
playing benefit, and base-v10 remains unpromoted.

No further replay is needed. [Issue #134](https://github.com/benyanc/spireshift/issues/134) now
provides a [frozen neural combat pilot](neural-combat-policy.md) using shared public card
properties and nonlinear state/action interactions. The owner runs its first saved-data stage
before further experiments. See the [current backlog](backlog.md). The coding agent has run no
real diagnostic replays.

The completed protocol used one worker and caps of 600 wall seconds, 1,200 CPU seconds,
4 GB memory and 250 MB output. The existing `scripts/diagnose-combat-confirmation-v1.sh` supports
cached display/resume; it is an archived procedure, not the next task. The remaining sections
describe that protocol and its limitations.

## What the diagnosis measures

Each case stores public observations, the exact ordered legal menu, both frozen policy score
vectors, the executed action and the actual transition. Combat choices have explicit card,
target, potion and end-turn bindings, visible player resources/enemy intents and public card
IDs absent from the fitting or reliable-label coverage. The coverage comes from the already
verified saved audit, without reopening the 1,299 teacher case files. In-hand upgrade/transform
choices use the existing public layout v3; unsupported bindings are explicit errors.

Paired analysis identifies the **first different action while both paths still have identical
observations and menus**, checking identical scores on identical inputs. Once actions differ,
later decisions belong to different paths. Shadow scores still compare both models on each
individual situation; later path totals are descriptive and must not be treated as matched
counterfactual outcomes.

The summary records disagreements by decision type and combat action kind, end turns with a
legal card/potion available, deaths after end turn, coverage gaps, and pointers to the final
eight combat decisions in each case. It includes visible HP before/after the last completed
transition when available. These observations guide the next intervention; they do not prove
that an available card would have prevented death, that a missing card caused a loss, or that
a confident score was a good action-value estimate. No alternative action is simulated.

## Frozen inputs and integrity

Diagnostic plan:
`configs/combat-replay-diagnostic/sts2-v0.107.1-base-v10-confirmation-v1.json`,
`sha256:f4db4d06f44d4c20d3112775754c7bc0cb1c8c1937916a085fb3431eebf440c9`.
It binds the original confirmation plan, its exact comparison and resource IDs, objective and
fixed replay protocol:

- Confirmation plan: `sha256:faa09afa7ee9f08b0ea329e53b3a5a6d4c27d2167edd88353920b32769425752`.
- Comparison: `sha256:3ae9c8644e653321f81d7ee3c28cc1bc9724a5225c238932d3daa31db1e7c850`.
- Comparison resource: `sha256:9e50a55d6116b2160b66039137fe79e075af5971ee76070850bb2ff68656141f`.
- Fitting coverage audit: `sha256:57666476aa7c42ce76cb46a44e9eb422ab7bfb21abf4b752e8cb0110ab3948fd`.

The confirmation plan binds candidate base-v10, reference base-v2, complete-run seed ownership,
admitted patch/ruleset and all existing guards. All **32 inspected train seeds at offsets
504–535** and both models are required; this is diagnosis of development evidence, not fresh
confirmation or a new strength benchmark. Public input hashes and candidate ordering must
reconcile. Models consume no hidden state; the diagnostic cannot clone or resample the engine.

Each replay must match its original action digest, final public state hash, decision count,
status, terminal/floor/act outcomes and guard/cycle diagnostics. Timing is deliberately not an
equality condition: shadow inference and recording add overhead. The original 128-CPU-second
run cap and 4,096-decision limit still apply, with diagnostic overhead charged. The outer job
report measures all work. These times do not replace the original comparison's latency or
policy compute measurements.

Every failed, unsupported, capped or mismatched replay remains in the original **64-case
denominator**. Only verified replays contribute descriptive choice totals; the excluded count
is explicit. A shadow-scoring failure is recorded without replacing the driver's action.
Non-combat score drift, unsupported bindings or inconsistent shared-prefix scores block an
integrity pass even when a replay reproduces its original outcome. There is never automatic
model promotion, a readiness pass or adaptive-controller authorization.

## Interruptions and cached results

Rerunning the same script validates saved cases and runs only missing ones. Failed or mismatched
saved cases are never replayed to seek a better outcome. A completed result is only verified
and displayed; no backend is initialized and neither model makes a new prediction. Changed
plans, models, source cases, public traces or summary arithmetic cause a stop. Existing
resource reports are preserved and each resumed attempt receives a new numbered report.

Work counters start at zero before preflight and update after each new attempted case, including
failed work. Cached cases are not charged as newly played games. A hard interruption inside an
unsaved attempt has incomplete counters; the wrapper's CPU/wall use remains measured and that
unsaved work must not be reported as a measured zero. Full traces stay ignored under `artifacts/`.
