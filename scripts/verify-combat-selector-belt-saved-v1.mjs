// Reproject a previously returned native state without launching a game.
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {preparePlayerProjection} from "./engine-player-projection-v3.mjs";
import {projectSelectionFlows as previous} from "./engine-abandon-confirmation-surface-v1.mjs";
import {projectSelectionFlows, selectionFlowReads} from "./engine-combat-selector-belt-v1.mjs";
import {inspectRunInput} from "./engine-run-contract-v7.mjs";

const {state, ...spec} = JSON.parse(readFileSync(0, "utf8"));
const {module} = await preparePlayerProjection(spec);
const runtimeId = "saved-selector-probe";
const options = {state, sequence: 1, runtimeInstanceId: runtimeId,
  environmentFingerprint: "saved-selector-regression", validateSdk: true,
  readProjector: selectionFlowReads};

async function read(surfaceProjector) {
  const session = new module.ManagedPlayerEnvironmentSession({
    process: {async request(request) {
      assert.equal(request.cmd, "start_run");
      return structuredClone(state);
    }},
    runtimeInstanceId: runtimeId, environmentFingerprint: options.environmentFingerprint,
    surfaceProjector, readProjector: selectionFlowReads, validateSdk: true,
  });
  const snapshot = await session.mount({seed: "SAVEDONLY"});
  return {snapshot, reads: snapshot.reads.map(row => session.read({
    readId: row.read_id, expectedSnapshotId: snapshot.snapshot_id,
  }))};
}

const old = await read(previous);
assert.throws(() => inspectRunInput(old.snapshot, old.reads, runtimeId),
  /unsupported_noncombat_potion_target/);
const {snapshot, reads} = await read(projectSelectionFlows);
assert.equal(inspectRunInput(snapshot, reads, runtimeId).terminal, false);
const proof = module.projectManagedCandidateDecision({...options, surfaceProjector: projectSelectionFlows});
assert.equal(proof.snapshot.snapshot_id, snapshot.snapshot_id);
const actions = snapshot.bound_actions.actions;
assert.equal(snapshot.interaction.kind, "card_selection");
assert.deepEqual(actions.filter(a => a.verb === "confirm").map(a => a.label),
  ["Confirm Second Wind", "Confirm Bash"]);
const [foul] = state.player.potions;
assert.equal(foul.id, "FOUL_POTION");
assert.equal(foul.target_type, "AllEnemies");
for (const verb of ["use_potion", "discard_potion"]) {
  const matches = actions.filter(a =>
    proof.bindings.get(a.bound_action_id).raw_request.action === verb);
  assert.equal(matches.length, 1);
  const raw = proof.bindings.get(matches[0].bound_action_id).raw_request;
  assert.deepEqual(raw.args, {potion_ref: foul.native_ref, potion_slot: foul.slot});
}
assert.equal(actions.length, 4);
assert.equal(new Set(snapshot.referents.map(row => row.referent_id)).size, snapshot.referents.length);
console.log(JSON.stringify({old_rejected: true, supported_menu: true,
  selector_choices: 2, potion_uses: 1, potion_discards: 1, native_game_launches: 0,
  snapshot, reads}));
