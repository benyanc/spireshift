import assert from "node:assert/strict";
import test from "node:test";
import { prepareRewardSave, visibleReward, rewardFacts, rewardActionKey, chooseRewardAction,
  nextRewardIntent, verifyRewardEffects } from "./engine-reward-bridge-contract-v1.mjs";
import { observation as shopObservation } from "./engine-shop-test-fixtures.mjs";

function observation(full=false, labels=["Synthetic Potion","Synthetic Potion"]) {
  const id="snapshot", potions=full?[{definition_id:"POTION_A",slot:0},{definition_id:"POTION_B",slot:1}]:[];
  const referents=[], actions=[], rewards=labels.map((label,index)=>({entity_id:`reward-${index}`,
    kind:"potion",label,description:"Synthetic visible effect",enabled:!full}));
  for(const reward of rewards) {
    referents.push({referent_id:reward.entity_id,role:"reward",properties:reward});
    if(reward.enabled) actions.push({bound_action_id:`claim-${reward.entity_id}`,verb:"activate",label:`Claim ${reward.label}`,
      subject_referent_id:reward.entity_id,arguments:[]});
  }
  const discardable=potions.map(row=>({...row,entity_id:`potion-${row.slot}`}));
  for(const potion of discardable) {
    referents.push({referent_id:potion.entity_id,role:"potion",properties:potion});
    actions.push({bound_action_id:`discard-${potion.slot}`,verb:"activate",subject_referent_id:potion.entity_id,arguments:[]});
  }
  actions.push({bound_action_id:"skip",verb:"skip",label:"Skip remaining rewards",subject_referent_id:null,arguments:[]});
  return {snapshot:{snapshot_id:id,status:"interactive",session:{runtime_instance_id:"runtime"},
    information_policy:{includes_hidden_information:false},completeness:{status:"complete"},
    interaction:{kind:"reward_claim",content:{surface:{rewards,potion_slots_full:full,discardable_potions:discardable}}},
    bound_actions:{status:"complete",actions,total_count:actions.length,materialized_count:actions.length},referents,
    persistent:{content:{run:{act:1,act_definition_id:"SYNTHETIC_ACT",floor:1,ascension:8},
      player:{character_definition_id:"IRONCLAD",hp:64,max_hp:80,gold:1000,max_potion_slots:2,relics:[],potions}}}},
    deckRead:{kind:"run_deck",expected_snapshot_id:id,observed_snapshot_id:id,completeness:{status:"complete"},
      information_policy:{includes_hidden_information:false},ordering_semantics:"unordered_multiset",
      content:{kind:"run_deck",card_count:0,cards:[]}}};
}
test("identical visible reward occurrences keep multiplicity and fresh action bindings",()=>{
  const {snapshot,deckRead}=observation(), facts=rewardFacts(snapshot,deckRead);
  assert.equal(facts.rewards.length,2); assert.equal(facts.actions.filter(row=>row.kind==="claim").length,2);
  const chosen=chooseRewardAction(snapshot,facts.actions.find(row=>row.kind==="claim"));
  assert.equal(chosen.bound_action_id,"claim-reward-0");
  snapshot.bound_actions.actions.splice(0,1); snapshot.bound_actions.total_count--; snapshot.bound_actions.materialized_count--;
  assert.throws(()=>rewardFacts(snapshot,deckRead),/every enabled reward occurrence/);
});
test("full A8 belt offers exact occupied-slot discard and skip, with zero potion claims",()=>{
  const {snapshot,deckRead}=observation(true), facts=rewardFacts(snapshot,deckRead);
  assert.equal(facts.actions.filter(row=>row.kind==="claim").length,0);
  const wanted=nextRewardIntent(snapshot,"cauldron-fill-replace-skip",{claims:2,discards:0});
  assert.deepEqual(wanted,{kind:"discard",potion:{definition_id:"POTION_A",slot:0}});
  assert.equal(chooseRewardAction(snapshot,wanted).bound_action_id,"discard-0");
  assert.equal(nextRewardIntent(snapshot,"cauldron-fill-skip",{claims:2,discards:0}).kind,"skip");
  snapshot.referents.filter(row=>row.role==="potion").forEach(row=>{row.role="discardable_potion";});
  assert.equal(chooseRewardAction(snapshot,wanted).bound_action_id,"discard-0");
});
test("capacity facts cannot silently disagree or enable a blocked reward",()=>{
  for(const change of [(row)=>{row.interaction.content.surface.potion_slots_full=false;},
    (row)=>{row.persistent.content.player.potions[1].slot=0;},
    (row)=>{row.interaction.content.surface.rewards[0].enabled=true;}]) {
    const {snapshot,deckRead}=observation(true); change(snapshot); assert.throws(()=>rewardFacts(snapshot,deckRead));
  }
});
test("an old/replaced reward or potion referent cannot be used as a current operand",()=>{
  const {snapshot}=observation(); const action=structuredClone(snapshot.bound_actions.actions[0]);
  snapshot.referents[0].properties={...snapshot.referents[0].properties,entity_id:"replacement"};
  assert.throws(()=>rewardActionKey(snapshot,action),/stale or disabled/);
  const full=observation(true).snapshot; full.interaction.content.surface.discardable_potions.shift();
  assert.throws(()=>rewardActionKey(full,full.bound_actions.actions[0]),/current full-belt/);
});
test("unknown reward kinds, partial descriptions, impossible skip controls and missing choices refuse execution",()=>{
  assert.throws(()=>visibleReward({kind:"unknown",label:"A",description:"B",enabled:true}));
  assert.throws(()=>visibleReward({kind:"potion",label:"A",enabled:true}));
  const snapshot=observation().snapshot;
  assert.throws(()=>rewardActionKey(snapshot,{verb:"activate",label:"Continue",arguments:[],subject_referent_id:null}));
  assert.throws(()=>chooseRewardAction(snapshot,{kind:"discard",potion:{definition_id:"MISSING",slot:0}}));
});
test("serialized Darv fixture changes only declared room/history fields and never mutates the source save",()=>{
  const original={ascension:8,current_act_index:0,acts:[{rooms:{ancient_id:"EVENT.NEOW"},saved_map:{
    start:{coord:{row:0,col:0},type:"ancient"},points:[{coord:{row:0,col:0},type:"ancient"}]}}],
    visited_map_coords:[{row:0,col:0}],pre_finished_room:{private:"original"},map_point_history:[[1]],
    rng:{private_seed:"synthetic"},players:[{gold:1000}]};
  const before=structuredClone(original), changed=prepareRewardSave(original,"calling-bell-claim-all");
  assert.deepEqual(original,before); assert.equal(changed.acts[0].rooms.ancient_id,"EVENT.DARV");
  assert.deepEqual(changed.rng,original.rng); assert.deepEqual(changed.players,original.players);
  assert.deepEqual(changed.acts[0].saved_map,original.acts[0].saved_map);
  assert.equal(prepareRewardSave(original,"cauldron-fill-skip").acts[0].saved_map.start.type,"shop");
  assert.throws(()=>prepareRewardSave({...original,ascension:0},"cauldron-fill-skip"));
  assert.throws(()=>prepareRewardSave(original,"unknown"));
});
test("whole pickup verification requires the actual curse, capacity and owner handoff",()=>{
  assert.throws(()=>verifyRewardEffects("calling-bell-claim-all",[]),/Incomplete/);
  const initial={kind:"event_option",run:{ascension:8,floor:1},player:{deck:[],relics:[]}};
  const offered={kind:"reward_claim",run:initial.run,rewards:[1,2,3],player:{deck:[],relics:[{definition_id:"CALLING_BELL"}]}};
  assert.throws(()=>verifyRewardEffects("calling-bell-claim-all",[{facts:initial},{facts:offered},{facts:initial}]),/exactly one curse/);
});
test("native flat shop_relic and shipped nested relic referents bind the same current priced purchase",()=>{
  const inventory={cards:[],potions:[],relics:[{entity_id:"offer",definition_id:"CAULDRON",price:182,
    is_stocked:true,can_purchase:true}],card_removal:{entity_id:"service",price:100,is_stocked:true,can_purchase:true}};
  for(const shipped of [false,true]) {
    const {snapshot}=shopObservation("shop_inventory",shipped,"shop",inventory);
    const ref=snapshot.referents[0]; ref.role=shipped?"relic":"shop_relic";
    if(shipped) {
      ref.properties.relic={definition_id:"CAULDRON"}; delete ref.properties.definition_id;
      snapshot.interaction.content.surface.relics[0].relic={definition_id:"CAULDRON"};
      delete snapshot.interaction.content.surface.relics[0].definition_id;
    }
    const action=chooseRewardAction(snapshot,{kind:"purchase_cauldron"});
    const key=rewardActionKey(snapshot,action);
    assert.equal(key.offer.item.definition_id,"CAULDRON"); assert.equal(key.offer.price,182);
    snapshot.interaction.content.surface.relics[0].can_purchase=false;
    assert.throws(()=>chooseRewardAction(snapshot,{kind:"purchase_cauldron"}));
  }
});
