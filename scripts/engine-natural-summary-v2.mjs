// Versioned correction of the saved E2E601/602 collector, with the game untouched.
import { shippedEnding } from "./engine-natural-shipped-contract-v1.mjs";
import { stableJson } from "./engine-public-input-v1.mjs";
import { sharedDecision } from "./engine-shared-input-v15.mjs";
import { terminalFacts, summaryAction } from "./engine-e2e-ending-v1.mjs";

export { terminalFacts, summaryAction };

export function verifySummaryTrace(proof, runtime) {
  const {before,before_reads,action,receipt,after,after_reads}=proof;
  const current=summaryAction(before,runtime), ending=shippedEnding(after,runtime), surface=after.interaction.content.surface;
  if(stableJson(action)!==stableJson(current) || receipt.delivery!=="delivered"
    || receipt.action?.bound_action_id!==action.bound_action_id
    || receipt.attribution?.runtime_instance_id!==runtime
    || after.snapshot_id===before.snapshot_id || surface.stage!=="summary"
    || surface.can_advance_summary!==false || surface.can_return!==true
    || ending.victory!==shippedEnding(before,runtime).victory)
    throw Error("Game-over Continue lacks a verified native summary successor");
  const left=terminalFacts(sharedDecision(before,before_reads));
  const right=terminalFacts(sharedDecision(after,after_reads));
  if(stableJson(left)!==stableJson(right))throw Error("Ending presentation changed public game facts");
  const context=after.interaction.content.context;
  if(!Number.isSafeInteger(context.score) || !Number.isSafeInteger(context.floor_reached)
    || context.floor_reached!==right.persistent.run.floor || context.ascension!==8)
    throw Error("Missing or conflicting native summary facts");
  return {summary_reached:true,can_return_observed:true,return_destination:surface.return_destination??null,
    victory:ending.victory,policy_actions_after_terminal:0};
}

export function recordSummaryTrace(proof, runtime, journal) {
  // Preserve actual reads and receipts even when validation rejects the proof.
  journal({kind:"ending_presentation_proof",proof});
  const result=verifySummaryTrace(proof,runtime);
  journal({kind:"ending_presentation_completion",proof});
  return result;
}
