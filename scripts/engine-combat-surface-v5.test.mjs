import assert from "node:assert/strict";
import test from "node:test";
import { projectExactCombatSurface, projectExactCombatReads } from "./engine-combat-surface-v5.mjs";

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
  player_statuses: [power("STRENGTH", 2), power("DEXTERITY", 7)], companions: [], orbs: [], orb_slots: 0, stars_visible: false, stars: null,
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

const orb = (id, passive, evoke) => ({ index: 0, id, name: id, passive, evoke,
  hover_complete: true, hover: [{ name: id, description: `Passive ${passive}, Evoke ${evoke}` }] });
test("foreign orbs preserve queue order, current values and capacity for Ironclad", () => {
  const state = fixture(); state.orb_slots = 2;
  state.orbs = [orb("PLASMA", 1, 2), { ...orb("DARK", 0, 17.5), index: 1 }];
  const first = project(state).result; assert.equal(first.complete, true);
  assert.deepEqual(first.context.player.orbs.map(o => [o.definition_id, o.slot, o.evoke]), [["PLASMA", 0, 2], ["DARK", 1, 17.5]]);
  state.orbs.reverse(); state.orbs.forEach((o, index) => { o.index = index; });
  assert.notDeepEqual(first.context.player.orbs, project(state).result.context.player.orbs);
  state.orb_slots = 1; assert.equal(project(state).result.complete, false);
});
test("stars gained outside Regent and X versus zero star costs survive projection", () => {
  const state = fixture(); state.stars_visible = true; state.stars = 7;
  state.hand[0].star_cost = "X"; state.hand[1].star_cost = 0;
  const { result } = project(state); assert.equal(result.complete, true);
  assert.equal(result.context.player.stars, 7);
  assert.deepEqual(result.context.player.hand.map(c => c.star_cost), ["X", 0]);
  state.stars_visible = false; assert.equal(project(state).result.complete, false);
});
test("companion health, identity, ownership and statuses are visible, without guessing card targets", () => {
  const state = fixture(); state.companions = [{ native_ref: "PET", id: "OSTY", name: "Osty",
    hp: 7, max_hp: 10, block: 2, alive: true, is_osty: true, statuses: [power("STRENGTH", 3)] }];
  state.hand = [handCard("C", { target_type: "Osty", valid_target_refs: null })];
  const { result, ctx } = project(state); assert.equal(result.complete, true);
  assert.equal(result.context.player.companions[0].owner_entity_id, result.context.player.player_entity_id);
  assert.deepEqual(ctx.actions.find(a => a.raw.action === "play_card").raw.args, { card_ref: "C" });
});
test("every native card target is either bound, automatic, explicitly disabled or rejected", () => {
  for (const target_type of ["None", "Self", "AllEnemies", "RandomEnemy", "AnyPlayer", "AllAllies", "Osty"]) {
    const state = fixture(); state.hand = [handCard("C", { target_type, valid_target_refs: null })];
    const { result, ctx } = project(state); assert.equal(result.complete, true, target_type);
    assert.deepEqual(ctx.actions.find(a => a.raw.action === "play_card").raw.args, { card_ref: "C" });
  }
  const state = fixture(); state.hand = [handCard("C", { target_type: "AnyAlly", can_play: false, valid_target_refs: [] })];
  assert.equal(project(state).result.complete, true);
  state.hand[0].can_play = true; assert.equal(project(state).result.complete, false);
  for (const target of ["TargetedNoCreature", "NEW_UNKNOWN_TARGET"]) {
    state.hand[0].target_type = target; assert.equal(project(state).result.complete, false);
  }
});
test("incomplete orb or companion descriptions block actions and collect every missing family", () => {
  const state = fixture(); state.orbs = [orb("DARK", 0, 6)]; state.orbs[0].hover_complete = false;
  state.companions = [{ native_ref: "PET" }]; state.stars_visible = true; state.stars = null;
  const { result, ctx } = project(state);
  assert.equal(result.complete, false); assert.equal(ctx.actions.length, 0);
  for (const name of ["native_visible_orb_facts", "native_visible_companion_facts", "native_visible_star_resource"])
    assert.ok(result.missing.includes(name));
});

test("single-player ally cards keep disabled native facts even when target geometry includes the owner", () => {
  const state = fixture(); state.hand = [handCard("C", { target_type: "AnyAlly", can_play: false,
    unplayable_reason: "NoLivingAllies", valid_target_refs: ["PRIVATE_PLAYER_CREATURE"] })];
  const {result, ctx} = project(state);
  assert.equal(result.complete, true);
  assert.equal(ctx.actions.some(a => a.raw.action === "play_card"), false);
  assert.equal(result.context.player.hand[0].unplayable_reason, "NoLivingAllies");
  assert.equal(JSON.stringify(result).includes("PRIVATE_PLAYER_CREATURE"), false);
  state.hand[0].can_play = true;
  assert.equal(project(state).result.complete, false);
});
test("malformed disabled ally target lists remain errors", () => {
  for (const valid_target_refs of [null, [null], ["DUPLICATE", "DUPLICATE"]]) {
    const state = fixture(); state.hand = [handCard("C", { target_type: "AnyAlly", can_play: false, valid_target_refs })];
    const {result, ctx} = project(state);
    assert.equal(result.complete, false); assert.equal(ctx.actions.length, 0);
  }
});

// The selection/legality distinction is owned by the source view.
test("ordinary combat cards explicitly publish unselected while can_play owns legality",()=>{
  const state=fixture();state.hand[1].can_play=false;
  const {result,ctx}=project(state);
  assert.deepEqual(result.context.player.hand.map(c=>c.is_selected),[false,false]);
  const playable=ctx.referents.find(r=>r.role==="playable_card"),disabled=ctx.referents.find(r=>r.role==="hand");
  assert.equal(playable.selected,null);assert.equal(disabled.selected,false);
  assert.equal(Object.hasOwn(playable,"enabled"),false);assert.equal(Object.hasOwn(disabled,"enabled"),false);
});
test("public combat pile cards publish selected false and keep keyword and modifier data",()=>{
  const card=handCard("PRIVATE_KEYWORD",{keywords:["Exhaust","Retain"]}),result=read([card]);
  assert.equal(result.content.zones[0].cards[0].is_selected,false);
  assert.deepEqual(result.content.zones[0].cards[0].keywords,["Exhaust","Retain"]);
});
test("combat discardable potion views contain exactly the native currently discardable slots",()=>{
  const state=fixture();let result=project(state).result;
  assert.equal(result.surface.discardable_potions.length,1);
  state.player.potions[0].can_discard=false;result=project(state).result;
  assert.deepEqual(result.surface.discardable_potions,[]);
});
