// Synthetic public controls only; no game assets or saved observations.
import { chooseShopAction, shopFacts, shopActionKey, shopPlans, shopRoomAction,
  removalUiAction, potionTutorialAction } from "./engine-shop-bridge-contract.mjs";
const action = (id, verb, subject = null, label = id, arguments_ = []) => ({
  bound_action_id: id, interaction_id: "interaction", verb, subject_referent_id: subject, label, arguments: arguments_ });
export function observation(kind = "shop_inventory", shipped = false, serial = "s", inventory, player, deck) {
  inventory ??= { cards: [{ entity_id: "offer", definition_id: "SYNTHETIC_CARD", cost: "1", is_upgraded: false,
    price: 50, is_stocked: true, can_purchase: true, on_sale: false }], relics: [],
    potions: [{ entity_id: "potion0", definition_id: "SYNTHETIC_POTION_A", price: 50, is_stocked: true, can_purchase: true },
      { entity_id: "potion1", definition_id: "SYNTHETIC_POTION_B", price: 50, is_stocked: true, can_purchase: true }],
    card_removal: { entity_id: "service", price: 100, is_stocked: true, can_purchase: true } };
  player ??= { character_definition_id: "IRONCLAD", hp: 70, max_hp: 80, gold: 1000, max_potion_slots: 2, relics: [], potions: [] };
  deck ??= [{ entity_id: "strike", definition_id: "STRIKE_IRONCLAD", cost: "1", is_upgraded: false }];
  const surface = {}, referents = [], actions = [];
  if (kind === "shop_inventory") {
    for (const group of ["cards", "relics", "potions"]) {
      surface[group] = inventory[group].map((row, index) => {
        const result = structuredClone(row);
        if (shipped) {
          result.stocked = result.is_stocked; delete result.is_stocked;
          if (group === "cards") { result.card = { definition_id: row.definition_id, cost: row.cost, is_upgraded: row.is_upgraded };
            delete result.definition_id; delete result.cost; delete result.is_upgraded; }
        }
        referents.push({ referent_id: result.entity_id, properties: result });
        if (result.can_purchase) actions.push(action(`buy-${group}-${index}`, "activate", result.entity_id));
        return result;
      });
    }
    surface.card_removal = structuredClone(inventory.card_removal);
    if (shipped) { surface.card_removal.stocked = surface.card_removal.is_stocked; delete surface.card_removal.is_stocked; }
    referents.push({ referent_id: "service", properties: surface.card_removal });
    if (surface.card_removal.can_purchase) actions.push(action("remove", shipped ? "open" : "activate", "service"));
    if (shipped) surface.can_close = true;
    actions.push(action("leave", shipped ? "cancel" : "close", null, shipped ? "Close shop inventory" : "Leave shop"));
  } else if (kind === "card_selection" || kind === "native_deck_card_selection") {
    Object.assign(surface, { cards: structuredClone(deck), min_select: 1, max_select: 1, cancelable: true,
      require_manual_confirmation: true, stage: "selecting", selected_count: 0, can_confirm: false, can_preview: false, can_cancel_selection: true });
    for (const row of deck) {
      referents.push({ referent_id: row.entity_id, properties: row });
      actions.push(action(`choose-${row.entity_id}`, shipped ? "select" : "confirm", shipped ? row.entity_id : null, row.entity_id,
        shipped ? [] : [{ role: "selected_card", referent_id: row.entity_id }]));
    }
    actions.push(action("cancel", "cancel"));
  } else if (kind === "shop_room") {
    Object.assign(surface, { can_open_inventory: true, can_proceed: true });
    actions.push(action("open", "open", null, "Open shop inventory"), action("proceed", "activate", null, "Leave shop and open map"));
  } else if (kind === "map_navigation") {
    const point = { col: 1, row: 1, point_type: "monster" }; surface.next_options = [point];
    referents.push({ referent_id: "point", properties: point }); actions.push(action("travel", "activate", "point"));
  }
  const snapshot = { snapshot_id: serial, status: "interactive", session: { runtime_instance_id: "runtime" },
    information_policy: { includes_hidden_information: false }, completeness: { status: "complete" },
    interaction: { interaction_id: "interaction", kind, content: { surface } }, referents,
    persistent: { content: { run: { act: 1, act_definition_id: "SYNTHETIC_ACT", floor: 1, ascension: 8 }, player: structuredClone(player) } },
    bound_actions: { actions, status: "complete", total_count: actions.length, materialized_count: actions.length } };
  const deckRead = { kind: "run_deck", completeness: { status: "complete" }, expected_snapshot_id: serial, observed_snapshot_id: serial,
    information_policy: { includes_hidden_information: false }, ordering_semantics: "unordered_multiset",
    content: { kind: "run_deck", cards: structuredClone(deck), card_count: deck.length } };
  return { snapshot, deckRead };
}
export function preview(source, selected, phase, serial) {
  const value = structuredClone(source), s = value.snapshot;
  s.snapshot_id = serial; value.deckRead.expected_snapshot_id = value.deckRead.observed_snapshot_id = serial;
  Object.assign(s.interaction.content.surface, { stage: phase, selected_count: 1,
    selected_card_entity_ids: [selected.subject_referent_id], can_preview: phase === "selecting", can_confirm: phase === "preview", can_cancel_preview: true });
  s.bound_actions.actions = phase === "selecting" ? [action("deselect", "deselect", selected.subject_referent_id),
    action("preview", "open", null, "Preview the selected cards"), action("cancel-selection", "cancel")]
    : [action("confirm", "confirm", null, "Confirm the selected cards"), action("cancel-preview", "cancel")];
  s.bound_actions.total_count = s.bound_actions.materialized_count = s.bound_actions.actions.length;
  return value;
}

export function potionPopup(after) {
  const value = structuredClone(after), s = value.snapshot;
  s.snapshot_id = "potion-popup";
  value.deckRead.expected_snapshot_id = value.deckRead.observed_snapshot_id = s.snapshot_id;
  s.interaction.kind = "tutorial";
  s.interaction.content = { context: { kind: "shop" }, surface: {
    tutorial_id: "obtain_potion_ftue", stage: "confirmation", title: "Potion", body: "Synthetic tutorial",
    options: [{ semantic_id: "dismiss_tutorial", enabled: true, label: "Continue" }] } };
  s.referents = [];
  s.bound_actions.actions = [action("dismiss-potion", "activate", null, "Continue")];
  s.bound_actions.total_count = s.bound_actions.materialized_count = 1;
  return value;
}

export function savedShopFixture(scenario, { restockedCardCost = "2" } = {}) {
  const ordinary = scenario === "ordinary-purchases-removal", operations = shopPlans[scenario];
  const initial = observation(), inventory = structuredClone(initial.snapshot.interaction.content.surface);
  const player = structuredClone(initial.snapshot.persistent.content.player);
  if (!ordinary) player.relics.push({ definition_id: "THE_COURIER" });
  let deck = structuredClone(initial.deckRead.content.cards), kind = "shop_inventory", cardNumber = 0;
  const plan = [], nativeSnapshots = [], observed = [];
  for (let i = 0; i <= operations.length; i++) {
    const native = observation(kind, false, `native-${i}`, inventory, player, deck);
    const shippedKind = kind === "card_selection" ? "native_deck_card_selection" : kind;
    const shipped = observation(shippedKind, true, `shipped-${i}`, inventory, player, deck);
    const chosen = i === operations.length ? null : chooseShopAction(native.snapshot, operations[i]);
    plan.push({ facts: shopFacts(native.snapshot, native.deckRead), action: chosen ? shopActionKey(native.snapshot, chosen) : null });
    nativeSnapshots.push(native);
    observed.push({ index: i, ...shipped, facts: shopFacts(shipped.snapshot, shipped.deckRead), matched: true });
    const op = operations[i];
    if (op === "card") {
      const item = inventory.cards[0]; player.gold -= item.price;
      deck.push({ entity_id: `bought-${cardNumber++}`, definition_id: item.definition_id, cost: item.cost, is_upgraded: item.is_upgraded });
      if (ordinary) item.is_stocked = item.can_purchase = false;
      else { item.definition_id = `SYNTHETIC_RESTOCK_${cardNumber}`; item.cost = restockedCardCost; }
    } else if (op?.startsWith("potion")) {
      const item = inventory.potions[op === "potion-second" ? 1 : 0]; player.gold -= item.price;
      player.potions.push({ definition_id: item.definition_id, slot: player.potions.length });
      if (ordinary) item.is_stocked = item.can_purchase = false;
      else item.definition_id = "SYNTHETIC_RESTOCK_POTION";
      if (player.potions.length === 2) inventory.potions.forEach((row) => { row.can_purchase = false; });
    } else if (op === "remove") kind = "card_selection";
    else if (op === "cancel") kind = "shop_inventory";
    else if (op === "confirm-strike") {
      player.gold -= inventory.card_removal.price;
      deck = deck.filter((row) => row.definition_id !== "STRIKE_IRONCLAD");
      inventory.card_removal.is_stocked = inventory.card_removal.can_purchase = false;
      kind = "shop_inventory";
    } else if (op === "close") kind = "map_navigation";
  }
  const first = observed[0], entry = observation("shop_room", true, "entry", undefined,
    first.snapshot.persistent.content.player, first.deckRead.content.cards);
  const open = shopRoomAction(entry.snapshot, "open"), ui = [{ kind: "open_inventory",
    before: entry.snapshot, beforeDeck: entry.deckRead, after: first.snapshot, afterDeck: first.deckRead,
    action: open, public_game_facts_unchanged: true }];
  const receipts = [], tutorials = [];
  const receipt = (command) => receipts.push({ request_id: `request-${receipts.length}`, delivery: "delivered",
    attribution: { runtime_instance_id: "runtime" }, action: structuredClone(command) });
  receipt(action("continue", "activate")); receipt(open);
  for (let i = 0; i < operations.length; i++) {
    const before = observed[i], next = observed[i + 1], chosen = chooseShopAction(before.snapshot, operations[i]);
    receipt(chosen);
    if (i === (ordinary ? 1 : 2)) {
      const popup = potionPopup(next), dismiss = potionTutorialAction(popup.snapshot); receipt(dismiss);
      tutorials.push({ index: i, before: popup.snapshot, beforeDeck: popup.deckRead, after: next.snapshot,
        afterDeck: next.deckRead, action: dismiss, public_game_facts_unchanged: true });
    }
    if (chosen.verb === "select") {
      const confirmation = preview(before, chosen, "preview", "preview");
      for (const [j, current] of [confirmation].entries()) {
        const phase = "preview";
        const command = removalUiAction(before.snapshot, before.deckRead, current.snapshot, current.deckRead, chosen, phase);
        receipt(command); ui.push({ kind: `removal_${phase}`, index: i, before: before.snapshot, beforeDeck: before.deckRead,
          current: current.snapshot, currentDeck: current.deckRead, after: next.snapshot,
          selected_action: chosen, action: command, public_game_facts_unchanged_before_commit: true });
      }
    } else if (operations[i] === "close") {
      const current = observation("shop_room", true, "exit", undefined, before.snapshot.persistent.content.player, before.deckRead.content.cards);
      const command = shopRoomAction(current.snapshot, "proceed"); receipt(command);
      ui.push({ kind: "proceed_to_map", index: i, before: before.snapshot, beforeDeck: before.deckRead,
        current: current.snapshot, currentDeck: current.deckRead, after: next.snapshot, action: command,
        public_game_facts_unchanged_before_commit: true });
    }
  }
  return { scenario, plan, nativeSnapshots, shipped: { comparisons: observed, shop_ui_steps: ui, potion_tutorial_steps: tutorials,
    starting_snapshot: first.snapshot, latest_snapshot: observed.at(-1).snapshot, receipts,
    public_actions_requested: operations.length + 4, semantic_actions_delivered: operations.length,
    menu_actions_requested: 1, tutorial_actions_requested: 1, privileged_fixture: true, training_allowed: false } };
}
