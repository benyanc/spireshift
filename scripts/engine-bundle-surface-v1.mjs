// Exact bundle menu with private instance/item operands. Existing frozen projections stay intact.
import { projectExactCombatSurface } from "./engine-combat-surface.mjs";

const identity = (value) => typeof value === "string" && value.length > 0;
export function projectExactBundleSurface(state, ctx, helpers) {
  if (state.decision !== "bundle_select") return projectExactCombatSurface(state, ctx, helpers);
  const missing = [];
  const rows = Array.isArray(state.bundles) ? state.bundles : [];
  if (!identity(state.selection_ref)) missing.push("native_bundle_selection_instance");
  if (!Array.isArray(state.bundles) || !rows.length) missing.push("native_bundle_options");
  if (rows.length > helpers.actionLimit) missing.push("finite_bundle_projection_exceeds_limit");
  if (rows.some((row) => !row || !Number.isSafeInteger(row.index) || row.index < 0 || row.index >= rows.length
      || !identity(row.native_ref)) || new Set(rows.map((row) => row?.index)).size !== rows.length
      || new Set(rows.map((row) => row?.native_ref)).size !== rows.length)
    missing.push("native_bundle_item_bindings");
  if (rows.some((row) => !Array.isArray(row?.cards) || !row.cards.length
      || row.cards.some((card) => !identity(card?.id) || !identity(card.name)
        || typeof card.description !== "string" || typeof card.is_upgraded !== "boolean"
        || !(card.cost === "X" || (Number.isSafeInteger(card.cost) && card.cost >= 0)))))
    missing.push("native_bundle_card_facts");
  const bundles = rows.map((row, occurrence) => {
    const item = ctx.referent({ role: "card_bundle", occurrence,
      label: `Bundle ${occurrence + 1}`, properties: { index: row?.index ?? null,
        cards: (Array.isArray(row?.cards) ? row.cards : []).map((card) => ({
          ...helpers.cardProperties(card ?? {}), description: helpers.visibleText(card?.description)
        })) } });
    if (!missing.length) ctx.action({ verb: "select", subject: item,
      label: `Take bundle ${occurrence + 1}`, raw: { cmd: "action", action: "select_bundle",
        args: { selection_ref: state.selection_ref, bundle_ref: row.native_ref, bundle_index: row.index } } });
    return item.properties;
  });
  return { kind: "card_bundle_selection", stage: "choosing", prompt: null,
    surface: { kind: "card_bundle_selection", stage: "choosing", bundles },
    context: { kind: "selection", run: state.context ?? null, player: helpers.withoutDeck(state.player) },
    complete: missing.length === 0, missing, totalCount: rows.length,
    visibleInformation: "same_build_native_bundle_choices_pending_shipped_comparison",
    interactionDiscovery: "native_current_bundle_and_selection_binding" };
}
