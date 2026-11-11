import test from "node:test";
import assert from "node:assert/strict";
import { fixture } from "./engine-interface-case-bank-v1.mjs";
import { publicPolicyInput, stableJson } from "./engine-public-input-v1.mjs";
import { sharedDecision as previous } from "./engine-shared-input-v16.mjs";
import { sharedDecision, deliveredAction } from "./engine-shared-input-v17.mjs";
import { restoreLayout } from "./engine-input-layout-v13.mjs";
import { flowWorkerInput } from "./engine-a8-mixed-practice-worker-v2.mjs";
import { projectCardSelector } from "./engine-card-selector-surface-v1.mjs";
import { ATOMIC_SELECTION, PLAN, CardAnswerPlanner, answerControls, cardAnswerDomain,
  directAnswers, nativeAnswer, needsAnswerPlan } from "./engine-card-answer-v1.mjs";

const owners = ["shop", "combat", "rest", "event", "treasure"];
const preview = {definition_id: "SPIRAL", name: "Spiral", description: "Visible preview",
  amount: 1, observation_source: "native_command_enchantment_and_amount"};

function source(owner, n = 4, min = 0, max = 3, cancelable = true) {
  const cards = Array.from({length: n}, (_, index) => ({
    index, native_ref: "native-card-" + index, id: "STRIKE_IRONCLAD", name: "Strike", upgraded: false,
  }));
  return {type: "decision", decision: "card_select", cards, selection_ref: "pending-selector",
    selection_owner: {kind: owner}, context: {ascension: 8, act: 1, floor: 3},
    player: {native_ref: "native-player", potions: [], deck: cards}, prompt: "Choose cards",
    min_select: min, max_select: max, cancelable, require_manual_confirmation: true,
    unpowered_previews: false, pretend_cards_can_be_played: false, selection_preferences_complete: true,
    enchantment: preview};
}

function frameFor(state, prefix = null) {
  const {snapshot, reads} = fixture("card_selection"), raw = [], refs = [];
  const helpers = {visibleText: text => text, withoutDeck: () => ({gold: 99}),
    cardProperties: card => ({definition_id: card.id, name: card.name, type: "Attack",
      cost: "1", is_upgraded: card.upgraded, description: "Identical card copies"})};
  const ctx = {snapshotId: snapshot.snapshot_id, id: (...fields) => fields.join(":"),
    action: row => raw.push(row),
    referent(row) {
      const r = {...row, referent_id: row.id, properties: {...row.properties, entity_id: row.id}};
      refs.push({referent_id: row.id, role: row.role, label: row.label, properties: r.properties,
        state: {visible: true, enabled: row.enabled ?? true}});
      return r;
    }};
  const stateWithPlan = prefix === null ? state : {...state, answer_plan: {contract: PLAN, selected: prefix}};
  const view = projectCardSelector(stateWithPlan, ctx, helpers);
  assert.equal(view.complete, true);
  snapshot.interaction.content = {context: view.context, surface: view.surface};
  snapshot.referents = refs;
  const actions = raw.map((row, i) => ({bound_action_id: "action-" + i,
    interaction_id: snapshot.interaction.interaction_id, verb: row.verb, label: row.label,
    subject_referent_id: row.subject?.id ?? null, arguments: (row.arguments ?? []).map(arg => ({
      role: arg.role, referent_id: arg.referent.id,
    }))}));
  snapshot.bound_actions = {status: "complete", total_count: actions.length,
    materialized_count: actions.length, actions};
  reads[0].content.cards = structuredClone(view.surface.cards);
  reads[0].content.card_count = state.cards.length;
  if (state.selection_owner.kind === "shop") {
    snapshot.reads.push({read_id: "catalog", kind: "shop_catalog"});
    reads.push({...reads[0], read_id: "catalog", kind: "shop_catalog", content: {
      cards: [], relics: [{entity_id: "offer", slot_entity_id: "slot"}], potions: [], card_removal: null,
    }});
  }
  return {snapshot, reads, raw};
}

function convert({snapshot, reads}) {
  const worker = flowWorkerInput(snapshot, reads, null);
  const frame = sharedDecision(snapshot, reads);
  assert.equal(worker.candidates.length, snapshot.bound_actions.total_count);
  assert.equal(frame.actions.length, snapshot.bound_actions.total_count);
  for (const [action_index, action] of frame.actions.entries())
    assert.equal(deliveredAction(frame, {binding_id: frame.binding_id, action_index}, snapshot).bound_action_id,
      action.bound_action_id);
  return frame;
}

for (const owner of owners) {
  test(`systematic selector case covers ${owner} in both formats with the same facts and full answers`, () => {
    const state = source(owner), domain = cardAnswerDomain(state);
    const direct = frameFor(state), compact = frameFor(state, []);
    const small = convert(direct), large = convert(compact);
    const baseline = previous(direct.snapshot, direct.reads);
    assert.deepEqual(small.public_input, baseline.public_input);
    assert.deepEqual(small.actions, baseline.actions);
    const facts = frame => {
      const context = structuredClone(frame.public_input.context);
      delete context.interaction.content.surface.selection_contract;
      delete context.interaction.content.surface.answer_plan;
      return context;
    };
    assert.deepEqual(facts(small), facts(large));
    assert.equal(small.public_input.context.interaction.content.surface.selection_contract, ATOMIC_SELECTION);
    assert.equal(large.public_input.context.interaction.content.surface.selection_contract, PLAN);
    assert.deepEqual(restoreLayout(large.layout_evidence).schema_version, "actual-engine-public-entity-graph-v1");
    const completed = new Set();
    function walk(prefix) {
      for (const {raw} of frameFor(state, prefix).raw) {
        if (raw.action === "ordered_answer_append") walk([...prefix, raw.args.index]);
        else completed.add(stableJson(nativeAnswer(domain, prefix, raw.action === "ordered_answer_cancel")));
      }
    }
    walk([]);
    assert.deepEqual(completed, new Set(direct.raw.map(row => stableJson(row.raw))));
    for (const menu of [direct, compact])
      assert.equal(menu.snapshot.bound_actions.actions.some(a => a.label.startsWith("Buy ")), false);
  });
}

test("both formats anchor copies before unordered reads and normalize known preview labels", () => {
  const state = source("event", 6);
  for (const prefix of [null, []]) {
    const f = frameFor(state, prefix), a = convert(f);
    const b = structuredClone(f);
    b.reads[0].content.cards.reverse();
    b.snapshot.interaction.content.surface.enchantment.observation_source = "localized_visible_ui_text+model_identity";
    const converted = convert(b);
    assert.deepEqual(a.public_input, converted.public_input);
    assert.deepEqual(a.actions, converted.actions);
    const cards = converted.public_input.context.interaction.content.surface.cards;
    assert.equal(new Set(cards.map(c => c.entity_id.public_slot)).size, 6);
    b.snapshot.interaction.content.surface.enchantment.amount++;
    assert.notEqual(a.input_digest, convert(b).input_digest);
  }
});

test("stale, foreign and ambiguous shop reads fail in the worker and converter in both formats", () => {
  for (const prefix of [null, []]) {
    const initial = frameFor(source("shop"), prefix);
    for (const [edit, pattern] of [
      [f => { f.snapshot.interaction.content.context.kind = "rest"; }, /outside its declared current owner/],
      [f => { f.reads[1].observed_snapshot_id = "old"; }, /stale/],
      [f => { f.reads[1].content.relics.push({...f.reads[1].content.relics[0], entity_id: "different"}); }, /Ambiguous/],
    ]) {
      const f = structuredClone(initial);
      edit(f);
      assert.throws(() => flowWorkerInput(f.snapshot, f.reads, null), pattern);
      assert.throws(() => sharedDecision(f.snapshot, f.reads), pattern);
    }
  }
});

test("512 complete answers stay direct; larger menus keep legal prefixes and one ordered native commit", () => {
  for (const n of [511, 512, 513]) {
    const state = source("shop", n, 1, 1, false), domain = cardAnswerDomain(state);
    assert.equal(needsAnswerPlan(domain), n > 512);
    if (n <= 512) assert.equal(directAnswers(domain).length, n);
    else assert.throws(() => directAnswers(domain), /exceeds_bound/);
  }
  const state = source("combat", 13, 0, 3, false), domain = cardAnswerDomain(state);
  assert.equal(directAnswers(domain, 2000).length, 1886);
  const planner = new CardAnswerPlanner();
  assert.deepEqual(planner.observe(state).answer_plan.selected, []);
  const send = (verb, prefix, index, ref = state.selection_ref) => planner.handle({cmd: "action",
    action: "ordered_answer_" + verb, args: {selection_ref: ref, prefix, index}});
  assert.throws(() => send("append", "", 4, "foreign"), /Stale/);
  assert.throws(() => send("cancel", ""), /Unadvertised/);
  assert.equal(send("append", "", 12).local, true);
  assert.equal(send("append", "12", 1).local, true);
  assert.throws(() => send("append", "12,1", 12), /Invalid/);
  assert.throws(() => planner.observe({...state, prompt: "Changed"}), /changed/);
  const commit = send("commit", "12,1");
  assert.equal(commit.local, false);
  assert.deepEqual(commit.native, nativeAnswer(domain, [12, 1]));
  assert.throws(() => send("commit", "12,1"), /No pending/);
  assert.throws(() => answerControls(domain, [0, 0]), /Invalid/);
  assert.deepEqual(nativeAnswer(domain, []).args, {selection_ref: state.selection_ref, indices: ""});
});

test("public format validation rejects forged prefixes without changing unrelated actions", () => {
  const f = frameFor(source("shop"), []);
  delete f.snapshot.interaction.content.surface.answer_plan;
  assert.throws(() => sharedDecision(f.snapshot, f.reads), /Incomplete public ordered answer plan/);
  const normal = fixture("combat_turn");
  assert.deepEqual(sharedDecision(normal.snapshot, normal.reads).public_input,
    previous(normal.snapshot, normal.reads).public_input);
  assert.deepEqual(flowWorkerInput(normal.snapshot, normal.reads, null),
    publicPolicyInput(normal.snapshot, normal.reads, null));
});
