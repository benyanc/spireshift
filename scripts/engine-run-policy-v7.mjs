// Separate diagnostic navigation for the native merchant approach/inventory owner.
import { chooseRunAction as previous, newDiagnosticNavigation as initial, recordDiagnosticNavigation as record,
  diagnosticScore } from "./engine-run-policy-v5.mjs";
import { chooseRunAction as rank } from "./engine-run-ranking-v1.mjs";
export const newDiagnosticNavigation = () => ({ ...initial(), inspected_shop_visits: [] });
const visit = snapshot => JSON.stringify([snapshot.persistent.content.run.act, snapshot.persistent.content.run.floor]);
export function recordDiagnosticNavigation(navigation, snapshot, action, receipt) {
  record(navigation, snapshot, action, receipt);
  if (receipt.delivery === "delivered" && snapshot.interaction.kind === "shop_inventory"
      && snapshot.interaction.content.surface.inventory_open === false && action.label === "Open inventory"
      && !navigation.inspected_shop_visits.includes(visit(snapshot))) navigation.inspected_shop_visits.push(visit(snapshot));
}
export function chooseRunAction(snapshot, scoreAction = diagnosticScore, navigation = newDiagnosticNavigation()) {
  if (scoreAction === diagnosticScore && snapshot.interaction.kind === "shop_inventory"
      && snapshot.interaction.content.surface.inventory_open === false)
    return rank(snapshot, (_, action) => action.label === (navigation.inspected_shop_visits.includes(visit(snapshot))
      ? "Leave shop" : "Open inventory") ? 1000 : diagnosticScore(snapshot, action));
  return previous(snapshot, scoreAction, navigation);
}
