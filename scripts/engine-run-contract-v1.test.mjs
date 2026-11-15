import test from "node:test";
import assert from "node:assert/strict";
import { assertPublicBoundary, inspectRunInput, publicProgressKey, driveRun, projectRunSurface, checkNativeEnding } from "./engine-run-contract-v1.mjs";

function snapshot(kind = "rest_site", sequence = 1) {
  const id = `snapshot-${sequence}`, interaction = `interaction-${sequence}`;
  return { snapshot_id: id, sequence, status: "interactive", session: { runtime_instance_id: "worker" },
    information_policy: { includes_hidden_information: false }, completeness: { status: "complete" },
    persistent: { content: { run: { ascension: 8, act: 1, floor: 1 }, player: { hp: 20, max_hp: 80 } } },
    referents: [], reads: [], interaction: { interaction_id: interaction, kind, content: { surface: {}, context: {} } },
    bound_actions: { status: "complete", materialized_count: 1, total_count: 1,
      actions: [{ bound_action_id: `action-${sequence}`, interaction_id: interaction,
        subject_referent_id: null, verb: "activate", label: "Rest", arguments: [] }] } };
}
function ended(sequence = 2, victory = false) {
  const s = snapshot("game_over", sequence); s.status = "observed";
  s.interaction.content.surface.victory = victory;
  s.bound_actions = { status: "complete", materialized_count: 0, total_count: 0, actions: [] };
  return s;
}
const options = { seed: "synthetic", runtimeId: "worker", maxDecisions: 20, maxRepeatedStates: 3, wholeRunBudget: 128 };

for (const key of ["rng", "seed", "native_ref", "selection_ref", "raw_request", "privileged_act_sequence"]) {
  test(`private ${key} fails before the policy acts`, () => {
    const s = snapshot(); s.persistent.content.player[key] = "private";
    assert.throws(() => inspectRunInput(s, [], "worker"), /Private engine field/u);
  });
}
test("an ordinary loss is a candidate ending, not a win or qualification", async () => {
  const result = await driveRun({ mount: async () => ended(), read() {} }, options);
  assert.equal(result.status, "candidate_terminal"); assert.equal(result.victory, false);
  assert.equal(result.decisions, 0); assert.equal(result.training_allowed, undefined);
});
test("an absent terminal outcome cannot become an ordinary loss", () => {
  const s = ended(); delete s.interaction.content.surface.victory;
  assert.throws(() => inspectRunInput(s, [], "worker"), /Unclassified terminal/u);
  const result = projectRunSurface({ decision: "game_over" }, {}, {
    defaultProjector: () => ({ complete: true, missing: [] }) });
  assert.equal(result.complete, false);
});
test("the same decision family is refreshed after every action", async () => {
  const first = snapshot(), next = snapshot("rest_site", 2), terminal = ended(3);
  next.bound_actions.actions[0].label = "Smith";
  const calls = []; const observations = [];
  const result = await driveRun({ mount: async () => first, read() {},
    submit: async args => { calls.push(args); return { delivery: "delivered", successor: calls.length === 1 ? next : terminal }; }
  }, { ...options, onRecord: (row, stage) => { if (stage === "observation") observations.push(row.snapshot.snapshot_id); } });
  assert.equal(result.status, "candidate_terminal"); assert.equal(result.decisions, 2);
  assert.deepEqual(calls.map(row => row.boundActionId), ["action-1", "action-2"]);
  assert.deepEqual(observations, ["snapshot-1", "snapshot-2", "snapshot-3"]);
});
test("fresh IDs alone do not hide a stalled loop", async () => {
  let sequence = 1;
  const result = await driveRun({ mount: async () => snapshot(), read() {},
    submit: async () => ({ delivery: "delivered", successor: snapshot("rest_site", ++sequence) }) }, options);
  assert.equal(result.status, "liveness_failure"); assert.equal(result.decisions, 3);
  assert.equal(publicProgressKey(snapshot(), []), publicProgressKey(snapshot("rest_site", 2), []));
});
test("a missing choice is rejected rather than silently truncated", async () => {
  const s = snapshot(); s.bound_actions.total_count = 2;
  let calls = 0;
  const result = await driveRun({ mount: async () => s, read() {}, submit: async () => calls++ }, options);
  assert.equal(result.status, "unsupported"); assert.equal(calls, 0);
});
test("unknown delivery is retained and never retried", async () => {
  let calls = 0;
  const result = await driveRun({ mount: async () => snapshot(), read() {},
    submit: async () => { calls++; return { delivery: "unknown", reason_code: "timeout" }; } }, options);
  assert.equal(result.status, "delivery_failure"); assert.equal(calls, 1); assert.equal(result.decisions, 1);
});
test("a new worker identity is unsupported rather than accepted", async () => {
  const s = snapshot(); s.session.runtime_instance_id = "other";
  const result = await driveRun({ mount: async () => s, read() {} }, options);
  assert.equal(result.status, "unsupported"); assert.equal(result.decisions, 0);
});
test("an incomplete read cannot enter a diagnostic policy input", () => {
  const s = snapshot();
  assert.throws(() => inspectRunInput(s, [{ expected_snapshot_id: s.snapshot_id, observed_snapshot_id: s.snapshot_id,
    completeness: { status: "partial" }, information_policy: { includes_hidden_information: false } }], "worker"), /Incomplete or stale public read/u);
});
test("the decision cap stays separate from a real ending", async () => {
  const result = await driveRun({ mount: async () => snapshot(), read() {} }, { ...options, maxDecisions: 0 });
  assert.equal(result.status, "decision_cap"); assert.equal(result.terminal, false);
});
test("boundary checks scan nested entries, not words in visible descriptions", () => {
  assert.doesNotThrow(() => assertPublicBoundary({ description: "seed and rng are words" }));
  assert.throws(() => assertPublicBoundary({ cards: [{ properties: { rng: 8 } }] }), /Private engine field/u);
});
for (const kind of ["reward_claim", "card_reward_selection", "treasure_relic_selection", "card_bundle_selection"]) {
  test(`the actual SDK ${kind} decision family is supported`, () => {
    assert.equal(inspectRunInput(snapshot(kind), [], "worker").terminal, false);
  });
}
test("a fabricated wrapper ending does not pass native ending evidence", () => {
  assert.throws(() => checkNativeEnding({ status: "candidate_terminal", victory: false }, {
    native_game_over: false, native_victory_room: false, native_player_dead: false }), /disagrees/u);
  assert.throws(() => checkNativeEnding({ status: "candidate_terminal", victory: true }, {
    native_game_over: true, native_victory_room: false, native_player_dead: false }), /disagrees/u);
  assert.throws(() => checkNativeEnding({ status: "candidate_terminal", victory: false }, {}), /Missing native/u);
  assert.equal(checkNativeEnding({ status: "candidate_terminal", victory: false }, {
    native_game_over: true, native_victory_room: false, native_player_dead: false }), true);
});
test("total agent compute includes more than just the action scorer", async () => {
  const result = await driveRun({ mount: async () => snapshot(), read() {} }, { ...options, wholeRunBudget: 0 });
  assert.equal(result.status, "compute_cap"); assert.equal(result.decisions, 0);
});
for (const canSkip of [false, true]) {
  test(`generated choice exposes only native canSkip=${canSkip} permissions`, () => {
    const actions = [];
    const ctx = { referent: row => ({ ...row, properties: row.properties }), action: row => actions.push(row) };
    const result = projectRunSurface({ decision: "generated_card_choice", selection_ref: "current",
      can_skip: canSkip, cards: [{ index: 0, name: "First" }, { index: 1, name: "Second" }] }, ctx,
      { cardProperties: row => ({ name: row.name }), withoutDeck: row => row });
    assert.equal(result.complete, true);
    assert.equal(actions.filter(row => row.verb === "select").length, 2);
    assert.equal(actions.filter(row => row.verb === "skip").length, canSkip ? 1 : 0);
    assert.equal(actions.some(row => row.verb === "confirm"), false);
  });
}
