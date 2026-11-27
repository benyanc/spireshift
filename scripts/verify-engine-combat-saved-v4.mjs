// Pure reconstruction from saved observations and receipts; never a game replay.
import { readFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { completePublicMenu } from "./engine-menu-probe.mjs";
import { combatBridgeFacts,combatActionKey,firstDifference,verifyCombatSignals } from "./engine-combat-bridge-contract-v6.mjs";
import { shuffleTutorialAction } from "./engine-combat-shuffle-v1.mjs";
import { tutorialAction } from "./engine-journey-tutorial-v4.mjs";
const same=(a,b)=>firstDifference(a,b)==null;
function delivered(snapshot,receipt,runtime=null) {
  if(!completePublicMenu(snapshot,snapshot.session?.runtime_instance_id) || receipt?.delivery!=="delivered"
      || runtime!=null && receipt.attribution?.runtime_instance_id!==runtime)throw Error("Missing or unbound combat delivery");
  const offers=snapshot.bound_actions.actions.filter(row=>row.bound_action_id===receipt.action?.bound_action_id);
  if(offers.length!==1 || ["verb","subject_referent_id","arguments"].some(key=>!same(offers[0][key],receipt.action[key])))
    throw Error("Combat receipt differs from the actual offered action");
  return offers[0];
}
export function verifyCombatEvidence(native,snapshots,shipped,scenario) {
  const plan=native.probe.journey,actual=shipped.probe.comparisons,probe=shipped.probe;
  const runtime=probe.capabilities.host.runtime_instance_id,nativeRuntime=`combat-bridge-${native.probe.runtime_identity.process_id}`;
  if(!Array.isArray(plan) || plan.length<8 || plan.length>21 || snapshots.length!==plan.length
      || actual.length!==plan.length || native.probe.receipts.length!==plan.length-1)
    throw Error("Incomplete combat prefix denominator");
  for(let i=0;i<plan.length;i++) {
    if(!completePublicMenu(snapshots[i].snapshot,nativeRuntime) || !completePublicMenu(actual[i].snapshot,runtime))
      throw Error("Combat snapshot belongs to a different runtime");
    const expected=combatBridgeFacts(snapshots[i].snapshot,snapshots[i].deckRead),facts=combatBridgeFacts(actual[i].snapshot,actual[i].deckRead);
    if(!same(expected,plan[i].facts) || !same(facts,actual[i].facts) || !same(expected,facts) || actual[i].matched!==true)
      throw Error("Saved combat facts do not reconstruct from raw observations");
    if(i<plan.length-1) {
      const receipt=native.probe.receipts[i],offered=delivered(snapshots[i].snapshot,receipt);
      if(!same(combatActionKey(snapshots[i].snapshot,offered),plan[i].action)
          || !same(receipt.successor,snapshots[i+1].snapshot))throw Error("Native combat delivery or successor changed");
    } else if(plan[i].action!==null)throw Error("Combat prefix must end before another action");
  }
  if(new Set(native.probe.receipts.map(row=>row.request_id)).size!==plan.length-1
      || !same(verifyCombatSignals(plan,scenario),native.probe.effect_checks)
      || !same(verifyCombatSignals(actual.map((row,i)=>({facts:row.facts,action:plan[i].action})),scenario),probe.effect_checks))
    throw Error("Combat signal or native receipt identity changed");
  if(probe.deliveries.length!==probe.receipts.length || new Set(probe.receipts.map(row=>row.request_id)).size!==probe.receipts.length)
    throw Error("Shipped combat receipt denominator changed");
  const effects=[];
  for(let i=0;i<probe.deliveries.length;i++) {
    const step=probe.deliveries[i];if(!same(step.receipt,probe.receipts[i]))throw Error("Shipped delivery record changed");
    const action=delivered(step.before,step.receipt,runtime);
    if(step.menu!==true)effects.push({snapshot:step.before,action});
  }
  if(effects.length!==plan.length-1 || probe.public_actions_requested!==effects.length
      || probe.menu_actions_requested!==probe.receipts.length-effects.length)
    throw Error("Shipped combat effect/action denominator changed");
  effects.forEach((step,i)=>{
    if(!same(step.snapshot,actual[i].snapshot) || !same(combatActionKey(step.snapshot,step.action),plan[i].action)
        || !same(actual[i].action,plan[i].action))throw Error("Shipped combat action differs from its current observation");
  });
  if(probe.tutorial_steps.length!==3)throw Error("Missing fresh combat tutorial steps");
  for(const step of probe.tutorial_steps) {
    const action=tutorialAction(step.before),before=combatBridgeFacts(step.before,step.beforeDeck,{tutorial:true});
    const after=combatBridgeFacts(step.after,step.afterDeck,{tutorial:step.after.interaction.kind==="tutorial"});delete after.actions;
    if(!same(before,after) || !probe.deliveries.some(d=>d.before.snapshot_id===step.before.snapshot_id
        && d.receipt.action.bound_action_id===action.bound_action_id && d.menu===true))throw Error("Combat tutorial evidence changed");
  }
  if(probe.shuffle_steps?.length!==1)throw Error("Missing fresh shuffle continuation");
  const shuffle=probe.shuffle_steps[0],shuffleAction=shuffleTutorialAction(shuffle.before);
  if(!same(combatBridgeFacts(shuffle.after,shuffle.afterDeck),plan.at(-1).facts)
      || !probe.deliveries.some(d=>d.before.snapshot_id===shuffle.before.snapshot_id
        && d.receipt.action.bound_action_id===shuffleAction.bound_action_id && d.menu===true))
    throw Error("Shuffle receipt or resumed native draw changed");
  if(probe.native_provenance.actual_seed!==native.probe.checkpoint.seed || probe.native_provenance.runtime_instance_id!==runtime)
    throw Error("Combat seed/runtime provenance changed");
  return {valid:true,observations:plan.length,effect_decisions:effects.length,
    public_game_ui_actions:probe.receipts.length,tutorial_steps:3,shuffle_steps:1,games_launched:0,training_allowed:false};
}
if(process.argv[1] && import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href) {
  let input="";for await(const chunk of process.stdin)input+=chunk.toString();const spec=JSON.parse(input);
  const json=file=>JSON.parse(readFileSync(file,"utf8"));
  const snapshots=readFileSync(spec.snapshots,"utf8").trim().split("\n").map(JSON.parse);
  process.stdout.write(JSON.stringify(verifyCombatEvidence(json(spec.native),snapshots,json(spec.shipped),spec.scenario))+"\n");
}
