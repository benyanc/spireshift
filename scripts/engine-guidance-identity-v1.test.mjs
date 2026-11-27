import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {fixture} from './engine-interface-case-bank-v1.mjs';
import {sharedDecision,deliveredAction} from './engine-shared-input-v11.mjs';
import {restoreLayout} from './engine-input-layout-v8.mjs';
import {stableJson} from './engine-public-input-v1.mjs';
import {finishRewardProceed,verifyRewardCommitTrace} from './engine-reward-commit-v3.mjs';
const clone=structuredClone;
const received=(s,a,delivery='delivered')=>({delivery,action:a,attribution:{runtime_instance_id:s.session.runtime_instance_id}});
function reward(){
 const root=fixture('reward_claim').snapshot;
 root.interaction.content.surface={kind:'reward_claim',rewards:[{entity_id:'gold',label:'Gold',enabled:true}],can_proceed:true,proceed_skips_remaining_rewards:true};
 const action={bound_action_id:'continue',interaction_id:root.interaction.interaction_id,verb:'activate',label:'Skip remaining rewards and continue',subject_referent_id:null,arguments:[]};
 root.bound_actions.actions=[action];root.bound_actions.total_count=root.bound_actions.materialized_count=1;
 const tutorial=clone(root);tutorial.snapshot_id='warning';tutorial.interaction.interaction_id='warning-owner';tutorial.interaction.kind='tutorial';
 tutorial.interaction.content.surface={kind:'tutorial',stage:'confirmation',tutorial_id:'combat_reward_ftue',title:'Rewards',body:'Remember rewards.',options:[{semantic_id:'dismiss_tutorial',label:'Got it!',enabled:true}]};
 tutorial.bound_actions.actions=[{...action,bound_action_id:'dismiss',interaction_id:'warning-owner',label:'Got it!'}];
 const back=clone(root);back.snapshot_id='returned';
 const after=clone(root);after.snapshot_id='map';after.interaction.kind='map_navigation';after.interaction.interaction_id='map-owner';after.bound_actions.actions[0].interaction_id='map-owner';
 return{root,action,tutorial,back,after,receipt:received(root,action)};
}
async function finish(f,initial,sequence,mutate=()=>{}){
 const sent=[];let clock=0;
 const result=await finishRewardProceed(f.root,f.action,f.receipt,initial,{
  deadline:20,now:()=>clock++,observe:async()=>{if(!sequence.length)throw Error('No observed successor');return sequence.shift();},
  send:async(s,a,kind)=>{sent.push(kind);const receipt=received(s,a);mutate(s,a,kind,receipt);return receipt;}
 });
 return{...result,sent};
}
test('one Continue includes the exact warning dismissal and freshly validated confirmation',async()=>{
 const f=reward(),r=await finish(f,f.tutorial,[f.back,f.after]);
 assert.deepEqual(r.sent,['tutorial','confirmation']);assert.equal(r.successor.interaction.kind,'map_navigation');
 assert.equal(r.proof.root_bound_action_id,f.action.bound_action_id);assert.equal(r.proof.ui_steps.length,2);
});
test('a tutorial never counts as final reward departure',()=>{
 const f=reward();assert.throws(()=>verifyRewardCommitTrace(f.root,f.action,f.receipt,[],f.tutorial),/not verified/);
});
test('direct departure needs no extra click and ordinary closing snapshots are only observed',async()=>{
 const f=reward(),r=await finish(f,f.back,[f.after]);assert.deepEqual(r.sent,[]);
 const direct=await finish(f,f.after,[]);assert.deepEqual(direct.sent,[]);
});
test('changed rewards, owner, money or menu cannot receive a confirmation',async()=>{
 for(const mutate of [s=>s.persistent.content.player.gold++,s=>s.interaction.interaction_id='other',s=>s.interaction.content.surface.rewards=[],s=>s.bound_actions.actions[0].label='Different action']){
  const f=reward();mutate(f.back);await assert.rejects(finish(f,f.tutorial,[f.back,f.after]),/changed owner/);
 }
});
test('unknown delivery, repeated warning and unrelated tutorials never authorize another Continue',async()=>{
 let f=reward();await assert.rejects(finish(f,f.tutorial,[f.back,f.after],(s,a,k,r)=>r.delivery='unknown'),/Unverified/);
 f=reward();await assert.rejects(finish(f,f.tutorial,[clone(f.tutorial),f.after]),/Repeated reward warning/);
 f=reward();f.tutorial.interaction.content.surface.tutorial_id='UNKNOWN';await assert.rejects(finish(f,f.tutorial,[f.back,f.after]));
});
function cards(){
 const f=fixture('card_selection');const first=f.snapshot.interaction.content.surface.cards[0],second={...clone(first),entity_id:'second-copy'};
 f.snapshot.interaction.content.surface.cards.push(second);f.snapshot.interaction.content.surface.selection_contract='atomic_public_card_choice_v1';
 f.snapshot.interaction.content.surface.selectable_card_entity_ids.push(second.entity_id);
 f.snapshot.referents.push({...clone(f.snapshot.referents[0]),referent_id:second.entity_id,properties:clone(second)});
 f.reads[0].content.cards.push(clone(second));f.reads[0].content.card_count=2;
 f.snapshot.bound_actions.actions=[first,second].map((c,i)=>({bound_action_id:'choose-'+i,interaction_id:f.snapshot.interaction.interaction_id,verb:'confirm',label:'Confirm Test card',arguments:[{role:'selected_card',referent_id:c.entity_id}]}));
 f.snapshot.bound_actions.total_count=f.snapshot.bound_actions.materialized_count=2;return f;
}
test('unordered read enumeration cannot swap selector identities or collapse equal copies',()=>{
 const a=cards(),b=clone(a);b.reads[0].content.cards.reverse();
 const p=sharedDecision(a.snapshot,a.reads),q=sharedDecision(b.snapshot,b.reads);
 assert.deepEqual(p.public_input,q.public_input);assert.deepEqual(p.actions,q.actions);
 assert.equal(new Set(p.public_input.context.interaction.content.surface.cards.map(c=>c.entity_id.public_slot)).size,2);
 for(let i=0;i<p.actions.length;i++)assert.equal(deliveredAction(p,{binding_id:p.binding_id,action_index:i},a.snapshot).bound_action_id,p.actions[i].bound_action_id);
});
test('different current costs and visible selection order remain meaningful',()=>{
 const a=cards();const id='second-copy';
 a.snapshot.interaction.content.surface.cards.find(c=>c.entity_id===id).cost='0';
 a.snapshot.referents.find(c=>c.referent_id===id).properties.cost='0';a.reads[0].content.cards.find(c=>c.entity_id===id).cost='0';
 const b=clone(a);b.snapshot.interaction.content.surface.cards.reverse();
 assert.notDeepEqual(sharedDecision(a.snapshot,a.reads).public_input,sharedDecision(b.snapshot,b.reads).public_input);
});
test('layout restoration verifies the complete original graph and retains unfamiliar fields',()=>{
 const a=cards();a.snapshot.interaction.content.surface.extra_visible_fact={meaning:'retain',amount:7};
 const before=clone(a);const frame=sharedDecision(a.snapshot,a.reads),original=restoreLayout(frame.layout_evidence);
 assert.equal(createHash('sha256').update(stableJson(original)).digest('hex'),frame.layout_evidence.original_digest);
 assert.deepEqual(frame.public_input.context.interaction.content.surface.extra_visible_fact,{meaning:'retain',amount:7});assert.deepEqual(a,before);
});
