import assert from 'node:assert/strict';
import test from 'node:test';
import {rewardOwnerDeparted, verifyRewardDeparture} from './engine-reward-commit-v2.mjs';
import {projectExactCombatSurface} from './engine-combat-surface-v6.mjs';
import {projectSelectionFlows, selectionFlowReads} from './engine-selection-flows-v2.mjs';
import {fixture} from './engine-interface-case-bank-v1.mjs';

const helpers = {visibleText: x => x, withoutDeck: ({deck, ...rest}) => rest,
  cardProperties: c => ({definition_id:c.id, name:c.name, type:'Attack', rarity:'Basic',
    cost:String(c.cost), is_upgraded:false, description:c.description})};
function ctx() {
  return {snapshotId:'s', refs:[], actions:[], id:(...p) => p.join(':'),
    referent(v) { const r={...v, referent_id:v.id, properties:{...v.properties,
      ...(v.includeEntityId===false?{}:{entity_id:v.id})}}; this.refs.push(r); return r; },
    action(v) {this.actions.push(v);}};
}
function combat() {
  return {decision:'combat_play', hand:[], enemies:[], player:{native_ref:'player', name:'Player',
    block:0, potions:[{native_ref:'copy', id:'TEST_POTION', name:'Test Potion',
      description:'Choose cards.', slot:1, usage:'CombatOnly', binding_supported:true,
      can_use:true, can_discard:true, target_type:'AnyPlayer', valid_target_refs:['player']}]},
    player_statuses:[], companions:[], orbs:[], orb_slots:0, stars_visible:false, stars:null,
    energy:3, max_energy:3, draw_pile_count:0, discard_pile_count:0, exhaust_pile_count:0,
    round:1, is_play_phase:true, turn_owner:'player', encounter_type:'normal'};
}
test('a changing reward signature cannot admit the same closing panel as another decision', () => {
  const root=fixture('reward_claim').snapshot;
  root.interaction.content.surface.can_proceed=true;
  const action={verb:'activate',label:'Skip remaining rewards and continue',
    subject_referent_id:null,arguments:[],bound_action_id:'leave'};
  root.bound_actions.actions=[action];
  const after=structuredClone(root); after.snapshot_id='new';after.interaction.interaction_id='changed';
  after.bound_actions.actions[0].interaction_id='changed';
  after.bound_actions.total_count=1;after.bound_actions.materialized_count=1;
  const receipt={delivery:'delivered',action,attribution:{runtime_instance_id:root.session.runtime_instance_id}};
  assert.equal(rewardOwnerDeparted(root,after),false);
  assert.throws(() => verifyRewardDeparture(root,action,receipt,after),/still mounted/);
  after.interaction.kind='map_navigation';
  assert.equal(rewardOwnerDeparted(root,after),true);
  assert.equal(verifyRewardDeparture(root,action,receipt,after).successor_snapshot.snapshot_id,'new');
  after.session.runtime_instance_id='foreign';
  assert.equal(rewardOwnerDeparted(root,after),false);
});
test('combat potion identity joins the exact owned inventory occurrence, independently of belt slot', () => {
  const s=combat(), c=ctx(), r=projectExactCombatSurface(s,c,helpers);
  assert.equal(r.complete,true);
  const p=c.refs.find(x=>x.role==='usable_potion');
  assert.equal(p.referent_id,c.id('potion','s','copy',0));
  assert.equal(p.properties.slot,1);
  assert.deepEqual(r.context.player.potion_states,[{entity_id:p.referent_id,
    target_type:'AnyPlayer',can_use:true,automatic:false}]);
  const use=c.actions.find(x=>x.raw.action==='use_potion');
  assert.equal(use.label,'Use Test Potion');
  assert.deepEqual(use.raw.args,{potion_slot:1,potion_ref:'copy',target_ref:'player'});
  assert.equal(use.arguments[0].referent.referent_id,r.context.player.player_entity_id);
  assert.equal(c.actions.find(x=>x.raw.action==='discard_potion').label,'Discard Test Potion from slot 2');
  assert.deepEqual(r.surface.discardable_potions,[{entity_id:p.referent_id,name:'Test Potion',slot:1}]);
});
test('two identical potion definitions remain different owned copies and preserve permissions', () => {
  const s=combat(); s.player.potions.push({...s.player.potions[0],native_ref:'other',slot:0,can_use:false,can_discard:false});
  const c=ctx(),r=projectExactCombatSurface(s,c,helpers);
  assert.equal(r.complete,true); const refs=c.refs.filter(x=>['potion','usable_potion'].includes(x.role));
  assert.notEqual(refs[0].referent_id,refs[1].referent_id);
  assert.equal(r.context.player.potion_states.length,2);
  assert.equal(c.actions.filter(x=>x.raw.action==='use_potion').length,1);
  assert.equal(c.actions.filter(x=>x.raw.action==='discard_potion').length,1);
});
test('a closed merchant has inspectable actual stock without granting purchase authority', () => {
  const s={decision:'merchant_approach',room_ref:'room',merchant_ref:'merchant',inventory_open:false,
    context:{},player:{native_ref:'p',name:'Player',hp:50,max_hp:80,potions:[]},
    shop_catalog:{access_state:'inventory_closed_open_to_inspect',cards:[{native_ref:'offer',inventory_index:0,
      price:70,stocked:true,visible:true,affordable:true,can_purchase:false,blocked_reason:'ui_control_disabled',
      card:{native_ref:'card',id:'CARD',name:'Example',is_selected:false,is_upgraded:false,cost:1}}],
      relics:[],potions:[],card_removal:null}};
  const c=ctx(),r=projectSelectionFlows(s,c,helpers),reads=selectionFlowReads(s,[],c,helpers);
  assert.equal(r.kind,'shop_room'); assert.equal(r.surface.can_open_inventory,true);
  assert.deepEqual(c.actions.map(x=>[x.verb,x.raw.action]),[['open','open_shop'],['activate','leave_shop']]);
  assert.equal(reads[0].content.cards[0].price,70);
  assert.equal(reads[0].content.cards[0].can_purchase,false);
  assert.equal(c.actions.some(x=>x.raw.action.startsWith('buy_')),false);
});
test('completed combat still uses the room proceed path, independently of merchant leave', () => {
  const c=ctx(); projectSelectionFlows({decision:'combat_rewards_complete',room_ref:'room',is_boss:false,
    player:{native_ref:'p',potions:[],max_potion_slots:2}},c,helpers);
  assert.equal(c.actions[0].raw.action,'proceed');
});
