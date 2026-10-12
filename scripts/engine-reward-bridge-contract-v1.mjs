// Finite public pickup/capacity semantics. Serialized fixture setup is privileged, never player input.
import { shopFacts, shopPersistentFacts, shopActionKey, prepareShopSave } from "./engine-shop-bridge-contract.mjs";
import { startingOptions } from "./engine-checkpoint-shipped-probe.mjs";
import { firstDifference } from "./engine-journey-contract-v2.mjs";
export { firstDifference };
export const rewardScenarios = new Set(["calling-bell-claim-all", "calling-bell-claim-skip",
  "cauldron-fill-replace-skip", "cauldron-fill-skip"]);
const canonical = (value) => Array.isArray(value) ? value.map(canonical) : value && typeof value === "object"
  ? Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonical(value[key])])) : value;
const sorted = (rows) => [...rows].sort((a, b) => JSON.stringify(canonical(a)).localeCompare(JSON.stringify(canonical(b)), "en"));
const fields = (row, keys) => Object.fromEntries(keys.map((key) => {
  if (row?.[key] == null) throw Error(`Missing public reward field: ${key}`); return [key, row[key]];
}));
export function prepareRewardSave(original, scenario) {
  if (!rewardScenarios.has(scenario)) throw Error("Unknown finite reward fixture");
  // The shop fixture validates the original initial map/save and clears the prefinished room/history.
  if (scenario.startsWith("cauldron")) return prepareShopSave(original);
  prepareShopSave(original);
  const saved = structuredClone(original);
  if (saved.acts[0].rooms?.ancient_id !== "EVENT.NEOW") throw Error("Darv fixture requires the original Neow ancient");
  saved.acts[0].rooms.ancient_id = "EVENT.DARV";
  saved.pre_finished_room = null; saved.map_point_history = [[]];
  return saved;
}
export function visibleReward(row) {
  const value = fields(row, ["kind", "label", "description", "enabled"]);
  if (!["relic", "potion"].includes(value.kind) || typeof value.label !== "string" || !value.label
      || typeof value.description !== "string" || typeof value.enabled !== "boolean")
    throw Error("Only complete visible relic/potion rewards are covered by this panel");
  return value;
}
function referent(snapshot, id) {
  const matches = snapshot.referents.filter((row) => row.referent_id === id);
  if (matches.length !== 1) throw Error("Reward action has no unique current public operand");
  return matches[0];
}
export function rewardActionKey(snapshot, action) {
  if (action.arguments?.length !== 0) throw Error("Reward prefix does not cover argument-based choices");
  if (snapshot.interaction.kind === "shop_inventory") {
    const key = shopActionKey(snapshot, action);
    if (key.subject?.group !== "relics" || key.subject.item?.definition_id !== "CAULDRON")
      throw Error("Only the current Cauldron purchase is covered");
    return { kind: "purchase_cauldron", offer: key.subject };
  }
  if (snapshot.interaction.kind === "event_option") {
    if (action.label !== "Calling Bell" || action.verb !== "activate") throw Error("Only Calling Bell pickup is covered");
    return { kind: "calling_bell" };
  }
  if (snapshot.interaction.kind !== "reward_claim") throw Error("Unexpected pickup decision family");
  const surface = snapshot.interaction.content.surface;
  if (action.subject_referent_id == null) {
    if ((action.verb === "skip" && action.label === "Skip remaining rewards")
        || (action.verb === "activate" && action.label === "Skip remaining rewards and continue"))
      return { kind: "skip" };
    throw Error("Unknown reward closing control");
  }
  const current = referent(snapshot, action.subject_referent_id);
  if (current.role === "reward") {
    const reward = visibleReward(current.properties);
    if (action.verb !== "activate" || !reward.enabled
        || !surface.rewards.some((row) => row.entity_id === current.properties.entity_id
          && !firstDifference(visibleReward(row), reward))) throw Error("Reward operand is stale or disabled");
    return { kind: "claim", reward };
  }
  if (["potion", "discardable_potion"].includes(current.role) && action.verb === "activate") {
    const potion = fields(current.properties, ["definition_id", "slot"]);
    if (surface.potion_slots_full !== true || !Number.isSafeInteger(potion.slot) || potion.slot < 0
        || !surface.discardable_potions?.some((row) => row.entity_id === current.properties.entity_id
          && !firstDifference(fields(row, ["definition_id", "slot"]), potion)))
      throw Error("Discard operand is not a current full-belt potion");
    return { kind: "discard", potion };
  }
  throw Error("Unsupported current reward control");
}
export function rewardFacts(snapshot, deckRead) {
  const kind = snapshot.interaction.kind;
  if (kind === "shop_inventory") return shopFacts(snapshot, deckRead);
  const facts = { kind, ...shopPersistentFacts(snapshot, deckRead) };
  if (kind === "event_option") { facts.options = startingOptions(snapshot); return facts; }
  if (kind !== "reward_claim") throw Error(`Unqualified reward prefix state: ${kind}`);
  const surface = snapshot.interaction.content.surface;
  if (!Array.isArray(surface.rewards) || typeof surface.potion_slots_full !== "boolean"
      || !Array.isArray(surface.discardable_potions)) throw Error("Incomplete current reward surface");
  facts.rewards = sorted(surface.rewards.map(visibleReward));
  facts.potion_slots_full = surface.potion_slots_full;
  facts.actions = sorted(snapshot.bound_actions.actions.map((row) => rewardActionKey(snapshot, row)));
  const claims = facts.actions.filter((row) => row.kind === "claim").map((row) => row.reward);
  if (firstDifference(sorted(claims), facts.rewards.filter((row) => row.enabled)))
    throw Error("Claim menu does not preserve every enabled reward occurrence");
  if (surface.potion_slots_full !== (facts.player.potions.length === facts.player.max_potion_slots)
      || (surface.potion_slots_full && facts.rewards.some((row) => row.kind === "potion" && row.enabled)))
    throw Error("Potion reward enablement differs from the current belt");
  return facts;
}
export function chooseRewardAction(snapshot, wanted) {
  if (wanted.kind === "calling_bell") {
    const rows = snapshot.bound_actions.actions.filter((row) => row.label === "Calling Bell");
    if (rows.length !== 1) throw Error("No unique offered Calling Bell"); return rows[0];
  }
  if (wanted.kind === "purchase_cauldron") {
    const rows = snapshot.bound_actions.actions.filter((row) => {
      const key = shopActionKey(snapshot,row);
      return key.verb === "activate" && key.subject?.group === "relics"
        && key.subject.item?.definition_id === "CAULDRON";
    });
    if (rows.length !== 1) throw Error("No unique current affordable Cauldron"); return rows[0];
  }
  const rows = snapshot.bound_actions.actions.filter((row) => !firstDifference(rewardActionKey(snapshot, row), wanted));
  // Identical visible potion/relic occurrences are interchangeable; preserve their multiplicity.
  if (!rows.length || (wanted.kind !== "claim" && rows.length !== 1)) throw Error("No current reward action matches the frozen public intent");
  return rows[0];
}
export function nextRewardIntent(snapshot, scenario, counts) {
  if (snapshot.interaction.kind !== "reward_claim") return null;
  const keys = snapshot.bound_actions.actions.map((row) => rewardActionKey(snapshot, row));
  if (scenario === "calling-bell-claim-skip" && counts.claims === 1) return keys.find((row) => row.kind === "skip");
  if (scenario.startsWith("cauldron") && counts.claims >= 2) {
    if (scenario === "cauldron-fill-replace-skip" && counts.discards === 0)
      return keys.find((row) => row.kind === "discard" && row.potion.slot === 0);
    if (scenario === "cauldron-fill-skip" || counts.claims === 3) return keys.find((row) => row.kind === "skip");
  }
  return sorted(keys.filter((row) => row.kind === "claim"))[0];
}
export function verifyRewardEffects(scenario, journey) {
  if (!rewardScenarios.has(scenario) || journey.length < 3) throw Error("Incomplete reward prefix");
  const initial = journey[0].facts, offered = journey[1].facts, final = journey.at(-1).facts;
  const bell = scenario.startsWith("calling-bell"), relic = bell ? "CALLING_BELL" : "CAULDRON";
  if (initial.run.ascension !== 8 || initial.run.floor !== 1 || offered.kind !== "reward_claim"
      || offered.rewards.length !== (bell ? 3 : 5) || !offered.player.relics.some((row) => row.definition_id === relic)
      || firstDifference(initial.run, final.run)) throw Error("Pickup fixture or offered rewards differ");
  if (bell && offered.player.deck.filter((row) => row.definition_id === "CURSE_OF_THE_BELL").length !== 1)
    throw Error("Calling Bell did not deliver exactly one curse before offering rewards");
  const actions = journey.slice(1,-1).map((row) => row.action);
  const claims = actions.filter((row) => row.kind === "claim"), discards = actions.filter((row) => row.kind === "discard");
  const skips = actions.filter((row) => row.kind === "skip");
  if (claims.length !== (bell ? (scenario.endsWith("all") ? 3 : 1) : (scenario.includes("replace") ? 3 : 2))
      || discards.length !== (scenario.includes("replace") ? 1 : 0)
      || skips.length !== (scenario.endsWith("all") ? 0 : 1)) throw Error("Missing pickup/capacity/skip decision");
  if (final.kind !== (bell ? "event_option" : "shop_inventory")) throw Error("Reward completion did not return to its owning event/shop");
  for (let i=1;i<journey.length-1;i++) {
    const before=journey[i].facts, after=journey[i+1].facts, action=journey[i].action;
    if (action.kind === "discard") {
      if (!before.potion_slots_full || after.potion_slots_full || before.player.potions.length-after.player.potions.length!==1
          || after.player.potions.some((row)=>row.slot===action.potion.slot)) throw Error("Discard did not reopen exactly one potion slot");
    } else if (action.kind === "claim" && action.reward.kind === "potion") {
      if (after.player.potions.length-before.player.potions.length!==1) throw Error("Potion claim did not occupy a new slot");
    } else if (action.kind === "skip" && firstDifference(before.player,after.player))
      throw Error("Skipping remaining rewards changed persistent ownership");
  }
  if (!bell && (final.player.potions.length!==2 || !journey.some((row)=>row.facts.potion_slots_full===true)))
    throw Error("A8 potion capacity was not exercised");
  return true;
}
