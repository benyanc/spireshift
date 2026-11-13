import test from "node:test";
import assert from "node:assert/strict";
import { naturalTutorialAction } from "./engine-natural-tutorial-v2.mjs";
function snapshot() {
  return { status: "interactive", session: { runtime_instance_id: "one" }, information_policy: { includes_hidden_information: false },
    completeness: { status: "complete" }, interaction: { kind: "tutorial", interaction_id: "popup", content: {
      surface: { tutorial_id: "map_select_ftue", stage: "confirmation", title: "Map", body: "Choose a destination.",
        options: [{ semantic_id: "dismiss_tutorial", label: "Continue", enabled: true }] }, context: { kind: "shop" } } },
    bound_actions: { status: "complete", total_count: 1, materialized_count: 1,
      actions: [{ bound_action_id: "confirm", interaction_id: "popup", verb: "activate", label: "Continue", arguments: [] }] } };
}
test("the exact map tutorial can be confirmed over its current underlying room", () => {
  assert.equal(naturalTutorialAction(snapshot()).bound_action_id, "confirm");
});
for (const change of [
  s => s.interaction.content.surface.options[0].enabled = false,
  s => s.bound_actions.actions[0].interaction_id = "stale",
  s => s.bound_actions.actions[0].label = "Other",
  s => s.interaction.content.surface.tutorial_id = "unknown_ftue",
  s => s.interaction.content.surface.body = "",
  s => s.bound_actions.total_count = 2,
  s => s.completeness.status = "partial",
]) test("unknown, missing, stale or disabled map tutorial controls stay unsupported", () => {
  const s = snapshot(); change(s); assert.throws(() => naturalTutorialAction(s));
});
