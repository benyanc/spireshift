// OFFLINE ONLY. No production caller, model loader, delivery API or filesystem writes.
import { createHash } from "node:crypto";
import { stableJson } from "../../scripts/engine-public-input-v1.mjs";
import { assertPublicBoundary } from "../../scripts/engine-run-contract-v1.mjs";

export const SCHEMA = "offline-public-input-layout-v1";
export const INPUT_SCHEMA = "offline-public-entity-graph-layout-v1";
export const digest = value => `sha256:${createHash("sha256").update(stableJson(value)).digest("hex")}`;
const same = (a, b) => stableJson(a) === stableJson(b);
const object = value => value !== null && typeof value === "object" && !Array.isArray(value);
const clone = value => structuredClone(value);
const escape = key => String(key).replaceAll("~", "~0").replaceAll("/", "~1");
function parts(path) {
  if (typeof path !== "string" || !path.startsWith("/") || /~(?![01])/u.test(path))
    throw Error("Invalid reconstruction path");
  const keys = path.slice(1).split("/").map(key => key.replaceAll("~1", "/").replaceAll("~0", "~"));
  if (keys.some(key => ["__proto__", "prototype", "constructor"].includes(key)))
    throw Error("Unsafe reconstruction path");
  return keys;
}
const own = (row, key) => {
  if (row === null || typeof row !== "object" || !Object.hasOwn(row, key))
    throw Error("Missing reconstruction path");
  return row[key];
};
const at = (value, path) => parts(path).reduce(own, value);
const parent = (value, path) => {
  const keys = parts(path), key = keys.pop();
  return [keys.reduce(own, value), key];
};

function validJson(value) {
  if (value === null || typeof value === "string" || typeof value === "boolean") return;
  if (typeof value === "number" && Number.isFinite(value)) return;
  if (Array.isArray(value)) { value.forEach(validJson); return; }
  if (!object(value) || Object.getPrototypeOf(value) !== Object.prototype)
    throw Error("Expected finite ordinary public JSON");
  for (const [key, item] of Object.entries(value)) {
    if (["__proto__", "prototype", "constructor"].includes(key))
      throw Error("Unsafe public JSON property");
    validJson(item);
  }
}

// These are explicit aliases in the pinned native persistent projection, NOT
// names guessed from equal observed values. Local floor and total floor differ.
const playerAliases = {
  character_id: "character_definition_id", name: "character_name", hp: "hp",
  max_hp: "max_hp", gold: "gold", max_potion_slots: "max_potion_slots",
};
const runAliases = {
  act: "act", act_definition_id: "act_definition_id", act_name: "act_name",
  total_floor: "floor", ascension: "ascension", modifiers: "modifiers",
};
const singletonKinds = new Set(["run", "event", "rest", "treasure", "reward", "selection", "terminal", "shop"]);
const pointerKey = key => /(?:entity|referent)_ids?$/u.test(key);
const operandPath = path => /^\/context\/referents\/\d+$/u.test(path)
  || /^\/candidates\/\d+\/(?:subject|arguments\/\d+\/entity)$/u.test(path);

function relabelSlots(input, rewrites) {
  const identities = new Map();
  const declare = id => {
    if (!Number.isSafeInteger(id) || id < 0) throw Error("Invalid local public entity slot");
    if (!identities.has(id)) identities.set(id, identities.size);
  };
  function declarations(row, path = "") {
    if (Array.isArray(row)) { row.forEach((item, i) => declarations(item, `${path}/${i}`)); return; }
    if (!object(row)) return;
    if (object(row.entity_id)) declare(row.entity_id.public_slot);
    if (operandPath(path) && Object.hasOwn(row, "public_slot")) {
      declare(row.public_slot);
    }
    for (const key of Object.keys(row).sort()) declarations(row[key], `${path}/${escape(key)}`);
  }
  // Choose labels by retained visible ownership/position, not the old numeric
  // labels or definition IDs. Equal-definition physical copies stay distinct.
  declarations(input.context.persistent, "/context/persistent");
  declarations(input.context.reads, "/context/reads");
  declarations(input.context.interaction, "/context/interaction");
  declarations(input.context.referents, "/context/referents");
  declarations(input.candidates, "/candidates");
  // Retain new public declarations outside the known anchors as well. A mere
  // owner/target pointer still cannot declare the entity it points to.
  declarations(input);
  function replace(row, path = "", pointer = false) {
    if (Array.isArray(row)) { row.forEach((item, i) => replace(item, `${path}/${i}`, pointer)); return; }
    if (!object(row)) return;
    if ((pointer || operandPath(path)) && Object.hasOwn(row, "public_slot")) {
      const before = row.public_slot, after = identities.get(before);
      if (after === undefined) throw Error("Unresolved local public entity slot");
      if (before !== after) {
        rewrites.push({ operation: "relabel_slot", path: `${path}/public_slot`, before, after,
          rule: "bijective_owned_occurrence_labels_v1" });
        row.public_slot = after;
      }
    }
    for (const key of Object.keys(row)) replace(row[key], `${path}/${escape(key)}`, pointerKey(key));
  }
  replace(input);
  return Object.fromEntries(identities);
}

export function actionsPreserved(result, original) {
  const input = clone(result.canonical_input);
  for (const rewrite of result.rewrites.toReversed()) if (rewrite.operation === "relabel_slot") {
    const [row, key] = parent(input, rewrite.path);
    if (row[key] !== rewrite.after) return false;
    row[key] = rewrite.before;
  }
  return same(actionIdentity(input), actionIdentity(original));
}
// Nullable declarations in VisibleCard / VisibleEventOptionTooltip. Missing
// IsSelected, enabled, locked and other required booleans are NEVER filled in.
const nullableCard = ["name", "star_cost", "description", "existing_enchantment",
  "target_type", "can_play", "unplayable_reason"];
const cardShape = value => object(value.entity_id) && Number.isSafeInteger(value.entity_id.public_slot)
  && typeof value.definition_id === "string" && typeof value.type === "string"
  && typeof value.cost === "string" && typeof value.rarity === "string"
  && typeof value.is_upgraded === "boolean";

function declaredPaths(input) {
  const cards = new Set(), tooltips = new Set();
  const card = (value, path) => { if (object(value) && cardShape(value)) cards.add(path); };
  const list = (values, path) => { if (Array.isArray(values)) values.forEach((value, i) => card(value, `${path}/${i}`)); };
  const option = (value, path) => {
    if (!Array.isArray(value?.tooltips)) return;
    value.tooltips.forEach((tip, i) => {
      const next = `${path}/tooltips/${i}`;
      if (object(tip) && ["text", "card"].includes(tip.kind)) {
        tooltips.add(next); card(tip.card, `${next}/card`);
      }
    });
  };
  const operand = (value, path) => {
    if (value?.role === "card") card(value.properties, `${path}/properties`);
    if (value?.role === "option") option(value.properties, `${path}/properties`);
  };
  input.context.referents?.forEach((value, i) => operand(value, `/context/referents/${i}`));
  input.candidates.forEach((value, i) => {
    operand(value.subject, `/candidates/${i}/subject`);
    value.arguments.forEach((arg, j) => operand(arg.entity, `/candidates/${i}/arguments/${j}/entity`));
  });
  input.context.reads?.forEach((read, i) => {
    const base = `/context/reads/${i}/content`;
    if (read.kind === "run_deck") list(read.content.cards, `${base}/cards`);
    if (read.kind === "surface_card") card(read.content, base);
    if (read.kind === "combat_piles") read.content.zones?.forEach((zone, j) => list(zone.cards, `${base}/zones/${j}/cards`));
  });
  const surface = input.context.interaction.content.surface, base = "/context/interaction/content/surface";
  if (surface?.kind === "event_option") surface.options?.forEach((value, i) => option(value, `${base}/options/${i}`));
  if (surface?.kind === "combat_turn") list(surface.hand, `${base}/hand`);
  if (["card_selection", "card_reward_selection", "native_generated_card_choice"].includes(surface?.kind))
    list(surface.cards, `${base}/cards`);
  for (const key of ["relics", "potions"])
    input.context.persistent.player?.[key]?.forEach((value, i) => list(value.card_previews,
      `/context/persistent/player/${key}/${i}/card_previews`));
  return { cards, tooltips };
}

export function actionIdentity(input) {
  return input.candidates.map(candidate => ({
    verb: candidate.verb, label: candidate.label, history: candidate.history,
    subject: candidate.subject === null ? null : {
      public_slot: candidate.subject.public_slot, role: candidate.subject.role,
      label: candidate.subject.label, state: candidate.subject.state,
    },
    arguments: candidate.arguments.map(argument => ({
      role: argument.role, name: argument.name,
      entity: argument.entity === null ? null : {
        public_slot: argument.entity.public_slot, role: argument.entity.role,
        label: argument.entity.label, state: argument.entity.state,
      },
    })),
  }));
}

export function convert(input) {
  validJson(input);
  assertPublicBoundary(input);
  if (!["actual-engine-public-entity-graph-v1", INPUT_SCHEMA].includes(input.schema_version)
      || !object(input.context?.persistent) || !object(input.context?.interaction?.content)
      || !Array.isArray(input.candidates)) throw Error("Expected a completed shared public graph");
  const canonical = clone(input), rewrites = [], unresolved = [], declared = declaredPaths(input);
  if (canonical.schema_version !== INPUT_SCHEMA) {
    rewrites.push({ operation: "replace_schema", path: "/schema_version",
      before: canonical.schema_version, after: INPUT_SCHEMA, rule: "offline_layout_schema_v1" });
    canonical.schema_version = INPUT_SCHEMA;
  }
  function addNull(row, key, path, rule) {
    if (Object.hasOwn(row, key)) return;
    row[key] = null;
    rewrites.push({ operation: "add_typed_null", path: `${path}/${escape(key)}`, rule });
  }
  function remove(row, key, path, rule, target = null) {
    rewrites.push({ operation: "remove_duplicate", path: `${path}/${escape(key)}`,
      before: clone(row[key]), rule, target });
    delete row[key];
  }
  // Only typed records, never every null field or every vaguely card-shaped object.
  function optional(row, path = "") {
    if (Array.isArray(row)) { row.forEach((item, index) => optional(item, `${path}/${index}`)); return; }
    if (!object(row)) return;
    if (declared.cards.has(path)) for (const key of nullableCard) addNull(row, key, path, "VisibleCard_nullable_v1");
    if (declared.tooltips.has(path))
      for (const key of ["name", "description", "card"])
        addNull(row, key, path, "VisibleEventOptionTooltip_nullable_v1");
    for (const key of Object.keys(row)) optional(row[key], `${path}/${escape(key)}`);
  }
  optional(canonical);
  const content = canonical.context.interaction.content, persistent = canonical.context.persistent;
  const current = content.context;
  if (persistent.scope === "active_single_player_run" && object(current) && singletonKinds.has(current.kind)) {
    for (const [kind, aliases] of [["player", playerAliases], ["run", runAliases]]) {
      const source = current[kind], target = persistent[kind];
      if (!object(source) || !object(target)) continue;
      const sourcePath = `/context/interaction/content/context/${kind}`;
      const targetPath = `/context/persistent/${kind}`;
      // The pinned native commonContext denotes the single local player. Any
      // explicit foreign/ambiguous owner overrides that assumption and is retained.
      const owners = [source.entity_id, source.player_entity_id, source.owner_entity_id]
        .filter(value => value !== undefined);
      if (kind === "player" && owners.some(owner => !same(owner, target.entity_id))) {
        unresolved.push({ code: "different_or_unresolved_player_owner", path: sourcePath }); continue;
      }
      const start = rewrites.length;
      for (const [name, alias] of Object.entries(aliases)) {
        if (!Object.hasOwn(source, name) || !Object.hasOwn(target, alias)) continue;
        if (!same(source[name], target[alias])) {
          unresolved.push({ code: "conflicting_singleton_fact", path: `${sourcePath}/${name}`,
            target: `${targetPath}/${alias}` }); continue;
        }
        remove(source, name, sourcePath, `same_current_${kind}_fact_v1`, `${targetPath}/${alias}`);
      }
      if (rewrites.length > start && !Object.keys(source).length)
        remove(current, kind, "/context/interaction/content/context", "empty_duplicate_container_v1");
    }
  }
  const slotMap = relabelSlots(canonical, rewrites);
  const result = {
    schema_version: SCHEMA, canonical_input: canonical,
    original_digest: digest(input), canonical_digest: digest(canonical),
    rewrites, unresolved, slot_map: slotMap,
    lossless_scope: "exact_shared_public_graph_reconstruction_not_raw_engine_state",
    production_ready: false, training_allowed: false,
  };
  if (!actionsPreserved(result, input)) throw Error("Legal choice identity changed");
  if (!same(restore(result), input)) throw Error("Input-layout reconstruction failed");
  return result;
}

export function restore(result) {
  validJson(result);
  assertPublicBoundary(result.canonical_input);
  if (result.schema_version !== SCHEMA || digest(result.canonical_input) !== result.canonical_digest)
    throw Error("Changed canonical input or converter version");
  const original = clone(result.canonical_input);
  for (const rewrite of result.rewrites.toReversed()) {
    const [row, key] = parent(original, rewrite.path);
    if (rewrite.operation === "add_typed_null") {
      if (!Object.hasOwn(row, key) || row[key] !== null) throw Error("Changed typed-null rewrite");
      delete row[key];
    } else if (rewrite.operation === "remove_duplicate") {
      if (Object.hasOwn(row, key)) throw Error("Changed duplicate rewrite");
      row[key] = clone(rewrite.before);
      if (rewrite.target !== null && !same(at(original, rewrite.target), row[key]))
        throw Error("Changed duplicate target");
    } else if (rewrite.operation === "relabel_slot") {
      if (row[key] !== rewrite.after || !Number.isSafeInteger(rewrite.before)) throw Error("Changed slot rewrite");
      row[key] = rewrite.before;
    } else if (rewrite.operation === "replace_schema") {
      if (rewrite.path !== "/schema_version" || row[key] !== INPUT_SCHEMA
          || rewrite.before !== "actual-engine-public-entity-graph-v1") throw Error("Changed schema rewrite");
      row[key] = rewrite.before;
    } else throw Error("Unknown layout rewrite");
  }
  if (digest(original) !== result.original_digest) throw Error("Changed reconstruction evidence");
  return original;
}

export function differencePaths(left, right, path = "", limit = 40) {
  if (same(left, right) || limit < 1) return [];
  if (object(left) && object(right)) {
    const result = [];
    for (const key of [...new Set([...Object.keys(left), ...Object.keys(right)])].sort()) {
      const next = `${path}/${escape(key)}`;
      result.push(...(!Object.hasOwn(left, key) || !Object.hasOwn(right, key) ? [next]
        : differencePaths(left[key], right[key], next, limit - result.length)));
      if (result.length >= limit) break;
    }
    return result;
  }
  if (Array.isArray(left) && Array.isArray(right) && left.length === right.length)
    return left.flatMap((item, index) => differencePaths(item, right[index], `${path}/${index}`, limit)).slice(0, limit);
  return [path];
}
