// Remove the exact observed gold-colour markup, preserving all text, values and order.
export const renderedRewardText = (value) => typeof value === "string"
  ? value.replace(/\[\/?gold\]/giu, "") : value;
export function renderNativeRewardState(state) {
  if (state.decision !== "reward_set" || !Array.isArray(state.rewards)) return state;
  return {...state,rewards:state.rewards.map(row=>({...row,description:renderedRewardText(row.description)}))};
}
