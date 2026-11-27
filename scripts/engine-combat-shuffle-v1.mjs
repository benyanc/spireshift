// Shuffle confirmation resumes a pending native draw; it is not a no-effect tutorial.
import { completePublicMenu } from "./engine-menu-probe.mjs";
export function shuffleTutorialAction(snapshot) {
  const surface=snapshot.interaction?.content?.surface,context=snapshot.interaction?.content?.context;
  const actions=snapshot.bound_actions?.actions;
  if(!completePublicMenu(snapshot,snapshot.session?.runtime_instance_id)
      || snapshot.interaction.kind!=="tutorial" || surface?.tutorial_id!=="shuffle_ftue"
      || surface.stage!=="confirmation" || !surface.title?.trim() || !surface.body?.trim()
      || surface.current_page!=null || surface.total_pages!=null
      || surface.options?.length!==1 || surface.options[0].semantic_id!=="dismiss_tutorial"
      || surface.options[0].enabled!==true || context?.kind!=="combat"
      || context.round!==2 || context.is_play_phase!==false || context.player.hand.length!==0
      || context.player.draw_pile_count!==0 || context.player.discard_pile_count<1
      || actions?.length!==1 || actions[0].verb!=="activate" || actions[0].subject_referent_id!=null
      || actions[0].arguments.length!==0 || actions[0].label!==surface.options[0].label)
    throw Error("Unqualified pending-draw shuffle tutorial");
  return actions[0];
}
