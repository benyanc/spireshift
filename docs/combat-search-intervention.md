# Single-intervention combat-search diagnostic

The paired threshold sweep verified the search implementation but rejected every action-changing
configuration. Greedy search reduced mean maximum floor from 7.75 to 6.75. A 0.05 advantage gate
reduced it to 7.125. The 0.10 and 0.20 gates produced identical action traces, spent about 45 times
the base policy's decision CPU, and produced no floor or victory improvement. Fixed threshold tuning
is therefore blocked.

This diagnostic measures the causal value of individual recommendations. It follows the base-v3
checkpoint trajectory while the existing search policy runs in shadow mode. For recommendations
chosen by a deterministic content-hash reservoir, it clones the exact source state, executes exactly
one search-recommended action, and returns control to the base checkpoint for the rest of the run.
The unchanged base trajectory supplies the paired outcome.

The frozen train-owned specification uses 16 runs beginning at train offset 80. It samples at most
two recommendations per seed from each prespecified search-margin stratum: `[0, 0.01)`,
`[0.01, 0.05)`, `[0.05, 0.20)`, and `[0.20, infinity)`. This bounds the run at 128 exact-state
counterfactuals while covering weak and strong recommendations across each trajectory. Every case
records the policy probabilities, paired-world candidate values, terminal/bootstrap counts, search
cost, continuation outcome, and terminal-victory-first paired label.

The report can establish whether the existing margin contains useful override signal and whether
there are enough beneficial and harmful examples to fit an override gate. It always emits
`validation_allowed=false`; it cannot promote search, authorize validation, or support an adaptive
search claim by itself. The frozen specification is
`sha256:0af0712dbda7e31da61612f2c6fa5807d899671c42b1e354925f5a1a178dae55`.

## Completed result

The operator run completed 16/16 base runs and 79/79 exact-state interventions. Overall, five
interventions improved maximum floor, 68 tied, and six were harmful; no run won. Scalar margin was
not monotonic: the medium band was the most harmful, while the large band had three improvements
and no regressions. The learned-gate diversity criterion failed.

One categorical signal survived: in seven interventions, both paired simulations defeated the base
action while neither defeated the search action. Those interventions were three beneficial, four
tied, and zero harmful across five seeds. The next experiment is the
[terminal-rescue preflight](terminal-rescue-search.md). Do not rerun this intervention job or fit a
learned gate from its labels.
