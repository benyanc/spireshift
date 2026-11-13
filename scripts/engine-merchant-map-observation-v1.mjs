import { stableJson } from "./engine-public-input-v1.mjs";

// The frozen host returns MapSelectState directly from leave_shop. Its
// merchant presentation refreshes on the next native Observe call.
export async function observeAfterMerchantExit(request, response, read) {
  if (request.cmd !== "action" || request.action !== "leave_shop"
      || response.type !== "decision" || response.decision !== "map_select") return response;
  const belt = response.player?.potions;
  const stale = row => row.target_type === "TargetedNoCreature"
    && (row.can_use || row.valid_target_refs?.length);
  if (!Array.isArray(belt) || !belt.some(stale)) return response;
  if (typeof request.args?.room_ref !== "string"
      || belt.some(row => stale(row) && (row.id !== "FOUL_POTION"
        || !Array.isArray(row.valid_target_refs) || row.valid_target_refs.length !== 1
        || typeof row.valid_target_refs[0] !== "string")))
    throw Error("Unrecognized native target after opening the map from a merchant");
  const expected = { ...response, player: { ...response.player, potions: belt.map(row =>
    stale(row) ? { ...row, can_use: false, valid_target_refs: [] } : row) } };
  const current = await read({ cmd: "observe" });
  if (stableJson(current) !== stableJson(expected))
    throw Error("Native merchant map refresh changed more than the departed target");
  return current;
}
