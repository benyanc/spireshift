// Saved inspection reconstruction only; no app launch, native simulation or training.
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import path from "node:path";
import { profileTextFacts,firstDifference } from "./engine-profile-text-contract-v1.mjs";
import { completePublicMenu } from "./engine-menu-probe.mjs";
export function verifyProfileEvidence(canonical,shipped,native) {
  const snapshot=shipped.probe.starting_snapshot, runtime=shipped.probe.capabilities.host.runtime_instance_id;
  if(!completePublicMenu(canonical.snapshot,`profile-checker-${native.process_id}`)
      ||!completePublicMenu(snapshot,runtime)) throw Error("Unbound saved profile inspection");
  const expected=profileTextFacts(canonical.snapshot,canonical.deckRead);
  const actual=profileTextFacts(snapshot,shipped.probe.deck_read);
  if(firstDifference(expected,canonical.facts)||firstDifference(actual,shipped.probe.facts)
      ||firstDifference(expected,actual)) throw Error("Saved raw public descriptions differ or do not reconstruct");
  const probe=shipped.probe;
  if(probe.native_provenance.actual_seed!==native.seed||probe.native_provenance.runtime_instance_id!==runtime
      ||![1,2].includes(probe.menu_actions_requested)||probe.receipts.length!==probe.menu_actions_requested
      ||probe.receipts.some(row=>row.delivery!=="delivered"||row.attribution?.runtime_instance_id!==runtime)
      ||new Set(probe.receipts.map(row=>row.request_id)).size!==probe.receipts.length)
    throw Error("Incomplete seed/runtime/startup delivery evidence");
  return {valid:true,observations:1,menu_actions:probe.menu_actions_requested,
    potion_descriptions:actual.player.potions.length,relic_descriptions:actual.player.relics.length,
    card_descriptions:actual.player.deck.length,option_descriptions:actual.options.length,
    games_launched:0,training_allowed:false};
}
if(process.argv[1]&&import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href){
  let input="";for await(const chunk of process.stdin)input+=chunk.toString();const spec=JSON.parse(input);
  const json=file=>JSON.parse(readFileSync(file,"utf8"));
  process.stdout.write(JSON.stringify(verifyProfileEvidence(json(spec.canonical),json(spec.shipped),json(spec.native)))+"\n");
}
