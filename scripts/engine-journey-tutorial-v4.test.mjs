import assert from "node:assert/strict";
import test from "node:test";
import { tutorialAction } from "./engine-journey-tutorial-v4.mjs";

const modal = (page) => ({
  interaction: { kind: "tutorial", content: { surface: { tutorial_id: "combat_rules_ftue", total_pages: 3,
    current_page: page, options: [{ enabled: true, semantic_id: "previous_tutorial_page", label: "Previous page" },
      { enabled: true, semantic_id: "advance_tutorial", label: page === 3 ? "Finish tutorial" : "Next page" }] } } },
  bound_actions: { actions: ["Previous page", page === 3 ? "Finish tutorial" : "Next page"].map((label) =>
    ({ label, verb: "activate", subject_referent_id: null, arguments: [] })) }
});
test("all three observed pages advance using the exact current public forward control", () => {
  for (const page of [1, 2, 3]) {
    const chosen = tutorialAction(modal(page));
    assert.equal(chosen.label, page === 3 ? "Finish tutorial" : "Next page");
  }
});
test("unknown, disabled, ambiguous and non-native controls are refused", () => {
  const unknown = modal(1); unknown.interaction.content.surface.tutorial_id = "another_tutorial";
  assert.throws(() => tutorialAction(unknown), /Unqualified/);
  const disabled = modal(3); disabled.interaction.content.surface.options[1].enabled = false;
  assert.throws(() => tutorialAction(disabled), /No unique/);
  const ambiguous = modal(2); ambiguous.bound_actions.actions.push({ ...ambiguous.bound_actions.actions[1] });
  assert.throws(() => tutorialAction(ambiguous), /uniquely/);
  const altered = modal(2); altered.bound_actions.actions[1].arguments = [{ value: 1 }];
  assert.throws(() => tutorialAction(altered), /uniquely/);
});
