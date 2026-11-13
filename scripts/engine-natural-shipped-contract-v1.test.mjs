import test from "node:test";
import assert from "node:assert/strict";
import { shippedEnding } from "./engine-natural-shipped-contract-v1.mjs";

const end = result => ({ status: "interactive", session: { runtime_instance_id: "one" },
  information_policy: { includes_hidden_information: false }, completeness: { status: "complete" },
  interaction: { kind: "game_over", content: { surface: { kind: "game_over", stage: "intro" },
    context: { kind: "game_over", game_mode: "standard", result } } } });
test("ordinary shipped win and loss use the explicit public result", () => {
  assert.equal(shippedEnding(end("win"), "one").victory, true);
  assert.equal(shippedEnding(end("loss"), "one").victory, false);
});
for (const change of [
  s => delete s.interaction.content.context.result,
  s => s.interaction.content.context.result = "unknown",
  s => s.interaction.content.context.game_mode = "custom",
  s => s.session.runtime_instance_id = "other",
  s => s.status = "settling",
  s => s.completeness.status = "partial",
]) test("a missing, different or incomplete ending cannot be turned into a loss", () => {
  const s = end("loss"); change(s); assert.throws(() => shippedEnding(s, "one"));
});
test("floor progress alone is not an ending", () => {
  const s = end("loss"); s.interaction.kind = "combat_turn";
  assert.equal(shippedEnding(s, "one"), null);
});
