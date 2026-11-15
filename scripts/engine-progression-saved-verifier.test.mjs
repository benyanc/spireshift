import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

function snapshot(kind, sequence) {
  const action = { bound_action_id: `action-${sequence}`, interaction_id: `screen-${sequence}`,
    label: kind === "reward_claim" ? "Continue from rewards" : "Threaten", verb: "activate", arguments: [] };
  return { snapshot_id: `state-${sequence}`, sequence, status: "interactive",
    session: { runtime_instance_id: "worker" }, information_policy: { includes_hidden_information: false },
    completeness: { status: "complete" }, persistent: { content: {
      run: { act: 3, act_definition_id: "EXAMPLE", ascension: 8 },
      player: { character_definition_id: "IRONCLAD", hp: kind === "game_over" ? 0 : 80 } } },
    interaction: { kind, interaction_id: `screen-${sequence}`, content: {
      surface: { kind, can_proceed: kind === "reward_claim" }, context: kind === "game_over"
        ? { kind, result: "win", game_mode: "standard" } : { event_id: "THE_ARCHITECT" } } },
    bound_actions: { status: "complete", total_count: 1, materialized_count: 1, actions: [action] } };
}
function fixture() {
  const snapshots = [snapshot("reward_claim", 1), snapshot("event_option", 2), snapshot("game_over", 3)];
  return { shutdown_requested: true, capabilities: { host: { runtime_instance_id: "worker" } }, snapshots,
    receipts: snapshots.slice(0, 2).map((before, index) => ({ before, phase: index ? "architect" : "proceed",
      expected_snapshot_id: before.snapshot_id, action: before.bound_actions.actions[0], receipt: {
        request_id: `request-${index}`, delivery: "delivered", action: { bound_action_id: `action-${index + 1}` },
        attribution: { runtime_instance_id: "worker" } } })) };
}
function reordered(value) {
  if (Array.isArray(value)) return value.map(reordered);
  if (value && typeof value === "object") return Object.fromEntries(Object.keys(value).sort().map(key => [key, reordered(value[key])]));
  return value;
}
for (const changed of [false, true]) {
  test(changed ? "saved audit rejects changed evidence" : "saved audit accepts reordered object keys without replay", () => {
    const directory = mkdtempSync(path.join(tmpdir(), "spireshift-progression-test-"));
    try {
      const original = fixture(), control = structuredClone(original);
      if (changed) control.snapshots.at(-1).interaction.content.context.result = "loss";
      const shipped = { probe: reordered(original), checks: { isolated: true },
        verdict: { status: "shipped_checkpoint_input_pass" }, training_allowed: false, full_run_attempts: 0 };
      const filenames = Object.fromEntries(["shipped", "control", "fixture"].map(name => [name, path.join(directory, `${name}.json`)]));
      writeFileSync(filenames.shipped, JSON.stringify(shipped));
      writeFileSync(filenames.control, JSON.stringify(control));
      writeFileSync(filenames.fixture, JSON.stringify({ act: 3, target: { act: 3, act_definition_id: "EXAMPLE" } }));
      const result = spawnSync(process.execPath, [new URL("./verify-engine-progression-saved-v4.mjs", import.meta.url).pathname], {
        input: JSON.stringify(filenames), encoding: "utf8", timeout: 3000 });
      assert.equal(result.status === 0, !changed, result.stderr);
      if (!changed) { assert.equal(JSON.parse(result.stdout).games_replayed, 0); assert.equal(JSON.parse(result.stdout).natural_victories, 0); }
    } finally { rmSync(directory, { recursive: true, force: true }); }
  });
}
