// Bounds for a complete executable answer, rather than just stored preferences.
import {CardAnswerPlanner} from "./engine-card-answer-v1.mjs";

export function executableSelection(state) {
  if (state?.decision !== "card_select" || state.enchantment == null
      || state.generated_choice_presentation != null) return state;
  if (state.enchantment.observation_source !== "native_command_enchantment_and_amount"
      || state.selection_preferences_complete !== true || !Number.isSafeInteger(state.min_select)
      || state.min_select < 0 || !Array.isArray(state.cards) || state.cards.length === 0
      || state.max_select < 1)
    throw Error("Missing qualified native enchant completion facts");
  // NDeckEnchantSelectScreen.ConfirmSelection has a nonempty guard before
  // the stored min/max check. Its empty preview therefore cannot complete.
  return {...state,min_select:Math.max(1,state.min_select)};
}

export class ExecutableCardAnswerPlanner extends CardAnswerPlanner {
  observe(state) { return super.observe(executableSelection(state)); }
}
