import test from 'node:test';
import assert from 'node:assert/strict';
import {fixture} from './engine-interface-case-bank-v1.mjs';
import {sharedDecision} from './engine-shared-input-v8.mjs';
import {normalizeLayout,restoreLayout} from './engine-input-layout-v6.mjs';
function rewardInput(native){
 const f=fixture('reward_claim'),input=sharedDecision(f.snapshot,f.reads).public_input;
 const reward={entity_id:{public_slot:100},kind:'relic',label:'Anchor',description:native?'Start with [blue]10[/blue] [gold]Block[/gold].':'Start with 10 Block.',enabled:true};
 const ref={public_slot:100,role:'reward',label:'Anchor',state:{visible:true,enabled:true},properties:structuredClone(reward)};
 input.context.referents.push(ref);
 input.context.interaction.content.context={kind:'reward_flow',reward_kind:'room_rewards'};
 input.context.interaction.content.surface={kind:'reward_claim',rewards:[reward],can_proceed:!native,proceed_skips_remaining_rewards:true,potion_slots_full:false,discardable_potions:[],...(native?{potion_states:[]}:{})};
 input.context.interaction.capabilities=[{verb:native?'skip':'activate',arguments:[],availability_basis:'current_native_interaction'},{verb:'activate',subject_role:'reward',arguments:[],availability_basis:'current_native_interaction'}];
 input.candidates=[{verb:native?'skip':'activate',label:native?'Skip remaining rewards':'Skip remaining rewards and continue',subject:null,arguments:[],history:{}},{verb:'activate',label:'Claim Anchor',subject:structuredClone(ref),arguments:[],history:{}}];
 return input;
}
test('an actually advertised reward exit has a common semantic name and exact reversible authority',()=>{
 const native=rewardInput(true),official=rewardInput(false);
 assert.deepEqual(normalizeLayout(native).public_input,normalizeLayout(official).public_input);
 assert.deepEqual(restoreLayout(normalizeLayout(native)),native);
 assert.equal(native.candidates[0].verb,'skip');
});
test('missing exits and disallowed skipping never acquire a new control',()=>{
 const input=rewardInput(true);input.candidates.shift();input.context.interaction.capabilities.shift();
 const result=normalizeLayout(input);assert.equal(result.public_input.candidates.length,1);
 assert.equal(result.public_input.context.interaction.content.surface.can_proceed,false);
});
test('only known display color tags are normalized; unknown markup and nonempty belts stay',()=>{
 const input=rewardInput(true);input.context.interaction.content.surface.rewards[0].description='[future]4[/future] [blue]2[/blue]';
 input.context.interaction.content.surface.potion_states=[{slot:0,can_use:false}];
 const result=normalizeLayout(input);assert.equal(result.public_input.context.interaction.content.surface.rewards[0].description,'[future]4[/future] 2');
 assert.equal(result.public_input.context.interaction.content.surface.potion_states.length,1);
 assert.deepEqual(restoreLayout(result),input);
});
