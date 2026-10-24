import test from "node:test";
import assert from "node:assert/strict";
import { fixture, caseBank } from "./engine-interface-case-bank-v1.mjs";
import { sharedDecision, deliveredAction, recordInterfaceNavigation } from "./engine-shared-input-v3.mjs";
import { newDiagnosticNavigation } from "./engine-run-policy-v7.mjs";
import { collectCurrentFrame } from "./engine-checkpoint-observation-v1.mjs";
import { mutationChecks } from "./engine-interface-mutations-v1.mjs";

for (const row of caseBank()) test(`source-family envelope: ${row.snapshot.interaction.kind}`, () => {
  const before = structuredClone(row), frame = sharedDecision(row.snapshot, row.reads);
  assert.equal(frame.actions.length, row.snapshot.bound_actions.actions.length);
  assert.deepEqual(row, before);
  assert.equal(frame.terminal, row.snapshot.interaction.kind === "game_over");
});
for (const result of mutationChecks()) test(`generated mutation: ${result.key}`, () => {
  assert.equal(result.passed, true, JSON.stringify(result));
});

test("terminal public loss/win retains result controls but is never sent to the policy", () => {
  for (const result of ["loss", "win"]) {
    const x = fixture("game_over"); x.snapshot.interaction.content.context.result = result;
    const frame = sharedDecision(x.snapshot, x.reads);
    assert.equal(frame.ending.victory, result === "win");
    assert.equal(frame.public_input.candidates.length, 1);
    assert.equal(frame.terminal_actions_are_presentation, true);
    assert.throws(() => deliveredAction(frame, { binding_id: frame.binding_id, action_index: 0 }, x.snapshot), /Stale/);
  }
  const x = fixture("game_over"); delete x.snapshot.interaction.content.context.result;
  assert.throws(() => sharedDecision(x.snapshot, x.reads), /ending/);
});

test("selected card flags keep their current surface/read ownership instead of merging", () => {
  const x = fixture("deck_transform_selection");
  x.snapshot.interaction.content.surface.cards[0].is_selected = true;
  x.snapshot.interaction.content.surface.selected_count = 1;
  x.snapshot.interaction.content.surface.selected_card_entity_ids = [x.reads[0].content.cards[0].entity_id];
  const frame = sharedDecision(x.snapshot, x.reads);
  const views = frame.public_input.context.referents[0].properties.public_card_views;
  assert.ok(Object.entries(views).some(([scope, v]) => scope.startsWith("interaction:") && v.is_selected === true));
  assert.ok(Object.entries(views).some(([scope, v]) => scope.startsWith("read:run_deck:") && v.is_selected === false));
  assert.equal(frame.public_input.context.interaction.content.surface.selected_count, 1);
});

test("descriptions and legality are view-specific while physical card identity stays shared", () => {
  const x = fixture();
  x.snapshot.interaction.content.context.player.hand[0].description = "Hand-specific description";
  x.snapshot.interaction.content.context.player.hand[0].can_play = true;
  x.reads[0].content.cards[0].description = "Deck-specific description";
  x.reads[0].content.cards[0].can_play = null;
  const frame = sharedDecision(x.snapshot, x.reads);
  const views = Object.values(frame.public_input.context.referents[0].properties.public_card_views);
  assert.ok(views.some(v => v.description === "Hand-specific description" && v.can_play === true));
  assert.ok(views.some(v => v.description === "Deck-specific description" && v.can_play === null));
});

test("transport relabelling and menu/referent enumeration do not change complete policy input", () => {
  const a = fixture("combat_turn", "one"), b = fixture("combat_turn", "other");
  b.snapshot.bound_actions.actions.reverse(); b.snapshot.referents.reverse();
  assert.deepEqual(sharedDecision(a.snapshot, a.reads).public_input, sharedDecision(b.snapshot, b.reads).public_input);
});

test("nested card tooltips merge only identical owned structures and retain each public view", () => {
  const x = fixture("event_option");
  const option = x.snapshot.interaction.content.surface.options[0];
  option.tooltips = [{ kind: "card", name: "Synthetic preview", description: "Preview",
    card: structuredClone(x.reads[0].content.cards[0]) }];
  x.snapshot.referents.at(-1).properties = structuredClone(option);
  const frame = sharedDecision(x.snapshot, x.reads);
  assert.equal(frame.actions.length, 1);
  const changed = structuredClone(x); changed.snapshot.referents.at(-1).properties.tooltips[0].name = "Different preview";
  assert.throws(() => sharedDecision(changed.snapshot, changed.reads), /Conflicting/);
});

test("shop room/open inventory state is explicit, and delivered inspection is remembered", () => {
  const closed = fixture("shop_room"), open = fixture("shop_inventory"), navigation = newDiagnosticNavigation();
  const frame = sharedDecision(closed.snapshot, closed.reads, navigation);
  assert.equal(frame.public_input.context.interaction.kind, "shop_inventory");
  assert.equal(frame.public_input.context.interaction.content.surface.inventory_open, false);
  const index = frame.public_input.candidates.findIndex(a => a.label === "Open inventory");
  const action = deliveredAction(frame, { binding_id: frame.binding_id, action_index: index }, closed.snapshot);
  assert.equal(action.label, "Open shop inventory"); // Exact original UI binding is returned.
  recordInterfaceNavigation(navigation, closed.snapshot, action, { delivery: "delivered" });
  assert.deepEqual(navigation.inspected_shop_visits, ["[1,3]"]);
  const again = sharedDecision(closed.snapshot, closed.reads, navigation);
  assert.ok(again.public_input.candidates.every(c => c.history.shop_inspected));
  assert.equal(sharedDecision(open.snapshot, open.reads).public_input.context.interaction.content.surface.inventory_open, true);
});

test("uncertain or contradictory shop controls do not become a default Boolean", () => {
  for (const change of [x => { delete x.snapshot.interaction.content.surface.can_close; },
    x => { x.snapshot.interaction.content.surface.can_close = false; },
    x => { x.snapshot.interaction.content.surface.inventory_open = null; }]) {
    const x = fixture("shop_inventory"); change(x);
    assert.throws(() => sharedDecision(x.snapshot, x.reads));
  }
});

const stale = () => Object.assign(new Error('Player Environment request failed with HTTP 409: {"error":{"code":"stale_state"}}'), { statusCode: 409 });
test("an explicit stale read discards the whole partial bundle before any sampling", async () => {
  const a = fixture(), b = fixture("combat_turn", "fresh"), journal = [];
  b.snapshot.session = a.snapshot.session; b.reads[0].session = a.snapshot.session;
  let calls = 0;
  const result = await collectCurrentFrame(a.snapshot, {
    read: async () => { if (++calls === 1) throw stale(); return b.reads[0]; },
    refresh: async () => b.snapshot, journal: row => journal.push(row), deadline: Date.now() + 1000 });
  assert.equal(result.snapshot.snapshot_id, b.snapshot.snapshot_id);
  assert.deepEqual(result.reads, b.reads); assert.equal(result.refreshes, 1);
  assert.equal(journal[0].action_submitted, false); assert.equal(journal[0].policy_sampled, false);
});

test("persistent stale reads stop at the declared cap without action retry", async () => {
  let reads = 0, refreshes = 0;
  const x = fixture();
  await assert.rejects(collectCurrentFrame(x.snapshot, { read: async () => { reads++; throw stale(); },
    refresh: async () => ({ ...x.snapshot, snapshot_id: `new-${++refreshes}` }), deadline: Date.now() + 1000 }), /refresh limit/);
  assert.equal(reads, 4); assert.equal(refreshes, 3);
});

test("refresh replaces every read after a second read goes stale, preserving the discarded evidence", async () => {
  const a = fixture(), b = fixture("combat_turn", "fresh-bundle"), journal = [];
  for (const x of [a, b]) {
    const extra = structuredClone(x.reads[0]);
    extra.kind = "combat_piles"; extra.read_id += "-piles"; extra.content = { zones: [] };
    x.snapshot.reads.push({ read_id: extra.read_id, kind: extra.kind }); x.reads.push(extra);
  }
  b.snapshot.session = a.snapshot.session;
  for (const read of b.reads) read.session = a.snapshot.session;
  const result = await collectCurrentFrame(a.snapshot, {
    read: async (id, snapshot) => {
      if (snapshot === a.snapshot.snapshot_id && id === a.reads[1].read_id) throw stale();
      return (snapshot === a.snapshot.snapshot_id ? a : b).reads.find(row => row.read_id === id);
    }, refresh: async () => b.snapshot, journal: row => journal.push(row), deadline: Date.now() + 1000 });
  assert.equal(journal.length, 1); assert.equal(journal[0].reads.length, 1);
  assert.equal(journal[0].reads[0].observed_snapshot_id, a.snapshot.snapshot_id);
  assert.equal(result.reads.length, 2);
  assert.ok(result.reads.every(row => row.observed_snapshot_id === b.snapshot.snapshot_id));
});

test("wrong runtime, other 409s, transport failures and successful stale payloads are never refreshed", async () => {
  for (const fail of [async () => { throw Object.assign(new Error("other 409"), { statusCode: 409 }); },
    async () => { throw new Error("transport timeout"); },
    async () => { const x = fixture(); x.reads[0].observed_snapshot_id = "old"; return x.reads[0]; }]) {
    const x = fixture();
    await assert.rejects(collectCurrentFrame(x.snapshot, { read: fail,
      refresh: async () => assert.fail("Do not refresh unrelated/uncertain failures"), deadline: Date.now() + 1000 }));
  }
});

test("public costs, counters, status amounts, targets, optional choices and unknown fields stay meaningful", () => {
  const original = fixture(), first = sharedDecision(original.snapshot, original.reads);
  for (const change of [x => { x.reads[0].content.cards[0].cost = "0"; },
    x => { x.snapshot.persistent.content.player.relics[0].counter = 3; },
    x => { x.snapshot.interaction.content.context.player.statuses[0].amount = 7; },
    x => { x.snapshot.interaction.content.surface.unfamiliar_public_fact = { amount: 2 }; }]) {
    const x = fixture(); change(x);
    // An inconsistent shared intrinsic fact must reject rather than choose a winner.
    try { assert.notEqual(sharedDecision(x.snapshot, x.reads).input_digest, first.input_digest); }
    catch (error) { assert.match(error.message, /Conflicting/); }
  }
});
