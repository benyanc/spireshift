import test from "node:test";import assert from "node:assert/strict";
import {PLAN,largeDomain,OrderedAnswerPlanner} from "./engine-ordered-plan-v1.mjs";
import {orderedChoices} from "./engine-atomic-selection-v6.mjs";
const source=(n=6,min=0,max=n,cancelable=false)=>({type:"decision",decision:"card_select",cards:Array.from({length:n},(_,index)=>({index,native_ref:"card-"+index})),min_select:min,max_select:max,cancelable,require_manual_confirmation:true,unpowered_previews:false,pretend_cards_can_be_played:false,selection_preferences_complete:true,selection_ref:"owner-1"});
function request(p,action,index){return {cmd:"action",action:"ordered_answer_"+action,args:{selection_ref:p.active.state.selection_ref,prefix:p.active.selected.join(","),...(index==null?{}:{index})}};}
test("ordered factorial threshold, including the observed six-card any-number answer",()=>{assert.equal(largeDomain(5,0,999999999,false),false);assert.equal(largeDomain(6,0,999999999,false),true);assert.equal(largeDomain(500,0,1,false),false);assert.equal(largeDomain(511,0,1,true),true);assert.throws(()=>largeDomain(6,7,7,false));});
test("all 1957 observed answers are reachable, including each physical ordering and empty answer",()=>{
 const root=source();const found=new Set();
 function visit(prefix){const p=new OrderedAnswerPlanner();p.observe(root);for(const i of prefix){const x=p.handle(request(p,"append",i));assert.equal(x.local,true);assert.equal(x.native,undefined);assert.equal(x.response.answer_plan.contract,PLAN);}
  const done=p.handle(request(p,"commit"));assert.equal(done.local,false);found.add(done.native.args.indices);
  for(let i=0;i<6;i++)if(!prefix.includes(i))visit([...prefix,i]);}
 visit([]);const expected=orderedChoices([0,1,2,3,4,5],0,6,false,2000).map(x=>x.join(","));assert.equal(found.size,1957);assert.deepEqual([...found].sort(),expected.sort());
});
test("large hands use a linear-length plan, no enumeration and one final native command",()=>{const p=new OrderedAnswerPlanner();p.observe(source(100,2,100));for(let i=99;i>=0;i--)assert.equal(p.handle(request(p,"append",i)).local,true);const r=p.handle(request(p,"commit"));assert.equal(r.native.args.indices.split(",").length,100);assert.equal(p.active,null);assert.throws(()=>p.handle({cmd:"action",action:"ordered_answer_commit",args:{}}));});
test("native bounds, stale owner/prefix, duplicate/out-of-range cards, cancellation and source drift fail closed",()=>{
 const p=new OrderedAnswerPlanner();p.observe(source(6,2,6,true));assert.throws(()=>p.handle(request(p,"commit")));assert.throws(()=>p.handle({...request(p,"append",0),args:{selection_ref:"wrong",prefix:"",index:0}}));p.handle(request(p,"append",0));assert.throws(()=>p.handle(request(p,"append",0)));assert.throws(()=>p.handle(request(p,"append",8)));assert.throws(()=>p.observe({...source(6,2,6,true),prompt:"changed"}));const r=p.handle(request(p,"cancel"));assert.equal(r.native.action,"skip_select");assert.equal(r.native.args.selection_ref,"owner-1");
 const q=new OrderedAnswerPlanner();q.observe(source());assert.throws(()=>q.handle(request(q,"cancel")));
});
test("small and generated selectors retain the old source, unrelated reads preserve pending plans",()=>{const p=new OrderedAnswerPlanner(),small=source(5);assert.equal(p.observe(small),small);const s=source();p.observe(s);const metrics={type:"process_metrics"};assert.equal(p.observe(metrics),metrics);assert.ok(p.active);const g={...s,generated_choice_presentation:"native_choose_card_initial_v1"};assert.equal(p.observe(g),g);assert.equal(p.active,null);});
test("native belt operations remain possible at the root and cannot interrupt an answer prefix",()=>{const p=new OrderedAnswerPlanner();p.observe(source());assert.equal(p.handle({cmd:'action',action:'discard_potion'}),null);assert.equal(p.active,null);p.observe(source());p.handle(request(p,'append',0));assert.throws(()=>p.handle({cmd:'action',action:'discard_potion'}));});
import {mkdtempSync,writeFileSync,rmSync} from 'node:fs';import {tmpdir} from 'node:os';import path from 'node:path';import {gzipSync} from 'node:zlib';import {spawnSync} from 'node:child_process';
test('saved verifier rejects a tampered local ledger and a false native delivery count',()=>{
 const dir=mkdtempSync(path.join(tmpdir(),'ordered-answer-test-'));
 try{
  const s=source(),p=new OrderedAnswerPlanner();p.observe(s);const add=request(p,'append',2),a=p.handle(add),commit=request(p,'commit'),b=p.handle(commit);
  const transcript=[{request:{cmd:'enter_room'},response:s},{request:add,response:a.response,transport:'local_selection_ui'},{request:b.native,response:{type:'decision',decision:'combat_play'}}];
  const ledger=[{request:add,...a},{request:commit,...b}];
  const receipts=[0,1].map(index=>({index,snapshot_id:'s'+index,successor_snapshot_id:'s'+(index+1),action:{bound_action_id:'a'+index},delivery:'delivered'}));
  const domains=receipts.map((r,i)=>({index:i,before_snapshot_id:r.snapshot_id,successor_snapshot_id:r.successor_snapshot_id,action_id:r.action.bound_action_id,delivery_domain:i===0?'local_answer_factor':'native'}));
  const save=(name,rows)=>writeFileSync(path.join(dir,name+'.jsonl.gz'),gzipSync(rows.map(x=>JSON.stringify(x)).join('\n')+'\n'));
  save('private-transcript',transcript);save('selection-cursor',ledger);save('public-receipts',receipts);save('answer-plan-deliveries',domains);
  const run=()=>spawnSync(process.execPath,['scripts/engine-ordered-plan-verify-v1.mjs',dir],{encoding:'utf8'});
  assert.equal(run().status,0);ledger[0].before=[5];save('selection-cursor',ledger);assert.notEqual(run().status,0);
  ledger[0].before=[];save('selection-cursor',ledger);domains[0].delivery_domain='native';save('answer-plan-deliveries',domains);assert.notEqual(run().status,0);
 }finally{rmSync(dir,{recursive:true,force:true});}
});
