// The shipped SDK reports RunHistory.Win as a public win/loss context, not surface.victory.
import { assertPublicBoundary } from "./engine-run-contract-v1.mjs";

export function shippedEnding(snapshot, runtimeId) {
  assertPublicBoundary(snapshot);
  const context = snapshot.interaction?.content?.context;
  const surface = snapshot.interaction?.content?.surface;
  if (snapshot.interaction?.kind !== "game_over") return null;
  if (snapshot.session?.runtime_instance_id !== runtimeId
      || snapshot.information_policy?.includes_hidden_information !== false
      || snapshot.completeness?.status !== "complete"
      || !["observed", "interactive"].includes(snapshot.status)
      || surface?.kind !== "game_over"
      || context?.kind !== "game_over" || context.game_mode !== "standard"
      || !["win", "loss"].includes(context.result))
    throw Error("No complete explicit standard shipped ending");
  return { victory: context.result === "win", basis: "shipped_public_RunHistory_Win_context" };
}
