// ID-invariant diagnostic initializer. Handles associate successive offers only;
// target preferences use the visible entity graph and keep the native binding unchanged.
import { assertPublicBoundary } from "./engine-run-contract-v1.mjs";
import { chooseRunAction as rankActions, actionSemantics, publicActionKey, diagnosticScore } from "./engine-run-ranking-v1.mjs";
import { newDiagnosticNavigation as shopNavigation,
  recordDiagnosticNavigation as recordShopNavigation } from "./engine-run-policy-v3.mjs";
export { actionSemantics, publicActionKey, diagnosticScore } from "./engine-run-ranking-v1.mjs";

export const newDiagnosticNavigation = () => ({ ...shopNavigation(), pending_card_reward: null,
  declined_card_rewards: [] });

function visit(snapshot) {
  const run = snapshot.persistent?.content?.run;
  if (!Number.isSafeInteger(run?.act) || run.act < 1
      || !Number.isSafeInteger(run?.floor) || run.floor < 0)
    throw Error("Reward navigation needs public act and floor");
  return JSON.stringify([run.act, run.floor]);
}

function cardReward(snapshot, action) {
  if (snapshot.interaction.kind !== "reward_claim" || action.verb !== "activate") return null;
  const item = snapshot.referents?.find(row => row.referent_id === action.subject_referent_id);
  if (item?.role !== "reward" || item.properties?.kind !== "card") return null;
  // The public handle links a particular offer across its preview/return. Its numeric or random
  // contents never rank choices; distinct same-text offers remain distinct within this game.
  return { visit: visit(snapshot), referent_id: item.referent_id, action_key: publicActionKey(snapshot, action) };
}

// Other reward rows can disappear and change public occurrence slots. Association
// uses this offer's handle within the same visit; its bytes never rank a preference.
const sameOffer = (a, b) => a?.visit === b?.visit && a?.referent_id === b?.referent_id;

export function recordDiagnosticNavigation(navigation, snapshot, action, receipt) {
  assertPublicBoundary({ navigation, snapshot });
  if (receipt.delivery !== "delivered") return;
  recordShopNavigation(navigation, snapshot, action, receipt);
  const offer = cardReward(snapshot, action);
  if (offer) { navigation.pending_card_reward = offer; return; }
  const pending = navigation.pending_card_reward;
  if (!pending || snapshot.interaction.kind === "tutorial") return;
  if (snapshot.interaction.kind === "card_reward_selection" && pending.visit === visit(snapshot)
      && actionSemantics(snapshot, action) === "skip_card"
      && !navigation.declined_card_rewards.some(row => sameOffer(row, pending)))
    navigation.declined_card_rewards.push(pending);
  navigation.pending_card_reward = null;
}

export function chooseRunAction(snapshot, scoreAction = diagnosticScore, navigation = newDiagnosticNavigation()) {
  assertPublicBoundary({ navigation, snapshot });
  if (scoreAction !== diagnosticScore) return rankActions(snapshot, scoreAction);
  if (snapshot.interaction.kind === "shop_room") {
    const inspected = navigation.inspected_shop_visits.includes(visit(snapshot));
    return rankActions(snapshot, (state, action) => {
      if (action.verb === "open" && action.label === "Open shop inventory") return inspected ? 0 : 100;
      if (action.verb === "activate" && action.label === "Leave shop and open map") return inspected ? 100 : 50;
      return diagnosticScore(state, action);
    });
  }
  if (snapshot.interaction.kind !== "reward_claim")
    return rankActions(snapshot, scoreAction);
  return rankActions(snapshot, (state, action) => {
    const offer = cardReward(state, action);
    // Collect other available rewards before the ordinary advertised Proceed control. If the
    // offer is the only legal choice, return it; no hidden exit or mandatory Skip is invented.
    return offer && navigation.declined_card_rewards.some(row => sameOffer(row, offer))
      ? -1 : diagnosticScore(state, action);
  });
}
