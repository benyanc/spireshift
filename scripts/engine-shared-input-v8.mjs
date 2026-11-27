// Versioned scoped-view conversion. Preserves the previous converter and all frozen results.
import { createHash } from "node:crypto";
import { createInterface } from "node:readline";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { completePublicMenu } from "./engine-menu-probe.mjs";
import { assertPublicBoundary } from "./engine-run-contract-v1.mjs";
import { publicPolicyInput, stableJson } from "./engine-public-input-v1.mjs";
import { newDiagnosticNavigation } from "./engine-run-policy-v7.mjs";
import { scopedCardSelections, recordInterfaceNavigation } from "./engine-interface-scopes-v2.mjs";
import { shippedEnding } from "./engine-natural-shipped-contract-v1.mjs";
export { recordInterfaceNavigation } from "./engine-interface-scopes-v2.mjs";

import { normalizeLayout, LAYOUT } from "./engine-input-layout-v5.mjs";

export const CONTRACT = "official_cli_shared_public_graph_v1";
const families = new Set(["event_option", "map_navigation", "combat_turn", "rest_site",
  "shop_inventory", "card_selection", "card_bundle_selection", "reward_claim", "card_reward_selection",
  "reward_completion", "treasure_chest", "treasure_relic_selection", "treasure_completion",
  "native_generated_card_choice", "game_over", "shop_room", "treasure_room", "event_dialogue"]);
// Exact names from the pinned official ReaderRegistrations/NativeUi catalog.
// The selected cards, purpose prompt, bounds, cancel/confirm/preview controls and
// original owner context remain in the input. This is naming, not action synthesis.
const selectionAliases = new Set(["native_deck_card_selection", "native_simple_card_selection",
  "native_combat_pile_selection", "combat_hand_card_selection", "deck_upgrade_selection",
  "deck_transform_selection", "deck_enchant_selection"]);
// These describe transport/projection provenance, not game facts. Validate freshness
// and completeness before removal. Unknown fields, including numeric previews, stay.
const transport = new Set(["content_schema", "properties_schema", "observation_basis", "stat_basis"]);
const opaque = /(?:entity|referent)_ids?$/u;
const digest = value => createHash("sha256").update(stableJson(value)).digest("hex");
const compare = (a, b) => a < b ? -1 : a > b ? 1 : 0;

function clean(value) {
  if (Array.isArray(value)) return value.map(clean);
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value)
    .filter(([key]) => !transport.has(key)).map(([key, item]) => [key, clean(item)]));
  if (typeof value === "number" && !Number.isFinite(value)) throw Error("Nonfinite public fact");
  if (value === undefined) throw Error("Undefined public fact");
  return value;
}
const withoutHandles = value => Array.isArray(value) ? value.map(withoutHandles)
  : value && typeof value === "object" ? Object.fromEntries(Object.entries(value)
    .filter(([key]) => !opaque.test(key)).map(([key, item]) => [key, withoutHandles(item)])) : value;

function orderedReads(reads, snapshot) {
  // Detail endpoints are an unordered set of current card views. Order them by
  // visible facts, then by their existing place in the owned surface for copies
  // with equal facts. Never use opaque runtime handles as a sorting key.
  const cards = snapshot.interaction?.content?.surface?.cards ?? [];
  const location = read => {
    const index = cards.findIndex(card => card.entity_id === read.content?.entity_id);
    return index < 0 ? cards.length : index;
  };
  return reads.map(read => {
    const result = clean(read), content = result.content;
    // Only explicitly unordered PUBLIC collections can be sorted. Never sort the
    // hand, status amounts independently, target operands or a known ordered pile.
    if (result.kind === "run_deck") {
      content.cards.sort((a, b) => compare(stableJson(withoutHandles(a)), stableJson(withoutHandles(b))));
    } else if (result.kind === "combat_piles") {
      for (const zone of content.zones ?? []) {
        if (zone.ordering_semantics === "unordered_multiset") zone.cards.sort((a, b) =>
          compare(stableJson(withoutHandles(a)), stableJson(withoutHandles(b))));
      }
    }
    return result;
  }).sort((a, b) => compare(a.kind, b.kind) || (a.kind === "surface_card"
    ? compare(stableJson(withoutHandles(a.content)), stableJson(withoutHandles(b.content)))
      || location(a) - location(b) : 0));
}

function normalize(snapshot, reads) {
  const current = clean(snapshot), ordered = orderedReads(reads, current), occurrences = new Map(), views = new Map();
  if (selectionAliases.has(current.interaction.kind)) {
    current.interaction.kind = "card_selection";
    current.interaction.content.surface.selection_source_kind = current.interaction.content.surface.kind;
    current.interaction.content.surface.kind = "card_selection";
  }
  if (["card_selection", "native_generated_card_choice", "card_bundle_selection"].includes(current.interaction.kind)) {
    const context = current.interaction.content.context;
    if (context.kind !== "selection") {
      context.owner_kind = context.kind;
      context.kind = "selection";
    }
  }
  function withoutScopedViews(value) {
    if (Array.isArray(value)) return value.map(withoutScopedViews);
    if (value && typeof value === "object") return Object.fromEntries(Object.entries(value)
      .filter(([key]) => key !== "public_card_views").map(([key, item]) => [key, withoutScopedViews(item)]));
    return value;
  }
  function combine(left, right, at) {
    if (stableJson(left) === stableJson(right)) return left;
    if (Array.isArray(left) && Array.isArray(right)
        && stableJson(withoutScopedViews(left)) === stableJson(withoutScopedViews(right)))
      return left.map((item, i) => combine(item, right[i], `${at}/${i}`));
    if (left && right && typeof left === "object" && typeof right === "object"
        && !Array.isArray(left) && !Array.isArray(right)) return merge(left, right, at);
    throw Error(`Conflicting current public entity facts: ${at}`);
  }
  function merge(left, right, at) {
    const result = { ...left };
    for (const [key, item] of Object.entries(right)) {
      if (!Object.hasOwn(result, key)) result[key] = item;
      else result[key] = combine(result[key], item, `${at}/${key}`);
    }
    return result;
  }
  function walk(value, at) {
    if (Array.isArray(value)) { value.forEach((item, i) => walk(item, `${at}/${i}`)); return; }
    if (!value || typeof value !== "object") return;
    if (typeof value.entity_id === "string" && !occurrences.has(value.entity_id))
      occurrences.set(value.entity_id, at);
    if (typeof value.entity_id === "string")
      views.set(value.entity_id, merge(views.get(value.entity_id) ?? {}, value, at));
    if (typeof value.player_entity_id === "string" && !occurrences.has(value.player_entity_id))
      occurrences.set(value.player_entity_id, `${at}/player`);
    for (const key of Object.keys(value).sort()) if (!opaque.test(key)) walk(value[key], `${at}/${key}`);
  }
  // Location/ownership before referent enumeration: the official SDK sorts action
  // handles differently from the CLI. No runtime ID is a sorting/tie-breaking key.
  walk(current.persistent?.content, "persistent");
  walk(current.interaction?.content, "interaction");
  ordered.forEach((read, i) => walk(read.content, `reads/${i}`));
  const refKey = ref => occurrences.get(ref.referent_id)
    ?? `referent/${ref.role}/${stableJson(withoutHandles(ref.properties))}`;
  current.referents = current.referents.map(ref => ({ ...ref,
    role: ref.role === "usable_potion" ? "potion" : ref.role,
    // Join a partial SDK operand to its already-public full hand/inventory view.
    // No unseen engine fact is fetched or inferred. Conflicting values stop the run.
    properties: merge(views.get(ref.properties?.entity_id ?? ref.referent_id) ?? {},
      ref.properties, `referents/${ref.role}`) }));
  const refs = new Map(current.referents.map(ref => [ref.referent_id, ref]));
  for (const action of current.bound_actions.actions) {
    const subject = refs.get(action.subject_referent_id), args = action.arguments ?? [];
    if (!["play", "use"].includes(action.verb) || !subject?.label || args.length !== 1
        || args[0].role !== "target") continue;
    const target = refs.get(args[0].referent_id);
    if (!target?.label) continue;
    const verb = action.verb === "play" ? "Play" : "Use";
    const canonical = `${verb} ${subject.label} on ${target.label}`;
    if (action.label === `${verb} ${subject.label} -> ${target.label}` || action.label === canonical)
      action.label = canonical;
  }
  const keys = current.referents.map(refKey);
  if (new Set(keys).size !== keys.length) throw Error("Ambiguous public occurrence ownership");
  current.referents.sort((a, b) => compare(refKey(a), refKey(b)));
  return { snapshot: current, reads: ordered };
}

export function sharedDecision(snapshot, reads, navigation = null) {
  assertPublicBoundary({ snapshot, reads });
  if (!families.has(snapshot?.interaction?.kind) && !selectionAliases.has(snapshot?.interaction?.kind))
    throw Error(`Unsupported shared family: ${snapshot?.interaction?.kind}`);
  const runtime = snapshot.session?.runtime_instance_id;
  if (!runtime || snapshot.information_policy?.includes_hidden_information !== false
      || snapshot.completeness?.status !== "complete") throw Error("Incomplete public observation");
  const run = snapshot.persistent?.content?.run;
  const player = snapshot.persistent?.content?.player;
  if (run?.ascension !== 8 || !Number.isSafeInteger(run.act) || run.act < 1
      || !Number.isSafeInteger(run.floor) || run.floor < 0
      || player?.character_definition_id !== "IRONCLAD") throw Error("Expected public Ironclad/A8 identity");
  if (!Array.isArray(reads) || !Array.isArray(snapshot.reads)
      || reads.length !== snapshot.reads.length
      || new Set(reads.map(row => row.read_id)).size !== reads.length) throw Error("Missing or duplicate advertised read");
  for (const descriptor of snapshot.reads) {
    const read = reads.find(row => row.read_id === descriptor.read_id);
    if (!read || read.kind !== descriptor.kind || read.expected_snapshot_id !== snapshot.snapshot_id
        || read.observed_snapshot_id !== snapshot.snapshot_id
        || read.session?.runtime_instance_id !== runtime
        || read.completeness?.status !== "complete"
        || read.information_policy?.includes_hidden_information !== false)
      throw Error("Missing, stale, partial, cross-runtime or hidden advertised read");
  }
  const terminal = snapshot.interaction.kind === "game_over";
  let ending = null;
  if (terminal) {
    if (snapshot.interaction.content.context?.kind === "game_over") ending = shippedEnding(snapshot, runtime);
    else if (typeof snapshot.interaction.content.surface?.victory === "boolean") ending = {
      victory: snapshot.interaction.content.surface.victory, basis: "native_public_explicit_terminal_boolean" };
    else throw Error("Terminal observation lacks an explicit public outcome");
    if (typeof snapshot.interaction.content.surface?.victory === "boolean"
        && ending.victory !== snapshot.interaction.content.surface.victory)
      throw Error("Conflicting public terminal outcomes");
  }
  if (!terminal && !completePublicMenu(snapshot, runtime)) throw Error("Incomplete legal action menu");
  if (terminal && !(snapshot.bound_actions?.status === "complete"
      && (snapshot.bound_actions.total_count === 0 && snapshot.bound_actions.actions.length === 0
        || completePublicMenu(snapshot, runtime)))) throw Error("Incomplete terminal presentation menu");
  const scoped = scopedCardSelections(snapshot, reads);
  const prepared = normalize(scoped.snapshot, scoped.reads);
  const originalInput = publicPolicyInput(prepared.snapshot, prepared.reads, navigation);
  const layout = normalizeLayout(originalInput);
  if (layout.unresolved.length) throw Error(`Conflicting layout facts: ${JSON.stringify(layout.unresolved)}`);
  const input = structuredClone(layout.public_input);
  // A canonical order drives both greedy tie-breaking and sampled cumulative mass.
  const indexed = input.candidates.map((candidate, index) => {
    const key = stableJson({ verb: candidate.verb, label: candidate.label,
      subject: candidate.subject?.public_slot ?? null,
      arguments: candidate.arguments.map(arg => ({ role: arg.role, name: arg.name,
        slot: arg.entity?.public_slot ?? null })) });
    return { candidate, index, key };
  }).sort((a, b) => compare(a.key, b.key));
  if (new Set(indexed.map(row => row.key)).size !== indexed.length) throw Error("Ambiguous semantic action mapping");
  input.candidates = indexed.map(row => row.candidate);
  const actions = indexed.map(row => ({ key: row.key, raw_index: row.index,
    bound_action_id: snapshot.bound_actions.actions[row.index].bound_action_id }));
  return { schema_version: "shared-public-decision-v1", contract: CONTRACT,
    source_family: snapshot.interaction.kind,
    observation: { runtime_instance_id: runtime, snapshot_id: snapshot.snapshot_id,
      interaction_id: snapshot.interaction.interaction_id },
    terminal, ending, terminal_actions_are_presentation: terminal, public_input: input, input_digest: digest(input), actions,
    input_layout: LAYOUT, layout_evidence: layout,
    // Transport bindings do not enter the policy. A choice is valid for one frame only.
    binding_id: digest({ runtime, snapshot: snapshot.snapshot_id, input: digest(input), actions, layout: LAYOUT }) };
}

export function deliveredAction(frame, choice, snapshot) {
  if (choice.binding_id !== frame.binding_id || frame.terminal
      || snapshot.snapshot_id !== frame.observation.snapshot_id
      || snapshot.session?.runtime_instance_id !== frame.observation.runtime_instance_id
      || !Number.isSafeInteger(choice.action_index)
      || choice.action_index < 0 || choice.action_index >= frame.actions.length)
    throw Error("Stale or unadvertised checkpoint choice");
  const selected = frame.actions[choice.action_index], action = snapshot.bound_actions.actions[selected.raw_index];
  if (action?.bound_action_id !== selected.bound_action_id
      || action.interaction_id !== frame.observation.interaction_id)
    throw Error("Current action ownership changed");
  return action;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const navigation = newDiagnosticNavigation();
  let current;
  for await (const line of createInterface({ input: process.stdin, crlfDelay: Infinity })) {
    let request;
    try {
      request = JSON.parse(line);
      if (request.command === "commit") {
        if (!current || request.acknowledgement?.delivery !== "delivered") throw Error("No delivered shared-input choice to commit");
        const action = deliveredAction(current.frame, request, current.snapshot);
        if (request.acknowledgement.bound_action_id !== action.bound_action_id
            || request.acknowledgement.runtime_instance_id !== current.frame.observation.runtime_instance_id)
          throw Error("Wrong shared navigation receipt");
        recordInterfaceNavigation(navigation, current.snapshot, action, request.acknowledgement);
        current = null;
        process.stdout.write(`${JSON.stringify({ request_id: request.request_id, ok: true })}\n`);
        continue;
      }
      if (current) throw Error("Previous shared-input choice is unacknowledged");
      const frame = sharedDecision(request.snapshot, request.reads, request.navigation ?? navigation);
      current = { snapshot: request.snapshot, frame };
      process.stdout.write(`${JSON.stringify({ request_id: request.request_id, ok: true, frame })}\n`);
    } catch (error) {
      process.stdout.write(`${JSON.stringify({ request_id: request?.request_id, ok: false, error: error.message })}\n`);
      process.exitCode = 1; break;
    }
  }
}
