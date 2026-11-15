// Saved-data reconstruction only. This file never opens a game or submits an action.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
let text = ""; for await (const chunk of process.stdin) text += chunk;
const spec = JSON.parse(text), report = JSON.parse(readFileSync(spec.report, "utf8"));
const shipped = report.shipped_report, probe = shipped.probe;
const { completePublicMenu } = await import(pathToFileURL(`${spec.sources}/engine-menu-probe.mjs`).href);
const { startingFacts } = await import(pathToFileURL(`${spec.sources}/engine-new-run-contract-v1.mjs`).href);
const runtimeId = probe.capabilities.host.runtime_instance_id;
const reference = JSON.parse(readFileSync(spec.reference, "utf8"));
assert.deepEqual(startingFacts(probe.starting_snapshot, probe.deck_read),
  startingFacts(reference.snapshot, reference.reads.find(row => row.kind === "run_deck")));
assert.equal(probe.native_provenance.actual_seed, spec.seed);
assert.equal(probe.native_provenance.runtime_instance_id, runtimeId);
let previous = -1;
const seen = new Set();
for (const row of probe.receipts) {
  assert.equal(completePublicMenu(row.before, runtimeId), true);
  assert.equal(seen.has(row.before.snapshot_id), false); seen.add(row.before.snapshot_id);
  assert.ok(row.before.sequence > previous); previous = row.before.sequence;
  assert.ok(row.before.bound_actions.actions.some(action => JSON.stringify(action) === JSON.stringify(row.action)));
  assert.equal(row.receipt.delivery, "delivered");
  assert.equal(row.receipt.action.bound_action_id, row.action.bound_action_id);
  assert.equal(row.receipt.attribution.runtime_instance_id, runtimeId);
}
const startup = probe.receipts.slice(0, probe.menu_actions_requested);
assert.ok(startup.every(row => !/continue|resume/iu.test(row.action.label)));
assert.ok(startup.some(row => /^embark$/iu.test(row.action.label)));
const gameplay = probe.receipts.slice(probe.menu_actions_requested);
if (report.natural_run) {
  assert.equal(gameplay.length, probe.gameplay.decisions);
  if (probe.gameplay.terminal) {
    const { shippedEnding } = await import(pathToFileURL(`${spec.sources}/engine-natural-shipped-contract-v1.mjs`).href);
    assert.equal(shippedEnding(probe.terminal_snapshot, runtimeId).victory, probe.gameplay.victory);
  }
}
process.stdout.write(JSON.stringify({ valid: true, startup_actions: startup.length,
  gameplay_actions: gameplay.length, candidate_terminal: probe.gameplay?.terminal === true,
  games_replayed: 0, optimizer_steps: 0, training_allowed: false }) + "\n");
