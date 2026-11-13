// A changed snapshot/signature does not mean a reward panel has departed.
// Its button may disable/re-enable while the same pending rewards still close.
import {rewardProceed, verifyRewardDeparture as previous} from './engine-reward-commit-v1.mjs';
export {rewardProceed};
export function rewardOwnerDeparted(root, successor) {
  return successor?.session?.runtime_instance_id === root.session.runtime_instance_id
    && successor.interaction?.kind !== 'reward_claim'
    && successor.interaction?.interaction_id !== root.interaction.interaction_id;
}
export function verifyRewardDeparture(root, action, receipt, successor) {
  if (!rewardOwnerDeparted(root, successor))
    throw Error('Reward owner is still mounted; wait without another model choice or input');
  return previous(root, action, receipt, successor);
}
