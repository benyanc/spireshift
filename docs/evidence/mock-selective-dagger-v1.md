# Mock selective-DAgger evidence v1

The checked iteration runs the issue 24 model on three new frozen training seeds: 13, 15, and 16.
Its source checkpoint is
`sha256:7f620aeb48248ded3842fff44a4a12397360ceb5236e87b70317e32a3bb15191`, and its reference
dataset is the same 12-run teacher dataset used to train that model.

The cheap probe uses four search simulations and four independent evaluation samples per candidate
with sampling seed 3. The expensive relabel uses 16 search simulations and 16 evaluation samples per
candidate with sampling seed 23. The selection thresholds are 0.40 maximum reference frequency,
0.95 normalized entropy, 0.65 confidence, and 0.25 independently evaluated regret.

The student completes all three runs, producing six decisions and nine candidates. The selective
loop sends four decisions to the expensive teacher and avoids two expensive labels.

| Result | Count |
|---|---:|
| Complete student runs | 3 |
| Student victories | 3 |
| Collected decisions | 6 |
| Expensive relabels | 4 |
| Expensive relabels avoided | 2 |
| Probe teacher disagreements | 1 |
| Rare-state triggers | 3 |
| Probe confident-error triggers | 1 |
| High-entropy triggers | 0 |

The probes consume 24 search simulations and 36 evaluation simulations. Selected relabels consume
64 search simulations and 80 evaluation simulations. Probe and relabel outcome seeds are disjoint in
every selected record.

The larger teacher does not confirm the probe disagreement or confident-error candidate in this tiny
sample. The artifact preserves that result explicitly. It demonstrates why selection triggers and
confirmed diagnoses must be reported separately when a cheap, noisy probe controls labeling cost.

The iteration identity is
`sha256:c8fcc9a4cb905b895a6b0b83249c8d9032cf81aa658e82dd129c225c53e49fbd`.
Its audited complete-run index identity is
`sha256:dbee201fabef5782e2c33dbfd9b2a2552f05b4b5deb16448b8caee0b693d0c60`.
Tests regenerate the entire artifact, replay complete student trajectories, validate split ownership,
verify source-model predictions, regenerate both teacher budgets, reject tampering and seed reuse,
and train a successor checkpoint from its four selected labels.

The checked successor fit combines 21 original records with the four selected labels. Its checkpoint
identity is `sha256:b9af7338733bc55ea3b9e2021f9d5d0f92429156f08568ea10ba1b6576d66406`, and its report identity
is `sha256:061b52c733428592087360f27df0cda8a1ce3130ebb569083b291f6180bf8bdb`.
The checkpoint binds the source iteration ID and the report preserves its model, run, decision, and
selected-record provenance.

This is pipeline evidence on the two-decision mock environment. It makes no claim about STS2 policy
improvement or the cost savings achievable on representative game states.
