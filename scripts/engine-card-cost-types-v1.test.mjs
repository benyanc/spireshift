import test from 'node:test';
import assert from 'node:assert/strict';
import {normalizeCardCosts,restoreCardCosts} from './engine-card-cost-types-v1.mjs';
import {sharedDecision,deliveredAction} from './engine-shared-input-v14.mjs';
import {fixture} from './engine-interface-case-bank-v1.mjs';

function combat(cost=2) {
  const f=fixture('combat_hand_card_selection');
  const surface=f.snapshot.interaction.content.surface;
  f.snapshot.interaction.content.context={kind:'combat',round:2,player:{hand:[structuredClone(surface.cards[0])],stars:7,energy:2}};
  surface.cards[0].star_cost=cost===null?null:String(cost);
  f.snapshot.interaction.content.context.player.hand[0].star_cost=cost;
  f.snapshot.referents[0].properties.star_cost=surface.cards[0].star_cost;
  f.reads[0].content.cards[0].star_cost=cost;
  return f;
}
test('the same current card joins numeric and textual star cost before entity merging',()=>{
  const numeric=combat(),textual=structuredClone(numeric);
  textual.snapshot.interaction.content.context.player.hand[0].star_cost='2';
  textual.reads[0].content.cards[0].star_cost='2';
  const before=structuredClone(numeric),a=sharedDecision(numeric.snapshot,numeric.reads),b=sharedDecision(textual.snapshot,textual.reads);
  assert.deepEqual(a.public_input,b.public_input);assert.deepEqual(a.actions,b.actions);
  assert.equal(a.scalar_normalization_evidence.rewrites.length,2);
  assert.deepEqual(numeric,before);
  assert.equal(deliveredAction(a,{binding_id:a.binding_id,action_index:0},numeric.snapshot).bound_action_id,a.actions[0].bound_action_id);
});
test('all raw types, unknown facts, list order and original source objects round trip exactly',()=>{
  const f=combat();f.snapshot.unfamiliar={star_cost:2,order:[7,2]};
  const original=structuredClone(f),typed=normalizeCardCosts(f.snapshot,f.reads);
  assert.deepEqual(typed.snapshot.unfamiliar,original.snapshot.unfamiliar);
  assert.equal(typed.snapshot.interaction.content.context.player.stars,7);
  assert.equal(typed.snapshot.interaction.content.context.player.energy,2);
  assert.deepEqual(restoreCardCosts({snapshot:typed.snapshot,reads:typed.reads},typed.evidence),original);
  assert.deepEqual(f,original);
});
test('zero, absent star cost and X remain strategically different',()=>{
  const inputs=[0,null,'X',2,7].map(cost=>sharedDecision(combat(cost).snapshot,combat(cost).reads).public_input);
  for(let i=0;i<inputs.length;i++)for(let j=0;j<i;j++)assert.notDeepEqual(inputs[i],inputs[j]);
});
test('a genuine disagreement between two current views still fails closed',()=>{
  const f=combat();f.snapshot.interaction.content.context.player.hand[0].star_cost=7;
  assert.throws(()=>sharedDecision(f.snapshot,f.reads),/Conflicting current public entity facts.*star_cost/u);
});
test('different physical copies with different costs do not collapse',()=>{
  const f=combat(),s=f.snapshot.interaction.content.surface,second={...structuredClone(s.cards[0]),entity_id:'second-copy',star_cost:'7'};
  s.cards.push(second);s.selectable_card_entity_ids.push(second.entity_id);
  const frame=sharedDecision(f.snapshot,f.reads),cards=frame.public_input.context.interaction.content.surface.cards;
  assert.equal(cards.length,2);assert.notDeepEqual(cards[0].entity_id,cards[1].entity_id);
  assert.deepEqual(cards.map(card=>card.star_cost),['2','7']);
});
test('unsupported typed costs never silently become a known cost',()=>{
  for(const bad of [-1,0.5,NaN,Infinity,Number.MAX_SAFE_INTEGER+1,'-1','2.0','02','unknown',{}]){
    const f=combat();f.snapshot.interaction.content.context.player.hand[0].star_cost=bad;
    assert.throws(()=>normalizeCardCosts(f.snapshot,f.reads),/star cost|Finite public scalar JSON/u);
  }
});
test('changed raw-normalization evidence cannot be treated as reversible',()=>{
  const f=combat(),typed=normalizeCardCosts(f.snapshot,f.reads),e=structuredClone(typed.evidence);
  e.rewrites[0].before=7;
  assert.throws(()=>restoreCardCosts({snapshot:typed.snapshot,reads:typed.reads},e),/Changed typed public scalar/u);
  typed.snapshot.interaction.content.context.player.energy=8;
  assert.throws(()=>restoreCardCosts({snapshot:typed.snapshot,reads:typed.reads},typed.evidence),/Changed public scalar evidence/u);
});
