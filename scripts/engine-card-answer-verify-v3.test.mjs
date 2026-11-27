import test from "node:test";
import assert from "node:assert/strict";
import {mkdtempSync,writeFileSync,rmSync} from "node:fs";
import {tmpdir} from "node:os";
import path from "node:path";
import {gzipSync} from "node:zlib";
import {ExecutableCardAnswerPlanner} from "./engine-executable-card-answer-v1.mjs";
import {verifyCardAnswers} from "./engine-card-answer-verify-v3.mjs";

function source(count=10,enchant=true,min=0,cancelable=false) {
  return {type:"decision",decision:"card_select",selection_ref:"owner",selection_owner:{kind:"shop"},
    cards:Array.from({length:count},(_,index)=>({index,native_ref:`physical-${index}`,upgraded:false})),
    min_select:min,max_select:3,cancelable,require_manual_confirmation:true,unpowered_previews:false,
    pretend_cards_can_be_played:false,selection_preferences_complete:true,
    ...(enchant?{enchantment:{definition_id:"SHARP",observation_source:"native_command_enchantment_and_amount"}}:{})};
}
function bindings(local) {
  const receipts=Array.from({length:local+1},(_,index)=>({index,snapshot_id:`s${index}`,
    successor_snapshot_id:`s${index+1}`,action:{bound_action_id:`a${index}`},delivery:"delivered"}));
  return {"public-receipts":receipts,"answer-plan-deliveries":receipts.map((r,i)=>({index:i,
    before_snapshot_id:r.snapshot_id,successor_snapshot_id:r.successor_snapshot_id,
    action_id:r.action.bound_action_id,delivery_domain:i<local?"local_answer_factor":"native"}))};
}
function ordinary(direct=false) {
  return {...bindings(0),"private-transcript":[
    {request:{cmd:"get_state"},response:direct?source(3):{type:"decision",decision:"combat_play"}},
    {request:{cmd:"action",action:direct?"select_cards":"end_turn",args:direct?
      {selection_ref:"owner",indices:"2,1"}:{}},response:{type:"game_over",victory:false}}]};
}
function ordered({enchant=true,min=0,selected=[2,9,7],cancel=false}={}) {
  const state=source(10,enchant,min,cancel),planner=new ExecutableCardAnswerPlanner();
  planner.observe(state);
  const transcript=[{request:{cmd:"get_state"},response:state}],cursor=[];
  for(const index of selected) {
    const request={cmd:"action",action:"ordered_answer_append",
      args:{selection_ref:"owner",prefix:planner.active.selected.join(","),index}};
    const result=planner.handle(request);cursor.push({request,...result});
    transcript.push({request,response:result.response,transport:"local_selection_ui"});
  }
  const request={cmd:"action",action:cancel?"ordered_answer_cancel":"ordered_answer_commit",
    args:{selection_ref:"owner",prefix:planner.active.selected.join(",")}};
  const result=planner.handle(request);cursor.push({request,...result});
  transcript.push({request:result.native,response:{type:"game_over",victory:false}});
  return {...bindings(selected.length),"private-transcript":transcript,"selection-cursor":cursor};
}
async function check(data) {
  const folder=mkdtempSync(path.join(tmpdir(),"optional-answer-ledger-"));
  try {
    for(const [name,rows] of Object.entries(data)) writeFileSync(path.join(folder,`${name}.jsonl.gz`),
      gzipSync(rows.map(r=>JSON.stringify(r)+"\n").join("")));
    return await verifyCardAnswers(folder);
  } finally {rmSync(folder,{recursive:true,force:true});}
}

test("normal games and small direct selectors accept absent or empty unused cursor files",async()=>{
  for(const direct of [false,true]) for(const present of [false,true]) {
    const data=ordinary(direct);if(present)data["selection-cursor"]=[];
    const proof=await check(data);assert.equal(proof.local_factors,0);
    assert.equal(proof.native_deliveries,1);assert.equal(proof.selection_cursor_present,present);
  }
});
test("enchant correction, ordinary empty answers, higher minima and cancellation still reconstruct",async()=>{
  for(const options of [{},{enchant:false,selected:[]},{min:2,selected:[8,1]},
    {enchant:false,selected:[4],cancel:true}]) {
    const proof=await check(ordered(options));assert.equal(proof.native_deliveries,1);
    assert.equal(proof.ordered_answer_native_commits,1);assert.equal(proof.selection_cursor_present,true);
  }
});
test("an absent cursor cannot conceal raw factors, native ordered commits or public local deliveries",async()=>{
  for(const data of [ordered(),ordered({enchant:false,selected:[]})]) {
    delete data["selection-cursor"];await assert.rejects(check(data),/ledger/u);
  }
  const falseDomain=ordinary();falseDomain["answer-plan-deliveries"][0].delivery_domain="local_answer_factor";
  await assert.rejects(check(falseDomain),/Local factors/u);
});
test("changed prefixes, physical order, successors, counts, extra records and missing mandatory inputs reject",async()=>{
  for(const change of [
    d=>{d["private-transcript"][1].response.min_select=0;},
    d=>{d["private-transcript"].at(-1).request.args.indices="2,7,9";},
    d=>{d["selection-cursor"][0].after=[8];},
    d=>{d["selection-cursor"].at(-1).after=[2];},
    d=>{d["answer-plan-deliveries"][0].successor_snapshot_id="wrong";},
    d=>{d["answer-plan-deliveries"][0].delivery_domain="native";},
    d=>{d["selection-cursor"].push(d["selection-cursor"][0]);},
    d=>{delete d["public-receipts"];},
    d=>{delete d["answer-plan-deliveries"];},
  ]) {const data=structuredClone(ordered());change(data);await assert.rejects(check(data));}
});
