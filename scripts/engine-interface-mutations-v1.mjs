// Bounded corruption and preservation probes. No native execution or learning.
import { fixture } from "./engine-interface-case-bank-v1.mjs";
import { sharedDecision } from "./engine-shared-input-v3.mjs";

export function mutationChecks() {
  const cases = [];
  const add = (key, kind, change, expected) => cases.push({ key, kind, change, expected });
  for (const [key, change] of Object.entries({
    hidden_snapshot: x => { x.snapshot.information_policy.includes_hidden_information = true; },
    hidden_nested_field: x => { x.snapshot.interaction.content.context.rng = 13; },
    partial_snapshot: x => { x.snapshot.completeness.status = "partial"; },
    missing_read: x => { x.reads = []; },
    duplicate_read: x => { x.reads.push(x.reads[0]); },
    stale_read: x => { x.reads[0].observed_snapshot_id = "old"; },
    foreign_read: x => { x.reads[0].session = { runtime_instance_id: "other" }; },
    hidden_read: x => { x.reads[0].information_policy.includes_hidden_information = true; },
    partial_read: x => { x.reads[0].completeness.status = "partial"; },
    truncated_menu: x => { x.snapshot.bound_actions.status = "truncated"; },
    wrong_menu_count: x => { x.snapshot.bound_actions.total_count++; },
    duplicate_action: x => { x.snapshot.bound_actions.actions[1].bound_action_id = x.snapshot.bound_actions.actions[0].bound_action_id; },
    foreign_action_owner: x => { x.snapshot.bound_actions.actions[0].interaction_id = "other"; },
    unknown_operand: x => { x.snapshot.bound_actions.actions[0].subject_referent_id = "missing"; },
    nonfinite_fact: x => { x.snapshot.persistent.content.player.hp = NaN; },
    unknown_family: x => { x.snapshot.interaction.kind = "future_unknown_family"; },
    ambiguous_selection_type: x => { x.reads[0].content.cards[0].is_selected = null; },
  })) add(key, "combat_turn", change, "reject");
  for (const [key, change] of Object.entries({
    missing_outcome: x => { delete x.snapshot.interaction.content.context.result; },
    unknown_outcome: x => { x.snapshot.interaction.content.context.result = "pending"; },
    foreign_game_mode: x => { x.snapshot.interaction.content.context.game_mode = "multiplayer"; },
    conflicting_outcomes: x => { x.snapshot.interaction.content.surface.victory = true; },
  })) add(key, "game_over", change, "reject");
  for (const [key, change] of Object.entries({
    missing_inventory_flag: x => { delete x.snapshot.interaction.content.surface.can_close; },
    contradictory_inventory_control: x => { x.snapshot.interaction.content.surface.can_close = false; },
    unknown_inventory_boolean: x => { x.snapshot.interaction.content.surface.inventory_open = null; },
  })) add(key, "shop_inventory", change, "reject");
  for (const [key, change] of Object.entries({
    missing_room_flag: x => { delete x.snapshot.interaction.content.surface.can_open_inventory; },
    contradictory_room_flag: x => { x.snapshot.interaction.content.surface.can_open_inventory = false; },
  })) add(key, "shop_room", change, "reject");
  for (const [key, change] of Object.entries({
    wrong_selected_count: x => { x.snapshot.interaction.content.surface.selected_count = 1; },
    foreign_selected_card: x => { x.snapshot.interaction.content.surface.selected_card_entity_ids = ["foreign"]; },
    contradictory_active_selection: x => { x.snapshot.interaction.content.surface.cards[0].is_selected = true; },
  })) add(key, "deck_transform_selection", change, "reject");
  for (const [key, change] of Object.entries({
    current_cost: x => { x.snapshot.interaction.content.context.player.hand[0].cost = "0"; },
    per_copy_upgrade: x => { x.snapshot.interaction.content.context.player.hand[0].is_upgraded = true; },
    named_status_amount: x => { x.snapshot.interaction.content.context.player.statuses[0].amount = 7; },
    owned_relic_counter: x => { x.snapshot.persistent.content.player.relics[0].counter = 9; },
    unfamiliar_public_fact: x => { x.snapshot.interaction.content.surface.future_mechanic = { amount: 27 }; },
  })) add(key, "combat_turn", change, "distinct_or_reject_conflict");
  add("view_specific_description", "combat_turn", x => {
    x.snapshot.interaction.content.context.player.hand[0].description = "Changed hand-only view";
  }, "distinct");
  add("view_specific_selected_flag", "deck_transform_selection", x => {
    x.reads[0].content.cards[0].is_selected = true;
  }, "distinct");
  add("missing_selected_is_unknown", "deck_transform_selection", x => {
    delete x.reads[0].content.cards[0].is_selected;
  }, "distinct");
  add("optional_skip_kept", "rest_site", x => {
    x.snapshot.bound_actions.actions.push({ ...x.snapshot.bound_actions.actions[0], bound_action_id: "extra-skip", label: "Another public option" });
    x.snapshot.bound_actions.total_count++; x.snapshot.bound_actions.materialized_count++;
  }, "distinct");
  return cases.map(({ key, kind, change, expected }) => {
    const base = fixture(kind), original = sharedDecision(base.snapshot, base.reads);
    const changed = structuredClone(base); change(changed);
    let frame, error = null;
    try { frame = sharedDecision(changed.snapshot, changed.reads); } catch (failure) { error = failure.message; }
    const distinct = !!frame && frame.input_digest !== original.input_digest;
    const passed = expected === "reject" ? !!error : expected === "distinct" ? distinct
      : distinct || !!error && error.startsWith("Conflicting current public entity facts");
    return { key, expected, passed, rejected: !!error, distinct, error };
  });
}
