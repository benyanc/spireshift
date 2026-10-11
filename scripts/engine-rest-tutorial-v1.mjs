// Only the newly qualified, single-confirmation rest popup is recognized.
import { completePublicMenu } from "./engine-menu-probe.mjs";
import { firstDifference, restPersistentFacts } from "./engine-rest-bridge-contract.mjs";

export function restTutorialAction(snapshot) {
  const surface = snapshot.interaction?.content?.surface;
  const actions = snapshot.bound_actions?.actions;
  if (!completePublicMenu(snapshot, snapshot.session?.runtime_instance_id)
      || snapshot.interaction.kind !== "tutorial" || snapshot.interaction.content.context?.kind !== "rest"
      || surface?.tutorial_id !== "rest_site_ftue" || surface.stage !== "confirmation"
      || surface.current_page != null || surface.total_pages != null
      || !surface.title?.trim() || !surface.body?.trim()
      || surface.options?.length !== 1 || surface.options[0].semantic_id !== "dismiss_tutorial"
      || surface.options[0].enabled !== true || actions?.length !== 1
      || actions[0].verb !== "activate" || actions[0].subject_referent_id != null
      || actions[0].arguments.length !== 0 || actions[0].label !== surface.options[0].label)
    throw new Error("Unqualified rest tutorial; no generic dismissal");
  return actions[0];
}

export function verifyRestTutorialEffect(before, beforeDeck, after, afterDeck) {
  restTutorialAction(before);
  if (after.interaction.kind !== "rest_site"
      || before.session.runtime_instance_id !== after.session.runtime_instance_id
      || before.snapshot_id === after.snapshot_id
      || firstDifference(restPersistentFacts(before, beforeDeck), restPersistentFacts(after, afterDeck)))
    throw new Error("Rest tutorial confirmation must leave public game facts unchanged");
  return true;
}
