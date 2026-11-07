import assert from "node:assert/strict";
import test from "node:test";
import { actionKey, firstDifference, journeyFacts, intentAmounts, tutorialAction, tutorialGameFacts } from "./engine-journey-contract-v2.mjs";

function combat() {
  const hand = [{ entity_id: "c1", definition_id: "STRIKE_IRONCLAD", cost: "1", is_upgraded: false, can_play: true }];
  const enemies = [{ entity_id: "e1", definition_id: "NIBBIT", hp: 20, max_hp: 30, block: 0,
    statuses: [{ definition_id: "VULNERABLE_POWER", amount: 2 }], intents: [{ type: "Attack", damage: 5, hits: 2, total_damage: 10 }] }];
  const actions = [{ bound_action_id: "play1", verb: "play", subject_referent_id: "card-ref", arguments: [{ role: "target", referent_id: "enemy-ref" }], interaction_id: "i" },
    { bound_action_id: "end1", verb: "end_turn", subject_referent_id: null, arguments: [], interaction_id: "i" }];
  return { status: "interactive", session: { runtime_instance_id: "r" }, information_policy: { includes_hidden_information: false },
    completeness: { status: "complete" }, bound_actions: { status: "complete", actions, total_count: 2, materialized_count: 2 },
    interaction: { kind: "combat_turn", interaction_id: "i", content: { surface: {}, context: { round: 1, turn_owner: "player", is_play_phase: true,
      player: { hand, block: 0, energy: 3, max_energy: 3, draw_pile_count: 5, discard_pile_count: 0, exhaust_pile_count: 0,
        statuses: [{ definition_id: "STRENGTH_POWER", amount: 2 }, { definition_id: "DEXTERITY_POWER", amount: 7 }] }, enemies } } },
    referents: [{ referent_id: "card-ref", properties: hand[0] }, { referent_id: "enemy-ref", properties: enemies[0] }],
    persistent: { content: { run: { act: 1, act_definition_id: "OVERGROWTH", floor: 2, ascension: 8 },
      player: { character_definition_id: "IRONCLAD", hp: 64, max_hp: 80, gold: 99, max_potion_slots: 2,
        relics: [{ definition_id: "BURNING_BLOOD" }], potions: [] } } } };
}

test("opaque action, snapshot and entity identities may differ across hosts", () => {
  const a = combat(), b = combat();
  b.interaction.interaction_id = "other";
  b.bound_actions.actions.forEach((row) => { row.interaction_id = "other"; row.bound_action_id += "-other"; });
  b.interaction.content.context.player.hand[0].entity_id = "other-card";
  b.referents[0].properties = b.interaction.content.context.player.hand[0];
  assert.equal(firstDifference(journeyFacts(a), journeyFacts(b)), null);
});
test("strength and dexterity amounts are not interchangeable", () => {
  const a = combat(), b = combat();
  b.interaction.content.context.player.statuses[0].amount = 7;
  b.interaction.content.context.player.statuses[1].amount = 2;
  assert.ok(firstDifference(journeyFacts(a), journeyFacts(b)).field.includes("statuses"));
});
test("enemy powers do not get merged into player powers", () => {
  const a = combat(), b = combat();
  b.interaction.content.context.enemies[0].statuses = [];
  b.interaction.content.context.player.statuses.push({ definition_id: "VULNERABLE_POWER", amount: 2 });
  assert.ok(firstDifference(journeyFacts(a), journeyFacts(b)));
});
test("current card cost, playability and intent multiplicity change the comparison", () => {
  for (const mutate of [
    (snap) => { snap.interaction.content.context.player.hand[0].cost = "0"; },
    (snap) => { snap.interaction.content.context.player.hand[0].can_play = false; },
    (snap) => { snap.interaction.content.context.enemies[0].intents[0].hits = 1; }
  ]) { const a = combat(), b = combat(); mutate(b); assert.ok(firstDifference(journeyFacts(a), journeyFacts(b))); }
});
test("missing amounts or partial menus stop before action selection", () => {
  const a = combat(); delete a.interaction.content.context.player.statuses[0].amount;
  assert.throws(() => journeyFacts(a), /Missing public/);
  const b = combat(); b.bound_actions.materialized_count = 1;
  assert.throws(() => journeyFacts(b), /complete public/);
});
test("a target binds through its current public referent, not an opaque ID guess", () => {
  const a = combat(); a.bound_actions.actions[0].arguments[0].referent_id = "old-ref";
  assert.throws(() => actionKey(a, a.bound_actions.actions[0]), /no current referent/);
});
test("skipped Proceed and missing legal actions are counted divergences", () => {
  assert.ok(firstDifference({ kind: "event_option", actions: ["Proceed"] }, { kind: "map_navigation", actions: [] }));
  const a = combat(), b = combat(); b.bound_actions.actions.pop();
  b.bound_actions.total_count = b.bound_actions.materialized_count = 1;
  assert.ok(firstDifference(journeyFacts(a), journeyFacts(b)));
});

test("shipped numeric intent labels match native typed damage and hit counts", () => {
  assert.deepEqual(intentAmounts({ type: "Attack", label: "5×2" }), { type: "Attack", damage: 5, hits: 2, total_damage: 10 });
  assert.deepEqual(intentAmounts({ type: "Attack", label: "12" }), { type: "Attack", damage: 12, hits: 1, total_damage: 12 });
  assert.throws(() => intentAmounts({ type: "Attack", label: "?" }), /Unqualified/);
});
test("only the exact public combat tutorial can be dismissed", () => {
  const snapshot = combat(); snapshot.interaction.kind = "tutorial";
  snapshot.interaction.content.context.kind = "combat";
  snapshot.interaction.content.surface = { tutorial_id: "combat_rules_ftue", total_pages: 3, current_page: 1,
    options: [{ semantic_id: "advance_tutorial", enabled: true }] };
  snapshot.bound_actions.actions = [{ bound_action_id: "next", interaction_id: "i", verb: "activate", subject_referent_id: null, arguments: [] }];
  snapshot.bound_actions.total_count = snapshot.bound_actions.materialized_count = 1;
  assert.equal(tutorialAction(snapshot).bound_action_id, "next");
  const before = tutorialGameFacts(snapshot); snapshot.interaction.content.context.player.energy = 2;
  assert.ok(firstDifference(before, tutorialGameFacts(snapshot)));
  snapshot.interaction.content.surface.tutorial_id = "unknown";
  assert.throws(() => tutorialAction(snapshot), /Unqualified/);
});
