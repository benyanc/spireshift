import test from "node:test";
import assert from "node:assert/strict";
import { progressionAction, progressionFacts, transitionTarget, verifyProgressionTrace } from "./engine-progression-contract-v3.mjs";

const runtime = "worker";
function snapshot(kind, sequence, act = 3) {
  const action = { bound_action_id: `action-${sequence}`, interaction_id: `screen-${sequence}`,
    label: kind === "reward_completion" ? "Proceed" : "Threaten", verb: "activate", arguments: [] };
  return { snapshot_id: `snapshot-${sequence}`, sequence, status: "interactive",
    session: { runtime_instance_id: runtime }, information_policy: { includes_hidden_information: false },
    completeness: { status: "complete" },
    persistent: { content: { run: { ascension: 8, act, act_definition_id: "EXAMPLE" },
      player: { character_definition_id: "IRONCLAD", hp: kind === "game_over" ? 0 : 80 } } },
    interaction: { interaction_id: `screen-${sequence}`, kind,
      content: { surface: { kind, ...(kind === "reward_completion" ? { can_proceed: true } : {}) }, context: kind === "game_over" ? { kind, game_mode: "standard", result: "win" }
        : { kind: "event", event_id: "THE_ARCHITECT" } } },
    bound_actions: { status: "complete", actions: [action], materialized_count: 1, total_count: 1 } };
}
const fixture = { act: 3, target: { act: 3, act_definition_id: "EXAMPLE" } };
function trace() {
  const snapshots = [snapshot("reward_completion", 1), snapshot("event_option", 2), snapshot("game_over", 3)];
  return { shutdown_requested: true, capabilities: { host: { runtime_instance_id: runtime } }, snapshots,
    receipts: snapshots.slice(0, 2).map((before, i) => ({ before, phase: i ? "architect" : "proceed",
      expected_snapshot_id: before.snapshot_id, action: before.bound_actions.actions[0],
      receipt: { request_id: `request-${i}`, delivery: "delivered", action: { bound_action_id: `action-${i + 1}` },
        attribution: { runtime_instance_id: runtime } } })) };
}

test("zero HP is compatible with a real explicit win; the Architect dialogue is not yet an ending", () => {
  const architect = snapshot("event_option", 2), ending = snapshot("game_over", 3);
  assert.equal(progressionFacts(architect, runtime).ending, null);
  assert.equal(transitionTarget(architect, runtime, 3, fixture.target), false);
  assert.equal(transitionTarget(ending, runtime, 3, fixture.target), true);
  delete ending.interaction.content.context.result;
  assert.throws(() => progressionFacts(ending, runtime), /explicit standard shipped ending/u);
});
test("earlier act targets need the next map and the correct native act definition", () => {
  const map = snapshot("map_navigation", 1, 2), target = { act: 2, act_definition_id: "EXAMPLE" };
  assert.equal(transitionTarget(map, runtime, 1, target), true);
  map.persistent.content.run.act_definition_id = "OTHER";
  assert.equal(transitionTarget(map, runtime, 1, target), false);
});
test("a forced transition cannot invent Proceed for a mandatory card choice or unseen state", () => {
  assert.throws(() => progressionAction(snapshot("card_selection", 1), 3, "proceed"), /Unsupported/u);
  const before = snapshot("reward_completion", 1);
  before.bound_actions.actions[0].label = "Choose a card";
  assert.throws(() => progressionAction(before, 3, "proceed"), /current progression fixture control/u);
  before.seed = "hidden";
  assert.throws(() => progressionFacts(before, runtime), /Private engine field/u);
});
test("saved reconstruction keeps privileged wins out of the natural-win denominator", () => {
  const result = verifyProgressionTrace(trace(), fixture);
  assert.equal(result.valid, true); assert.equal(result.proceed_actions, 1);
  assert.equal(result.natural_victories, 0); assert.equal(result.training_allowed, false);
});
test("the native Continue from rewards control needs its advertised Proceed permission", () => {
  const current = snapshot("reward_completion", 1);
  current.bound_actions.actions[0].label = "Continue from rewards";
  assert.equal(progressionAction(current, 3, "proceed"), current.bound_actions.actions[0]);
  current.interaction.content.surface.can_proceed = false;
  assert.throws(() => progressionAction(current, 3, "proceed"), /current progression fixture control/u);
});
for (const mutation of ["unknown", "stale", "unoffered", "duplicate", "missing", "wrong_ending", "wrong_target"]) {
  test(`saved reconstruction rejects ${mutation} progression evidence`, () => {
    const control = trace(), current = structuredClone(fixture);
    if (mutation === "unknown") control.receipts[0].receipt.delivery = "unknown";
    if (mutation === "stale") control.receipts[0].expected_snapshot_id = "old";
    if (mutation === "unoffered") control.receipts[0].action = { ...control.receipts[0].action, bound_action_id: "not-offered" };
    if (mutation === "duplicate") control.receipts[1].receipt.request_id = control.receipts[0].receipt.request_id;
    if (mutation === "missing") control.snapshots.pop();
    if (mutation === "wrong_ending") control.snapshots.at(-1).interaction.content.context.result = "loss";
    if (mutation === "wrong_target") current.target.act_definition_id = "OTHER";
    assert.throws(() => verifyProgressionTrace(control, current));
  });
}

test("the advertised reward exit may decline remaining optional rewards", () => {
  const current = snapshot("reward_completion", 1);
  current.bound_actions.actions[0].label = "Skip remaining rewards and continue";
  current.interaction.content.surface.proceed_skips_remaining_rewards = true;
  assert.equal(progressionAction(current, 1, "proceed"), current.bound_actions.actions[0]);
});
