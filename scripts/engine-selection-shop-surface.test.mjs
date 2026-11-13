import assert from "node:assert/strict";
import test from "node:test";
import { projectExactSelectionShopSurface } from "./engine-selection-shop-surface.mjs";

function project(state) {
  const ctx = { referents: [], actions: [],
    referent(value) { const item = { ...value, properties: { ...value.properties,
      entity_id: `entity-${this.referents.length}` } }; this.referents.push(item); return item; },
    action(value) { this.actions.push(value); } };
  const helpers = { withoutDeck: (value) => value, visibleText: (value) => value ?? null,
    cardProperties: (card) => ({ definition_id: card.id, name: card.name, cost: String(card.cost) }),
    defaultProjector: () => ({ unchanged: true }), actionLimit: 512,
    enumerateSelections(items, min, max) {
      assert.ok(max <= 1); return [...(min === 0 ? [[]] : []), ...(max === 1 ? items.map((item) => [item]) : [])];
    } };
  return { result: projectExactSelectionShopSurface(state, ctx, helpers), ...ctx };
}
const entry = (id) => ({ id, name: id, native_ref: `PRIVATE_ENTRY_${id}`, item_ref: `PRIVATE_ITEM_${id}`,
  cost: 75, card_cost: 2, is_stocked: true, can_purchase: true, on_sale: false });
const shop = () => ({ decision: "shop", room_ref: "PRIVATE_ROOM", cards: [entry("CARD")],
  relics: [entry("RELIC")], potions: [entry("POTION")], card_removal: {
    native_ref: "PRIVATE_SERVICE", cost: 50, is_stocked: true, can_purchase: true } });
const selection = () => ({ decision: "card_select", selection_ref: "PRIVATE_SELECTION",
  selection_preferences_complete: true, prompt: "Choose a card", min_select: 1, max_select: 1,
  cancelable: true, require_manual_confirmation: true, unpowered_previews: false,
  pretend_cards_can_be_played: true, cards: [{ index: 0, id: "CARD", name: "Card" }] });

test("shop bindings retain current model and gold price privately; public card energy stays distinct", () => {
  const actual = project(shop());
  assert.equal(actual.result.complete, true); assert.equal(actual.actions.length, 5);
  assert.deepEqual(actual.actions[0].raw.args,
    { entry_ref: "PRIVATE_ENTRY_CARD", item_ref: "PRIVATE_ITEM_CARD", quoted_cost: 75 });
  assert.equal(actual.result.surface.cards[0].cost, "2");
  assert.equal(actual.result.surface.cards[0].price, 75);
  assert.equal(actual.result.surface.relics[0].definition_id, "RELIC");
  assert.deepEqual(actual.actions[3].raw.args, { entry_ref: "PRIVATE_SERVICE", quoted_cost: 50 });
  assert.doesNotMatch(JSON.stringify({ surface: actual.result, referents: actual.referents }),
    /PRIVATE_|native_ref|room_ref|item_ref/u);
});
test("current native enablement controls exhausted services and forbidden or full-capacity potions", () => {
  const state = shop(); state.potions[0].can_purchase = false;
  state.card_removal.is_stocked = false; state.card_removal.can_purchase = false;
  const actual = project(state);
  assert.deepEqual(actual.actions.map((item) => item.raw.action), ["buy_card", "buy_relic", "leave_shop"]);
  assert.equal(actual.result.surface.potions[0].can_purchase, false);
});
test("X energy and free zero energy remain distinct in restocked shop offers and purchase quotes", () => {
  const state = shop();
  state.cards[0].card_cost = "X";
  state.cards.push({ ...entry("FREE"), card_cost: 0 });
  const actual = project(state);
  assert.equal(actual.result.complete, true);
  assert.deepEqual(actual.result.surface.cards.map((row) => [row.cost, row.price]), [["X", 75], ["0", 75]]);
  assert.deepEqual(actual.actions.slice(0, 2).map((row) => row.raw.args.quoted_cost), [75, 75]);
  state.cards[0].item_ref = "PRIVATE_RESTOCK_X";
  state.cards[0].cost = 57;
  const restocked = project(state);
  assert.equal(restocked.result.surface.cards[0].cost, "X");
  assert.equal(restocked.actions[0].raw.args.item_ref, "PRIVATE_RESTOCK_X");
  assert.equal(restocked.actions[0].raw.args.quoted_cost, 57);
});
test("restocked entries get the replacement item and price instead of stale purchase operands", () => {
  const before = shop(), after = shop(); after.cards[0].item_ref = "PRIVATE_RESTOCK"; after.cards[0].cost = 99;
  assert.notDeepEqual(project(before).actions[0].raw, project(after).actions[0].raw);
});
test("missing, ambiguous and malformed native shop authority never advertises purchases or exit", () => {
  for (const change of [
    (state) => { delete state.room_ref; }, (state) => { delete state.cards; },
    (state) => { delete state.card_removal; }, (state) => { state.cards[0].cost = "75"; },
    (state) => { delete state.cards[0].item_ref; }, (state) => { delete state.relics[0].id; },
    (state) => { state.potions[0].can_purchase = null; },
    (state) => { state.cards[0].is_stocked = false; },
    (state) => { state.relics[0].native_ref = state.cards[0].native_ref; }
  ]) {
    const state = shop(); change(state); const actual = project(state);
    assert.equal(actual.result.complete, false); assert.equal(actual.actions.length, 0);
  }
});
test("selector instance and native preview settings stay bound across confirm and cancel", () => {
  const actual = project(selection());
  assert.equal(actual.result.complete, true); assert.equal(actual.result.prompt, "Choose a card");
  assert.equal(actual.result.surface.pretend_cards_can_be_played, true);
  for (const action of actual.actions) assert.equal(action.raw.args.selection_ref, "PRIVATE_SELECTION");
  assert.deepEqual(actual.actions.map((item) => item.verb), ["confirm", "cancel"]);
  assert.doesNotMatch(JSON.stringify({ surface: actual.result, referents: actual.referents }), /PRIVATE_|selection_ref/u);
});
test("mandatory single-card selection has no cancel, and optional empty confirm stays a separate action", () => {
  const state = selection(); state.cancelable = false;
  assert.deepEqual(project(state).actions.map((item) => item.verb), ["confirm"]);
  state.cancelable = true; state.min_select = 0;
  const actual = project(state);
  assert.deepEqual(actual.actions.map((item) => item.verb), ["confirm", "confirm", "cancel"]);
  assert.equal(actual.actions[0].raw.args.indices, "");
});
test("unknown captured preferences, preview settings or selection identity fail closed", () => {
  for (const change of [
    (state) => { delete state.selection_ref; },
    (state) => { state.selection_preferences_complete = false; },
    (state) => { delete state.unpowered_previews; },
    (state) => { state.pretend_cards_can_be_played = null; }
  ]) {
    const state = selection(); change(state); const actual = project(state);
    assert.equal(actual.result.complete, false); assert.equal(actual.actions.length, 0);
  }
});
