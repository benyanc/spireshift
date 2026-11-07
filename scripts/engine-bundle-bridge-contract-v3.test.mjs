import assert from "node:assert/strict";
import test from "node:test";
import { verifyBundleAward, bundleActionPack, packFacts } from "./engine-bundle-bridge-contract-v3.mjs";

const card = (id, cost = "1") => ({ definition_id: id, cost, is_upgraded: false });
function award() {
  const selected = [card("A"), card("C")];
  const before = { kind: "card_bundle_selection", run: { act: 1, floor: 1, ascension: 8 },
    player: { hp: 80, gold: 99, deck: [card("B", "2"), card("D")] } };
  const after = { kind: "event_option", run: { ...before.run }, player: { ...before.player,
    deck: [...before.player.deck, ...selected].map((row) => ({ ...row }))
      .sort((a, b) => a.definition_id.localeCompare(b.definition_id)) } };
  return { before, after, selected };
}
test("JSON field order and source enumeration cannot change exact multiset award checking", () => {
  const { before, after, selected } = award();
  const reordered = selected.map(({ definition_id, cost, is_upgraded }) => ({ cost, is_upgraded, definition_id }));
  assert.equal(verifyBundleAward(before, after, reordered), true);
  assert.equal(verifyBundleAward(before, { ...after, player: { ...after.player, deck: [...after.player.deck].reverse() } }, reordered), true);
});
test("wrong card/cost/upgrade, omitted copies and unrelated persistent changes remain failures", () => {
  for (const change of [
    (after) => { after.player.deck[0].definition_id = "WRONG"; },
    (after) => { after.player.deck[0].cost = "3"; },
    (after) => { after.player.deck[0].is_upgraded = true; },
    (after) => { after.player.deck.pop(); },
    (after) => { after.player.gold--; }
  ]) {
    const { before, after, selected } = award(); change(after);
    assert.throws(() => verifyBundleAward(before, after, selected));
  }
});
test("native and observed shipped bundle roles bind the same visible pack without accepting stale referents", () => {
  for (const role of ["card_bundle", "bundle"]) {
    const cards = [card("A"), card("B")], properties = { entity_id: "PACK", cards };
    const snapshot = { interaction: { kind: "card_bundle_selection", content: { surface: { bundles: [properties] } } },
      referents: [{ referent_id: "CURRENT", role, properties }] };
    const action = { verb: "select", subject_referent_id: "CURRENT", arguments: [] };
    assert.deepEqual(bundleActionPack(snapshot, action), packFacts(cards));
    snapshot.referents[0].properties = { entity_id: "STALE", cards };
    assert.throws(() => bundleActionPack(snapshot, action));
  }
});
