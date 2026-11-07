// A bounded UI for large native subsets. Only final Confirm/Cancel reaches the game.
// Ordered prefixes represent every native subset and ordering without enumerating them.
import { projectRunSurface as previous } from "./engine-run-contract-v5.mjs";
export const SELECTION_PROTOCOL = "public_ordered_card_subset_cursor_v1";
export const ACTION_LIMIT = 512;

export function exceedsLimit(n, min, max, cancelable, limit = ACTION_LIMIT) {
  let combinations = 1, total = cancelable ? 1 : 0;
  for (let k = 0; k <= Math.min(max, n); k++) {
    if (k >= min) total += combinations;
    if (total > limit) return true;
    combinations = combinations * (n - k) / (k + 1);
  }
  return false;
}
export function validSelection(s) {
  return s?.decision === "card_select" && Array.isArray(s.cards)
    && s.cards.every((c, i) => c.index === i)
    && Number.isSafeInteger(s.min_select) && Number.isSafeInteger(s.max_select)
    && s.min_select >= 0 && s.max_select >= s.min_select && s.min_select <= s.cards.length
    && typeof s.cancelable === "boolean" && typeof s.require_manual_confirmation === "boolean"
    && typeof s.unpowered_previews === "boolean" && typeof s.pretend_cards_can_be_played === "boolean"
    && s.selection_preferences_complete === true && typeof s.selection_ref === "string" && !!s.selection_ref;
}
export function additions(s, selected) {
  return selected.length >= s.max_select ? [] : s.cards.map(c => c.index).filter(i =>
    !selected.includes(i) && selected.length + s.cards.length - selected.length >= s.min_select);
}
export class SelectionCursor {
  constructor() { this.active = null; }
  observe(state) {
    if (state?.type !== "decision") return state;
    if (!validSelection(state) || !exceedsLimit(state.cards.length, state.min_select, state.max_select, state.cancelable)) {
      this.active = null; return state;
    }
    if (this.active?.state.selection_ref === state.selection_ref) {
      const prior = this.active.state;
      if (JSON.stringify(prior) !== JSON.stringify(state)) throw Error("Native selection changed under an uncommitted UI prefix");
    } else this.active = { state, selected: [] };
    return this.view();
  }
  view() {
    if (!this.active) throw Error("No large native selection is pending");
    return { ...this.active.state, selection_ui: { protocol: SELECTION_PROTOCOL, selected: [...this.active.selected] } };
  }
  handle(request) {
    if (request.cmd !== "action" || !String(request.action).startsWith("selection_cursor_")) return null;
    if (!this.active) throw Error("No pending selection cursor");
    const { state, selected } = this.active, args = request.args ?? {};
    if (args.selection_ref !== state.selection_ref || args.prefix !== selected.join(","))
      throw Error("Stale selection cursor or prefix");
    const before = [...selected];
    if (request.action === "selection_cursor_add") {
      if (!additions(state, selected).includes(args.index)) throw Error("Unadvertised card-prefix addition");
      selected.push(args.index);
      return { local: true, response: this.view(), before, after: [...selected] };
    }
    let native;
    if (request.action === "selection_cursor_confirm") {
      if (selected.length < state.min_select || new Set(selected).size !== selected.length || selected.length > state.max_select) throw Error("Native selection count not satisfied");
      native = { cmd: "action", action: "select_cards", args: { selection_ref: state.selection_ref, indices: selected.join(",") } };
    } else if (request.action === "selection_cursor_cancel" && state.cancelable) {
      native = { cmd: "action", action: "skip_select", args: { selection_ref: state.selection_ref } };
    } else throw Error("Unadvertised cursor confirmation/cancellation");
    this.active = null;
    return { local: false, native, before, after: [] };
  }
}
export function projectSelectionSurface(state, ctx, helpers) {
  if (!state.selection_ui) return previous(state, ctx, helpers);
  if (!validSelection(state) || state.selection_ui.protocol !== SELECTION_PROTOCOL)
    throw Error("Malformed native selection UI");
  const selected = state.selection_ui.selected;
  if (!Array.isArray(selected) || selected.some((x, i) => !Number.isSafeInteger(x) || x < 0 || x >= state.cards.length)
      || new Set(selected).size !== selected.length || selected.length > state.max_select) throw Error("Malformed selected prefix");
  const refs = state.cards.map((c, i) => ctx.referent({ role: "card", occurrence: i,
    label: c.name ?? `Card ${i+1}`, properties: { index: i, ...helpers.cardProperties(c), selected: selected.includes(i), selection_order: selected.includes(i) ? selected.indexOf(i) : null } }));
  const raw = action => ({ cmd: "action", action, args: { selection_ref: state.selection_ref, prefix: selected.join(",") } });
  for (const i of additions(state, selected)) ctx.action({ verb: "select", subject: refs[i], label: `Add ${refs[i].label}`,
    raw: { ...raw("selection_cursor_add"), args: { ...raw("selection_cursor_add").args, index: i } } });
  if (selected.length >= state.min_select) ctx.action({ verb: "confirm",
    arguments: selected.map(i => ({ role: "selected_card", referent: refs[i] })),
    label: selected.length ? "Confirm selected cards" : "Confirm empty selection", raw: raw("selection_cursor_confirm") });
  if (state.cancelable) ctx.action({ verb: "cancel", label: "Cancel selection", raw: raw("selection_cursor_cancel") });
  return { kind: "card_selection", stage: "choosing", prompt: helpers.visibleText(state.prompt),
    surface: { kind: "card_selection", stage: "choosing", cards: refs.map(r => r.properties), min_select: state.min_select,
      max_select: state.max_select, cancelable: state.cancelable, require_manual_confirmation: state.require_manual_confirmation,
      unpowered_previews: state.unpowered_previews, pretend_cards_can_be_played: state.pretend_cards_can_be_played },
    context: { kind: "selection", run: state.context ?? null, player: helpers.withoutDeck(state.player) },
    complete: true, missing: [], visibleInformation: SELECTION_PROTOCOL,
    interactionDiscovery: "native_bounds_with_local_public_subset_prefix_and_explicit_commit" };
}
