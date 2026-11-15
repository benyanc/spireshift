import test from "node:test";
import assert from "node:assert/strict";
import { actionSemantics, publicActionKey, chooseRunAction, diagnosticScore } from "./engine-run-policy-v2.mjs";

export function choice(kind = "card_reward_selection") {
  return { interaction: { kind }, persistent: { content: { player: { hp: 80, max_hp: 80 } } },
    referents: [{ referent_id: "card", role: "card", properties: { definition_id: "STRIKE", cost: 1,
      stats: { damage: 6 }, name: "Strike" } }, { referent_id: "skip", role: "option", properties: { label: "Skip" } }],
    bound_actions: { actions: [{ bound_action_id: "take", label: "Take Strike", verb: "select", subject_referent_id: "card", arguments: [] },
      { bound_action_id: "skip-binding", label: "Skip", verb: "activate", subject_referent_id: "skip", arguments: [] }] } };
}
test("native and shipped Skip have the same meaning and score", () => {
  const s = choice(), shipped = s.bound_actions.actions[1];
  const native = { ...shipped, verb: "skip", subject_referent_id: null, label: "Skip card reward" };
  assert.equal(actionSemantics(s, native), "skip_card");
  assert.equal(publicActionKey(s, native), publicActionKey(s, shipped));
  assert.equal(diagnosticScore(s, native), diagnosticScore(s, shipped));
  assert.equal(diagnosticScore(s, shipped), diagnosticScore(s, s.bound_actions.actions[0]));
});
test("a scorer can prefer Skip or taking the card without changing legality", () => {
  const s = choice();
  assert.equal(chooseRunAction(s, (_, action) => actionSemantics(s, action) === "skip_card" ? 10 : 0).bound_action_id, "skip-binding");
  assert.equal(chooseRunAction(s, (_, action) => actionSemantics(s, action) === "take_card" ? 10 : 0).bound_action_id, "take");
});
test("reordering the menu and replacing runtime IDs does not change the preferred semantic action", () => {
  const s = choice(), original = actionSemantics(s, chooseRunAction(s));
  const reversed = structuredClone(s); reversed.bound_actions.actions.reverse();
  reversed.referents.forEach(row => { row.properties.entity_id = "fresh-id"; });
  reversed.bound_actions.actions.forEach(row => { row.bound_action_id += "-fresh"; });
  assert.equal(actionSemantics(reversed, chooseRunAction(reversed)), original);
});
test("public amount ownership and per-copy costs cannot collapse in a tie key", () => {
  const s = choice(), a = s.bound_actions.actions[0], before = publicActionKey(s, a);
  s.referents[0].properties.cost = 0; assert.notEqual(publicActionKey(s, a), before);
  s.referents[0].properties.stats = { strength: 2, dexterity: 7 };
  const amounts = publicActionKey(s, a);
  s.referents[0].properties.stats = { strength: 7, dexterity: 2 };
  assert.notEqual(publicActionKey(s, a), amounts);
});
test("leaving a shop is scored alongside buying and can be selected", () => {
  const s = choice("shop_inventory");
  s.bound_actions.actions = [{ verb: "activate", label: "Buy Strike", arguments: [], subject_referent_id: "card" },
    { verb: "close", label: "Leave shop", arguments: [] }];
  assert.equal(diagnosticScore(s, s.bound_actions.actions[0]), diagnosticScore(s, s.bound_actions.actions[1]));
  assert.equal(actionSemantics(s, chooseRunAction(s, (_, a) => actionSemantics(s, a) === "leave_shop" ? 1 : 0)), "leave_shop");
});
test("mandatory menus receive no invented skip", () => {
  const s = choice("native_deck_card_selection"); s.bound_actions.actions.pop();
  assert.equal(chooseRunAction(s).bound_action_id, "take"); assert.equal(s.bound_actions.actions.length, 1);
});
test("a card or event named Skip is not an optional decline", () => {
  const s = choice(), card = s.bound_actions.actions[0];
  card.verb = "activate"; card.label = "Skip";
  assert.equal(actionSemantics(s, card), "activate");
});
test("nonfinite scores and private policy input fail", () => {
  const s = choice(); assert.throws(() => chooseRunAction(s, () => NaN));
  s.persistent.content.player.rng = "private"; assert.throws(() => chooseRunAction(s), /Private/u);
});
