// One model Continue includes native, non-gameplay tutorial acknowledgements.
// Only the exact combat-reward warning permits a freshly revalidated final click.
import {stableJson} from './engine-public-input-v1.mjs';
import {completePublicMenu} from './engine-menu-probe.mjs';
import {naturalTutorialAction} from './engine-natural-tutorial-v3.mjs';
import {rewardProceed, verifyRewardDeparture as prior} from './engine-reward-commit-v1.mjs';
export {rewardProceed};
const WARNING='combat_reward_ftue';
const same=(a,b)=>stableJson(a)===stableJson(b);
function received(snapshot,action,receipt,runtime){
  if(snapshot.session?.runtime_instance_id!==runtime||!completePublicMenu(snapshot,runtime)
    ||!snapshot.bound_actions.actions.some(a=>same(a,action))||receipt?.delivery!=='delivered'
    ||receipt.attribution?.runtime_instance_id!==runtime
    ||receipt.action?.bound_action_id!==action.bound_action_id)
    throw Error('Unverified reward UI delivery; no retry');
}
export function rewardConfirmation(root,action,current){
  const runtime=root.session.runtime_instance_id;
  if(!rewardProceed(root,action)||root.interaction.content.surface.proceed_skips_remaining_rewards!==true
    ||!root.interaction.content.surface.rewards?.length||!completePublicMenu(current,runtime)
    ||current.interaction.kind!=='reward_claim'
    ||current.interaction.interaction_id!==root.interaction.interaction_id
    ||!same(current.persistent,root.persistent)||!same(current.interaction.content,root.interaction.content)
    ||!same(current.referents,root.referents)||!same(current.bound_actions,root.bound_actions))
    throw Error('Reward warning returned to a changed owner, state or menu; no confirmation');
  const exact=current.bound_actions.actions.filter(a=>same(a,action));
  if(exact.length!==1)throw Error('No exact current reward confirmation');
  return exact[0];
}
export function verifyRewardCommitTrace(root,action,receipt,steps,successor){
  const runtime=root.session.runtime_instance_id;
  received(root,action,receipt,runtime);
  if(!Array.isArray(steps)||steps.length>4)throw Error('Reward UI step cap');
  let warning=false,confirmed=false;
  for(const step of steps){
    received(step.snapshot,step.action,step.receipt,runtime);
    if(step.kind==='tutorial'){
      const expected=naturalTutorialAction(step.snapshot);
      if(expected.verb!=='activate'||expected.subject_referent_id!=null||expected.arguments.length
        ||!same(expected,step.action))throw Error('Reward guidance must be a non-gameplay dismissal');
      if(step.snapshot.interaction.content.surface.tutorial_id===WARNING){
        if(warning||confirmed)throw Error('Repeated reward warning; preserve without retry');
        warning=true;
      }
    }else if(step.kind==='confirmation'){
      if(!warning||confirmed||!same(rewardConfirmation(root,action,step.snapshot),step.action))
        throw Error('Reward confirmation lacks its exact preceding warning');
      confirmed=true;
    }else throw Error('Unknown reward UI operation');
  }
  if(['tutorial','reward_claim','no_action'].includes(successor.interaction?.kind))
    throw Error('Reward presentation is not verified owner departure');
  return {...prior(root,action,receipt,successor),semantic_contract:'reward_proceed_with_guidance_v1',
    initial_receipt:receipt,ui_steps:steps};
}
export async function finishRewardProceed(root,action,receipt,initial,
  {observe,send,deadline,now=Date.now,onTutorial=()=>{}}){
  const runtime=root.session.runtime_instance_id,steps=[];
  received(root,action,receipt,runtime);
  let current=initial,warning=false,confirmed=false;
  while(now()<deadline){
    if(current.session?.runtime_instance_id!==runtime)throw Error('Changed reward runtime');
    if(current.interaction.kind==='tutorial'){
      if(steps.length>=4)throw Error('Reward UI step cap');
      const dismiss=naturalTutorialAction(current),id=current.interaction.content.surface.tutorial_id;
      if(dismiss.verb!=='activate'||dismiss.subject_referent_id!=null||dismiss.arguments.length)
        throw Error('Reward tutorial attempted gameplay');
      if(id===WARNING){
        if(warning||confirmed)throw Error('Repeated reward warning; no retry');
        warning=true;
      }
      const acknowledged=await send(current,dismiss,'tutorial');
      received(current,dismiss,acknowledged,runtime);
      steps.push({kind:'tutorial',snapshot:current,action:dismiss,receipt:acknowledged});onTutorial();
    }else if(current.interaction.kind==='reward_claim'){
      if(warning&&!confirmed){
        if(steps.length>=4)throw Error('Reward UI step cap');
        const confirm=rewardConfirmation(root,action,current);
        const committed=await send(current,confirm,'confirmation');
        received(current,confirm,committed,runtime);
        steps.push({kind:'confirmation',snapshot:current,action:confirm,receipt:committed});confirmed=true;
      }
      // Without that exact warning, observe only. Never repeat a pending input.
    }else return {successor:current,proof:verifyRewardCommitTrace(root,action,receipt,steps,current)};
    current=await observe(current.snapshot_id,deadline);
  }
  throw Error('Reward completion cap; preserve uncertain delivery without retry');
}
