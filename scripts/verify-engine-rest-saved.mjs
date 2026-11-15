// Read-only audit: no game launcher, network client or learning runtime.
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import path from "node:path";
import { chooseRestAction, firstDifference, restActionKey, restFacts, restPlans, upgradePreviewConfirmation } from "./engine-rest-bridge-contract.mjs";
import { restTutorialAction, verifyRestTutorialEffect } from "./engine-rest-tutorial-v1.mjs";

const deliveredAction = (action) => ({ verb: action.verb, bound_action_id: action.bound_action_id,
  subject_referent_id: action.subject_referent_id ?? null, arguments: action.arguments });

export function verifySavedRest(scenario, plan, nativeSnapshots, shipped, freshTutorial = false) {
  const operations = restPlans[scenario];
  if (!operations || plan?.length !== 7 || nativeSnapshots?.length !== 7
      || shipped.comparisons?.length !== 7 || shipped.upgrade_ui_steps?.length !== 1
      || shipped.semantic_actions_delivered !== 6 || shipped.public_actions_requested !== 7
      || shipped.menu_actions_requested !== 1 || shipped.privileged_fixture !== true
      || shipped.training_allowed !== false || shipped.receipts?.length !== (freshTutorial ? 9 : 8))
    throw new Error("Incomplete saved rest fixture evidence");
  const runtime = shipped.starting_snapshot?.session?.runtime_instance_id;
  const ledger = shipped.receipts;
  if (!runtime || ledger.some((row) => row.delivery !== "delivered"
      || row.attribution?.runtime_instance_id !== runtime || !row.request_id)
      || new Set(ledger.map((row) => row.request_id)).size !== ledger.length)
    throw new Error("Saved rest delivery ledger is incomplete or from another host");
  let receiptIndex = shipped.menu_actions_requested;
  const checkReceipt = (action) => {
    if (firstDifference(deliveredAction(ledger[receiptIndex++]?.action ?? {}), deliveredAction(action)))
      throw new Error("Saved delivery does not match the current bound rest action");
  };
  if (freshTutorial) {
    if (shipped.rest_tutorial_steps?.length !== 1 || shipped.tutorial_actions_requested !== 1)
      throw new Error("Fresh rest tutorial evidence is absent");
    const step = shipped.rest_tutorial_steps[0];
    verifyRestTutorialEffect(step.before, step.beforeDeck, step.after, step.afterDeck);
    if (step.public_game_facts_unchanged !== true
        || firstDifference(restTutorialAction(step.before), step.action)
        || firstDifference(step.after, shipped.starting_snapshot))
      throw new Error("Fresh rest tutorial evidence does not bind to the fixture start");
    checkReceipt(step.action);
  }
  for (let i = 0; i < plan.length; i++) {
    const row = plan[i], native = nativeSnapshots[i], observed = shipped.comparisons[i];
    if (observed.index !== i || observed.matched !== true
        || observed.snapshot.session?.runtime_instance_id !== runtime
        || firstDifference(restFacts(native.snapshot, native.deckRead), row.facts)
        || firstDifference(restFacts(observed.snapshot, observed.deckRead), row.facts)
        || firstDifference(observed.facts, row.facts))
      throw new Error(`Saved public rest observation differs at ${i}`);
    if (i === operations.length) {
      if (row.action !== null) throw new Error("Final rest observation unexpectedly has an action");
      continue;
    }
    const nativeAction = chooseRestAction(native.snapshot, operations[i]);
    const matches = observed.snapshot.bound_actions.actions.filter((action) =>
      !firstDifference(restActionKey(observed.snapshot, action), row.action));
    if (!row.action || firstDifference(restActionKey(native.snapshot, nativeAction), row.action) || matches.length !== 1)
      throw new Error(`Saved rest action does not bind uniquely at ${i}`);
    checkReceipt(matches[0]);
    if (matches[0].verb === "select") {
      const step = shipped.upgrade_ui_steps[0];
      if (step.index !== i || step.public_game_facts_unchanged !== true
          || firstDifference(step.before, observed.snapshot)
          || firstDifference(step.selected_action, matches[0]))
        throw new Error("Saved upgrade selection has no matching preview evidence");
      const confirm = upgradePreviewConfirmation(step.before, observed.deckRead, step.preview, step.deckRead,
        plan[i + 1].facts.player.deck[0]);
      if (step.preview.session?.runtime_instance_id !== runtime || firstDifference(confirm, step.confirm_action))
        throw new Error("Saved upgrade confirmation belongs to another preview");
      checkReceipt(confirm);
    }
  }
  const initial = plan[0].facts, final = plan.at(-1).facts;
  if (receiptIndex !== ledger.length || firstDifference(shipped.starting_snapshot, shipped.comparisons[0].snapshot)
      || firstDifference(shipped.latest_snapshot, shipped.comparisons.at(-1).snapshot)
      || initial.kind !== "rest_site" || initial.player.hp !== 25 || initial.player.max_hp !== 80
      || initial.player.deck.length !== 1 || initial.player.deck[0].definition_id !== "STRIKE_IRONCLAD"
      || initial.player.deck[0].is_upgraded !== false || initial.run.ascension !== 8
      || !initial.player.relics.some((row) => row.definition_id === "MINIATURE_TENT")
      || final.kind !== "map_navigation" || final.player.hp !== 49
      || final.player.deck.length !== 1 || final.player.deck[0].is_upgraded !== true)
    throw new Error("Saved rest fixture effects or ledger are incomplete");
  return { compared_snapshots: 7, semantic_actions_delivered: 6, public_actions_delivered: 7, upgrade_ui_steps: 1,
    ...(freshTutorial ? { rest_tutorial_steps: 1 } : {}) };
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  let input = ""; for await (const chunk of process.stdin) input += chunk.toString();
  const result = JSON.parse(input).map((item) => verifySavedRest(item.scenario, item.plan,
    readFileSync(item.native_snapshots, "utf8").trim().split("\n").map((line) => JSON.parse(line)), item.shipped, item.fresh_tutorial === true));
  console.log(JSON.stringify(result));
}
