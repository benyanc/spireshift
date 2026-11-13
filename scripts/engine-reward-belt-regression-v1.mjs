// Saved observations only. No native process or action is started here.
import {readFileSync} from "node:fs";
import {pathToFileURL} from "node:url";
import {projectSelectionFlows as old,selectionFlowReads} from "./engine-chest-surface-v1.mjs";
import {projectSelectionFlows as fixed} from "./engine-reward-belt-surface-v1.mjs";
const input=JSON.parse(readFileSync(0,"utf8"));
const {projectManagedCandidateDecision:project,ManagedPlayerEnvironmentSession}=await import(pathToFileURL(input.module_path).href);
const options={state:input.state,runtimeInstanceId:"saved-reward-belt-regression",environmentFingerprint:"saved-only",
  sequence:28,readProjector:selectionFlowReads,validateSdk:true};
let rejected=false;
try{project({...options,surfaceProjector:old});}catch(e){if(!e.message.includes("referent ids must be unique"))throw e;rejected=true;}
if(!rejected)throw Error("The exact old duplicate-ID failure did not reproduce");
const result=project({...options,surfaceProjector:fixed});
const raw=[...result.bindings.values()].map(v=>v.raw_request);
const discard=raw.filter(v=>v.action==="discard_potion");
if(discard.length!==2 || raw.some(v=>v.action==="select_reward")
  || new Set(discard.map(v=>v.args.potion_ref)).size!==2)throw Error("Changed native full-belt action operands");
for(const action of discard){const p=input.state.player.potions.find(p=>p.slot===action.args.potion_slot);
  if(p?.native_ref!==action.args.potion_ref || !p.can_discard)throw Error("Discard no longer binds its native owned potion");}
const session=new ManagedPlayerEnvironmentSession({process:{request(){throw Error("Saved regression must not execute native commands");}},
  runtimeInstanceId:options.runtimeInstanceId,environmentFingerprint:options.environmentFingerprint,
  surfaceProjector:fixed,readProjector:selectionFlowReads,validateSdk:true});
const snapshot=await session.acceptNativeObservation(input.state);
const reads=snapshot.reads.map(r=>session.read({readId:r.read_id,expectedSnapshotId:snapshot.snapshot_id}));
console.log(JSON.stringify({old_strict_decoder_rejects:rejected,new_strict_decoder_passes:true,
  snapshot,reads,raw_actions:raw,new_games:0,optimizer_updates:0}));
