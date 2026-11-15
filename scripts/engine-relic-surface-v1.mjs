// Only an observed public counter is added. Native rules and action operands stay unchanged.
import { projectSelectionSurface as previous } from "./engine-selection-cursor-v1.mjs";
export const INVENTORY_CONTRACT = "public_owned_combat_relic_counters_v1";

export function publicCombatRelics(state) {
  if (!Array.isArray(state.player?.relics)) throw Error("Missing native combat relic inventory");
  return state.player.relics.map(row => {
    if (typeof row.id !== "string" || !row.id || !Object.hasOwn(row, "counter")
        || !(row.counter === null || typeof row.counter === "number" && Number.isFinite(row.counter)))
      throw Error("Missing or invalid native public relic identity/counter");
    // Do not spread a native object: vars, handles and unqualified fields stay private.
    return { id: row.id, counter: row.counter };
  });
}

export function projectRelicSurface(state, ctx, helpers) {
  if (state.decision !== "combat_play") return previous(state, ctx, helpers);
  const relics = publicCombatRelics(state); // Validate before advertising any action.
  const result = previous(state, ctx, helpers);
  result.context.player.relics = relics;
  result.inventoryObservation = INVENTORY_CONTRACT;
  return result;
}
