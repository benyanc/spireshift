// Privileged fixture construction, never an ordinary episode or learning label.
import { prepareRestSave } from "./engine-rest-bridge-contract.mjs";

export function prepareTreasureSave(original) {
  const value=prepareRestSave(original), map=value.acts[0].saved_map;
  map.start.type="treasure";
  const start=map.points.find(point=>point.coord.col===map.start.coord.col
    && point.coord.row===map.start.coord.row);
  if(start)start.type="treasure";
  return value;
}
