import { prepareRestSave } from "./engine-rest-bridge-contract.mjs";

// Fresh privileged diagnostic save only. Both hosts execute the subsequent
// native battle and postcombat potion effect; this is never learning data.
export function preparePotionSave(original) {
  const value = prepareRestSave(original);
  const map = value.acts[0].saved_map;
  map.start.type = "monster";
  const start = map.points.find(point => point.coord.col === map.start.coord.col
    && point.coord.row === map.start.coord.row);
  if (start) start.type = "monster";
  if (value.players.length !== 1 || value.players[0].current_hp !== 48)
    throw Error("Require declared fresh 48/80 diagnostic player");
  return value;
}
