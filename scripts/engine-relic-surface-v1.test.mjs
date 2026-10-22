import assert from "node:assert/strict";
import test from "node:test";
import { projectSelectionSurface } from "./engine-selection-cursor-v1.mjs";
import { projectRelicSurface, publicCombatRelics, INVENTORY_CONTRACT } from "./engine-relic-surface-v1.mjs";

const fixture = () => ({ decision: "combat_play", hand: [], enemies: [],
  player: { native_ref: "PRIVATE_PLAYER", name: "Player", block: 0, potions: [], relics: [
    { id: "SWORD_OF_STONE", counter: 0, native_ref: "PRIVATE_RELIC", vars: { Hidden: 99 } },
    { id: "INK_BOTTLE", counter: 7, native_ref: "PRIVATE_OTHER" }, { id: "BURNING_BLOOD", counter: null }
  ] }, player_statuses: [], companions: [], orbs: [], orb_slots: 0, stars_visible: false, stars: null,
  energy: 3, max_energy: 3, draw_pile_count: 0, discard_pile_count: 0, exhaust_pile_count: 0,
  round: 1, is_play_phase: true, turn_owner: "player", encounter_type: "normal" });
function context() {
  return { snapshotId: "SNAPSHOT", actions: [], referents: [], id: (...p) => p.join(":"),
    referent(v) { const r = { ...v, referent_id: v.id }; this.referents.push(r); return r; },
    action(v) { this.actions.push(v); } };
}
const helpers = { visibleText: x => x, cardProperties: x => x };

test("numeric zero, no counter and owner-bound values remain distinct", () => {
  const s = fixture(), ctx = context(), before = JSON.stringify(s);
  const r = projectRelicSurface(s, ctx, helpers);
  assert.equal(r.complete, true);
  assert.equal(r.inventoryObservation, INVENTORY_CONTRACT);
  assert.deepEqual(r.context.player.relics, [
    { id: "SWORD_OF_STONE", counter: 0 }, { id: "INK_BOTTLE", counter: 7 }, { id: "BURNING_BLOOD", counter: null }
  ]);
  assert.equal(JSON.stringify(r.context.player.relics).includes("PRIVATE"), false);
  assert.equal(JSON.stringify(r.context.player.relics).includes("Hidden"), false);
  assert.equal(JSON.stringify(s), before);
  s.player.relics[0].counter = 7; s.player.relics[1].counter = 0;
  assert.notDeepEqual(publicCombatRelics(s), r.context.player.relics);
});

test("the repaired projection adds no actions, changes no operands and leaves legacy facts exact", () => {
  const a = context(), b = context(), s = fixture();
  const old = projectSelectionSurface(s, a, helpers), updated = projectRelicSurface(s, b, helpers);
  delete updated.context.player.relics; delete updated.inventoryObservation;
  assert.deepEqual(updated, old); assert.deepEqual(a.actions, b.actions); assert.deepEqual(a.referents, b.referents);
});

test("missing or malformed counters fail before advertising any action", () => {
  const mutations = [s => { delete s.player.relics; }, s => { s.player.relics = null; },
    s => { delete s.player.relics[0].counter; }, s => { s.player.relics[0].counter = NaN; },
    s => { s.player.relics[0].counter = true; }, s => { s.player.relics[0].id = ""; }];
  for (const change of mutations) {
    const s = fixture(), ctx = context(); change(s);
    assert.throws(() => projectRelicSurface(s, ctx, helpers), /relic/u); assert.deepEqual(ctx.actions, []);
  }
});

test("an empty owned inventory stays empty; unknown fields are never copied", () => {
  const s = fixture(); s.player.relics = []; assert.deepEqual(publicCombatRelics(s), []);
  s.player.relics = [{ id: "NEW_RELIC", counter: 2, rng_state: "PRIVATE", future_reward: "PRIVATE" }];
  assert.deepEqual(publicCombatRelics(s), [{ id: "NEW_RELIC", counter: 2 }]);
});
