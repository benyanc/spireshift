# Exact combat potion discards on the frozen game

The owner completed the previous [combat-effects panel](actual-engine-combat-effects.md): all
8/8 cases and independent saved reconstruction pass. Its scope explicitly excluded potion
discard, which the native wrapper offered but the shipped Host omitted. This separate #145
package implements and tests that gap on fixed Ironclad/A8 and the frozen v0.111.0 game.

## Implemented and checked

Host v9 exposes each discardable potion in the current combat menu, including automatic potions
that cannot be used manually. The choice binds the actual potion entity and its advertised belt
slot. Before delivery, the Host rechecks the same combat room, local play phase, ownership, native
`CanUseOrRemovePotions` permission, queued state and exact slot. The original native
`DiscardPotionGameAction` performs the effect; no game rule or official assembly is patched.

The native public combat projection also publishes the already-validated visible slot. The
combat referent and persistent inventory use different facet IDs, so a definition-only fallback
could not distinguish two identical potions. The new contract binds by exact entity or current
slot plus definition and rejects missing/ambiguous slots. A potion present in both shipped
use/discard lists can share a public referent; discard still requires membership in the actual
current discard surface. Every combat play/use/discard/end-turn offer is compared in the new
prefix, with unknown activations rejected rather than filtered.

Two short native-versus-shipped checks and independent saved-only audits pass:

- Discard Fairy in a Bottle from the first slot while retaining Strength Potion in the second;
  Fairy has a discard choice and no manual use choice.
- Start with two identical Strength Potions; discard only the first slot, then use the remaining
  second-slot potion exactly once. Strength remains zero after discard and becomes two after use.

Both prefixes play an attack and Defend, reach turn two through the fresh reshuffle confirmation,
retain the expected Pen Nib counter and compare current costs/descriptions, owned effects, full
menus and deck/potion state. They cover **18 observations, 16 effect decisions and 26 game/UI
actions**. Their wall times were **43.994 and 46.750 seconds**. Both reuse the same app/inode with
fresh profiles, zero new copies and verified reset receipts. These five-card/two-potion fixtures
are privileged setup, not training trajectories or evidence of playing strength.

Two fresh Host builds reproduce in **8.552 seconds**. Seven synthetic C# permission/slot/descriptor
checks and five Node identity/menu tests pass. Each saved case reconstructs and rejects seventeen
deliberately corrupted records, including a missing discard choice and a wrong potion slot.
Repository checks pass **1,213 tests**, lint/format/types and the C# protocol contract. The original
completed eight-case combat audit still reconstructs identically. Historical helper/Host recipes
and exclusions are unchanged. [Implementation evidence](evidence/actual-engine-v0.111.0-combat-discard-v1.json)
records the source/binary/projection identities and limits.

## One next owner command

Close STS2, then run from the repository:

```bash
bash scripts/compare-combat-potion-discard-v1.sh
```

Expected duration is **6–9 minutes**, capped at 15 minutes elapsed, 1,800 CPU seconds, 8 GB memory
and 6 GB tracked files including the one shared app pool. Read-only preflight already passes and
the batch workspace has not been created. Eight serial cases cover two independent A8 seeds,
both automatic/identical-potion fixtures, each twice, with fresh private benchmark profiles.

The helper shows progress by case and stops at the first mismatch. All planned cases stay counted;
repeated public facts and action semantics must agree. Only saved verification follows success.
A completed batch is displayed/audited on reinvocation without game replay; incomplete evidence
is preserved for inspection. No full run, training, adaptive controller or next experiment follows.

## Remaining work

This qualifies a bounded potion-discard scope, not every potion, queued state or interaction.
Original headless diagnostics remain saved. Broader public selectors/modes, startup through the
shipped new-run lobby, later-act transitions and actual endings remain #145 work. Historical
panels do not automatically qualify a changed Host. Complete-run throughput and a separate A8
neural lineage remain #146 work after required qualification; adaptive thinking still requires
a useful policy/value foundation. No new long task has been launched by Codex.
