import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {ownedBeltContext} from './engine-relic-surface-v3.mjs';
import {appendPotionControls} from './engine-potion-surface-v1.mjs';
const helpers={visibleText:v=>v??null,cardProperties:r=>({definition_id:r.id})};
const potion=(extra={})=>({id:'BLOOD_POTION',name:'Blood Potion',native_ref:'private-potion',description:'Restore health',slot:2,usage:'AnyTime',can_use:true,can_discard:true,binding_supported:true,target_type:'AnyPlayer',valid_target_refs:['private-player'],...extra});
function fixture(rows=[potion()]){
 const ctx={snapshotId:'s',referents:[],actions:[],id:(...args)=>createHash('sha256').update(JSON.stringify(args)).digest('hex'),
  action(v){this.actions.push(v);},referent(v){const r={...v,referent_id:v.id,properties:{...v.properties,entity_id:v.id}};this.referents.push(r);return r;}};
 const state={decision:'rest',player:{native_ref:'private-player',name:'The Ironclad',hp:30,max_hp:80,potions:rows}};
 const result=appendPotionControls(state,ownedBeltContext(state,ctx),helpers,{complete:true,missing:[],surface:{}});
 return {ctx,result,state};
}
test('global belt references use the same exact physical potion and player keys as the persistent HUD',()=>{
 const {ctx,result,state}=fixture();assert.equal(result.complete,true);
 assert.equal(result.surface.potion_states[0].entity_id,ctx.id('potion','s',state.player.potions[0].native_ref,0));
 const use=ctx.actions.find(a=>a.verb==='use');assert.equal(use.arguments[0].referent.referent_id,ctx.id('player','s','private-player'));
 assert.deepEqual(use.raw.args,{potion_slot:2,potion_ref:'private-potion',target_ref:'private-player'});
});
test('empty and unusable belts do not create an unused current-player entity',()=>{
 for(const rows of [[],[potion({can_use:false,usage:'CombatOnly'})]]){
  const {ctx,result}=fixture(rows);assert.equal(result.complete,true);assert.equal(ctx.referents.some(r=>r.role==='player'),false);
 }
});
test('identical-definition potions in different real slots keep separate physical controls',()=>{
 const {ctx,result}=fixture([potion(),potion({native_ref:'private-copy-2',slot:0})]);assert.equal(result.complete,true);
 assert.equal(new Set(result.surface.potion_states.map(p=>p.entity_id)).size,2);
 assert.deepEqual(ctx.actions.filter(a=>a.verb==='use').map(a=>a.raw.args.potion_slot),[2,0]);
});
test('source ownership and target validation still reject a foreign player',()=>{
 const {ctx,result}=fixture([potion({valid_target_refs:['foreign-player']})]);
 assert.equal(result.complete,false);assert.equal(ctx.actions.length,0);
});
