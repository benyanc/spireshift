import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { fixture } from "./engine-interface-case-bank-v1.mjs";
import { sharedDecision } from "./engine-shared-input-v16.mjs";

function request() {
  const {snapshot:before,reads:before_reads}=fixture("game_over");
  before.interaction.content.surface.can_return=false;
  const after=structuredClone(before);after.snapshot_id="summary";
  Object.assign(after.interaction.content.surface,{stage:"summary",can_advance_summary:false,
    can_return:true,return_destination:"main_menu"});
  Object.assign(after.interaction.content.context,{score:144,floor_reached:3,ascension:8});
  after.bound_actions.actions[0].bound_action_id="return";
  after.bound_actions.actions[0].label="Return to the main menu";
  const after_reads=structuredClone(before_reads);
  after_reads.forEach(row=>{row.expected_snapshot_id=after.snapshot_id;row.observed_snapshot_id=after.snapshot_id;});
  const runtime=before.session.runtime_instance_id, action=before.bound_actions.actions[0];
  return {request_id:1,runtime,terminal_frame:sharedDecision(before,before_reads),
    proof:{before,before_reads,after,after_reads,action,receipt:{delivery:"delivered",
      action:{bound_action_id:action.bound_action_id},attribution:{runtime_instance_id:runtime}}}};
}
function verify(value) {
  const child=spawnSync(process.execPath,[fileURLToPath(new URL("./engine-chest-verify-ending-v1.mjs",import.meta.url))],
    {input:JSON.stringify(value)+"\n",encoding:"utf8",timeout:5000});
  assert.equal(child.status,0,child.stderr);
  return JSON.parse(child.stdout);
}
test("saved bridge rechecks the actual native summary schema and terminal facts",()=>{
  const result=verify(request());assert.equal(result.ok,true);assert.equal(result.result.summary_reached,true);
});
test("a different captured terminal persistent fact rejects the summary proof",()=>{
  const value=request();value.terminal_frame.public_input.context.persistent.player.gold++;
  assert.equal(verify(value).ok,false);
});
test("the historical wrong floor field cannot pass the new saved verifier",()=>{
  const value=request();delete value.proof.after.interaction.content.context.floor_reached;
  value.proof.after.interaction.content.context.total_floor=3;
  assert.equal(verify(value).ok,false);
});
test("missing actual summary reads cannot be substituted by a result label",()=>{
  const value=request();value.proof.after_reads=[];
  assert.equal(verify(value).ok,false);
});
