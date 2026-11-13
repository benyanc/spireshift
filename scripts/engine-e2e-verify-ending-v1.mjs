// Independent saved-proof checker; never starts or connects to a game.
import { createInterface } from "node:readline";
import { verifySummaryTrace } from "./engine-e2e-ending-v1.mjs";
for await(const line of createInterface({input:process.stdin,crlfDelay:Infinity})) {
  const request=JSON.parse(line);
  try {
    const result=verifySummaryTrace(request.proof,request.runtime);
    process.stdout.write(`${JSON.stringify({request_id:request.request_id,ok:true,result})}\n`);
  }catch(error){process.stdout.write(`${JSON.stringify({request_id:request.request_id,ok:false,error:error.message})}\n`);}
}
