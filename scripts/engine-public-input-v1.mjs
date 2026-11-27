// Public entity graph, independent of runtime handles. Slots are local visible occurrences,
// not engine IDs. Ordered lists and relationships stay intact; no game facts are inferred.
import { assertPublicBoundary } from "./engine-run-contract-v1.mjs";

export const PUBLIC_INPUT = "actual-engine-public-entity-graph-v1";
const metadata = new Set(["snapshot_id", "interaction_id", "bound_action_id", "read_id",
  "expected_snapshot_id", "observed_snapshot_id", "observed_at", "session", "sequence", "combat_id"]);
const pointer = key => /(?:entity|referent)_ids?$/u.test(key);
const ordered = value => Array.isArray(value) ? value.map(ordered) : value && typeof value === "object"
  ? Object.fromEntries(Object.entries(value).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)
    .map(([key, item]) => [key, ordered(item)])) : value;
export const stableJson = value => JSON.stringify(ordered(value));

export function publicEntityGraph(snapshot, reads = []) {
  assertPublicBoundary({ snapshot, reads });
  const slots = new Map(), refs = new Map();
  const register = id => {
    if (typeof id !== "string" || !id) throw Error("Invalid public entity handle");
    if (!slots.has(id)) slots.set(id, slots.size);
  };
  // Register declarations, never a dangling target/owner pointer. Some inspectable pile
  // cards have no action referent; their own entity_id is still a public declaration.
  for (const item of snapshot.referents ?? []) {
    if (refs.has(item.referent_id)) throw Error("Duplicate public referent");
    register(item.referent_id); refs.set(item.referent_id, item);
  }
  function declarations(value) {
    if (Array.isArray(value)) { value.forEach(declarations); return; }
    if (!value || typeof value !== "object") return;
    if (Object.hasOwn(value, "entity_id")) register(value.entity_id);
    for (const [key, item] of Object.entries(value).sort())
      if (!metadata.has(key)) declarations(item);
  }
  declarations({ persistent: snapshot.persistent, interaction: snapshot.interaction,
    referents: snapshot.referents, reads: reads.map(row => row.content) });
  const resolve = id => {
    if (id == null) return null;
    if (!slots.has(id)) throw Error("Unresolved public entity reference");
    return { public_slot: slots.get(id) };
  };
  function normalize(value, key = "") {
    if (pointer(key)) return Array.isArray(value) ? value.map(resolve) : resolve(value);
    if (Array.isArray(value)) return value.map(item => normalize(item));
    if (value && typeof value === "object") return Object.fromEntries(Object.entries(value)
      .filter(([name]) => !metadata.has(name)).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)
      .map(([name, item]) => [name, normalize(item, name)]));
    if (typeof value === "number" && !Number.isFinite(value)) throw Error("Nonfinite public fact");
    if (value === undefined) throw Error("Undefined public fact");
    return value;
  }
  function entity(id) {
    if (id == null) return null;
    const item = refs.get(id);
    if (!item) throw Error("Action operand has no current public referent");
    return { ...resolve(id), role: item.role, label: item.label ?? null,
      state: normalize(item.state ?? {}), properties: normalize(item.properties ?? {}) };
  }
  function action(row) {
    return { verb: row.verb, label: row.label ?? null, subject: entity(row.subject_referent_id),
      arguments: (row.arguments ?? []).map(arg => ({ role: arg.role ?? null, name: arg.name ?? null,
        entity: entity(arg.referent_id) })) };
  }
  return { normalize, entity, action, context: {
    persistent: normalize(snapshot.persistent?.content ?? {}),
    interaction: normalize(snapshot.interaction ?? {}),
    referents: (snapshot.referents ?? []).map(item => entity(item.referent_id)),
    reads: reads.map(row => ({ kind: row.kind, content: normalize(row.content) })) } };
}

export function publicPolicyInput(snapshot, reads = [], navigation = null) {
  const graph = publicEntityGraph(snapshot, reads);
  const run = snapshot.persistent?.content?.run;
  const visit = JSON.stringify([run?.act, run?.floor]);
  const declined = action => (navigation?.declined_card_rewards ?? []).some(row =>
    row.visit === visit && row.referent_id === action.subject_referent_id);
  // Public memory of our own delivered choices, never raw handles or hidden game history.
  const history = { shop_inspected: navigation?.inspected_shop_visits?.includes(visit) ?? false };
  return { schema_version: PUBLIC_INPUT, context: graph.context,
    candidates: (snapshot.bound_actions?.actions ?? []).map(action => ({ ...graph.action(action),
      history: { ...history, card_reward_declined: declined(action) } })) };
}
