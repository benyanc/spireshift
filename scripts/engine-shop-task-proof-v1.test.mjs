import test from "node:test";
import assert from "node:assert/strict";
import { requireShopProgress, shopTaskIdentity } from "./engine-shop-task-proof-v1.mjs";

const receipt = { delivery: "delivered", detail: "Native UI input was delivered (native_shop_relic_purchase_started;native_shop_task_started:7)." };
const row = () => ({ accepted_task_id: 7, task_status: "WaitingForActivation", faulted: false,
  canceled: false, completion_proven: false, purchase_succeeded: null, active_child_entity_id: "screen-exact" });
const proof = () => ({ schema_version: "native-shop-task-lifecycle-v1", pending: 1, observations: [row()] });
const successor = () => ({ status: "interactive", interaction: { interaction_id: "screen-exact" }, bound_actions: { actions: [{}] } });

test("Exact causal child remains available while the native shop wrapper awaits it", () => {
  assert.equal(requireShopProgress(receipt, proof(), successor()).completed, false);
});
test("An omitted nullable result matches the Connector's pending-task JSON format", () => {
  const p = proof(); delete p.observations[0].purchase_succeeded;
  assert.equal(requireShopProgress(receipt, p, successor()).completed, false);
  p.observations[0].purchase_succeeded = false;
  assert.throws(() => requireShopProgress(receipt, p, successor()));
});
test("Success and native false-result cancellation both finish the retained wrapper", () => {
  for (const result of [true, false]) {
    const p = proof(); p.pending = 0;
    Object.assign(p.observations[0], { task_status: "RanToCompletion", completion_proven: true,
      purchase_succeeded: result, active_child_entity_id: null });
    assert.deepEqual(requireShopProgress(receipt, p, successor()), { accepted_task_id: 7, completed: true, purchase_succeeded: result });
  }
});
test("Changed gold, stock or acquired relic alone never release a shop task", () => {
  const p = proof(); p.observations[0].active_child_entity_id = null;
  assert.throws(() => requireShopProgress(receipt, p, successor()));
});
test("Foreign child, settling state and empty actions cannot substitute for owned input", () => {
  for (const mutate of [s => s.interaction.interaction_id = "foreign", s => s.status = "settling", s => s.bound_actions.actions = []]) {
    const s = successor(); mutate(s); assert.throws(() => requireShopProgress(receipt, proof(), s));
  }
});
test("Foreign, unknown, faulted, canceled and contradictory tasks fail closed", () => {
  for (const mutate of [r => r.accepted_task_id = 8, r => r.faulted = true, r => r.canceled = true,
    r => r.task_status = "acceptance_unknown", r => r.completion_proven = true, r => r.purchase_succeeded = true]) {
    const p = proof(); mutate(p.observations[0]); assert.throws(() => requireShopProgress(receipt, p, successor()));
  }
});
test("Missing, rejected and zero task identity do not prove native acceptance", () => {
  for (const r of [{ detail: receipt.detail, delivery: "unknown" }, { delivery: "delivered", detail: "enqueue only" },
    { ...receipt, detail: receipt.detail.replace(":7)", ":0)") }]) assert.throws(() => shopTaskIdentity(r));
});
test("An earlier completion row cannot hide a later outstanding or failed observation", () => {
  const p = proof(); p.observations.unshift({ ...row(), task_status: "RanToCompletion", completion_proven: true, purchase_succeeded: true });
  assert.equal(requireShopProgress(receipt, p, successor()).completed, false);
  p.observations.push({ ...row(), faulted: true });
  assert.throws(() => requireShopProgress(receipt, p, successor()));
});
