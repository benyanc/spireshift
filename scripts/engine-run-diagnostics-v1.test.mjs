import test from "node:test";
import assert from "node:assert/strict";
import { newIssueCollection, recordUnsupported, recordRunProgress, recoveryAction, freshRunObservation } from "./engine-run-diagnostics-v1.mjs";

const limits = { mode: "discovery", max_unique_issues: 8, max_issue_observations: 8, max_recoveries: 2, unsupported_grace_ms: 3000 };
function snapshot(kind = "card_reward_selection", status = "visible_unsupported", floor = 5) {
  return { snapshot_id: "current", status, sequence: 5, session: { runtime_instance_id: "worker" },
    information_policy: { includes_hidden_information: false }, completeness: { status: "visible_unmapped", missing: ["card_text", "effect_amounts"] },
    persistent: { content: { run: { floor, act: 1, ascension: 8 }, player: { hp: 44, max_hp: 80 } } },
    referents: [], interaction: { kind, interaction_id: "current-interaction", content: { surface: { reason: "Missing description" }, context: { kind: "reward_flow" } } },
    bound_actions: { status: "complete", total_count: 1, materialized_count: 1, actions: [
      { bound_action_id: "skip", interaction_id: "current-interaction", verb: "skip", label: "Skip", arguments: [] }] } };
}
test("the living unsupported floor is reached without becoming a loss or supported screen", () => {
  const progress = { maximum_floor: 4, maximum_act: 1, last_supported_floor: 4, terminal: false };
  recordRunProgress(progress, snapshot());
  assert.equal(progress.maximum_floor, 5); assert.equal(progress.last_supported_floor, 4);
  assert.equal(progress.last_observed.hp, 44); assert.equal(progress.terminal, false);
});
test("all missing fields are collected, repeated polls are deduplicated, and changed states count", () => {
  const collection = newIssueCollection(), s = snapshot();
  recordUnsupported(collection, s, limits); recordUnsupported(collection, s, limits);
  assert.equal(collection.issues.length, 2); assert.equal(collection.observations.length, 1);
  const next = structuredClone(s); next.persistent.content.run.floor = 6; next.snapshot_id = "next";
  recordUnsupported(collection, next, limits);
  assert.equal(collection.issues.length, 2); assert.equal(collection.issues[0].occurrences, 2);
  assert.equal(collection.clean, false); assert.equal(collection.training_allowed, false);
});
test("a known complete current skip binding can continue diagnostic discovery", () => {
  assert.equal(recoveryAction(snapshot(), "worker", limits, newIssueCollection()).bound_action_id, "skip");
});
for (const change of [
  s => s.bound_actions.actions = [],
  s => s.bound_actions.status = "truncated",
  s => s.bound_actions.total_count = 2,
  s => s.bound_actions.actions[0].interaction_id = "stale",
  s => s.session.runtime_instance_id = "other",
  s => s.interaction.kind = "unsupported",
  s => s.information_policy.includes_hidden_information = true,
  s => s.bound_actions.actions[0].verb = "select",
]) test("unavailable, stale, unknown or unsafe controls have no recovery", () => {
  const s = snapshot(); change(s); assert.equal(recoveryAction(s, "worker", limits, newIssueCollection()), null);
});
test("validation mode and exhausted recovery budgets forbid continuing", () => {
  assert.equal(recoveryAction(snapshot(), "worker", { ...limits, mode: "validation" }, newIssueCollection()), null);
  assert.equal(recoveryAction(snapshot(), "worker", limits, { recoveries: [{}, {}] }), null);
});
test("a blocking unknown owner records every omission and stops with its observed floor", async () => {
  const s = snapshot("unsupported"); s.bound_actions.actions = []; s.bound_actions.total_count = 0; s.bound_actions.materialized_count = 0;
  const collection = newIssueCollection(), gameplay = {}; let clock = 0;
  await assert.rejects(freshRunObservation({ observe: async () => s, previous: null, runtimeId: "worker", deadline: 9000,
    gameplay, collection, limits, now: () => clock, pause: async ms => { clock += ms; } }), /no verified recovery/u);
  assert.equal(gameplay.maximum_floor, 5); assert.equal(collection.issues.length, 2);
});
test("discovery can return a verified recovery and then a fresh clean successor", async () => {
  const collection = newIssueCollection(), gameplay = {}; let clock = 0;
  const recovered = await freshRunObservation({ observe: async () => snapshot(), previous: null, runtimeId: "worker", deadline: 9000,
    gameplay, collection, limits, now: () => clock, pause: async ms => { clock += ms; } });
  assert.equal(recovered.recovery, true);
  const next = snapshot("card_reward_selection", "interactive", 6); next.snapshot_id = "next"; next.completeness = { status: "complete" };
  const fresh = await freshRunObservation({ observe: async () => next, previous: "current", runtimeId: "worker", deadline: 9000,
    gameplay, collection, limits, now: () => clock });
  assert.equal(fresh.recovery, false); assert.equal(gameplay.last_supported_floor, 6); assert.equal(collection.clean, false);
});
test("runtime changes and private facts stop immediately without consuming a recovery", async () => {
  const s = snapshot(); s.persistent.content.player.rng = 1;
  await assert.rejects(freshRunObservation({ observe: async () => s, previous: null, runtimeId: "worker", deadline: Date.now() + 1000,
    gameplay: {}, collection: newIssueCollection(), limits }), /Private/u);
});
test("collection storage is finite", () => {
  assert.throws(() => recordUnsupported(newIssueCollection(), snapshot(), { ...limits, max_unique_issues: 1 }), /cap/u);
});
