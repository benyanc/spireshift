import test from 'node:test';import assert from 'node:assert/strict';
import {projectSelectionFlows,selectionFlowReads} from './engine-selection-flows-v1.mjs';
import {bundleRoot,bundleConfirmation,verifyBundleCommit} from './engine-bundle-commit-v1.mjs';
import {publicShopSlots} from './engine-interface-contract-v2.mjs';
import {fixture} from './engine-interface-case-bank-v1.mjs';
import {sharedDecision} from './engine-shared-input-v10.mjs';
const helpers={cardProperties:c=>({definition_id:c.id,name:c.name,type:'Attack',rarity:'Basic',cost:String(c.cost),is_upgraded:c.is_upgraded,description:c.description}),visibleText:x=>x??null,withoutDeck:({deck,...p})=>p};
const ctx=()=>({snapshotId:'s',refs:[],actions:[],id:(...a)=>a.join('-'),referent(v){const r={...v,properties:{...v.properties,entity_id:v.id}};this.refs.push(r);return r;},action(v){this.actions.push(v);}});
const card=id=>({native_ref:id,id:'STRIKE',name:'Strike',cost:1,is_upgraded:false,is_selected:false,description:'Deal 6 damage'});
const state=()=>({decision:'card_reward',context:{},player:{native_ref:'p',name:'Ironclad',hp:30,max_hp:80,potions:[]},cards:[{...card('a'),index:0},{...card('b'),index:1,cost:0}],alternatives:[{index:0,native_ref:'skip',label:'Skip',enabled:true},{index:1,native_ref:'heal',label:'Heal 2 HP',enabled:true}]});
test('all actual reward alternatives and exact card copies remain independent choices',()=>{const s=state(),c=ctx(),r=projectSelectionFlows(s,c,helpers);assert.equal(r.complete,true);assert.deepEqual(c.actions.map(x=>x.label),['Take Strike','Take Strike','Skip','Heal 2 HP']);assert.equal(c.actions[1].raw.args.card_ref,'b');assert.equal(r.surface.cards[1].cost,'0');assert.equal(c.actions[3].raw.args.alternative_ref,'heal');assert.equal(r.surface.cards[0].is_selected,false);});
test('a mandatory reward cannot acquire a Skip action',()=>{const s=state();s.alternatives=[];const c=ctx();projectSelectionFlows(s,c,helpers);assert.equal(c.actions.length,2);assert.ok(!c.actions.some(a=>a.label==='Skip'));});
test('disabled alternatives are visible and never offered as actions',()=>{const s=state();s.alternatives[1].enabled=false;const c=ctx(),r=projectSelectionFlows(s,c,helpers);assert.equal(r.surface.alternatives.length,2);assert.equal(c.actions.length,3);});
test('star costs and card-detail identities survive offered-card projection',()=>{const s=state(),c=ctx();s.cards[0].star_cost='X';s.cards[1].star_cost=0;const surface=projectSelectionFlows(s,c,helpers),reads=selectionFlowReads(s,[],c,helpers);assert.equal(surface.surface.cards[0].star_cost,'X');assert.equal(surface.surface.cards[1].star_cost,'0');assert.deepEqual(reads.map(r=>r.content),surface.surface.cards);for(const r of reads){assert.equal(typeof r.completeness.visible_information,'string');assert.equal(r.completeness.interaction_discovery,'read_only');}});
test('missing alternative identity or flags fail before action selection',()=>{for(const mutate of [s=>delete s.alternatives[0].enabled,s=>delete s.cards[0].is_selected,s=>delete s.alternatives[0].native_ref]){const s=state();mutate(s);assert.throws(()=>projectSelectionFlows(s,ctx(),helpers));}});
function packFixture(){const {snapshot:root}=fixture('card_bundle_selection');const id='bundle';const pack={entity_id:id,cards:[{...root.interaction.content.surface.cards[0]}]};root.interaction.content.surface={kind:'card_bundle_selection',stage:'choosing',bundles:[pack],selectable_bundle_entity_ids:[id],can_confirm:false,can_cancel_preview:false};root.interaction.stage='choosing';root.referents.push({referent_id:id,role:'bundle',state:{visible:true},properties:pack});const action={bound_action_id:'select',interaction_id:root.interaction.interaction_id,verb:'select',subject_referent_id:id,arguments:[],label:'Preview bundle: Test card'};root.bound_actions={status:'complete',total_count:1,materialized_count:1,actions:[action]};const preview=structuredClone(root);preview.snapshot_id='preview';Object.assign(preview.interaction.content.surface,{stage:'preview',selected_bundle_entity_id:id,selectable_bundle_entity_ids:[],can_confirm:true,can_cancel_preview:true});const confirm={...action,bound_action_id:'confirm',verb:'confirm',label:'Confirm pack'};preview.bound_actions.actions=[confirm];const receipt={delivery:'delivered',action:confirm,attribution:{runtime_instance_id:root.session.runtime_instance_id}};const after=structuredClone(root);after.snapshot_id='after';after.interaction.interaction_id='new_owner';after.interaction.kind='event_option';return {root,pack,action,preview,confirm,receipt,after};}
test('pack preview and final commit verify exactly one complete model choice',()=>{const f=packFixture();assert.deepEqual(bundleRoot(f.root,f.action),f.pack);assert.deepEqual(bundleConfirmation(f.root,f.pack,f.preview),f.confirm);assert.equal(verifyBundleCommit(f.root,f.action,f.preview,f.confirm,f.receipt,f.after).game_committed,true);});
for(const [name,mutate]of Object.entries({foreign_owner:f=>f.preview.interaction.interaction_id='foreign',foreign_runtime:f=>f.preview.session.runtime_instance_id='foreign',other_pack:f=>f.preview.interaction.content.surface.selected_bundle_entity_id='other',changed_card:f=>f.preview.interaction.content.surface.bundles[0].cards[0].cost='2',missing_confirm:f=>f.preview.bound_actions.actions=[],uncertain:f=>f.receipt.delivery='unknown',owner_still_open:f=>f.after.interaction.interaction_id=f.root.interaction.interaction_id}))test(`pack commit rejects ${name}`,()=>{const f=packFixture();mutate(f);assert.throws(()=>verifyBundleCommit(f.root,f.action,f.preview,f.confirm,f.receipt,f.after));});
test('pack actions preserve their raw binding while sharing one committed meaning',()=>{const f=packFixture();const before=structuredClone(f.root);const reads=fixture('card_bundle_selection').reads;const frame=sharedDecision(f.root,reads);assert.equal(frame.public_input.candidates[0].label,'Take pack: Test card');assert.equal(frame.actions[0].bound_action_id,'select');assert.deepEqual(f.root,before);});
test('merchant catalogs are accepted only for an explicitly merchant-owned atomic selector',()=>{const s=fixture('card_selection').snapshot;s.interaction.content.context={kind:'shop'};s.interaction.content.surface.selection_contract='atomic_public_card_choice_v1';const r={read_id:'shop',kind:'shop_catalog',content:{cards:[],relics:[],potions:[]}};assert.doesNotThrow(()=>publicShopSlots(s,[r]));s.interaction.content.context.kind='rest';assert.throws(()=>publicShopSlots(s,[r]),/owner/);s.interaction.content.context.kind='shop';delete s.interaction.content.surface.selection_contract;assert.throws(()=>publicShopSlots(s,[r]),/owner/);});

test('every new surface declares the complete decoder contract',()=>{
 const reward=state(),pack={...reward,decision:'bundle_select',selection_ref:'p',prompt:'Choose a Pack',selection_owner:{kind:'event'},bundles:[{index:0,native_ref:'b',cards:[card('c')]}]};
 const shop={...reward,decision:'shop',room_ref:'shop',shop_catalog:{access_state:'open',cards:[],relics:[],potions:[],card_removal:null}};
 for(const s of [reward,pack,shop]){const projected=projectSelectionFlows(s,ctx(),helpers);assert.equal(projected.complete,true);assert.equal(typeof projected.visibleInformation,'string');assert.equal(typeof projected.interactionDiscovery,'string');assert.deepEqual(projected.missing,[]);}
});
test('the same pending reward keeps its handle across snapshots and row removal',()=>{
 const reward={native_ref:'native-reward',kind:'card_choice'},other={native_ref:'gold',kind:'gold'};
 const project=(snapshotId,rewards)=>{const c=ctx();c.snapshotId=snapshotId;projectSelectionFlows({decision:'reward_set',player:{potions:[]},rewards},c,{...helpers,defaultProjector(s,owner){s.rewards.forEach((r,i)=>owner.referent({role:'reward',occurrence:i,properties:{kind:r.kind}}));return {kind:'reward_claim'};}});return c.refs.find(r=>r.properties.kind==='card_choice').properties.entity_id;};
 assert.equal(project('before',[other,reward]),project('returned',[other,reward]));
 assert.equal(project('before',[other,reward]),project('gold-claimed',[reward]));
 assert.notEqual(project('before',[reward]),project('other-world',[{...reward,native_ref:'another-reward'}]));
});
test('empty reward belt aliases collapse; actual belt facts remain explicit',()=>{
 for(const potions of [[],[{slot:0,definition_id:'FIRE_POTION'}]]){
  const f=fixture('card_reward_selection');f.snapshot.interaction.content.context={kind:'reward_flow',reward_kind:'card_reward'};
  f.snapshot.interaction.content.surface.potion_states=structuredClone(potions);f.snapshot.persistent.content.player.potions=structuredClone(potions);
  const output=sharedDecision(f.snapshot,f.reads).public_input;
  assert.equal(Object.hasOwn(output.context.interaction.content.surface,'potion_states'),potions.length>0);
  assert.deepEqual(f.snapshot.interaction.content.surface.potion_states,potions);
 }
});
import {rewardProceed,verifyRewardDeparture} from './engine-reward-commit-v1.mjs';
test('reward Continue waits for owner departure without another input',()=>{
 const f=fixture('reward_claim'),root=f.snapshot;root.interaction.content.surface.can_proceed=true;
 const action={verb:'activate',label:'Skip remaining rewards and continue',subject_referent_id:null,arguments:[],bound_action_id:'proceed'};root.bound_actions.actions=[action];
 const receipt={delivery:'delivered',action,attribution:{runtime_instance_id:root.session.runtime_instance_id}};
 const after=structuredClone(root);after.snapshot_id='next';after.interaction.interaction_id='departed';after.bound_actions.actions[0].interaction_id='departed';after.bound_actions.total_count=1;after.bound_actions.materialized_count=1;
 assert.equal(rewardProceed(root,action),true);assert.equal(verifyRewardDeparture(root,action,receipt,after).successor_snapshot.snapshot_id,'next');
 for(const change of [x=>x.after.interaction.interaction_id=root.interaction.interaction_id,x=>x.receipt.delivery='unknown',x=>x.after.session.runtime_instance_id='foreign']){
  const c=structuredClone({after,receipt});change(c);assert.throws(()=>verifyRewardDeparture(root,action,c.receipt,c.after));
 }
 assert.equal(rewardProceed(root,{...action,label:'Claim 9 Gold'}),false);
});
import {flowWorkerInput} from './engine-native-worker-v15.mjs';
import {publicPolicyInput} from './engine-public-input-v1.mjs';
import {newDiagnosticNavigation} from './engine-run-policy-v7.mjs';
test('the worker declares read-only merchant slots before its diagnostic graph',()=>{
 const f=fixture('shop_inventory');const read={kind:'shop_catalog',content:{cards:[{entity_id:'offer',slot_entity_id:'slot'}],relics:[],potions:[],card_removal:null}};
 const nav=newDiagnosticNavigation();assert.throws(()=>publicPolicyInput(f.snapshot,[...f.reads,read],nav),/Unresolved/);
 const original=structuredClone(read),output=flowWorkerInput(f.snapshot,[...f.reads,read],nav);
 assert.ok(output.context.reads.some(r=>r.content.declared_shop_slots?.length===1));assert.deepEqual(read,original);
});
test('completed combat keeps boss provenance and the actual empty reward Continue',()=>{
 for(const is_boss of [false,true]){
  const c=ctx(),s={decision:'combat_rewards_complete',room_ref:'room',is_boss,player:{native_ref:'p',potions:[],max_potion_slots:2}};
  const view=projectSelectionFlows(s,c,helpers);assert.equal(view.kind,'reward_claim');assert.deepEqual(view.surface.rewards,[]);
  assert.equal(view.context.completed_boss_combat,is_boss);assert.equal(view.surface.proceed_skips_remaining_rewards,false);
  assert.equal(c.actions[0].label,'Continue from rewards');assert.equal(c.actions[0].raw.args.room_ref,'room');
 }
 const s={decision:'combat_rewards_complete',room_ref:'r',player:{potions:[],max_potion_slots:2}};assert.throws(()=>projectSelectionFlows(s,ctx(),helpers));
});
test('the rendered event page shares one typed body name without changing amounts',()=>{
 const a=fixture('event_option'),b=structuredClone(a),text='Gain 2 Strength and 7 Dexterity.';
 Object.assign(a.snapshot.interaction.content.context,{kind:'event',description:text});delete a.snapshot.interaction.content.context.body;
 Object.assign(b.snapshot.interaction.content.context,{kind:'event',body:text});delete b.snapshot.interaction.content.context.description;
 delete a.snapshot.interaction.content.surface.description;delete b.snapshot.interaction.content.surface.description;
 const original=structuredClone(a),left=sharedDecision(a.snapshot,a.reads),right=sharedDecision(b.snapshot,b.reads);
 assert.deepEqual(left.public_input,right.public_input);assert.deepEqual(a,original);
 b.snapshot.interaction.content.context.body='Gain 7 Strength and 2 Dexterity.';
 assert.notDeepEqual(left.public_input,sharedDecision(b.snapshot,b.reads).public_input);
 b.snapshot.interaction.content.context.description=text;assert.throws(()=>sharedDecision(b.snapshot,b.reads),/Conflicting/);
});
import {contextReference,atomicSelectionReads,projectAtomicSelection} from './engine-atomic-selection-v2.mjs';
test('context-only combat cards retain identity without duplicate action declarations',()=>{
 const card={id:'same-hand-card',role:'hand',properties:{cost:'1',stats:{block:5}}},view=contextReference(card);
 assert.equal(view.referent_id,card.id);assert.equal(view.properties.entity_id,card.id);assert.deepEqual(card.properties,{cost:'1',stats:{block:5}});
 assert.equal(contextReference({...card,includeEntityId:false}).properties.entity_id,undefined);
 assert.throws(()=>contextReference({...card,id:null}),/identity/);
});
test('a combat card selector retains openable piles and the selected copy identity',()=>{
 const c=ctx(),copy=card('discard-copy'),s={decision:'card_select',cards:[{...copy,upgraded:false}],
   player:{deck:[]},selection_combat:{combat_piles:[{pile:'draw',cards:[]},{pile:'discard',cards:[copy]},{pile:'exhaust',cards:[]}]}};
 const before=structuredClone(s),reads=atomicSelectionReads(s,[],c,helpers),piles=reads.find(r=>r.descriptor.kind==='combat_piles');
 assert.equal(piles.completeness.status,'complete');assert.deepEqual(piles.descriptor.hidden_by_policy,['draw_pile_true_order']);
 assert.equal(piles.content.zones[1].cards[0].entity_id,reads.find(r=>r.descriptor.kind==='surface_card').content.entity_id);
 assert.equal(atomicSelectionReads(s,reads.filter(r=>r.descriptor.kind==='combat_piles'),c,helpers).filter(r=>r.descriptor.kind==='combat_piles').length,1);
 assert.deepEqual(s,before);delete s.selection_combat.combat_piles;
 assert.throws(()=>atomicSelectionReads(s,[],c,helpers),/Missing public piles/);
 assert.ok(!atomicSelectionReads({decision:'card_select',cards:[],player:{deck:[]}},[],c,helpers).some(r=>r.descriptor.kind==='combat_piles'));
});
test('selection deduplicates chosen hand cards while keeping other inspectable operands',()=>{
 const c=ctx(),a={...card('a'),upgraded:false,can_play:true,target_type:'Self',stats:{block:5}},b={...a,native_ref:'b'};
 const combat={decision:'combat_play',hand:[a,b],enemies:[],player:{native_ref:'p',name:'Ironclad',potions:[],block:0},
   player_statuses:[],companions:[],orbs:[],orb_slots:0,stars_visible:false,stars:null,round:1,is_play_phase:true,
   turn_owner:'player',encounter_type:'normal',energy:2,max_energy:3,draw_pile_count:0,discard_pile_count:0,exhaust_pile_count:0};
 const s={decision:'card_select',player:{deck:[]},cards:[a],selection_preferences_complete:true,selection_ref:'picker',
   cancelable:false,require_manual_confirmation:false,unpowered_previews:false,pretend_cards_can_be_played:false,
   selection_owner:{kind:'combat'},selection_combat:combat,min_select:1,max_select:1,prompt:'Pick a card'};
 const view=projectAtomicSelection(s,c,helpers);assert.equal(c.refs.length,3);assert.equal(new Set(c.refs.map(r=>r.id)).size,3);
 assert.deepEqual(c.refs.map(r=>r.role).sort(),['card','hand','player']);assert.equal(c.actions.length,1);
 assert.equal(view.context.player.hand.length,2);assert.equal(c.actions[0].raw.args.indices,'0');
});
import {normalizeLayout} from './engine-input-layout-v7.mjs';
test('nullable stars have the same meaning inside a combat selection',()=>{
 const f=fixture('card_selection'),input=sharedDecision(f.snapshot,f.reads).public_input;
 input.context.interaction.content.context={kind:'selection',owner_kind:'combat',player:{stars_visible:false,stars:null}};
 const other=structuredClone(input);delete other.context.interaction.content.context.player.stars;
 assert.deepEqual(normalizeLayout(input).public_input,normalizeLayout(other).public_input);
 other.context.interaction.content.context.player={stars_visible:true,stars:7};
 assert.equal(normalizeLayout(other).public_input.context.interaction.content.context.player.stars,7);
});
