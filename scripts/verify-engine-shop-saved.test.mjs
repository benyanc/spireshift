import test from "node:test";
import assert from "node:assert/strict";
import { savedShopFixture } from "./engine-shop-test-fixtures.mjs";
import { verifySavedShop } from "./verify-engine-shop-saved.mjs";

const verify = (value) => verifySavedShop(value.scenario, value.plan, value.nativeSnapshots, value.shipped);
for (const scenario of ["ordinary-purchases-removal", "courier-restock-removal"]) {
  test(`saved ${scenario} audit verifies the complete public purchase, popup and removal sequence`, () => {
    const result = verify(savedShopFixture(scenario));
    assert.equal(result.semantic_actions_delivered, scenario.startsWith("ordinary") ? 8 : 9);
    assert.equal(result.shop_ui_steps, 3); assert.equal(result.potion_tutorial_steps, 1);
  });
}

test("saving reordered JSON object keys preserves the purchased-card multiset", () => {
  const sortedKeys = (value) => Array.isArray(value) ? value.map(sortedKeys)
    : value && typeof value === "object" ? Object.fromEntries(Object.keys(value).sort().map((key) => [key, sortedKeys(value[key])])) : value;
  assert.equal(verify(sortedKeys(savedShopFixture("courier-restock-removal"))).semantic_actions_delivered, 9);
});

test("fresh reads of the same public deck can have different observation times", () => {
  const value = savedShopFixture("ordinary-purchases-removal");
  value.shipped.potion_tutorial_steps[0].afterDeck = structuredClone(value.shipped.potion_tutorial_steps[0].afterDeck);
  value.shipped.potion_tutorial_steps[0].afterDeck.observed_at = "synthetic-earlier-read";
  value.shipped.comparisons[2].deckRead.observed_at = "synthetic-later-read";
  assert.equal(verify(value).potion_tutorial_steps, 1);
  value.shipped.potion_tutorial_steps[0].afterDeck.expected_snapshot_id = "old";
  assert.throws(() => verify(value));
});

test("a success label cannot hide changed prices, missing receipts, misplaced previews or cross-host data", () => {
  for (const corrupt of [
    (a) => { a.shipped.comparisons[1].snapshot.interaction.content.surface.potions[0].price++; },
    (a) => { a.shipped.receipts.splice(3, 1); },
    (a) => { a.shipped.receipts[3].action.bound_action_id = "old-offer"; },
    (a) => { a.shipped.receipts[3].attribution.runtime_instance_id = "another-host"; },
    (a) => { a.shipped.receipts[3].request_id = a.shipped.receipts[2].request_id; },
    (a) => { a.shipped.shop_ui_steps[1].current.persistent.content.player.gold--; },
    (a) => { a.shipped.shop_ui_steps[1].index--; },
    (a) => { a.shipped.potion_tutorial_steps[0].before.interaction.content.surface.tutorial_id = "unknown_ftue"; },
    (a) => { a.shipped.potion_tutorial_steps[0].before.persistent.content.player.potions[0].slot = 1; },
    (a) => { a.nativeSnapshots[2].deckRead.content.cards.pop(); a.nativeSnapshots[2].deckRead.content.card_count--; },
  ]) { const value = savedShopFixture("ordinary-purchases-removal"); corrupt(value); assert.throws(() => verify(value)); }
});
