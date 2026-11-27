import test from "node:test";
import assert from "node:assert/strict";
import {ownedPhysicalId,ownedCatalogContext} from "./engine-owned-inventory-identity-v1.mjs";

const context = {snapshotId:"current",id:(kind,...parts)=>JSON.stringify([kind,...parts])};
function state() {
  return {shop_catalog:{},player:{
    relics:[{native_ref:"r1",id:"SAME"},{native_ref:"r2",id:"SAME"}],
    deck:[{native_ref:"c1",id:"STRIKE",upgraded:false},{native_ref:"c2",id:"STRIKE",upgraded:false}],
    potions:[{native_ref:"p1",id:"BLOOD_POTION"},{native_ref:"p2",id:"BLOOD_POTION"}],
  }};
}

for (const [kind,key,prefix] of [["relic","relics","r"],["card","deck","c"],["potion","potions","p"]]) {
  test(`${kind} uses exact source identity and preserves duplicate physical copies`,()=>{
    const source=state();
    assert.notEqual(ownedPhysicalId(source,context,kind,prefix+"1"),ownedPhysicalId(source,context,kind,prefix+"2"));
    assert.equal(ownedPhysicalId(source,context,kind,"another-copy"),null);
    assert.deepEqual(source,state());
  });
  test(`${kind} rejects ambiguous or absent physical provenance`,()=>{
    const source=state();source.player[key][1].native_ref=source.player[key][0].native_ref;
    assert.throws(()=>ownedPhysicalId(source,context,kind,prefix+"1"),/duplicate/u);
    delete source.player[key][0].native_ref;
    assert.throws(()=>ownedPhysicalId(source,context,kind,prefix+"1"),/Incomplete/u);
  });
}

test("catalog and inventory reuse the same source object, with independent offer and slot identities",()=>{
  const ctx=ownedCatalogContext(state(),context);
  assert.equal(ctx.id("shop_relic","current","r2"),context.id("relic","current","r2",1));
  assert.equal(ctx.id("shop_card","current","c2"),context.id("deck_card","c2","STRIKE",false));
  for(const kind of ["shop_entry","shop_slot","shop_relic","shop_card","shop_potion"])
    assert.equal(ctx.id(kind,"current","new-copy"),context.id(kind,"current","new-copy"));
  assert.throws(()=>ctx.id("shop_relic","stale","r2"),/scope/u);
});

test("a matching name or definition never joins a different offered instance",()=>{
  const source=state(),ctx=ownedCatalogContext(source,context);
  assert.notEqual(ctx.id("shop_relic","current","new-copy"),ownedPhysicalId(source,context,"relic","r1"));
  assert.equal(ownedCatalogContext({player:source.player},context),context);
});
