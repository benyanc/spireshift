import test from "node:test";
import assert from "node:assert/strict";
import { sharedDecision, deliveredAction } from "./engine-shared-input-v1.mjs";

function fixture(prefix = "a") {
  const id = name => `${prefix}-${name}`;
  const card = { entity_id: id("card"), definition_id: "STRIKE_IRONCLAD", cost: "1",
    is_upgraded: false, description: "Deal 6 damage.", stats: { damage: 6 } };
  const snapshot = { snapshot_id: id("snapshot"), session: { runtime_instance_id: id("runtime") },
    information_policy: { includes_hidden_information: false }, completeness: { status: "complete" }, status: "interactive",
    persistent: { content: { run: { act: 1, floor: 3, ascension: 8 },
      player: { entity_id: id("player"), character_definition_id: "IRONCLAD", hp: 41,
        relics: [{ entity_id: id("relic"), definition_id: "PEN_NIB", counter: 2 }] } } },
    interaction: { interaction_id: id("interaction"), kind: "combat_turn", stage: "ready",
      content: { context: { kind: "combat", player: { hand: [card],
        statuses: [{ definition_id: "STRENGTH", amount: 2 }, { definition_id: "DEXTERITY", amount: 7 }] } },
        surface: { kind: "combat_turn", playable_cards: [card] } } },
    referents: [{ referent_id: id("card"), role: "playable_card", label: "Strike", properties: card, state: { visible: true } }],
    reads: [{ read_id: id("read"), kind: "run_deck", ordering_semantics: "unordered_multiset" }],
    bound_actions: { status: "complete", total_count: 2, materialized_count: 2, actions: [
      { bound_action_id: id("play"), interaction_id: id("interaction"), verb: "play", label: "Play Strike", subject_referent_id: id("card"), arguments: [] },
      { bound_action_id: id("end"), interaction_id: id("interaction"), verb: "end_turn", label: "End turn", arguments: [] }] } };
  const reads = [{ read_id: id("read"), kind: "run_deck", expected_snapshot_id: snapshot.snapshot_id,
    observed_snapshot_id: snapshot.snapshot_id, session: snapshot.session,
    completeness: { status: "complete" }, information_policy: { includes_hidden_information: false },
    content: { kind: "run_deck", card_count: 1, cards: [{ ...card, entity_id: id("deck-card") }] } }];
  return { snapshot, reads };
}

test("same public facts across hosts and menu permutations yield the same policy input", () => {
  const a = fixture("cli"), b = fixture("official");
  b.snapshot.bound_actions.actions.reverse(); b.snapshot.referents.reverse();
  const first = sharedDecision(a.snapshot, a.reads), second = sharedDecision(b.snapshot, b.reads);
  assert.deepEqual(first.public_input, second.public_input);
  assert.equal(first.input_digest, second.input_digest);
  assert.notEqual(first.binding_id, second.binding_id);
  assert.equal(first.actions.length, 2);
});

test("owned status amounts, card costs, relic counters and unfamiliar public facts survive", () => {
  const a = fixture(), before = structuredClone(a);
  const original = sharedDecision(a.snapshot, a.reads);
  assert.deepEqual(a, before);
  for (const modify of [
    x => { x.snapshot.interaction.content.context.player.statuses[0].amount = 7; x.snapshot.interaction.content.context.player.statuses[1].amount = 2; },
    x => { x.snapshot.interaction.content.context.player.hand[0].cost = "0"; },
    x => { x.snapshot.persistent.content.player.relics[0].counter = 9; },
    x => { x.snapshot.interaction.content.context.player.unfamiliar_visible_counter = 27; },
    x => { x.snapshot.interaction.content.context.player.hand[0].is_upgraded = true; },
  ]) {
    const changed = fixture(); modify(changed);
    assert.notEqual(sharedDecision(changed.snapshot, changed.reads).input_digest, original.input_digest);
  }
});

test("every advertised read is required, current, fair and in the same session", () => {
  for (const modify of [x => { x.reads = []; }, x => { x.reads.push(x.reads[0]); },
    x => { x.reads[0].observed_snapshot_id = "stale"; },
    x => { x.reads[0].session = { runtime_instance_id: "other" }; },
    x => { x.reads[0].completeness.status = "partial"; },
    x => { x.reads[0].information_policy.includes_hidden_information = true; }]) {
    const x = fixture(); modify(x);
    assert.throws(() => sharedDecision(x.snapshot, x.reads), /read/iu);
  }
});

test("skip, discard and leave controls are not filtered from any supported family", () => {
  for (const kind of ["card_reward_selection", "card_selection", "rest_site", "shop_inventory",
    "card_bundle_selection", "native_generated_card_choice", "treasure_relic_selection", "event_option"]) {
    const x = fixture(); x.snapshot.interaction.kind = kind;
    x.snapshot.bound_actions.actions.push({ bound_action_id: "optional", interaction_id: x.snapshot.interaction.interaction_id,
      verb: "skip", label: "Skip", arguments: [] });
    x.snapshot.bound_actions.total_count++; x.snapshot.bound_actions.materialized_count++;
    const frame = sharedDecision(x.snapshot, x.reads);
    assert.equal(frame.actions.length, 3);
    assert.equal(frame.public_input.candidates.filter(c => c.verb === "skip").length, 1);
  }
});

test("choice delivery uses exact current binding instead of a remembered temporary ID", () => {
  const x = fixture(), frame = sharedDecision(x.snapshot, x.reads);
  const choice = { binding_id: frame.binding_id, action_index: 0 };
  assert.equal(deliveredAction(frame, choice, x.snapshot).bound_action_id, frame.actions[0].bound_action_id);
  assert.throws(() => deliveredAction(frame, { ...choice, binding_id: "old" }, x.snapshot), /Stale/);
  assert.throws(() => deliveredAction(frame, { ...choice, action_index: 8 }, x.snapshot), /Stale/);
  const other = fixture("other");
  assert.throws(() => deliveredAction(frame, choice, other.snapshot), /Stale/);
  x.snapshot.bound_actions.actions[frame.actions[0].raw_index].bound_action_id = "changed";
  assert.throws(() => deliveredAction(frame, choice, x.snapshot), /ownership/);
});

test("unsupported families and hidden facts are reported instead of guessed", () => {
  const x = fixture(); x.snapshot.interaction.kind = "unqualified_new_menu";
  assert.throws(() => sharedDecision(x.snapshot, x.reads), /Unsupported/);
  x.snapshot.interaction.kind = "combat_turn"; x.snapshot.interaction.content.context.rng = 42;
  assert.throws(() => sharedDecision(x.snapshot, x.reads), /Private/);
});

test("a partial SDK card operand inherits its own public current-cost and preview facts", () => {
  const a = fixture("cli"), b = fixture("official");
  for (const x of [a, b]) {
    x.snapshot.interaction.content.context.player.hand[0].name = "Strike";
    x.snapshot.interaction.content.surface.playable_cards[0].name = "Strike";
  }
  b.snapshot.referents[0].properties = { entity_id: "official-card", name: "Strike" };
  assert.deepEqual(sharedDecision(a.snapshot, a.reads).public_input,
    sharedDecision(b.snapshot, b.reads).public_input);
  b.snapshot.referents[0].properties.cost = "8";
  assert.throws(() => sharedDecision(b.snapshot, b.reads), /Conflicting current public entity facts/);
});

test("targets keep exact ownership across different caption templates", () => {
  const a = fixture("cli"), b = fixture("official");
  for (const [prefix, x] of [["cli", a], ["official", b]]) {
    const enemy = { entity_id: `${prefix}-enemy`, definition_id: "TOADPOLE", hp: 11, block: 2 };
    x.snapshot.interaction.content.context.enemies = [enemy];
    x.snapshot.referents.push({ referent_id: enemy.entity_id, role: "enemy", label: "Toadpole", properties: enemy });
    const play = x.snapshot.bound_actions.actions[0];
    play.arguments = [{ role: "target", referent_id: enemy.entity_id }];
    play.label = prefix === "cli" ? "Play Strike on Toadpole" : "Play Strike -> Toadpole";
  }
  assert.deepEqual(sharedDecision(a.snapshot, a.reads).public_input,
    sharedDecision(b.snapshot, b.reads).public_input);
});

test("pinned official selection variants retain their complete scope and parent ownership", () => {
  for (const kind of ["native_deck_card_selection", "native_simple_card_selection",
    "native_combat_pile_selection", "combat_hand_card_selection", "deck_upgrade_selection",
    "deck_transform_selection", "deck_enchant_selection"]) {
    const x = fixture(); x.snapshot.interaction.kind = kind;
    const surface = x.snapshot.interaction.content.surface;
    surface.kind = kind; surface.min_select = 1; surface.max_select = 3;
    surface.selected_count = 0; surface.cancelable = false;
    const f = sharedDecision(x.snapshot, x.reads);
    assert.equal(f.source_family, kind);
    assert.equal(f.public_input.context.interaction.kind, "card_selection");
    assert.equal(f.public_input.context.interaction.content.context.kind, "selection");
    assert.equal(f.public_input.context.interaction.content.context.owner_kind, "combat");
    assert.equal(f.public_input.context.interaction.content.surface.max_select, 3);
    assert.equal(f.public_input.context.interaction.content.surface.cancelable, false);
    assert.equal(f.public_input.candidates.length, x.snapshot.bound_actions.actions.length);
  }
});
