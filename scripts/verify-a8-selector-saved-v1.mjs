// Reconstruct the stopped shop handoff and its prior public frames without a game process.
import assert from "node:assert/strict";
import { createReadStream, readFileSync } from "node:fs";
import { createInterface } from "node:readline";
import { createGunzip } from "node:zlib";
import { preparePlayerProjection } from "./engine-player-projection-v3.mjs";
import { projectSelectionFlows, selectionFlowReads } from "./engine-combat-selector-belt-v2.mjs";
import { CardAnswerPlanner, PLAN } from "./engine-card-answer-v1.mjs";
import { flowWorkerInput as oldWorker } from "./engine-native-worker-v24.mjs";
import { flowWorkerInput } from "./engine-a8-mixed-practice-worker-v2.mjs";
import { sharedDecision as oldConverter } from "./engine-shared-input-v16.mjs";
import { sharedDecision } from "./engine-shared-input-v17.mjs";
import { inspectRunInput } from "./engine-run-contract-v7.mjs";
import { stableJson } from "./engine-public-input-v1.mjs";

const {state, observations, ...spec} = JSON.parse(readFileSync(0, "utf8"));
const {module} = await preparePlayerProjection(spec);
let ordinaryFrames = 0;
for await (const line of createInterface({input: createReadStream(observations).pipe(createGunzip())})) {
  const {snapshot, reads} = JSON.parse(line);
  const old = oldConverter(snapshot, reads), current = sharedDecision(snapshot, reads);
  assert.deepEqual(current.public_input, old.public_input);
  assert.deepEqual(current.actions, old.actions);
  assert.deepEqual(flowWorkerInput(snapshot, reads, null), oldWorker(snapshot, reads, null));
  ordinaryFrames++;
}

const planner = new CardAnswerPlanner(), root = planner.observe(state), runtime = "saved-selector";
const session = new module.ManagedPlayerEnvironmentSession({
  process: {async request(request) {
    if (request.cmd === "start_run") return root;
    const response = planner.handle(request);
    assert.equal(response.local, true);
    return response.response;
  }},
  character: "Ironclad", ascension: 8, runtimeInstanceId: runtime, environmentFingerprint: runtime,
  surfaceProjector: projectSelectionFlows, readProjector: selectionFlowReads, validateSdk: true,
});
let snapshot = await session.mount({seed: "SAVEDONLY"});
const readsFor = view => view.reads.map(row => session.read({readId: row.read_id,
  expectedSnapshotId: view.snapshot_id}));
const reads = readsFor(snapshot), surface = snapshot.interaction.content.surface;
assert.equal(snapshot.interaction.content.context.kind, "shop");
assert.equal(surface.selection_contract, PLAN);
assert.equal(surface.cards.length, 13);
assert.throws(() => oldWorker(snapshot, reads, null), /Shop catalog is outside/);
assert.throws(() => oldConverter(snapshot, reads), /Shop catalog is outside/);
const start = sharedDecision(snapshot, reads);
assert.equal(inspectRunInput(snapshot, reads, runtime).terminal, false);
const graph = flowWorkerInput(snapshot, reads, null);
assert.equal(start.actions.length, graph.candidates.length);
const slots = graph.context.reads.find(row => row.kind === "shop_catalog").content.declared_shop_slots.length;
assert.equal(slots, 14);

// Distinct identical copies are tied to selector order, even if the deck read
// enumerates them differently.
const permuted = structuredClone(reads);
const deck = permuted.find(row => row.kind === "run_deck").content.cards;
const facts = deck.map(({entity_id, ...card}) => stableJson(card));
const i = facts.findIndex((key, index) => facts.slice(index + 1).includes(key));
assert.ok(i >= 0);
const j = facts.indexOf(facts[i], i + 1);
[deck[i], deck[j]] = [deck[j], deck[i]];
const same = sharedDecision(snapshot, permuted);
assert.deepEqual(same.public_input, start.public_input);
assert.deepEqual(same.actions, start.actions);

for (const index of [4, 1]) {
  const id = snapshot.interaction.content.surface.cards[index].entity_id;
  const action = snapshot.bound_actions.actions.find(a => a.verb === "select" && a.subject_referent_id === id);
  const receipt = await session.submit({requestId: "saved-prefix-" + index,
    expectedSnapshotId: snapshot.snapshot_id, boundActionId: action.bound_action_id, timeoutMs: 15000});
  assert.equal(receipt.delivery, "delivered");
  snapshot = receipt.successor;
  assert.equal(sharedDecision(snapshot, readsFor(snapshot)).source_family, "card_selection");
}
const commit = planner.handle({cmd: "action", action: "ordered_answer_commit",
  args: {selection_ref: state.selection_ref, prefix: "4,1"}});
assert.equal(commit.local, false);
assert.deepEqual(commit.native, {cmd: "action", action: "select_cards",
  args: {selection_ref: state.selection_ref, indices: "4,1"}});
console.log(JSON.stringify({saved_frames_unchanged: ordinaryFrames, exact_child_controls: start.actions.length,
  catalog_slots: slots, stable_unordered_copies: true, local_prefixes: 2, native_bindings_verified: 1,
  native_game_launches: 0, optimizer_updates: 0}));
