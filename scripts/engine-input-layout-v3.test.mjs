import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {fixture,caseBank} from './engine-interface-case-bank-v1.mjs';
import {sharedDecision,deliveredAction} from './engine-shared-input-v6.mjs';
import {normalizeLayout,restoreLayout} from './engine-input-layout-v3.mjs';
import {scopedCardSelections} from './engine-interface-scopes-v2.mjs';
import {stableJson} from './engine-public-input-v1.mjs';
const hash=value=>createHash('sha256').update(stableJson(value)).digest('hex');
function roundTrip(frame){assert.equal(hash(restoreLayout(frame.layout_evidence)),frame.layout_evidence.original_digest);}
for(const row of caseBank())test(`layout v2 preserves public source and raw action authority: ${row.key}`,()=>{
  const before=structuredClone(row),frame=sharedDecision(row.snapshot,row.reads);
  assert.deepEqual(row,before);roundTrip(frame);
  assert.equal(frame.actions.length,row.snapshot.bound_actions.actions.length);
  if(!frame.terminal)for(let i=0;i<frame.actions.length;i++)assert.equal(
    deliveredAction(frame,{binding_id:frame.binding_id,action_index:i},row.snapshot).bound_action_id,frame.actions[i].bound_action_id);
});
test('base pile stats and target-dependent combat previews retain their distinct current owners',()=>{
  const row=fixture(),id=row.reads[0].content.cards[0].entity_id;
  row.reads[0].content.cards[0].stats={damage:6};
  const card=row.snapshot.interaction.content.context.player.hand.find(c=>c.entity_id===id);
  assert.ok(card);card.stats={damage:9};
  const frame=sharedDecision(row.snapshot,row.reads),text=stableJson(frame.public_input);
  assert.match(text,/"damage":6/);assert.match(text,/"damage":9/);roundTrip(frame);
});
test('upgrade previews, negative costs and modifiers survive as public learning features',()=>{
  const row=fixture();
  const id=row.reads[0].content.cards[0].entity_id;
  function update(v){if(Array.isArray(v))return v.forEach(update);if(!v||typeof v!=='object')return;
    if(v.entity_id===id)Object.assign(v,{cost:'X',keywords:['Exhaust'],after_upgrade:{stats:{damage:12},added_keywords:['Retain']},affliction:{definition_id:'TEST_AFFLICTION',amount:2}});
    Object.values(v).forEach(update);}
  update(row);
  const frame=sharedDecision(row.snapshot,row.reads);roundTrip(frame);
  const card=frame.public_input.context.reads[0].content.cards[0];
  assert.equal(card.cost,'X');assert.deepEqual(card.keywords,['Exhaust']);assert.equal(card.affliction.amount,2);
  assert.ok(Object.values(card.public_card_views).some(v=>v.after_upgrade?.stats.damage===12));
});
test('selection flags come from the source and are never invented for old missing data',()=>{
  const row=fixture('deck_transform_selection'),original=structuredClone(row);
  const id=row.snapshot.interaction.content.surface.cards[0].entity_id;
  row.snapshot.interaction.content.surface.cards[0].is_selected=true;
  row.snapshot.interaction.content.surface.selected_card_entity_ids=[id];
  row.snapshot.interaction.content.surface.selected_count=1;
  const a=sharedDecision(row.snapshot,row.reads),b=sharedDecision(original.snapshot,original.reads);
  assert.notDeepEqual(a.public_input,b.public_input);roundTrip(a);
  const scoped=scopedCardSelections(original.snapshot,original.reads);
  assert.equal(scoped.snapshot.interaction.content.surface.cards[0].is_selected,undefined);
});
test('capability declarations are unordered, while named status amounts stay attached',()=>{
  const row=fixture();row.snapshot.interaction.capabilities=[{kind:'b'},{kind:'a'}];
  const a=sharedDecision(row.snapshot,row.reads);
  const other=structuredClone(row);other.snapshot.interaction.capabilities.reverse();
  const b=sharedDecision(other.snapshot,other.reads);assert.deepEqual(a.public_input,b.public_input);
  const input=structuredClone(a.public_input),statuses=input.context.interaction.content.context.player.statuses;
  statuses[0].amount=7;statuses[1].amount=2;
  assert.notDeepEqual(normalizeLayout(input).public_input,a.public_input);
});
test('card view contradictions reject while public view differences remain learnable',()=>{
  const row=fixture();row.snapshot.interaction.content.context.player.hand[0].stats={block:8};
  row.reads[0].content.cards[0].stats={block:5};
  assert.doesNotThrow(()=>sharedDecision(row.snapshot,row.reads));
  row.snapshot.interaction.content.context.player.hand[0].enchantment={definition_id:'A',amount:2};
  row.snapshot.interaction.content.context.player.hand[0].existing_enchantment={definition_id:'B',amount:2};
  assert.throws(()=>sharedDecision(row.snapshot,row.reads),/Conflicting public enchantment/);
});
test('unfamiliar fields on modifiers remain explicit',()=>{
  const row=fixture();row.reads[0].content.cards[0].enchantment={definition_id:'A',amount:2,observation_source:'future_semantics',extra:{amount:7}};
  const frame=sharedDecision(row.snapshot,row.reads);roundTrip(frame);
  const item=frame.public_input.context.reads[0].content.cards[0].existing_enchantment;
  assert.equal(item.observation_source,'future_semantics');assert.equal(item.extra.amount,7);
});
test('late map floors and nonempty potion belts are not erased',()=>{
  const row=fixture('map_navigation'),frame=sharedDecision(row.snapshot,row.reads),input=structuredClone(frame.public_input);
  input.context.persistent.run.act=2;input.context.persistent.run.floor=21;
  input.context.interaction.content.context.run={act:2,act_index:1,total_floor:21,floor:3};
  input.context.interaction.content.surface.potion_states=[{slot:0,definition_id:'FOUL_POTION',can_discard:true}];
  const result=normalizeLayout(input);assert.equal(result.public_input.context.interaction.content.context.run.floor,3);
  assert.equal(result.public_input.context.interaction.content.surface.potion_states.length,1);assert.deepEqual(restoreLayout(result),input);
});

for(const [raw,expected]of [[0,"0"],[2,"2"],["X","X"],[null,null]])test(`typed card star cost ${raw} preserves its meaning`,()=>{
  const f=fixture(),frame=sharedDecision(f.snapshot,f.reads),input=structuredClone(frame.public_input);
  input.context.reads[0].content.cards[0].star_cost=raw;
  const normalized=normalizeLayout(input);
  assert.equal(normalized.public_input.context.reads[0].content.cards[0].star_cost,expected);
  assert.deepEqual(restoreLayout(normalized),input);
});
test("zero and X star costs remain different while unrelated numeric resources remain numeric",()=>{
  const f=fixture(),input=sharedDecision(f.snapshot,f.reads).public_input;
  const a=structuredClone(input),b=structuredClone(input);
  a.context.reads[0].content.cards[0].star_cost=0;b.context.reads[0].content.cards[0].star_cost="X";
  a.context.interaction.content.context.player.stars=2;
  const out=normalizeLayout(a).public_input;
  assert.equal(typeof out.context.interaction.content.context.player.stars,"number");
  assert.notDeepEqual(out,normalizeLayout(b).public_input);
});
