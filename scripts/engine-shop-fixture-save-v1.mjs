import { prepareRestSave } from "./engine-rest-bridge-contract.mjs";

// A fresh privileged shop-entry fixture. Subsequent purchases, native child
// choices, cancellation, gold/deck changes and final hooks execute normally.
export function prepareShopSave(original) {
  const value = prepareRestSave(original);
  const map = value.acts[0].saved_map;
  map.start.type = "shop";
  const start = map.points.find(p => p.coord.col === map.start.coord.col && p.coord.row === map.start.coord.row);
  if (start) start.type = "shop";
  const player = value.players[0];
  if (value.players.length !== 1 || player.current_hp !== 48 || player.gold !== 1000 || player.deck.length !== 3)
    throw Error("Require the exact fresh three-card funded shop diagnostic");
  return value;
}
