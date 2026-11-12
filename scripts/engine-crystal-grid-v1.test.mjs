import assert from "node:assert/strict";
import test from "node:test";
import { crystalGrid, projectSelectionFlows } from "./engine-crystal-grid-v1.mjs";

function nativeGrid() {
  const coordinates = Array.from({ length: 121 }, (_, index) =>
    `(${Math.floor(index / 11)},${index % 11})`);
  const visible = coordinates.map((cell, index) => `${cell}: ${index ? "covered" : "empty"}`);
  const options = ["Small", "Big"].flatMap(tool => coordinates.map(cell => ({
    title: `${tool} at ${cell}`, description: `Use ${tool} on visible grid coordinate ${cell}.`,
    is_locked: false,
  }))).map((option, index) => ({ ...option, index }));
  return {
    decision: "event_choice", event_id: "CRYSTAL_SPHERE", event_name: "Crystal Sphere — grid",
    description: `Divinations remaining: 3. Visible grid: ${visible.join("; ")}`,
    context: { room_type: "Event" }, options,
    player: { native_ref: "player-1", hp: 30, max_hp: 80, potions: [{
      native_ref: "potion-1", id: "FRUIT_JUICE", slot: 0, name: "Fruit Juice", description: "Heal",
      usage: "AnyTime", can_use: true, can_discard: true, binding_supported: true, target_type: "Self",
    }] },
  };
}

test("Crystal Sphere exposes every native index and keeps the potion belt usable", () => {
  const state = nativeGrid(), actions = [];
  const context = {
    snapshotId: "snapshot", id: (...fields) => fields.join(":"),
    referent: row => ({ ...row, properties: row.properties }),
    action: row => actions.push(row),
  };
  const view = projectSelectionFlows(state, context, {
    withoutDeck: ({ deck, ...player }) => player,
    cardProperties: row => ({ definition_id: row.id }),
    visibleText: text => text,
  });
  assert.equal(view.complete, true);
  assert.equal(view.kind, "event_option");
  assert.equal(view.surface.description, state.description);
  assert.deepEqual(view.surface.options, state.options);
  assert.deepEqual(actions.slice(0, 242).map(row => row.raw),
    state.options.map(row => ({ cmd: "action", action: "choose_option", args: { option_index: row.index } })));
  assert.deepEqual(actions.slice(242).map(row => row.raw.action), ["use_potion", "discard_potion"]);
  assert.equal(actions[0].label, "Small at (0,0)");
  assert.equal(actions[121].label, "Big at (0,0)");
});

test("Only the grid uses the tool-and-coordinate contract", () => {
  const state = nativeGrid();
  assert.equal(crystalGrid({ ...state, event_name: "Crystal Sphere" }), null);
  assert.equal(crystalGrid({ ...state, event_id: "OTHER_EVENT" }), null);
  assert.throws(() => crystalGrid({ ...state, options: state.options.slice(1) }), /Incomplete/);
  assert.throws(() => crystalGrid({ ...state, description: state.description.replace("(0,0)", "(0,1)") }),
    /coordinates differ/);
  assert.throws(() => crystalGrid({ ...state, description: state.description.replace("3.", "0.") }),
    /Incomplete/);
  for (const changed of [{ index: 1 }, { title: "Big at (0,0)" }, { is_locked: true }]) {
    const options = [{ ...state.options[0], ...changed }, ...state.options.slice(1)];
    assert.throws(() => crystalGrid({ ...state, options }), /choice differs/);
  }
});
