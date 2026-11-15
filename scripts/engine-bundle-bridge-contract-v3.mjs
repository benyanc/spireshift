// Compare visible pack identities/costs/upgrades and ownership; no hidden state.
import { restPersistentFacts } from "./engine-rest-bridge-contract.mjs";
import { firstDifference } from "./engine-journey-contract-v2.mjs";
export { firstDifference };
const canonical = (value) => Array.isArray(value) ? value.map(canonical)
  : value && typeof value === "object" ? Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonical(value[key])])) : value;
const sorted = (rows) => [...rows].sort((a, b) => JSON.stringify(canonical(a)).localeCompare(JSON.stringify(canonical(b)), "en"));
export function bundleCardFacts(card) {
  if (!card || typeof card.definition_id !== "string" || !card.definition_id
      || typeof card.cost !== "string" || !(card.cost === "X" || /^\d+$/u.test(card.cost))
      || typeof card.is_upgraded !== "boolean") throw Error("Incomplete public bundle card identity/cost/upgrade");
  return { definition_id: card.definition_id, cost: card.cost, is_upgraded: card.is_upgraded };
}
export const packFacts = (cards) => sorted(cards.map(bundleCardFacts));
export function bundleFacts(snapshot, deckRead) {
  const result = { kind: snapshot.interaction.kind, ...restPersistentFacts(snapshot, deckRead) };
  if (snapshot.interaction.kind === "card_bundle_selection") {
    const surface = snapshot.interaction.content.surface;
    if (surface.stage !== "choosing" || !Array.isArray(surface.bundles) || surface.bundles.length !== 2
        || surface.bundles.some((bundle) => bundle.cards?.length !== 3))
      throw Error("Expected exactly two complete current Scroll Boxes packs");
    result.packs = sorted(surface.bundles.map((bundle) => packFacts(bundle.cards)));
    result.actions = sorted(snapshot.bound_actions.actions.map((action) => bundleActionPack(snapshot, action)));
    if (firstDifference(result.packs, result.actions)) throw Error("Public pack menu is incomplete or ambiguous");
  } else if (snapshot.interaction.kind !== "event_option") throw Error("Unqualified bundle prefix state");
  return result;
}
export function bundleActionPack(snapshot, action) {
  if (snapshot.interaction.kind !== "card_bundle_selection" || action.verb !== "select"
      || action.arguments?.length !== 0 || !action.subject_referent_id)
    throw Error("Expected a current public pack selection");
  const subject = snapshot.referents.find((row) => row.referent_id === action.subject_referent_id);
  if (!["card_bundle", "bundle"].includes(subject?.role) || !Array.isArray(subject.properties?.cards))
    throw Error("Pack selection has no visible card-bundle operand");
  const matches = snapshot.interaction.content.surface.bundles.filter((row) =>
    row.entity_id === subject.properties.entity_id);
  if (matches.length !== 1 || firstDifference(packFacts(matches[0].cards), packFacts(subject.properties.cards)))
    throw Error("Pack operand does not match exactly one current visible bundle");
  return packFacts(subject.properties.cards);
}
export function choosePack(snapshot, expected) {
  const actions = snapshot.bound_actions.actions.filter((row) => firstDifference(bundleActionPack(snapshot, row), expected) == null);
  if (actions.length !== 1) throw Error("Requested pack does not bind uniquely in the current menu");
  return actions[0];
}
export function verifyBundlePreview(before, beforeDeck, preview, previewDeck, expected) {
  const surface = preview.interaction.content.surface;
  if (preview.interaction.kind !== "card_bundle_selection" || surface.stage !== "preview"
      || surface.bundles?.length !== 1 || typeof surface.selected_bundle_entity_id !== "string"
      || surface.bundles[0].entity_id !== surface.selected_bundle_entity_id
      || surface.can_confirm !== true || surface.can_cancel_preview !== true
      || firstDifference(packFacts(surface.bundles[0].cards), expected)
      || firstDifference(restPersistentFacts(before, beforeDeck), restPersistentFacts(preview, previewDeck)))
    throw Error("Bundle preview changed game facts or does not identify the chosen pack");
  const actions = preview.bound_actions.actions;
  const confirm = actions.filter((row) => row.verb === "confirm" && row.arguments?.length === 0);
  const cancel = actions.filter((row) => row.verb === "cancel" && row.arguments?.length === 0);
  if (confirm.length !== 1 || cancel.length !== 1 || actions.length !== 2)
    throw Error("Bundle preview must expose exactly one confirmation and cancellation");
  return { confirm: confirm[0], cancel: cancel[0] };
}
export function verifyBundleAward(before, after, chosen) {
  if (before.kind !== "card_bundle_selection" || after.kind !== "event_option"
      || firstDifference(before.run, after.run)) throw Error("Bundle award left its expected native event/floor");
  const old = { ...before.player }, next = { ...after.player };
  const oldDeck = old.deck, nextDeck = next.deck; delete old.deck; delete next.deck;
  if (firstDifference(old, next) || firstDifference(sorted([...oldDeck, ...chosen]), sorted(nextDeck)))
    throw Error("Bundle award differs from the chosen cards or changes other persistent facts");
  return true;
}
