// Explicit new layout lineage. Old helpers, recipes and checkpoint bytes remain frozen.
import { createHash } from "node:crypto";
import { createInterface } from "node:readline";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { sharedDecision as previous, deliveredAction, recordInterfaceNavigation, CONTRACT } from "./engine-shared-input-v3.mjs";
import { normalizeLayout, LAYOUT } from "./engine-input-layout-v1.mjs";
import { stableJson } from "./engine-public-input-v1.mjs";
import { newDiagnosticNavigation } from "./engine-run-policy-v7.mjs";
export { deliveredAction, recordInterfaceNavigation, CONTRACT };
const hash=v=>createHash("sha256").update(stableJson(v)).digest("hex");
export function sharedDecision(snapshot,reads,navigation=null) {
  const frame=previous(snapshot,reads,navigation), layout=normalizeLayout(frame.public_input);
  if(layout.unresolved.length)throw Error(`Conflicting layout facts: ${JSON.stringify(layout.unresolved)}`);
  const rows=layout.public_input.candidates.map((candidate,i)=>({candidate,binding:frame.actions[i],key:stableJson({
    verb:candidate.verb,label:candidate.label,subject:candidate.subject?.public_slot??null,
    arguments:candidate.arguments.map(a=>({role:a.role,name:a.name,slot:a.entity?.public_slot??null}))
  })})).sort((a,b)=>a.key<b.key?-1:a.key>b.key?1:0);
  if(new Set(rows.map(r=>r.key)).size!==rows.length)throw Error("Ambiguous normalized action identity");
  const public_input={...layout.public_input,candidates:rows.map(r=>r.candidate)};
  const actions=rows.map(r=>({...r.binding,key:r.key})), input_digest=hash(public_input);
  return {...frame,public_input,actions,input_digest,input_layout:LAYOUT,
    layout_evidence:layout,binding_id:hash({runtime:frame.observation.runtime_instance_id,
      snapshot:frame.observation.snapshot_id,input:input_digest,actions,layout:LAYOUT})};
}
if(process.argv[1]&&import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href) {
  const navigation=newDiagnosticNavigation();let current;
  for await(const line of createInterface({input:process.stdin,crlfDelay:Infinity})) {
    let request;
    try {
      request=JSON.parse(line);
      if(request.command==="commit") {
        if(!current||request.acknowledgement?.delivery!=="delivered")throw Error("No delivered layout choice");
        const action=deliveredAction(current.frame,request,current.snapshot);
        if(request.acknowledgement.bound_action_id!==action.bound_action_id
          ||request.acknowledgement.runtime_instance_id!==current.frame.observation.runtime_instance_id
          ||request.acknowledgement.before_snapshot_id!==current.snapshot.snapshot_id)
          throw Error("Wrong layout navigation receipt");
        recordInterfaceNavigation(navigation,current.snapshot,action,request.acknowledgement);current=null;
        process.stdout.write(`${JSON.stringify({request_id:request.request_id,ok:true})}\n`);continue;
      }
      if(current)throw Error("Prior layout choice is unacknowledged");
      const frame=sharedDecision(request.snapshot,request.reads,request.navigation??navigation);
      current={snapshot:request.snapshot,frame};
      process.stdout.write(`${JSON.stringify({request_id:request.request_id,ok:true,frame})}\n`);
    }catch(e){process.stdout.write(`${JSON.stringify({request_id:request?.request_id,ok:false,error:e.message})}\n`);process.exitCode=1;break;}
  }
}
