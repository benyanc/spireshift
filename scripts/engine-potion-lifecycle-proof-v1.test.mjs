import test from "node:test";
import assert from "node:assert/strict";
import { requireFinishedPotionUse } from "./engine-potion-lifecycle-proof-v1.mjs";

const receipt = { detail: "Native UI input was delivered (native_noncombat_potion_use_enqueued:17); inspect successor for game progress." };
const completed = { accepted_action_id: 17, current_action_id: 22, state: "Finished",
  task_status: "RanToCompletion", faulted: false, completion_proven: true };

test("completion binds initial acceptance even if native resume changed current ID", () => {
  assert.equal(requireFinishedPotionUse(receipt, { pending: 0, observations: [completed] }).accepted_action_id, 17);
});
for (const state of ["None", "WaitingForExecution", "Executing", "GatheringPlayerChoice", "ReadyToResumeExecuting", "Canceled"]) {
  test(`bottle removal cannot substitute for ${state} completion`, () => {
    assert.throws(() => requireFinishedPotionUse(receipt, { pending: 0, observations: [{ ...completed, state }] }));
  });
}
test("finished label with unfinished task rejects", () => {
  assert.throws(() => requireFinishedPotionUse(receipt, { pending: 0, observations: [{ ...completed, task_status: "WaitingForActivation" }] }));
});
test("foreign acceptance, faults, and unresolved operations reject", () => {
  for (const proof of [
    { pending: 0, observations: [{ ...completed, accepted_action_id: 18 }] },
    { pending: 0, observations: [{ ...completed, faulted: true }] },
    { pending: 1, observations: [completed] },
  ]) assert.throws(() => requireFinishedPotionUse(receipt, proof));
});
