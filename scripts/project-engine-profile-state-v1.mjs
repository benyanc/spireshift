// Project a saved native inspection observation; no simulator/game process or action is started.
import { readFileSync,writeFileSync } from "node:fs";
import { preparePlayerProjection } from "./engine-player-projection.mjs";
import { projectExactBundleSurface } from "./engine-bundle-surface-v1.mjs";
import { projectExactCombatReads } from "./engine-combat-surface.mjs";
import { profileTextFacts } from "./engine-profile-text-contract-v1.mjs";
let input="";for await(const chunk of process.stdin) input+=chunk.toString();
const spec=JSON.parse(input),state=JSON.parse(readFileSync(spec.native_state,"utf8"));
const prepared=await preparePlayerProjection(spec);
const session=new prepared.module.ManagedPlayerEnvironmentSession({
  process:{request:async()=>{throw Error("Saved inspection projection cannot issue native commands");}},
  character:"Ironclad",ascension:8,runtimeInstanceId:`profile-checker-${spec.native_pid}`,
  environmentFingerprint:spec.environment_fingerprint,
  surfaceProjector:projectExactBundleSurface,readProjector:projectExactCombatReads,validateSdk:true
});
const snapshot=await session.acceptNativeObservation(state);
const descriptor=snapshot.reads.find(row=>row.kind==="run_deck");
const deckRead=session.read({readId:descriptor?.read_id,expectedSnapshotId:snapshot.snapshot_id});
const result={snapshot,deckRead,facts:profileTextFacts(snapshot,deckRead),projection_identity:prepared.identity};
writeFileSync(spec.output,JSON.stringify(result,null,2)+"\n");
process.stdout.write(JSON.stringify({valid:true,games_launched:0,actions:0,training_allowed:false})+"\n");
