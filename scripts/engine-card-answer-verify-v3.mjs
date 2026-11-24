// The cursor ledger is written lazily. Its absence proves nothing on its own:
// both the raw transport and public domains must independently contain no factors.
import {createReadStream,existsSync} from "node:fs";
import {createGunzip} from "node:zlib";
import {createInterface} from "node:readline";
import path from "node:path";
import {pathToFileURL} from "node:url";
import {ExecutableCardAnswerPlanner} from "./engine-executable-card-answer-v1.mjs";
import {stableJson} from "./engine-public-input-v1.mjs";

const same=(a,b)=>stableJson(a)===stableJson(b);
async function* rows(file) {
  const source=createReadStream(file),input=source.pipe(createGunzip());
  // Propagate a missing mandatory input as a checked failure rather than an
  // unhandled error on the source side of a pipe.
  source.on("error",error=>input.destroy(error));
  const lines=createInterface({input,crlfDelay:Infinity});
  try {for await(const line of lines) yield JSON.parse(line);}
  finally {lines.close();source.destroy();input.destroy();}
}

export async function verifyCardAnswers(folder) {
  const planner=new ExecutableCardAnswerPlanner();
  const file=path.join(folder,"selection-cursor.jsonl.gz"),present=existsSync(file);
  const cursor=present?rows(file)[Symbol.asyncIterator]():null;
  const nextLedger=async()=>cursor?(await cursor.next()).value:undefined;
  let local=0,commits=0;
  for await(const row of rows(path.join(folder,"private-transcript.jsonl.gz"))) {
    if(row.transport==="local_selection_ui") {
      const ledger=await nextLedger(),expected=planner.handle(row.request);
      if(!ledger || !same(ledger.request,row.request) || expected?.local!==true
        || ledger.local!==true || !same(expected.response,row.response)
        || !same(expected.response,ledger.response) || !same(expected.before,ledger.before)
        || !same(expected.after,ledger.after)) throw Error("Missing or changed executable answer prefix ledger");
      local++;
    } else {
      if(planner.active && ["select_cards","skip_select"].includes(row.request.action)) {
        const ledger=await nextLedger(),expected=ledger&&planner.handle(ledger.request);
        if(!expected || expected.local!==false || ledger.local!==false
          || !same(expected.native,row.request) || !same(expected.native,ledger.native)
          || !same(expected.before,ledger.before) || !same(expected.after,ledger.after))
          throw Error("Missing or changed final native executable answer ledger");
        commits++;
      } else if(row.request.cmd==="action") planner.handle(row.request);
      planner.observe(row.response);
    }
  }
  if((planner.active?.selected.length??0)>0 || (cursor && !(await cursor.next()).done))
    throw Error("Uncommitted or extra executable answer evidence");
  let locals=0,native=0;
  const domains=rows(path.join(folder,"answer-plan-deliveries.jsonl.gz"))[Symbol.asyncIterator]();
  for await(const receipt of rows(path.join(folder,"public-receipts.jsonl.gz"))) {
    const domain=(await domains.next()).value;
    if(!domain || domain.index!==receipt.index || domain.before_snapshot_id!==receipt.snapshot_id
      || domain.action_id!==receipt.action.bound_action_id
      || domain.successor_snapshot_id!==receipt.successor_snapshot_id || receipt.delivery!=="delivered")
      throw Error("Wrong executable answer delivery binding");
    if(domain.delivery_domain==="local_answer_factor") locals++;
    else if(domain.delivery_domain==="native") native++;
    else throw Error("Unknown delivery domain");
  }
  if(!(await domains.next()).done || local!==locals)
    throw Error("Local factors counted as native deliveries");
  return {contract:"qualified_executable_card_answer_verification_v2",local_factors:local,
    native_deliveries:native,ordered_answer_native_commits:commits,
    all_prefixes_and_exact_commits_reconstructed:true,selection_cursor_present:present,
    absent_cursor_requires_zero_raw_factors_and_zero_public_local_deliveries:true};
}

if(process.argv[1] && import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href)
  console.log(JSON.stringify(await verifyCardAnswers(process.argv[2])));
