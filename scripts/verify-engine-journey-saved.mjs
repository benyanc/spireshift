// Pure saved-data audit. Imports no process launcher, network client or game runtime.
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import path from "node:path";
import { actionKey, firstDifference, journeyFacts, tutorialGameFacts } from "./engine-journey-contract-v2.mjs";
import { tutorialAction } from "./engine-journey-tutorial-v4.mjs";

export function verifySavedJourney(plan, nativeSnapshots, shipped) {
  if (!Array.isArray(plan) || plan.length < 4 || plan.length > 13
      || nativeSnapshots.length !== plan.length || shipped.comparisons?.length !== plan.length
      || shipped.public_actions_requested !== plan.length - 1 || shipped.tutorial_steps?.length !== 3)
    throw new Error("Incomplete saved first-turn evidence");
  for (let i = 0; i < plan.length; i++) {
    const row = plan[i], native = nativeSnapshots[i], observed = shipped.comparisons[i];
    if (firstDifference(journeyFacts(native), row.facts)
        || observed.index !== i || observed.matched !== true
        || firstDifference(journeyFacts(observed.snapshot), row.facts)
        || firstDifference(observed.facts, row.facts))
      throw new Error(`Saved public observation differs at ${i}`);
    if (i < plan.length - 1) {
      for (const snapshot of [native, observed.snapshot]) {
        const matches = snapshot.bound_actions.actions.filter((action) => !firstDifference(actionKey(snapshot, action), row.action));
        if (row.action == null || matches.length !== 1) throw new Error(`Saved action does not bind at ${i}`);
      }
    } else if (row.action !== null || row.facts.combat?.round !== 2) {
      throw new Error("Saved prefix has no complete second turn");
    }
  }
  for (let i = 0; i < 3; i++) {
    const step = shipped.tutorial_steps[i];
    tutorialAction(step.before);
    if (step.before.interaction.content.surface.current_page !== i + 1
        || step.game_facts_unchanged !== true
        || firstDifference(tutorialGameFacts(step.before), tutorialGameFacts(step.after)))
      throw new Error("Saved tutorial changed public game facts");
  }
  if (shipped.receipts?.some((row) => row.delivery !== "delivered")
      || shipped.receipts?.length !== shipped.menu_actions_requested + shipped.public_actions_requested)
    throw new Error("Saved delivery ledger is incomplete");
  return { compared_snapshots: plan.length, public_actions_delivered: plan.length - 1, tutorial_steps: 3 };
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  let input = ""; for await (const chunk of process.stdin) input += chunk.toString();
  const cases = JSON.parse(input);
  const result = cases.map((item) => verifySavedJourney(item.plan,
    readFileSync(item.native_snapshots, "utf8").trim().split("\n").map((line) => JSON.parse(line)), item.shipped));
  console.log(JSON.stringify(result));
}
