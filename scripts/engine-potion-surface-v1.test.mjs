import assert from "node:assert/strict";
import test from "node:test";
import { appendPotionControls } from "./engine-potion-surface-v1.mjs";
import { projectRunSurface } from "./engine-run-contract-v5.mjs";
const helpers = { visibleText: value => value ?? null, cardProperties: row => ({ definition_id: row.id }), withoutDeck: ({ deck, ...value }) => value };
function context() {
  const ctx = { actions: [], referents: [], snapshotId: "snapshot", id: (...values) => `public-${values.length}-${values[0]}`,
    action: value => ctx.actions.push(value), referent(value) { const row = { ...value,
      referent_id: value.id, properties: { ...value.properties, entity_id: value.id } }; ctx.referents.push(row); return row; } };
  return ctx;
}
const potion = (id = "BLOOD_POTION", extra = {}) => ({ id, name: id, native_ref: "private-copy", description: "Public description", slot: 0,
  usage: "AnyTime", can_use: true, can_discard: true, binding_supported: true, target_type: "AnyPlayer", valid_target_refs: ["private-player"], ...extra });
const state = (row = potion()) => ({ decision: "rest", player: { native_ref: "private-player", name: "Player", hp: 30, max_hp: 80, potions: [row] } });
function project(input) { const ctx = context(), result = appendPotionControls(input, ctx, helpers, { complete: true, missing: [], surface: {} }); return { ctx, result }; }
test("outside-combat use binds the exact belt copy, slot and current player", () => {
  const { ctx, result } = project(state()); assert.equal(result.complete, true);
  const use = ctx.actions.find(a => a.verb === "use");
  assert.deepEqual(use.raw.args, { potion_slot: 0, potion_ref: "private-copy", target_ref: "private-player" });
  assert.equal(use.arguments[0].referent.role, "player");
  assert.equal(ctx.actions.filter(a => a.raw.action === "discard_potion").length, 1);
  assert(!JSON.stringify(result).includes("private-"));
});
test("current slots distinguish identical potions and are not enumeration indices", () => {
  const input = state(); input.player.potions.push(potion("BLOOD_POTION", { native_ref: "other-copy", slot: 1 })); input.player.potions.reverse();
  const uses = project(input).ctx.actions.filter(a => a.verb === "use");
  assert.deepEqual(uses.map(a => a.raw.args.potion_slot), [1, 0]);
  assert.deepEqual(uses.map(a => a.raw.args.potion_ref), ["other-copy", "private-copy"]);
});
test("the exact current closed merchant is a non-creature target", () => {
  const input = { ...state(potion("FOUL_POTION", { target_type: "TargetedNoCreature", valid_target_refs: ["private-merchant"] })),
    decision: "merchant_approach", room_ref: "private-room", merchant_ref: "private-merchant", inventory_open: false };
  const { ctx, result } = project(input); assert.equal(result.complete, true);
  const use = ctx.actions.find(a => a.verb === "use"); assert.equal(use.arguments[0].referent.role, "merchant");
  assert.deepEqual(use.raw.args, { potion_slot: 0, potion_ref: "private-copy", target_ref: "private-merchant", room_ref: "private-room" });
  assert(!JSON.stringify(result).includes("private-"));
  for (const change of [s => s.inventory_open = true, s => s.merchant_ref = "stale", s => s.room_ref = null]) {
    const changed = structuredClone(input); change(changed); const bad = project(changed);
    assert.equal(bad.result.complete, false); assert.equal(bad.ctx.actions.length, 0);
  }
});
test("automatic, combat-only and unavailable potions keep discard without illegal use", () => {
  for (const usage of ["Automatic", "CombatOnly", "AnyTime"]) {
    const { ctx, result } = project(state(potion("FORTIFIER", { usage, can_use: false })));
    assert.equal(result.complete, true); assert.deepEqual(ctx.actions.map(a => a.raw.action), ["discard_potion"]);
  }
  assert.equal(project(state(potion("FORTIFIER", { usage: "CombatOnly" }))).result.complete, false);
});
test("missing or conflicting target/copy facts make the public menu incomplete", () => {
  for (const change of [s => s.player.potions[0].native_ref = null, s => s.player.potions[0].slot = -1,
    s => s.player.potions[0].valid_target_refs = ["somebody-else"], s => s.player.potions[0].can_use = null,
    s => s.player.potions.push(structuredClone(s.player.potions[0]))]) {
    const input = state(); change(input); const { ctx, result } = project(input);
    assert.equal(result.complete, false); assert.equal(ctx.actions.length, 0);
  }
});
test("terminal and combat surfaces never receive duplicate global potion actions", () => {
  for (const decision of ["game_over", "combat_play"]) {
    const input = { ...state(), decision }; const { ctx, result } = project(input);
    assert.equal(ctx.actions.length, 0); assert.deepEqual(result.surface, {});
  }
});
test("the merchant approach exports open and leave, without revealing inventory", () => {
  const input = { ...state(), decision: "merchant_approach", inventory_open: false, room_ref: "room", merchant_ref: "merchant", context: {} };
  const ctx = context(), result = projectRunSurface(input, ctx, helpers);
  assert.equal(result.complete, true); assert.deepEqual(result.surface.cards, []);
  assert.deepEqual(ctx.actions.slice(0, 2).map(a => a.raw.action), ["open_shop", "leave_shop"]);
  assert(ctx.actions.some(a => a.raw.action === "use_potion"));
});
