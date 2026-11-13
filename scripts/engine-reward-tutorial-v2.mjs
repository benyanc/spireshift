// Only exact fresh relic/potion reward tutorials; never arbitrary modal dismissal.
import { completePublicMenu } from "./engine-menu-probe.mjs";
import { shopPersistentFacts } from "./engine-shop-bridge-contract.mjs";
import { firstDifference } from "./engine-journey-contract-v2.mjs";
export function rewardTutorialAction(snapshot, expectedId) {
  const surface=snapshot.interaction?.content?.surface, actions=snapshot.bound_actions?.actions;
  if (!["obtain_relic_ftue","obtain_potion_ftue"].includes(expectedId)
      || !completePublicMenu(snapshot,snapshot.session?.runtime_instance_id)
      || snapshot.interaction.kind!=="tutorial" || surface?.tutorial_id!==expectedId
      || surface.stage!=="confirmation" || surface.current_page!=null || surface.total_pages!=null || typeof surface.title!=="string" || !surface.title
      || typeof surface.body!=="string" || !surface.body || surface.options?.length!==1
      || surface.options[0].semantic_id!=="dismiss_tutorial" || surface.options[0].enabled!==true
      || actions?.length!==1 || actions[0].verb!=="activate" || actions[0].subject_referent_id!=null
      || actions[0].arguments?.length!==0 || actions[0].label!==surface.options[0].label)
    throw Error("Unqualified reward tutorial; no generic dismissal");
  return actions[0];
}
export function verifyRewardTutorial(before,beforeDeck,after,afterDeck,expectedId) {
  rewardTutorialAction(before,expectedId);
  if (after.interaction.kind!=="reward_claim" || before.snapshot_id===after.snapshot_id
      || before.session.runtime_instance_id!==after.session.runtime_instance_id
      || firstDifference(shopPersistentFacts(before,beforeDeck),shopPersistentFacts(after,afterDeck)))
    throw Error("Reward tutorial confirmation changed persistent facts or its reward owner");
  return true;
}
