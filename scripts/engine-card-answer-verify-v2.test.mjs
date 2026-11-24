import test from "node:test";
import assert from "node:assert/strict";
import {mkdtempSync,writeFileSync,rmSync} from "node:fs";
import {tmpdir} from "node:os";
import path from "node:path";
import {gzipSync} from "node:zlib";
import {ExecutableCardAnswerPlanner} from "./engine-executable-card-answer-v1.mjs";
import {verifyCardAnswers} from "./engine-card-answer-verify-v2.mjs";

function source({min=0,cancelable=false,enchant=true,count=10}={}) {
  return {type:"decision",decision:"card_select",selection_ref:"owner",selection_owner:{kind:"shop"},
    cards:Array.from({length:count},(_,index)=>({index,native_ref:`physical-${index}`,upgraded:false})),
    min_select:min,max_select:3,cancelable,require_manual_confirmation:true,unpowered_previews:false,
    pretend_cards_can_be_played:false,selection_preferences_complete:true,
    ...(enchant?{enchantment:{definition_id:"SHARP",observation_source:"native_command_enchantment_and_amount"}}:{})};
}

function evidence(state,selected=[2,9,7],cancel=false) {
  const planner=new ExecutableCardAnswerPlanner();planner.observe(state);
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
  transcript.push({request:result.native,response:{type:"decision",decision:"shop_inventory"}});
  const receipts=Array.from({length:selected.length+1},(_,index)=>({index,snapshot_id:`s${index}`,
    successor_snapshot_id:`s${index+1}`,action:{bound_action_id:`a${index}`},delivery:"delivered"}));
  const domains=receipts.map((r,i)=>({index:i,before_snapshot_id:r.snapshot_id,
    successor_snapshot_id:r.successor_snapshot_id,action_id:r.action.bound_action_id,
    delivery_domain:i<selected.length?"local_answer_factor":"native"}));
  return {"private-transcript":transcript,"selection-cursor":cursor,
    "public-receipts":receipts,"answer-plan-deliveries":domains};
}

async function check(data) {
  const folder=mkdtempSync(path.join(tmpdir(),"executable-answer-proof-"));
  try {
    for(const [name,rows] of Object.entries(data))
      writeFileSync(path.join(folder,`${name}.jsonl.gz`),gzipSync(rows.map(r=>JSON.stringify(r)+"\n").join("")));
    return await verifyCardAnswers(folder);
  } finally {rmSync(folder,{recursive:true,force:true});}
}

test("qualified enchant correction reconstructs every factor and its one native answer",async()=>{
  const data=evidence(source()),proof=await check(data);
  assert.equal(proof.local_factors,3);assert.equal(proof.native_deliveries,1);
  assert.equal(proof.ordered_answer_native_commits,1);
  assert.equal(data["private-transcript"][0].response.min_select,0);
  assert.equal(data["selection-cursor"][0].response.min_select,1);
});

test("ordinary zero answers, higher minima and cancellation keep their native domains",async()=>{
  for(const [state,selected,cancel] of [
    [source({enchant:false}),[],false],
    [source({min:2}),[8,1],false],
    [source({enchant:false,cancelable:true}),[4],true],
  ]) assert.equal((await check(evidence(state,selected,cancel))).native_deliveries,1);
});

test("small direct selectors need no local ledger or factorial enumeration",async()=>{
  const data={"private-transcript":[{request:{cmd:"get_state"},response:source({count:3})},
    {request:{cmd:"action",action:"select_cards",args:{selection_ref:"owner",indices:"2,1"}},
      response:{type:"decision",decision:"shop_inventory"}}],"selection-cursor":[],
    "public-receipts":[{index:0,snapshot_id:"s0",successor_snapshot_id:"s1",action:{bound_action_id:"a0"},delivery:"delivered"}],
    "answer-plan-deliveries":[{index:0,before_snapshot_id:"s0",successor_snapshot_id:"s1",action_id:"a0",delivery_domain:"native"}]};
  const proof=await check(data);assert.equal(proof.local_factors,0);assert.equal(proof.native_deliveries,1);
});

test("wrong minima, physical order, ledger, successor and delivery domain still fail closed",async()=>{
  for(const change of [
    d=>{d["private-transcript"][1].response.min_select=0;},
    d=>{d["private-transcript"].at(-1).request.args.indices="2,7,9";},
    d=>{d["selection-cursor"][0].after=[8];},
    d=>{d["selection-cursor"].at(-1).after=[2];},
    d=>{d["answer-plan-deliveries"][0].successor_snapshot_id="wrong";},
    d=>{d["answer-plan-deliveries"][0].delivery_domain="native";},
    d=>{d["selection-cursor"].push(d["selection-cursor"][0]);},
  ]) {const data=structuredClone(evidence(source()));change(data);await assert.rejects(check(data));}
});
