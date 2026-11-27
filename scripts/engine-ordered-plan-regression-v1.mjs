// Reconstruct the exact failed native response without executing a game command.
import {readFileSync} from "node:fs";import {pathToFileURL} from "node:url";
import {projectSelectionFlows as old} from "./engine-reward-belt-surface-v1.mjs";
import {projectSelectionFlows as fixed,selectionFlowReads} from "./engine-ordered-plan-surface-v1.mjs";
import {OrderedAnswerPlanner} from "./engine-ordered-plan-v1.mjs";
import {sharedDecision} from "./engine-shared-input-v16.mjs";
const input=JSON.parse(readFileSync(0,'utf8'));
const {projectManagedCandidateDecision:project,ManagedPlayerEnvironmentSession}=await import(pathToFileURL(input.module_path).href);
const opts={state:input.state,runtimeInstanceId:'saved-ordered-answer',environmentFingerprint:'native-only-plan1',sequence:1,readProjector:selectionFlowReads,validateSdk:true};
let rejected=false;try{project({...opts,surfaceProjector:old});}catch(e){if(!e.message.includes('atomic_selection_domain_exceeds_bound'))throw e;rejected=true;}
if(!rejected)throw Error('Old exact large-selection rejection did not reproduce');
const planner=new OrderedAnswerPlanner();let state=planner.observe(input.state);const out=[];
const session=new ManagedPlayerEnvironmentSession({process:{request(){throw Error('Saved test cannot execute a native command');}},runtimeInstanceId:opts.runtimeInstanceId,environmentFingerprint:opts.environmentFingerprint,surfaceProjector:fixed,readProjector:selectionFlowReads,validateSdk:true});
for(const index of [null,4,1]){
 if(index!==null)state=planner.handle({cmd:'action',action:'ordered_answer_append',args:{selection_ref:state.selection_ref,prefix:planner.active.selected.join(','),index}}).response;
 const snapshot=await session.acceptNativeObservation(state);const reads=snapshot.reads.map(r=>session.read({readId:r.read_id,expectedSnapshotId:snapshot.snapshot_id}));
 const frame=sharedDecision(snapshot,reads);out.push({snapshot,reads,frame});
 if(snapshot.bound_actions.total_count>7)throw Error('Factor menu exceeds n+1 size');
}
const command=planner.handle({cmd:'action',action:'ordered_answer_commit',args:{selection_ref:state.selection_ref,prefix:'4,1'}});
if(command.native.args.indices!=='4,1')throw Error('Physical order changed');
console.log(JSON.stringify({old_rejection_reproduced:rejected,strict_SDK_and_shared_input_pass:true,frames:out,exact_ordered_request:command.native,new_games:0,optimizer_updates:0}));
