# Mock teacher-data evidence v1

The checked artifact exercises independently evaluated teacher generation on frozen training seed
0. It uses 32 UCB search simulations per decision and 32 independent evaluation samples per legal
candidate.

The complete run contains two decision records and three candidate evaluations. Search used 64
rollouts and independent grading used 96 distinct rollouts. At the first decision, UCB assigned 6
visits to `safe_path` and 26 to `elite_path`, then selected `elite_path`. Independent evaluation used
32 new samples for each action and estimated terminal values of 0.21875 and 0.65625 respectively.
The resulting trajectory reached a terminal victory.

The artifact identity is
`sha256:fa36b2516fc195e1c9ecd1b39f184ee563c7d5874286ed7f490563c381c4649f`. Its audited
complete-run index identity is
`sha256:201f1beaf23a19aed55dd6ba49a9e8c1cb932b9e2641fc5ad9df64391c9eb15b`.

Contract tests validate the dataset, index, and verification report against versioned JSON Schemas.
Unit tests regenerate the artifact exactly, confirm equal evaluation budgets and disjoint seed
domains, replay every recorded sample and transition, and reject outcome tampering, search/evaluation
seed reuse, insufficient search coverage, duplicate seeds, split leakage, and artifact replacement.

The artifact demonstrates the collection and audit protocol. Its small mock sample counts are test
evidence rather than a claim about STS2 policy strength.
