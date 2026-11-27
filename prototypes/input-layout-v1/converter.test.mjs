import assert from "node:assert/strict";
import test from "node:test";
import { actionsPreserved, convert, digest, restore, INPUT_SCHEMA } from "./converter.mjs";

const ref = public_slot => ({ public_slot });
function fixture() {
  const card = (slot, cost = "1", upgraded = false) => ({ entity_id: ref(slot), owner_entity_id: ref(0),
    definition_id: "TEST_ATTACK", name: "Test attack", type: "Attack", cost,
    rarity: "Basic", is_upgraded: upgraded, description: "Public test description" });
  const first = card(2), second = card(3);
  const operand = item => ({ public_slot: item.entity_id.public_slot, role: "card", label: item.name,
    state: { enabled: true }, properties: structuredClone(item) });
  const enemy = slot => ({ public_slot: slot, role: "enemy", label: "Test enemy", state: {}, properties: { hp: 9 } });
  const candidates = [first, second].map(item => ({ verb: "play", label: "Play attack",
    subject: operand(item), arguments: [{ role: "target", name: "target", entity: enemy(8) }], history: {} }));
  for (const [verb, label] of [["skip", "Skip card"], ["leave", "Leave rest site"],
    ["rest", "Rest"], ["smith", "Smith"], ["use", "Use potion"], ["buy", "Buy item"]])
    candidates.push({ verb, label, subject: null, arguments: [], history: {} });
  return { schema_version: "actual-engine-public-entity-graph-v1", candidates,
    context: {
      persistent: { scope: "active_single_player_run", run: { act: 1, floor: 4, ascension: 8 },
        player: { entity_id: ref(0), character_definition_id: "IRONCLAD", character_name: "The Ironclad",
          hp: 41, max_hp: 80, gold: 99, max_potion_slots: 2,
          relics: [{ entity_id: ref(5), definition_id: "TEST_RELIC", counter: 2 }] } },
      interaction: { kind: "event_option", content: { context: { kind: "event" },
        surface: { kind: "event_option", options: [{ entity_id: ref(11), title: "Test option",
          is_enabled: true, is_locked: false, tooltips: [{ kind: "text", name: "Test", description: "Details" }] }] } } },
      referents: [operand(first), operand(second), enemy(8), enemy(9)],
      reads: [{ kind: "run_deck", content: { cards: [first, second] } },
        { kind: "combat_piles", content: { zones: [
          { kind: "draw", ordering_semantics: "unordered_multiset", cards: [card(4)] },
          { kind: "discard", cards: [] }, { kind: "exhaust", cards: [] }] } }],
    } };
}

test("proven singleton aliases and typed optional nulls share one layout, exactly reversible", () => {
  const official = fixture(), native = structuredClone(official);
  native.context.interaction.content.context.player = { character_id: "IRONCLAD", name: "The Ironclad",
    hp: 41, max_hp: 80, gold: 99, max_potion_slots: 2 };
  native.context.interaction.content.context.run = { act: 1, total_floor: 4, ascension: 8 };
  native.context.reads[0].content.cards[0].can_play = null;
  native.context.interaction.content.surface.options[0].tooltips[0].card = null;
  const saved = structuredClone(native), a = convert(official), b = convert(native);
  assert.deepEqual(a.canonical_input, b.canonical_input);
  assert.deepEqual(restore(a), official); assert.deepEqual(restore(b), native);
  assert.deepEqual(native, saved);
  assert.ok(b.rewrites.some(row => row.rule === "same_current_player_fact_v1"));
});

test("only same-owner facts collapse; foreign owners and conflicts remain visible", () => {
  const foreign = fixture(), conflicting = fixture();
  foreign.context.interaction.content.context.player = { entity_id: ref(99), hp: 41 };
  conflicting.context.interaction.content.context.player = { hp: 17 };
  for (const input of [foreign, conflicting]) {
    const result = convert(input);
    assert.equal(result.unresolved.length, 1);
    assert.equal(result.canonical_input.context.interaction.content.context.player.hp,
      input.context.interaction.content.context.player.hp);
    assert.deepEqual(restore(result), input);
  }
});

test("act-local floor is not confused with cumulative floor, even when numbers coincide", () => {
  const input = fixture();
  input.context.interaction.content.context.run = { floor: 4, total_floor: 4, act_index: 0 };
  const result = convert(input), run = result.canonical_input.context.interaction.content.context.run;
  assert.deepEqual(run, { floor: 4, act_index: 0 });
  assert.deepEqual(restore(result), input);
  input.context.persistent.run = { act: 2, floor: 21, ascension: 8 };
  input.context.interaction.content.context.run = { floor: 4, total_floor: 21, act_index: 1 };
  assert.deepEqual(convert(input).canonical_input.context.interaction.content.context.run, { floor: 4, act_index: 1 });
});

const changes = {
  "deck definition": input => { input.context.reads[0].content.cards[0].definition_id = "TEST_OTHER_ATTACK"; },
  "individual card cost": input => { input.context.reads[0].content.cards[0].cost = "0"; },
  "individual upgrade": input => { input.context.reads[0].content.cards[1].is_upgraded = true; },
  "same-definition copy identity": input => { input.context.reads[0].content.cards[1].entity_id = ref(40); },
  "relic identity": input => { input.context.persistent.player.relics[0].definition_id = "TEST_OTHER_RELIC"; },
  "owned relic counter": input => { input.context.persistent.player.relics[0].counter = 3; },
  "card owner": input => { input.context.reads[0].content.cards[0].owner_entity_id = ref(8); },
  "card zone": input => { input.context.reads[1].content.zones[2].cards.push(input.context.reads[1].content.zones[0].cards.pop()); },
  "target": input => { input.candidates[0].arguments[0].entity.public_slot = 9; },
  "optional skip choice": input => { input.candidates.splice(2, 1); },
  "declined-card memory": input => { input.candidates[0].history.card_reward_declined = true; },
  "unknown mechanic": input => { input.context.persistent.player.new_mechanic = { amount: 3 }; },
  "nested choice": input => { input.context.interaction.content.surface.pending_selection = { minimum: 1, maximum: 2 }; },
  "selection limit": input => { input.context.interaction.content.surface.maximum_selection = 2; },
  "unknown null versus absent": input => { input.context.persistent.player.new_mechanic = null; },
};
for (const [name, change] of Object.entries(changes)) test(`preserves a meaningful distinction: ${name}`, () => {
  const original = fixture(), altered = structuredClone(original); change(altered);
  const a = convert(original), b = convert(altered);
  assert.notEqual(a.canonical_digest, b.canonical_digest);
  assert.deepEqual(restore(b), altered);
});

test("named Strength and Dexterity amounts never detach from their status identity or owner", () => {
  const a = fixture(), b = fixture();
  a.context.persistent.player.statuses = [{ definition_id: "STRENGTH", amount: 2 }, { definition_id: "DEXTERITY", amount: 7 }];
  b.context.persistent.player.statuses = [{ definition_id: "STRENGTH", amount: 7 }, { definition_id: "DEXTERITY", amount: 2 }];
  assert.notEqual(convert(a).canonical_digest, convert(b).canonical_digest);
});

test("does not sort a hand, detach counters, deduplicate identical card copies or prune any choice", () => {
  const input = fixture(), result = convert(input);
  assert.equal(result.canonical_input.context.reads[0].content.cards.length, 2);
  assert.equal(actionsPreserved(result, input), true);
  assert.equal(result.canonical_input.candidates.length, 8);
  const changed = structuredClone(input); changed.context.reads[0].content.cards.reverse();
  assert.notEqual(convert(changed).canonical_digest, result.canonical_digest);
});

test("nullable playability stays unknown, and missing required booleans stay distinct", () => {
  const input = fixture(), playable = fixture(), selected = fixture();
  playable.context.reads[0].content.cards[0].can_play = false;
  selected.context.reads[0].content.cards[0].is_selected = false;
  const base = convert(input);
  assert.equal(base.canonical_input.context.reads[0].content.cards[0].can_play, null);
  assert.equal(Object.hasOwn(base.canonical_input.context.reads[0].content.cards[0], "is_selected"), false);
  assert.notEqual(base.canonical_digest, convert(playable).canonical_digest);
  assert.notEqual(base.canonical_digest, convert(selected).canonical_digest);
  delete selected.context.interaction.content.surface.options[0].is_enabled;
  assert.equal(Object.hasOwn(convert(selected).canonical_input.context.interaction.content.surface.options[0], "is_enabled"), false);
});

test("unfamiliar card-shaped objects do not inherit a guessed record schema", () => {
  const input = fixture();
  input.context.future_mechanic = structuredClone(input.context.reads[0].content.cards[0]);
  input.context.future_mechanic.tooltips = [{ kind: "text", name: "Unknown", description: "Unknown" }];
  const result = convert(input);
  assert.deepEqual(result.canonical_input.context.future_mechanic, input.context.future_mechanic);
  const changed = structuredClone(input); changed.context.future_mechanic.can_play = null;
  assert.notEqual(result.canonical_digest, convert(changed).canonical_digest);
});

test("private fields and malformed JSON cannot enter the prototype", () => {
  for (const bad of [input => { input.context.hidden = { rng: 42 }; },
    input => { input.context.persistent.player.hp = NaN; },
    input => { input.context.persistent.player.hp = undefined; }]) {
    const input = fixture(); bad(input); assert.throws(() => convert(input));
  }
});

test("tampering with canonical facts or rewrite evidence is detected", () => {
  const result = convert(fixture()), a = structuredClone(result), b = structuredClone(result);
  a.canonical_input.context.persistent.player.hp++;
  assert.throws(() => restore(a), /Changed canonical/);
  b.rewrites.find(row => row.operation === "add_typed_null").path = "/context/persistent/player/hp";
  assert.throws(() => restore(b), /Changed typed-null/);
  assert.equal(digest(restore(result)), result.original_digest);
});

test("reconstruction evidence cannot address JavaScript prototypes", () => {
  const result = convert(fixture());
  result.rewrites.push({ operation: "remove_duplicate", path: "/__proto__/layout_polluted", before: true, target: null });
  assert.throws(() => restore(result), /Unsafe reconstruction/);
  assert.equal(Object.hasOwn(Object.prototype, "layout_polluted"), false);
});

test("consistent relabelling of local handles changes no represented public fact", () => {
  const input = fixture(), changed = structuredClone(input);
  function relabel(row) {
    if (!row || typeof row !== "object") return;
    if (Object.hasOwn(row, "public_slot")) row.public_slot = row.public_slot * 19 + 101;
    Object.values(row).forEach(relabel);
  }
  relabel(changed);
  assert.deepEqual(convert(input).canonical_input, convert(changed).canonical_input);
  assert.deepEqual(restore(convert(changed)), changed);
});

test("relabel preserves distinct action operands, embedded entities and unknown numeric fields", () => {
  const input = fixture();
  input.candidates[0].subject.properties.entity_id = ref(77);
  input.context.extra_mechanic = { public_slot: 349, counter: 12 };
  const result = convert(input);
  assert.notEqual(result.canonical_input.candidates[0].subject.public_slot,
    result.canonical_input.candidates[0].subject.properties.entity_id.public_slot);
  assert.deepEqual(result.canonical_input.context.extra_mechanic, input.context.extra_mechanic);
  assert.deepEqual(restore(result), input);
});

test("unresolved owner pointers are rejected instead of manufacturing an entity", () => {
  const input = fixture(); input.context.reads[0].content.cards[0].owner_entity_id = ref(999);
  assert.throws(() => convert(input), /Unresolved local public entity slot/);
});

test("canonical layout is idempotent without reordering or removing repeated choices", () => {
  const input = fixture();
  input.candidates.push(structuredClone(input.candidates[3]));
  const first = convert(input), second = convert(first.canonical_input);
  assert.deepEqual(second.canonical_input, first.canonical_input);
  assert.equal(second.rewrites.length, 0);
  assert.equal(second.canonical_input.candidates.length, input.candidates.length);
});

test("prototype input is explicitly versioned apart from the production input schema", () => {
  const input = fixture(), result = convert(input);
  assert.equal(result.canonical_input.schema_version, INPUT_SCHEMA);
  assert.notEqual(result.canonical_input.schema_version, input.schema_version);
  assert.equal(result.production_ready, false); assert.equal(result.training_allowed, false);
  assert.deepEqual(restore(result), input);
});

test("new public entities in unfamiliar layouts keep their facts and ownership", () => {
  const input = fixture();
  input.context.future_mechanic = { entity_id: ref(777), owner_entity_id: ref(0),
    definition_id: "TEST_NEW_MECHANIC", amount: 7, optional_value: null };
  const result = convert(input);
  assert.equal(result.canonical_input.context.future_mechanic.amount, 7);
  assert.equal(result.canonical_input.context.future_mechanic.owner_entity_id.public_slot,
    result.canonical_input.context.persistent.player.entity_id.public_slot);
  assert.equal(actionsPreserved(result, input), true);
  assert.deepEqual(restore(result), input);
});
