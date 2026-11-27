// Replay a saved public projection through the frozen SDK, without a native process.
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {projectSelectionFlows as old} from "./engine-ordered-plan-surface-v1.mjs";
import {projectSelectionFlows as repaired, selectionFlowReads} from "./engine-generated-choice-belt-surface-v1.mjs";
import {preparePlayerProjection} from "./engine-player-projection-v3.mjs";
import {sharedDecision} from "./engine-shared-input-v16.mjs";

const {projection, state} = JSON.parse(readFileSync(0, "utf8"));
const {module: {projectManagedCandidateDecision: project, ManagedPlayerEnvironmentSession}}
  = await preparePlayerProjection(projection);
const options = {state, runtimeInstanceId: "saved-generated-choice-belt", environmentFingerprint: "saved-only",
  sequence: 5, readProjector: selectionFlowReads, validateSdk: true};
assert.equal(state.decision, "generated_card_choice");
assert.equal(state.selection_owner.kind, "combat");
assert.throws(() => project({...options, surfaceProjector: old}), /referent ids must be unique/);
const rejected = project({...options, validateSdk: false, surfaceProjector: old});
const duplicate = rejected.snapshot.referents.filter((value, index, rows) =>
  rows.findIndex(item => item.referent_id === value.referent_id) !== index);
assert.equal(duplicate.length, 1);
assert.equal(duplicate[0].label, "Liquid Bronze");
assert.equal(duplicate[0].role, "potion");

const fixed = project({...options, surfaceProjector: repaired});
assert.deepEqual(fixed.snapshot.persistent, rejected.snapshot.persistent);
assert.deepEqual(fixed.snapshot.interaction.content, rejected.snapshot.interaction.content);
assert.deepEqual(fixed.snapshot.bound_actions, rejected.snapshot.bound_actions);
assert.deepEqual(fixed.bindings, rejected.bindings);
assert.deepEqual(fixed.reads, rejected.reads);
assert.equal(fixed.snapshot.referents.length, rejected.snapshot.referents.length - 1);
assert.equal(new Set(fixed.snapshot.referents.map(ref => ref.referent_id)).size, fixed.snapshot.referents.length);

const raw = [...fixed.bindings.values()].map(binding => binding.raw_request);
assert.deepEqual(raw.filter(row => row.action === "select_cards").map(row => row.args.indices).sort(), ["0", "1", "2"]);
assert.ok(raw.filter(row => row.action === "select_cards").every(row => row.args.selection_ref === state.selection_ref));
assert.deepEqual(raw.filter(row => row.action === "skip_select").map(row => row.args), [{selection_ref: state.selection_ref}]);
const [held] = state.player.potions;
assert.deepEqual(raw.filter(row => row.action === "discard_potion").map(row => row.args), [{
  potion_slot: held.slot, potion_ref: held.native_ref
}]);
assert.ok(!raw.some(row => ["use_potion", "play_card", "end_turn"].includes(row.action)));

const session = new ManagedPlayerEnvironmentSession({
  process: {request() {throw Error("Saved regression must not execute native commands");}},
  runtimeInstanceId: options.runtimeInstanceId, environmentFingerprint: options.environmentFingerprint,
  surfaceProjector: repaired, readProjector: selectionFlowReads, validateSdk: true
});
const snapshot = await session.acceptNativeObservation(state);
const reads = snapshot.reads.map(row => session.read({readId: row.read_id, expectedSnapshotId: snapshot.snapshot_id}));
const shared = sharedDecision(snapshot, reads);
assert.equal(shared.source_family, "native_generated_card_choice");
assert.equal(shared.public_input.candidates.length, 5);

const empty = structuredClone(state);
empty.player.potions = [];
empty.selection_combat.player.potions = [];
const before = project({...options, state: empty, surfaceProjector: old});
const after = project({...options, state: empty, surfaceProjector: repaired});
assert.deepEqual({...after.snapshot, observed_at: null}, {...before.snapshot, observed_at: null});
assert.deepEqual(after.bindings, before.bindings);
assert.deepEqual(after.reads, before.reads);

const duplicates = structuredClone(state);
const playerRef = duplicates.player.native_ref;
const sameType = [0, 2].map(slot => ({
  ...held, id: "BLOOD_POTION", name: "Blood Potion", description: "Heal for 20% of your Max HP.",
  slot, native_ref: `test-potion-${slot}`, can_use: true, usage: "AnyTime", target_type: "AnyPlayer",
  valid_target_refs: [playerRef]
}));
duplicates.player.potions = sameType;
duplicates.selection_combat.player.potions = sameType;
const withCopies = project({...options, state: duplicates, surfaceProjector: repaired});
const uses = [...withCopies.bindings.values()].map(binding => binding.raw_request)
  .filter(row => row.action === "use_potion");
assert.deepEqual(uses.map(row => row.args), sameType.map(row => ({
  potion_slot: row.slot, potion_ref: row.native_ref, target_ref: playerRef
})));
const playerTargets = withCopies.snapshot.bound_actions.actions.filter(row => row.verb === "use")
  .map(row => row.arguments[0].referent_id);
assert.equal(playerTargets.length, 2);
assert.equal(new Set(playerTargets).size, 1);
assert.equal(withCopies.snapshot.referents.filter(row => row.referent_id === playerTargets[0]).length, 1);
console.log(JSON.stringify({
  old_strict_decoder_rejects: true, duplicate_label: duplicate[0].label,
  repaired_strict_sdk_and_converter_pass: true, preserved_raw_actions: raw.length,
  preserved_public_reads: reads.length, empty_belt_observation_unchanged: true,
  distinct_copies_and_single_player_target_verified: true,
  new_games: 0, optimizer_updates: 0
}));
