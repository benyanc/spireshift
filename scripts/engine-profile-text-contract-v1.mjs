// Exact public inspection facts only. Benchmark progress and future act/RNG metadata stay outside.
import { restPersistentFacts } from "./engine-rest-bridge-contract.mjs";
import { firstDifference } from "./engine-journey-contract-v2.mjs";
export { firstDifference };
const required = (row, keys) => Object.fromEntries(keys.map(key => {
  if (row?.[key] == null) throw Error(`Missing profile/text public field: ${key}`);
  return [key,row[key]];
}));
const sorted = rows => [...rows].sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b),"en"));
const text = value => {
  if (typeof value !== "string" || !value.trim()) throw Error("Missing formatted public text");
  if (/\{[A-Za-z][^}]*\}/u.test(value)) throw Error("Unresolved native description variables");
  return value;
};
export function profileTextFacts(snapshot, deckRead) {
  const facts=restPersistentFacts(snapshot,deckRead), player=snapshot.persistent.content.player;
  if(snapshot.interaction.kind!=="event_option") throw Error("Only initial benchmark ancient inspection is covered");
  facts.player.potions=sorted(player.potions.map(row=>({
    ...required(row,["definition_id","slot"]), description:text(row.description)
  })));
  facts.player.relics=sorted(player.relics.map(row=>({
    ...required(row,["definition_id"]), description:text(row.description), counter:row.counter??null
  })));
  facts.player.deck=sorted(deckRead.content.cards.map(row=>({
    ...required(row,["definition_id","cost","is_upgraded"]),description:text(row.description)
  })));
  facts.options=snapshot.interaction.content.surface.options.map(row=>({
    title:text(row.title??row.label),description:text(row.description),
    is_locked:typeof row.is_locked==="boolean"?row.is_locked:
      typeof row.enabled==="boolean"?!row.enabled:null
  }));
  if(facts.options.some(row=>row.is_locked===null)||facts.run.ascension!==8
      ||facts.run.floor!==1||facts.player.potions.length!==2)
    throw Error("Incomplete fixed A8/profile inspection fixture");
  return facts;
}
