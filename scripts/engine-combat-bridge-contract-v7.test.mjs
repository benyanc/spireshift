import assert from "node:assert/strict";
import test from "node:test";
import {combatActionKey,combatBridgeFacts,firstDifference,chooseCombatBridgeAction} from "./engine-combat-bridge-contract-v7.mjs";
function sample() {
  const hand=[{entity_id:"c",definition_id:"STRIKE_IRONCLAD",cost:"1",is_upgraded:false,can_play:true,target_type:"AnyEnemy",description:"Deal 13 damage."}];
  const enemies=[{entity_id:"e",definition_id:"BEETLE",hp:30,max_hp:30,block:0,statuses:[],intents:[]}];
  const actions=[{bound_action_id:"a",interaction_id:"i",verb:"play",subject_referent_id:"c-ref",arguments:[{role:"target",referent_id:"e-ref"}]},
    {bound_action_id:"b",interaction_id:"i",verb:"use",subject_referent_id:"p-ref",arguments:[{role:"target",referent_id:"player-ref"}]}];
  const snapshot={status:"interactive",session:{runtime_instance_id:"r"},completeness:{status:"complete"},information_policy:{includes_hidden_information:false},
    bound_actions:{status:"complete",actions,total_count:2,materialized_count:2},interaction:{kind:"combat_turn",interaction_id:"i",content:{surface:{},context:{kind:"combat",round:1,turn_owner:"player",is_play_phase:true,
      player:{player_entity_id:"player",hand,block:0,energy:3,max_energy:3,draw_pile_count:0,discard_pile_count:0,exhaust_pile_count:0,
        statuses:[{definition_id:"STRENGTH_POWER",amount:7,type:"Buff",description:"Strength adds damage."},{definition_id:"DEXTERITY_POWER",amount:5,type:"Buff",description:"Dexterity adds Block."}]},enemies}}},
    referents:[{referent_id:"c-ref",properties:hand[0]},{referent_id:"e-ref",properties:enemies[0]},
      {referent_id:"p-ref",role:"usable_potion",properties:{entity_id:"p"}},{referent_id:"player-ref",role:"player",properties:{player_entity_id:"player"}}],
    snapshot_id:"s",persistent:{content:{run:{act:1,act_definition_id:"UNDERDOCKS",floor:2,ascension:8},player:{character_definition_id:"IRONCLAD",hp:64,max_hp:80,gold:99,max_potion_slots:2,
      relics:[{definition_id:"PEN_NIB",counter:1,description:"Every 10th Attack deals double damage."}],potions:[{entity_id:"p",definition_id:"SPEED_POTION",slot:1,description:"Gain 5 Dexterity."}]}}}};
  const deckRead={kind:"run_deck",expected_snapshot_id:"s",observed_snapshot_id:"s",completeness:{status:"complete"},information_policy:{includes_hidden_information:false},ordering_semantics:"unordered_multiset",content:{kind:"run_deck",card_count:1,cards:hand}};
  return {snapshot,deckRead};
}

function duplicates() {
  const {snapshot,deckRead}=sample();
  snapshot.persistent.content.player.potions=[
    {entity_id:"stored-0",definition_id:"STRENGTH_POTION",slot:0,description:"Gain 2 Strength."},
    {entity_id:"stored-1",definition_id:"STRENGTH_POTION",slot:1,description:"Gain 2 Strength."}];
  snapshot.referents[2]={referent_id:"p-ref",role:"potion",properties:{entity_id:"combat-0",definition_id:"STRENGTH_POTION",name:"Strength Potion",slot:0,can_discard:true}};
  snapshot.referents.push({referent_id:"p1-ref",role:"potion",properties:{entity_id:"combat-1",definition_id:"STRENGTH_POTION",name:"Strength Potion",slot:1,can_discard:true}});
  snapshot.bound_actions.actions=[
    {bound_action_id:"d0",interaction_id:"i",verb:"activate",subject_referent_id:"p-ref",arguments:[],label:"Discard Strength Potion"},
    {bound_action_id:"d1",interaction_id:"i",verb:"activate",subject_referent_id:"p1-ref",arguments:[],label:"Discard Strength Potion"},
    {bound_action_id:"u1",interaction_id:"i",verb:"use",subject_referent_id:"p1-ref",arguments:[{role:"target",referent_id:"player-ref"}],label:"Use Strength Potion"}];
  snapshot.bound_actions.total_count=3;snapshot.bound_actions.materialized_count=3;
  return {snapshot,deckRead};
}
test("identical native definitions retain exact slots without a name-based fallback",()=>{
  const {snapshot}=duplicates();const keys=snapshot.bound_actions.actions.map(a=>combatActionKey(snapshot,a));
  assert.deepEqual(keys.slice(0,2).map(k=>k.subject.slot),[0,1]);
  assert.equal(keys[2].subject.slot,1);assert.equal(keys[0].verb,"discard");
  assert.equal(chooseCombatBridgeAction(snapshot,{operation:{verb:"use",slot:1}}).bound_action_id,"u1");
});
test("missing slot cannot disambiguate duplicate native potion definitions",()=>{
  const {snapshot}=duplicates();delete snapshot.referents[2].properties.slot;
  assert.throws(()=>combatActionKey(snapshot,snapshot.bound_actions.actions[0]),/Unqualified/);
});
test("a removed slot cannot bind to its identical neighbour",()=>{
  const {snapshot}=duplicates();snapshot.persistent.content.player.potions.shift();
  assert.throws(()=>combatActionKey(snapshot,snapshot.bound_actions.actions[0]),/Unqualified/);
});
test("shared shipped use/discard referents bind by current surface membership and entity",()=>{
  const {snapshot}=duplicates();snapshot.referents[2]={referent_id:"p-ref",role:"usable_potion",properties:{entity_id:"stored-0"}};
  snapshot.interaction.content.surface.discardable_potions=[{entity_id:"stored-0",slot:0,name:"Strength Potion"}];
  snapshot.bound_actions.actions[0].label="Discard Strength Potion from slot 1";
  assert.equal(combatActionKey(snapshot,snapshot.bound_actions.actions[0]).subject.slot,0);
  snapshot.interaction.content.surface.discardable_potions=[];
  assert.throws(()=>combatActionKey(snapshot,snapshot.bound_actions.actions[0]),/Unknown/);
});
test("full combat menu retains both discard choices, and refuses unknown activations",()=>{
  const {snapshot,deckRead}=duplicates();const facts=combatBridgeFacts(snapshot,deckRead);
  assert.equal(facts.actions.filter(a=>a.verb==="discard").length,2);
  snapshot.bound_actions.actions[0].label="Preview Strength Potion";
  assert.throws(()=>combatBridgeFacts(snapshot,deckRead),/Unknown/);
});
