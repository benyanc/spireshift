// Reconstruct frozen public pickup/capacity evidence and exact action deliveries. No game launch.
import { readFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { completePublicMenu } from "./engine-menu-probe.mjs";
import { rewardFacts, rewardActionKey, chooseRewardAction, verifyRewardEffects, firstDifference } from "./engine-reward-bridge-contract-v1.mjs";
import { shopPersistentFacts, shopRoomAction } from "./engine-shop-bridge-contract.mjs";
import { rewardTutorialAction, verifyRewardTutorial } from "./engine-reward-tutorial-v2.mjs";
const check = (ok, message) => { if (!ok) throw Error(message); };
const delivered = (action) => ({ verb:action?.verb,bound_action_id:action?.bound_action_id,
  subject_referent_id:action?.subject_referent_id??null,arguments:action?.arguments });
export function verifyRewardEvidence(native, shipped, raw, scenario) {
  const plan=native.probe.journey, probe=shipped.probe, runtime=probe.capabilities.host.runtime_instance_id;
  check(Array.isArray(plan) && plan.length>=3 && plan.length<=12 && raw.length===plan.length
    && probe.comparisons.length===plan.length,"Incomplete raw reward prefix denominator");
  check(plan.at(-1).action===null && plan.slice(0,-1).every(row=>row.action),"Uncommitted reward prefix");
  for(let i=0;i<plan.length;i++) {
    const source=raw[i], actual=probe.comparisons[i];
    check(completePublicMenu(source.snapshot,`reward-bridge-${native.probe.runtime_identity.process_id}`),"Unbound native reward snapshot");
    check(completePublicMenu(actual.snapshot,runtime),"Unbound shipped reward snapshot");
    const facts=rewardFacts(source.snapshot,source.deckRead), observed=rewardFacts(actual.snapshot,actual.deckRead);
    check(!firstDifference(facts,plan[i].facts) && !firstDifference(observed,actual.facts)
      && !firstDifference(facts,observed),"Raw reward facts do not reconstruct or differ between hosts");
    if(plan[i].action) {
      const action=chooseRewardAction(source.snapshot,plan[i].action);
      check(!firstDifference(rewardActionKey(source.snapshot,action),plan[i].action),"Native action intent lacks its current public binding");
    }
  }
  check(Number.isSafeInteger(probe.menu_actions_requested) && probe.menu_actions_requested>=1
    && probe.menu_actions_requested<=2,"Unexpected menu entry denominator");
  let receiptIndex=probe.menu_actions_requested;
  const checkReceipt=(action)=>check(!firstDifference(delivered(action),delivered(probe.receipts[receiptIndex++]?.action)),"Reward receipt differs from the current public action");
  check(probe.entry_steps.length===(scenario.startsWith("cauldron")?1:0),"Unexpected pickup owner entry steps");
  for(const step of probe.entry_steps) {
    check(step.kind==="open_inventory" && completePublicMenu(step.before,runtime) && completePublicMenu(step.after,runtime),"Unbound shop entry");
    check(!firstDifference(step.before,probe.starting_snapshot) && !firstDifference(step.after,probe.comparisons[0].snapshot),"Shop entry has a different source or successor");
    check(!firstDifference(shopPersistentFacts(step.before,step.beforeDeck),shopPersistentFacts(step.after,step.afterDeck)),"Shop entry changed public ownership");
    checkReceipt(shopRoomAction(step.before,"open"));
  }
  const tutorialIndices=new Set();
  for(let i=0;i<plan.length;i++) {
    const steps=probe.tutorial_steps.filter(step=>step.index===i);
    check(steps.length<=1,"Duplicate first-potion tutorial step");
    if(steps.length) {
      const step=steps[0]; tutorialIndices.add(i);
      check(i>0 && completePublicMenu(step.before,runtime) && completePublicMenu(step.after,runtime),"Unbound potion tutorial");
      const expectedId=scenario.startsWith("calling-bell")?"obtain_relic_ftue":"obtain_potion_ftue";
      verifyRewardTutorial(step.before,step.beforeDeck,step.after,step.afterDeck,expectedId);
      check(!firstDifference(step.after,probe.comparisons[i].snapshot),"Tutorial has a different semantic successor");
      check(!firstDifference(step.action,rewardTutorialAction(step.before,expectedId)),"Unqualified tutorial action"); checkReceipt(step.action);
    }
    if(plan[i].action) checkReceipt(chooseRewardAction(probe.comparisons[i].snapshot,plan[i].action));
  }
  check(tutorialIndices.size===probe.tutorial_steps.length
    && tutorialIndices.size===1,"Missing or extra fresh potion tutorial");
  check(probe.semantic_actions_delivered===plan.length-1 && probe.receipts.length===receiptIndex
    && probe.public_actions_requested===plan.length-1+probe.entry_steps.length+probe.tutorial_steps.length
    && probe.receipts.every(row=>row.delivery==="delivered" && row.request_id
      && row.attribution?.runtime_instance_id===runtime)
    && new Set(probe.receipts.map(row=>row.request_id)).size===probe.receipts.length,"Incomplete or unbound reward delivery receipts");
  verifyRewardEffects(scenario,plan);
  verifyRewardEffects(scenario,probe.comparisons.map((row,i)=>({facts:rewardFacts(row.snapshot,row.deckRead),action:plan[i].action})));
  return {valid:true,observations:plan.length,effect_decisions:plan.length-1,
    public_game_ui_actions:probe.public_actions_requested,tutorial_steps:probe.tutorial_steps.length,
    games_launched:0,training_allowed:false};
}
if(process.argv[1] && import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href) {
  let input=""; for await(const chunk of process.stdin) input+=chunk.toString(); const spec=JSON.parse(input);
  const native=JSON.parse(readFileSync(spec.native_report,"utf8")), shipped=JSON.parse(readFileSync(spec.shipped_report,"utf8"));
  const raw=readFileSync(spec.native_snapshots,"utf8").trim().split("\n").map(row=>JSON.parse(row));
  process.stdout.write(JSON.stringify(verifyRewardEvidence(native,shipped,raw,spec.scenario))+"\n");
}
