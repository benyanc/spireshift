// Versioned public-view repairs. Old observations, actions and helpers are immutable.
import { assertPublicBoundary } from "./engine-run-contract-v1.mjs";
import { publicShopSlots } from "./engine-interface-contract-v1.mjs";
import { recordDiagnosticNavigation } from "./engine-run-policy-v7.mjs";

const plain = value => value !== null && typeof value === "object" && !Array.isArray(value);
const exactControl = (action, verb, label) => action.verb === verb && action.label === label
  && action.subject_referent_id == null && !(action.arguments ?? []).length;

export function shopScope(snapshot) {
  const current = structuredClone(snapshot), interaction = current.interaction, surface = interaction?.content?.surface;
  if (!["shop_room", "shop_inventory"].includes(interaction?.kind)) return current;
  if (interaction.content.context?.kind !== "shop" || surface?.kind !== interaction.kind)
    throw Error("Shop surface and current owner differ");
  if (Object.hasOwn(surface, "inventory_open")) {
    if (typeof surface.inventory_open !== "boolean") throw Error("Unknown explicit shop inventory state");
    return current; // Native projection already publishes the explicit state.
  }
  const actions = current.bound_actions.actions;
  if (interaction.kind === "shop_room") {
    if (typeof surface.can_open_inventory !== "boolean" || typeof surface.can_proceed !== "boolean")
      throw Error("Missing declared shop-room control flags");
    const opens = actions.filter(action => exactControl(action, "open", "Open shop inventory"));
    const leaves = actions.filter(action => exactControl(action, "activate", "Leave shop and open map"));
    if (opens.length !== Number(surface.can_open_inventory) || leaves.length !== Number(surface.can_proceed))
      throw Error("Shop-room flags do not match exact current controls");
    for (const action of opens) { action.verb = "activate"; action.label = "Open inventory"; }
    for (const action of leaves) { action.verb = "close"; action.label = "Leave shop"; }
    interaction.kind = surface.kind = "shop_inventory";
    surface.source_surface_kind = "shop_room";
    surface.inventory_open = false;
  } else {
    if (!["cards", "relics", "potions"].every(key => Array.isArray(surface[key]))
        || typeof surface.can_close !== "boolean") throw Error("Missing declared open-inventory fields");
    const closes = actions.filter(action => exactControl(action, "cancel", "Close shop inventory"));
    if (closes.length !== Number(surface.can_close)) throw Error("Inventory close flag disagrees with its control");
    surface.inventory_open = true; // Pinned ShopInventorySurface is the open native screen.
  }
  return current;
}

export function scopedCardSelections(snapshot, reads) {
  const fixed = publicShopSlots(snapshot, reads), current = shopScope(fixed.snapshot);
  const cardIds = new Set();
  function cards(value) {
    if (Array.isArray(value)) { value.forEach(cards); return; }
    if (!plain(value)) return;
    if (Object.hasOwn(value, "public_card_views")) throw Error("Source uses adapter-owned card-view namespace");
    if (typeof value.entity_id === "string" && typeof value.definition_id === "string"
        && typeof value.cost === "string" && typeof value.type === "string"
        && typeof value.is_upgraded === "boolean") cardIds.add(value.entity_id);
    Object.values(value).forEach(cards);
  }
  // Only declared current public card entities. Other selected flags stay intact.
  cards(current);
  for (const read of fixed.reads) if (["run_deck", "combat_piles", "surface_card", "shop_catalog"].includes(read.kind)) cards(read.content);
  const selection = current.interaction.content.surface;
  if (Array.isArray(selection.selected_card_entity_ids) && Array.isArray(selection.cards)) {
    const declared = [...selection.selected_card_entity_ids].sort();
    if (new Set(declared).size !== declared.length || declared.some(id => !selection.cards.some(card => card.entity_id === id)))
      throw Error("Selected cards have ambiguous or foreign current owners");
    if (Object.hasOwn(selection, "selected_count")
        && (!Number.isInteger(selection.selected_count) || selection.selected_count !== declared.length))
      throw Error("Selected count disagrees with exact current card membership");
    if (selection.cards.every(card => typeof card.is_selected === "boolean")) {
      const selected = selection.cards.filter(card => card.is_selected).map(card => card.entity_id).sort();
      if (JSON.stringify(selected) !== JSON.stringify(declared)) throw Error("Current selection flags disagree with selected cards");
    }
  }
  function move(value, source, at = "") {
    if (Array.isArray(value)) { value.forEach((item, i) => move(item, source, `${at}/${i}`)); return; }
    if (!plain(value)) return;
    if (cardIds.has(value.entity_id)) {
      const facts = {};
      // BuildCard takes a selected flag, display pile and optional legality query.
      // Those are facts about a view, not conflicting intrinsic card identity.
      for (const [key, type] of Object.entries({ is_selected: "boolean", description: "string",
        target_type: "string", can_play: "boolean", unplayable_reason: "string" })) {
        if (!Object.hasOwn(value, key)) continue;
        if (!(typeof value[key] === type || key !== "is_selected" && value[key] === null))
          throw Error(`Unknown card view field: ${key}`);
        facts[key] = value[key]; delete value[key];
      }
      if (Object.keys(facts).length) {
        if (Object.hasOwn(value, "public_card_views")) throw Error("Source uses adapter-owned card-view namespace");
        // The enclosing card ID owns the view. An unordered collection's index
        // and a runtime handle must not become a new semantic feature.
        const scope = `${source}:${at.replace(/\/\d+(?=\/|$)/gu, "/*")}`;
        value.public_card_views = { [scope]: facts };
      }
    }
    for (const [key, item] of Object.entries(value)) move(item, source, `${at}/${key}`);
  }
  move(current.persistent.content, "persistent");
  move(current.interaction.content, "interaction");
  for (const referent of current.referents) move(referent, `referent:${referent.role}`);
  for (const read of fixed.reads) move(read.content, `read:${read.kind}`);
  assertPublicBoundary({ snapshot: current, reads: fixed.reads });
  return { snapshot: current, reads: fixed.reads };
}

export function recordInterfaceNavigation(navigation, snapshot, action, receipt) {
  const canonical = shopScope(snapshot);
  const bound = canonical.bound_actions.actions.find(row => row.bound_action_id === action.bound_action_id);
  if (!bound) throw Error("Delivered action is absent from the current navigation owner");
  recordDiagnosticNavigation(navigation, canonical, bound, receipt);
}
