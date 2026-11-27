// One physical native object keeps one public identity across visible owners.
// Definition/name equality never establishes physical identity.
import {projectSelectionFlows as previous} from "./engine-crystal-grid-v1.mjs";
import {selectionFlowReads as previousReads} from "./engine-chest-surface-v1.mjs";

export const INVENTORY_IDENTITY = "native_owned_inventory_object_identity_v1";

export function ownedPhysicalId(state, ctx, kind, source) {
  const key = {relic:"relics",card:"deck",potion:"potions"}[kind];
  if (!key || typeof source !== "string" || !source) throw Error("Invalid physical inventory lookup");
  const rows = state.player?.[key];
  if (!Array.isArray(rows) || rows.some(row => typeof row?.native_ref !== "string" || !row.native_ref)
      || new Set(rows.map(row => row.native_ref)).size !== rows.length)
    throw Error("Incomplete or duplicate physical inventory identities");
  const index = rows.findIndex(row => row.native_ref === source);
  if (index < 0) return null;
  const item = rows[index];
  return kind === "card" ? ctx.id("deck_card",item.native_ref,item.id,item.upgraded)
    : ctx.id(kind,ctx.snapshotId,item.native_ref,index);
}

export function ownedCatalogContext(state, ctx) {
  if (state.shop_catalog == null) return ctx;
  return {...ctx,id(kind,...parts) {
    const family = {shop_relic:"relic",shop_card:"card"}[kind];
    if (family) {
      if (parts.length !== 2 || parts[0] !== ctx.snapshotId)
        throw Error("Unexpected catalog identity scope");
      const owned = ownedPhysicalId(state,ctx,family,parts[1]);
      if (owned !== null) return owned;
    }
    return ctx.id(kind,...parts);
  }};
}

export function projectSelectionFlows(state, ctx, helpers) {
  return previous(state,ownedCatalogContext(state,ctx),helpers);
}

export function selectionFlowReads(state, reads, ctx, helpers) {
  return previousReads(state,reads,ownedCatalogContext(state,ctx),helpers);
}
