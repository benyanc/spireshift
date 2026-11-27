// The diagnostic player remembers an inspected shop; this does not constrain a learned scorer.
import { assertPublicBoundary } from "./engine-run-contract-v1.mjs";
import { chooseRunAction as rankActions, diagnosticScore } from "./engine-run-policy-v2.mjs";
export { actionSemantics, publicActionKey, diagnosticScore } from "./engine-run-policy-v2.mjs";

export const newDiagnosticNavigation = () => ({ inspected_shop_visits: [] });

function shopVisit(snapshot) {
  const run = snapshot.persistent?.content?.run;
  if (!Number.isSafeInteger(run?.act) || run.act < 1
      || !Number.isSafeInteger(run?.floor) || run.floor < 0)
    throw Error("Shop navigation needs public act and floor");
  return JSON.stringify([run.act, run.floor]);
}

function shopControl(snapshot, action) {
  if (snapshot.interaction.kind !== "shop_room") return null;
  if (action.verb === "open" && action.label === "Open shop inventory") return "inspect";
  if (action.verb === "activate" && action.label === "Leave shop and open map") return "leave";
  return null;
}

export function recordDiagnosticNavigation(navigation, snapshot, action, receipt) {
  assertPublicBoundary({ navigation, snapshot });
  if (receipt.delivery !== "delivered" || shopControl(snapshot, action) !== "inspect") return;
  const visit = shopVisit(snapshot);
  if (!navigation.inspected_shop_visits.includes(visit)) navigation.inspected_shop_visits.push(visit);
}

export function chooseRunAction(snapshot, scoreAction = diagnosticScore, navigation = newDiagnosticNavigation()) {
  assertPublicBoundary({ navigation, snapshot });
  // Only the simple initializer gets a navigation preference. All advertised actions remain
  // available to an external scorer, including revisiting inventory or leaving without buying.
  if (snapshot.interaction.kind !== "shop_room" || scoreAction !== diagnosticScore)
    return rankActions(snapshot, scoreAction);
  const inspected = navigation.inspected_shop_visits.includes(shopVisit(snapshot));
  return rankActions(snapshot, (state, action) => {
    const control = shopControl(state, action);
    if (control === "inspect") return inspected ? 0 : 100;
    if (control === "leave") return inspected ? 100 : 50;
    return diagnosticScore(state, action);
  });
}
