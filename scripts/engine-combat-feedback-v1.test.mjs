import assert from "node:assert/strict";
import test from "node:test";
import {projectSelectionFlows} from "./engine-abandon-confirmation-surface-v1.mjs";
import {checkNativeEnding} from "./engine-native-ending-v1.mjs";

test("a native victory with the dead flag cannot verify a loss", () => {
  const native = {native_game_over: true, native_victory_room: true, native_player_dead: true};
  const end = {status: "candidate_terminal", victory: true};
  assert.equal(checkNativeEnding(end, native), true);
  assert.throws(() => checkNativeEnding({...end, victory: false}, native), /disagrees/);
  assert.throws(() => checkNativeEnding(end, {...native, native_victory_room: false}), /disagrees/);
  assert.throws(() => checkNativeEnding(end, {...native, native_game_over: false}), /disagrees/);
  assert.throws(() => checkNativeEnding(end, {...native, native_player_dead: null}), /Missing/);
  assert.equal(checkNativeEnding({...end, status: "in_progress"}, native), false);
});

test("abandon confirmation binds only the two native-owned answers", () => {
  const state = {
    decision: "event_choice", event_id: "ABANDON_RUN_CONFIRMATION",
    abandon_confirmation_ref: "abandon-2",
    options: ["confirm", "cancel"].map((name, index) => ({
      index, text_key: "GENERIC_POPUP." + name, is_locked: false, will_kill_player: index === 0,
    })),
  };
  const actions = [];
  const ctx = {action: value => actions.push(value)};
  const helpers = {defaultProjector(current, surface) {
    assert.equal(current, state);
    for (const option of current.options)
      surface.action({verb: "activate", raw: {action: "choose_option",
        args: {option_index: option.index}}});
    return "modal";
  }};
  assert.equal(projectSelectionFlows(state, ctx, helpers), "modal");
  assert.deepEqual(actions, [true, false].map((confirm, index) => ({
    verb: ["confirm", "cancel"][index],
    raw: {cmd: "action", action: "resolve_abandon_confirmation",
      args: {confirmation_ref: state.abandon_confirmation_ref, confirm}},
  })));
  assert.throws(() => projectSelectionFlows({...state, abandon_confirmation_ref: ""}, ctx, helpers),
    /Incomplete native abandon confirmation/);
  assert.throws(() => projectSelectionFlows(state, ctx, {
    defaultProjector(_, surface) {
      surface.action({raw: {action: "discard_potion", args: {option_index: 0}}});
    }
  }), /Unbound abandon confirmation action/);
  assert.equal(actions.length, 2);
});
