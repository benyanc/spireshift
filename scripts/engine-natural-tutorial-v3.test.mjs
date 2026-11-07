import test from "node:test";
import assert from "node:assert/strict";
import { naturalTutorialAction } from "./engine-natural-tutorial-v3.mjs";
function snapshot(id, extra) {
  const options = [{ semantic_id: "dismiss_tutorial", label: "Continue", enabled: true }];
  if (extra) options.push({ semantic_id: extra, label: "Highlighted control", enabled: true });
  return { status: "interactive", session: { runtime_instance_id: "one" }, information_policy: { includes_hidden_information: false },
    completeness: { status: "complete" }, interaction: { kind: "tutorial", interaction_id: "popup", content: {
      surface: { tutorial_id: id, stage: "confirmation", title: "Guidance", body: "Visible guidance.", options } } },
    bound_actions: { status: "complete", total_count: options.length, materialized_count: options.length,
      actions: options.map((option, i) => ({ bound_action_id: `action-${i}`, interaction_id: "popup",
        verb: "activate", label: option.label, arguments: [] })) } };
}
for (const [id, extra] of [["combat_reward_ftue", null], ["can_play_cards_ftue", null],
  ["cannot_play_card_ftue", "end_turn"], ["merchant_ftue", "inspect_merchant"]]) {
  test(`the full ${id} menu retains every enabled control and acknowledges guidance`, () => {
    const s = snapshot(id, extra); assert.equal(naturalTutorialAction(s).bound_action_id, "action-0");
    assert.equal(s.bound_actions.actions.length, extra ? 2 : 1);
  });
}
test("unknown or omitted highlight controls cannot be silently ignored", () => {
  const s = snapshot("merchant_ftue", "inspect_merchant");
  s.interaction.content.surface.options[1].semantic_id = "unknown";
  assert.throws(() => naturalTutorialAction(s));
  s.interaction.content.surface.options[1].semantic_id = "inspect_merchant";
  s.bound_actions.actions.pop(); s.bound_actions.total_count = 1; s.bound_actions.materialized_count = 1;
  assert.throws(() => naturalTutorialAction(s));
});
