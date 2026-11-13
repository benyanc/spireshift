import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { inspectFrame, publicShopSlots, unresolvedReferences } from "./engine-interface-contract-v1.mjs";
import { sharedDecision, deliveredAction } from "./engine-shared-input-v2.mjs";
const contract = JSON.parse(readFileSync(new URL("../configs/native-compatibility/sts2-v0.111.0-interface-contract-v1.json", import.meta.url)));
function fixture(prefix = "one") {
  const snapshot = { snapshot_id: `${prefix}-now`, session: { runtime_instance_id: `${prefix}-runtime` },
    information_policy: { includes_hidden_information: false }, completeness: { status: "complete" }, status: "interactive",
    persistent: { content: { run: { act: 1, floor: 4, ascension: 8 },
      player: { entity_id: `${prefix}-player`, character_definition_id: "IRONCLAD", hp: 38 } } },
    interaction: { kind: "shop_room", interaction_id: `${prefix}-owner`, content: {
      context: { kind: "shop" }, surface: { kind: "shop_room", can_open_inventory: true, can_proceed: true } } },
    referents: [], reads: [{ read_id: `${prefix}-catalog`, kind: "shop_catalog" }],
    bound_actions: { status: "complete", total_count: 2, materialized_count: 2, actions: [
      { bound_action_id: `${prefix}-open`, interaction_id: `${prefix}-owner`, verb: "open", label: "Open inventory", arguments: [] },
      { bound_action_id: `${prefix}-leave`, interaction_id: `${prefix}-owner`, verb: "activate", label: "Leave", arguments: [] }] } };
  const reads = [{ read_id: `${prefix}-catalog`, kind: "shop_catalog", session: snapshot.session,
    expected_snapshot_id: snapshot.snapshot_id, observed_snapshot_id: snapshot.snapshot_id,
    completeness: { status: "complete" }, information_policy: { includes_hidden_information: false },
    content: { cards: [{ entity_id: `${prefix}-offer`, slot_entity_id: `${prefix}-slot`, price: 45,
      card: { entity_id: `${prefix}-card`, definition_id: "STRIKE_IRONCLAD", cost: "0" } }],
      relics: [], potions: [], card_removal: null } }];
  return { snapshot, reads };
}
test("closed shop public slot links resolve without inventing action authority", () => {
  const x = fixture(), before = structuredClone(x);
  assert.equal(unresolvedReferences(x.snapshot, x.reads).length, 1);
  const fixed = publicShopSlots(x.snapshot, x.reads);
  assert.deepEqual(x, before); assert.deepEqual(unresolvedReferences(fixed.snapshot, fixed.reads), []);
  const f = sharedDecision(x.snapshot, x.reads);
  assert.equal(f.actions.length, 2); assert.equal(f.public_input.candidates.some(a => a.verb === "buy"), false);
  assert.equal(deliveredAction(f, { binding_id: f.binding_id, action_index: 0 }, x.snapshot).bound_action_id, f.actions[0].bound_action_id);
});
test("public slot identity is local while ownership, prices and costs remain meaningful", () => {
  const a = fixture("cli"), b = fixture("official");
  assert.deepEqual(sharedDecision(a.snapshot, a.reads).public_input, sharedDecision(b.snapshot, b.reads).public_input);
  for (const change of [x => x.reads[0].content.cards[0].price++, x => x.reads[0].content.cards[0].card.cost = "2"]) {
    const c = fixture("cli"); change(c);
    assert.notEqual(sharedDecision(a.snapshot, a.reads).input_digest, sharedDecision(c.snapshot, c.reads).input_digest);
  }
});
test("ambiguous offer-slot ownership, missing arrays and foreign read owners stop conversion", () => {
  for (const modify of [x => x.reads[0].content.cards.push(x.reads[0].content.cards[0]),
    x => delete x.reads[0].content.potions, x => x.snapshot.interaction.kind = "rest_site"]) {
    const x = fixture(); modify(x); assert.throws(() => sharedDecision(x.snapshot, x.reads));
  }
});
test("nullable removal service may be omitted; missing booleans are still unknown", () => {
  const x = fixture(); delete x.reads[0].content.card_removal;
  assert.doesNotThrow(() => sharedDecision(x.snapshot, x.reads));
  x.snapshot.interaction.kind = "event_option"; x.snapshot.interaction.content.surface.options = [{ index: 0, title: "Choice", description: "Choice", is_locked: false }];
  x.snapshot.reads = []; x.reads = [];
  const result = inspectFrame(x.snapshot, x.reads, contract);
  assert.ok(result.issues.some(i => i.path.endsWith('/is_enabled')));
  assert.ok(result.issues.some(i => i.path.endsWith('/will_kill_player')));
  assert.equal(result.issues.some(i => i.path.endsWith('/relic_name')), false);
});
test("audit accumulates every dangling reference and every missing option fact", () => {
  const x = fixture(); x.reads[0].content.relics = [{ entity_id: "other-offer", slot_entity_id: "other-slot" }];
  const r = inspectFrame(x.snapshot, x.reads, contract);
  assert.equal(r.issues.filter(i => i.code === "unresolved_reference").length, 2);
  assert.equal(r.slot_reference_repair_exercised, true);
  x.snapshot.interaction.kind = "event_option"; x.snapshot.interaction.content.surface.options = [{}, {}];
  x.snapshot.reads = []; x.reads = [];
  assert.equal(inspectFrame(x.snapshot, x.reads, contract).issues.filter(i => i.code === "missing_public_option_field").length,
    2 * contract.event_option_required_fields.length);
});
test("unknown pointers and hidden state are never repaired by declaring arbitrary IDs", () => {
  const x = fixture(); x.snapshot.persistent.content.player.target_entity_id = "missing-target";
  const r = inspectFrame(x.snapshot, x.reads, contract);
  assert.equal(r.converted, false); assert.ok(r.remaining_unresolved_references.length);
  x.snapshot.persistent.content.player.rng = 42;
  const hidden = inspectFrame(x.snapshot, x.reads, contract);
  assert.equal(hidden.converted, false); assert.equal(hidden.issues[0].code, "private_input");
});
test("surface-card reads remain complete and snapshot bound", () => {
  const x = fixture(); x.snapshot.reads[0].kind = x.reads[0].kind = "surface_card";
  x.snapshot.reads[0].target_referent_id = x.reads[0].target_referent_id = "visible-card";
  x.reads[0].content = { entity_id: "visible-card", definition_id: "STRIKE_IRONCLAD", cost: "0" };
  assert.equal(inspectFrame(x.snapshot, x.reads, contract).issues.length, 0);
  x.reads[0].observed_snapshot_id = "old";
  assert.ok(inspectFrame(x.snapshot, x.reads, contract).issues.some(i => i.code === "stale_read"));
  x.reads[0].content.entity_id = "different-card";
  assert.throws(() => sharedDecision(x.snapshot, x.reads), /different current card/);
});
test("option enablement is joined from the same public referent, including false", () => {
  const x = fixture(); x.snapshot.interaction.kind = "event_option";
  x.snapshot.reads = []; x.reads = [];
  x.snapshot.interaction.content.surface = { kind: "event_option", options: [{ entity_id: "choice", title: "Choice" }] };
  x.snapshot.referents = [{ referent_id: "choice", role: "option", label: "Choice",
    state: { visible: true, enabled: false }, properties: { entity_id: "choice", title: "Choice" } }];
  const fixed = publicShopSlots(x.snapshot, x.reads);
  assert.equal(fixed.snapshot.interaction.content.surface.options[0].is_enabled, false);
  assert.equal(fixed.snapshot.referents[0].properties.is_enabled, false);
  assert.equal(x.snapshot.interaction.content.surface.options[0].is_enabled, undefined);
  x.snapshot.interaction.content.surface.options[0].is_enabled = true;
  assert.throws(() => sharedDecision(x.snapshot, x.reads), /Conflicting/);
  delete x.snapshot.interaction.content.surface.options[0].is_enabled;
  delete x.snapshot.referents[0].state.enabled;
  assert.throws(() => sharedDecision(x.snapshot, x.reads), /no default flag/);
});
