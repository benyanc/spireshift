// A scoped differential over public facts only. This is not a learned player or broad parity.
import { completePublicMenu } from "./engine-menu-probe.mjs";

const sorted = (rows) => rows.sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b), "en"));
const required = (object, keys) => Object.fromEntries(keys.map((key) => {
  if (object?.[key] == null) throw new Error(`Missing public journey field: ${key}`);
  return [key, object[key]];
}));
const definition = (row) => required(row, ["definition_id"]);
const card = (row) => required(row, ["definition_id", "cost", "is_upgraded", "can_play"]);
const coordinate = (row) => required(row, ["col", "row", "point_type"]);

export function actionKey(snapshot, action) {
  const referent = (id) => {
    const found = snapshot.referents.find((row) => row.referent_id === id);
    if (!found) throw new Error("Public action operand has no current referent");
    const props = found.properties;
    if (snapshot.interaction.kind === "map_navigation") return coordinate(props);
    if (snapshot.interaction.kind === "event_option") return required(props, ["index", "title"]);
    if (snapshot.interaction.kind === "combat_turn") {
      const context = snapshot.interaction.content.context;
      const handIndex = context.player.hand.findIndex((row) => row.entity_id === props.entity_id);
      if (handIndex >= 0) return { role: "hand", index: handIndex, ...card(context.player.hand[handIndex]) };
      const enemyIndex = context.enemies.findIndex((row) => row.entity_id === props.entity_id);
      if (enemyIndex >= 0) return { role: "enemy", index: enemyIndex, ...definition(context.enemies[enemyIndex]) };
      throw new Error("Unqualified journey combat operand; potion/player targets need a later panel");
    }
    throw new Error(`Unqualified journey action family: ${snapshot.interaction.kind}`);
  };
  return {
    verb: action.verb,
    subject: action.verb === "end_turn" || action.subject_referent_id == null ? null : referent(action.subject_referent_id),
    arguments: sorted(action.arguments.map((arg) => ({ role: arg.role, target: referent(arg.referent_id) })))
  };
}

export function journeyFacts(snapshot) {
  if (!completePublicMenu(snapshot, snapshot.session?.runtime_instance_id))
    throw new Error("Journey requires a complete public snapshot and legal menu");
  const kind = snapshot.interaction.kind;
  const context = snapshot.interaction.content.context;
  const surface = snapshot.interaction.content.surface;
  const result = { kind, ...persistentFacts(snapshot),
    actions: sorted(snapshot.bound_actions.actions.map((action) => actionKey(snapshot, action))) };
  if (kind === "event_option") {
    result.options = surface.options.map((row) => required(row, ["index", "title", "is_locked"]));
  } else if (kind === "map_navigation") {
    result.next_options = sorted(surface.next_options.map(coordinate));
  } else if (kind === "combat_turn") {
    result.combat = combatFacts(context);
  } else throw new Error(`Unqualified journey observation: ${kind}`);
  return result;
}

export function firstDifference(left, right, field = "$public") {
  if (JSON.stringify(left) === JSON.stringify(right)) return null;
  if (left == null || right == null || typeof left !== typeof right)
    return { field, managed: left, shipped: right };
  if (typeof left !== "object") return { field, managed: left, shipped: right };
  for (const key of [...new Set([...Object.keys(left), ...Object.keys(right)])].sort()) {
    const found = firstDifference(left[key], right[key], `${field}.${key}`);
    if (found) return found;
  }
  return null;
}

export function chooseJourneyAction(snapshot, { startingOption, plays, started }) {
  journeyFacts(snapshot);
  const actions = snapshot.bound_actions.actions;
  if (snapshot.interaction.kind === "event_option") {
    if (!started) {
      const matches = actions.filter((row) => actionKey(snapshot, row).subject?.title === startingOption);
      if (matches.length !== 1) throw new Error("The frozen starting option is not uniquely offered");
      return matches[0];
    }
    if (actions.length === 1) return actions[0];
    throw new Error("Unexpected event choice after the starting reward");
  }
  if (snapshot.interaction.kind === "map_navigation") {
    const candidates = actions.filter((row) => actionKey(snapshot, row).subject?.point_type === "monster");
    if (!candidates.length) throw new Error("No directly offered first normal combat room");
    return candidates.sort((a, b) => JSON.stringify(actionKey(snapshot, a)).localeCompare(JSON.stringify(actionKey(snapshot, b)), "en"))[0];
  }
  if (snapshot.interaction.kind === "combat_turn") {
    const playable = actions.filter((row) => row.verb === "play");
    if (plays < 3 && playable.length) return playable.sort((a, b) => JSON.stringify(actionKey(snapshot, a)).localeCompare(JSON.stringify(actionKey(snapshot, b)), "en"))[0];
    const end = actions.filter((row) => row.verb === "end_turn");
    if (end.length !== 1) throw new Error("No unique native End Turn control");
    return end[0];
  }
  throw new Error("Unexpected journey family");
}

// Exact English attack-number labels are public UI facts. Unknown labels never become zeros.
export function intentAmounts(intent) {
  if (!/Attack/i.test(intent.type)) return { type: intent.type, damage: null, hits: null, total_damage: null };
  if ([intent.damage, intent.hits, intent.total_damage].every(Number.isSafeInteger))
    return { type: intent.type, damage: intent.damage, hits: intent.hits, total_damage: intent.total_damage };
  const match = String(intent.label).match(/^(\d+)(?:\s*[x×]\s*(\d+))?$/u);
  if (!match) throw new Error("Unqualified public attack amount label");
  const damage = Number(match[1]), hits = Number(match[2] ?? 1);
  if (![damage, hits, damage * hits].every(Number.isSafeInteger) || hits < 1)
    throw new Error("Invalid public attack amount label");
  return { type: intent.type, damage, hits, total_damage: damage * hits };
}

export function tutorialAction(snapshot) {
  const surface = snapshot.interaction?.content?.surface;
  const actions = snapshot.bound_actions?.actions;
  if (snapshot.interaction?.kind !== "tutorial" || surface?.tutorial_id !== "combat_rules_ftue"
      || surface.total_pages !== 3 || !Number.isSafeInteger(surface.current_page)
      || surface.current_page < 1 || surface.current_page > 3 || surface.options?.length !== 1
      || !["advance_tutorial", "dismiss_tutorial"].includes(surface.options[0].semantic_id)
      || surface.options[0].enabled !== true || actions?.length !== 1
      || actions[0].verb !== "activate" || actions[0].subject_referent_id != null || actions[0].arguments.length)
    throw new Error("Unqualified tutorial modal; no automatic dismissal");
  return actions[0];
}

export function tutorialGameFacts(snapshot) {
  if (!completePublicMenu(snapshot, snapshot.session?.runtime_instance_id)
      || !["tutorial", "combat_turn"].includes(snapshot.interaction.kind)
      || snapshot.interaction.content.context.kind !== "combat")
    throw new Error("No complete public combat context under the tutorial");
  return { kind: "combat_turn", ...persistentFacts(snapshot), combat: combatFacts(snapshot.interaction.content.context) };
}

function persistentFacts(snapshot) {
  const persistent = snapshot.persistent?.content;
  return {
    run: required(persistent?.run, ["act", "act_definition_id", "floor", "ascension"]),
    player: { ...required(persistent?.player, ["character_definition_id", "hp", "max_hp", "gold", "max_potion_slots"]),
      relics: sorted(persistent.player.relics.map(definition)),
      potions: sorted(persistent.player.potions.map((row) => required(row, ["definition_id", "slot"]))) },
  };
}

function combatFacts(context) {
  const statuses = (rows) => sorted(rows.map((row) => required(row, ["definition_id", "amount"])));
    return { ...required(context, ["round", "turn_owner", "is_play_phase"]),
      player: { ...required(context.player, ["block", "energy", "max_energy", "draw_pile_count", "discard_pile_count", "exhaust_pile_count"]),
        hand: context.player.hand.map(card), statuses: statuses(context.player.statuses) },
      enemies: context.enemies.map((row) => ({ ...required(row, ["definition_id", "hp", "max_hp", "block"]),
        statuses: statuses(row.statuses),
        intents: row.intents.map(intentAmounts) })) };
}
