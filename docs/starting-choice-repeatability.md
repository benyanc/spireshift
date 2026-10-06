# Starting-choice lesson repeatability

[Issue #128](https://github.com/benyanc/spireshift/issues/128) implements one bounded study after
the completed [starting-evidence diagnosis](starting-evidence-diagnosis.md). The question is
whether option/context lessons repeat on fresh independent game seeds before another small
starting-choice training attempt. The audit found opposing realized lessons, but did not establish
whether missing public context or variation in futures caused them. Accepted base-v2 remains fixed.

## One owner command

From the repository directory, run only:

```bash
bash scripts/study-starting-repeatability-v1.sh
```

The owner launches and monitors this job. It verifies prior evidence, collects the fresh cohort,
verifies the saved cases and writes one analysis. **No training follows.** It uses four workers,
with caps of **30 wall minutes**, 7,200 CPU seconds, 4 GB memory and 1 GB output. These are limits,
not predicted durations. Progress is printed every eight completed seeds. Share the final summary.

Interrupted attempts keep separate resource reports and resume only missing complete seed cases.
Failed cases remain immutable evidence. If collection finished before an interruption in analysis,
the next attempt verifies/analyzes the saved collection without loading the game backend. A
completed study rerun checks/displays the saved report's identity and frozen bindings, without
repeating collection or source-case verification. Existing results are never replaced.

## Frozen sample and information boundary

The configuration is `configs/starting-repeatability/sts2-v0.107.1-base-v2-train-v1.json`, identity
`sha256:b1c8e17beecd00e9b049e29623facd33badbb2c484d2adb966587b8dee52948c`.
Its nested collection config is
`sha256:684986ffa849f1b49bff60162bc94bed25165a19d9e271b723a47695e1178a3f`.
It preserves the admitted v0.107.1 ruleset, immutable base-v2 model/report, corrected frontier
ranking and terminal-victory ObjectiveSpec.

The cohort is **192 train seeds**, offsets 312–503 in the frozen split manifest: 144 discovery
seeds and 48 confirmation seeds. Complete-run ownership is fixed by the salted assignment before
outcomes. All three initial options are evaluated per seed, giving up to **576 trajectories**,
not 576 independent examples. Only decision zero is forced; all later choices use base-v2.
The existing collector checks exact reset alignment and public option/action binding. There is
no hidden-world cloning, RNG editing or forced unavailable menu, avoiding the unresolved #105
clone defect. Each option sees one deterministic seeded future.

A conservative protected prefix excludes the first 312 train seeds. Seven frozen, content-addressed
prior report inventories also check disjointness against earlier curricula and trajectory
preferences, including inspected validation evidence. Their seed metadata is verified; the study
does not re-audit or replay every original teacher rollout. The full 64-case historical starting
collection is checked with its existing saved-case contract. Only its 48 fitting seeds enter
historical matching and discovery; the 16 old selection seeds never supply target votes.
A bounded implementation check verified the seven inventories, historical report identity and
new seed window in 0.044 seconds without loading trajectory cases or starting an environment.
The full historical/source-case verification remains part of the owner job.

## What is compared

Each completed case keeps all three pair comparisons, canonicalized by visible option ID rather
than execution position. The report retains ties, activity-only exclusions, rank components and
signed differences in each outcome measure. Failed/truncated runs and unavailable comparisons
remain in the configured run/branch denominators and block a supported conclusion.

Matching uses three prespecified levels:

- **Encoded context:** the option pair plus the public resource/act context used by the residual
  encoder, before feature hashing.
- **Full menu:** the same context plus the complete set of visible option IDs. Menu permutations
  are kept separately as metadata; execution indices are not option identities.
- **Exact public state:** the complete public observation and ordered legal actions, excluding
  opaque state-hash metadata. This is finer than the encoder context.

The historical fitting inventory reports replication and direct floor-direction disagreements
at each level. The combined discovery inventory uses historical fitting and the 144 fresh
discovery seeds. It shows stronger versus weaker labels, menu/state variation, paired outcome
differences and disagreements. A reduction in disagreement under finer matching is descriptive;
smaller groups alone can create that reduction. It does not prove that omitted context caused it.

A **strong** direction preserves terminal victory, Act 1 clear, boss reach, then maximum floor.
The separate **all-eligible** direction also includes frontier tie-breakers; activity-only
comparisons contribute no strict lesson. Raw floor-direction disagreements are shown separately,
because floor alone must not override victory or other stronger outcomes.

## Frozen confirmation rule and stopping point

For each matching group and target, a discovery direction exists only with at least **three
independent strict discovery runs** and a majority of at least **two thirds**. Ties remain recorded.
Confirmation outcomes never choose the groups, directions, matching levels or thresholds.

Each matched confirmation comparison scores 1 for agreement, 0 for opposition and 0.5 for a tie.
All matched comparisons within a seed are averaged first. Each independent seed then contributes
one mean score. Conservative Hoeffding bounds use alpha 0.05, conditional on discovery and
matched public strata, with independence assumed across complete seeds. They do not treat the
three comparisons or overlapping groups as independent draws. Unmatched confirmation seeds stay
in the cohort denominator, but do not enter this conditional matched-stratum interval.

Only the **encoded-context strong** comparison drives the decision. Other matching levels and
all-eligible scores are descriptive, with no alternative success claim selected after inspection.
The frozen minimum coverage is five matched qualified groups, 12 independent covered confirmation
runs and 12 confirmation runs with a non-tied strong comparison; all fresh runs must be complete.

- **Supported:** coverage passes and the agreement interval lies wholly above 0.5. This supports
  pooling these auxiliary lessons on the matched strata, not better game play or universal option value.
- **Unsupported:** coverage passes and the interval lies wholly below 0.5.
- **Inconclusive:** inadequate coverage, any failed/truncated run, or an interval overlapping 0.5.

There is no automatic extension, replacement cohort, tuning or training. Unsupported/inconclusive
results stop this starting-choice experiment and recommend returning foundation work to combat
and run-level competence. A supported result can justify proposing a separately frozen training
experiment with fresh confirmation. This study's inspected confirmation cannot become its later
untouched test. The original #127 advancement and safety limits stay unchanged.

## Saved outputs and claims

The report is `artifacts/repeatability/sts2-v0.107.1-base-v2-train-v1/starting-repeatability.json`.
The fresh collection is in the same directory's `evidence/starting-option-evidence.json` and
`evidence/cases/`. Resource reports are
`artifacts/resources/starting-repeatability-base-v2-train-v1-attempt-N.json`. All raw outputs stay
outside Git. Per-attempt trajectory/transition counters exclude already saved cases; CPU/wall
accounting covers verification too. Work lost inside exceptions is not inferred from nonexistent
records; failures and the configured denominator remain explicit.

The analysis is deterministic and content addressed. It uses verified saved cases and checks
source IDs, ObjectiveSpec, fixed policy/ruleset, action bindings, split ownership, paired ranks,
continuation trace contracts and summaries. This is not independent engine replay or proof of
real-game equivalence. Naturally occurring fresh seeds vary both public context and futures;
they are not repeated stochastic draws from one identical state.

No model is updated or promoted. Full-run victory under the whole-run computation budget stays
primary; floor and HP remain auxiliary. Foundation readiness and adaptive-controller training
remain separate blocked work. The coding agent runs only short toy tests and bounded metadata
checks; the owner runs and monitors every sustained collection or verification job. No code push
or GitHub Actions job is part of this package.
