import test from "node:test";
import assert from "node:assert/strict";
import { fixture } from "./engine-interface-case-bank-v1.mjs";
import { sharedDecision } from "./engine-shared-input-v15.mjs";
import { terminalFacts,summaryAction,verifySummaryTrace } from "./engine-e2e-ending-v1.mjs";

function proof() {
  const x=fixture("game_over"), before=x.snapshot, runtime=before.session.runtime_instance_id;
  before.interaction.content.surface.can_return=false;
  const after=structuredClone(before);after.snapshot_id="summary";
  Object.assign(after.interaction.content.surface,{stage:"summary",can_advance_summary:false,can_return:true,return_destination:"main_menu"});
  Object.assign(after.interaction.content.context,{score:77,total_floor:3,ascension:8});
  after.bound_actions.actions[0].bound_action_id="return";
  after.bound_actions.actions[0].label="Return to the main menu";
  const reads=structuredClone(x.reads);
  reads.forEach(row=>{row.expected_snapshot_id=after.snapshot_id;row.observed_snapshot_id=after.snapshot_id;});
  return {runtime,proof:{before,before_reads:x.reads,after,after_reads:reads,
    action:before.bound_actions.actions[0],receipt:{delivery:"delivered",
      action:{bound_action_id:before.bound_actions.actions[0].bound_action_id},
      attribution:{runtime_instance_id:runtime}}}};
}
test("actual summary control preserves all persistent/deck facts and requests no policy action",()=>{
  const p=proof();assert.equal(summaryAction(p.proof.before,p.runtime).label,"Continue to the run summary");
  assert.deepEqual(verifySummaryTrace(p.proof,p.runtime),{summary_reached:true,can_return_observed:true,
    return_destination:"main_menu",victory:false,policy_actions_after_terminal:0});
});
for(const change of [
  p=>{p.receipt.delivery="not_delivered";},
  p=>{p.receipt.attribution.runtime_instance_id="foreign";},
  p=>{p.receipt.action.bound_action_id="foreign";},
  p=>{p.after.snapshot_id=p.before.snapshot_id;},
  p=>{p.after.interaction.content.surface.can_return=false;},
  p=>{p.after.interaction.content.context.score=null;},
  p=>{p.after.interaction.content.context.total_floor=999;},
  p=>{p.after.persistent.content.player.gold++;},
  p=>{p.after_reads[0].content.cards[0].definition_id="OTHER";},
  p=>{p.before.interaction.content.surface.can_advance_summary=false;},
  p=>{p.before.bound_actions.total_count=2;},
])test("missing, stale or contradictory summary proof rejects",()=>{
  const p=proof();change(p.proof);assert.throws(()=>verifySummaryTrace(p.proof,p.runtime));
});
test("terminal comparison retains unfamiliar persistent and read facts",()=>{
  const p=proof();const before=sharedDecision(p.proof.before,p.proof.before_reads);
  const after=sharedDecision(p.proof.after,p.proof.after_reads);
  assert.deepEqual(terminalFacts(before),terminalFacts(after));
  after.public_input.context.persistent.unfamiliar_native_fact=1;
  assert.notDeepEqual(terminalFacts(before),terminalFacts(after));
});
test("ordinary HP/floor progress and a choice guard cannot produce an ending",()=>{
  const p=proof();const frame=sharedDecision(p.proof.before,p.proof.before_reads);
  frame.terminal=false;assert.throws(()=>terminalFacts(frame));
  frame.terminal=true;frame.ending={victory:0};assert.throws(()=>terminalFacts(frame));
});
