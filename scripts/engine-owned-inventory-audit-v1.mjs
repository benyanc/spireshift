// Saved-only reproduction. A request for live game state is an error.
import {readFileSync} from "node:fs";
import {gunzipSync} from "node:zlib";
import path from "node:path";
import {preparePlayerProjection} from "./engine-player-projection-v3.mjs";
import {CardAnswerPlanner} from "./engine-card-answer-v1.mjs";
import {projectSelectionFlows as prior} from "./engine-crystal-grid-v1.mjs";
import {selectionFlowReads as priorReads} from "./engine-chest-surface-v1.mjs";
import {projectSelectionFlows,selectionFlowReads} from "./engine-owned-inventory-identity-v1.mjs";
import {sharedDecision,recordInterfaceNavigation} from "./engine-shared-input-v17.mjs";
import {newDiagnosticNavigation} from "./engine-run-policy-v7.mjs";
import {stableJson} from "./engine-public-input-v1.mjs";

const rows=file=>gunzipSync(readFileSync(file)).toString().trim().split("\n").map(JSON.parse);
const source=path.resolve(process.argv[2]),official=path.resolve(process.argv[3]);
const identity=JSON.parse(readFileSync(path.join(source,"worker/identity.json")));
const marker=JSON.parse(readFileSync(path.join(identity.shared_projection.directory,"identity.json")));
const prepared=await preparePlayerProjection({shared_projection:identity.shared_projection,projection:marker.projection});
const original=rows(path.join(source,"frames.jsonl.gz"));
const choices=rows(path.join(source,"choices.jsonl.gz"));
const shipped=rows(path.join(official,"live-public.jsonl.gz")).filter(r=>r.kind==="policy_input");
const raw=rows(path.join(source,"worker/private-transcript.jsonl.gz"))
  .filter(r=>r.response.type==="decision").slice(0,3);
if(raw.length!==3||shipped.length!==3)throw Error("Require the preserved two-delivery/three-offer prefix");
const frames=[];
for(const fixed of [false,true]){
  const session=new prepared.module.ManagedPlayerEnvironmentSession({
    process:{request(){throw Error("Saved regression cannot request live game state");}},
    character:"Ironclad",ascension:8,runtimeInstanceId:"saved-inventory-regression",
    environmentFingerprint:"saved-inventory-regression",validateSdk:true,
    surfaceProjector:fixed?projectSelectionFlows:prior,readProjector:fixed?selectionFlowReads:priorReads,
  });
  const planner=new CardAnswerPlanner(),navigation=newDiagnosticNavigation(),converted=[];
  for(let i=0;i<raw.length;i++){
    planner.handle(raw[i].request);
    const snapshot=await session.acceptNativeObservation(planner.observe(raw[i].response));
    const reads=snapshot.reads.map(d=>session.read({readId:d.read_id,expectedSnapshotId:snapshot.snapshot_id}));
    const frame=sharedDecision(snapshot,reads,navigation);
    const expected=fixed?shipped[i].frame:original[i];
    if(stableJson(frame.public_input)!==stableJson(expected.public_input)
        ||stableJson(frame.actions.map(a=>a.key))!==stableJson(expected.actions.map(a=>a.key)))
      throw Error(`Saved ${fixed?"corrected official":"original native"} frame ${i} does not reconstruct exactly`);
    converted.push(frame);
    if(i<raw.length-1){
      const index=choices[i].choice.action_index;
      const action=snapshot.bound_actions.actions[frame.actions[index].raw_index];
      recordInterfaceNavigation(navigation,snapshot,action,{delivery:"delivered"});
    }
  }
  frames.push(converted);
}
console.log(JSON.stringify({original_native_frames_reconstructed:frames[0].length,
  corrected_frames_matching_official:frames[1].length,menus_unchanged:true,
  physical_identity_repaired:true,games_launched:0,optimizer_updates:0}));
