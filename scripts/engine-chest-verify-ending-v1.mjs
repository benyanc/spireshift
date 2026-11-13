// Saved proof verification only. Never starts or connects to a game.
import { createInterface } from "node:readline";
import { verifySummaryTrace,terminalFacts } from "./engine-natural-summary-v2.mjs";
import { sharedDecision } from "./engine-shared-input-v16.mjs";
import { stableJson } from "./engine-public-input-v1.mjs";

for await(const line of createInterface({input:process.stdin,crlfDelay:Infinity})) {
  const request=JSON.parse(line);
  try {
    const before=sharedDecision(request.proof.before,request.proof.before_reads);
    if(stableJson(terminalFacts(before))!==stableJson(terminalFacts(request.terminal_frame)))
      throw Error("Summary proof differs from the captured terminal game facts");
    const result=verifySummaryTrace(request.proof,request.runtime);
    process.stdout.write(`${JSON.stringify({request_id:request.request_id,ok:true,result})}\n`);
  }catch(error){process.stdout.write(`${JSON.stringify({request_id:request.request_id,ok:false,error:error.message})}\n`);}
}
