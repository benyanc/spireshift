// Artificial public envelopes derived from the registered interface families.
// These are parser/routing probes, never engine outcomes or training episodes.
export const PRESENTATION = ["main_menu", "singleplayer_menu", "character_select", "tutorial"];
export const POLICY = ["event_option", "event_dialogue", "map_navigation", "combat_turn", "rest_site",
  "shop_room", "shop_inventory", "native_deck_card_selection", "native_simple_card_selection",
  "native_combat_pile_selection", "combat_hand_card_selection", "deck_upgrade_selection",
  "deck_transform_selection", "deck_enchant_selection", "native_generated_card_choice",
  "card_bundle_selection", "reward_claim", "card_reward_selection", "treasure_room"];

export function fixture(kind = "combat_turn", prefix = "artificial") {
  const id = value => `${prefix}-${value}`;
  const card = { entity_id: id("card"), definition_id: "TEST_CARD", name: "Test card", type: "Attack",
    cost: "1", rarity: "Basic", is_upgraded: false, is_selected: false, description: "Synthetic card" };
  const snapshot = { snapshot_id: id("snapshot"), session: { runtime_instance_id: id("runtime") },
    information_policy: { includes_hidden_information: false }, completeness: { status: "complete" }, status: "interactive",
    persistent: { content: { scope: "active_single_player_run",
      run: { act: 1, act_definition_id: "UNDERDOCKS", floor: 3, ascension: 8 },
      player: { entity_id: id("player"), character_definition_id: "IRONCLAD", hp: 41, max_hp: 80,
        gold: 99, relics: [{ entity_id: id("relic"), definition_id: "TEST_RELIC", counter: 2 }], potions: [] } } },
    interaction: { interaction_id: id("interaction"), kind, stage: "ready",
      content: { context: { kind: "selection" }, surface: { kind, cards: [structuredClone(card)] } } },
    referents: [{ referent_id: id("card"), role: "card", label: "Test card",
      properties: structuredClone(card), state: { visible: true, enabled: true } }],
    reads: [{ read_id: id("read"), kind: "run_deck", ordering_semantics: "unordered_multiset" }],
    bound_actions: { status: "complete", total_count: 1, materialized_count: 1, actions: [] } };
  const action = (name, verb, label, subject = null, arguments_ = []) => ({
    bound_action_id: id(name), interaction_id: id("interaction"), verb, label,
    ...(subject ? { subject_referent_id: subject } : {}), arguments: arguments_ });
  snapshot.bound_actions.actions = [action("skip", "skip", "Skip")];
  const context = snapshot.interaction.content.context, surface = snapshot.interaction.content.surface;
  if (kind === "combat_turn") {
    Object.assign(context, { kind: "combat", round: 2, player: { player_entity_id: id("player"), hand: [structuredClone(card)],
      statuses: [{ definition_id: "STRENGTH", amount: 2 }, { definition_id: "DEXTERITY", amount: 7 }], energy: 2, block: 0 } });
    snapshot.bound_actions.actions = [action("play", "play", "Play test card", id("card")), action("end", "end_turn", "End turn")];
  } else if (kind === "event_option") {
    context.kind = "event";
    surface.options = [{ entity_id: id("option"), index: 0, title: "Synthetic choice", description: "Synthetic option",
      is_enabled: true, is_locked: false, is_proceed: false, was_chosen: false, will_kill_player: false, tooltips: [] }];
    snapshot.referents.push({ referent_id: id("option"), role: "option", label: "Synthetic choice",
      state: { visible: true, enabled: true }, properties: surface.options[0] });
    snapshot.bound_actions.actions = [action("choose", "choose", "Synthetic choice", id("option"))];
  } else if (kind === "event_dialogue") context.kind = "event";
  else if (kind === "shop_room") {
    context.kind = "shop"; snapshot.interaction.content.surface = { kind, can_open_inventory: true, can_proceed: true };
    snapshot.bound_actions.actions = [action("open", "open", "Open shop inventory"), action("leave", "activate", "Leave shop and open map")];
  } else if (kind === "shop_inventory") {
    context.kind = "shop"; snapshot.interaction.content.surface = { kind, cards: [], relics: [], potions: [], card_removal: null, can_close: true };
    snapshot.bound_actions.actions = [action("close", "cancel", "Close shop inventory")];
  } else if (kind === "game_over") {
    Object.assign(context, { kind: "game_over", result: "loss", game_mode: "standard" });
    snapshot.interaction.content.surface = { kind, stage: "intro", can_advance_summary: true, can_return: false, other_controls: [] };
    snapshot.bound_actions.actions = [action("continue", "activate", "Continue to the run summary")];
  } else if (kind === "rest_site") context.kind = "rest";
  else if (kind === "treasure_room") context.kind = "treasure";
  else if (kind === "map_navigation") context.kind = "map";
  else if (["card_reward_selection", "reward_claim"].includes(kind)) context.kind = "reward";
  if (kind.includes("selection") || kind === "native_generated_card_choice")
    Object.assign(surface, { selected_count: 0, min_select: 0, max_select: 2, selected_card_entity_ids: [],
      selectable_card_entity_ids: [id("card")], deselectable_card_entity_ids: [], can_confirm: true, can_cancel: true });
  snapshot.bound_actions.total_count = snapshot.bound_actions.materialized_count = snapshot.bound_actions.actions.length;
  const reads = [{ read_id: id("read"), kind: "run_deck", expected_snapshot_id: snapshot.snapshot_id,
    observed_snapshot_id: snapshot.snapshot_id, session: snapshot.session,
    completeness: { status: "complete" }, information_policy: { includes_hidden_information: false },
    content: { kind: "run_deck", card_count: 1, cards: [structuredClone(card)] } }];
  return { snapshot, reads };
}

export function caseBank() {
  return [...POLICY, "game_over"].map(kind => ({ key: `registered-${kind}`, ...fixture(kind) }));
}
