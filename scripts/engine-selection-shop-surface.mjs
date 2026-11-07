// Public facts and private action bindings. All enablement and selection preferences are native.
import { projectExactRestSurface } from "./engine-rest-surface.mjs";

const identity = (value) => typeof value === "string" && value.length > 0;

export function projectExactSelectionShopSurface(state, ctx, helpers) {
  if (state.decision === "card_select") {
    const missing = [];
    if (!identity(state.selection_ref)) missing.push("native_selection_instance_binding");
    if (state.selection_preferences_complete !== true) missing.push("native_selection_preferences_capture");
    for (const name of ["unpowered_previews", "pretend_cards_can_be_played"])
      if (typeof state[name] !== "boolean") missing.push(`native_selection_${name}`);
    const selectionContext = { ...ctx, referent: (value) => ctx.referent(value),
      action(value) {
        if (missing.length) return;
        ctx.action({ ...value, raw: { ...value.raw,
          args: { ...value.raw.args, selection_ref: state.selection_ref } } });
      } };
    const result = projectExactRestSurface(state, selectionContext, helpers);
    result.missing = [...result.missing, ...missing];
    result.complete = result.missing.length === 0;
    result.prompt = helpers.visibleText(state.prompt);
    for (const name of ["unpowered_previews", "pretend_cards_can_be_played"])
      if (typeof state[name] === "boolean") result.surface[name] = state[name];
    result.visibleInformation = "same_build_native_selection_preferences_pending_shipped_comparison";
    return result;
  }
  if (state.decision !== "shop") return projectExactRestSurface(state, ctx, helpers);

  const missing = [];
  if (!identity(state.room_ref)) missing.push("native_shop_room_binding");
  for (const group of ["cards", "relics", "potions"])
    if (!Array.isArray(state[group])) missing.push(`native_shop_${group}`);
  if (!state.card_removal || typeof state.card_removal !== "object") missing.push("native_shop_removal_service");
  const groups = ["cards", "relics", "potions"].map((name) => Array.isArray(state[name]) ? state[name] : []);
  const entries = [...groups.flat(), ...(state.card_removal ? [state.card_removal] : [])];
  if (entries.some((row) => !row || typeof row !== "object" || !identity(row.native_ref))
      || new Set(entries.map((row) => row?.native_ref)).size !== entries.length)
    missing.push("native_shop_entry_bindings");
  if (entries.some((row) => !Number.isSafeInteger(row?.cost) || row.cost < 0)) missing.push("native_shop_current_prices");
  if (entries.some((row) => typeof row?.can_purchase !== "boolean" || typeof row?.is_stocked !== "boolean"
      || (row.can_purchase && !row.is_stocked)))
    missing.push("native_shop_purchase_availability");
  if (groups.flat().some((row) => row?.is_stocked && (!identity(row.id) || !identity(row.item_ref))))
    missing.push("native_shop_stocked_item_identity");
  if (groups[0].some((row) => typeof row?.on_sale !== "boolean")) missing.push("native_shop_card_sale_status");

  const purchaseGroups = ["buy_card", "buy_relic", "buy_potion"];
  const roles = ["shop_card", "shop_relic", "shop_potion"];
  const projected = groups.map((rows, group) => rows.map((row, occurrence) => {
    const props = group === 0 ? helpers.cardProperties({ ...row, cost: row.card_cost }) : {
      definition_id: identity(row?.id) ? helpers.cardProperties(row).definition_id : null,
      name: row?.name ?? null, description: helpers.visibleText(row?.description)
    };
    const item = ctx.referent({ role: roles[group], occurrence, label: row?.name ?? `Item ${occurrence + 1}`,
      enabled: typeof row?.can_purchase === "boolean" ? row.can_purchase : null,
      properties: { ...props, price: row?.cost ?? null, is_stocked: row?.is_stocked ?? null,
        can_purchase: row?.can_purchase ?? null, ...(group === 0 ? { on_sale: row?.on_sale ?? null } : {}) } });
    if (!missing.length && row.can_purchase) ctx.action({ verb: "activate", subject: item,
      label: `Buy ${item.label}`, raw: { cmd: "action", action: purchaseGroups[group], args: {
        entry_ref: row.native_ref, item_ref: row.item_ref, quoted_cost: row.cost } } });
    return item.properties;
  }));
  let removal = null;
  if (state.card_removal && typeof state.card_removal === "object") {
    const row = state.card_removal;
    const item = ctx.referent({ role: "shop_service", label: "Card removal",
      enabled: typeof row.can_purchase === "boolean" ? row.can_purchase : null,
      properties: { service: "card_removal", price: row.cost ?? null, is_stocked: row.is_stocked ?? null,
        can_purchase: row.can_purchase ?? null } });
    removal = item.properties;
    if (!missing.length && row.can_purchase) ctx.action({ verb: "activate", subject: item,
      label: "Buy card removal", raw: { cmd: "action", action: "remove_card", args: {
        entry_ref: row.native_ref, quoted_cost: row.cost } } });
  }
  if (!missing.length) ctx.action({ verb: "close", label: "Leave shop",
    raw: { cmd: "action", action: "leave_shop", args: { room_ref: state.room_ref } } });
  return { kind: "shop_inventory", stage: "choosing", prompt: null,
    surface: { kind: "shop_inventory", stage: "choosing", cards: projected[0], relics: projected[1],
      potions: projected[2], card_removal: removal },
    context: { kind: "shop", run: state.context ?? null, player: helpers.withoutDeck(state.player) },
    complete: missing.length === 0, missing,
    visibleInformation: "same_build_native_shop_purchase_controls_pending_shipped_comparison",
    interactionDiscovery: "native_purchase_availability_current_item_and_price_binding" };
}
