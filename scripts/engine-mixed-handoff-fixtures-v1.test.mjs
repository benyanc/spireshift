import test from "node:test";
import assert from "node:assert/strict";
import {mixedFixture} from "./engine-mixed-handoff-fixtures-v1.mjs";

const spec={seed:"SP1RESH1FTMHTEST1",family:"rest",hp:31,deck:["BASH"],girya:2,second_rest:true};
function original() {
  return {rng:{seed:spec.seed},ascension:8,current_act_index:0,visited_map_coords:[{row:0,col:0}],
    acts:[{saved_map:{start:{coord:{row:0,col:0},type:"monster"},points:[
      {coord:{row:1,col:0},type:"monster"},{coord:{row:2,col:0},type:"event"}]}}],
    players:[{max_hp:80,current_hp:31,gold:1000,deck:[{id:"CARD.BASH"}],
      relics:[{id:"RELIC.GIRYA",props:{ints:[{name:"TimesLifted",value:0}]}}],
      odds:{potion_reward_odds_value:0.4},relic_grab_bag:{relic_id_lists:{shop:["RELIC.KIFUDA","RELIC.OTHER"]}}}]};
}
test("diagnostic map and cap setup preserves the native source save",()=>{
  const source=original(), bytes=JSON.stringify(source), value=mixedFixture(source,spec);
  assert.equal(JSON.stringify(source),bytes);
  assert.equal(value.acts[0].saved_map.start.type,"rest_site");
  assert.equal(value.acts[0].saved_map.points[0].type,"rest_site");
  assert.equal(value.acts[0].saved_map.points[1].type,"monster");
  assert.equal(value.players[0].relics[0].props.ints[0].value,2);
});
test("the potion reward branch is explicit and preserves native potion generation",()=>{
  const value=mixedFixture(original(),{...spec,family:"reward",girya:undefined,second_rest:false});
  assert.equal(value.players[0].odds.potion_reward_odds_value,1);
  assert.equal(value.players[0].deck.length,5);
  assert.equal(value.acts[0].saved_map.start.type,"monster");
  assert.equal(value.players[0].potions,undefined);
});
test("setup fails on a different world, changed player or already-used Girya",()=>{
  for (const change of [value=>value.rng.seed="OTHER",value=>value.players[0].gold=900,
    value=>value.players[0].relics[0].props.ints[0].value=1]) {
    const value=original();change(value);assert.throws(()=>mixedFixture(value,spec));
  }
});
test("Kifuda ordering uses its existing occurrence without duplicating stock",()=>{
  const value=mixedFixture(original(),{...spec,family:"shop",second_rest:false,kifuda:true});
  assert.deepEqual(value.players[0].relic_grab_bag.relic_id_lists.shop,["RELIC.OTHER","RELIC.KIFUDA"]);
  const bad=original();bad.players[0].relic_grab_bag.relic_id_lists.shop.push("RELIC.KIFUDA");
  assert.throws(()=>mixedFixture(bad,{...spec,kifuda:true}));
});
