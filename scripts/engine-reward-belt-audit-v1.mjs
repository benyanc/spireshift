// Reconcile one saved reward projection using the exact new C# provider helper.
// This never submits a game action and leaves all source evidence unchanged.
import {readFileSync} from "node:fs";
import {gunzipSync} from "node:zlib";
import {spawnSync} from "node:child_process";
import path from "node:path";
import {sharedDecision} from "./engine-shared-input-v17.mjs";
import {stableJson} from "./engine-public-input-v1.mjs";
import {newDiagnosticNavigation} from "./engine-run-policy-v7.mjs";

const rows=file=>gunzipSync(readFileSync(file)).toString().trim().split("\n").map(JSON.parse);
const native=path.resolve(process.argv[2]),official=path.resolve(process.argv[3]),project=path.resolve(process.argv[4]);
const captures=rows(path.join(official,"live-public.jsonl.gz")).filter(r=>r.kind==="public_frame");
const capture=captures.at(-1),snapshot=structuredClone(capture.snapshot);
const surface=snapshot.interaction.content.surface;
if(snapshot.interaction.kind!=="reward_claim"||surface.potion_states?.length!==2
    ||surface.discardable_potions?.length!==2)throw Error("Require the exact preserved full-belt reward capture");
let rejected=false;
try{sharedDecision(snapshot,capture.reads,newDiagnosticNavigation());}catch(error){
  if(!error.message.includes("Conflicting current public entity facts"))throw error;
  rejected=true;
}
if(!rejected)throw Error("The original contradictory potion view was not rejected");
const bindings=snapshot.bound_actions.actions.map(action=>{
  const potion=surface.discardable_potions.find(p=>p.entity_id===action.subject_referent_id);
  const legacy=potion&&action.verb==="activate"&&action.arguments.length===0
    &&action.label===`Discard ${potion.name} from slot ${potion.slot+1} to make room`;
  return {action,operation:legacy?"discard_potion_for_reward":"other",
    operands:legacy?{potion_id:potion.entity_id}:{}};
});
const child=spawnSync("dotnet",["run","--project",project,"--no-launch-profile"],{
  input:JSON.stringify({surface,belt:surface.potion_states,bindings}),encoding:"utf8",timeout:30000,
  env:{...process.env,DOTNET_ROLL_FORWARD:"Major"},maxBuffer:2000000,
});
if(child.status!==0)throw Error(`Reward belt probe failed: ${child.stderr}`);
const result=JSON.parse(child.stdout.trim().split("\n").at(-1));
const removed=snapshot.bound_actions.actions.length-result.actions.length;
if(removed!==2)throw Error("The exact two duplicate capacity aliases were not coalesced");
snapshot.interaction.content.surface=result.surface;
snapshot.bound_actions.actions=result.actions;
snapshot.bound_actions.total_count=result.actions.length;
snapshot.bound_actions.materialized_count=result.actions.length;
const fixed=sharedDecision(snapshot,capture.reads,newDiagnosticNavigation());
const expected=rows(path.join(native,"frames.jsonl.gz"))[2];
if(stableJson(fixed.public_input)!==stableJson(expected.public_input)
    ||stableJson(fixed.actions.map(a=>a.key))!==stableJson(expected.actions.map(a=>a.key)))
  throw Error("Corrected reward public facts/menu do not exactly match the native capture");
console.log(JSON.stringify({original_conflict_reproduced:true,duplicate_discard_aliases_removed:removed,
  corrected_complete_reward_input_matches_native:true,authoritative_potion_targets_and_permissions_preserved:true,
  games_launched:0,optimizer_updates:0}));
