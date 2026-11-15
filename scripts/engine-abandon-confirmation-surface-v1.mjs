import {projectSelectionFlows as previous, selectionFlowReads} from "./engine-generated-choice-belt-surface-v1.mjs";
export {selectionFlowReads};

const choices = ["confirm", "cancel"];

export function projectSelectionFlows(state, ctx, helpers) {
  if (!Object.hasOwn(state, "abandon_confirmation_ref")) return previous(state, ctx, helpers);
  if (state.decision !== "event_choice" || state.event_id !== "ABANDON_RUN_CONFIRMATION"
      || !/^abandon-[1-9][0-9]*$/u.test(state.abandon_confirmation_ref)
      || !Array.isArray(state.options) || state.options.length !== choices.length
      || state.options.some((option, index) => option.index !== index
        || option.text_key !== "GENERIC_POPUP." + choices[index]
        || option.is_locked !== false || option.will_kill_player !== (index === 0)))
    throw Error("Incomplete native abandon confirmation");

  // Reuse the SDK's public event-option surface. Modal ownership keeps the
  // underlying event and potion controls unavailable until the popup closes.
  return helpers.defaultProjector(state, {...ctx, action(action) {
    const index = action.raw?.args?.option_index;
    if (action.raw?.action !== "choose_option" || !choices[index])
      throw Error("Unbound abandon confirmation action");
    ctx.action({...action, verb: choices[index], raw: {
      cmd: "action", action: "resolve_abandon_confirmation",
      args: {confirmation_ref: state.abandon_confirmation_ref, confirm: index === 0},
    }});
  }});
}
