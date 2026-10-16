// Current native belt facts extend every live noncombat menu. IDs/raw operands stay in the ledger.
const identity = value => typeof value === "string" && value.length > 0;
export function appendPotionControls(state, ctx, helpers, result) {
  if (state.decision === "combat_play" || state.decision === "game_over" || !result.complete) return result;
  const missing = [], potions = state.player?.potions;
  if (!Array.isArray(potions) || !identity(state.player?.native_ref)) missing.push("native_belt_and_owner");
  const rows = Array.isArray(potions) ? potions : [];
  if (new Set(rows.map(row => row.native_ref)).size !== rows.length
      || new Set(rows.map(row => row.slot)).size !== rows.length) missing.push("native_belt_copy_bindings");
  const player = ctx.referent({ role: "player", id: ctx.id("potion_player", ctx.snapshotId, state.player?.native_ref),
    label: state.player?.name ?? "Player", properties: { hp: state.player?.hp, max_hp: state.player?.max_hp } });
  let merchant = null;
  if (state.decision === "merchant_approach") {
    if (!identity(state.merchant_ref) || !identity(state.room_ref) || state.inventory_open !== false)
      missing.push("native_closed_merchant_target");
    else merchant = ctx.referent({ role: "merchant", id: ctx.id("merchant", ctx.snapshotId, state.merchant_ref),
      label: "Merchant", properties: { target_type: "merchant", inventory_open: false } });
  }
  const actions = [], visible = rows.map((row, occurrence) => {
    if (!identity(row.native_ref) || !identity(row.id) || !Number.isSafeInteger(row.slot) || row.slot < 0
        || typeof row.can_use !== "boolean" || typeof row.can_discard !== "boolean"
        || typeof row.binding_supported !== "boolean" || typeof row.description !== "string"
        || !["AnyTime", "CombatOnly", "Automatic", "None"].includes(row.usage)) missing.push("native_current_potion_facts");
    const targets = [];
    if (row.can_use) {
      if (row.usage !== "AnyTime" || !row.binding_supported) missing.push("native_noncombat_potion_enablement");
      if (row.target_type === "AnyPlayer") {
        if (!Array.isArray(row.valid_target_refs) || row.valid_target_refs.length !== 1
            || row.valid_target_refs[0] !== state.player.native_ref) missing.push("native_potion_player_target");
        else targets.push({ item: player, native: row.valid_target_refs[0] });
      } else if (row.target_type === "TargetedNoCreature") {
        if (!merchant || row.id !== "FOUL_POTION" || !Array.isArray(row.valid_target_refs)
            || row.valid_target_refs.length !== 1 || row.valid_target_refs[0] !== state.merchant_ref)
          missing.push("native_potion_merchant_target");
        else targets.push({ item: merchant, native: state.merchant_ref });
      } else if (!["Self", "None"].includes(row.target_type)) missing.push("unsupported_noncombat_potion_target");
    }
    const item = ctx.referent({ role: "potion", occurrence, id: ctx.id("belt_potion", ctx.snapshotId, row.native_ref),
      label: row.name, enabled: row.can_use, properties: { definition_id: helpers.cardProperties(row).definition_id,
        name: row.name, description: helpers.visibleText(row.description), slot: row.slot, usage: row.usage,
        target_type: row.target_type, can_use: row.can_use, can_discard: row.can_discard,
        target_entity_ids: targets.map(target => target.item.properties.entity_id) } });
    if (row.can_use) {
      const args = { potion_slot: row.slot, potion_ref: row.native_ref };
      if (targets.length) for (const target of targets) actions.push({ verb: "use", subject: item,
        arguments: [{ role: "target", referent: target.item }], label: `Use ${row.name} on ${target.item.label}`,
        raw: { cmd: "action", action: "use_potion", args: { ...args, target_ref: target.native,
          ...(row.target_type === "TargetedNoCreature" ? { room_ref: state.room_ref } : {}) } } });
      else actions.push({ verb: "use", subject: item, label: `Use ${row.name}`,
        raw: { cmd: "action", action: "use_potion", args } });
    }
    if (row.can_discard) actions.push({ verb: "activate", subject: item, label: `Discard ${row.name}`,
      raw: { cmd: "action", action: "discard_potion", args: { potion_slot: row.slot, potion_ref: row.native_ref } } });
    return item.properties;
  });
  if (!missing.length) for (const action of actions) ctx.action(action);
  result.surface.potion_states = visible;
  result.complete = missing.length === 0;
  result.missing = [...(result.missing ?? []), ...new Set(missing)];
  return result;
}
