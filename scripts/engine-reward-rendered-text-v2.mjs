// Exact observed colour tags and the A8 Ironclad energy glyph, as exposed by the shipped Host.
// Preserve every word/value/order and every glyph occurrence. Unknown markup remains a difference.
const energyIcon="res://images/packed/sprite_fonts/ironclad_energy_icon.png";
export const renderedRewardText = (value) => typeof value === "string"
  ? value.replace(/\[\/?(?:gold|blue|green)\]/giu, "")
    .replaceAll(`[img]${energyIcon}[/img]`,"[ironclad_energy_icon.png]") : value;
export function renderNativeRewardState(state) {
  if (state.decision !== "reward_set" || !Array.isArray(state.rewards)) return state;
  return {...state,rewards:state.rewards.map(row=>({...row,description:renderedRewardText(row.description)}))};
}
