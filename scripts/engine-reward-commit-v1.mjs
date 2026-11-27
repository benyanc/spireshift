import {completePublicMenu} from './engine-menu-probe.mjs';
export function rewardProceed(snapshot,action){
 return snapshot.interaction.kind==='reward_claim'&&snapshot.interaction.content.surface.can_proceed===true
  &&action.subject_referent_id==null&&action.arguments.length===0
  &&action.verb==='activate'&&['Proceed','Skip remaining rewards and continue','Continue from rewards'].includes(action.label);
}
export function verifyRewardDeparture(root,action,receipt,successor){
 const runtime=root.session.runtime_instance_id;
 if(!rewardProceed(root,action)||!root.bound_actions.actions.some(a=>a.bound_action_id===action.bound_action_id)
  ||receipt.delivery!=='delivered'||receipt.action?.bound_action_id!==action.bound_action_id
  ||receipt.attribution?.runtime_instance_id!==runtime||successor.session.runtime_instance_id!==runtime
  ||successor.snapshot_id===root.snapshot_id||successor.interaction.interaction_id===root.interaction.interaction_id
  ||!(completePublicMenu(successor,runtime)||successor.interaction.kind==='game_over'&&successor.completeness.status==='complete'))
  throw Error('Reward Continue has no verified owner departure; no retry');
 return {root_snapshot_id:root.snapshot_id,root_bound_action_id:action.bound_action_id,successor_snapshot:successor};
}
