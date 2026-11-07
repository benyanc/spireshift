// Player-visible combat facts and exact private operands; native code owns all rules.
import { projectExactSelectionShopSurface } from "./engine-selection-shop-surface.mjs";

const identity = (value) => typeof value === "string" && value.length > 0;
const finite = (value) => typeof value === "number" && Number.isFinite(value);
const unique = (rows) => rows.every((row) => identity(row?.native_ref))
  && new Set(rows.map((row) => row.native_ref)).size === rows.length;
const supportedUntargeted = new Set(["Self", "None", "AllEnemies", "RandomEnemy", "AllAllies"]);

export function projectExactCombatReads(state, reads, ctx, helpers) {
  return reads.map((read) => {
    if (read.descriptor.kind !== "combat_piles") return read;
    const missing = [];
    const zones = (state.combat_piles ?? []).map((zone) => {
      const rows = Array.isArray(zone.cards) ? zone.cards : [];
      if (!unique(rows) || !Array.isArray(zone.cards)) missing.push("native_pile_copy_identity");
      const cards = rows.map((row) => ({ ...helpers.cardProperties(row),
        entity_id: ctx.id("pile_card", ctx.snapshotId, zone.pile, row.native_ref),
        description: helpers.visibleText(row.description) }));
      // Source enumeration order and source index are never ordering keys or ID inputs.
      const key = ({ entity_id, ...facts }) => JSON.stringify(facts) + entity_id;
      cards.sort((left, right) => key(left) < key(right) ? -1 : key(left) > key(right) ? 1 : 0);
      return { zone: zone.pile, card_count: cards.length, ordering_semantics: "unordered_multiset", cards };
    });
    return { ...read, content: { kind: "combat_piles", zones }, completeness: { ...read.completeness,
      status: missing.length ? "partial" : "complete", missing: [...new Set(missing)] } };
  });
}

export function projectExactCombatSurface(state, ctx, helpers) {
  if (state.decision !== "combat_play") return projectExactSelectionShopSurface(state, ctx, helpers);
  const missing = [];
  const hand = Array.isArray(state.hand) ? state.hand : [];
  const enemies = Array.isArray(state.enemies) ? state.enemies : [];
  const potions = Array.isArray(state.player?.potions) ? state.player.potions : [];
  for (const name of ["hand", "enemies", "player_statuses", "companions", "orbs"])
    if (!Array.isArray(state[name])) missing.push(`native_combat_${name}`);
  if (!identity(state.player?.native_ref) || !unique([...hand, ...enemies, ...potions])) missing.push("native_combat_operand_identity");
  for (const name of ["round", "energy", "max_energy", "draw_pile_count", "discard_pile_count", "exhaust_pile_count", "orb_slots"])
    if (!Number.isSafeInteger(state[name]) || state[name] < 0) missing.push(`native_combat_${name}`);
  if (state.is_play_phase !== true || state.turn_owner !== "player") missing.push("native_local_player_play_phase");
  if (!identity(state.encounter_type)) missing.push("native_combat_encounter_type");
  if (state.companions?.length || state.orbs?.length) missing.push("unqualified_companion_or_orb_mechanics");
  const visibleStatus = (row) => {
    if (!identity(row?.id) || !finite(row.amount) || typeof row.description !== "string") missing.push("native_visible_status_facts");
    return { definition_id: row?.id ?? null, name: row?.name ?? null, amount: row?.amount ?? null,
      type: row?.type ?? null, description: helpers.visibleText(row?.description) };
  };
  const visibleCard = (row) => {
    if (!identity(row?.id) || !(row.cost === "X" || (Number.isSafeInteger(row.cost) && row.cost >= 0))
        || typeof row.can_play !== "boolean" || !identity(row.target_type) || typeof row.description !== "string")
      missing.push("native_current_hand_card_facts");
    if (row.stats != null && (typeof row.stats !== "object" || Array.isArray(row.stats)
        || Object.values(row.stats).some((value) => !finite(value)))) missing.push("native_card_preview_stats");
    const result = { ...helpers.cardProperties(row), entity_id: ctx.id("card", ctx.snapshotId, row.native_ref),
      description: helpers.visibleText(row.description), stats: row.stats == null ? null : { ...row.stats },
      stat_basis: "native_untargeted_card_preview", unplayable_reason: row.unplayable_reason ?? null };
    for (const kind of ["enchantment", "affliction"]) if (row[kind] != null) {
      if (!identity(row[`${kind}_id`]) || typeof row[`${kind}_description`] !== "string") missing.push(`native_card_${kind}_definition`);
      result[kind] = { definition_id: row[`${kind}_id`] ?? null, name: row[kind], amount: row[`${kind}_amount`] ?? null,
        description: helpers.visibleText(row[`${kind}_description`]) };
    }
    return result;
  };
  const playerEntity = ctx.id("player", ctx.snapshotId, state.player?.native_ref);
  const playerContext = { player_entity_id: playerEntity, block: state.player?.block ?? null, energy: state.energy,
    max_energy: state.max_energy, hand: [], statuses: (state.player_statuses ?? []).map(visibleStatus),
    draw_pile_count: state.draw_pile_count, discard_pile_count: state.discard_pile_count, exhaust_pile_count: state.exhaust_pile_count,
    companions: [], orbs: [], orb_slots: state.orb_slots, potion_states: [] };
  const playerTarget = ctx.referent({ role: "player", id: playerEntity, label: state.player?.name ?? "Player",
    properties: playerContext, includeEntityId: false });
  const targets = new Map([[state.player?.native_ref, playerTarget]]);
  const enemyRows = enemies.map((row, occurrence) => {
    if (!identity(row.id) || !Number.isSafeInteger(row.combat_id) || ![row.hp, row.max_hp, row.block].every(finite)
        || !Array.isArray(row.statuses)) missing.push("native_visible_enemy_facts");
    const intents = (row.intents ?? []).map((intent) => {
      if (![intent.type, intent.label, intent.title, intent.description].every((value) => typeof value === "string"))
        missing.push("native_enemy_intent_text");
      const result = { type: intent.type, label: helpers.visibleText(intent.label), title: helpers.visibleText(intent.title),
        description: helpers.visibleText(intent.description) };
      for (const field of ["damage", "hits", "total_damage"]) if (intent[field] != null) {
        if (!finite(intent[field])) missing.push(`native_intent_${field}`); result[field] = intent[field];
      }
      return result;
    });
    const item = ctx.referent({ role: "enemy", occurrence, id: ctx.id("enemy", ctx.snapshotId, row.native_ref),
      label: row.name ?? `Enemy ${occurrence + 1}`, properties: { definition_id: row.id, combat_id: row.combat_id,
        hp: row.hp, max_hp: row.max_hp, block: row.block, name: row.name,
        statuses: (row.statuses ?? []).map(visibleStatus), intents, intends_attack: row.intends_attack } });
    targets.set(row.native_ref, item); return item.properties;
  });
  const nativeTargets = (row, playerOnly = false) => {
    if (!Array.isArray(row.valid_target_refs) || new Set(row.valid_target_refs).size !== row.valid_target_refs.length
        || row.valid_target_refs.some((ref) => !targets.has(ref)
          || (playerOnly ? ref !== state.player.native_ref : ref === state.player.native_ref))) {
      missing.push("native_current_target_bindings"); return [];
    }
    return row.valid_target_refs.map((ref) => ({ native: ref, item: targets.get(ref) }));
  };
  const handEntries = hand.map((row, occurrence) => {
    const props = visibleCard(row);
    const targetRows = row.target_type === "AnyEnemy" ? nativeTargets(row) : [];
    if (row.target_type !== "AnyEnemy" && !supportedUntargeted.has(row.target_type)) missing.push("unqualified_card_target_type");
    const item = ctx.referent({ role: row.can_play ? "playable_card" : "hand", occurrence,
      id: props.entity_id, label: row.name, enabled: row.can_play, properties: props });
    const option = { entity_id: props.entity_id, name: row.name, target_entity_ids: targetRows.map(({ item }) => item.properties.entity_id) };
    return { row, item, option, props, targetRows };
  });
  playerContext.hand.push(...handEntries.map(({ props }) => props));
  const potionEntries = potions.map((row, occurrence) => {
    if (typeof row.can_use !== "boolean" || typeof row.can_discard !== "boolean" || row.binding_supported !== true
        || !Number.isSafeInteger(row.slot) || row.slot < 0) missing.push("native_potion_enablement");
    const targetRows = ["AnyEnemy", "AnyPlayer"].includes(row.target_type) ? nativeTargets(row, row.target_type === "AnyPlayer") : [];
    if (!["AnyEnemy", "AnyPlayer"].includes(row.target_type) && !supportedUntargeted.has(row.target_type))
      missing.push("unqualified_potion_target_type");
    const props = { entity_id: ctx.id("potion", ctx.snapshotId, row.native_ref), definition_id: row.id, name: row.name,
      description: helpers.visibleText(row.description), target_type: row.target_type, can_use: row.can_use,
      can_discard: row.can_discard, automatic: row.usage === "Automatic",
      target_entity_ids: targetRows.map(({ item }) => item.properties.entity_id ?? playerEntity) };
    const item = ctx.referent({ role: "potion", occurrence, id: props.entity_id, label: row.name, properties: props });
    return { row, item, props, targetRows };
  });
  playerContext.potion_states.push(...potionEntries.map(({ props }) => props));
  if (!missing.length) {
    for (const { row, item, targetRows } of handEntries.filter(({ row }) => row.can_play)) {
      if (row.target_type === "AnyEnemy") for (const target of targetRows) ctx.action({ verb: "play", subject: item,
        arguments: [{ role: "target", referent: target.item }], label: `Play ${row.name} on ${target.item.label}`,
        raw: { cmd: "action", action: "play_card", args: { card_ref: row.native_ref, target_ref: target.native } } });
      else ctx.action({ verb: "play", subject: item, label: `Play ${row.name}`,
        raw: { cmd: "action", action: "play_card", args: { card_ref: row.native_ref } } });
    }
    ctx.action({ verb: "end_turn", label: "End turn",
      raw: { cmd: "action", action: "end_turn", args: { player_ref: state.player.native_ref } } });
    for (const { row, item, targetRows } of potionEntries) {
      if (row.can_use) {
        const args = { potion_slot: row.slot, potion_ref: row.native_ref };
        if (["AnyEnemy", "AnyPlayer"].includes(row.target_type)) for (const target of targetRows)
          ctx.action({ verb: "use", subject: item, arguments: [{ role: "target", referent: target.item }],
            label: `Use ${row.name} on ${target.item.label}`, raw: { cmd: "action", action: "use_potion", args: { ...args, target_ref: target.native } } });
        else ctx.action({ verb: "use", subject: item, label: `Use ${row.name}`, raw: { cmd: "action", action: "use_potion", args } });
      }
      if (row.can_discard) ctx.action({ verb: "activate", subject: item, label: `Discard ${row.name}`,
        raw: { cmd: "action", action: "discard_potion", args: { potion_slot: row.slot, potion_ref: row.native_ref } } });
    }
  }
  return { kind: "combat_turn", stage: "ready", prompt: null,
    surface: { kind: "combat_turn", can_end_turn: state.is_play_phase === true && !missing.length,
      playable_cards: handEntries.filter(({ row }) => row.can_play).map(({ option }) => option),
      usable_potions: potionEntries.filter(({ row }) => row.can_use).map(({ props }) => props) },
    context: { kind: "combat", encounter_type: state.encounter_type, round: state.round, turn_owner: state.turn_owner,
      is_play_phase: state.is_play_phase, player: playerContext, enemies: enemyRows },
    complete: missing.length === 0, missing: [...new Set(missing)],
    visibleInformation: "named_same_build_native_combat_facts_pending_shipped_comparison",
    interactionDiscovery: "native_current_playability_cost_and_operand_binding",
    hiddenByPolicy: ["hidden_rng", "draw_pile_true_order", "future_enemy_moves", "future_rewards"] };
}
