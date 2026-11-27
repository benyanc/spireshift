import test from 'node:test';import assert from 'node:assert/strict';
import {orderedChoices,projectAtomicSelection,atomicSelectionReads,AtomicSelectionCursor} from './engine-atomic-selection-v1.mjs';
import {requireAtomicCompletion} from './engine-atomic-selection-receipt-v1.mjs';
const helpers={cardProperties:c=>({definition_id:c.id,name:c.name,cost:String(c.cost),type:'Attack',rarity:'Basic',is_upgraded:c.upgraded,description:c.description,stats:c.stats,after_upgrade:c.after_upgrade??null}),visibleText:s=>s?.replace(/\[\/?[a-z]+\]/g,'')??null,withoutDeck:({deck,...p})=>p};
const fixture=()=>({decision:'card_select',cards:[{index:0,native_ref:'private1',id:'STRIKE',name:'Strike',cost:1,upgraded:false,description:'Deal 6 damage',stats:{damage:6}},{index:1,native_ref:'private2',id:'STRIKE',name:'Strike',cost:0,upgraded:true,description:'Deal 9 damage',stats:{damage:9}}],player:{deck:[{native_ref:'private1',id:'STRIKE',upgraded:false},{native_ref:'private2',id:'STRIKE',upgraded:true}],hp:20,max_hp:80},context:{room_type:'Event'},selection_owner:{kind:'event',event_id:'NEOW',name:'Neow',ancient:true,in_dialogue:false},selection_ref:'private-selector',selection_preferences_complete:true,min_select:1,max_select:1,cancelable:false,require_manual_confirmation:false,unpowered_previews:false,pretend_cards_can_be_played:false,prompt:'Remove a card'});
const ctx=()=>({snapshotId:'snapshot',refs:[],actions:[],id:(...a)=>JSON.stringify(a),referent(v){const r={...v,referent_id:v.id,properties:{...v.properties,entity_id:v.id}};this.refs.push(r);return r;},action(v){this.actions.push(v);}});
test('all ordered choices and legal empty answers are present',()=>{const v=orderedChoices(['a','b','c'],0,2,true);assert.equal(v.length,10);assert.ok(v.some(s=>s.join()==='a,b'));assert.ok(v.some(s=>s.join()==='b,a'));assert.deepEqual(v[0],[]);});
test('oversized, duplicate, invalid and unavailable cardinalities reject without truncation',()=>{assert.throws(()=>orderedChoices(Array.from({length:25},(_,i)=>i),0,2,true),/exceeds_bound/);for(const a of [[['a','a'],0,1,false],[['a'],2,2,false],[['a'],1,0,false]])assert.throws(()=>orderedChoices(...a));});
test('one committed native action uses the exact physical copies and complete private selection answer',()=>{const s=fixture(),c=ctx(),out=projectAtomicSelection(s,c,helpers);assert.equal(out.complete,true);assert.equal(c.actions.length,2);assert.equal(out.context.event_id,'NEOW');assert.equal(out.surface.cards[0].is_selected,false);assert.equal(out.surface.cards[1].cost,'0');assert.notEqual(c.refs[0].referent_id,c.refs[1].referent_id);assert.deepEqual(c.actions[1].raw.args,{selection_ref:'private-selector',indices:'1'});assert.equal(c.actions[1].verb,'confirm');assert.equal(c.refs[0].id,c.id('deck_card','private1','STRIKE',false));});
test('decline and commit an empty selection remain different choices',()=>{const s=fixture();s.min_select=0;s.max_select=0;s.cancelable=true;const c=ctx();projectAtomicSelection(s,c,helpers);assert.deepEqual(c.actions.map(a=>[a.verb,a.raw.action]),[['confirm','select_cards'],['cancel','skip_select']]);});
test('selected flags, source ownership and preferences must be supplied by the source',()=>{for(const update of [s=>delete s.selection_owner,s=>delete s.require_manual_confirmation,s=>s.cards[1].native_ref=s.cards[0].native_ref]){const s=fixture();update(s);assert.throws(()=>projectAtomicSelection(s,ctx(),helpers));}});
test('selection detail reads carry the same card and preview facts as the surface',()=>{const s=fixture(),c=ctx(),surface=projectAtomicSelection(s,c,helpers),reads=atomicSelectionReads(s,[],c,helpers);assert.equal(reads.length,2);for(let i=0;i<2;i++){assert.equal(reads[i].descriptor.target_referent_id,surface.surface.cards[i].entity_id);assert.deepEqual(reads[i].content,surface.surface.cards[i]);}});
test('older local UI prefixes cannot be resumed under the committed-choice contract',()=>{const c=new AtomicSelectionCursor();assert.equal(c.observe(fixture()).decision,'card_select');assert.throws(()=>c.handle({cmd:'action',action:'selection_cursor_confirm'}));});
const snapshot={snapshot_id:'s'},action={verb:'confirm',arguments:[{role:'selected_card',referent_id:'card-a'}]};
const proof=()=>({runtime_instance_id:'r',selection:{request_id:'q',root_snapshot_id:'s',status:'committed',chosen_card_ids:['card-a'],game_committed:true,steps:[{kind:'select',card_id:'card-a',candidate_id:'c1',accepted:true},{kind:'confirm',candidate_id:'c2',accepted:true}]}});
test('a model choice is acknowledged only after the exact planned UI chain is verified',()=>assert.equal(requireAtomicCompletion(proof(),snapshot,action,'q','r').status,'committed'));
for(const [name,change]of Object.entries({pending:p=>p.selection.status='pending',wrong_copy:p=>p.selection.chosen_card_ids=['card-b'],wrong_request:p=>p.selection.request_id='other',wrong_runtime:p=>p.runtime_instance_id='other',uncertain_step:p=>p.selection.steps[0].accepted=false,missing_confirm:p=>p.selection.steps.pop(),wrong_root:p=>p.selection.root_snapshot_id='old',extra_selection:p=>p.selection.steps.unshift({kind:'select',card_id:'card-b',candidate_id:'b',accepted:true})}))test(`incomplete/foreign semantic receipt blocks: ${name}`,()=>{const p=proof();change(p);assert.throws(()=>requireAtomicCompletion(p,snapshot,action,'q','r'));});

import {fixture as publicFixture} from './engine-interface-case-bank-v1.mjs';
import {sharedDecision} from './engine-shared-input-v8.mjs';
import {restoreLayout} from './engine-input-layout-v5.mjs';
test('current card-detail endpoint enumeration does not change the strategic input',()=>{
  const row=publicFixture('deck_transform_selection');
  const cards=row.snapshot.interaction.content.surface.cards;
  const extraCard={...structuredClone(cards[0]),entity_id:'artificial-second-card',definition_id:'TEST_SECOND',name:'Second synthetic card'};
  cards.push(extraCard);
  row.reads[0].content.cards.push(structuredClone(extraCard));row.reads[0].content.card_count=2;
  for(const [i,card] of cards.entries()){
    const readId=`detail-${i}`;
    row.snapshot.reads.push({read_id:readId,kind:'surface_card',target_referent_id:card.entity_id,content_schema:'test/current-card',snapshot_bound:true,ordering_semantics:'single_entity',hidden_by_policy:[]});
    row.reads.push({read_id:readId,kind:'surface_card',target_referent_id:card.entity_id,content:structuredClone(card),session:structuredClone(row.reads[0].session),expected_snapshot_id:row.snapshot.snapshot_id,observed_snapshot_id:row.snapshot.snapshot_id,completeness:structuredClone(row.reads[0].completeness),information_policy:structuredClone(row.reads[0].information_policy)});
  }
  const original=structuredClone(row),first=sharedDecision(row.snapshot,row.reads);
  const other=structuredClone(row);other.reads.reverse();other.snapshot.reads.reverse();
  const second=sharedDecision(other.snapshot,other.reads);
  assert.deepEqual(first.public_input,second.public_input);
  assert.deepEqual(row,original);
  assert.equal(restoreLayout(first.layout_evidence).schema_version,'actual-engine-public-entity-graph-v1');
});
