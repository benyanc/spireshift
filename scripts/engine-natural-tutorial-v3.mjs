// Standard single-player tutorial controls, including separately advertised highlight actions.
import { completePublicMenu } from "./engine-menu-probe.mjs";
import { naturalTutorialAction as previous } from "./engine-natural-tutorial-v2.mjs";
const extra = new Map([["combat_reward_ftue", null], ["can_play_cards_ftue", null],
  ["cannot_play_card_ftue", "end_turn"], ["merchant_ftue", "inspect_merchant"]]);

export function naturalTutorialAction(snapshot) {
  const surface = snapshot.interaction?.content?.surface;
  if (!extra.has(surface?.tutorial_id)) return previous(snapshot);
  const actions = snapshot.bound_actions?.actions, options = surface.options;
  if (!completePublicMenu(snapshot, snapshot.session?.runtime_instance_id)
      || snapshot.interaction.kind !== "tutorial" || surface.stage !== "confirmation"
      || !surface.title?.trim() || !surface.body?.trim()
      || surface.current_page != null || surface.total_pages != null
      || !Array.isArray(options) || options.length !== actions.length
      || options.some(option => option.enabled !== true || !option.label?.trim()
        || !["dismiss_tutorial", extra.get(surface.tutorial_id)].includes(option.semantic_id))
      || new Set(options.map(option => option.semantic_id)).size !== options.length
      || actions.some(action => action.subject_referent_id != null || action.arguments.length
        || !["activate", "end_turn"].includes(action.verb))
      || options.some(option => actions.filter(action => action.label === option.label).length !== 1))
    throw Error(`Unqualified standard tutorial ${surface?.tutorial_id}`);
  // The diagnostic player acknowledges guidance, then selects gameplay from the refreshed full
  // room/turn menu. Highlight actions remain in the legal menu for future learned policies.
  const dismiss = options.find(option => option.semantic_id === "dismiss_tutorial");
  if (!dismiss) throw Error("No current non-gameplay tutorial confirmation");
  return actions.find(action => action.label === dismiss.label);
}
