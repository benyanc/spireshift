// Reconstruct saved actions, issue collection and reached progress. Never starts a game.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
let input = ""; for await (const chunk of process.stdin) input += chunk;
const spec = JSON.parse(input), report = JSON.parse(readFileSync(spec.report, "utf8"));
const probe = report.shipped_report.probe;
const { completePublicMenu } = await import(pathToFileURL(`${spec.sources}/engine-menu-probe.mjs`).href);
const { startingFacts } = await import(pathToFileURL(`${spec.sources}/engine-new-run-contract-v1.mjs`).href);
const { currentBoundMenu, recordRunProgress, newIssueCollection, recordUnsupported, recoveryAction,
  assertObservationIdentity } = await import(pathToFileURL(`${spec.sources}/engine-run-diagnostics-v1.mjs`).href);
const recipe = JSON.parse(readFileSync(`${spec.sources}/recipe.json`, "utf8"));
const hasNavigation = "engine-run-policy-v3.mjs" in recipe.helpers_sha256;
const policy = await import(pathToFileURL(`${spec.sources}/engine-run-policy-${hasNavigation ? "v3" : "v2"}.mjs`).href);
const { publicActionKey, chooseRunAction } = policy;
const navigation = hasNavigation ? policy.newDiagnosticNavigation() : null;
const tutorial = "engine-natural-tutorial-v3.mjs" in recipe.helpers_sha256
  ? "engine-natural-tutorial-v3.mjs" : "engine-natural-tutorial-v2.mjs";
const { naturalTutorialAction } = await import(pathToFileURL(`${spec.sources}/${tutorial}`).href);
const limits = recipe.diagnostic_limits, runtimeId = probe.capabilities.host.runtime_instance_id;
const reference = JSON.parse(readFileSync(spec.reference, "utf8"));
assert.deepEqual(startingFacts(probe.starting_snapshot, probe.deck_read),
  startingFacts(reference.snapshot, reference.reads.find(row => row.kind === "run_deck")));
assert.equal(probe.native_provenance.actual_seed, spec.seed);
assert.equal(probe.native_provenance.runtime_instance_id, runtimeId);
assert.deepEqual(report.diagnostics, probe.diagnostics);
const reconstructed = newIssueCollection();
for (const row of probe.diagnostics.observations) {
  assertObservationIdentity(row.snapshot, runtimeId);
  try { recordUnsupported(reconstructed, row.snapshot, limits); }
  catch (error) {
    assert.ok(reconstructed.cap && probe.error?.includes("cap"));
    assert.match(error.message, /Diagnostic .*cap/u);
  }
}
if (probe.diagnostics.cap && !reconstructed.cap) {
  assertObservationIdentity(probe.diagnostics.cap.snapshot, runtimeId);
  assert.throws(() => recordUnsupported(reconstructed, probe.diagnostics.cap.snapshot, limits), /Diagnostic .*cap/u);
}
assert.deepEqual(reconstructed.cap ?? null, probe.diagnostics.cap ?? null);
assert.deepEqual(reconstructed.issues, probe.diagnostics.issues);
assert.deepEqual(reconstructed.observations, probe.diagnostics.observations);
assert.equal(reconstructed.clean, probe.diagnostics.clean);
let previous = -1, recoveries = 0;
const seen = new Set(), progressSnapshots = [];
for (const [index, row] of probe.receipts.entries()) {
  assertObservationIdentity(row.before, runtimeId);
  assert.equal(currentBoundMenu(row.before, runtimeId), true);
  assert.equal(seen.has(row.before.snapshot_id), false); seen.add(row.before.snapshot_id);
  assert.ok(row.before.sequence > previous); previous = row.before.sequence;
  assert.ok(row.before.bound_actions.actions.some(action => JSON.stringify(action) === JSON.stringify(row.action)));
  assert.equal(row.receipt.action.bound_action_id, row.action.bound_action_id);
  const gameplay = index >= probe.menu_actions_requested;
  if (row.recovery) {
    assert.equal(gameplay, true);
    const recovery = probe.diagnostics.recoveries[recoveries++];
    assert.deepEqual(recovery, { before_snapshot_id: row.before.snapshot_id, receipt_index: index,
      action_key: publicActionKey(row.before, row.action), delivery: row.receipt.delivery });
    assert.ok(probe.diagnostics.observations.some(issue => issue.snapshot.snapshot_id === row.before.snapshot_id));
    const expected = recoveryAction(row.before, runtimeId, limits, {
      ...probe.diagnostics, recoveries: probe.diagnostics.recoveries.slice(0, recoveries - 1) });
    assert.deepEqual(row.action, expected);
  } else {
    assert.equal(completePublicMenu(row.before, runtimeId), true);
    if (gameplay) assert.deepEqual(row.action, row.before.interaction.kind === "tutorial"
      ? naturalTutorialAction(row.before) : chooseRunAction(row.before, undefined, navigation));
  }
  if (gameplay) assert.equal(row.action_key, publicActionKey(row.before, row.action));
  if (row.receipt.delivery !== "delivered" || row.receipt.attribution?.runtime_instance_id !== runtimeId) {
    assert.equal(index, probe.receipts.length - 1, "Uncertain delivery cannot be replayed or followed by another action");
    assert.ok(probe.error); assert.equal(probe.gameplay.terminal, false);
  }
  if (hasNavigation && gameplay && row.receipt.attribution?.runtime_instance_id === runtimeId)
    policy.recordDiagnosticNavigation(navigation, row.before, row.action, row.receipt);
  progressSnapshots.push(row.before);
}
if (hasNavigation) assert.deepEqual(probe.diagnostic_navigation, navigation);
assert.equal(recoveries, probe.diagnostics.recoveries.length);
const startup = probe.receipts.slice(0, probe.menu_actions_requested);
assert.ok(startup.every(row => !/continue|resume/iu.test(row.action.label)));
assert.ok(startup.some(row => /^embark$/iu.test(row.action.label)));
const gameplay = probe.receipts.slice(probe.menu_actions_requested);
assert.equal(gameplay.length, probe.gameplay.decisions);
progressSnapshots.push(probe.starting_snapshot, probe.latest_snapshot,
  probe.last_progress_snapshot, ...probe.progress_observations,
  ...probe.diagnostics.observations.map(row => row.snapshot));
if (probe.terminal_snapshot) progressSnapshots.push(probe.terminal_snapshot);
const progress = { maximum_floor: 0, maximum_act: 0, last_supported_floor: 0, last_supported_act: 0 };
for (const snapshot of progressSnapshots.filter(Boolean).sort((a, b) => a.sequence - b.sequence))
  recordRunProgress(progress, snapshot, completePublicMenu(snapshot, runtimeId)
    || (snapshot.interaction.kind === "game_over" && snapshot.completeness.status === "complete"));
for (const key of ["maximum_floor", "maximum_act", "last_supported_floor", "last_supported_act", "last_observed"])
  assert.deepEqual(probe.gameplay[key], progress[key], `Progress mismatch: ${key}`);
if (probe.gameplay.terminal) {
  const { shippedEnding } = await import(pathToFileURL(`${spec.sources}/engine-natural-shipped-contract-v1.mjs`).href);
  assert.equal(shippedEnding(probe.terminal_snapshot, runtimeId).victory, probe.gameplay.victory);
}
if (report.status === "natural_shipped_run_pass") {
  assert.equal(probe.gameplay.terminal, true); assert.equal(probe.diagnostics.clean, true);
  assert.equal(recoveries, 0); assert.equal(probe.checks.natural_run_clean, true);
}
process.stdout.write(JSON.stringify({ valid: true, startup_actions: startup.length,
  gameplay_actions: gameplay.length, candidate_terminal: probe.gameplay.terminal,
  clean: probe.diagnostics.clean, unique_issues: reconstructed.issues.length, recoveries,
  reached_floor: progress.maximum_floor, last_supported_floor: progress.last_supported_floor,
  games_replayed: 0, optimizer_steps: 0, training_allowed: false }) + "\n");
