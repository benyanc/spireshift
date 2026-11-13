// Verify the saved transition without dispatching any historical game action.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { CardAnswerPlanner } from "./engine-card-answer-v1.mjs";
import { selectionFlowReads } from "./engine-combat-selector-belt-v2.mjs";
import { projectSelectionFlows } from "./engine-crystal-grid-v1.mjs";
import { observeAfterMerchantExit } from "./engine-merchant-map-observation-v1.mjs";
import { preparePlayerProjection } from "./engine-player-projection-v3.mjs";
import { sharedDecision } from "./engine-shared-input-v17.mjs";

const { states, ...spec } = JSON.parse(readFileSync(0, "utf8"));
const [approach, open, closed, leave] = states;
const stale = leave.response.player.potions.find(potion => potion.id === "FOUL_POTION");
assert.equal(stale.can_use, true);
assert.deepEqual(stale.valid_target_refs, [closed.response.merchant_ref]);
assert.equal(leave.request.args.room_ref, closed.response.room_ref);
assert.equal(leave.response.decision, "map_select");
// Expected shape of the native read. Separate live controls verify that the
// frozen host actually returns it for both types of merchant.
const refreshed = structuredClone(leave.response);
const potion = refreshed.player.potions.find(row => row.native_ref === stale.native_ref);
potion.can_use = false;
potion.valid_target_refs = [];

const { module } = await preparePlayerProjection(spec);
function sessionFor(repair) {
  const cursor = new CardAnswerPlanner();
  let index = 1, reads = 0;
  const session = new module.ManagedPlayerEnvironmentSession({
    process: { async request(request) {
      if (request.cmd === "start_run") return cursor.observe(approach.response);
      if (request.cmd === "get_map") return spec.map;
      const pair = states[index++];
      assert.deepEqual(request, pair.request);
      const response = cursor.observe(pair.response);
      return repair ? observeAfterMerchantExit(request, response, next => {
        assert.deepEqual(next, { cmd: "observe" });
        reads++;
        return refreshed;
      }) : response;
    } }, character: "Ironclad", ascension: 8, runtimeInstanceId: "saved-merchant-map",
    environmentFingerprint: "saved-merchant-map", surfaceProjector: projectSelectionFlows,
    readProjector: selectionFlowReads, validateSdk: true,
  });
  return { session, reads: () => reads };
}

const legacy = sessionFor(false), fixed = sessionFor(true);
async function submit(session, before, label) {
  const action = before.bound_actions.actions.find(row => row.label === label);
  assert(action);
  return session.submit({ requestId: label, expectedSnapshotId: before.snapshot_id,
    boundActionId: action.bound_action_id });
}
function reads(session, snapshot) {
  return snapshot.reads.map(row => session.read({ readId: row.read_id, expectedSnapshotId: snapshot.snapshot_id }));
}

let old = await legacy.session.mount({ seed: "SAVEDONLY" });
let current = await fixed.session.mount({ seed: "SAVEDONLY" });
for (const [label, canUse] of [["Open shop inventory", true], ["Close shop inventory", false],
  ["Leave shop and open map", true]]) {
  assert.equal(current.bound_actions.status, "complete");
  assert.equal(current.bound_actions.actions.some(a => a.label === "Use Foul Potion on Merchant"), canUse);
  assert.deepEqual(sharedDecision(old, reads(legacy.session, old)).public_input,
    sharedDecision(current, reads(fixed.session, current)).public_input);
  const [before, after] = await Promise.all([
    submit(legacy.session, old, label), submit(fixed.session, current, label),
  ]);
  assert.equal(before.delivery, "delivered");
  assert.equal(after.delivery, "delivered");
  old = before.successor;
  current = after.successor;
}

assert.equal(old.bound_actions.status, "unavailable");
assert(old.completeness.missing.includes("native_potion_merchant_target"));
assert.equal(current.bound_actions.status, "complete");
const frame = sharedDecision(current, reads(fixed.session, current));
assert.equal(frame.source_family, "map_navigation");
assert.equal(frame.actions.length, leave.response.choices.length + leave.response.player.potions.length);
assert.equal(frame.public_input.candidates.filter(a => a.label.startsWith("Choose ")).length, leave.response.choices.length);
assert(frame.public_input.candidates.some(a => a.label === "Discard Foul Potion"));
assert(!frame.public_input.candidates.some(a => a.label === "Use Foul Potion on Merchant"));
assert.equal(legacy.reads(), 0);
assert.equal(fixed.reads(), 1);
console.log(JSON.stringify({ saved_shop_menus_exact: 3, original_error_reproduced: true,
  map_choices: leave.response.choices.length, legal_belt_choices: leave.response.player.potions.length,
  read_only_refreshes: fixed.reads(), native_games_launched: 0 }));
