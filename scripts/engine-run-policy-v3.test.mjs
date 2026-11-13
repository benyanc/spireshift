import test from "node:test";
import assert from "node:assert/strict";
import { chooseRunAction, newDiagnosticNavigation, recordDiagnosticNavigation } from "./engine-run-policy-v3.mjs";

const shop = (floor = 5) => ({ interaction: { kind: "shop_room" },
  persistent: { content: { run: { act: 1, floor: floor, ascension: 8 } } },
  bound_actions: { actions: [
    { verb: "activate", label: "Leave shop and open map", bound_action_id: "leave", arguments: [] },
    { verb: "open", label: "Open shop inventory", bound_action_id: "open", arguments: [] },
  ] } });

test("a delivered inspection followed by closing inventory leaves instead of opening forever", () => {
  const navigation = newDiagnosticNavigation(), before = shop();
  const open = chooseRunAction(before, undefined, navigation);
  assert.equal(open.bound_action_id, "open");
  recordDiagnosticNavigation(navigation, before, open, { delivery: "delivered" });
  const returned = shop(); returned.bound_actions.actions.reverse();
  returned.bound_actions.actions.forEach(action => { action.bound_action_id += "-refreshed"; });
  assert.equal(chooseRunAction(returned, undefined, navigation).bound_action_id, "leave-refreshed");
});

test("an uncertain or unsuccessful inspection does not become public navigation history", () => {
  for (const delivery of ["unknown", "rejected", "timed_out"]) {
    const state = shop(), navigation = newDiagnosticNavigation();
    recordDiagnosticNavigation(navigation, state, state.bound_actions.actions[1], { delivery });
    assert.deepEqual(navigation, newDiagnosticNavigation());
  }
});

test("each later shop and each new game has a fresh inspection opportunity", () => {
  const navigation = newDiagnosticNavigation(), state = shop();
  recordDiagnosticNavigation(navigation, state, state.bound_actions.actions[1], { delivery: "delivered" });
  assert.equal(chooseRunAction(shop(10), undefined, navigation).bound_action_id, "open");
  assert.equal(chooseRunAction(shop(), undefined, newDiagnosticNavigation()).bound_action_id, "open");
});

test("the same shop inspection is counted once and non-inspection controls add no history", () => {
  const navigation = newDiagnosticNavigation(), state = shop();
  for (let repeat = 0; repeat < 3; repeat++)
    for (const action of state.bound_actions.actions)
      recordDiagnosticNavigation(navigation, state, action, { delivery: "delivered" });
  assert.deepEqual(navigation.inspected_shop_visits, ["[1,5]"]);
});

test("a learned scorer may reopen an inspected shop or leave a fresh shop", () => {
  const navigation = newDiagnosticNavigation(), state = shop();
  recordDiagnosticNavigation(navigation, state, state.bound_actions.actions[1], { delivery: "delivered" });
  assert.equal(chooseRunAction(state, (_, action) => action.verb === "open" ? 10 : 0, navigation).bound_action_id, "open");
  assert.equal(chooseRunAction(shop(), (_, action) => action.verb === "activate" ? 10 : 0).bound_action_id, "leave");
});

test("mandatory or unavailable controls receive no invented shop exit", () => {
  const state = shop(), navigation = { inspected_shop_visits: ["[1,5]"] };
  state.bound_actions.actions.shift();
  assert.equal(chooseRunAction(state, undefined, navigation).bound_action_id, "open");
  assert.equal(state.bound_actions.actions.length, 1);
});

test("shop history cannot consume private engine fields or missing public progress", () => {
  const state = shop(); delete state.persistent.content.run.floor;
  assert.throws(() => chooseRunAction(state), /public act and floor/u);
  assert.throws(() => chooseRunAction(shop(), undefined, { seed: "private" }), /Private engine field/u);
});
