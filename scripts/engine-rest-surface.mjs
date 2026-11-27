// Public interaction projection only. Native options and selection preferences own legality.
export function projectExactRestSurface(state, ctx, helpers) {
  const { defaultProjector, withoutDeck, cardProperties, visibleText, enumerateSelections, actionLimit } = helpers;
  if (!["rest_site", "card_select"].includes(state.decision)) return defaultProjector(state, ctx);
  const context = { kind: state.decision === "rest_site" ? "rest" : "selection",
    run: state.context ?? null, player: withoutDeck(state.player) };
  const result = (surface, missing = [], totalCount = 0) => ({
    kind: surface.kind, stage: "choosing", prompt: null, surface, context,
    complete: missing.length === 0, missing, totalCount,
    visibleInformation: "same_build_native_rest_interaction_pending_shipped_comparison",
    interactionDiscovery: "native_current_options_and_explicit_selection_preferences"
  });
  const identity = (value) => typeof value === "string" && value.length > 0;
  const uniqueIndices = (items) => items.every((item) => Number.isSafeInteger(item?.index)
    && item.index >= 0 && item.index < items.length)
    && new Set(items.map((item) => item.index)).size === items.length;

  if (state.decision === "rest_site") {
    const raw = Array.isArray(state.options) ? state.options : [];
    const missing = [];
    if (!Array.isArray(state.options)) missing.push("native_remaining_rest_options");
    if (!identity(state.room_ref)) missing.push("native_rest_room_binding");
    if (typeof state.can_leave !== "boolean") missing.push("native_rest_proceed_availability");
    if (!uniqueIndices(raw) || raw.some((option) => !identity(option?.native_ref))
        || new Set(raw.map((option) => option.native_ref)).size !== raw.length)
      missing.push("native_rest_option_bindings");
    if (raw.some((option) => typeof option?.is_enabled !== "boolean"))
      missing.push("native_rest_option_enablement");
    const options = raw.map((option, index) => {
      const item = ctx.referent({ role: "rest_option", occurrence: index,
        label: option.name ?? option.option_id ?? `Option ${index + 1}`,
        enabled: typeof option.is_enabled === "boolean" ? option.is_enabled : null,
        properties: { index: option.index, option_id: option.option_id ?? null,
          name: option.name ?? null, description: visibleText(option.description),
          ...(typeof option.is_enabled === "boolean" ? { is_enabled: option.is_enabled } : {}) } });
      if (missing.length === 0 && option.is_enabled) ctx.action({
        verb: "activate", subject: item, label: item.label,
        raw: { cmd: "action", action: "choose_option", args: {
          room_ref: state.room_ref, option_ref: option.native_ref, option_index: option.index } }
      });
      return item.properties;
    });
    if (missing.length === 0 && state.can_leave) ctx.action({
      verb: "close", label: "Leave rest site",
      raw: { cmd: "action", action: "leave_room", args: { room_ref: state.room_ref } }
    });
    return result({ kind: "rest_site", stage: "choosing", options,
      ...(typeof state.can_leave === "boolean" ? { can_leave: state.can_leave } : {}) }, missing);
  }

  const raw = Array.isArray(state.cards) ? state.cards : [];
  const missing = [];
  if (!Array.isArray(state.cards) || !uniqueIndices(raw)) missing.push("native_selection_card_indices");
  const min = state.min_select, max = state.max_select;
  if (!Number.isSafeInteger(min) || !Number.isSafeInteger(max) || min < 0 || max < min || min > raw.length)
    missing.push("native_selection_bounds");
  if (typeof state.cancelable !== "boolean") missing.push("native_selection_cancelability");
  if (typeof state.require_manual_confirmation !== "boolean") missing.push("native_selection_confirmation_preference");
  const cards = raw.map((card, index) => ctx.referent({ role: "card", occurrence: index,
    label: card.name ?? `Card ${index + 1}`, properties: { index: card.index, ...cardProperties(card) } }));
  const surface = { kind: "card_selection", stage: "choosing", cards: cards.map((item) => item.properties),
    ...(Number.isSafeInteger(min) ? { min_select: min } : {}),
    ...(Number.isSafeInteger(max) ? { max_select: max } : {}),
    ...(typeof state.cancelable === "boolean" ? { cancelable: state.cancelable } : {}),
    ...(typeof state.require_manual_confirmation === "boolean"
      ? { require_manual_confirmation: state.require_manual_confirmation } : {}) };
  if (missing.length) return result(surface, missing);
  // Do not confuse cancellation with confirmation of an allowed empty selection.
  const selections = enumerateSelections(cards, min, max, actionLimit + 1);
  const count = selections.length + (state.cancelable ? 1 : 0);
  if (count > actionLimit) return result(surface, ["finite_selection_projection_exceeds_limit"], count);
  for (const selected of selections) ctx.action({
    verb: "confirm", arguments: selected.map((referent) => ({ role: "selected_card", referent })),
    label: selected.length ? `Confirm ${selected.map((item) => item.label).join(", ")}` : "Confirm empty selection",
    raw: { cmd: "action", action: "select_cards", args: { indices: selected.map((item) => item.properties.index).join(",") } }
  });
  if (state.cancelable) ctx.action({ verb: "cancel", label: "Cancel selection",
    raw: { cmd: "action", action: "skip_select" } });
  return result(surface);
}
