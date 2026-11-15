import assert from "node:assert/strict";
import test from "node:test";
import { projectExactCombatSurface, projectExactCombatReads } from "./engine-combat-surface.mjs";

const helpers = { cardProperties: (row) => ({ definition_id: row.id, name: row.name, type: row.type,
  cost: String(row.cost), is_upgraded: row.is_upgraded, stats: row.stats, keywords: row.keywords }),
  visibleText: (text) => text?.replace(/\[\/?[a-z]+\]/gu, "") ?? null };
function context() {
  const ctx = { snapshotId: "snapshot", referents: [], actions: [],
    id: (...parts) => parts.join(":"),
    referent(value) {
      const item = { ...value, referent_id: value.id, properties: { ...value.properties,
        ...(value.includeEntityId === false ? {} : { entity_id: value.id }) } };
      this.referents.push(item); return item;
    }, action(value) { this.actions.push(value); } };
  return ctx;
}
const power = (id, amount) => ({ id, amount, name: id, description: `${id}: ${amount}`, type: "Buff" });
const handCard = (ref, extra = {}) => ({ native_ref: ref, id: "CARD.STRIKE", name: "Strike", type: "Attack",
  cost: 1, is_upgraded: false, can_play: true, target_type: "AnyEnemy", valid_target_refs: ["PRIVATE_E1", "PRIVATE_E2"],
  description: "Deal 6 damage", stats: { damage: 6 }, keywords: [], ...extra });
const enemy = (ref, number) => ({ native_ref: ref, id: "MONSTER", combat_id: number, name: "Enemy",
  hp: 30, max_hp: 30, block: 0, statuses: [power("STRENGTH", number)], intends_attack: true,
  intents: [{ type: "Attack", label: "5 x 2", title: "Attack", description: "Twice", damage: 5, hits: 2, total_damage: 10 }] });
const fixture = () => ({ decision: "combat_play", hand: [handCard("PRIVATE_C1"), handCard("PRIVATE_C2", { cost: 0, stats: { damage: 9 } })],
  enemies: [enemy("PRIVATE_E1", 1), enemy("PRIVATE_E2", 2)], player: { native_ref: "PRIVATE_PLAYER", name: "Player", block: 0,
    potions: [{ native_ref: "PRIVATE_POTION", id: "STRENGTH_POTION", name: "Strength", description: "Strength +2", slot: 0,
      binding_supported: true, can_use: true, can_discard: true, target_type: "AnyPlayer", valid_target_refs: ["PRIVATE_PLAYER"] }] },
  player_statuses: [power("STRENGTH", 2), power("DEXTERITY", 7)], companions: [], orbs: [], orb_slots: 0,
  energy: 3, max_energy: 3, draw_pile_count: 2, discard_pile_count: 0, exhaust_pile_count: 0,
  round: 1, is_play_phase: true, turn_owner: "player", encounter_type: "normal" });
const project = (state) => { const ctx = context(); return { result: projectExactCombatSurface(state, ctx, helpers), ctx }; };

test("copies of the same card keep their current costs, stats, targets and private delivery operands", () => {
  const { result, ctx } = project(fixture());
  assert.equal(result.complete, true); assert.equal(ctx.actions.length, 7);
  const hand = result.context.player.hand;
  assert.notEqual(hand[0].entity_id, hand[1].entity_id);
  assert.deepEqual(hand.map(({ cost, stats }) => ({ cost, stats })), [{ cost: "1", stats: { damage: 6 } }, { cost: "0", stats: { damage: 9 } }]);
  assert.deepEqual(ctx.actions[2].raw.args, { card_ref: "PRIVATE_C2", target_ref: "PRIVATE_E1" });
});
test("different stat amounts keep their owner and meaning across player and enemies", () => {
  const { result } = project(fixture());
  assert.deepEqual(result.context.player.statuses.map(({ definition_id, amount }) => [definition_id, amount]), [["STRENGTH", 2], ["DEXTERITY", 7]]);
  assert.deepEqual(result.context.enemies.map((row) => row.statuses[0].amount), [1, 2]);
  const changed = fixture(); changed.player_statuses = [power("STRENGTH", 7), power("DEXTERITY", 2)];
  assert.notDeepEqual(project(changed).result.context.player.statuses, result.context.player.statuses);
});
test("player-targeted potions bind the current player and keep both use and discard", () => {
  const { result, ctx } = project(fixture());
  const action = ctx.actions.find((row) => row.raw.action === "use_potion");
  assert.deepEqual(action.raw.args, { potion_slot: 0, potion_ref: "PRIVATE_POTION", target_ref: "PRIVATE_PLAYER" });
  assert.equal(action.arguments[0].referent.referent_id, result.context.player.player_entity_id);
  const player = ctx.referents.find((row) => row.role === "player");
  assert.deepEqual(player.properties.hand, result.context.player.hand);
  assert.deepEqual(player.properties.potion_states, result.context.player.potion_states);
});
test("multi-hit amounts remain per hit, count and total; X is distinct from zero", () => {
  const state = fixture(); state.hand[0].cost = "X";
  const { result } = project(state);
  assert.equal(result.context.player.hand[0].cost, "X");
  const intent = result.context.enemies[0].intents[0];
  assert.deepEqual([intent.damage, intent.hits, intent.total_damage], [5, 2, 10]);
});
test("unknown operands, cost facts, ownership, modifiers and player phases never offer actions", () => {
  for (const change of [
    (state) => { state.hand[1].native_ref = state.hand[0].native_ref; },
    (state) => { state.hand[0].cost = "?"; },
    (state) => { state.player_statuses[0].amount = null; },
    (state) => { state.hand[0].affliction = "Hex"; },
    (state) => { state.hand[0].valid_target_refs = ["PRIVATE_PLAYER"]; },
    (state) => { state.player.potions[0].valid_target_refs = ["PRIVATE_E1"]; },
    (state) => { state.turn_owner = "enemy"; },
    (state) => { state.companions = [{ name: "Unqualified companion" }]; }
  ]) { const state = fixture(); change(state); const { result, ctx } = project(state);
    assert.equal(result.complete, false); assert.equal(ctx.actions.length, 0); }
});
test("disabled cards and potions retain facts without advertising their use", () => {
  const state = fixture(); state.hand[1].can_play = false; state.player.potions[0].can_use = false;
  const { result, ctx } = project(state);
  assert.equal(result.context.player.hand.length, 2);
  assert.equal(ctx.actions.filter((row) => row.raw.action === "play_card").length, 2);
  assert.equal(ctx.actions.some((row) => row.raw.action === "use_potion"), false);
  assert.equal(ctx.actions.some((row) => row.raw.action === "discard_potion"), true);
});

const descriptor = { descriptor: { kind: "combat_piles" }, completeness: { status: "complete", missing: [] } };
const read = (cards) => projectExactCombatReads({ combat_piles: [{ pile: "draw", cards }] }, [descriptor], context(), helpers)[0];
test("changing private draw enumeration and indices cannot change the public multiset", () => {
  const first = handCard("PRIVATE_C1"), second = handCard("PRIVATE_C2", { cost: 0 });
  const a = read([{ ...first, index: 0 }, { ...second, index: 1 }]);
  const b = read([{ ...second, index: 0 }, { ...first, index: 1 }]);
  assert.deepEqual(a, b);
  assert.equal(a.content.zones[0].ordering_semantics, "unordered_multiset");
  assert.equal(a.content.zones[0].cards.length, 2);
  assert.equal(a.content.zones[0].cards.some((row) => "index" in row || "native_ref" in row), false);
});
test("ambiguous or absent card-copy identities make the pile read explicitly partial", () => {
  assert.equal(read([handCard("SAME"), handCard("SAME")]).completeness.status, "partial");
  assert.equal(read([handCard(null)]).completeness.status, "partial");
});
