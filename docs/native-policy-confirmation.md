# Fresh-seed standard-player confirmation

Prepared 2026-10-18 for #143 / #35 / #146. The completed learning curve improved
development mean floor from 6.28125 to 9.09375 under the standard 32-game / three-pass
method, with no full wins. This comparison tests whether that progress repeats on
new seeds. It does not train, select another checkpoint or promote a player.

**Completed:** all 256 attempts finish without failures. Original mean floor is
7.2890625 versus trained 8.859375; the predeclared auxiliary criterion passes,
with zero full wins. See the [result and next work](native-policy-confirmation-result.md).
The prospective plan below stays preserved; its completed command only verifies results.

## Frozen plan

Use both original numerical initializers (2 and 3) and their own final standard
players after exactly 512 training games. All four state files, model IDs and
complete Adam states stay unchanged in the completed study. The loader verifies
their source report, original chunk receipts, final evaluation model identities,
state hashes and environment/score identities. No intermediate checkpoint is eligible.

For each initializer, reserve **64 new complete-run seeds** and run both original
and trained player on each: **128 distinct seeds / 256 attempts total**. The two
initializers get disjoint panels. Neither training, development nor the separate
eight-game runner control uses these seeds. Both numeric IDs and native seed strings
are checked against all 16 prior native seed manifests plus this runner's control.

Keep the original frozen v0.111.0 / 41cef1ea Ironclad/A8 environment, startup profile,
tutorials, mechanics admission, public inputs, all legal actions and whole-run CPU
budget. Use the same sampled softmax behavior and temperature **0.8** as the original
development evaluation. The unchanged RNG salt couples the two players on each
seed without including the model ID or checkpoint version. This is a comparison
of sampled players; greedy play is a different experiment.

## Outcomes and interpretation declared before the batch

Full-run wins remain the primary goal. Report wins and failures for each original
and trained player, and aggregate them with all **128 attempts per version** retained.
Also report maximum floor, paired higher/tied/lower-floor counts and win discordance.
Failed attempts contribute **zero floor and zero wins** to the confirmation endpoints;
the raw reached floor and error remain in the separate collection summaries.

For auxiliary progress to be confirmed, require all of:

- Positive average paired floor change for each of the two trained players.
- A positive lower endpoint of the pooled 95% paired floor-change interval.
- No reduction in observed wins for either player, and no failed games.

The interval uses 10,000 fixed-seed percentile bootstrap samples, resampling whole
game seeds within each fixed initializer. It describes these two trained players,
with one sampled trajectory per player/seed. It does not cover a population of
training initializers or remove sampling uncertainty from individual decisions.
The short control cannot confirm progress regardless of its outcomes.

Even a positive floor result with zero full wins is only an auxiliary learning
milestone. No result automatically promotes a checkpoint, satisfies base/value/search
readiness, trains an adaptive controller or launches more training. If improvement
repeats, the next package can specify bounded continuation of **both** standard
players with their saved weights and complete Adam state on fresh training seeds.
If it does not repeat, investigate action credit/qualified teachers before scaling.

## Execution, restart and evidence

The runner interleaves original and trained players in **eight-game chunks**, with
two qualified isolated native workers. They share frozen game/runtime/SDK/support
code; no app copies are made. Existing worker retirement, shutdown proof, public
behavior reconstruction and streaming delivery audits remain unchanged. Compact
sealed outcomes and paths are retained rather than every game's history in memory.

Every committed chunk seals its exact task, seeds, model and output files. Clean
restarts verify and reuse completed chunks. Uncommitted/uncertain chunks are preserved
and stop the script; they are never replayed or reset automatically. Missing or
unauditable games stop. A retired failed game stays in the original denominator;
at most two are tolerated per complete 64-game player panel, not two per chunk.
Any failure prevents a positive confirmation under the rule above.

The single command below may continue clean 15-minute sessions within the same
fixed comparison. A failed/capped session stops without automatic retry. Re-running
the command resumes a clean pause; after completion it verifies saved results and
plays no more games. Source/config changes invalidate the saved identity.

Expected duration: **10–20 minutes**, based on the eight-game check's 69.46-second
resource time, smaller two-game chunks and repeated startup/input/audit overhead.
It is an estimate, not a deadline. Limits are one hour per invocation, 15 minutes /
1,800 CPU seconds per session, 4 GB RAM and 2 GB retained comparison output. Existing
shared frozen files and the prior experiment are excluded from generated-output
storage accounting and remain protected by hashes. No extra launch follows completion.

The owner launches and monitors this batch under the five-minute execution boundary.
Close any running STS2 game, then run this **one command** from any directory:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/confirm-native-a8-policy-v1.sh
```

Workspace and final summary are recipe-owned:
`artifacts/native-confirmation/sts2-v0.111.0-a8-standard-fresh-v1/report.json`.
The agent has not started any of those 256 attempts.

## Short checks already completed

The separate four-player bridge completed **8/8 attempts, zero failed games**, with
zero optimizer updates and zero app copies. Its tiny panel is a delivery/integration
check and is excluded from the fresh comparison. Historical source/player files and
shared inputs remain unchanged. The control's resource time is **69.46 seconds**,
peak RAM **734.66 MB**, retained output **20.86 MB**; full repository checks are measured
separately. See [sanitized evidence](evidence/native-policy-confirmation-v1.json).

New tests exercise exact paired ownership, final-player binding, prior-seed overlap,
changed evaluation settings, corrupted/uncertain evidence, no replay, failure
denominators, fixed confirmation criteria, and restart/cap behavior. The complete
repository checks pass before the local commit. No push or GitHub Actions is needed.
