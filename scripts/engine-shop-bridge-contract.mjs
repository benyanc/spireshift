// Finite public shop semantics. Private fixture setup is never a player/model input.
import { completePublicMenu } from "./engine-menu-probe.mjs";
import { restPersistentFacts } from "./engine-rest-bridge-contract.mjs";
import { actionKey as mapAction, journeyFacts, firstDifference } from "./engine-journey-contract-v2.mjs";
export { firstDifference };
const sorted = (rows) => rows.sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b), "en"));
const fields = (row, names) => Object.fromEntries(names.map((name) => {
  if (row?.[name] == null) throw new Error(`Missing public shop field: ${name}`);
  return [name, row[name]];
}));
const card = (row) => fields(row, ["definition_id", "cost", "is_upgraded"]);
const stock = (row) => {
  const values = [row?.is_stocked, row?.stocked].filter((value) => value !== undefined);
  if (!values.length || values.some((value) => typeof value !== "boolean" || value !== values[0]))
    throw new Error("Missing or conflicting current shop stock status");
  if (!Number.isSafeInteger(row.price) || row.price < 0 || typeof row.can_purchase !== "boolean"
      || (row.can_purchase && !values[0])) throw new Error("Invalid current shop price/availability");
  return { price: row.price, is_stocked: values[0], can_purchase: row.can_purchase };
};
const groups = ["cards", "relics", "potions"];
const selectionKinds = new Set(["card_selection", "native_deck_card_selection"]);
export function shopPersistentFacts(snapshot, deckRead) {
  const result = restPersistentFacts(snapshot, deckRead);
  const potions = snapshot.persistent.content.player.potions;
  if (!Array.isArray(potions) || potions.some((row) => !Number.isSafeInteger(row.slot) || row.slot < 0)
      || new Set(potions.map((row) => row.slot)).size !== potions.length
      || potions.some((row) => row.slot >= result.player.max_potion_slots))
    throw new Error("Invalid current public potion slots");
  result.player.potions = sorted(potions.map((row) => fields(row, ["definition_id", "slot"])));
  return result;
}
export function shopOffer(row, group, index) {
  const status = stock(row), result = { group, index, ...status };
  if (group === "cards") {
    if (typeof row.on_sale !== "boolean") throw new Error("Missing current shop sale status");
    result.on_sale = row.on_sale;
  }
  // Some UIs retain the sold item's display model; it is not a currently stocked item.
  // Identity is compared only for live stock; removal, prices and availability still compare.
  result.item = !status.is_stocked ? null : group === "cards" ? card(row.card ?? row)
    : fields(group === "relics" ? row.relic ?? row : row, ["definition_id"]);
  return result;
}
function selectionCards(snapshot) {
  const surface = snapshot.interaction.content.surface;
  if (!selectionKinds.has(snapshot.interaction.kind) || !Array.isArray(surface.cards)
      || !surface.cards.length || surface.min_select !== 1 || surface.max_select !== 1
      || surface.cancelable !== true) throw new Error("Expected the scoped cancelable single-removal picker");
  if (snapshot.interaction.kind === "native_deck_card_selection"
      && (surface.stage !== "selecting" || surface.selected_count !== 0 || surface.can_confirm !== false
        || surface.can_preview !== false || surface.can_cancel_selection !== true))
    throw new Error("Expected an unselected shipped removal picker");
  if (snapshot.interaction.kind === "card_selection" && surface.require_manual_confirmation !== true)
    throw new Error("Removal must retain native explicit confirmation");
  return sorted(surface.cards.map(card));
}
function currentReferent(snapshot, id) {
  const matches = snapshot.referents.filter((row) => row.referent_id === id);
  if (matches.length !== 1) throw new Error("Shop action lacks a unique current public operand");
  return matches[0];
}
export function shopActionKey(snapshot, action) {
  if (snapshot.interaction.kind === "map_navigation") return mapAction(snapshot, action);
  if (selectionKinds.has(snapshot.interaction.kind)) {
    const cards = selectionCards(snapshot);
    if (action.verb === "cancel" && action.subject_referent_id == null && action.arguments.length === 0)
      return { verb: "cancel", subject: null, arguments: [] };
    const id = action.verb === "select" && action.arguments.length === 0 ? action.subject_referent_id
      : action.verb === "confirm" && action.subject_referent_id == null
        && action.arguments.length === 1 && action.arguments[0].role === "selected_card" ? action.arguments[0].referent_id : null;
    const referent = currentReferent(snapshot, id);
    if (id == null || !snapshot.interaction.content.surface.cards.some((row) => row.entity_id === id
        && !firstDifference(card(referent.properties), card(row))) || !cards.length)
      throw new Error("Removal choice lacks a current visible card");
    return { verb: "confirm", subject: null, arguments: [{ role: "selected_card", target: card(referent.properties) }] };
  }
  if (snapshot.interaction.kind !== "shop_inventory" || action.arguments.length !== 0)
    throw new Error("Unqualified shop action family/operands");
  const surface = snapshot.interaction.content.surface;
  if ((action.verb === "close" || (action.verb === "cancel" && action.label === "Close shop inventory"))
      && action.subject_referent_id == null
      && (surface.can_close === undefined || surface.can_close === true))
    return { verb: "close", subject: null, arguments: [] };
  const referent = currentReferent(snapshot, action.subject_referent_id);
  if (!referent) throw new Error("Shop action lacks a current public operand");
  for (const group of groups) {
    const index = surface[group].findIndex((row) => row.entity_id === referent.referent_id);
    if (index >= 0 && action.verb === "activate") {
      const offer = shopOffer(surface[group][index], group, index);
      if (!offer.can_purchase) throw new Error("Unpurchasable shop offer advertised as an action");
      return { verb: "activate", subject: offer, arguments: [] };
    }
  }
  const service = surface.card_removal;
  if (["open", "activate"].includes(action.verb) && service?.entity_id === referent.referent_id
      && stock(service).can_purchase) return { verb: "activate", subject: { service: "card_removal", ...stock(service) }, arguments: [] };
  throw new Error("Unqualified shop control");
}
export function shopFacts(snapshot, deckRead) {
  const surface = snapshot.interaction.content.surface;
  const result = { kind: selectionKinds.has(snapshot.interaction.kind) ? "single_card_removal_selection" : snapshot.interaction.kind,
    ...shopPersistentFacts(snapshot, deckRead),
    actions: sorted(snapshot.bound_actions.actions.map((action) => shopActionKey(snapshot, action))) };
  if (snapshot.interaction.kind === "shop_inventory") {
    if (groups.some((group) => !Array.isArray(surface[group])) || !surface.card_removal)
      throw new Error("Incomplete public shop inventory");
    result.inventory = Object.fromEntries(groups.map((group) => [group,
      surface[group].map((row, index) => shopOffer(row, group, index))]));
    result.inventory.card_removal = stock(surface.card_removal);
  } else if (selectionKinds.has(snapshot.interaction.kind)) {
    result.selection = { min_select: 1, max_select: 1, cancelable: true, cards: selectionCards(snapshot) };
  } else if (snapshot.interaction.kind === "map_navigation") result.next_options = journeyFacts(snapshot).next_options;
  else throw new Error("Unqualified shop observation family");
  return result;
}
export const shopPlans = {
  "ordinary-purchases-removal": ["card", "potion-first", "potion-second", "remove", "cancel", "remove", "confirm-strike", "close"],
  "courier-restock-removal": ["card", "card", "potion-first", "potion-first", "remove", "cancel", "remove", "confirm-strike", "close"],
};
export function chooseShopAction(snapshot, operation) {
  const matches = snapshot.bound_actions.actions.filter((action) => {
    const key = shopActionKey(snapshot, action);
    if (["cancel", "close"].includes(operation)) return key.verb === operation;
    if (operation === "confirm-strike") return key.verb === "confirm"
      && key.arguments[0]?.target.definition_id === "STRIKE_IRONCLAD";
    if (operation === "remove") return key.subject?.service === "card_removal";
    return key.verb === "activate" && key.subject?.group === (operation === "card" ? "cards" : "potions")
      && key.subject.index === (operation === "potion-second" ? 1 : 0);
  });
  if (matches.length !== 1) throw new Error(`No unique current shop control for ${operation}`);
  return matches[0];
}
export function shopRoomAction(snapshot, operation) {
  const surface = snapshot.interaction.content.surface;
  if (!completePublicMenu(snapshot, snapshot.session?.runtime_instance_id)
      || snapshot.interaction.kind !== "shop_room" || surface.can_open_inventory !== true || surface.can_proceed !== true)
    throw new Error("Expected the complete live shop-room entry/exit menu");
  const labels = { open: "Open shop inventory", proceed: "Leave shop and open map" };
  const actions = snapshot.bound_actions.actions;
  if (actions.length !== 2 || actions.some((row) => row.subject_referent_id != null || row.arguments.length)
      || !Object.values(labels).every((label) => actions.filter((row) => row.label === label).length === 1)
      || !Object.hasOwn(labels, operation))
    throw new Error("Unqualified shop-room menu");
  return actions.find((row) => row.label === labels[operation]);
}
export function removalUiAction(before, beforeDeck, current, currentDeck, selectedAction, phase) {
  const surface = current.interaction.content.surface;
  const chosen = before.referents.find((row) => row.referent_id === selectedAction.subject_referent_id);
  if (!chosen || current.interaction.kind !== "native_deck_card_selection" || surface.stage !== phase
      || surface.selected_count !== 1 || surface.selected_card_entity_ids?.length !== 1
      || surface.selected_card_entity_ids[0] !== chosen.referent_id || surface.min_select !== 1 || surface.max_select !== 1
      || surface.cancelable !== true || !Array.isArray(surface.cards)
      || firstDifference(selectionCards(before), sorted(surface.cards.map(card)))
      || !surface.cards.some((row) => row.entity_id === chosen.referent_id && !firstDifference(card(row), card(chosen.properties)))
      || firstDifference(shopPersistentFacts(before, beforeDeck), shopPersistentFacts(current, currentDeck)))
    throw new Error("Removal preview must preserve the selected card and uncommitted gold/deck/potions");
  const actions = current.bound_actions.actions;
  const label = phase === "selecting" ? "Preview the selected cards" : "Confirm the selected cards";
  const matches = actions.filter((row) => row.label === label && row.subject_referent_id == null && row.arguments.length === 0);
  if (matches.length !== 1 || (phase === "selecting" ? surface.can_preview !== true
      || surface.can_confirm !== false || surface.can_cancel_selection !== true || actions.length !== 3
      || !actions.some((row) => row.verb === "deselect" && row.subject_referent_id === chosen.referent_id)
    : surface.can_confirm !== true || surface.can_cancel_preview !== true || actions.length !== 2)
      || !actions.some((row) => row.verb === "cancel" && row.subject_referent_id == null && row.arguments.length === 0))
    throw new Error("Incomplete current removal preview/back/confirm menu");
  return matches[0];
}
export function verifyShopEffects(scenario, plan) {
  const ops = shopPlans[scenario];
  if (!ops || plan.length !== ops.length + 1) throw new Error("Incomplete scoped shop sequence");
  const initial = plan[0].facts;
  if (initial.kind !== "shop_inventory" || initial.run.ascension !== 8 || initial.run.floor !== 1
      || initial.player.gold !== 1000 || initial.player.deck.length !== 1 || initial.player.deck[0].definition_id !== "STRIKE_IRONCLAD"
      || initial.player.potions.length !== 0 || initial.player.max_potion_slots !== 2
      || initial.player.relics.some((row) => row.definition_id === "THE_COURIER") !== (scenario === "courier-restock-removal"))
    throw new Error("Unexpected privileged shop fixture setup");
  for (let i = 0; i < ops.length; i++) {
    const before = plan[i].facts, after = plan[i + 1].facts, op = ops[i];
    if (op === "remove" || op === "cancel") {
      if (firstDifference({ run: before.run, player: before.player }, { run: after.run, player: after.player }))
        throw new Error("Opening/cancelling removal changed uncommitted game facts");
      if (op === "cancel" && firstDifference(after, plan[i - 1].facts))
        throw new Error("Removal cancellation did not restore the original inventory/menu");
    } else if (op === "close") {
      if (after.kind !== "map_navigation" || firstDifference(before.player, after.player))
        throw new Error("Shop exit changed player facts or did not open the map");
    } else {
      const quote = op === "confirm-strike" ? plan[i - 1].facts.inventory.card_removal.price : plan[i].action.subject.price;
      if (after.kind !== "shop_inventory" || after.player.gold !== before.player.gold - quote)
        throw new Error("Shop effect did not charge the current quote exactly once");
      if (op === "card") {
        const bought = plan[i].action.subject.item;
        // Rebuild the public fields before sorting: saved JSON may reorder object keys.
        if (firstDifference(sorted([...before.player.deck, bought].map(card)), sorted(after.player.deck.map(card))))
          throw new Error("Purchased card absent from public deck");
        if (after.inventory.cards[0].is_stocked !== (scenario === "courier-restock-removal")) throw new Error("Unexpected card restocking");
      } else if (op.startsWith("potion")) {
        if (after.player.potions.length !== before.player.potions.length + 1
            || !after.player.potions.some((row) => row.definition_id === plan[i].action.subject.item.definition_id
              && !before.player.potions.some((old) => old.slot === row.slot))) throw new Error("Purchased potion absent from a new visible slot");
        if (after.player.potions.length === 2 && after.inventory.potions.some((row) => row.can_purchase))
          throw new Error("Full potion inventory still offers purchases");
      } else if (op === "confirm-strike") {
        if (after.player.deck.some((row) => row.definition_id === "STRIKE_IRONCLAD")
            || after.player.deck.length !== before.player.deck.length - 1
            || after.inventory.card_removal.is_stocked || after.inventory.card_removal.can_purchase)
          throw new Error("Card removal did not commit once and consume its service");
      }
    }
  }
  return true;
}
export function prepareShopSave(original) {
  const value = structuredClone(original), map = value.acts?.[0]?.saved_map;
  if (value.ascension !== 8 || value.current_act_index !== 0 || !map?.start || map.start.coord.row !== 0
      || value.visited_map_coords?.length !== 1 || firstDifference(value.visited_map_coords[0], map.start.coord))
    throw new Error("Expected the frozen A8 initial-map fixture save");
  map.start.type = "shop";
  const start = map.points.find((row) => !firstDifference(row.coord, map.start.coord));
  if (start) start.type = "shop";
  value.pre_finished_room = null; value.map_point_history = [[]];
  return value;
}

export function potionTutorialAction(snapshot) {
  const surface = snapshot.interaction?.content?.surface;
  const actions = snapshot.bound_actions?.actions;
  if (!completePublicMenu(snapshot, snapshot.session?.runtime_instance_id)
      || snapshot.interaction.kind !== "tutorial" || snapshot.interaction.content.context?.kind !== "shop"
      || surface?.tutorial_id !== "obtain_potion_ftue" || surface.stage !== "confirmation"
      || surface.current_page != null || surface.total_pages != null
      || !surface.title?.trim() || !surface.body?.trim()
      || surface.options?.length !== 1 || surface.options[0].semantic_id !== "dismiss_tutorial"
      || surface.options[0].enabled !== true || actions?.length !== 1
      || actions[0].verb !== "activate" || actions[0].subject_referent_id != null
      || actions[0].arguments.length !== 0 || actions[0].label !== surface.options[0].label)
    throw new Error("Unqualified potion tutorial; no generic dismissal");
  return actions[0];
}

export function verifyPotionTutorialEffect(before, beforeDeck, after, afterDeck) {
  potionTutorialAction(before);
  if (after.interaction.kind !== "shop_inventory"
      || before.session.runtime_instance_id !== after.session.runtime_instance_id
      || before.snapshot_id === after.snapshot_id
      || firstDifference(shopPersistentFacts(before, beforeDeck), shopPersistentFacts(after, afterDeck)))
    throw new Error("Potion tutorial confirmation must leave public game facts unchanged");
  return true;
}
