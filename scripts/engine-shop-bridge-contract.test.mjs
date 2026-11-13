import test from "node:test";
import assert from "node:assert/strict";
import { shopFacts, shopOffer, shopPersistentFacts, shopActionKey, chooseShopAction,
  shopRoomAction, removalUiAction, prepareShopSave, firstDifference } from "./engine-shop-bridge-contract.mjs";

import { observation, preview } from "./engine-shop-test-fixtures.mjs";
test("nested shipped shop offers and native flattened offers compare current prices and owned potion slots", () => {
  const a = observation(), b = observation("shop_inventory", true);
  assert.equal(firstDifference(shopFacts(a.snapshot, a.deckRead), shopFacts(b.snapshot, b.deckRead)), null);
  b.snapshot.interaction.content.surface.cards[0].price++;
  assert.ok(firstDifference(shopFacts(a.snapshot, a.deckRead), shopFacts(b.snapshot, b.deckRead)));
  b.snapshot.persistent.content.player.potions = [{ definition_id: "SYNTHETIC_POTION", slot: 1 }];
  assert.ok(firstDifference(shopPersistentFacts(a.snapshot, a.deckRead), shopPersistentFacts(b.snapshot, b.deckRead)));
});
test("sold-out identity is scoped away while stock, price and availability still compare", () => {
  const a = { definition_id: "SYNTHETIC_CARD", cost: "1", is_upgraded: false, price: 50, is_stocked: false, can_purchase: false, on_sale: false };
  const b = { ...a, card: { definition_id: "OLD_DISPLAY", cost: "0", is_upgraded: false } };
  assert.deepEqual(shopOffer(a, "cards", 0), shopOffer(b, "cards", 0));
  assert.throws(() => shopOffer({ ...a, stocked: true }, "cards", 0), /conflicting/);
  assert.throws(() => shopOffer({ ...a, can_purchase: true }, "cards", 0), /availability/);
  assert.throws(() => shopOffer({ ...a, price: "50" }, "cards", 0), /price/);
});
test("restocked items bind to this fresh offer and quote; old or duplicate references fail", () => {
  const { snapshot } = observation(); const chosen = chooseShopAction(snapshot, "card");
  snapshot.interaction.content.surface.cards[0].definition_id = "NEW_CARD";
  assert.equal(shopActionKey(snapshot, chosen).subject.item.definition_id, "NEW_CARD");
  snapshot.referents.push(structuredClone(snapshot.referents[0]));
  assert.throws(() => shopActionKey(snapshot, chosen), /unique current public operand/);
  snapshot.referents.pop();
  chosen.subject_referent_id = "old-offer";
  assert.throws(() => shopActionKey(snapshot, chosen), /current public operand/);
});
test("only the observed Close-inventory alias is normalized, with current close permission", () => {
  const { snapshot } = observation("shop_inventory", true); const close = chooseShopAction(snapshot, "close");
  assert.equal(close.verb, "cancel"); close.label = "Other modal";
  assert.throws(() => shopActionKey(snapshot, close), /current public operand/);
  close.label = "Close shop inventory"; snapshot.interaction.content.surface.can_close = false;
  assert.throws(() => shopActionKey(snapshot, close));
});
test("partial menus, hidden reads and colliding potion slots cannot qualify", () => {
  for (const corrupt of [
    (a) => { a.snapshot.bound_actions.materialized_count = 0; },
    (a) => { a.deckRead.information_policy.includes_hidden_information = true; },
    (a) => { a.deckRead.observed_snapshot_id = "old"; },
    (a) => { a.snapshot.persistent.content.player.potions = [{ definition_id: "A", slot: 0 }, { definition_id: "B", slot: 0 }]; },
  ]) { const a = observation(); corrupt(a); assert.throws(() => shopFacts(a.snapshot, a.deckRead)); }
});
test("room open/Proceed controls must both be live and complete", () => {
  const { snapshot } = observation("shop_room", true);
  assert.equal(shopRoomAction(snapshot, "open").bound_action_id, "open");
  snapshot.interaction.content.surface.can_proceed = false;
  assert.throws(() => shopRoomAction(snapshot, "proceed"), /complete live/);
});
test("removal preview must not change gold, deck, potion ownership or chosen card", () => {
  const a = observation("native_deck_card_selection", true), selected = chooseShopAction(a.snapshot, "confirm-strike");
  const p = preview(a, selected, "preview", "p");
  assert.equal(removalUiAction(a.snapshot, a.deckRead, p.snapshot, p.deckRead, selected, "preview").verb, "confirm");
  for (const corrupt of [
    (row) => { row.snapshot.persistent.content.player.gold--; },
    (row) => { row.deckRead.content.cards.pop(); row.deckRead.content.card_count--; },
    (row) => { row.snapshot.interaction.content.surface.selected_card_entity_ids = ["other"]; },
    (row) => { row.snapshot.interaction.content.surface.cards[0].cost = "0"; },
    (row) => { row.snapshot.bound_actions.actions.pop(); row.snapshot.bound_actions.total_count--; row.snapshot.bound_actions.materialized_count--; },
  ]) { const value = structuredClone(p); corrupt(value); assert.throws(() => removalUiAction(a.snapshot, a.deckRead, value.snapshot, value.deckRead, selected, "preview")); }
});
test("shop fixture mutation is explicit, narrow and leaves the original save unchanged", () => {
  const value = { ascension: 8, current_act_index: 0, players: [{ gold: 1000 }], visited_map_coords: [{ col: 0, row: 0 }],
    acts: [{ saved_map: { start: { coord: { col: 0, row: 0 }, type: "ancient" }, points: [] } }], pre_finished_room: { old: true } };
  const out = prepareShopSave(value);
  assert.equal(out.acts[0].saved_map.start.type, "shop"); assert.equal(value.acts[0].saved_map.start.type, "ancient");
  assert.deepEqual(out.players, value.players); assert.equal(out.pre_finished_room, null);
  assert.throws(() => prepareShopSave({ ...value, ascension: 0 }), /frozen A8/);
});
