// v2 adds the same-build map-selection confirmation; all other exact checks stay versioned.
import { completePublicMenu } from "./engine-menu-probe.mjs";
import { naturalTutorialAction as previous } from "./engine-natural-tutorial-v1.mjs";

export function naturalTutorialAction(snapshot) {
  const surface = snapshot.interaction?.content?.surface;
  if (surface?.tutorial_id !== "map_select_ftue") return previous(snapshot);
  const actions = snapshot.bound_actions?.actions;
  if (!completePublicMenu(snapshot, snapshot.session?.runtime_instance_id)
      || snapshot.interaction.kind !== "tutorial" || surface.stage !== "confirmation"
      || !surface.title?.trim() || !surface.body?.trim()
      || surface.current_page != null || surface.total_pages != null
      || surface.options?.length !== 1 || surface.options[0].semantic_id !== "dismiss_tutorial"
      || surface.options[0].enabled !== true || actions.length !== 1
      || actions[0].verb !== "activate" || actions[0].subject_referent_id != null
      || actions[0].arguments.length !== 0 || actions[0].label !== surface.options[0].label)
    throw Error("Unqualified natural-run map-selection tutorial");
  return actions[0];
}
