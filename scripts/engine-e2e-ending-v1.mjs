// Explicit native ending facts; UI presentation is retained separately from policy facts.
import { shippedEnding } from "./engine-natural-shipped-contract-v1.mjs";
import { stableJson } from "./engine-public-input-v1.mjs";
import { sharedDecision } from "./engine-shared-input-v15.mjs";
import { completePublicMenu } from "./engine-menu-probe.mjs";

export function terminalFacts(frame) {
  if(frame?.terminal!==true || frame.source_family!=="game_over"
    || frame.terminal_actions_are_presentation!==true || typeof frame.ending?.victory!=="boolean"
    || !["native_public_explicit_terminal_boolean","shipped_public_RunHistory_Win_context"].includes(frame.ending.basis))
    throw Error("A cap, HP estimate or incomplete observation is not a native ending");
  const c=frame.public_input?.context;
  if(c?.interaction?.kind!=="game_over" || c.persistent?.scope!=="active_single_player_run"
    || c.persistent?.run?.ascension!==8 || !Array.isArray(c.reads))
    throw Error("Incomplete public ending facts");
  if(!c.reads.some(read=>read.kind==="run_deck"))throw Error("Missing ending deck observation");
  return {victory:frame.ending.victory,persistent:c.persistent,reads:c.reads};
}

export function summaryAction(snapshot,runtime) {
  if(!shippedEnding(snapshot,runtime))throw Error("No ending before presentation");
  if(!completePublicMenu(snapshot,runtime))throw Error("Incomplete ending presentation menu");
  const surface=snapshot.interaction.content.surface;
  if(surface.stage!=="intro" || surface.can_advance_summary!==true || surface.can_return!==false)
    throw Error("No current game-over intro authority");
  const candidates=snapshot.bound_actions.actions.filter(action=>action.verb==="activate"
    && action.label==="Continue to the run summary" && action.subject_referent_id==null
    && action.arguments.length===0 && action.interaction_id===snapshot.interaction.interaction_id);
  if(candidates.length!==1)throw Error("No unique current game-over Continue binding");
  return candidates[0];
}

export function verifySummaryTrace(proof,runtime) {
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
  if(!Number.isSafeInteger(context.score) || context.total_floor!==right.persistent.run.floor
    || context.ascension!==8)throw Error("Missing or conflicting native summary facts");
  return {summary_reached:true,can_return_observed:true,return_destination:surface.return_destination??null,
    victory:ending.victory,policy_actions_after_terminal:0};
}
