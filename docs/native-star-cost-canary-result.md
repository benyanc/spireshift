# Completed star-cost comparison: execution passes, inputs still differ

The owner completed selection-flows v10 on worlds 411/412 and both unchanged
players. All eight host prefixes execute 128 choices, shut down cleanly and pass
app/profile/archive restoration. The batch takes 1,039.61 seconds (17.33 minutes)
within its 30-minute allowance; no resource cap occurs. The resource wrapper's
failure status is the declared input-compatibility rejection, not a crashed game.
The previous numeric/text star-cost failure does not recur.

Independent saved-only verification reconstructs all 1,024 inputs, checkpoint
choices and delivery receipts in 24.37 seconds without starting a game. Both
original full player/Adam files retain their exact SHA-256. No training or
promotion occurs, and no next experiment is started.

There are no complete matching pairs. Their identical initial prefixes contain
56, 76, 117 and 109 choices. Inspect only the first mismatch after each common
prefix; later different inputs can cause different actions and different worlds.
These counts are not an overall percentage of compatible decisions.

| First mismatch | Native interface | Official interface | Required follow-up |
| --- | --- | --- | --- |
| Energy Potion reward description | Two rich image tags | Two normalized energy-glyph tokens | Normalize declared visible reward text while preserving glyph identity, order and count. |
| Setup Strike status title | Localization key `SETUP_STRIKE_POWER.title` | `Setup Strike` | Resolve the native model's current localized title; preserve its ID, amount 3 and matching effect description. |
| Nimble Defend in the deck read | Gain 5 Block | Gain 7 Block | Render per-copy enchantment modifiers in the actual card display context; verify effects as well as descriptions. Both hosts already expose Nimble amount 2. |
| Potion during Headbutt's card selection | Adds Discard Explosive Ampoule | Does not advertise that action | Verify current modal permissions and owned potion identity. Align actual advertised actions and context, retaining inventory facts and raw bindings. |

The first three action menus match at the observed difference. The last mismatch
also changes the action menu, so it cannot be treated as text cleanup. Its public
potion summaries also disagree: the native selector reports use disabled/discard
enabled and repeats the owned potion under a different ID; the official selector
has a sparse `can_use: true` context but no potion action. The source of truth must
be tested against the current official selection owner. Do not assume either
summary alone proves which UI action can be delivered, remove potion information
to hide the difference, or infer universal permissions for every modal screen.

The next work is a consolidated correction of these four observed gaps with saved
first-difference regressions and short native/official controls. Include varied
reward glyphs, localized status titles, permanent card modifiers and nested
selection owners so fixes cover their declared interfaces rather than these four
specific names. Preserve all prior source versions and results; qualify a new
tuple before another longer comparison. The current result does not establish
complete compatibility, stronger playing strength or readiness for training.

Rerunning the completed v10 plan reuses its saved result. It cannot repair these
differences. See [the evidence](evidence/native-star-cost-canary-assessment-v1.json)
and the current backlog.
