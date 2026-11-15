import assert from "node:assert/strict";
import test from "node:test";
import { projectExactBundleSurface } from "./engine-bundle-surface-v1.mjs";

const card = (id, cost = 1) => ({ id, name: id, cost, description: `Effect ${id}`, is_upgraded: false });
const state = () => ({ decision: "bundle_select", selection_ref: "PRIVATE_SELECTION",
  bundles: [ { index: 0, native_ref: "PRIVATE_A", cards: [card("A"), card("B", "X")] },
    { index: 1, native_ref: "PRIVATE_B", cards: [card("C", 0), card("C", 0)] } ] });
function project(value, limit = 512) {
  const actions = [], referents = [];
  const ctx = { referent(row) { const item = { ...row, properties: { ...row.properties,
    entity_id: `entity-${referents.length}` } }; referents.push(item); return item; },
    action(row) { actions.push(row); } };
  const helpers = { actionLimit: limit, withoutDeck: (row) => row, visibleText: (row) => row ?? null,
    cardProperties: (row) => ({ definition_id: row.id, cost: String(row.cost), is_upgraded: row.is_upgraded }) };
  return { result: projectExactBundleSurface(value, ctx, helpers), actions, referents };
}
test("all choices, repeated definitions and X/free costs retain current private bindings", () => {
  const actual = project(state());
  assert.equal(actual.result.complete, true); assert.equal(actual.actions.length, 2);
  assert.deepEqual(actual.actions[1].raw.args,
    { selection_ref: "PRIVATE_SELECTION", bundle_ref: "PRIVATE_B", bundle_index: 1 });
  assert.deepEqual(actual.result.surface.bundles[0].cards.map((row) => row.cost), ["1", "X"]);
  assert.deepEqual(actual.result.surface.bundles[1].cards.map((row) => row.definition_id), ["C", "C"]);
  assert.doesNotMatch(JSON.stringify({ surface: actual.result, referents: actual.referents }),
    /PRIVATE_|selection_ref|native_ref|bundle_ref/u);
});
test("a replaced choice instance cannot reuse old operands despite identical card contents", () => {
  const old = project(state()); const next = state(); next.selection_ref = "PRIVATE_NEW_SELECTION";
  next.bundles[1].native_ref = "PRIVATE_NEW_B";
  assert.notDeepEqual(old.actions[1].raw.args, project(next).actions[1].raw.args);
});
test("unknown, ambiguous and incomplete bundle authority never advertises a choice", () => {
  for (const change of [
    (row) => { delete row.selection_ref; }, (row) => { row.bundles = []; },
    (row) => { row.bundles[1].native_ref = row.bundles[0].native_ref; },
    (row) => { row.bundles[1].index = 0; }, (row) => { row.bundles[1].index = -1; },
    (row) => { row.bundles[1].index = "1"; }, (row) => { row.bundles[1].cards = []; },
    (row) => { delete row.bundles[0].cards[0].id; }, (row) => { row.bundles[0].cards[0].cost = "1"; },
    (row) => { row.bundles[0].cards[0].description = null; },
    (row) => { delete row.bundles[0].cards[0].is_upgraded; }
  ]) {
    const row = state(); change(row); const actual = project(row);
    assert.equal(actual.result.complete, false); assert.equal(actual.actions.length, 0);
  }
});
test("finite menu limits fail explicitly instead of silently truncating bundles", () => {
  const actual = project(state(), 1);
  assert.equal(actual.result.complete, false); assert.equal(actual.actions.length, 0);
  assert.equal(actual.result.totalCount, 2);
});
