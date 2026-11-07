# One committed card choice across both hosts

The owner chose one model decision for a complete card answer. The official-game
adapter performs its required select, preview and confirmation controls. This is
an explicit new decision contract, `atomic_public_card_choice_v1`, rather than a
change to either saved player or the game's rules.

The new source tuple is CLI export v40, native worker v14, shared helper v9/layout
v6, official connector v16 and shared environment v14. All earlier tuples,
results, failed attempts, original numerical weights and complete Adam states
remain unchanged. New metadata imports name the changed observations explicitly;
unchanged numeric weights do not promise unchanged action probabilities.

## Strategic choices and execution

Every admissible ordered card answer is advertised, including an empty answer
when the game permits one. Cancellation remains a separate action. The adapter
never chooses a different card or supplies a default answer. It binds each actual
card copy to the current deck or visible combat pile, retaining costs, previews,
selected flags, public owner, selection preferences and all advertised detail
reads. Current-card detail reads are ordered by public content and owned surface
position, never by opaque runtime identifiers.

The official host accepts one exact advertised macro, then checks the current UI
owner and native controls at each primitive step. Ordinary observation does not
start a transaction. While an authorized transaction is pending, the intermediate
UI is settling rather than another policy decision. A pending click is never
resent. Changed owners/cards, ambiguous controls, timeouts or uncertain delivery
stop the attempt and preserve evidence.

The client acknowledges the model choice only after authenticated host evidence
proves the exact ordered selected copies and native commit or cancellation. The
saved-record verifier separately reconstructs each original choice and requires
this completion evidence. A delivered acceptance alone is insufficient.

This first implementation handles the seven registered deck/upgrade/transform/
enchant/simple/hand/pile selector families. Generated-card and card-pack protocols
retain their separately versioned behavior. Menus exceeding 512 ordered answers
are rejected as unsupported in their entirety; they are never silently truncated.
A compact protocol for such large domains remains a prerequisite if encountered
before broader learning. Source coverage is not proof that every family's game
effects have been exercised.

## Evidence and limits

The saved-only audit passes 845 recorded complete public frames plus 20 generated
envelopes: 865 reversible reconstructions and exact raw action-binding checks,
with 1,720 frozen-player input probes. Its protection receipt checks 3,119 prior
files. It starts no games and makes no optimizer updates.

Targeted tests cover ordered and empty answers, distinct cancellation, missing
preferences, physical card-copy identity, bounded menus, read enumeration,
pending UI responses, exact commit evidence and stale/foreign/rejected receipts.
The C# transaction kernel and noncombat belt permission checks are separate from
actual shipped effects. Full repository validation and live results are recorded
in the portable evidence.

The first explicitly labelled replay of a previously completed removal case
stopped in the native export: Neow has no description at that selector boundary.
The game checks `Description.Exists()` before formatting it; v40 uses that same
condition and native formatting bindings. V39's blocked attempt, source-at-launch
and stopped process remain preserved. Its uncertain choice is not replayed.
A new world is used for the repaired live check.

The next broader validation uses both frozen players on two fresh canonical worlds,
with matched public inputs and actions checked from the beginning of each prefix.
It remains a finite compatibility diagnostic, not PPO, a complete-game strength
measurement, promotion or permission for adaptive thinking. No automatic learning
follows. Mismatched states are never realigned to make a later comparison pass.

## Completed targeted check and next command

The controlled card-removal prefix passes all four complete inputs, action menus
and actual deliveries per host in 36.67 seconds. Its official adapter executes
select and confirm as two primitive UI steps for one model decision; a separate
preview click is used only when that current screen requires it. Saved-only
verification reconstructs all eight choices/receipts in 5.26 seconds. Both decks
lose exactly the chosen Strike copy (11 → 10 cards), with all other public card
facts unchanged. This is a natural offered bonus, not an injected privileged card.

The scenario was selected by observing four starting menus and frozen model choices,
without submitting any game action or inspecting later outcomes. Its targeted
replay is explicitly marked as observation-only scenario reuse, never fresh
playing-strength evidence. The earlier completed reward path retains its mismatch;
layout v6 now maps only its actually advertised skip control and known display
colors. Missing exits, unknown markup and nonempty belts stay explicit.

The longer plan is preflighted, with no main games started. Close any running STS2
and run this one command. Repeat it only after a reported clean pause; completed
pairs are reused and uncertain attempts stay preserved.

```bash
bash scripts/compare-semantic-selection-v3.sh
```

The launch is capped at 15 minutes and 4 GB memory/files. It covers both frozen
players and two new worlds, up to 128 choices per host. It reuses one app, starts
no training and grants no promotion or adaptive controller. The v1/v2 selection
launch prototypes remain only to preserve earlier source receipts.

[Portable evidence](evidence/native-semantic-selection-v1.json) records the exact
sources, tests, controls, preservation receipt, resource reports and remaining
qualification limits.

Final repository validation passes 2,573 tests, strict types on 613 source files,
format/lint and the C# protocol in 146.25 seconds. The latest focused suite also
passes 12 Python tests (including the actual owner-launcher chain), 20 Node cases
and 20 C# transaction/belt permission checks. No app copies or optimizer updates
are created by these checks. Nonzero/X star costs in cross-character selection
views and additional shipped selector effects remain explicit targeted coverage
work; ordinary energy-only cards do not establish those cases.
