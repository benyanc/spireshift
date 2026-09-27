# Terminal-rescue combat search

The exact-state intervention diagnostic rejected scalar search margin as a general override gate.
It found one narrow deterministic signal: when every paired simulation defeated the base action and
none defeated the search action, the intervention was beneficial three times, tied four times, and
harmful zero times across five train seeds. This rule directly represents imminent simulated death
avoidance and does not require fitting a classifier to the insufficient intervention labels.

Combat-advancement configuration v3 adds the `terminal_rescue` override rule. It executes a search
action only when all of these conditions hold:

- search selects a different legal action from the base checkpoint;
- both paired base-action rollouts terminate in defeat;
- the selected search action has zero paired defeats;
- search value exceeds base value by at least 0.20.

Every search trace records the base and search terminal victories, defeats, bootstrapped leaves,
rule eligibility, and execution decision. Legacy v1/v2 configuration and policy identities are
unchanged.

The frozen preflight compared base, shadow, and applied terminal rescue on 16 train seeds beginning
at offset 96. This window was disjoint from the 16 seeds used to derive the rule. An applied rule
could advance only when shadow exactly preserved base, all runs completed, no base victory was lost,
mean maximum floor improved, more seeds improved than regressed, progress per CPU-hour was positive,
and no executed override violated the terminal-rescue condition. The specification is
`sha256:f5fde31b9555527a49978aeded257b416c13b55e289b450536ee9abde73f3edb`.

## Completed preflight result

The operator-started preflight completed all 48 trajectories and both artifacts verify. The
diagnostic report is
`sha256:2201fff0b39b6bcdfe163a8662046ffdba53764a76b521c535eb83a87122c8a1`; the resource report is
`sha256:196dc6408abdc46abbbcd3a117eb7d0c324685daa7f7e01c6033dd236c6db09b`.
It used 708.98 wall seconds, 705.21 CPU seconds, 19,352 simulations, 128,635 transitions, 148 MB
peak memory, and 1.72 MB of artifact storage.

Shadow search reproduced all 16 base action traces and outcomes. Applied terminal rescue executed
eight eligible overrides across seven changed trajectories with zero rule violations. All 16 base
and applied runs terminated in defeat, and every paired maximum floor tied: both systems averaged
7.9375. The applied policy consumed 350.99 decision CPU seconds, compared with 7.63 seconds for the
base policy, without improving a run.

The failure exposes a semantic weakness in the original rule. In each executed override, both base
rollouts terminated in defeat, while both search rollouts merely reached the eight-step horizon and
were bootstrapped. None of the selected search rollouts observed a combat clear or run victory.
Zero sampled defeats therefore meant short-horizon survival rather than demonstrated recovery.

`validation_allowed=false`. Do not run this configuration on validation, increase its sample count,
or interpret it as evidence that terminal rescue improves play. Any later tactical rescue rule must
distinguish combat clearance from a censored horizon and require resolution-level evidence before
it can alter the base policy.
