import test from "node:test";
import assert from "node:assert/strict";
import {projectSelectionFlows} from "./engine-reward-belt-surface-v1.mjs";
const potion=(slot,overrides={})=>({slot,native_ref:`p${slot}`,id:"FIRE_POTION",name:`Potion ${slot}`,
  description:"Deal 20 damage.",can_use:false,can_discard:true,binding_supported:true,
  usage:"CombatOnly",target_type:"AnyEnemy",valid_target_refs:[],...overrides});
function setup(){
  const refs=[],actions=[];const ctx={snapshotId:"saved",id:(...p)=>p.join("/"),
    referent(value){const r={...value,referent_id:value.id,properties:{...value.properties,entity_id:value.id}};refs.push(r);return r;},
    action:a=>actions.push(a)};
  const helpers={cardProperties:p=>({definition_id:p.id}),visibleText:s=>s};
  const state={type:"decision",decision:"reward_set",potion_slots_full:true,can_skip:true,is_terminal:false,can_proceed:false,
    player:{native_ref:"player",name:"Ironclad",hp:50,max_hp:80,max_potion_slots:2,potions:[potion(0),potion(1)]},
    rewards:[{index:0,native_ref:"reward",kind:"potion",name:"New potion",description:"A potion"}]};
  return {state,ctx,helpers,refs,actions};
}
test("full reward belt has one referent and exact discard operand per owned potion",()=>{
  const x=setup(),out=projectSelectionFlows(x.state,x.ctx,x.helpers);
  assert.equal(out.complete,true);assert.equal(new Set(x.refs.map(r=>r.referent_id)).size,x.refs.length);
  const owned=x.refs.filter(r=>r.role==="potion");assert.equal(owned.length,2);
  assert.equal(x.actions.filter(a=>a.raw.action==="discard_potion").length,2);
  assert.equal(x.actions.some(a=>a.raw.action==="select_reward"),false);
  for(const action of x.actions.filter(a=>a.raw.action==="discard_potion")){
    const i=action.raw.args.potion_slot;assert.equal(action.raw.args.potion_ref,`p${i}`);
    assert.equal(action.subject.properties.entity_id,`potion/saved/p${i}/${i}`);
  }
});
test("locked discards stay unavailable; use targets retain native player ownership",()=>{
  const x=setup();x.state.player.potions[0]=potion(0,{can_discard:false});
  x.state.player.potions[1]=potion(1,{can_use:true,usage:"AnyTime",target_type:"AnyPlayer",valid_target_refs:["player"]});
  projectSelectionFlows(x.state,x.ctx,x.helpers);
  assert.equal(x.actions.filter(a=>a.raw.action==="discard_potion").length,1);
  const use=x.actions.find(a=>a.raw.action==="use_potion");assert.equal(use.raw.args.target_ref,"player");
  assert.equal(use.arguments[0].referent.properties.entity_id,"player/saved/player");
});
test("mixed rewards preserve claims, skip and native terminal proceed",()=>{
  const x=setup();x.state.rewards.push({index:1,native_ref:"gold",kind:"gold",name:"10 Gold",description:"10 Gold"});
  projectSelectionFlows(x.state,x.ctx,x.helpers);
  assert.deepEqual(x.actions.find(a=>a.raw.action==="select_reward").raw.args,{reward_ref:"gold"});
  assert.ok(x.actions.some(a=>a.raw.action==="skip_rewards"));
  const y=setup();Object.assign(y.state,{is_terminal:true,can_proceed:true,room_ref:"room"});
  projectSelectionFlows(y.state,y.ctx,y.helpers);
  assert.deepEqual(y.actions.find(a=>a.raw.action==="proceed").raw.args,{room_ref:"room"});
});
test("ambiguous native identities or inconsistent full-belt facts fail closed",()=>{
  const x=setup();x.state.player.potions.pop();assert.throws(()=>projectSelectionFlows(x.state,x.ctx,x.helpers));
  const y=setup();y.state.rewards[0].native_ref=null;assert.throws(()=>projectSelectionFlows(y.state,y.ctx,y.helpers));
});
