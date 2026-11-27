// Shared public card selector projection. Only the action representation varies.
import { cardFacts, contextReference } from "./engine-atomic-selection-v6.mjs";
import { projectExactCombatSurface } from "./engine-combat-surface-v6.mjs";
import { appendPotionControls } from "./engine-potion-surface-v1.mjs";
import { ownedBeltContext } from "./engine-relic-surface-v3.mjs";
import { ATOMIC_SELECTION, PLAN, answerControls, cardAnswerDomain, directAnswers,
  nativeAnswer } from "./engine-card-answer-v1.mjs";

function enchantmentPreview(value) {
  if (value == null) return {};
  if (typeof value !== "object" || Array.isArray(value) || typeof value.definition_id !== "string"
      || !value.definition_id || typeof value.name !== "string" || typeof value.description !== "string"
      || !Number.isSafeInteger(value.amount) || value.observation_source !== "native_command_enchantment_and_amount")
    throw Error("Incomplete exact native enchantment preview");
  return {enchantment: structuredClone(value)};
}

export function projectCardSelector(state, ctx, helpers) {
  const domain = cardAnswerDomain(state), plan = state.answer_plan;
  if (plan && plan.contract !== PLAN) throw Error("Unknown ordered answer contract");
  const selected = plan ? plan.selected : [];
  const controls = answerControls(domain, selected);
  const views = {...helpers, cardProperties(card) {
    return {...helpers.cardProperties(card),
      ...(card.star_cost == null ? {} : {star_cost: String(card.star_cost)})};
  }};
  let context = {...state.selection_owner, run: state.context, player: views.withoutDeck(state.player)};
  const contextRefs = [];
  if (state.selection_combat) {
    const observed = projectExactCombatSurface(state.selection_combat, {...ctx, action() {},
      referent(value) { contextRefs.push(value); return contextReference(value); }}, views);
    if (observed.missing.some(fact => fact !== "native_local_player_play_phase"))
      throw Error(`Incomplete selected combat observation: ${observed.missing}`);
    context = observed.context;
  }
  const refs = state.cards.map(card => {
    const props = cardFacts(state, card, ctx, views);
    return ctx.referent({role: "card", id: props.entity_id, label: props.name, selected: false, properties: props});
  });
  const cardIds = new Set(refs.map(ref => ref.properties.entity_id));
  const belt = state.player?.potions ?? [];
  const beltIds = new Set(belt.map((potion, i) => ctx.id("potion", ctx.snapshotId, potion.native_ref, i)));
  const needsPlayer = belt.some(potion => potion.can_use && potion.target_type === "AnyPlayer");
  const beltWillDeclare = ref => selected.length === 0 && (
    ["potion", "usable_potion"].includes(ref.role) && beltIds.has(ref.id)
    || needsPlayer && ref.role === "player" && ref.id === ctx.id("player", ctx.snapshotId, state.player.native_ref));
  for (const ref of contextRefs)
    if (!cardIds.has(ref.id) && !beltWillDeclare(ref))
      ctx.referent({...ref, ...(ref.role === "playable_card" ? {role: "hand", selected: false} : {})});

  const operands = indices => indices.map(i => ({role: "selected_card", referent: refs[i]}));
  const names = indices => indices.map(i => refs[i].label).join(", ");
  if (plan) {
    const args = {selection_ref: domain.ref, prefix: selected.join(",")};
    for (const index of controls.append) ctx.action({verb: "select", subject: refs[index],
      label: "Append " + refs[index].label, raw: {cmd: "action", action: "ordered_answer_append", args: {...args, index}}});
    if (controls.confirm) ctx.action({verb: "confirm", arguments: operands(selected),
      label: selected.length ? "Commit ordered answer: " + names(selected) : "Commit empty answer",
      raw: {cmd: "action", action: "ordered_answer_commit", args}});
    if (controls.cancel) ctx.action({verb: "cancel", label: "Cancel selection",
      raw: {cmd: "action", action: "ordered_answer_cancel", args}});
  } else {
    for (const indices of directAnswers(domain)) ctx.action({verb: "confirm", arguments: operands(indices),
      label: indices.length ? "Confirm " + names(indices) : "Confirm empty selection",
      raw: nativeAnswer(domain, indices)});
    if (controls.cancel) ctx.action({verb: "cancel", label: "Cancel selection", raw: nativeAnswer(domain, [], true)});
  }
  const format = plan ? PLAN : ATOMIC_SELECTION;
  const result = {kind: "card_selection", stage: "choosing", prompt: views.visibleText(state.prompt), context,
    surface: {kind: "card_selection", stage: "choosing", cards: refs.map(ref => ref.properties),
      min_select: state.min_select, max_select: state.max_select, cancelable: domain.cancelable,
      require_manual_confirmation: state.require_manual_confirmation, unpowered_previews: state.unpowered_previews,
      pretend_cards_can_be_played: state.pretend_cards_can_be_played, selection_contract: format,
      ...(plan ? {answer_plan: {contract: PLAN, selected: [...selected], native_commits_only_at_answer_completion: true}} : {}),
      ...enchantmentPreview(state.enchantment)},
    complete: true, missing: [], visibleInformation: format,
    interactionDiscovery: plan ? "compact_ordered_answer_grammar_without_native_prefix_actions"
      : "native_exact_preferences_and_committed_ordered_card_answer"};
  return selected.length === 0 ? appendPotionControls(state, ownedBeltContext(state, ctx), views, result) : result;
}
