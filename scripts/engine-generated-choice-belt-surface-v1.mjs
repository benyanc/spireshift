// Native generated choices can nest combat context while the belt remains visible.
import {projectSelectionFlows as previous, selectionFlowReads} from "./engine-ordered-plan-surface-v1.mjs";
import {cardFacts, contextReference} from "./engine-atomic-selection-v6.mjs";
import {projectExactCombatSurface} from "./engine-combat-surface-v6.mjs";
import {appendPotionControls} from "./engine-potion-surface-v1.mjs";
import {ownedBeltContext} from "./engine-relic-surface-v3.mjs";

export {selectionFlowReads};

const identity = value => typeof value === "string" && value.length > 0;

export function projectSelectionFlows(state, ctx, helpers) {
  if (state.decision !== "generated_card_choice" || !state.selection_combat)
    return previous(state, ctx, helpers);

  if (state.generated_choice_presentation !== "native_choose_card_initial_v1"
      || typeof state.can_skip !== "boolean" || state.generated_choice_is_peeking !== false
      || !identity(state.generated_choice_prompt) || !identity(state.selection_ref)
      || !state.selection_owner || !Array.isArray(state.cards) || !state.cards.length
      || state.cards.length > 3 || state.min_select !== (state.can_skip ? 0 : 1)
      || state.max_select !== 1)
    throw Error("Incomplete exact generated choice source");

  const views = {...helpers, cardProperties(card) {
    return {...helpers.cardProperties(card),
      ...(card.star_cost == null ? {} : {star_cost: String(card.star_cost)})};
  }};
  const contextRefs = [];
  const observed = projectExactCombatSurface(state.selection_combat, {...ctx,
    action() {},
    referent(value) {
      contextRefs.push(value);
      return contextReference(value);
    }
  }, views);
  if (observed.missing.some(fact => fact !== "native_local_player_play_phase"))
    throw Error("Incomplete generated-choice combat context");

  const cards = state.cards.map((card, index) => {
    if (card.index !== index || card.is_selected !== false)
      throw Error("Generated card order or initial selection changed");
    const props = cardFacts(state, card, ctx, views);
    const ref = ctx.referent({
      role: "card", id: props.entity_id, label: props.name, selected: false, properties: props
    });
    ctx.action({verb: "select", subject: ref, label: `Choose ${ref.label}`,
      raw: {cmd: "action", action: "select_cards",
        args: {selection_ref: state.selection_ref, indices: String(index)}}});
    return ref.properties;
  });
  const cardIds = new Set(cards.map(card => card.entity_id));
  const belt = state.player?.potions ?? [];
  const beltIds = new Set(belt.map((potion, index) => ctx.id("potion", ctx.snapshotId, potion.native_ref, index)));
  const needsPlayer = belt.some(potion => potion.can_use && potion.target_type === "AnyPlayer");
  const playerId = ctx.id("player", ctx.snapshotId, state.player?.native_ref);
  for (const value of contextRefs) {
    // Keep the sparse combat view. The active belt owns the actual referents.
    const beltOwns = ["potion", "usable_potion"].includes(value.role) && beltIds.has(value.id)
      || needsPlayer && value.role === "player" && value.id === playerId;
    if (!cardIds.has(value.id) && !beltOwns)
      ctx.referent({...value, ...(value.role === "playable_card" ? {role: "hand", selected: false} : {})});
  }
  if (state.can_skip) ctx.action({verb: "skip", label: "Skip",
    raw: {cmd: "action", action: "skip_select", args: {selection_ref: state.selection_ref}}});
  return appendPotionControls(state, ownedBeltContext(state, ctx), views, {
    kind: "native_generated_card_choice", stage: "choosing", prompt: state.generated_choice_prompt,
    context: observed.context,
    surface: {kind: "native_generated_card_choice", stage: "choosing", prompt: state.generated_choice_prompt,
      cards, selectable_card_entity_ids: cards.map(card => card.entity_id),
      can_skip: state.can_skip, is_peeking: state.generated_choice_is_peeking},
    complete: true, missing: [],
    visibleInformation: "native_initial_generated_choice_with_exact_owner_card_views_and_canSkip",
    interactionDiscovery: "native_FromChooseACardScreen_committed_choice"
  });
}
