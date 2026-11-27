# Effect-free decision cycles and the re-entry guard

The owner approved this framework repair on November 27, 2026, after the
[normalization result](native-hidden-normalization-result-v1.md). There, final
normalized player 2 spent 37.8% of its decisions opening and closing the shop
inventory. Nothing here trains a model, promotes a checkpoint or changes an
existing recipe.

## Saved-only scan

`scripts/scan-effect-free-cycles-v1.py` streams sealed journals only and skips
unsealed or failed cells. A cycle is a run of delivered choices that starts and
ends at the same public input (identical `public_input_id`). Same id means the
entire visible run, deck, HUD and menu are unchanged, so the steps in between had
no public effect.

| Saved games scanned | Games | Decisions | Games with cycles | Decisions inside cycles |
| --- | ---: | ---: | ---: | ---: |
| Normalization continuation (all arms, train + development) | 879 | 149,959 | 311 | 27,632 (18.4%) |
| Capacity study v1 prefix | 633 | 103,445 | 213 | 4,452 (4.3%) |

Every cycle found has one of four shapes. Each opens a sub-menu and then backs
out of it:

| Cycle | Normalization decisions | Capacity decisions |
| --- | ---: | ---: |
| Shop: Open inventory → Close shop inventory | 27,172 | 4,404 |
| Rewards: Claim "Add a card" → Skip | 406 | 18 |
| Rest site: Smith → Cancel selection | 44 | 0 |
| Shop: Choose a card to remove → Cancel selection | 10 | 30 |

No combat, map or event cycles occur. The current full-menu contract
(`native_a8_all_advertised_actions_own_policy_v1`) offers every step as a model
decision on purpose. An earlier routed contract, `native_shop_policy.ShopNavigation`,
forced the first open and withheld later reopens. That routing was dropped when the
model took ownership of every choice, and the loop returned.

## Repair: `native_cycle_guard_v2`

The policy sees every advertised candidate except a non-exit action already
**proved effect-free**. That means the model took the action from this exact
public input and the run later came back to the identical input. Example: from a
shop room it opened the inventory, closed it and is back in the same room. From
then on, that action is withheld from that same input.

- Exit and decline controls are never withheld. These are native verbs
  `cancel`/`close`/`skip`/`proceed`, the visible control words
  Skip/Proceed/Continue/Leave/Cancel/Close, or `is_proceed`. The guard only
  withholds while an exit stays on offer, so the most it can do is leave a
  decline or exit as the remaining choice. It never forces a purchase, card or
  other effect.
- Any public change produces a new input id, which restores the full menu. For
  example, a potion used in the shop changes the visible state, so reopening is
  available again.
- No game outcome becomes unreachable. Every outcome available through the
  withheld action was offered on the identical sub-menu the model already
  visited and left.
- The guard uses only the public inputs the policy saw and its own delivered
  choices. It reads no hidden or native-only state. The native menu, the
  bindings, the delivery and the saved journal are unchanged. Every advertised
  binding still reaches the raw verifier.
- `groups` re-derives each withheld set from the saved public inputs. PPO then
  rebuilds the effective menu and the effective action index the model sampled
  from, so behavior log-probabilities stay exact. Each choice records
  `withheld_effect_free_actions`.
- New recipes opt in with `using_cycle_guard()` and the new contract
  `native_a8_all_actions_effect_free_cycle_guard_v2`. Historical recipes, workers,
  verifiers and results are unchanged.

### Preserved first design (v1)

`native_cycle_guard_v1` withheld whichever action closed the cycle, exits
included. Its native control (`artifacts/effect-free-cycles/control-v1`) finished
four games, but one revealed a flaw. The first shop room differs from later ones,
because the visible "inspected" flag flips. So the inventory became the first
repeated state, v1 withheld its Close, and a purchase was left as the only option.
That would let the guard, not the model, create a native effect. The control and
the v1 code are kept as negative evidence. The v2 unit test reproduces the exact
sequence.

## Short native controls (v2)

`spireshift.native_cycle_guard_control_v2` plays four fresh declared control worlds
(SP1RESH1FTA8CYG101–104) on frozen round-64 finals: normalized player 2 three
times and raw player 3 once. Each runs with the frozen game, host, deferred-potion
adapter and full-menu worker. Every game:

- reaches a genuine native loss, and the raw verifier replays the guarded policy
  from native observations;
- rebuilds exactly one PPO decision per native delivery (120/77/197/146) through
  the guarded `groups`/`samples`;
- withholds only re-entries. Three times it withheld "Open inventory" (leaving
  Leave shop) or "Claim Add a card" (leaving Skip remaining rewards) after a
  proved round trip. No exit was withheld, and no game had more than two
  inventory opens.

The frozen game, runtime, SDK, archive and all four original/source full states
with Adam remain exact. There were zero optimizer updates and zero labels. The
four games are execution controls, not strength evidence. The v2 run took about
1 minute.

## Scope

This guard removes repeated effect-free re-entry only. It does not address
single-option menus (each still counts as a decision), and it is not a
complete-mechanics or official-parity claim. Official Connector behavior is
unchanged and still tracked under #149. The next learning stage must bind it
explicitly in its own versioned recipe.

Evidence: [native-effect-free-cycles-v1.json](evidence/native-effect-free-cycles-v1.json).
