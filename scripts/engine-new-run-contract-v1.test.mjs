import test from "node:test";
import assert from "node:assert/strict";
import { chooseStartupAction } from "./engine-new-run-contract-v1.mjs";
const menu = (kind, labels, surface = {}) => ({ interaction: { kind, content: { surface } },
  bound_actions: { actions: labels.map(label => ({ label })) } });
test("a new-run check cannot enter through Continue", () => {
  assert.throws(() => chooseStartupAction(menu("main_menu", ["Play", "Continue"])), /Continue/u);
});
test("standard startup does not choose custom or daily runs", () => {
  assert.equal(chooseStartupAction(menu("singleplayer_menu", ["Custom Run", "Daily Run", "Standard Run"])).label, "Standard Run");
});
test("A8 is selected before Embark", () => {
  const characters = [{ character_id: "CHARACTER.IRONCLAD", is_selected: true, is_locked: false }];
  assert.equal(chooseStartupAction(menu("character_select", ["Embark", "Increase Ascension"], { characters, ascension: 7 })).label, "Increase Ascension");
  assert.equal(chooseStartupAction(menu("character_select", ["Embark", "Decrease Ascension"], { characters, ascension: 8 })).label, "Embark");
});
test("an unavailable Ironclad or unknown startup cannot be substituted", () => {
  assert.throws(() => chooseStartupAction(menu("character_select", ["Embark"], { characters: [], ascension: 8 })), /Ironclad/u);
  assert.throws(() => chooseStartupAction(menu("unknown", ["Play"])), /Unsupported/u);
});
test("the native Yes option enables tutorials without guessing from its label", () => {
  const s = menu("tutorial", ["Yes", "No"], { tutorial_id: "accept_tutorials_ftue",
    options: [{ semantic_id: "enable_tutorials", enabled: true, label: "Yes" }] });
  assert.equal(chooseStartupAction(s).label, "Yes");
});
