// Scoped rest/upgrade semantics; all choices bind through the freshly offered public menu.
import { completePublicMenu } from "./engine-menu-probe.mjs";
import { actionKey as journeyAction, journeyFacts, firstDifference } from "./engine-journey-contract-v2.mjs";
export { firstDifference };
const sorted = (rows) => rows.sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b), "en"));
const fields = (row, keys) => Object.fromEntries(keys.map((key) => {
  if (row?.[key] == null) throw new Error(`Missing public rest field: ${key}`);
  return [key, row[key]];
}));
const card = (row) => fields(row, ["definition_id", "cost", "is_upgraded"]);
const booleanAlias = (row, nativeName, shippedName) => {
  const values = [row?.[nativeName], row?.[shippedName]].filter((value) => value !== undefined);
  if (!values.length || values.some((value) => typeof value !== "boolean") || values.some((value) => value !== values[0]))
    throw new Error(`Missing or conflicting public rest field: ${nativeName}/${shippedName}`);
  return values[0];
};

const upgradeKinds = new Set(["card_selection", "deck_upgrade_selection"]);
const singleUpgradeCard = (snapshot) => {
  const surface = snapshot.interaction.content.surface;
  if (!upgradeKinds.has(snapshot.interaction.kind) || surface.cards?.length !== 1
      || surface.min_select !== 1 || surface.max_select !== 1 || surface.cancelable !== true)
    throw new Error("Only the explicit single-card cancelable upgrade fixture is qualified");
  if (snapshot.interaction.kind === "deck_upgrade_selection"
      && (surface.stage !== "selecting" || surface.selected_count !== 0 || surface.can_confirm !== false))
    throw new Error("Expected an unselected shipped upgrade picker");
  return card(surface.cards[0]);
};

function upgradeActionKey(snapshot, action) {
  const candidate = singleUpgradeCard(snapshot);
  if (action.verb === "cancel" && action.subject_referent_id == null && action.arguments.length === 0)
    return { verb: "cancel", subject: null, arguments: [] };
  const id = action.verb === "select" && action.arguments.length === 0 ? action.subject_referent_id
    : action.verb === "confirm" && action.subject_referent_id == null
      && action.arguments.length === 1 && action.arguments[0].role === "selected_card" ? action.arguments[0].referent_id : null;
  if (id != null) {
    const current = snapshot.referents.find((row) => row.referent_id === id);
    if (!current || firstDifference(card(current.properties), candidate)) throw new Error("Upgrade choice has no current public card");
    return { verb: "confirm", subject: null, arguments: [{ role: "selected_card", target: candidate }] };
  }
  // This visible toggle changes presentation; it is recorded but outside the effect comparison.
  if (snapshot.interaction.kind === "deck_upgrade_selection" && action.verb === "activate"
      && action.subject_referent_id == null && action.arguments.length === 0
      && action.label === "Show upgraded card previews"
      && snapshot.interaction.content.surface.can_toggle_upgrade_view === true) return null;
  throw new Error("Unqualified upgrade picker control");
}

export function restActionKey(snapshot, action) {
  if (snapshot.interaction.kind === "map_navigation") return journeyAction(snapshot, action);
  if (upgradeKinds.has(snapshot.interaction.kind)) return upgradeActionKey(snapshot, action);
  let verb = action.verb;
  if (snapshot.interaction.kind === "rest_site" && action.subject_referent_id == null) {
    const surface = snapshot.interaction.content.surface;
    // The released Host labels its operand-free Proceed control as activate.
    // Normalize only that observed control, with current public permission to leave.
    if ((verb === "activate" && action.label === "Proceed to map") || verb === "close") {
      if (action.arguments.length !== 0 || !booleanAlias(surface, "can_leave", "can_proceed"))
        throw new Error("Proceed requires the current operand-free rest exit");
      verb = "close";
    } else throw new Error("Unqualified operand-free rest control");
  }
  const operand = (id) => {
    const row = snapshot.referents.find((item) => item.referent_id === id);
    if (!row) throw new Error("Rest action has no current public operand");
    if (snapshot.interaction.kind === "rest_site") return fields(row.properties, ["option_id"]);
    throw new Error("Unqualified rest action family");
  };
  return { verb, subject: action.subject_referent_id == null ? null : operand(action.subject_referent_id),
    arguments: sorted(action.arguments.map((arg) => ({ role: arg.role, target: operand(arg.referent_id) }))) };
}

export function restPersistentFacts(snapshot, deckRead) {
  if (!completePublicMenu(snapshot, snapshot.session?.runtime_instance_id)) throw new Error("Incomplete public rest decision");
  if (deckRead?.kind !== "run_deck" || deckRead.completeness?.status !== "complete"
      || deckRead.expected_snapshot_id !== snapshot.snapshot_id || deckRead.observed_snapshot_id !== snapshot.snapshot_id
      || deckRead.information_policy?.includes_hidden_information !== false
      || deckRead.ordering_semantics !== "unordered_multiset"
      || deckRead.content?.kind !== "run_deck" || !Array.isArray(deckRead.content.cards)
      || deckRead.content.card_count !== deckRead.content.cards.length)
    throw new Error("Complete public run-deck read is required");
  const persistent = snapshot.persistent.content;
  return {
    run: fields(persistent.run, ["act", "act_definition_id", "floor", "ascension"]),
    player: { ...fields(persistent.player, ["character_definition_id", "hp", "max_hp", "gold", "max_potion_slots"]),
      relics: sorted(persistent.player.relics.map((row) => fields(row, ["definition_id"]))),
      deck: sorted(deckRead.content.cards.map(card)) } };
}

export function restFacts(snapshot, deckRead) {
  const surface = snapshot.interaction.content.surface;
  const result = { kind: upgradeKinds.has(snapshot.interaction.kind) ? "single_card_upgrade_selection" : snapshot.interaction.kind,
    ...restPersistentFacts(snapshot, deckRead),
    actions: sorted(snapshot.bound_actions.actions.map((action) => restActionKey(snapshot, action)).filter((action) => action != null)) };
  if (snapshot.interaction.kind === "rest_site") {
    result.rest = { can_leave: booleanAlias(surface, "can_leave", "can_proceed"),
      options: surface.options.map((row) => ({ ...fields(row, ["index", "option_id"]),
        is_enabled: booleanAlias(row, "is_enabled", "enabled") })) };
  } else if (upgradeKinds.has(snapshot.interaction.kind)) {
    result.selection = { ...fields(surface, ["min_select", "max_select", "cancelable"]), cards: [singleUpgradeCard(snapshot)] };
  } else if (snapshot.interaction.kind === "map_navigation") result.next_options = journeyFacts(snapshot).next_options;
  else throw new Error("Unqualified rest observation family");
  return result;
}

export function upgradePreviewConfirmation(before, beforeDeck, preview, previewDeck, expectedCard) {
  const surface = preview.interaction.content.surface;
  const chosenId = before.interaction.content.surface.cards[0]?.entity_id;
  if (preview.interaction.kind !== "deck_upgrade_selection" || surface.stage !== "preview"
      || surface.min_select !== 1 || surface.max_select !== 1 || surface.cancelable !== true
      || surface.selected_count !== 1 || surface.selected_card_entity_ids?.length !== 1
      || surface.selected_card_entity_ids[0] !== chosenId || surface.can_confirm !== true
      || surface.preview_cards?.length !== 1 || surface.preview_cards[0].is_upgraded !== true
      || firstDifference(card(surface.preview_cards[0]), expectedCard)
      || firstDifference(restPersistentFacts(before, beforeDeck), restPersistentFacts(preview, previewDeck)))
    throw new Error("Upgrade preview must preserve the chosen card and uncommitted public game facts");
  const actions = preview.bound_actions.actions;
  const confirm = actions.filter((row) => row.verb === "confirm" && row.label === "Confirm card upgrade"
    && row.subject_referent_id == null && row.arguments.length === 0);
  const back = actions.filter((row) => row.verb === "cancel" && row.label === "Return to card selection"
    && row.subject_referent_id == null && row.arguments.length === 0);
  if (confirm.length !== 1 || back.length !== 1 || actions.length !== 2 || surface.can_cancel_preview !== true)
    throw new Error("Expected the complete current upgrade preview confirmation/back menu");
  return confirm[0];
}

export const restPlans = {
  "tent-heal-cancel-smith": ["HEAL", "SMITH", "cancel", "SMITH", "confirm", "close"],
  "tent-smith-cancel-heal": ["SMITH", "cancel", "SMITH", "confirm", "HEAL", "close"],
};
export function chooseRestAction(snapshot, operation) {
  const matches = snapshot.bound_actions.actions.filter((row) => {
    const key = restActionKey(snapshot, row);
    if (key == null) return false;
    return operation === "confirm" ? key.verb === "confirm" && key.arguments.length === 1
      : ["cancel", "close"].includes(operation) ? key.verb === operation
      : key.verb === "activate" && key.subject?.option_id === operation;
  });
  if (matches.length !== 1) throw new Error(`No unique current rest control for ${operation}`);
  return matches[0];
}

export function prepareRestSave(original) {
  // Explicit privileged test fixture, never a naturally reached run or training input.
  const value = structuredClone(original), map = value.acts?.[0]?.saved_map;
  if (value.ascension !== 8 || value.current_act_index !== 0 || !map?.start
      || map.start.coord.row !== 0 || value.visited_map_coords?.length !== 1
      || firstDifference(value.visited_map_coords[0], map.start.coord))
    throw new Error("Expected the frozen A8 initial-map fixture save");
  map.start.type = "rest_site";
  const start = map.points.find((row) => !firstDifference(row.coord, map.start.coord));
  // The native schema stores the start separately; tolerate a duplicated point only when present.
  if (start) start.type = "rest_site";
  value.pre_finished_room = null;
  value.map_point_history = [[]];
  return value;
}
