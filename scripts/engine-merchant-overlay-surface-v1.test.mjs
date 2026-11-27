import test from "node:test";
import assert from "node:assert/strict";
import {merchantMapTarget} from "./engine-merchant-overlay-surface-v1.mjs";

const state=()=>({decision:"map_select",context:{room_type:"Shop"},
  merchant_map_target:{contract:"native_current_merchant_room_under_map_v1",
    room_ref:"actual-room",merchant_ref:"actual-button",inventory_open:false},
  player:{potions:[{id:"FOUL_POTION",can_use:true,target_type:"TargetedNoCreature",
    valid_target_refs:["actual-button"]}]}});

test("target permission requires the exact current native merchant operand under the map",()=>{
  const input=state();assert.equal(merchantMapTarget(input),input.merchant_map_target);
  assert.deepEqual(input,state());
  for(const edit of [s=>s.player.potions[0].valid_target_refs=["another-button"],
    s=>s.player.potions[0].valid_target_refs.push("another-button"),
    s=>s.player.potions[0].id="OTHER_POTION"]) {
    const invalid=state();edit(invalid);assert.throws(()=>merchantMapTarget(invalid),/operand/u);
  }
});

test("an overlay witness cannot authorize another room, owner or open inventory",()=>{
  for(const edit of [s=>s.decision="shop",s=>s.context.room_type="RestSite",
    s=>s.merchant_map_target.inventory_open=true,s=>s.merchant_map_target.room_ref=null,
    s=>s.merchant_map_target.merchant_ref="",s=>s.merchant_map_target.contract="unknown"]) {
    const invalid=state();edit(invalid);assert.throws(()=>merchantMapTarget(invalid),/Unqualified/u);
  }
  assert.equal(merchantMapTarget({decision:"combat_play"}),null);
  const input=state();input.player.potions=[];
  assert.equal(merchantMapTarget(input),input.merchant_map_target);
});
