// Stateless saved-frame checker: no game/session/optimizer endpoint.
import { createInterface } from "node:readline";
import { sharedDecision,deliveredAction } from "./engine-shared-input-v11.mjs";
import { createHash } from "node:crypto";
const hash=value=>createHash("sha256").update(stableJson(value)).digest("hex");
import { restoreLayout } from "./engine-input-layout-v8.mjs";
import { stableJson } from "./engine-public-input-v1.mjs";
import { caseBank } from "./engine-interface-case-bank-v1.mjs";
for await(const line of createInterface({input:process.stdin,crlfDelay:Infinity})) {
  const request=JSON.parse(line);
  try {
    if(request.command==="case_bank") {
      const cases=caseBank().map(row=>{
        const frame=sharedDecision(row.snapshot,row.reads);
        return {key:row.key,frame,exact_round_trip:hash(restoreLayout(frame.layout_evidence))===frame.layout_evidence.original_digest,
          bindings_preserved:frame.terminal||frame.actions.every((a,i)=>deliveredAction(frame,{binding_id:frame.binding_id,action_index:i},row.snapshot).bound_action_id===a.bound_action_id),
          complete_menu:frame.actions.length===row.snapshot.bound_actions.actions.length};
      });
      process.stdout.write(`${JSON.stringify({request_id:request.request_id,ok:true,cases})}\n`);continue;
    }
    const original=stableJson({snapshot:request.snapshot,reads:request.reads});
    const frame=sharedDecision(request.snapshot,request.reads);
    const restored=restoreLayout(frame.layout_evidence);
    const mapped=frame.actions.every((binding,i)=>frame.terminal||
      deliveredAction(frame,{binding_id:frame.binding_id,action_index:i},request.snapshot).bound_action_id===binding.bound_action_id);
    process.stdout.write(`${JSON.stringify({request_id:request.request_id,ok:true,frame,
      exact_round_trip:hash(restored)===frame.layout_evidence.original_digest && original===stableJson({snapshot:request.snapshot,reads:request.reads}),bindings_preserved:mapped,
      complete_menu:frame.actions.length===request.snapshot.bound_actions.actions.length})}\n`);
  } catch(e) {process.stdout.write(`${JSON.stringify({request_id:request.request_id,ok:false,error:e.message})}\n`);}
}
