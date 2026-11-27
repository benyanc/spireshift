// The same qualified relic observations, with explicit current card-view flags.
import { projectRelicSurface as previous, publicCombatRelics, INVENTORY_CONTRACT } from "./engine-relic-surface-v1.mjs";
import { projectExactCombatSurface } from "./engine-combat-surface-v5.mjs";
export { INVENTORY_CONTRACT };
export function projectRelicSurface(state,ctx,helpers) {
  if(state.decision!=="combat_play")return previous(state,ctx,helpers);
  const relics=publicCombatRelics(state),result=projectExactCombatSurface(state,ctx,helpers);
  result.context.player.relics=relics;result.inventoryObservation=INVENTORY_CONTRACT;return result;
}
