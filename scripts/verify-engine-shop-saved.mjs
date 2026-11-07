// Saved data only: no game launcher, network client, optimizer or implicit follow-up.
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import path from "node:path";
import { chooseShopAction, firstDifference, shopActionKey, shopFacts, shopPersistentFacts,
  shopRoomAction, removalUiAction, shopPlans, verifyShopEffects, potionTutorialAction, verifyPotionTutorialEffect } from "./engine-shop-bridge-contract.mjs";
const deliveredAction = (action) => ({ verb: action.verb, bound_action_id: action.bound_action_id,
  subject_referent_id: action.subject_referent_id ?? null, arguments: action.arguments });
export function verifySavedShop(scenario, plan, nativeSnapshots, shipped) {
  const operations = shopPlans[scenario], count = operations?.length;
  if (!count || plan?.length !== count + 1 || nativeSnapshots?.length !== plan.length
      || shipped.comparisons?.length !== plan.length || shipped.shop_ui_steps?.length !== 3
      || shipped.semantic_actions_delivered !== count || shipped.public_actions_requested !== count + 4
      || shipped.menu_actions_requested !== 1 || shipped.privileged_fixture !== true
      || shipped.training_allowed !== false || shipped.receipts?.length !== count + 5
      || shipped.potion_tutorial_steps?.length !== 1 || shipped.tutorial_actions_requested !== 1)
    throw new Error("Incomplete saved shop evidence");
  const runtime = shipped.starting_snapshot?.session?.runtime_instance_id, ledger = shipped.receipts;
  if (!runtime || ledger.some((row) => row.delivery !== "delivered"
      || row.attribution?.runtime_instance_id !== runtime || !row.request_id)
      || new Set(ledger.map((row) => row.request_id)).size !== ledger.length)
    throw new Error("Saved shop delivery ledger belongs to an incomplete/different host");
  const own = (snapshot) => {
    if (snapshot?.session?.runtime_instance_id !== runtime) throw new Error("Shop UI step belongs to another host");
  };
  let receiptIndex = 1;
  const checkReceipt = (action) => {
    if (firstDifference(deliveredAction(ledger[receiptIndex++]?.action ?? {}), deliveredAction(action)))
      throw new Error("Saved shop receipt does not match the freshly bound public action");
  };
  const entry = shipped.shop_ui_steps[0];
  own(entry.before); own(entry.after);
  if (entry.kind !== "open_inventory" || entry.public_game_facts_unchanged !== true
      || firstDifference(shopRoomAction(entry.before, "open"), entry.action)
      || firstDifference(shopPersistentFacts(entry.before, entry.beforeDeck), shopPersistentFacts(entry.after, entry.afterDeck))
      || firstDifference(entry.after, shipped.starting_snapshot))
    throw new Error("Saved shop entry is incomplete or changed game facts");
  checkReceipt(entry.action);
  for (let i = 0; i < plan.length; i++) {
    const row = plan[i], native = nativeSnapshots[i], observed = shipped.comparisons[i];
    own(observed.snapshot);
    if (observed.index !== i || observed.matched !== true
        || firstDifference(shopFacts(native.snapshot, native.deckRead), row.facts)
        || firstDifference(shopFacts(observed.snapshot, observed.deckRead), row.facts)
        || firstDifference(observed.facts, row.facts))
      throw new Error(`Saved public shop observation differs at ${i}`);
    if (i === count) {
      if (row.action !== null) throw new Error("Final shop observation unexpectedly has an action");
      continue;
    }
    const nativeAction = chooseShopAction(native.snapshot, operations[i]);
    const matches = observed.snapshot.bound_actions.actions.filter((action) => !firstDifference(shopActionKey(observed.snapshot, action), row.action));
    if (!row.action || firstDifference(shopActionKey(native.snapshot, nativeAction), row.action) || matches.length !== 1)
      throw new Error(`Saved shop action lacks a unique current operand at ${i}`);
    checkReceipt(matches[0]);
    const tutorialIndex = scenario === "ordinary-purchases-removal" ? 1 : 2;
    const tutorial = shipped.potion_tutorial_steps[0];
    if (tutorial.index !== tutorialIndex) throw new Error("Fresh potion tutorial belongs to another purchase");
    if (i === tutorialIndex) {
      own(tutorial.before); own(tutorial.after);
      verifyPotionTutorialEffect(tutorial.before, tutorial.beforeDeck, tutorial.after, tutorial.afterDeck);
      if (tutorial.public_game_facts_unchanged !== true
          || firstDifference(potionTutorialAction(tutorial.before), tutorial.action)
          || firstDifference(tutorial.after, shipped.comparisons[i + 1].snapshot)
          || firstDifference(shopPersistentFacts(tutorial.after, tutorial.afterDeck),
            shopPersistentFacts(shipped.comparisons[i + 1].snapshot, shipped.comparisons[i + 1].deckRead)))
        throw new Error("Fresh potion tutorial is unbound or changes the purchase result");
      checkReceipt(tutorial.action);
    }
    if (matches[0].verb === "select") {
      const steps = shipped.shop_ui_steps.filter((step) => step.index === i);
      if (steps.length !== 1) throw new Error("Missing removal selection/preview evidence");
      for (let j = 0; j < 1; j++) {
        const step = steps[j], phase = "preview";
        own(step.before); own(step.current); own(step.after);
        if (step.kind !== `removal_${phase}` || step.public_game_facts_unchanged_before_commit !== true
            || firstDifference(step.before, observed.snapshot) || firstDifference(step.beforeDeck, observed.deckRead)
            || firstDifference(step.selected_action, matches[0])) throw new Error("Removal UI evidence has another source decision");
        const action = removalUiAction(step.before, step.beforeDeck, step.current, step.currentDeck, matches[0], phase);
        if (firstDifference(action, step.action)
            || firstDifference(step.after, shipped.comparisons[i + 1].snapshot))
          throw new Error("Removal UI steps are reordered or have an unobserved successor");
        checkReceipt(action);
      }
    } else if (row.action.verb === "close") {
      const steps = shipped.shop_ui_steps.filter((step) => step.index === i);
      if (steps.length !== 1) throw new Error("Missing shop-room Proceed evidence");
      const step = steps[0]; own(step.current); own(step.after);
      if (step.kind !== "proceed_to_map" || step.public_game_facts_unchanged_before_commit !== true
          || firstDifference(step.before, observed.snapshot) || firstDifference(step.beforeDeck, observed.deckRead)
          || firstDifference(shopPersistentFacts(step.before, step.beforeDeck), shopPersistentFacts(step.current, step.currentDeck))
          || firstDifference(shopRoomAction(step.current, "proceed"), step.action)
          || firstDifference(step.after, shipped.comparisons[i + 1].snapshot))
        throw new Error("Shop exit evidence changes facts or lacks the current Proceed control");
      checkReceipt(step.action);
    }
  }
  if (receiptIndex !== ledger.length || firstDifference(shipped.starting_snapshot, shipped.comparisons[0].snapshot)
      || firstDifference(shipped.latest_snapshot, shipped.comparisons.at(-1).snapshot))
    throw new Error("Incomplete or unused shop delivery evidence");
  verifyShopEffects(scenario, plan);
  return { compared_snapshots: plan.length, semantic_actions_delivered: count,
    public_actions_delivered: count + 4, shop_ui_steps: 3, potion_tutorial_steps: 1 };
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  let input = ""; for await (const chunk of process.stdin) input += chunk.toString();
  const results = JSON.parse(input).map((item) => verifySavedShop(item.scenario, item.plan,
    readFileSync(item.native_snapshots, "utf8").trim().split("\n").map((line) => JSON.parse(line)), item.shipped));
  console.log(JSON.stringify(results));
}
