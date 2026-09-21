# Independently evaluated teacher data

SpireShift's teacher-data contract separates the samples used to construct a search policy from the
samples used to estimate its quality. A search result never grades itself.

For each public state, `monte-carlo-ucb-terminal-victory-v1` first visits every legal candidate and
then assigns the remaining search budget with UCB. These rollouts produce each candidate's visit
count, visit probability, estimated terminal-victory value, and stochastic outcome variance. The
teacher action is selected only from search visits, with search value and candidate order as
deterministic tie breakers.

After search is complete, every candidate receives the same number of independent evaluation
rollouts. Search seeds occupy an even-numbered domain; evaluation seeds occupy a disjoint
odd-numbered domain derived from the dataset sampling seed, run seed, decision index, and public
state hash. No search trajectory is reused as evaluation evidence. The dataset stores every sample
seed, binary terminal outcome, reward, and rollout length so estimates can be reproduced exactly.

Each decision record also stores:

- the content-addressed compositional model input;
- the aligned source action handle and candidate index;
- the search and independent-evaluation estimates;
- the selected action and observed successor-state hash; and
- the terminal outcome of the complete trajectory containing the decision.

Records and complete datasets have independent content identities. A companion dataset index binds
every decision and encounter to its complete run and frozen train, validation, or test partition.
Generation rejects a seed assigned to another partition.

## Verification

`verify_teacher_dataset` checks identities, candidate alignment, sample counts, visit probabilities,
means, population variances, seed uniqueness, parity isolation, complete-run ownership, summaries,
and the frozen dataset index. It then regenerates every search and evaluation sample from its seed
and replays the chosen trajectory through the environment. A changed outcome, missing sample,
reused seed, stale state, or altered transition makes verification fail.

The implementation accepts the common cloneable `EnvironmentAdapter` and `Policy` protocols. The
checked generator uses the mock environment to make the data contract executable before the
admitted STS2 search backend is connected. The same target builder can be used by that backend; STS2
teacher quality remains a measured property of the later exact-engine search experiments.

## Commands

Generate one high-budget training trajectory and its audited index:

```bash
uv run spireshift teacher generate-mock artifacts/teacher/mock-v1.json \
  --runs 1 \
  --search-simulations 256 \
  --evaluation-samples 256
```

Select explicit seeds only when they belong to the declared frozen partition:

```bash
uv run spireshift teacher generate-mock artifacts/teacher/mock-seeds.json \
  --partition train \
  --seeds 0 2 3
```

Verify an artifact without generating new data:

```bash
uv run spireshift teacher verify artifacts/teacher/mock-v1.json
```

The serialized contract is [teacher-dataset-v1.json](../schemas/teacher-dataset-v1.json). Checked
results are recorded in [mock-teacher-data-v1.md](evidence/mock-teacher-data-v1.md).
