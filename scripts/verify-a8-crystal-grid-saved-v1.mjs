// Reproject the saved native transition without delivering its historical action.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { preparePlayerProjection } from "./engine-player-projection-v3.mjs";
import { projectSelectionFlows as previous, selectionFlowReads } from "./engine-combat-selector-belt-v2.mjs";
import { crystalGrid, projectSelectionFlows } from "./engine-crystal-grid-v1.mjs";
import { flowWorkerInput } from "./engine-a8-mixed-practice-worker-v2.mjs";
import { sharedDecision } from "./engine-shared-input-v17.mjs";
import { inspectRunInput } from "./engine-run-contract-v7.mjs";

const { offer, grid, ...spec } = JSON.parse(readFileSync(0, "utf8"));
const { module } = await preparePlayerProjection(spec);
const runtime = "saved-crystal-grid";
let nativeBindings = 0;
const sessionFor = projector => new module.ManagedPlayerEnvironmentSession({
  process: { async request(request) {
    if (request.cmd === "start_run") return offer;
    assert.deepEqual(request, { cmd: "action", action: "choose_option", args: { option_index: 1 } });
    nativeBindings++;
    return grid;
  } },
  character: "Ironclad", ascension: 8, runtimeInstanceId: runtime, environmentFingerprint: runtime,
  surfaceProjector: projector, readProjector: selectionFlowReads, validateSdk: true,
});
const reads = (session, snapshot) => snapshot.reads.map(row =>
  session.read({ readId: row.read_id, expectedSnapshotId: snapshot.snapshot_id }));
const old = sessionFor(previous), repaired = sessionFor(projectSelectionFlows);
const oldOffer = await old.mount({ seed: "SAVEDONLY" }), newOffer = await repaired.mount({ seed: "SAVEDONLY" });
const withoutTime = ({ observed_at, ...value }) => value;
assert.deepEqual(withoutTime(oldOffer), withoutTime(newOffer));
assert.deepEqual(reads(old, oldOffer).map(withoutTime), reads(repaired, newOffer).map(withoutTime));
const purchase = (session, snapshot) => session.submit({
  requestId: "saved-grid-handoff", expectedSnapshotId: snapshot.snapshot_id,
  boundActionId: snapshot.bound_actions.actions.find(a => a.label === "Payment Plan").bound_action_id,
});
await assert.rejects(purchase(old, oldOffer), /Missing native public event-option export fields/);
const receipt = await purchase(repaired, newOffer);
assert.equal(receipt.delivery, "delivered");
const snapshot = receipt.successor, currentReads = reads(repaired, snapshot);
const frame = sharedDecision(snapshot, currentReads);
const native = crystalGrid(grid);
assert.equal(native.divinations, 6);
assert.equal(inspectRunInput(snapshot, currentReads, runtime).terminal, false);
assert.equal(frame.source_family, "event_option");
assert.equal(frame.actions.length, 242);
assert.equal(flowWorkerInput(snapshot, currentReads, null).candidates.length, 242);
const bindings = frame.actions.map(binding => snapshot.bound_actions.actions[binding.raw_index]);
assert.equal(new Set(bindings.map(a => a.bound_action_id)).size, 242);
assert.deepEqual(bindings.map(a => a.label).sort(), native.options.map(a => a.title).sort());
assert.equal(snapshot.interaction.content.surface.description, grid.description);
assert.equal(nativeBindings, 2);
console.log(JSON.stringify({
  ordinary_offer_exact: true, legacy_error_reproduced: true, complete_grid_actions: bindings.length,
  visible_board_exact: true, divinations: native.divinations, native_game_launches: 0,
}));
