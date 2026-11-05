import test from "node:test";
import assert from "node:assert/strict";
import { stageAct, entrySave } from "./engine-win-curriculum-save-v1.mjs";

function save(){return {ascension:8,current_act_index:0,players:[{net_id:1,current_hp:60,max_hp:80,gold:100,deck:[{id:"CARD.BASH"},{id:"CARD.STRIKE_IRONCLAD"}]}],
  rng:{secret:"unchanged"},acts:[{id:"ACT.UNDERDOCKS",rooms:{}},{id:"ACT.HIVE",rooms:{}},{id:"ACT.GLORY",rooms:{}}]};}
const scenario={act:3,act_definition:"GLORY",boss:"QUEEN_BOSS",entry:"boss",profile:{upgrades:1}};

test("native act staging preserves RNG and original save; upgrades only declared cards",()=>{
  const original=save(),before=structuredClone(original),value=stageAct(original,scenario);
  assert.deepEqual(original,before);assert.deepEqual(value.rng,original.rng);
  assert.equal(value.current_act_index,2);assert.deepEqual(value.visited_map_coords,[]);
  assert.equal(value.acts[2].rooms.boss_id,"ENCOUNTER.QUEEN_BOSS");
  assert.equal(value.players[0].deck[0].current_upgrade_level,1);
  assert.equal(value.players[0].deck[1].current_upgrade_level,undefined);
  assert.equal(value.players[0].max_energy,undefined);
});
test("wrong ascension or native act definition is rejected",()=>{
  assert.throws(()=>stageAct({...save(),ascension:10},scenario));
  assert.throws(()=>stageAct(save(),{...scenario,act_definition:"HIVE"}));
});
test("limited upgrades follow declared strategic priorities without reordering the deck",()=>{
  const original=save();original.players[0].deck=[{id:"CARD.POMMEL_STRIKE"},{id:"CARD.BARRICADE"}];
  const value=stageAct(original,{...scenario,profile:{upgrades:1,upgrade_priority:["BARRICADE"]}});
  assert.equal(value.players[0].deck[0].current_upgrade_level,undefined);
  assert.equal(value.players[0].deck[1].current_upgrade_level,1);
  assert.deepEqual(value.players[0].deck.map(c=>c.id),original.players[0].deck.map(c=>c.id));
});
function mapped(){const value=stageAct(save(),scenario);value.acts[2].saved_map={
  start:{coord:{row:0,col:0},type:"ancient",children:[{row:1,col:0}]},
  points:[{coord:{row:1,col:0},type:"shop",children:[{row:2,col:0}]},
          {coord:{row:2,col:0},type:"rest_site",children:[{row:3,col:0}]}],
  boss:{coord:{row:3,col:0},type:"boss",children:[]}};return value;}
test("boss starts use an existing native connected map path",()=>{
  const value=mapped(),before=structuredClone(value),prepared=entrySave(value,scenario);
  assert.deepEqual(value,before);
  assert.deepEqual(prepared.visited_map_coords,[{row:0,col:0},{row:1,col:0},{row:2,col:0},{row:3,col:0}]);
  assert.deepEqual(prepared.acts,value.acts);assert.deepEqual(prepared.rng,value.rng);
  assert.equal(prepared.map_point_history[2].length,3);
  assert.ok(prepared.map_point_history[2].every(e=>e.rooms.length===0 && e.player_stats.length===1));
  assert.deepEqual(prepared.map_point_history[2][0].player_stats,
    [{player_id:1,current_hp:60,max_hp:80,current_gold:100}]);
});
test("preboss rest and shop choose actual native points; missing events fail",()=>{
  assert.equal(entrySave(mapped(),{...scenario,entry:"preboss"}).visited_map_coords.at(-1).row,2);
  assert.equal(entrySave(mapped(),{...scenario,entry:"shop"}).visited_map_coords.at(-1).row,1);
  assert.throws(()=>entrySave(mapped(),{...scenario,entry:"event"}),/No native/);
});
test("act starts expose the native map without fabricated visited progress",()=>{
  assert.deepEqual(entrySave(mapped(),{...scenario,entry:"act_start"}).visited_map_coords,[]);
  assert.throws(()=>entrySave(stageAct(save(),scenario),scenario),/native-generated/);
});
