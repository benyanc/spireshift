// Natural decks may trigger a reshuffle after drawing only part of the next hand.
// Select only the exact currently offered control; no fixture-specific hand/round assumptions.
import { completePublicMenu } from "./engine-menu-probe.mjs";
import { tutorialAction } from "./engine-journey-tutorial-v4.mjs";

const confirmations = new Set(["shuffle_ftue", "rest_site_ftue", "obtain_relic_ftue", "obtain_potion_ftue", "power_card_ftue"]);
export function naturalTutorialAction(snapshot) {
  const surface = snapshot.interaction?.content?.surface;
  const context = snapshot.interaction?.content?.context;
  const actions = snapshot.bound_actions?.actions;
  if (!completePublicMenu(snapshot, snapshot.session?.runtime_instance_id)
      || snapshot.interaction.kind !== "tutorial") throw Error("Incomplete natural-run tutorial");
  if (surface?.tutorial_id === "combat_rules_ftue") return tutorialAction(snapshot);
  if (!confirmations.has(surface?.tutorial_id) || surface.stage !== "confirmation"
      || !surface.title?.trim() || !surface.body?.trim()
      || surface.current_page != null || surface.total_pages != null
      || surface.options?.length !== 1 || surface.options[0].semantic_id !== "dismiss_tutorial"
      || surface.options[0].enabled !== true || actions.length !== 1
      || actions[0].verb !== "activate" || actions[0].subject_referent_id != null
      || !Array.isArray(actions[0].arguments) || actions[0].arguments.length !== 0
      || actions[0].label !== surface.options[0].label)
    throw Error(`Unqualified natural-run tutorial ${surface?.tutorial_id}`);
  if (surface.tutorial_id === "shuffle_ftue" && (context?.kind !== "combat"
      || !Number.isSafeInteger(context.round) || context.round < 1 || context.is_play_phase !== false
      || !Array.isArray(context.player?.hand) || context.player.draw_pile_count !== 0
      || !Number.isSafeInteger(context.player.discard_pile_count) || context.player.discard_pile_count < 1))
    throw Error("No pending native reshuffle at the current tutorial");
  return actions[0];
}
