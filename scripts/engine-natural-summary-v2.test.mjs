import test from "node:test";
import assert from "node:assert/strict";
import { fixture } from "./engine-interface-case-bank-v1.mjs";
import { verifySummaryTrace as historicalVerifier } from "./engine-e2e-ending-v1.mjs";
import { verifySummaryTrace, recordSummaryTrace } from "./engine-natural-summary-v2.mjs";

function nativeProof() {
  const {snapshot:before,reads:before_reads}=fixture("game_over");
  before.interaction.content.surface.can_return=false;
  const after=structuredClone(before);
  after.snapshot_id="summary";
  Object.assign(after.interaction.content.surface,{stage:"summary",can_advance_summary:false,
    can_return:true,return_destination:"main_menu"});
  // GameOverLiveContext.FloorReached serializes to floor_reached in the pinned Host.
  Object.assign(after.interaction.content.context,{score:144,floor_reached:3,ascension:8});
  after.bound_actions.actions[0].bound_action_id="return";
  after.bound_actions.actions[0].label="Return to the main menu";
  const after_reads=structuredClone(before_reads);
  after_reads.forEach(row=>{row.expected_snapshot_id=after.snapshot_id;row.observed_snapshot_id=after.snapshot_id;});
  const runtime=before.session.runtime_instance_id, action=before.bound_actions.actions[0];
  return {runtime,proof:{before,before_reads,after,after_reads,action,
    receipt:{delivery:"delivered",action:{bound_action_id:action.bound_action_id},
      attribution:{runtime_instance_id:runtime}}}};
}

test("native floor_reached schema exposes the historical verifier bug",()=>{
  const {proof,runtime}=nativeProof();
  assert.throws(()=>historicalVerifier(proof,runtime),/Missing or conflicting native summary facts/);
  assert.equal(verifySummaryTrace(proof,runtime).summary_reached,true);
});

for(const change of [
  p=>{delete p.after.interaction.content.context.floor_reached;p.after.interaction.content.context.total_floor=3;},
  p=>{p.after.interaction.content.context.floor_reached=4;},
  p=>{p.after.interaction.content.context.floor_reached=false;},
  p=>{p.after.interaction.content.context.score=null;},
  p=>{p.after.interaction.content.context.ascension=0;},
  p=>{p.receipt.delivery="not_delivered";},
  p=>{p.receipt.attribution.runtime_instance_id="foreign";},
  p=>{p.receipt.action.bound_action_id="foreign";},
  p=>{p.after.snapshot_id=p.before.snapshot_id;},
  p=>{p.after.interaction.content.surface.can_return=false;},
  p=>{p.after.persistent.content.player.gold++;},
  p=>{p.after_reads[0].content.cards[0].definition_id="OTHER";},
  p=>{p.before.interaction.content.surface.can_advance_summary=false;},
])test("missing or inconsistent public summary evidence remains rejected",()=>{
  const {proof,runtime}=nativeProof();change(proof);
  assert.throws(()=>verifySummaryTrace(proof,runtime));
});

test("retain the complete raw proof before an unsuccessful verification",()=>{
  const {proof,runtime}=nativeProof(), records=[];
  proof.after.interaction.content.context.floor_reached=999;
  assert.throws(()=>recordSummaryTrace(proof,runtime,row=>records.push(row)));
  assert.deepEqual(records,[{kind:"ending_presentation_proof",proof}]);
});

test("a verified summary records proof then completion with no policy request",()=>{
  const {proof,runtime}=nativeProof(), records=[];
  assert.equal(recordSummaryTrace(proof,runtime,row=>records.push(row)).policy_actions_after_terminal,0);
  assert.deepEqual(records.map(row=>row.kind),["ending_presentation_proof","ending_presentation_completion"]);
});
