import test from "node:test";
import assert from "node:assert/strict";
import { projectSelectionFlows } from "./engine-chest-surface-v1.mjs";
import { prepareTreasureSave } from "./engine-chest-fixture-save-v1.mjs";
import { inspectRunInput as currentInspection } from "./engine-run-contract-v7.mjs";
import { inspectRunInput as historicalInspection } from "./engine-run-contract-v6.mjs";
import { fixture } from "./engine-interface-case-bank-v1.mjs";
import { requireChestMenu } from "./engine-chest-contract-v1.mjs";

function source(stage="relic_choice") {
  const decisions={closed:"treasure_chest",relic_choice:"treasure_relic",completed:"treasure_complete"};
  const value={decision:decisions[stage],stage,room_ref:"private-room",context:{act:1,ascension:8},
    chest_opened:stage!=="closed",can_choose:stage==="relic_choice",can_skip:stage==="relic_choice",
    can_proceed:stage==="completed",player:{native_ref:"private-player",potions:[]}};
  if(stage==="relic_choice")value.relics=[{index:0,native_ref:"private-relic",id:"VENERABLE_TEA_SET",
    name:"Venerable Tea Set",description:"Start the next combat with [energy][energy].",rarity:"Common",
    keywords:[{name:"Energy",description:"Energy plays cards."}],card_previews:[],hover_facts_complete:true}];
  return value;
}
function project(raw) {
  const actions=[],refs=[],helpers={withoutDeck:value=>structuredClone(value),visibleText:value=>value,
    cardProperties:value=>({definition_id:value.id,name:value.name,cost:value.cost,description:value.description,
      rarity:value.rarity,type:value.type,is_upgraded:value.is_upgraded,keywords:value.keywords,
      target_type:null,can_play:null,stats:null,after_upgrade:null})};
  const ctx={snapshotId:"snapshot",id:(...parts)=>JSON.stringify(parts),action:row=>actions.push(row),
    referent(value){const row={...value,referent_id:value.id,properties:{...value.properties,entity_id:value.id}};
      refs.push(row);return row;}};
  const surface=projectSelectionFlows(raw,ctx,helpers);
  return {surface,actions,refs};
}
function wire(stage="closed") {
  const x=fixture("rest_site"), p=project(source(stage)), s=x.snapshot;
  s.interaction.kind="treasure_room";s.interaction.stage=stage;
  s.interaction.content={context:{kind:"treasure"},surface:p.surface.surface};
  s.referents=p.refs.map(row=>({...row,state:{visible:true}}));
  s.bound_actions.actions=p.actions.map((row,i)=>({bound_action_id:`chest-${i}`,
    interaction_id:s.interaction.interaction_id,verb:row.verb,label:row.label,
    subject_referent_id:row.subject?.referent_id??null,arguments:[]}));
  s.bound_actions.total_count=s.bound_actions.materialized_count=s.bound_actions.actions.length;
  return x;
}

test("closed chest has the same operand-free Open control as the actual UI",()=>{
  const {surface,actions,refs}=project(source("closed"));
  assert.equal(surface.kind,"treasure_room");
  assert.deepEqual(surface.surface,{kind:"treasure_room",stage:"closed",chest_opened:false,
    relics:[],can_choose:false,can_skip:false,can_proceed:false,potion_states:[]});
  assert.equal(actions.length,1);assert.equal(actions[0].verb,"open");
  assert.equal(actions[0].subject,undefined);assert.equal(refs.length,0);
  assert.deepEqual(actions[0].raw,{cmd:"action",action:"open_treasure",args:{room_ref:"private-room"}});
});
test("Take binds the exact offered relic; Skip binds the current room",()=>{
  const {surface,actions}=project(source());
  assert.deepEqual(actions.map(row=>[row.verb,row.label]),[
    ["activate","Take Venerable Tea Set"],["skip","Skip the visible treasure relic"]]);
  assert.equal(actions[0].subject.role,"relic");assert.equal(actions[1].subject,undefined);
  assert.deepEqual(actions[0].raw.args,{relic_ref:"private-relic"});
  assert.deepEqual(actions[1].raw.args,{room_ref:"private-room"});
  assert.deepEqual(surface.surface.relics[0].keywords,source().relics[0].keywords);
  assert.equal(Object.hasOwn(surface.surface.relics[0],"index"),false);
  assert.equal(Object.hasOwn(surface.surface.relics[0],"native_ref"),false);
});
test("completion preserves the actual Continue-to-map binding",()=>{
  const {surface,actions}=project(source("completed"));
  assert.equal(surface.stage,"completed");assert.equal(surface.surface.can_proceed,true);
  assert.deepEqual(actions,[{verb:"activate",label:"Continue from the treasure room",
    raw:{cmd:"action",action:"leave_room",args:{room_ref:"private-room"}}}]);
});
for(const flag of ["chest_opened","can_choose","can_skip","can_proceed"])
  test(`missing or numeric ${flag} never becomes permission`,()=>{
    for(const invalid of [undefined,0,1,null]) {
      const raw=source();if(invalid===undefined)delete raw[flag];else raw[flag]=invalid;
      assert.throws(()=>project(raw),/permission export/);
    }
  });
test("partial Skip readiness cannot publish a narrowed Take-only policy menu",()=>{
  const raw=source();raw.can_skip=false;
  assert.throws(()=>project(raw),/unsettled/);
});
test("the original incomplete treasure relic export is rejected",()=>{
  const raw=source();delete raw.relics[0].keywords;delete raw.relics[0].card_previews;
  assert.throws(()=>project(raw),/public facts/);
});
test("incomplete hover semantics are never silently reported complete",()=>{
  const raw=source();raw.relics[0].hover_facts_complete=false;
  assert.throws(()=>project(raw),/public facts/);
});
test("unknown public relic and preview facts survive the typed projection",()=>{
  const raw=source();raw.relics[0].new_public_amount=0;
  raw.relics[0].card_previews=[{id:"DEFEND_IRONCLAD",name:"Defend",type:"Skill",cost:"1",star_cost:null,
    description:"Gain 5 Block.",rarity:"Basic",is_upgraded:false,is_selected:false,keywords:null,new_public_flag:false}];
  const {surface,refs}=project(raw), relic=surface.surface.relics[0];
  assert.equal(relic.new_public_amount,0);assert.equal(relic.card_previews[0].new_public_flag,false);
  assert.equal(relic.card_previews[0].definition_id,"DEFEND_IRONCLAD");
  assert.equal(relic.card_previews[0].star_cost,null);
  assert.equal(refs.some(row=>row.role==="card_preview"),true);
});
test("unknown multi-holder domains reject without choosing a first relic",()=>{
  const raw=source();raw.relics.push({...raw.relics[0],index:1,native_ref:"second"});
  assert.throws(()=>project(raw),/single-player treasure holder/);
});
test("visible relic facts outside their current chest phase reject",()=>{
  const raw=source("closed");raw.relics=source().relics;
  assert.throws(()=>project(raw),/current visible phase/);
});
test("fixture creates a fresh native treasure entry without modifying the original save",()=>{
  const original={ascension:8,current_act_index:0,acts:[{saved_map:{start:{coord:{col:3,row:0},type:"ancient"},points:[]}}],
    visited_map_coords:[{col:3,row:0}],pre_finished_room:{room_type:"combat"},map_point_history:[[{}]]};
  const before=structuredClone(original), saved=prepareTreasureSave(original);
  assert.deepEqual(original,before);assert.equal(saved.acts[0].saved_map.start.type,"treasure");
  assert.equal(saved.pre_finished_room,null);assert.deepEqual(saved.map_point_history,[[]]);
  original.ascension=0;assert.throws(()=>prepareTreasureSave(original),/A8 initial-map/);
});
test("the native public envelope accepts only the newly declared chest family",()=>{
  const {snapshot,reads}=wire();
  const runtime=snapshot.session.runtime_instance_id;
  assert.throws(()=>historicalInspection(snapshot,reads,runtime),/Unsupported decision family/);
  assert.equal(currentInspection(snapshot,reads,runtime).terminal,false);
  snapshot.interaction.kind="unknown_chest_owner";
  assert.throws(()=>currentInspection(snapshot,reads,runtime),/Unsupported decision family/);
  snapshot.interaction.kind="treasure_room";
  snapshot.interaction.content.surface.room_ref="private";
  assert.throws(()=>currentInspection(snapshot,reads,runtime),/Private engine field/);
});
for(const stage of ["closed","relic_choice","completed"])
  test(`complete actual ${stage} menu validates without changing public data`,()=>{
    const {snapshot}=wire(stage), before=structuredClone(snapshot);
    requireChestMenu(snapshot);assert.deepEqual(snapshot,before);
  });
for(const change of [
  s=>{s.interaction.content.surface.can_skip=false;},
  s=>{delete s.interaction.content.surface.can_skip;},
  s=>{s.bound_actions.actions.pop();},
  s=>{s.bound_actions.actions[0].subject_referent_id="foreign";},
  s=>{s.bound_actions.actions[0].interaction_id="foreign";},
  s=>{delete s.interaction.content.surface.relics[0].keywords;},
])test("the shared sampler rejects incomplete or foreign chest authority",()=>{
  const {snapshot}=wire("relic_choice");change(snapshot);
  assert.throws(()=>requireChestMenu(snapshot));
});
