import assert from "node:assert/strict";
import test from "node:test";
import { tutorialAction } from "./engine-journey-tutorial-v3.mjs";

const modal = (page, semantic = "advance_tutorial") => ({
  interaction: { kind: "tutorial", content: { surface: { tutorial_id: "combat_rules_ftue", total_pages: 3,
    current_page: page, options: [{ enabled: true, semantic_id: "previous_tutorial_page", label: "Previous page" },
      { enabled: true, semantic_id: semantic, label: "Forward" }] } } },
  bound_actions: { actions: ["Previous page", "Forward"].map((label) => ({ label, verb: "activate", subject_referent_id: null, arguments: [] })) }
});
test("a Previous Page button does not prevent the exact forward control from binding", () => {
  assert.equal(tutorialAction(modal(2)).label, "Forward");
  assert.equal(tutorialAction(modal(3, "dismiss_tutorial")).label, "Forward");
});
test("unknown tutorial, non-native operation and ambiguous buttons are refused", () => {
  const a = modal(2); a.interaction.content.surface.tutorial_id = "unknown";
  assert.throws(() => tutorialAction(a), /Unqualified/);
  assert.throws(() => tutorialAction(modal(3, "start_game")), /No unique/);
  const b = modal(2); b.bound_actions.actions.push({ ...b.bound_actions.actions[1] });
  assert.throws(() => tutorialAction(b), /uniquely/);
});
