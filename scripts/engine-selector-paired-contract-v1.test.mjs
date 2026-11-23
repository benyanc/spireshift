import assert from "node:assert/strict";
import test from "node:test";
import {requireLocalAnswerFactor} from "./engine-selector-paired-contract-v1.mjs";

function values() {
  const before = {snapshot_id:"root",interaction:{interaction_id:"owner",content:{surface:{
    cards:[{entity_id:"a"},{entity_id:"b"},{entity_id:"c"}],max_select:3,answer_plan:{selected:[2]}}}}};
  const after = structuredClone(before);
  after.snapshot_id = "new";
  after.interaction.content.surface.answer_plan.selected = [2,0];
  const action = {subject_referent_id:"a"};
  const body = {runtime_instance_id:"runtime",selection:{status:"local_answer_factor",request_id:"request",
    root_snapshot_id:"root",game_committed:false,steps:[],native_selected_card_ids:[],
    before:[2],after:[2,0],appended_card_id:"a"}};
  return [body,before,action,after,"request","runtime"];
}

test("local append preserves exact order and delivers no native card toggles", () => {
  assert.equal(requireLocalAnswerFactor(...values()).status,"local_answer_factor");
});

for (const [name,change] of [
  ["another runtime",v=>v[0].runtime_instance_id="other"],
  ["another request",v=>v[0].selection.request_id="old"],
  ["stale root",v=>v[0].selection.root_snapshot_id="old"],
  ["native primitive",v=>v[0].selection.steps.push({kind:"select"})],
  ["native toggle",v=>v[0].selection.native_selected_card_ids.push("a")],
  ["game commit",v=>v[0].selection.game_committed=true],
  ["reordered prefix",v=>v[0].selection.after=[0,2]],
  ["wrong card",v=>v[0].selection.appended_card_id="b"],
  ["changed owner",v=>v[3].interaction.interaction_id="other"],
  ["missing fresh state",v=>v[3].snapshot_id="root"],
  ["wrong successor prefix",v=>v[3].interaction.content.surface.answer_plan.selected=[0]],
]) test(`reject ${name}`, () => {
  const args=values();change(args);
  assert.throws(()=>requireLocalAnswerFactor(...args),/Unverified local answer factor/u);
});
