import test from "node:test";
import assert from "node:assert/strict";
import { verifySavedRest } from "./verify-engine-rest-saved.mjs";
import { chooseRestAction, restActionKey, restFacts, restPlans } from "./engine-rest-bridge-contract.mjs";

// Invented controls and IDs exercise the contracts without shipping game observations.
function observation(index, kind, remaining, hp, upgraded) {
  const options = remaining.map((option_id, i) => ({ index: i, option_id, is_enabled: true }));
  const actions = options.map((row) => ({ verb: "activate", subject_referent_id: row.option_id,
    arguments: [], bound_action_id: `action-${index}-${row.option_id}`, interaction_id: `i-${index}` }));
  const card = { definition_id: "STRIKE_IRONCLAD", cost: "1", is_upgraded: upgraded, entity_id: "chosen" };
  const surface = { options, can_leave: index > 0 };
  const referents = options.map((row) => ({ referent_id: row.option_id, properties: row }));
  if (kind === "rest_site" && index > 0) actions.push({ verb: "close", arguments: [], bound_action_id: `leave-${index}`, interaction_id: `i-${index}` });
  if (kind === "card_selection") {
    Object.assign(surface, { cards: [card], min_select: 1, max_select: 1, cancelable: true });
    referents.push({ referent_id: "chosen", properties: card });
    actions.push({ verb: "confirm", arguments: [{ role: "selected_card", referent_id: "chosen" }], bound_action_id: `choice-${index}`, interaction_id: `i-${index}` },
      { verb: "cancel", arguments: [], bound_action_id: `cancel-${index}`, interaction_id: `i-${index}` });
  }
  if (kind === "map_navigation") {
    const point = { col: 1, row: 1, point_type: "monster" };
    surface.next_options = [point]; referents.push({ referent_id: "node", properties: point });
    actions.push({ verb: "activate", subject_referent_id: "node", arguments: [], bound_action_id: "travel", interaction_id: `i-${index}` });
  }
  const snapshot = { snapshot_id: `s-${index}`, status: "interactive", session: { runtime_instance_id: "runtime" },
    information_policy: { includes_hidden_information: false }, completeness: { status: "complete" },
    bound_actions: { actions, status: "complete", total_count: actions.length, materialized_count: actions.length },
    interaction: { interaction_id: `i-${index}`, kind, content: { surface } }, referents,
    persistent: { content: { run: { act: 1, act_definition_id: "SYNTHETIC_ACT", floor: 1, ascension: 8 },
      player: { character_definition_id: "IRONCLAD", hp, max_hp: 80, gold: 99, max_potion_slots: 2,
        relics: [{ definition_id: "MINIATURE_TENT" }], potions: [] } } } };
  const deckRead = { kind: "run_deck", completeness: { status: "complete" }, expected_snapshot_id: snapshot.snapshot_id,
    observed_snapshot_id: snapshot.snapshot_id, information_policy: { includes_hidden_information: false },
    ordering_semantics: "unordered_multiset", content: { kind: "run_deck", card_count: 1, cards: [card] } };
  return { snapshot, deckRead };
}
function evidence() {
  const scenario = "tent-heal-cancel-smith", native = [
    observation(0, "rest_site", ["HEAL", "SMITH"], 25, false),
    observation(1, "rest_site", ["SMITH"], 49, false),
    observation(2, "card_selection", [], 49, false),
    observation(3, "rest_site", ["SMITH"], 49, false),
    observation(4, "card_selection", [], 49, false),
    observation(5, "rest_site", [], 49, true),
    observation(6, "map_navigation", [], 49, true),
  ];
  const plan = native.map(({ snapshot, deckRead }, i) => ({ facts: restFacts(snapshot, deckRead),
    action: i < 6 ? restActionKey(snapshot, chooseRestAction(snapshot, restPlans[scenario][i])) : null }));
  const shipped = { comparisons: structuredClone(native).map((row, i) => ({ ...row, facts: plan[i].facts, index: i, matched: true })),
    privileged_fixture: true, training_allowed: false, menu_actions_requested: 1,
    public_actions_requested: 7, semantic_actions_delivered: 6, upgrade_ui_steps: [], receipts: [] };
  for (const index of [2, 4]) {
    const snapshot = shipped.comparisons[index].snapshot;
    snapshot.interaction.kind = "deck_upgrade_selection";
    Object.assign(snapshot.interaction.content.surface, { stage: "selecting", selected_count: 0, can_confirm: false });
    const choice = snapshot.bound_actions.actions[0]; choice.verb = "select"; choice.subject_referent_id = "chosen"; choice.arguments = [];
  }
  const receipt = (action) => ({ action: structuredClone(action), delivery: "delivered", request_id: `request-${shipped.receipts.length}`,
    attribution: { runtime_instance_id: "runtime" } });
  shipped.receipts.push(receipt({ verb: "activate", bound_action_id: "continue", arguments: [] }));
  for (let i = 0; i < 6; i++) {
    const row = shipped.comparisons[i], selected = chooseRestAction(row.snapshot, restPlans[scenario][i]);
    shipped.receipts.push(receipt(selected));
    if (selected.verb !== "select") continue;
    const preview = structuredClone(row.snapshot); preview.snapshot_id = "preview";
    Object.assign(preview.interaction.content.surface, { stage: "preview", selected_count: 1, selected_card_entity_ids: ["chosen"],
      can_confirm: true, can_cancel_preview: true, preview_cards: [{ ...row.deckRead.content.cards[0], is_upgraded: true }] });
    const confirm = { verb: "confirm", label: "Confirm card upgrade", arguments: [], bound_action_id: "confirm-preview", interaction_id: preview.interaction.interaction_id };
    preview.bound_actions.actions = [confirm, { verb: "cancel", label: "Return to card selection", arguments: [], bound_action_id: "back", interaction_id: preview.interaction.interaction_id }];
    const previewDeck = structuredClone(row.deckRead); previewDeck.expected_snapshot_id = previewDeck.observed_snapshot_id = "preview";
    shipped.upgrade_ui_steps.push({ index: i, before: row.snapshot, preview, deckRead: previewDeck,
      selected_action: selected, confirm_action: confirm, public_game_facts_unchanged: true });
    shipped.receipts.push(receipt(confirm));
  }
  shipped.starting_snapshot = shipped.comparisons[0].snapshot; shipped.latest_snapshot = shipped.comparisons.at(-1).snapshot;
  return { scenario, plan, native, shipped };
}
const audit = ({ scenario, plan, native, shipped }) => verifySavedRest(scenario, plan, native, shipped);
test("saved rest evidence separates six effect decisions from seven delivered UI actions", () => {
  assert.deepEqual(audit(evidence()), { compared_snapshots: 7, semantic_actions_delivered: 6, public_actions_delivered: 7, upgrade_ui_steps: 1 });
});
for (const [name, corrupt] of [
  ["a changed raw observation behind an unchanged pass flag", (e) => { e.native[1].snapshot.persistent.content.player.hp = 48; }],
  ["a confirmation that upgrades the deck before commit", (e) => { e.shipped.upgrade_ui_steps[0].deckRead.content.cards[0].is_upgraded = true; }],
  ["a receipt for a different bound choice", (e) => { e.shipped.receipts[1].action.bound_action_id = "stale"; }],
  ["a delivered action attributed to another process", (e) => { e.shipped.receipts[2].attribution.runtime_instance_id = "other"; }],
  ["a duplicate delivery request", (e) => { e.shipped.receipts[2].request_id = e.shipped.receipts[1].request_id; }],
  ["a hidden or stale deck read", (e) => { e.shipped.comparisons[3].deckRead.observed_snapshot_id = "stale"; }],
  ["a changed expected rest sequence", (e) => { e.scenario = "tent-smith-cancel-heal"; }],
]) test(`saved rest audit rejects ${name}`, () => { const e = evidence(); corrupt(e); assert.throws(() => audit(e)); });

function freshEvidence() {
  const e = evidence(), after = e.shipped.starting_snapshot, afterDeck = e.shipped.comparisons[0].deckRead;
  const before = structuredClone(after); before.snapshot_id = "tutorial";
  before.interaction.kind = "tutorial"; before.interaction.content.context = { kind: "rest" };
  const action = { verb: "activate", label: "Continue", arguments: [], bound_action_id: "dismiss", interaction_id: before.interaction.interaction_id };
  before.interaction.content.surface = { kind: "tutorial", stage: "confirmation", tutorial_id: "rest_site_ftue", title: "Rest", body: "Information",
    current_page: null, total_pages: null, options: [{ semantic_id: "dismiss_tutorial", label: "Continue", enabled: true }] };
  before.bound_actions.actions = [action]; before.bound_actions.materialized_count = before.bound_actions.total_count = 1;
  const beforeDeck = structuredClone(afterDeck); beforeDeck.expected_snapshot_id = beforeDeck.observed_snapshot_id = "tutorial";
  e.shipped.rest_tutorial_steps = [{ before, beforeDeck, after, afterDeck, action, public_game_facts_unchanged: true }];
  e.shipped.tutorial_actions_requested = 1;
  e.shipped.receipts.splice(1, 0, { action: structuredClone(action), delivery: "delivered", request_id: "popup-request", attribution: { runtime_instance_id: "runtime" } });
  return e;
}
const freshAudit = ({ scenario, plan, native, shipped }) => verifySavedRest(scenario, plan, native, shipped, true);
test("fresh rest audit includes a delivered popup control and unchanged public deck and HUD", () => {
  assert.equal(freshAudit(freshEvidence()).rest_tutorial_steps, 1);
});
for (const [name, corrupt] of [
  ["an unknown tutorial", (e) => { e.shipped.rest_tutorial_steps[0].before.interaction.content.surface.tutorial_id = "unknown_ftue"; }],
  ["a missing tutorial", (e) => { e.shipped.rest_tutorial_steps = []; }],
  ["a hidden second popup control", (e) => { e.shipped.rest_tutorial_steps[0].before.bound_actions.materialized_count = 0; }],
  ["HP changes during tutorial dismissal", (e) => { e.shipped.rest_tutorial_steps[0].before.persistent.content.player.hp = 1; }],
  ["a changed popup button label", (e) => { e.shipped.rest_tutorial_steps[0].before.interaction.content.surface.options[0].label = "Different"; }],
]) test(`fresh rest audit rejects ${name}`, () => { const e = freshEvidence(); corrupt(e); assert.throws(() => freshAudit(e)); });
