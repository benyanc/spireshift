import test from "node:test";
import assert from "node:assert/strict";
import { publicPolicyInput, stableJson } from "./engine-public-input-v1.mjs";
import { chooseRunAction, publicActionKey } from "./engine-run-policy-v5.mjs";

function combat() {
  const enemies = [12, 15].map((hp, i) => ({ referent_id: `enemy-${i}`, role: "enemy", label: "Rat",
    properties: { entity_id: `enemy-${i}`, hp, statuses: [{ name: "Weak", amount: i + 1 }],
      intents: [{ name: "Attack", damage: 6 + i }] } }));
  return { persistent: { content: { player: { entity_id: "id-player", hp: 20 } } },
    interaction: { kind: "combat_turn", content: { surface: { target_entity_ids: enemies.map(e => e.referent_id) } } },
    referents: [{ referent_id: "id-player", role: "player", properties: {} }, ...enemies,
      { referent_id: "id-potion", role: "potion", label: "Weak Potion", properties: { cost: 0,
        target_entity_ids: enemies.map(e => e.referent_id), owner_entity_id: "id-player" } }],
    bound_actions: { actions: enemies.map((enemy, i) => ({ bound_action_id: `binding-${i}`, verb: "use",
      subject_referent_id: "id-potion", label: "Use Weak Potion on Rat",
      arguments: [{ role: "target", referent_id: enemy.referent_id }] })) } };
}
function rename(value, salt) {
  const handles = new Map(["id-player", "enemy-0", "enemy-1", "id-potion"].map((id, i) => [id, `${salt}:${i}`]));
  const walk = v => Array.isArray(v) ? v.map(walk) : v && typeof v === "object"
    ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, walk(x)])) : handles.get(v) ?? v;
  return walk(value);
}
test("nested target arrays, owners and arguments are invariant under consistent ID renaming", () => {
  const s = combat(), original = publicPolicyInput(s);
  for (let i = 0; i < 50; i++) {
    const changed = rename(s, `different-${i}`);
    assert.deepEqual(publicPolicyInput(changed), original);
    assert.equal(chooseRunAction(changed).bound_action_id, chooseRunAction(s).bound_action_id);
    for (let j = 0; j < 2; j++) assert.equal(publicActionKey(changed, changed.bound_actions.actions[j]),
      publicActionKey(s, s.bound_actions.actions[j]));
  }
  assert(!stableJson(original).includes("enemy-0"));
});
test("same-label enemies keep distinct HP, status ownership, intent and legal target bindings", () => {
  const s = combat(), input = publicPolicyInput(s), [a, b] = input.candidates;
  assert.notDeepEqual(a.arguments, b.arguments);
  assert.notEqual(publicActionKey(s, s.bound_actions.actions[0]), publicActionKey(s, s.bound_actions.actions[1]));
  const before = stableJson(input);
  [s.referents[1].properties.statuses, s.referents[2].properties.statuses] =
    [s.referents[2].properties.statuses, s.referents[1].properties.statuses];
  assert.notEqual(stableJson(publicPolicyInput(s)), before);
});
test("different card copies, costs, named amounts, counters and selection bounds remain observable", () => {
  const s = combat(); s.referents[3].properties = { cost: 1, strength: 2, dexterity: 7,
    counter: 3, expiry: "turn", selection: { minimum: 0, maximum: 2 } };
  const before = stableJson(publicPolicyInput(s));
  for (const [key, value] of [["cost", 0], ["strength", 7], ["counter", 4], ["expiry", "combat"],
    ["selection", { minimum: 1, maximum: 2 }]]) {
    const changed = structuredClone(s); changed.referents[3].properties[key] = value;
    assert.notEqual(stableJson(publicPolicyInput(changed)), before);
  }
});
test("dangling operands, hidden information, duplicate declarations and nonfinite facts fail", () => {
  const s = combat(); s.referents[3].properties.target_entity_ids.push("missing");
  assert.throws(() => publicPolicyInput(s), /Unresolved/u);
  const p = combat(); p.referents[0].properties.rng = 1;
  assert.throws(() => publicPolicyInput(p), /Private/u);
  const d = combat(); d.referents.push(d.referents[0]);
  assert.throws(() => publicPolicyInput(d), /Duplicate/u);
  const n = combat(); n.referents[1].properties.hp = NaN;
  assert.throws(() => publicPolicyInput(n), /Nonfinite/u);
});
test("reordered legal actions keep the same chosen binding and all choices remain selectable", () => {
  const s = combat(), selected = chooseRunAction(s).bound_action_id;
  s.bound_actions.actions.reverse(); assert.equal(chooseRunAction(s).bound_action_id, selected);
  for (const a of s.bound_actions.actions)
    assert.equal(chooseRunAction(s, (_, b) => a === b ? 10 : 0), a);
});
