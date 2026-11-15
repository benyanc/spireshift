import assert from "node:assert/strict";
import test from "node:test";
import {combatActionKey,combatBridgeFacts,firstDifference,chooseCombatBridgeAction} from "./engine-combat-bridge-contract-v6.mjs";

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
test("shipped usable-potion operands bind to their actual public entity and slot",()=>{
  const {snapshot}=sample();const key=combatActionKey(snapshot,snapshot.bound_actions.actions[1]);
  assert.deepEqual(key.subject,{role:"potion",definition_id:"SPEED_POTION",slot:1});
  assert.deepEqual(key.arguments,[{role:"target",target:{role:"player"}}]);
});
test("wrong potion entity or stale target is refused",()=>{
  const {snapshot}=sample();snapshot.referents[2].properties.entity_id="stale";
  assert.throws(()=>combatActionKey(snapshot,snapshot.bound_actions.actions[1]),/Unqualified/);
});
test("only whitespace is equivalent; swapped stats, changed costs, counter or effect amounts differ",()=>{
  const a=sample(),b=sample();b.snapshot.interaction.content.context.player.hand[0].description="Deal\n13 damage.";
  assert.equal(firstDifference(combatBridgeFacts(a.snapshot,a.deckRead),combatBridgeFacts(b.snapshot,b.deckRead)),null);
  for(const change of [
    s=>{s.interaction.content.context.player.hand[0].cost="0";},
    s=>{s.interaction.content.context.player.hand[0].description="Deal 12 damage.";},
    s=>{s.interaction.content.context.player.statuses[0].amount=5;s.interaction.content.context.player.statuses[1].amount=7;},
    s=>{s.persistent.content.player.relics[0].counter=2;}
  ]) {const c=sample();change(c.snapshot);assert.ok(firstDifference(combatBridgeFacts(a.snapshot,a.deckRead),combatBridgeFacts(c.snapshot,c.deckRead)));}
});
test("missing effect information and a deck read from another snapshot are refused",()=>{
  const a=sample();delete a.snapshot.interaction.content.context.player.statuses[0].amount;
  assert.throws(()=>combatBridgeFacts(a.snapshot,a.deckRead),/Missing/);
  const b=sample();b.deckRead.observed_snapshot_id="old";assert.throws(()=>combatBridgeFacts(b.snapshot,b.deckRead),/Complete public/);
});
test("an unavailable declared operation never falls back to another action",()=>{
  const {snapshot}=sample();assert.throws(()=>chooseCombatBridgeAction(snapshot,{operation:{verb:"play",id:"CORRUPTION"}}),/does not offer/);
});
