// Shared public diagnostic policy. Optional declines are ordinary choices, never fabricated.
import { createHash } from "node:crypto";
import { assertPublicBoundary } from "./engine-run-contract-v1.mjs";

const cardChoices = new Set(["card_reward_selection", "native_generated_card_choice"]);
const selections = new Set(["card_selection", "native_deck_card_selection", "combat_hand_card_selection"]);
const shops = new Set(["shop_inventory", "merchant_room"]);
const volatile = new Set(["entity_id", "referent_id", "bound_action_id", "interaction_id", "snapshot_id"]);
const canonical = value => Array.isArray(value) ? value.map(canonical)
  : value && typeof value === "object" ? Object.fromEntries(Object.entries(value)
    .filter(([key]) => !volatile.has(key)).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)
    .map(([key, item]) => [key, canonical(item)])) : value;
const text = value => String(value ?? "").trim().replace(/\s+/gu, " ").toLowerCase();
const referent = (snapshot, id) => (snapshot.referents ?? []).find(row => row.referent_id === id);

export function actionSemantics(snapshot, action) {
  const kind = snapshot.interaction.kind, item = referent(snapshot, action.subject_referent_id);
  const label = text(action.label), role = item?.role;
  // The SDK represents Skip as activate on an alternative option; the native projection uses skip.
  const explicitSkip = action.verb === "skip" || (action.verb === "activate"
    && (item == null || role === "option") && /^skip(?:$| (?:card|reward|choice|all)\b)/u.test(label));
  if (explicitSkip) return cardChoices.has(kind) ? "skip_card" : "skip_optional";
  if (cardChoices.has(kind) && action.verb === "select" && role === "card") return "take_card";
  if (shops.has(kind) && (action.verb === "close" || (action.verb === "activate"
    && /^(?:leave shop|close inventory|back)$/u.test(label)))) return "leave_shop";
  if (shops.has(kind) && action.verb === "activate" && /^(?:buy|purchase)\b/u.test(label)) return "buy";
  if (action.verb === "activate" && /^(?:proceed|continue)$/u.test(label)) return "proceed";
  if (action.verb === "activate" && /^(?:confirm|confirm selected cards)$/u.test(label)) return "confirm";
  return action.verb;
}

export function publicActionKey(snapshot, action) {
  const semantic = actionSemantics(snapshot, action);
  const subject = referent(snapshot, action.subject_referent_id);
  const controlOnly = ["skip_card", "skip_optional", "leave_shop", "proceed", "confirm", "cancel", "close"].includes(semantic);
  const properties = canonical(subject?.properties ?? {});
  if (properties.cost != null) properties.cost = String(properties.cost);
  // Named public amounts/modifiers remain distinct. Opaque runtime IDs never break preference ties.
  return JSON.stringify(canonical({ semantic,
    label: controlOnly ? semantic : text(action.label).replace(/^(?:take|select|buy|purchase) /u, ""),
    subject: controlOnly ? null : { role: subject?.role ?? null, properties },
    arguments: (action.arguments ?? []).map(arg => ({ role: arg.role, name: arg.name,
      properties: canonical(referent(snapshot, arg.referent_id)?.properties ?? {}) })) }));
}

export function diagnosticScore(snapshot, action) {
  const semantic = actionSemantics(snapshot, action), kind = snapshot.interaction.kind;
  const props = referent(snapshot, action.subject_referent_id)?.properties ?? {};
  const player = snapshot.persistent?.content?.player ?? {};
  if (kind === "combat_turn") {
    if (semantic === "play") return 100 + (Number(props.stats?.damage) || 0) + (Number(props.stats?.block) || 0);
    if (semantic === "use") return 80;
    return semantic === "end_turn" ? 10 : -10;
  }
  if (kind === "rest_site") {
    if (semantic === "close" || semantic === "proceed") return 0;
    return /heal|rest/iu.test(action.label) ? (player.hp < player.max_hp * 0.7 ? 100 : 10) : 50;
  }
  if (selections.has(kind)) return semantic === "confirm" ? 100 : semantic === "cancel" ? 0 : 50;
  // There is no automatic reward for taking a card or spending gold. A future scorer can rank
  // any legal action, including Skip/leave, above the alternatives using the full public state.
  if (cardChoices.has(kind) || shops.has(kind)) return 50;
  if (semantic === "cancel") return 0;
  if (["proceed", "close"].includes(semantic)) return 0;
  return 50;
}

export function chooseRunAction(snapshot, scoreAction = diagnosticScore) {
  assertPublicBoundary(snapshot);
  const actions = snapshot.bound_actions?.actions;
  if (!actions?.length) throw Error("Diagnostic policy has no legal action");
  const ranked = actions.map(action => {
    const score = scoreAction(snapshot, action), key = publicActionKey(snapshot, action);
    if (!Number.isFinite(score)) throw Error("Action score must be finite");
    return { action, score, key, tie: createHash("sha256").update(key).digest("hex") };
  });
  ranked.sort((a, b) => b.score - a.score || (a.tie < b.tie ? -1 : a.tie > b.tie ? 1 : 0));
  // Truly indistinguishable copies share a preference, but the returned native binding stays intact.
  return ranked[0].action;
}
