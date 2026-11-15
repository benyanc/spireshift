import test from "node:test";
import assert from "node:assert/strict";
import { prepareRestSave, restFacts, chooseRestAction, restActionKey, firstDifference, upgradePreviewConfirmation } from "./engine-rest-bridge-contract.mjs";

function rest({ remaining = ["HEAL", "SMITH"], canLeave = false } = {}) {
  const options = remaining.map((option_id, index) => ({ index, option_id, is_enabled: true }));
  const actions = options.map((row) => ({ verb: "activate", subject_referent_id: `ref-${row.option_id}`,
    arguments: [], bound_action_id: `action-${row.option_id}`, interaction_id: "i" }));
  if (canLeave) actions.push({ verb: "close", subject_referent_id: null, arguments: [], bound_action_id: "leave", interaction_id: "i" });
  const snapshot = { snapshot_id: "s", status: "interactive", session: { runtime_instance_id: "r" },
    information_policy: { includes_hidden_information: false }, completeness: { status: "complete" },
    bound_actions: { actions, status: "complete", total_count: actions.length, materialized_count: actions.length },
    interaction: { interaction_id: "i", kind: "rest_site", content: { surface: { options, can_leave: canLeave } } },
    referents: options.map((row) => ({ referent_id: `ref-${row.option_id}`, properties: row })),
    persistent: { content: { run: { act: 1, act_definition_id: "TEST_ACT", floor: 1, ascension: 8 },
      player: { character_definition_id: "IRONCLAD", hp: 25, max_hp: 80, gold: 99, max_potion_slots: 2,
        relics: [{ definition_id: "MINIATURE_TENT" }] } } } };
  const deckRead = { kind: "run_deck", completeness: { status: "complete" }, expected_snapshot_id: "s", observed_snapshot_id: "s",
    information_policy: { includes_hidden_information: false }, ordering_semantics: "unordered_multiset",
    content: { kind: "run_deck", card_count: 1, cards: [{ definition_id: "TEST_CARD", cost: "1", is_upgraded: false }] } };
  return { snapshot, deckRead };
}

test("remaining rest choices and Proceed are separate, observable legal controls", () => {
  const initial = rest(), healed = rest({ remaining: ["SMITH"], canLeave: true });
  healed.snapshot.persistent.content.player.hp = 49;
  assert.throws(() => chooseRestAction(initial.snapshot, "close"), /No unique/);
  assert.equal(chooseRestAction(healed.snapshot, "SMITH").bound_action_id, "action-SMITH");
  assert.equal(chooseRestAction(healed.snapshot, "close").bound_action_id, "leave");
  assert.throws(() => chooseRestAction(healed.snapshot, "HEAL"), /No unique/);
  assert.ok(firstDifference(restFacts(initial.snapshot, initial.deckRead), restFacts(healed.snapshot, healed.deckRead)));
});
test("stale operands and partial menus never become guessed actions", () => {
  const { snapshot, deckRead } = rest();
  snapshot.bound_actions.actions[0].subject_referent_id = "stale";
  assert.throws(() => restActionKey(snapshot, snapshot.bound_actions.actions[0]), /no current/);
  snapshot.bound_actions.materialized_count = 0;
  assert.throws(() => restFacts(snapshot, deckRead), /Incomplete/);
});
test("the observed Host Proceed alias still requires its exact label and current exit permission", () => {
  const native = rest({ canLeave: true }), shipped = rest({ canLeave: true });
  const action = shipped.snapshot.bound_actions.actions.at(-1);
  action.verb = "activate"; action.label = "Proceed to map"; delete action.subject_referent_id;
  assert.equal(firstDifference(restFacts(native.snapshot, native.deckRead), restFacts(shipped.snapshot, shipped.deckRead)), null);
  assert.equal(chooseRestAction(shipped.snapshot, "close").bound_action_id, "leave");
  action.label = "Other control";
  assert.throws(() => restActionKey(shipped.snapshot, action), /Unqualified/);
  action.label = "Proceed to map"; shipped.snapshot.interaction.content.surface.can_leave = false;
  assert.throws(() => restActionKey(shipped.snapshot, action), /current operand-free/);
});
test("the two verified rest schema spellings agree; conflicting or absent flags fail", () => {
  const native = rest(), shipped = rest();
  const surface = shipped.snapshot.interaction.content.surface;
  surface.can_proceed = surface.can_leave; delete surface.can_leave;
  surface.options.forEach((row) => { row.enabled = row.is_enabled; delete row.is_enabled; });
  assert.equal(firstDifference(restFacts(native.snapshot, native.deckRead), restFacts(shipped.snapshot, shipped.deckRead)), null);
  surface.can_leave = !surface.can_proceed;
  assert.throws(() => restFacts(shipped.snapshot, shipped.deckRead), /conflicting/);
  delete surface.can_leave; delete surface.can_proceed;
  assert.throws(() => restFacts(shipped.snapshot, shipped.deckRead), /Missing/);
});
test("upgrade effect and current card cost remain attached to the card definition", () => {
  const original = rest(), upgraded = rest();
  upgraded.deckRead.content.cards[0].is_upgraded = true;
  assert.ok(firstDifference(restFacts(original.snapshot, original.deckRead), restFacts(upgraded.snapshot, upgraded.deckRead)).field.includes("deck"));
  upgraded.deckRead.content.cards[0].cost = "0";
  assert.ok(firstDifference(restFacts(original.snapshot, original.deckRead), restFacts(upgraded.snapshot, upgraded.deckRead)));
});
test("a deck read must be public, complete and bound to this observation", () => {
  for (const change of [
    (row) => { row.information_policy.includes_hidden_information = true; },
    (row) => { row.observed_snapshot_id = "old"; },
    (row) => { row.completeness.status = "partial"; },
    (row) => { row.content.card_count = 2; }
  ]) { const { snapshot, deckRead } = rest(); change(deckRead); assert.throws(() => restFacts(snapshot, deckRead), /Complete public/); }
});
test("fixture edits preserve native player data and do not mutate the exported original", () => {
  const save = { ascension: 8, current_act_index: 0, players: [{ current_hp: 25 }],
    visited_map_coords: [{ col: 3, row: 0 }], map_point_history: [[{ fixture: "old" }]], pre_finished_room: { fixture: "old" },
    acts: [{ saved_map: { start: { coord: { col: 3, row: 0 }, type: "ancient" }, points: [] } }] };
  const updated = prepareRestSave(save);
  assert.deepEqual(updated.players, save.players);
  assert.equal(updated.acts[0].saved_map.start.type, "rest_site");
  assert.equal(updated.pre_finished_room, null); assert.deepEqual(updated.map_point_history, [[]]);
  assert.equal(save.acts[0].saved_map.start.type, "ancient");
  assert.throws(() => prepareRestSave({ ...save, ascension: 0 }), /frozen A8/);
});

function picker(shipped) {
  const { snapshot, deckRead } = rest();
  const chosen = { ...deckRead.content.cards[0], index: 0, entity_id: "chosen" };
  snapshot.interaction.kind = shipped ? "deck_upgrade_selection" : "card_selection";
  snapshot.interaction.content.surface = { cards: [chosen], min_select: 1, max_select: 1, cancelable: true,
    stage: "selecting", selected_count: 0, can_confirm: false, can_toggle_upgrade_view: true };
  snapshot.referents = [{ referent_id: "chosen", properties: chosen }];
  const choice = { verb: shipped ? "select" : "confirm", subject_referent_id: shipped ? "chosen" : null,
    arguments: shipped ? [] : [{ role: "selected_card", referent_id: "chosen" }], bound_action_id: "choice", interaction_id: "i" };
  snapshot.bound_actions.actions = [choice, { verb: "cancel", subject_referent_id: null, arguments: [], bound_action_id: "cancel", interaction_id: "i" }];
  if (shipped) snapshot.bound_actions.actions.push({ verb: "activate", label: "Show upgraded card previews", subject_referent_id: null,
    arguments: [], bound_action_id: "view", interaction_id: "i" });
  snapshot.bound_actions.total_count = snapshot.bound_actions.materialized_count = snapshot.bound_actions.actions.length;
  return { snapshot, deckRead };
}

test("atomic native upgrade and shipped picker agree only on this single-card effect menu", () => {
  const native = picker(false), shipped = picker(true);
  assert.equal(firstDifference(restFacts(native.snapshot, native.deckRead), restFacts(shipped.snapshot, shipped.deckRead)), null);
  shipped.snapshot.bound_actions.actions.at(-1).label = "Unknown gameplay operation";
  assert.throws(() => restFacts(shipped.snapshot, shipped.deckRead), /Unqualified upgrade/);
  const ambiguous = picker(true);
  ambiguous.snapshot.interaction.content.surface.cards.push({ ...ambiguous.snapshot.interaction.content.surface.cards[0] });
  assert.throws(() => restFacts(ambiguous.snapshot, ambiguous.deckRead), /single-card/);
});

test("upgrade preview may not commit early, switch cards or hide confirmation controls", () => {
  const before = picker(true), after = structuredClone(before);
  const surface = after.snapshot.interaction.content.surface;
  const expected = { ...before.deckRead.content.cards[0], is_upgraded: true };
  Object.assign(surface, { stage: "preview", selected_count: 1, selected_card_entity_ids: ["chosen"], can_confirm: true,
    preview_cards: [expected], can_cancel_preview: true });
  after.snapshot.bound_actions.actions = [
    { verb: "confirm", label: "Confirm card upgrade", subject_referent_id: null, arguments: [], bound_action_id: "confirm", interaction_id: "i" },
    { verb: "cancel", label: "Return to card selection", subject_referent_id: null, arguments: [], bound_action_id: "back", interaction_id: "i" }];
  after.snapshot.bound_actions.materialized_count = after.snapshot.bound_actions.total_count = 2;
  assert.equal(upgradePreviewConfirmation(before.snapshot, before.deckRead, after.snapshot, after.deckRead, expected).bound_action_id, "confirm");
  for (const change of [
    (row) => { row.snapshot.interaction.content.surface.selected_card_entity_ids = ["other"]; },
    (row) => { row.deckRead.content.cards[0].is_upgraded = true; },
    (row) => { row.snapshot.bound_actions.actions.pop(); },
    (row) => { row.snapshot.interaction.content.surface.preview_cards[0].cost = "0"; },
  ]) {
    const changed = structuredClone(after); change(changed);
    assert.throws(() => upgradePreviewConfirmation(before.snapshot, before.deckRead, changed.snapshot, changed.deckRead, expected));
  }
});
