import test from "node:test";
import assert from "node:assert/strict";
import { fixture,caseBank } from "./engine-interface-case-bank-v1.mjs";
import { sharedDecision as old } from "./engine-shared-input-v3.mjs";
import { sharedDecision,deliveredAction } from "./engine-shared-input-v4.mjs";
import { normalizeLayout,restoreLayout } from "./engine-input-layout-v1.mjs";
import { canonicalSeed,requireCanonicalSeed,verifyEpisodeSeed } from "./engine-seed-contract-v1.mjs";
import { observationBoundary } from "./engine-observation-boundary-v1.mjs";
import { observationDeadline } from "./engine-observation-boundary-v2.mjs";

function pair() {
  const official=fixture("event_option","official"),native=fixture("event_option","native");
  for(const row of [native,official]) {
    const p=row.snapshot.persistent.content;
    p.player.character_name="The Ironclad";p.run.act_name="Underdocks";
    p.run.bosses=[{definition_id:"TEST_BOSS",name:"Test boss",order:0}];
    Object.assign(row.snapshot.interaction.content.context,{event_id:"TEST_EVENT",name:"Test event",ancient:false,in_dialogue:false});
  }
  const content=native.snapshot.interaction.content,p=native.snapshot.persistent.content;
  native.snapshot.interaction.stage="choosing";native.snapshot.interaction.prompt=null;
  Object.assign(content.surface,{stage:"choosing",title:"Test event",description:null,potion_states:[]});
  content.context.player={character_id:"IRONCLAD",name:"The Ironclad",hp:41,max_hp:80,gold:99,
    block:0,deck_size:1,relics:[{id:"TEST_RELIC",counter:2}],potions:[]};
  content.context.run={act:1,act_index:0,act_definition_id:"UNDERDOCKS",act_name:"Underdocks",floor:3,total_floor:3,
    ascension:8,room_type:"Event",boss:{id:"TEST_BOSS",name:"Test boss"},bosses:[{id:"TEST_BOSS",name:"Test boss",order:0}]};
  for(const option of [content.surface.options[0],native.snapshot.referents.at(-1).properties])
    Object.assign(option,{text_key:"TEST_EVENT.pages.INITIAL.options.ONE",variables:null});
  native.snapshot.referents.push({referent_id:"extra-player",role:"player",label:"The Ironclad",state:{visible:true},
    properties:{entity_id:"extra-player",hp:41,max_hp:80}});
  return {native,official};
}

test("complete typed alternate layouts produce identical public inputs and semantic action keys",()=>{
  const {native,official}=pair(),a=sharedDecision(native.snapshot,native.reads),b=sharedDecision(official.snapshot,official.reads);
  assert.deepEqual(a.public_input,b.public_input);assert.deepEqual(a.actions.map(x=>x.key),b.actions.map(x=>x.key));
  for(const [row,frame]of [[native,a],[official,b]]) {
    assert.deepEqual(restoreLayout(frame.layout_evidence),old(row.snapshot,row.reads).public_input);
    for(let i=0;i<frame.actions.length;i++)assert.equal(deliveredAction(frame,{binding_id:frame.binding_id,action_index:i},row.snapshot).bound_action_id,frame.actions[i].bound_action_id);
  }
});

for(const row of caseBank())test(`typed layout retains complete bindings and exact reconstruction: ${row.key}`,()=>{
  const prior=structuredClone(row),a=sharedDecision(row.snapshot,row.reads);
  assert.equal(a.actions.length,row.snapshot.bound_actions.actions.length);assert.deepEqual(row,prior);
  assert.deepEqual(restoreLayout(a.layout_evidence),old(row.snapshot,row.reads).public_input);
  if(!a.terminal)for(let i=0;i<a.actions.length;i++)assert.ok(deliveredAction(a,{binding_id:a.binding_id,action_index:i},row.snapshot));
});

const probes={
  deck_definition:x=>{x.context.reads[0].content.cards[0].definition_id="OTHER_CARD";},
  current_card_cost:x=>{x.context.reads[0].content.cards[0].cost="0";},
  per_copy_upgrade:x=>{x.context.reads[0].content.cards[0].is_upgraded=true;},
  relic_identity:x=>{x.context.persistent.player.relics[0].definition_id="OTHER_RELIC";},
  relic_counter:x=>{x.context.persistent.player.relics[0].counter=7;},
  named_amount_owner:x=>{x.context.interaction.content.context.player.statuses.reverse();},
  named_amount_value:x=>{x.context.interaction.content.context.player.statuses[0].amount=7;},
  unfamiliar_public_fact:x=>{x.context.interaction.content.surface.future_rule={amount:3,owner:x.context.persistent.player.entity_id};},
  optional_skip:x=>{x.candidates.push({verb:"skip",label:"Skip",subject:null,arguments:[],history:{shop_inspected:false}});},
  unknown_nullable:x=>{x.context.interaction.content.surface.future_nullable=null;},
};
for(const [key,change]of Object.entries(probes))test(`meaningful state/action remains distinct: ${key}`,()=>{
  const f=fixture(),input=old(f.snapshot,f.reads).public_input,a=normalizeLayout(input),changed=structuredClone(input);change(changed);
  const b=normalizeLayout(changed);assert.notDeepEqual(a.public_input,b.public_input);assert.deepEqual(restoreLayout(b),changed);
});

test("foreign current-player owners and extra fields cannot be collapsed into the local HUD",()=>{
  const {native}=pair(),input=old(native.snapshot,native.reads).public_input;
  input.context.interaction.content.context.player.owner_entity_id=input.context.reads[0].content.cards[0].entity_id;
  const result=normalizeLayout(input);assert.equal(result.public_input.context.interaction.content.context.player.hp,41);
  assert.deepEqual(restoreLayout(result),input);
});
test("nonzero outside-combat block and later-act local floors remain explicit, not guessed",()=>{
  const {native}=pair(),input=old(native.snapshot,native.reads).public_input;
  input.context.interaction.content.context.player.block=7;
  input.context.persistent.run.act=2;input.context.interaction.content.context.run.act=2;
  input.context.interaction.content.context.run.act_index=1;input.context.persistent.run.floor=21;
  input.context.interaction.content.context.run.total_floor=21;
  const result=normalizeLayout(input);
  assert.equal(result.public_input.context.interaction.content.context.player.block,7);
  assert.equal(result.public_input.context.interaction.content.context.run.floor,3);
});
test("conflicting duplicated current HUD facts reject the decision instead of disappearing",()=>{
  const {native}=pair();native.snapshot.interaction.content.context.player.gold=5;
  assert.throws(()=>sharedDecision(native.snapshot,native.reads),/Conflicting layout/);
});
test("Shop room enums collapse exactly; event-owned shop room facts remain visible",()=>{
  const f=fixture("shop_inventory"),input=old(f.snapshot,f.reads).public_input;
  input.context.interaction.content.context.run={room_type:"Shop"};
  const ordinary=normalizeLayout(input);assert.equal(ordinary.public_input.context.interaction.content.context.run,undefined);
  input.context.interaction.content.context.run.room_type="Event";
  const event=normalizeLayout(input);assert.equal(event.public_input.context.interaction.content.context.run.room_type,"Event");
  assert.deepEqual(event.unresolved,[]);assert.deepEqual(restoreLayout(event),input);
});
test("missing event metadata in old captures is not synthesized from text keys or titles",()=>{
  const {native}=pair();delete native.snapshot.interaction.content.context.event_id;
  const result=sharedDecision(native.snapshot,native.reads);assert.equal(result.public_input.context.interaction.content.context.event_id,undefined);
});
test("required selected/enablement booleans are never filled by nullable-field normalization",()=>{
  const f=fixture("deck_transform_selection"),input=old(f.snapshot,f.reads).public_input;
  delete input.context.interaction.content.surface.can_confirm;
  const result=normalizeLayout(input);assert.equal(result.public_input.context.interaction.content.surface.can_confirm,undefined);
});
test("typed-null changes are idempotent and reconstruction evidence is tamper evident",()=>{
  const {native}=pair(),a=normalizeLayout(old(native.snapshot,native.reads).public_input);
  assert.deepEqual(normalizeLayout(a.public_input).public_input,a.public_input);
  const broken=structuredClone(a);broken.public_input.context.persistent.player.hp++;
  assert.throws(()=>restoreLayout(broken),/Changed layout/);
});
test("canonical seed treatment agrees with the actual game's O/I substitutions",()=>{
  assert.equal(canonicalSeed(" oiabc123 "),"01ABC123");
  assert.equal(requireCanonicalSeed("SP1RESH1FTLAY0UT101"),"SP1RESH1FTLAY0UT101");
  for(const seed of["SP1RESH1FTSCOPECTRL003","abc"," A1 ","A-B","ß","",null])assert.throws(()=>requireCanonicalSeed(seed));
});
test("same-seed evaluation requires actual matching official episode provenance",()=>{
  const p={status:"seed_observed",runtime_instance_id:"runtime",requested_seed:"A123",actual_seed:"A123",seed_matches:true};
  assert.equal(verifyEpisodeSeed(p,"A123","runtime").status,"exact_episode_seed_verified");
  for(const change of[{actual_seed:"B123"},{requested_seed:"B123"},{seed_matches:false},{runtime_instance_id:"foreign"},{status:"seed_configured"}])
    assert.throws(()=>verifyEpisodeSeed({...p,...change},"A123","runtime"));
});
test("explicit unsupported states stop immediately, settling waits, and only fresh complete public states pass",()=>{
  const s={session:{runtime_instance_id:"r"},snapshot_id:"s",information_policy:{includes_hidden_information:false},completeness:{status:"complete"},status:"interactive"};
  assert.equal(observationBoundary(s,"r"),"ready");assert.equal(observationBoundary(s,"r","s"),"wait");
  assert.equal(observationBoundary({...s,status:"settling"},"r"),"wait");
  for(const status of["visible_unsupported","unsupported","invented"])assert.throws(()=>observationBoundary({...s,status},"r"));
  assert.throws(()=>observationBoundary(s,"foreign"));
  assert.throws(()=>observationBoundary({...s,information_policy:{includes_hidden_information:true}},"r"));
});
test("ready-state normalization preserves repeated rest choices and the optional exit",()=>{
  const x=fixture("rest_site"),labels=["Rest","Smith","Hatch","Leave rest site"];
  x.snapshot.bound_actions.actions=labels.map((label,i)=>({bound_action_id:`rest-${i}`,
    interaction_id:x.snapshot.interaction.interaction_id,verb:"activate",label,arguments:[]}));
  x.snapshot.bound_actions.total_count=x.snapshot.bound_actions.materialized_count=labels.length;
  x.snapshot.interaction.content.surface.remaining_uses=2;
  const f=sharedDecision(x.snapshot,x.reads);
  assert.deepEqual(f.public_input.candidates.map(c=>c.label).sort(),[...labels].sort());
  assert.equal(f.public_input.context.interaction.content.surface.remaining_uses,2);
  assert.equal(f.actions.length,4);
  assert.deepEqual(restoreLayout(f.layout_evidence),old(x.snapshot,x.reads).public_input);
});
test("outside-combat Foul Potion retains its exact merchant target and raw delivery",()=>{
  const x=fixture("shop_room");
  x.snapshot.referents.push({referent_id:"merchant",role:"merchant",label:"Merchant",state:{visible:true},
    properties:{entity_id:"merchant",target_type:"merchant"}},
  {referent_id:"foul",role:"potion",label:"Foul Potion",state:{visible:true,enabled:true},
    properties:{entity_id:"foul",definition_id:"FOUL_POTION",usage:"AnyTime",slot:0}});
  x.snapshot.bound_actions.actions.push({bound_action_id:"throw-foul",interaction_id:x.snapshot.interaction.interaction_id,
    verb:"use",label:"Use Foul Potion on Merchant",subject_referent_id:"foul",arguments:[{role:"target",referent_id:"merchant"}]});
  x.snapshot.bound_actions.total_count=x.snapshot.bound_actions.materialized_count=x.snapshot.bound_actions.actions.length;
  const f=sharedDecision(x.snapshot,x.reads),i=f.public_input.candidates.findIndex(c=>c.verb==="use");
  assert.equal(f.public_input.candidates[i].arguments[0].entity.role,"merchant");
  assert.equal(deliveredAction(f,{binding_id:f.binding_id,action_index:i},x.snapshot).arguments[0].referent_id,"merchant");
});
test("identical card definitions with different current costs remain separate physical action operands",()=>{
  const x=fixture(),card=structuredClone(x.reads[0].content.cards[0]);card.entity_id="discounted-copy";card.cost="0";
  x.reads[0].content.cards.push(card);x.reads[0].content.card_count=2;
  x.snapshot.interaction.content.context.player.hand.push(structuredClone(card));
  x.snapshot.referents.push({referent_id:card.entity_id,role:"card",label:"Test card",state:{visible:true,enabled:true},properties:structuredClone(card)});
  x.snapshot.bound_actions.actions.push({bound_action_id:"play-copy",interaction_id:x.snapshot.interaction.interaction_id,
    verb:"play",label:"Play test card",subject_referent_id:card.entity_id,arguments:[]});
  x.snapshot.bound_actions.total_count=x.snapshot.bound_actions.materialized_count=x.snapshot.bound_actions.actions.length;
  const f=sharedDecision(x.snapshot,x.reads),plays=f.public_input.candidates.filter(c=>c.verb==="play");
  assert.equal(new Set(plays.map(c=>c.subject.public_slot)).size,2);
  assert.deepEqual(plays.map(c=>c.subject.properties.cost).sort(),["0","1"]);
  const i=f.public_input.candidates.findIndex(c=>c.subject?.properties.cost==="0");
  assert.equal(deliveredAction(f,{binding_id:f.binding_id,action_index:i},x.snapshot).subject_referent_id,"discounted-copy");
});
test("runtime handles and current action/referent enumeration cannot change canonical policy inputs",()=>{
  const a=fixture("combat_turn","first"),b=fixture("combat_turn","second");
  b.snapshot.referents.reverse();b.snapshot.bound_actions.actions.reverse();
  assert.deepEqual(sharedDecision(a.snapshot,a.reads).public_input,sharedDecision(b.snapshot,b.reads).public_input);
});
test("a nonempty unfamiliar formatting-variable payload remains represented",()=>{
  const {native}=pair();native.snapshot.interaction.content.surface.options[0].variables={future:7};
  native.snapshot.referents.at(-2).properties.variables={future:7};
  const f=sharedDecision(native.snapshot,native.reads);
  assert.deepEqual(f.public_input.context.interaction.content.surface.options[0].variables,{future:7});
});
test("contradictory event text owners reject instead of selecting a preferred version",()=>{
  const {native}=pair();native.snapshot.interaction.content.surface.title="Different event";
  assert.throws(()=>sharedDecision(native.snapshot,native.reads),/Conflicting event text/);
});
test("startup loading has a bounded window without extending read/delivery or whole-case deadlines",()=>{
  assert.equal(observationDeadline(1000,100000,100000,true),46000);
  assert.equal(observationDeadline(1000,100000,100000),16000);
  assert.equal(observationDeadline(1000,10000,100000,true),10000);
  assert.equal(observationDeadline(1000,100000,9000,true),9000);
  assert.throws(()=>observationDeadline(0,Infinity,100));
});
