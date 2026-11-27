import assert from "node:assert/strict";
import test from "node:test";
import { projectExactRestSurface } from "./engine-rest-surface.mjs";

// Synthetic public contract inputs, no game data, SDK installation, or proprietary source.
function project(state, limit = 512) {
  const ctx = { referents: [], actions: [], bindings: new Map(),
    referent(value) {
      const id = `r${this.referents.length}`;
      const item = { ...value, referent_id: id, properties: { ...value.properties, entity_id: id } };
      this.referents.push(item); return item;
    },
    action(value) {
      this.actions.push(value); this.bindings.set(this.actions.length, value.raw);
    } };
  const helpers = { withoutDeck: (value) => value, cardProperties: ({ name }) => ({ name }),
    visibleText: (value) => value ?? null, actionLimit: limit,
    defaultProjector: () => ({ default: true }),
    enumerateSelections(items, min, max, cap) {
      const rows = [];
      function visit(start, chosen, count) {
        if (rows.length >= cap) return;
        if (!count) { rows.push(chosen); return; }
        for (let i = start; i < items.length; i++) visit(i + 1, [...chosen, items[i]], count - 1);
      }
      for (let count = min; count <= Math.min(max, items.length); count++) visit(0, [], count);
      return rows;
    } };
  return { result: projectExactRestSurface(state, ctx, helpers), ...ctx };
}
const rest = () => ({ decision: "rest_site", room_ref: "PRIVATE_ROOM", can_leave: false, options: [
  { index: 0, native_ref: "PRIVATE_HEAL", option_id: "HEAL", name: "Rest", is_enabled: true },
  { index: 1, native_ref: "PRIVATE_UPGRADE", option_id: "SMITH", name: "Upgrade", is_enabled: true }
] });
const select = () => ({ decision: "card_select", cards: [{ index: 0, name: "Example" }],
  min_select: 1, max_select: 1, cancelable: true, require_manual_confirmation: true });

test("rest choices retain native operands privately and advertise only enabled actions", () => {
  const state = rest(); state.options[1].is_enabled = false;
  const actual = project(state);
  assert.equal(actual.actions.length, 1);
  assert.deepEqual(actual.bindings.get(1).args,
    { room_ref: "PRIVATE_ROOM", option_ref: "PRIVATE_HEAL", option_index: 0 });
  const publicJson = JSON.stringify({ result: actual.result, referents: actual.referents });
  assert.doesNotMatch(publicJson, /PRIVATE_|native_ref|room_ref|option_ref/u);
  assert.equal(actual.result.surface.options.length, 2);
  assert.equal(actual.result.surface.options[1].is_enabled, false);
});
test("refreshed choices and Proceed follow native state including early leave and exhausted menus", () => {
  const state = rest(); state.options = [{ ...state.options[1], index: 0 }]; state.can_leave = true;
  const actual = project(state);
  assert.deepEqual(actual.actions.map((action) => action.verb), ["activate", "close"]);
  assert.equal(actual.bindings.get(1).args.option_index, 0);
  assert.equal(actual.bindings.get(1).args.option_ref, "PRIVATE_UPGRADE");
  assert.equal(actual.bindings.get(2).action, "leave_room");
  state.options = [];
  assert.equal(project(state).actions.length, 1);
  state.can_leave = false;
  assert.equal(project(state).actions.length, 0);
});
test("missing, aliased, or malformed rest authority never creates an actionable menu", () => {
  for (const mutate of [
    (state) => { delete state.room_ref; }, (state) => { delete state.can_leave; },
    (state) => { delete state.options; }, (state) => { delete state.options[0].native_ref; },
    (state) => { delete state.options[0].is_enabled; }, (state) => { state.options[0].is_enabled = "yes"; },
    (state) => { state.options[1].index = 0; },
    (state) => { state.options[1].index = 999; },
    (state) => { state.options[1].native_ref = state.options[0].native_ref; }
  ]) {
    const state = rest(); mutate(state); const actual = project(state);
    assert.equal(actual.result.complete, false); assert.equal(actual.actions.length, 0);
  }
});
test("single-card upgrade still needs explicit confirmation and can cancel", () => {
  const actual = project(select());
  assert.deepEqual(actual.actions.map((action) => action.verb), ["confirm", "cancel"]);
  assert.equal(actual.bindings.get(1).args.indices, "0");
  assert.equal(actual.bindings.get(2).action, "skip_select");
  assert.equal(actual.result.surface.require_manual_confirmation, true);
  assert.equal(actual.result.surface.cancelable, true);
});
test("empty confirmation and cancellation remain distinct; native bounds are not clamped", () => {
  const state = select(); state.min_select = 0; state.cancelable = false;
  const actual = project(state);
  assert.deepEqual(actual.actions.map((action) => action.verb), ["confirm", "confirm"]);
  assert.equal(actual.bindings.get(1).args.indices, "");
  assert.equal(actual.result.surface.cancelable, false);
  state.min_select = 2; state.max_select = 2;
  assert.equal(project(state).result.complete, false);
  assert.equal(project(state).actions.length, 0);
});
test("unknown selection preferences, invalid indices/bounds and capped combinations fail closed", () => {
  for (const mutate of [
    (state) => { delete state.min_select; }, (state) => { state.max_select = 0; },
    (state) => { delete state.cancelable; }, (state) => { delete state.require_manual_confirmation; },
    (state) => { state.cards[0].index = -1; }, (state) => { state.min_select = -1; },
    (state) => { state.cards[0].index = 999; },
    (state) => { state.cards.push({ index: 0, name: "Duplicate" }); }
  ]) {
    const state = select(); mutate(state); const actual = project(state);
    assert.equal(actual.result.complete, false); assert.equal(actual.actions.length, 0);
  }
  const limited = project(select(), 1);
  assert.equal(limited.result.complete, false); assert.equal(limited.result.totalCount, 2);
  assert.equal(limited.actions.length, 0);
});
test("other decision families delegate without asserting new qualification", () => {
  assert.deepEqual(project({ decision: "shop" }).result, { default: true });
});
