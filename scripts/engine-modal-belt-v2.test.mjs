import test from 'node:test';
import assert from 'node:assert/strict';
import {projectSelectionFlows} from './engine-selection-flows-v9.mjs';

const clone=structuredClone;
const helpers={visibleText:v=>v??null,withoutDeck:p=>Object.fromEntries(Object.entries(p).filter(([k])=>k!=='deck')),
 cardProperties:c=>({definition_id:c.id,name:c.name,type:c.type,rarity:c.rarity,cost:String(c.cost),is_upgraded:c.is_upgraded,description:c.description})};
function fixture({use=false,discard=true,usage='CombatOnly'}={}){
 const potion={native_ref:'potion-copy',id:'EXPLOSIVE_AMPOULE',name:'Explosive Ampoule',description:'Deal 10 damage to ALL enemies.',slot:0,
  can_use:use,can_discard:discard,binding_supported:true,target_type:'AllEnemies',usage,valid_target_refs:[]};
 if(use){potion.target_type='Self';potion.id='FRUIT_JUICE';potion.name='Fruit Juice';}
 const card={native_ref:'card-copy',id:'DEFEND_IRONCLAD',name:'Defend',description:'Gain 5 Block.',type:'Skill',rarity:'Basic',cost:1,is_upgraded:false,upgraded:false,is_selected:false};
 const player={native_ref:'player',name:'Ironclad',hp:40,max_hp:80,block:0,potions:[potion],deck:[]};
 const combat={decision:'combat_play',hand:[],enemies:[],player,player_statuses:[],companions:[],orbs:[],orb_slots:0,stars_visible:false,stars:null,
  energy:3,max_energy:3,draw_pile_count:0,discard_pile_count:1,exhaust_pile_count:0,round:2,is_play_phase:false,turn_owner:'player',encounter_type:'normal',
  combat_piles:[{pile:'discard',cards:[card]}]};
 return{decision:'card_select',player,context:{floor:5},selection_ref:'select-owner',selection_owner:{kind:'combat'},selection_combat:combat,cards:[card],
  selection_preferences_complete:true,min_select:1,max_select:1,cancelable:false,require_manual_confirmation:false,unpowered_previews:false,pretend_cards_can_be_played:false};
}
function project(state){
 const refs=[],actions=[],ctx={snapshotId:'snapshot',id:(...x)=>x.join(':'),referent(v){
  if(refs.some(r=>r.referent_id===v.id))throw Error('Duplicate referent ID');
  const row={...v,referent_id:v.id,properties:{...v.properties,...(v.includeEntityId===false?{}:{entity_id:v.id})}};refs.push(row);return row;
 },action(v){actions.push(v);}};
 return{result:projectSelectionFlows(state,ctx,helpers),refs,actions};
}
test('combat selection keeps a single owned potion identity in context, surface and exact discard binding',()=>{
 const raw=fixture(),before=clone(raw),{result,actions}=project(raw);assert.equal(result.complete,true);
 const summary=result.context.player.potion_states[0],belt=result.surface.potion_states[0];
 assert.deepEqual(Object.keys(summary).sort(),['automatic','can_use','entity_id','target_type']);
 assert.equal(summary.entity_id,belt.entity_id);assert.equal(summary.can_use,false);assert.equal(belt.can_discard,true);
 const discard=actions.find(a=>a.raw.action==='discard_potion');assert.ok(discard);assert.equal(discard.subject.properties.entity_id,belt.entity_id);
 assert.deepEqual(discard.raw.args,{potion_slot:0,potion_ref:'potion-copy'});assert.ok(actions.some(a=>a.verb==='confirm'));
 assert.deepEqual(raw,before);
});
test('a pending discard removes its own authority while preserving the same inventory copy and card answers',()=>{
 const {result,actions}=project(fixture({discard:false}));assert.equal(result.complete,true);
 assert.equal(result.surface.potion_states.length,1);assert.equal(result.surface.potion_states[0].can_discard,false);
 assert.equal(actions.some(a=>a.raw.action==='discard_potion'),false);assert.ok(actions.some(a=>a.verb==='confirm'));
});
test('AnyTime potion use remains available independently of a combat card selector',()=>{
 const {result,actions}=project(fixture({use:true,usage:'AnyTime'}));assert.equal(result.complete,true);
 assert.equal(result.context.player.potion_states[0].can_use,true);assert.ok(actions.some(a=>a.raw.action==='use_potion'));
 assert.ok(actions.some(a=>a.raw.action==='discard_potion'));
});
test('combat-only use is never invented from discard permission and missing permissions are incomplete',()=>{
 let f=fixture();let p=project(f);assert.equal(p.actions.some(a=>a.raw.action==='use_potion'),false);
 delete f.player.potions[0].can_discard;assert.throws(()=>project(f),/Incomplete selected combat observation.*native_potion_enablement/u);
});
test('a usable player-targeted potion does not register its player target twice during selection',()=>{
 const raw=fixture({use:true,usage:'AnyTime'});raw.player.potions[0].target_type='AnyPlayer';raw.player.potions[0].valid_target_refs=['player'];
 const {result,refs,actions}=project(raw);assert.equal(result.complete,true);assert.equal(new Set(refs.map(r=>r.referent_id)).size,refs.length);
 const use=actions.find(a=>a.raw.action==='use_potion');assert.ok(use);assert.equal(use.raw.args.target_ref,'player');
 assert.equal(use.arguments[0].referent.referent_id,result.context.player.player_entity_id);
});
