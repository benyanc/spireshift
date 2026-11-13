import test from "node:test";
import assert from "node:assert/strict";
import { newDiagnosticNavigation, recordDiagnosticNavigation } from "./engine-run-policy-v7.mjs";
import { publicPolicyInput } from "./engine-public-input-v1.mjs";
test("new merchant inspection feeds the existing public learner memory without removing choices", () => {
  const snapshot = { persistent: { content: { run: { act: 1, floor: 5 } } },
    interaction: { kind: "shop_inventory", content: { surface: { inventory_open: false } } }, referents: [],
    bound_actions: { actions: [{ verb: "activate", label: "Open inventory" }, { verb: "close", label: "Leave shop" }] } };
  const navigation = newDiagnosticNavigation();
  assert.equal(publicPolicyInput(snapshot, [], navigation).candidates[0].history.shop_inspected, false);
  recordDiagnosticNavigation(navigation, snapshot, snapshot.bound_actions.actions[0], { delivery: "delivered" });
  const input = publicPolicyInput(snapshot, [], navigation);
  assert(input.candidates.every(a => a.history.shop_inspected));
  assert.deepEqual(input.candidates.map(a => a.label), ["Open inventory", "Leave shop"]);
  recordDiagnosticNavigation(navigation, snapshot, snapshot.bound_actions.actions[0], { delivery: "delivered" });
  assert.equal(navigation.inspected_shop_visits.length, 1);
  const other = structuredClone(snapshot); other.persistent.content.run.floor++;
  assert.equal(publicPolicyInput(other, [], navigation).candidates[0].history.shop_inspected, false);
});
