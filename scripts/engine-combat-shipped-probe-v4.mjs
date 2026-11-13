// Replay one finite public prefix through the real game; stop at the first divergence.
import { spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { completePublicMenu, validateLoadedIdentity } from "./engine-menu-probe.mjs";
import { startingOptions } from "./engine-checkpoint-shipped-probe.mjs";
import { combatActionKey, firstDifference, combatBridgeFacts, verifyCombatSignals } from "./engine-combat-bridge-contract-v6.mjs";

import { shuffleTutorialAction } from "./engine-combat-shuffle-v1.mjs";

import { tutorialAction } from "./engine-journey-tutorial-v4.mjs";

const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function main(spec) {
  const { EnvironmentControllerSession, PlayerEnvironmentRestClient } = await import(pathToFileURL(
    path.join(spec.toolchain, "node_modules/@rsgcsg/sts2-connector-client/dist/index.js")).href);
  const client = new PlayerEnvironmentRestClient(spec.endpoint, 2500);
  const started = Date.now(), deadline = started + spec.max_wall_seconds * 1000;
  const result = { checks: {}, menu_actions_requested: 0, public_actions_requested: 0,
    shutdown_requested: false, training_allowed: false, comparisons: [], receipts: [], tutorial_steps: [], shuffle_steps: [], deliveries: [] };
  let runtimeId, session;
  const check = (name, ok) => { result.checks[name] = ok === true; if (!ok) throw new Error(`Journey gate failed: ${name}`); };
  try {
    let capabilities;
    while (Date.now() < deadline) {
      process.kill(spec.expected_pid, 0);
      try { capabilities = (await client.capabilities()).data; break; }
      catch { await pause(250); }
    }
    if (!capabilities) throw new Error("No exact shipped Host before the cap");
    runtimeId = capabilities.host.runtime_instance_id; result.capabilities = capabilities;
    check("loaded_identity", validateLoadedIdentity(capabilities, spec));
    const endpoint = new URL(spec.endpoint);
    check("loopback_endpoint", endpoint.hostname === "127.0.0.1" && endpoint.protocol === "http:"
      && endpoint.pathname === "/" && endpoint.port && !endpoint.username && !endpoint.password && !endpoint.search && !endpoint.hash);
    const owned = spawnSync("/usr/sbin/lsof", ["-nP", `-iTCP:${endpoint.port}`, "-sTCP:LISTEN", "-Fp"], { encoding: "utf8", timeout: 2000 });
    check("endpoint_owned_by_child", owned.status === 0
      && JSON.stringify(owned.stdout?.split("\n").filter((row) => /^p\d+$/u.test(row))) === JSON.stringify([`p${spec.expected_pid}`]));
    session = new EnvironmentControllerSession(client, { productId: "spireshift-combat-effects-qualification",
      productName: "SpireShift Combat Effects Comparison", productVersion: "1" });
    await session.register(capabilities.host, capabilities.control);
    const stable = async (previous = null) => {
      while (Date.now() < deadline) {
        const current = (await client.observe()).data; result.latest_snapshot = current;
        if (completePublicMenu(current, runtimeId) && current.snapshot_id !== previous) return current;
        await pause(150);
      }
      throw new Error("No fresh complete decision before the cap");
    };
    const submit = async (snapshot, action, menu = false) => {
      const receipt = (await client.submit({ requestId: `journey-${randomUUID()}`,
        expectedSnapshotId: snapshot.snapshot_id, boundActionId: action.bound_action_id,
        ...await session.credentials() })).data;
      result.receipts.push(receipt);
      result.deliveries.push({before:snapshot,receipt,menu});
      if (menu) result.menu_actions_requested++; else result.public_actions_requested++;
      if (receipt.delivery !== "delivered" || receipt.attribution?.runtime_instance_id !== runtimeId)
        throw new Error(`Journey delivery ${receipt.delivery}; no retry`);
      return stable(snapshot.snapshot_id);
    };
    let snapshot = await stable();
    for (let i = 0; i < 8 && snapshot.interaction.kind !== "event_option"; i++) {
      if (!["main_menu", "singleplayer_menu"].includes(snapshot.interaction.kind)) throw new Error("Unqualified checkpoint entry");
      const continueAction = snapshot.bound_actions.actions.find((item) => /continue|resume/i.test(item.label));
      if (continueAction) check("native_continue_offered", true);
      const action = continueAction ?? snapshot.bound_actions.actions.find((item) => /single ?player|play/i.test(item.label));
      if (!action) throw new Error("No exact checkpoint entry action");
      snapshot = await submit(snapshot, action, true);
    }
    result.starting_snapshot = snapshot;
    check("native_checkpoint_loaded", result.checks.native_continue_offered === true && snapshot.interaction.kind === "event_option");
    check("complete_public_starting_event", completePublicMenu(snapshot, runtimeId));
    const provenance = await fetch(`${spec.endpoint}/api/host-control/provenance`, { method: "POST",
      headers: { "content-type": "application/json" }, body: JSON.stringify({ expected_runtime_instance_id: runtimeId,
        host_control_token: spec.host_control_token }), signal: AbortSignal.timeout(3000) });
    result.native_provenance = await provenance.json();
    check("native_A8_seed_preserved", provenance.ok && result.native_provenance.actual_seed === spec.fixture.seed
      && result.native_provenance.runtime_instance_id === runtimeId && snapshot.persistent.content.run.ascension === 8);
    const original = JSON.parse(readFileSync(spec.fixture.snapshot_path, "utf8"));
    result.starting_options_comparison = { managed: startingOptions(original), shipped: startingOptions(snapshot) };
    check("same_starting_public_option_titles_and_availability", result.starting_options_comparison.managed != null
      && firstDifference(result.starting_options_comparison.managed, result.starting_options_comparison.shipped) == null);
    check("native_current_act_preserved",snapshot.persistent.content.run.act_definition_id===original.persistent.content.run.act_definition_id);
    const plan = JSON.parse(readFileSync(spec.fixture.combat_report_path, "utf8")).probe.journey;
    const readDeck=async current=>{
      const descriptor=current.reads.find(row=>row.kind==="run_deck");
      if(!descriptor)throw Error("No complete public deck descriptor");
      return (await client.read(descriptor.read_id,current.snapshot_id)).data;
    };
    for(let i=0;i<plan.length;i++) {
      if(snapshot.interaction.kind==="tutorial" && snapshot.interaction.content.surface.tutorial_id==="shuffle_ftue") {
        if(i!==plan.length-1)throw Error("Shuffle pause occurred outside the frozen second-turn boundary");
        const before=snapshot,beforeDeck=await readDeck(before),action=shuffleTutorialAction(before);
        snapshot=await submit(before,action,true);
        const afterDeck=await readDeck(snapshot),facts=combatBridgeFacts(snapshot,afterDeck);
        const difference=firstDifference(plan[i].facts,facts);
        result.shuffle_steps.push({before,beforeDeck,after:snapshot,afterDeck,pending_draw_resumed:difference==null});
        if(difference){result.first_divergence={index:i,shuffle:true,...difference};throw Error("Shuffle resume differs from native second turn");}
      }
      for(let page=0;snapshot.interaction.kind==="tutorial" && page<3;page++) {
        const before=snapshot,beforeDeck=await readDeck(before),action=tutorialAction(before);
        const underlying=combatBridgeFacts(before,beforeDeck,{tutorial:true});
        const expected={...plan[i].facts};delete expected.actions;
        const initialDifference=firstDifference(expected,underlying);
        if(initialDifference){result.first_divergence={index:i,tutorial:true,...initialDifference};throw Error("Tutorial game facts differ");}
        snapshot=await submit(before,action,true);
        const afterDeck=await readDeck(snapshot);
        const after=combatBridgeFacts(snapshot,afterDeck,{tutorial:snapshot.interaction.kind==="tutorial"});delete after.actions;
        const difference=firstDifference(underlying,after);
        result.tutorial_steps.push({before,beforeDeck,after:snapshot,afterDeck,game_facts_unchanged:difference==null});
        if(difference){result.first_divergence={index:i,tutorial:true,...difference};throw Error("Tutorial changed game facts");}
      }
      const row={index:i,snapshot,deckRead:await readDeck(snapshot),matched:false};result.comparisons.push(row);
      row.facts=combatBridgeFacts(snapshot,row.deckRead);
      const difference=firstDifference(plan[i].facts,row.facts);
      if(difference){result.first_divergence={index:i,...difference};throw Error("Public combat facts differ");}
      row.matched=true;
      if(plan[i].action==null)break;
      const matches=snapshot.bound_actions.actions.filter(action=>firstDifference(combatActionKey(snapshot,action),plan[i].action)==null);
      if(matches.length!==1)throw Error("Current combat action binding is not unique");
      row.action=combatActionKey(snapshot,matches[0]);
      snapshot=await submit(snapshot,matches[0]);
    }
    check("combat_all_snapshots_match",result.comparisons.length===plan.length && result.comparisons.every(row=>row.matched));
    check("combat_all_actions_delivered",result.public_actions_requested===plan.length-1);
    result.effect_checks=verifyCombatSignals(result.comparisons.map((row,index)=>({facts:row.facts,action:plan[index].action})),spec.fixture.scenario);
    check("combat_effect_signals_verified",Object.values(result.effect_checks).every(value=>value===true));
    check("combat_fresh_tutorials_preserve_facts",result.tutorial_steps.length===3 && result.tutorial_steps.every(row=>row.game_facts_unchanged)
      && result.shuffle_steps.length===1 && result.shuffle_steps[0].pending_draw_resumed===true);
  } catch (error) { result.error = error.message; }
  finally {
    if (session) await session.close();
    if (runtimeId) {
      try {
        const response = await fetch(`${spec.endpoint}/api/host-control/shutdown`, { method: "POST",
          headers: { "content-type": "application/json" }, body: JSON.stringify({ expected_runtime_instance_id: runtimeId,
            host_control_token: spec.host_control_token }), signal: AbortSignal.timeout(3000) });
        result.shutdown_requested = response.ok && (await response.json()).status === "shutdown_requested";
      } catch (error) { result.shutdown_error = error.message; }
    }
    result.wall_seconds = (Date.now() - started) / 1000;
    writeFileSync(path.join(spec.attempt, "checkpoint-control.json"), `${JSON.stringify(result, null, 2)}\n`);
  }
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  let input = ""; for await (const chunk of process.stdin) input += chunk.toString(); await main(JSON.parse(input));
}
