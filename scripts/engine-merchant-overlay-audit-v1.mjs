// Saved-only counterfactual projection; never deliver a game action.
import {readFileSync} from "node:fs";
import {gunzipSync} from "node:zlib";
import path from "node:path";
import {preparePlayerProjection} from "./engine-player-projection-v3.mjs";
import {ExecutableCardAnswerPlanner} from "./engine-executable-card-answer-v1.mjs";
import {projectSelectionFlows as prior,selectionFlowReads} from "./engine-owned-inventory-identity-v1.mjs";
import {projectSelectionFlows} from "./engine-merchant-overlay-surface-v1.mjs";
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
const transcript=rows(path.join(source,"worker/private-transcript.jsonl.gz"));
const raw=transcript.filter(r=>r.response.type==="decision" && r.request.cmd!=="observe").slice(0,10);
const refreshed=transcript.find(r=>r.request.cmd==="observe" && r.response.decision==="map_select");
const map=transcript.find(r=>r.request.cmd==="get_map");
if(raw.length!==10 || shipped.length!==10 || choices.length!==10 || !refreshed)
  throw Error("Require the exact nine-delivery/ten-offer merchant-map stop");
for(const fixed of [false,true]) {
  let mapReads=0;
  const session=new prepared.module.ManagedPlayerEnvironmentSession({
    process:{request(request){
      if(request.cmd!=="get_map" || !map || mapReads++)throw Error("Undeclared saved read");
      return structuredClone(map.response);
    }},
    character:"Ironclad",ascension:8,runtimeInstanceId:"saved-merchant-overlay",environmentFingerprint:"saved-merchant-overlay",
    validateSdk:true,surfaceProjector:fixed?projectSelectionFlows:prior,readProjector:selectionFlowReads,
  });
  const planner=new ExecutableCardAnswerPlanner(),navigation=newDiagnosticNavigation();
  for(let i=0;i<raw.length;i++) {
    let state=structuredClone(i===9&&!fixed?refreshed.response:raw[i].response);
    if(i===9&&fixed) {
      const foul=state.player.potions.find(p=>p.id==="FOUL_POTION");
      if(!foul?.can_use || foul.valid_target_refs?.length!==1)throw Error("Missing the original native merchant binding");
      state.merchant_map_target={contract:"native_current_merchant_room_under_map_v1",
        room_ref:raw[i].request.args.room_ref,merchant_ref:foul.valid_target_refs[0],inventory_open:false};
    }
    planner.handle(raw[i].request);
    const snapshot=await session.acceptNativeObservation(planner.observe(state));
    if(snapshot.completeness?.status!=="complete") throw Error(JSON.stringify({fixed,index:i,completeness:snapshot.completeness}));
    const reads=snapshot.reads.map(d=>session.read({readId:d.read_id,expectedSnapshotId:snapshot.snapshot_id}));
    const frame=sharedDecision(snapshot,reads,navigation),expected=fixed?shipped[i].frame:original[i];
    if(stableJson(frame.public_input)!==stableJson(expected.public_input)
      ||stableJson(frame.actions.map(a=>a.key))!==stableJson(expected.actions.map(a=>a.key)))
      throw Error(`Saved ${fixed?"room-lifetime":"original"} frame ${i} differs`);
    if(i<9) {
      const action=snapshot.bound_actions.actions[frame.actions[choices[i].choice.action_index].raw_index];
      recordInterfaceNavigation(navigation,snapshot,action,{delivery:"delivered"});
    }
  }
}
console.log(JSON.stringify({original_frames_reconstructed:10,corrected_frames_matching_official:10,
  original_deliveries:9,gameplay_replayed:false,games_launched:0,optimizer_updates:0,
  scope:"saved_counterfactual_projection_not_native_effect_qualification"}));
