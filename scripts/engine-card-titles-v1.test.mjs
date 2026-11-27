import test from 'node:test';
import assert from 'node:assert/strict';
import {fixture} from './engine-interface-case-bank-v1.mjs';
import {sharedDecision} from './engine-shared-input-v10.mjs';

function cardFrame(name, upgraded) {
  const f=fixture('card_selection'),card=f.snapshot.interaction.content.surface.cards[0];
  const id=card.entity_id;
  function update(value) {
    if(Array.isArray(value)){value.forEach(update);return;}
    if(!value||typeof value!=='object')return;
    if(value.entity_id===id&&typeof value.definition_id==='string') {
      value.name=name;value.is_upgraded=upgraded;
    }
    Object.values(value).forEach(update);
  }
  update(f);f.snapshot.referents[0].label=name;
  f.snapshot.bound_actions.actions=[{bound_action_id:'confirm-card',
    interaction_id:f.snapshot.interaction.interaction_id,verb:'confirm',
    label:'Confirm '+name,arguments:[{role:'selected_card',referent_id:id}]}];
  return f;
}

for(const [name,upgraded]of [['Strike',false],['Strike+',true],['Repeated upgrade+3',true],['A changed visible title',false]]) {
  test('current title is preserved verbatim: '+name,()=>{
    const f=cardFrame(name,upgraded),before=structuredClone(f),frame=sharedDecision(f.snapshot,f.reads);
    const offered=frame.public_input.context.interaction.content.surface.cards[0];
    const deck=frame.public_input.context.reads.find(r=>r.kind==='run_deck').content.cards[0];
    assert.equal(offered.name,name);assert.equal(offered.is_upgraded,upgraded);
    assert.equal(deck.name,name);assert.equal(frame.public_input.candidates[0].label,'Confirm '+name);
    assert.equal(frame.actions[0].bound_action_id,'confirm-card');assert.deepEqual(f,before);
  });
}

test('conflicting current titles still reject before any action selection',()=>{
  const f=cardFrame('Strike+',true);f.snapshot.interaction.content.surface.cards[0].name='Strike';
  assert.throws(()=>sharedDecision(f.snapshot,f.reads),/Conflicting current public entity facts/);
});

test('base and upgraded copies keep separate identities and exact raw bindings',()=>{
  const f=cardFrame('Strike',false),a=f.snapshot.interaction.content.surface.cards[0];
  const b={...structuredClone(a),entity_id:'upgraded-copy',name:'Strike+',is_upgraded:true};
  f.snapshot.interaction.content.surface.cards.push(b);
  f.snapshot.interaction.content.surface.selectable_card_entity_ids.push(b.entity_id);
  f.reads[0].content.cards.push(structuredClone(b));f.reads[0].content.card_count=2;
  f.snapshot.referents.push({referent_id:b.entity_id,role:'card',label:b.name,
    properties:structuredClone(b),state:{visible:true,enabled:true}});
  f.snapshot.bound_actions.actions.push({...structuredClone(f.snapshot.bound_actions.actions[0]),
    bound_action_id:'confirm-upgraded',label:'Confirm '+b.name,
    arguments:[{role:'selected_card',referent_id:b.entity_id}]});
  f.snapshot.bound_actions.total_count=f.snapshot.bound_actions.materialized_count=2;
  const frame=sharedDecision(f.snapshot,f.reads),cards=frame.public_input.context.interaction.content.surface.cards;
  assert.notEqual(cards[0].entity_id.public_slot,cards[1].entity_id.public_slot);
  assert.deepEqual(cards.map(c=>[c.name,c.is_upgraded,c.cost]),[['Strike',false,'1'],['Strike+',true,'1']]);
  const upgraded=frame.public_input.candidates.findIndex(c=>c.label==='Confirm Strike+');
  assert.equal(frame.actions[upgraded].bound_action_id,'confirm-upgraded');
  assert.equal(frame.actions[upgraded].raw_index,1);
});
