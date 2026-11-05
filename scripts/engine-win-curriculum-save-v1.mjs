// Explicit curriculum setup on native saves. No enemy/energy/RNG or outcome edits.
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import path from "node:path";
const copy = value => structuredClone(value);
const same = (a,b) => a?.row === b?.row && a?.col === b?.col;

export function stageAct(original, scenario) {
  const value=copy(original), index=scenario.act-1;
  if(value.ascension!==8 || ![0,1,2].includes(index) || value.players?.length!==1
      || value.acts?.[index]?.id!==`ACT.${scenario.act_definition}`)
    throw Error("Curriculum requires exact A8 native act identity");
  value.current_act_index=index;
  value.visited_map_coords=[];
  value.pre_finished_room=null;
  value.map_point_history=Array.from({length:index+1},()=>[]);
  value.acts[index].saved_map=null;
  const rooms=value.acts[index].rooms;
  if(scenario.boss)rooms.boss_id=`ENCOUNTER.${scenario.boss}`;
  rooms.boss_encounters_visited=0;rooms.second_boss_id=null;
  rooms.normal_encounters_visited=0;rooms.elite_encounters_visited=0;rooms.events_visited=0;
  const p=value.players[0];
  // Native serialization restores these legitimate card upgrades before combat.
  let remaining=scenario.profile.upgrades;
  const priorities=scenario.profile.upgrade_priority??[];
  const priority=card=>{const i=priorities.indexOf(card.id.replace(/^CARD\./u,""));return i<0?999:i;};
  for(const card of [...p.deck].sort((a,b)=>priority(a)-priority(b)))if(remaining>0 && !["CARD.STRIKE_IRONCLAD","CARD.DEFEND_IRONCLAD"].includes(card.id)){
    card.current_upgrade_level=1;remaining--;
  }
  return value;
}

export function entrySave(original, scenario) {
  const value=copy(original),index=scenario.act-1,map=value.acts?.[index]?.saved_map;
  if(value.current_act_index!==index || value.ascension!==8 || !map?.start || !map?.boss)
    throw Error("A native-generated current-act map is required");
  value.pre_finished_room=null;
  if(scenario.entry==="act_start") {value.visited_map_coords=[];return value;}
  const points=[map.start,...map.points,map.boss];
  const queue=[[map.start.coord]],seen=new Set();let selected=null;
  while(queue.length){
    const path=queue.shift(),coord=path.at(-1),key=`${coord.col}/${coord.row}`;
    if(seen.has(key))continue;seen.add(key);
    const point=points.find(p=>same(p.coord,coord));if(!point)throw Error("Invalid native map edge");
    const target=scenario.entry==="boss"?same(coord,map.boss.coord)
      :scenario.entry==="preboss"?point.type==="rest_site" && coord.row>=map.boss.coord.row-3
      :scenario.entry==="shop"?point.type==="shop"
      :scenario.entry==="event"?["unknown","event"].includes(point.type)
      :scenario.entry==="treasure"?point.type==="treasure":false;
    if(target && (!selected || coord.row>selected.at(-1).row))selected=path;
    for(const child of point.children??[])queue.push([...path,child]);
  }
  if(!selected)throw Error(`No native current-map entry for ${scenario.entry}`);
  value.visited_map_coords=selected;
  // LoadIntoLatestMapCoord appends the current room to native history. The
  // preceding path needs count-consistent synthetic entries, explicitly belonging
  // to a constructed training start rather than a claimed played prefix.
  value.map_point_history[index]=selected.slice(0,-1).map(coord=>({
    map_point_type:points.find(p=>same(p.coord,coord)).type,rooms:[],
    // Native MapPointHistoryEntry creates one owner entry per player. End-game
    // scoring traverses all entries, even this explicitly synthetic prefix.
    player_stats:value.players.map(p=>({player_id:p.net_id,current_hp:p.current_hp,
      max_hp:p.max_hp,current_gold:p.gold}))
  }));
  return value;
}

if(process.argv[1] && import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href){
  const request=JSON.parse(readFileSync(0,"utf8"));
  if(!["stage","entry"].includes(request.mode))throw Error("Unknown curriculum save operation");
  console.log(JSON.stringify((request.mode==="stage"?stageAct:entrySave)(request.save,request.scenario)));
}
