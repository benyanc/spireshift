import assert from "node:assert/strict";
import test from "node:test";
import { observeAfterMerchantExit } from "./engine-merchant-map-observation-v1.mjs";

const exit = { cmd: "action", action: "leave_shop", args: { room_ref: "room" } };
const stale = { id: "FOUL_POTION", slot: 1, target_type: "TargetedNoCreature",
  native_ref: "foul", can_use: true, can_discard: true, valid_target_refs: ["merchant"] };
const blood = { id: "BLOOD_POTION", slot: 0, target_type: "Self", native_ref: "blood",
  can_use: true, can_discard: true, valid_target_refs: null };
const map = { type: "decision", decision: "map_select", choices: [{ col: 1, row: 2 }],
  context: { room_type: "Shop" }, player: { hp: 30, potions: [blood, stale] } };
const fresh = { ...map, player: { ...map.player, potions: [
  blood, { ...stale, can_use: false, valid_target_refs: [] },
] } };

test("merchant exit obtains one native observation without replaying the exit", async () => {
  const requests = [];
  const actual = await observeAfterMerchantExit(exit, map, request => {
    requests.push(request);
    return fresh;
  });
  assert.equal(actual, fresh);
  assert.deepEqual(requests, [{ cmd: "observe" }]);
  assert.equal(stale.can_use, true);
});

test("current map, inventory and merchant menus need no extra native read", async () => {
  const never = () => assert.fail("Unexpected native read");
  assert.equal(await observeAfterMerchantExit(exit, fresh, never), fresh);
  assert.equal(await observeAfterMerchantExit({ cmd: "action", action: "close_shop" }, map, never), map);
  const shop = { ...map, decision: "merchant_approach" };
  assert.equal(await observeAfterMerchantExit(exit, shop, never), shop);
});

test("an inconsistent read or unknown target fails without replacing legal choices", async () => {
  for (const response of [map, { ...fresh, choices: [] },
    { ...fresh, player: { ...fresh.player, hp: 29 } }]) {
    await assert.rejects(observeAfterMerchantExit(exit, map, () => response), /refresh changed/u);
  }
  const unknown = { ...map, player: { ...map.player, potions: [{ ...stale, id: "UNKNOWN" }] } };
  await assert.rejects(observeAfterMerchantExit(exit, unknown, () => fresh), /Unrecognized native target/u);
});
