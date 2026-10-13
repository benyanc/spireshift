import test from "node:test";
import assert from "node:assert/strict";
import { naturalTutorialAction } from "./engine-natural-tutorial-v1.mjs";

function shuffle() {
  return { status: "interactive", session: { runtime_instance_id: "one" },
    information_policy: { includes_hidden_information: false }, completeness: { status: "complete" },
    interaction: { interaction_id: "tutorial", kind: "tutorial", content: {
      surface: { tutorial_id: "shuffle_ftue", stage: "confirmation", title: "Shuffle", body: "Draw resumes.",
        options: [{ semantic_id: "dismiss_tutorial", label: "Continue", enabled: true }] },
      context: { kind: "combat", round: 4, is_play_phase: false,
        player: { hand: [{ name: "A" }, { name: "B" }], draw_pile_count: 0, discard_pile_count: 9 } } } },
    bound_actions: { status: "complete", materialized_count: 1, total_count: 1,
      actions: [{ bound_action_id: "current", interaction_id: "tutorial", verb: "activate", arguments: [], label: "Continue" }] } };
}
test("a partial hand and a later round do not prevent a real reshuffle confirmation", () => {
  assert.equal(naturalTutorialAction(shuffle()).bound_action_id, "current");
});
test("a tutorial without a pending reshuffle is rejected", () => {
  const s = shuffle(); s.interaction.content.context.player.draw_pile_count = 2;
  assert.throws(() => naturalTutorialAction(s), /pending native reshuffle/u);
});
for (const change of [
  s => s.interaction.content.surface.options[0].enabled = false,
  s => s.interaction.content.surface.options[0].semantic_id = "other",
  s => s.bound_actions.actions[0].interaction_id = "previous",
  s => s.bound_actions.total_count = 2,
  s => s.interaction.content.surface.tutorial_id = "unknown_ftue",
]) test("an unavailable, stale, incomplete or unknown tutorial is not blindly dismissed", () => {
  const s = shuffle(); change(s); assert.throws(() => naturalTutorialAction(s));
});
