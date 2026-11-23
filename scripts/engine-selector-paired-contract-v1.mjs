// Authenticated transport evidence. These fields never reach policy inputs.
export function requireLocalAnswerFactor(body, before, action, after, request, runtime) {
  const proof = body?.selection, surface = before.interaction.content.surface;
  const next = after.interaction.content.surface;
  const index = surface.cards.findIndex(card => card.entity_id === action.subject_referent_id);
  const prefix = surface.answer_plan.selected;
  const expected = [...prefix,index];
  if (index < 0 || prefix.includes(index) || prefix.length >= surface.max_select
      || before.snapshot_id === after.snapshot_id || before.interaction.interaction_id !== after.interaction.interaction_id
      || body.runtime_instance_id !== runtime || proof?.request_id !== request
      || proof.root_snapshot_id !== before.snapshot_id || proof.status !== "local_answer_factor"
      || proof.game_committed !== false || !Array.isArray(proof.steps) || proof.steps.length !== 0
      || !Array.isArray(proof.native_selected_card_ids) || proof.native_selected_card_ids.length !== 0
      || proof.appended_card_id !== action.subject_referent_id
      || JSON.stringify(proof.before) !== JSON.stringify(prefix)
      || JSON.stringify(proof.after) !== JSON.stringify(expected)
      || JSON.stringify(next.answer_plan?.selected) !== JSON.stringify(expected))
    throw Error("Unverified local answer factor; preserve without retry");
  return proof;
}
