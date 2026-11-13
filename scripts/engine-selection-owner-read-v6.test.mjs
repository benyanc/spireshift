import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {fixture} from './engine-interface-case-bank-v1.mjs';
import {sharedDecision,deliveredAction} from './engine-shared-input-v14.mjs';
import {restoreLayout} from './engine-input-layout-v11.mjs';
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

import {projectAtomicSelection} from './engine-atomic-selection-v5.mjs';
const preview=(amount=1)=>({definition_id:'SPIRAL',name:'Spiral',description:'This card gains Replay '+amount+'.',amount,observation_source:'native_command_enchantment_and_amount'});
function enchantedSelection(){
 const f=cards();f.snapshot.interaction.content.context={kind:'selection',owner_kind:'event',event_id:'WHIRLPOOL',name:'Whirlpool',description:'Exact visible page.'};
 f.snapshot.interaction.content.surface.enchantment=preview();return f;
}
test('event owner body aliases match without losing visible text, amount or enchantment',()=>{
 const a=enchantedSelection(),b=clone(a);
 delete b.snapshot.interaction.content.context.description;b.snapshot.interaction.content.context.body='Exact visible page.';
 b.snapshot.interaction.content.surface.enchantment.observation_source='localized_visible_ui_text+model_identity';
 const first=sharedDecision(a.snapshot,a.reads),second=sharedDecision(b.snapshot,b.reads);
 assert.deepEqual(first.public_input,second.public_input);
 assert.equal(first.public_input.context.interaction.content.context.body,'Exact visible page.');
 assert.equal(first.public_input.context.interaction.content.surface.enchantment.amount,1);
 restoreLayout(first.layout_evidence);restoreLayout(second.layout_evidence);
});
test('conflicting body aliases reject; different enchantments, amounts, descriptions and unknown provenance remain distinct',()=>{
 const a=enchantedSelection(),conflict=clone(a);conflict.snapshot.interaction.content.context.body='Different page';
 assert.throws(()=>sharedDecision(conflict.snapshot,conflict.reads),/Conflicting selected event/);
 for(const [key,value]of Object.entries({definition_id:'SHARP',amount:7,description:'Deal more damage.',observation_source:'unknown-source'})){
  const b=clone(a);b.snapshot.interaction.content.surface.enchantment[key]=value;
  assert.notDeepEqual(sharedDecision(a.snapshot,a.reads).public_input,sharedDecision(b.snapshot,b.reads).public_input);
 }
});
test('source preview propagates through atomic projection, preserves unknown facts, and never invents missing previews',()=>{
 const state={decision:'card_select',selection_preferences_complete:true,selection_ref:'s',cards:[{native_ref:'card',id:'STRIKE',name:'Strike',upgraded:false}],min_select:1,max_select:1,cancelable:false,require_manual_confirmation:false,unpowered_previews:false,pretend_cards_can_be_played:false,selection_owner:{kind:'event'},context:{},player:{deck:[]},prompt:'Choose',enchantment:{...preview(),extra_fact:{count:2}}};
 const ctx={snapshotId:'x',id:(...a)=>a.join('-'),referent:v=>v,action:()=>{}};
 const helpers={cardProperties:c=>({name:c.name}),withoutDeck:()=>({}),visibleText:t=>t};
 const projected=projectAtomicSelection(state,ctx,helpers);assert.deepEqual(projected.surface.enchantment,state.enchantment);
 projected.surface.enchantment.extra_fact.count=8;assert.equal(state.enchantment.extra_fact.count,2);
 delete state.enchantment;assert.equal(projectAtomicSelection(state,ctx,helpers).surface.enchantment,undefined);
 state.enchantment={...preview(),amount:null};assert.throws(()=>projectAtomicSelection(state,ctx,helpers),/Incomplete exact/);
});

import {normalizeLayout} from './engine-input-layout-v11.mjs';
import {projectSelectionFlows} from './engine-selection-flows-v8.mjs';
function relicPreview(){
 const f=fixture('event_option');const card=clone(f.reads[0].content.cards[0]);card.entity_id='relic-preview';
 f.snapshot.persistent.content.player.relics=[{entity_id:'relic',definition_id:'RELIC',name:'Relic',card_previews:[card],counter:2}];
 const {entity_id,definition_id,is_selected,...raw}=card;
 f.snapshot.interaction.content.context.player={relics:[{id:'RELIC',name:'Relic',card_previews:[{...raw,id:definition_id}],counter:2}]};return f;
}
test('owned relic card preview aliases collapse only when every source fact is retained',()=>{
 const a=relicPreview(),b=clone(a);delete b.snapshot.interaction.content.context.player;
 assert.deepEqual(sharedDecision(a.snapshot,a.reads).public_input,sharedDecision(b.snapshot,b.reads).public_input);
 for(const patch of [{cost:'7'},{description:'Different effect'},{unfamiliar:{amount:9}}]){
  const c=clone(a);Object.assign(c.snapshot.interaction.content.context.player.relics[0].card_previews[0],patch);
  assert.notDeepEqual(sharedDecision(c.snapshot,c.reads).public_input,sharedDecision(b.snapshot,b.reads).public_input);
 }
});
function shopGraph(){
 const graph=clone(sharedDecision(fixture('card_selection').snapshot,fixture('card_selection').reads).public_input);
 graph.context.interaction.kind='shop_inventory';graph.context.interaction.content.context={kind:'shop'};graph.context.interaction.content.surface={kind:'shop_inventory'};
 const card=clone(graph.context.reads[0].content.cards[0]);const view=clone(Object.values(card.public_card_views)[0]);
 card.public_card_views={'read:shop_catalog:/cards/*/card':clone(view)};
 graph.context.reads.push({kind:'shop_catalog',content:{cards:[{card:clone(card),price:23}]}});
 const detailed=clone(card);detailed.public_card_views={'read:surface_card:':clone(view)};
 graph.context.reads.push({kind:'surface_card',content:detailed});
 for(const ref of graph.context.referents)if(ref.public_slot===card.entity_id.public_slot)ref.properties.public_card_views={...card.public_card_views,...detailed.public_card_views};
 return graph;
}
test('same-card shop detail is folded into its exact catalog view with reversible source evidence',()=>{
 const a=shopGraph(),b=clone(a);b.context.reads=b.context.reads.filter(r=>r.kind!=='surface_card');
 for(const ref of b.context.referents)if(ref.properties.public_card_views)delete ref.properties.public_card_views['read:surface_card:'];
 const first=normalizeLayout(a),second=normalizeLayout(b);assert.deepEqual(first.public_input,second.public_input);
 assert.deepEqual(restoreLayout(first),a);
 for(const patch of [r=>r.content.cost='7',r=>r.content.public_card_views['read:surface_card:'].description='Different',r=>r.extra={visible:true}]){
  const c=shopGraph();patch(c.context.reads.find(r=>r.kind==='surface_card'));
  assert(normalizeLayout(c).public_input.context.reads.some(r=>r.kind==='surface_card'));
 }
});
function generated(canSkip){
 const state={decision:'generated_card_choice',selection_ref:'s',selection_owner:{kind:'event',event_id:'TEST'},generated_choice_presentation:'native_choose_card_initial_v1',generated_choice_prompt:'Choose a Card',generated_choice_is_peeking:false,can_skip:canSkip,min_select:canSkip?0:1,max_select:1,player:{potions:[],max_potion_slots:2},cards:[0,1].map(i=>({index:i,native_ref:'copy'+i,id:'TEST',name:'Card',cost:'1',type:'Attack',rarity:'Common',is_selected:false,is_upgraded:false,upgraded:false}))};
 const actions=[],ctx={snapshotId:'x',id:(...a)=>a.join('-'),referent:v=>v,action:v=>actions.push(v)};
 const helpers={withoutDeck:()=>({}),visibleText:t=>t,cardProperties:c=>({name:c.name,cost:c.cost,definition_id:c.id})};
 return {state,actions,ctx,helpers};
}
test('generated choice preserves native skip permission, current owner, distinct copies and exact commit bindings',()=>{
 for(const optional of [false,true]){
  const f=generated(optional),p=projectSelectionFlows(f.state,f.ctx,f.helpers);
  assert.equal(f.actions.filter(a=>a.verb==='skip').length,Number(optional));assert.equal(p.context.event_id,'TEST');
  assert.equal(p.surface.cards.length,2);assert.notEqual(p.surface.cards[0].entity_id,p.surface.cards[1].entity_id);
  assert.deepEqual(f.actions.slice(0,2).map(a=>a.raw.args),[{selection_ref:'s',indices:'0'},{selection_ref:'s',indices:'1'}]);
 }
 for(const change of [s=>s.cards[0].is_selected=true,s=>delete s.can_skip,s=>s.generated_choice_is_peeking=true,s=>s.selection_owner.kind='combat']){
  const f=generated(true);change(f.state);assert.throws(()=>projectSelectionFlows(f.state,f.ctx,f.helpers));
 }
});
test('empty potion slots retain prices and sold status without a card-removal label or purchase action',()=>{
 const state={decision:'shop',context:{},room_ref:'r',player:{potions:[],max_potion_slots:2},shop_catalog:{access_state:'inventory_open',cards:[],relics:[],potions:[{native_ref:'slot',inventory_index:11,price:48,stocked:false,visible:false,affordable:true,can_purchase:false,blocked_reason:'sold_out'}],card_removal:null}};
 const refs=[],actions=[],ctx={snapshotId:'s',id:(...a)=>a.join('-'),referent:v=>{refs.push(v);return v;},action:v=>actions.push(v)};
 const result=projectSelectionFlows(state,ctx,{withoutDeck:()=>({}),cardProperties:c=>c});
 const slot=refs.find(r=>r.role==='potion');assert.equal(slot.label,null);assert.equal(slot.properties.visible,false);
 assert.equal(slot.properties.price,48);assert.equal(slot.properties.blocked_reason,'sold_out');
 assert(!actions.some(a=>a.label.includes('Buy')));assert.equal(result.surface.potions[0].stocked,false);
});
