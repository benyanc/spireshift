import {prepareRestSave} from "./engine-rest-bridge-contract.mjs";
import {requireCanonicalSeed} from "./engine-seed-contract-v1.mjs";

export function mixedFixture(original, spec) {
  requireCanonicalSeed(spec.seed);
  if (original.rng?.seed !== spec.seed || !["reward","shop","rest"].includes(spec.family))
    throw Error("Wrong mixed fixture seed or family");
  const save=prepareRestSave(original), player=save.players[0], map=save.acts[0].saved_map;
  if (save.players.length!==1 || player.max_hp!==80 || player.current_hp!==spec.hp
      || player.gold!==1000 || player.deck.length!==spec.deck.length)
    throw Error("Unexpected native diagnostic player");
  map.start.type={reward:"monster",shop:"shop",rest:"rest_site"}[spec.family];
  const start=map.points.find(p=>p.coord.row===map.start.coord.row && p.coord.col===map.start.coord.col);
  if (start) start.type=map.start.type;
  if (spec.family==="reward") {
    if (player.odds?.potion_reward_odds_value!==0.4) throw Error("Unexpected native reward odds");
    player.odds.potion_reward_odds_value=1;
    player.deck=Array.from({length:5},()=>({id:"CARD.BLUDGEON",current_upgrade_level:1}));
    player.max_energy=20;
    player.gold=0;
  }
  if (spec.girya!==undefined) {
    const rows=player.relics.filter(r=>r.id==="RELIC.GIRYA");
    const counters=rows[0]?.props?.ints?.filter(p=>p.name==="TimesLifted");
    if (rows.length!==1 || counters?.length!==1 || counters[0].value!==0
        || ![2,3].includes(spec.girya)) throw Error("Unexpected native Girya counter");
    counters[0].value=spec.girya;
  }
  if (spec.kifuda) {
    const bag=player.relic_grab_bag.relic_id_lists.shop, key="RELIC.KIFUDA";
    if (!Array.isArray(bag) || bag.filter(r=>r===key).length!==1)
      throw Error("Missing the existing shop-tier Kifuda");
    player.relic_grab_bag.relic_id_lists.shop=[...bag.filter(r=>r!==key),key];
  }
  if (spec.second_rest) {
    const following=map.points.filter(p=>p.coord.row===1);
    if (spec.family!=="rest" || !following.length) throw Error("Missing second rest destinations");
    for (const point of following) point.type="rest_site";
    for (const point of map.points.filter(p=>p.coord.row===2)) point.type="monster";
  }
  return save;
}
