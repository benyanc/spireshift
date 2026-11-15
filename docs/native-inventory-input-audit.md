# Player deck/relic distinctions and the combat-counter repair

The saved-state audit is complete. The tested inventory distinctions reach the
actual policy encoders, while a separate **upstream projection defect** dropped
owned relic counters from combat observations. Worker v11 repairs that defect;
four short native diagnostic replays pass. Both original players, their complete
Adam states and all six structured-input finals remain unchanged.

## What passed

The audit reads 128 saved TRAIN attempts from the two unchanged-input players and
two rounds: 64 distinct worlds, 18,481 non-navigation rows and 14 decision families.
It does not fit anything, consume fresh evaluation worlds or launch a game.

Eighty controlled probes cover ten distinctions, eight examples each: owned card
definition, upgrade, displayed cost, which card owns a cost/upgrade, relic
definition, counter value, zero versus unavailable counter, which relic owns a
counter, and current hand-copy cost with its advertised subject. The probes hold
the coarse predictor's 20 features exactly fixed; prose and public slots do not
change to supply an accidental shortcut. Actual original, hashed-supplement and
named-supplement policy inputs differ, and candidate permutation preserves rows.
The check does not require the old player to choose differently or correctly.

Sixteen natural cross-world pairs also have identical coarse features and different
inventory signatures and actor inputs. They are sampled observations, with repeated
world pairs and other public differences, **not isolated causal inventory tests**.
The controlled probes are syntactic feature checks, not proven reachable native
states, strategic preferences or ordinary PPO examples. This is a scoped wiring
audit, not a proof that compression preserves every possible game state.

## The actual missing information

All 12,518 inspected combat decisions lack the public combat relic-counter view.
In 53 of the 128 source attempts, the saved native DEBUG response already contains
a numeric owned relic counter, including Sword of Stone at zero. The public
projection discards it. Owned card/relic identities still reach the actor; a
same-count alias in the separate coarse credit predictor does not imply a whole
actor-input alias.

`engine-relic-surface-v1.mjs` delegates to the frozen selection/combat projection
and adds only `{id, counter}` for each owned combat relic. It preserves identity
and multiplicity/order, numeric zero and native null. Missing/malformed facts fail
before advertising actions. It never spreads raw native objects, vars, handles,
RNG or unqualified state. The native engine remains responsible for effects.

Worker v11 and its separately versioned Python constructor use this projector.
The historical v10 worker, SDK/support-code cache, game, runtime and source
contracts stay unchanged. The new native environment manifest v9 explicitly binds
the observation change. Future forks copy every numerical weight and Adam moment
and counter; only their environment metadata/IDs change. There is no silent
rewrite of an old checkpoint or reinterpretation of old results.

## Native verification

Two saved TRAIN traces are replayed twice, as diagnostics only: **four games,
498 actions, 502 observations and 336 combat observations**, zero failures.
After removing only the newly added combat-counter view, every public input and
advertised menu is exactly the old saved input. The same actions produce the same
endings. Delivery and shutdown verify; an independent ordered streaming check
matches every combat relic ID/counter to its corresponding native response.

There are 142 numeric counter observations, all zero, and 824 null observations.
The native panel therefore establishes zero/null delivery and repeated legacy
trace preservation; nonzero/ownership changes are covered by code-level probes,
not claimed as naturally exercised by these four replays. Later production games
also receive the ordered native/public counter verifier. These are known TRAIN
world replays, not new independent evaluation games or PPO training data.

The native panel takes 31.79 seconds (32.01 with resource wrapper), peaks at
376.85 MB and retains 12.23 MB. Frozen game/runtime/SDK, account profile and all
saved model states verify unchanged. No app copies or optimizer updates occur.

The active saved-state audit is recipe v2: 35.57 seconds (35.81 wrapped), 276.68 MB
peak and 14.75 MB retained. V1 passed the same runtime checks but needed a local
typing annotation before commit; its result and exact launch sources are preserved
separately. Do not rerun either completed audit. See
[portable evidence](evidence/native-inventory-input-repair-v1.json).

## Next

Keep the coarse credit predictor fixed: the tested richer linear correction still
worsens held-game error. The next comparison uses the repaired observations in
both arms and tests **32 versus 128 fresh games per training round**, with exactly
preserved initial numerical weights/Adam and fresh frozen full-game evaluation.
See [the experience-budget experiment](native-experience-budget-comparison.md).
The input repair does not by itself establish stronger play or explain every loss.
