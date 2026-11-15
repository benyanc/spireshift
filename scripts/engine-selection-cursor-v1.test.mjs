import test from "node:test";
import assert from "node:assert/strict";
import { SelectionCursor, exceedsLimit, additions, projectSelectionSurface } from "./engine-selection-cursor-v1.mjs";
const state = (n=21,min=5,max=5,cancelable=false) => ({ type: "decision", decision: "card_select", selection_ref: "PRIVATE",
  cards: Array.from({length:n},(_,index)=>({index,name:`Card ${index}`,id:`CARD_${index}`})), min_select:min,max_select:max,cancelable,
  require_manual_confirmation:false,unpowered_previews:false,pretend_cards_can_be_played:false,selection_preferences_complete:true });
const request = (cursor, action, extra={}) => ({cmd:"action",action:`selection_cursor_${action}`,args:{ selection_ref:"PRIVATE",prefix:cursor.active.selected.join(","),...extra }});
test("large 21-choose-5 and 15-up-to-3 menus use bounded ordered prefixes",()=>{
  for(const s of [state(),state(15,0,3)]) {
    assert.equal(exceedsLimit(s.cards.length,s.min_select,s.max_select,s.cancelable),true);
    const c=new SelectionCursor();c.observe(s);
    for(const index of [0,3,8].slice(0,s.max_select)) {
      const r=c.handle(request(c,"add",{index}));assert.equal(r.local,true);
      assert.ok(additions(s,c.active.selected).every(i=>!c.active.selected.includes(i)));
    }
  }
});
test("ordered prefixes reach every valid subset and every native order",()=>{
  for(let n=1;n<=7;n++) for(let min=0;min<=n;min++) for(let max=min;max<=n;max++) {
    const s=state(n,min,max);const seen=[];
    const visit=prefix=>{ if(prefix.length>=min)seen.push([...prefix].sort((a,b)=>a-b).join(","));for(const i of additions(s,prefix))visit([...prefix,i]); };
    visit([]);const expected=[];
    for(let mask=0;mask<2**n;mask++){const indices=Array.from({length:n},(_,i)=>i).filter(i=>mask&(1<<i));if(indices.length>=min&&indices.length<=max)expected.push(indices.join(","));}
    assert.deepEqual([...new Set(seen)].sort(),expected.sort());
  }
});
test("a native selection commits once with exact original indices; no native action for additions",()=>{
  const c=new SelectionCursor();c.observe(state());
  for(const index of [20,19,18,17,16])assert.equal(c.handle(request(c,"add",{index})).local,true);
  assert.deepEqual(c.handle(request(c,"confirm")).native,{cmd:"action",action:"select_cards",args:{selection_ref:"PRIVATE",indices:"20,19,18,17,16"}});
  assert.throws(()=>c.handle({cmd:"action",action:"selection_cursor_confirm"}),/pending/);
});
test("empty confirmation and native cancellation remain distinct",()=>{
  const c=new SelectionCursor();c.observe(state(15,0,3,true));
  assert.equal(c.handle(request(c,"confirm")).native.action,"select_cards");
  c.observe(state(15,0,3,true));assert.equal(c.handle(request(c,"cancel")).native.action,"skip_select");
  c.observe(state());assert.throws(()=>c.handle(request(c,"cancel")),/Unadvertised/);
});
test("stale, duplicate and incomplete prefixes never reach native commit",()=>{
  const c=new SelectionCursor();c.observe(state());
  assert.throws(()=>c.handle(request(c,"confirm")),/count/);
  c.handle(request(c,"add",{index:3}));
  for(const index of [3,-1,21])assert.throws(()=>c.handle(request(c,"add",{index})),/Unadvertised/);
  assert.throws(()=>c.handle({...request(c,"add",{index:4}),args:{selection_ref:"PRIVATE",prefix:"",index:4}}),/Stale/);
  assert.throws(()=>c.observe({...state(),max_select:6}),/changed/);
});
test("small menus are unchanged; missing native preferences still fail closed",()=>{
  const c=new SelectionCursor();const s=state(8,2,2);assert.equal(c.observe(s),s);assert.equal(c.active,null);
  for(const key of ["selection_ref","cancelable","selection_preferences_complete"]){const malformed=state();delete malformed[key];assert.equal(c.observe(malformed),malformed);assert.equal(c.active,null);}
});
test("public selection UI has card operands and own-prefix flags, never native handles",()=>{
  const c=new SelectionCursor();const s=c.observe(state());let id=0;const actions=[];
  const result=projectSelectionSurface(s,{referent:x=>({...x,referent_id:`r${id++}`}),action:x=>actions.push(x)},
    {cardProperties:x=>({name:x.name}),withoutDeck:x=>x,visibleText:x=>x??null});
  assert.equal(result.complete,true);assert.equal(result.kind,"card_selection");
  assert.ok(actions.length<=21);assert.ok(actions.every(a=>a.verb==="select"));
  assert.equal(JSON.stringify(result).includes("PRIVATE"),false);
});
