import assert from "node:assert/strict";
import test from "node:test";
import {projectSelectionFlows as previous} from "./engine-abandon-confirmation-surface-v1.mjs";
import {projectSelectionFlows} from "./engine-combat-selector-belt-v1.mjs";
import {PLAN} from "./engine-ordered-plan-v1.mjs";

const helpers = {
  visibleText: value => value ?? null,
  withoutDeck: ({deck, ...player}) => player,
  cardProperties: card => ({
    definition_id: card.id, name: card.name, type: card.type, rarity: card.rarity,
    cost: String(card.cost), is_upgraded: card.upgraded, description: card.description,
  }),
};

function fixture(target = "AllEnemies") {
  const potion = {native_ref: "bottle", id: "POTION", name: "Potion", description: "Visible.",
    slot: 0, can_use: true, can_discard: true, binding_supported: true, target_type: target,
    usage: "AnyTime", valid_target_refs: target === "AnyEnemy" ? ["enemy-two"] : null};
  const cards = [0, 1].map(index => ({index, native_ref: "card-" + index, id: "DEFEND_IRONCLAD",
    name: "Defend", description: "Gain 5 Block.", type: "Skill", rarity: "Basic",
    cost: 1, upgraded: false, is_selected: false}));
  const player = {native_ref: "player", name: "Ironclad", hp: 40, max_hp: 80,
    block: 0, potions: [potion], deck: []};
  const enemies = ["enemy-one", "enemy-two"].map((native_ref, combat_id) => ({
    native_ref, combat_id, id: "ENEMY", name: native_ref, hp: 30, max_hp: 30,
    block: 0, statuses: [], intents: [], intends_attack: false,
  }));
  const combat = {decision: "combat_play", hand: [], enemies, player: structuredClone(player),
    player_statuses: [], companions: [], orbs: [], orb_slots: 0, stars_visible: false, stars: null,
    energy: 0, max_energy: 3, draw_pile_count: 0, discard_pile_count: 2, exhaust_pile_count: 0,
    round: 2, is_play_phase: false, turn_owner: "player", encounter_type: "normal",
    combat_piles: [{pile: "discard", cards}]};
  return {decision: "card_select", player, context: {floor: 5}, selection_ref: "selector",
    selection_owner: {kind: "combat"}, selection_combat: combat, cards,
    selection_preferences_complete: true, min_select: 1, max_select: 1, cancelable: false,
    require_manual_confirmation: false, unpowered_previews: false, pretend_cards_can_be_played: false};
}

function project(state, projector = projectSelectionFlows) {
  const refs = [], actions = [], ctx = {
    snapshotId: "snapshot", id: (...parts) => parts.join(":"),
    referent(value) {
      const row = {...value, referent_id: value.id, properties: {
        ...value.properties, ...(value.includeEntityId === false ? {} : {entity_id: value.id}),
      }};
      refs.push(row);
      return row;
    },
    action(value) { actions.push(value); },
  };
  return {result: projector(state, ctx, helpers), refs, actions};
}

test("a combat selector offers the exact area potion and both card answers", () => {
  const raw = fixture(), before = structuredClone(raw);
  assert.deepEqual(project(raw, previous).result.missing, ["unsupported_noncombat_potion_target"]);
  const {result, refs, actions} = project(raw);
  assert.deepEqual(raw, before);
  assert.equal(result.complete, true);
  assert.equal(new Set(refs.map(ref => ref.id)).size, refs.length);
  const [slot] = result.surface.potion_states;
  assert.equal(slot.can_use, true);
  assert.equal(slot.target_type, "AllEnemies");
  assert.equal(result.context.player.potion_states[0].entity_id, slot.entity_id);
  assert.equal(actions.filter(a => a.verb === "confirm").length, 2);
  const [use] = actions.filter(a => a.verb === "use");
  const [discard] = actions.filter(a => a.raw.action === "discard_potion");
  assert.equal(use.subject, discard.subject);
  assert.deepEqual(use.raw.args, {potion_slot: 0, potion_ref: "bottle"});
  assert.equal(actions.some(a => ["play_card", "end_turn"].includes(a.raw.action)), false);
});

test("combat geometry binds just the natively valid enemy", () => {
  const raw = fixture("AnyEnemy");
  const {result, actions} = project(raw);
  const [use] = actions.filter(a => a.verb === "use");
  assert.deepEqual(use.raw.args, {potion_slot: 0, potion_ref: "bottle", target_ref: "enemy-two"});
  const [target] = use.arguments;
  assert.equal(target.referent.label, "enemy-two");
  assert.deepEqual(result.surface.potion_states[0].target_entity_ids, [target.referent.id]);
  raw.player.potions[0].valid_target_refs = ["stale"];
  assert.throws(() => project(raw), /differs from its current combat/);
  raw.selection_combat.player.potions[0].valid_target_refs = ["stale"];
  assert.throws(() => project(raw), /Missing exact combat selector potion targets/);
});

test("generated and compact selectors use the same combat belt boundary", () => {
  const generated = fixture("RandomEnemy");
  Object.assign(generated, {decision: "generated_card_choice", can_skip: true, min_select: 0,
    generated_choice_presentation: "native_choose_card_initial_v1", generated_choice_prompt: "Choose",
    generated_choice_is_peeking: false});
  const one = project(generated);
  assert.equal(one.result.complete, true);
  assert.deepEqual(one.actions.map(a => a.verb), ["select", "select", "skip", "activate", "use"]);
  const compact = fixture("AllAllies");
  compact.answer_plan = {contract: PLAN, selected: []};
  assert.equal(project(compact).actions.filter(a => a.verb === "use").length, 1);
  compact.answer_plan.selected = [0];
  assert.deepEqual(project(compact).actions.map(a => a.verb), ["confirm"]);
});

test("disabled use and selectors outside combat retain the original contract", () => {
  const disabled = fixture();
  for (const player of [disabled.player, disabled.selection_combat.player]) {
    player.potions[0].can_use = false;
    player.potions[0].can_discard = false;
  }
  assert.deepEqual(project(disabled), project(disabled, previous));
  const outside = fixture();
  outside.selection_owner.kind = "event";
  delete outside.selection_combat;
  assert.deepEqual(project(outside), project(outside, previous));
  assert.equal(project(outside).result.complete, false);
});
