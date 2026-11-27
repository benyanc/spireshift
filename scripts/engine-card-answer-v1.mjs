// One native card-answer domain for direct actions and local answer construction.
import { ATOMIC_SELECTION, orderedChoices } from "./engine-atomic-selection-v6.mjs";
import { PLAN, largeDomain } from "./engine-ordered-plan-v1.mjs";
import { validSelection } from "./engine-selection-cursor-v1.mjs";

export { ATOMIC_SELECTION, PLAN };
const owners = new Set(["event", "rest", "shop", "combat", "treasure"]);

export function selectorFormat(interaction) {
  const surface = interaction?.content?.surface;
  if (interaction?.kind !== "card_selection") return null;
  if (surface?.kind !== "card_selection") return null;
  const format = surface.selection_contract;
  if (format === ATOMIC_SELECTION) {
    if (Object.hasOwn(surface, "answer_plan")) throw Error("Direct selector has an ordered answer prefix");
    return format;
  }
  if (format !== PLAN) return null;
  const plan = surface.answer_plan, count = surface.cards?.length;
  if (plan?.contract !== PLAN || plan.native_commits_only_at_answer_completion !== true
      || !Array.isArray(surface.cards) || !Number.isSafeInteger(surface.min_select)
      || !Number.isSafeInteger(surface.max_select) || surface.min_select < 0 || surface.min_select > count
      || surface.max_select < surface.min_select || typeof surface.cancelable !== "boolean")
    throw Error("Incomplete public ordered answer plan");
  answerControls({count, min: surface.min_select, max: Math.min(count, surface.max_select),
    cancelable: surface.cancelable}, plan.selected);
  return format;
}

export function cardAnswerDomain(state) {
  if (!validSelection(state) || !owners.has(state.selection_owner?.kind)
      || state.cards.some(card => typeof card.native_ref !== "string" || !card.native_ref
        || typeof card.upgraded !== "boolean")
      || new Set(state.cards.map(card => card.native_ref)).size !== state.cards.length)
    throw Error("Incomplete exact native selection source");
  return {ref: state.selection_ref, count: state.cards.length, min: state.min_select,
    max: Math.min(state.max_select, state.cards.length), cancelable: state.cancelable};
}

export function needsAnswerPlan(domain) {
  return largeDomain(domain.count, domain.min, domain.max, domain.cancelable);
}

export function directAnswers(domain, limit) {
  return orderedChoices(Array.from({length: domain.count}, (_, i) => i),
    domain.min, domain.max, domain.cancelable, limit);
}

export function answerControls(domain, prefix) {
  if (!Array.isArray(prefix) || new Set(prefix).size !== prefix.length
      || prefix.length > domain.max || prefix.some(i => !Number.isSafeInteger(i) || i < 0 || i >= domain.count))
    throw Error("Invalid public ordered answer prefix");
  return {
    append: prefix.length < domain.max
      ? Array.from({length: domain.count}, (_, i) => i).filter(i => !prefix.includes(i)) : [],
    confirm: prefix.length >= domain.min,
    cancel: domain.cancelable,
  };
}

export function nativeAnswer(domain, prefix, cancel = false) {
  const controls = answerControls(domain, prefix);
  if (cancel && controls.cancel)
    return {cmd: "action", action: "skip_select", args: {selection_ref: domain.ref}};
  if (!cancel && controls.confirm)
    return {cmd: "action", action: "select_cards", args: {selection_ref: domain.ref, indices: prefix.join(",")}};
  throw Error("Unadvertised native answer completion");
}

export class CardAnswerPlanner {
  constructor() { this.active = null; }

  observe(state) {
    if (state?.type !== "decision") return state;
    if (state.decision !== "card_select" || state.generated_choice_presentation != null) {
      this.active = null;
      return state;
    }
    const domain = cardAnswerDomain(state);
    if (!needsAnswerPlan(domain)) {
      this.active = null;
      return state;
    }
    if (this.active) {
      if (JSON.stringify(this.active.state) !== JSON.stringify(state))
        throw Error("Native selection changed during answer planning");
    } else {
      this.active = {state: structuredClone(state), domain, selected: []};
    }
    return this.view();
  }

  view() {
    const {state, selected} = this.active;
    return {...state, answer_plan: {contract: PLAN, selected: [...selected]}};
  }

  handle(request) {
    if (request.cmd !== "action") return null;
    if (!String(request.action).startsWith("ordered_answer_")) {
      if (this.active?.selected.length) throw Error("Cannot interleave native actions with an unfinished answer");
      this.active = null;
      return null;
    }
    if (!this.active) throw Error("No pending ordered answer");
    const {domain, selected} = this.active, args = request.args ?? {};
    if (args.selection_ref !== domain.ref || args.prefix !== selected.join(","))
      throw Error("Stale ordered answer owner or prefix");
    const before = [...selected];
    if (request.action === "ordered_answer_append") {
      if (!answerControls(domain, selected).append.includes(args.index))
        throw Error("Invalid ordered answer append");
      selected.push(args.index);
      return {local: true, response: this.view(), before, after: [...selected]};
    }
    if (!["ordered_answer_commit", "ordered_answer_cancel"].includes(request.action))
      throw Error("Unadvertised ordered answer completion");
    const native = nativeAnswer(domain, selected, request.action === "ordered_answer_cancel");
    this.active = null;
    return {local: false, native, before, after: []};
  }
}
